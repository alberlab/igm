import os
import os.path
import time
import traceback
import multiprocessing

POLL_INTERVAL = 30  # check 30 seconds


class GeneratorLen(object):
    def __init__(self, gen, length):
        self.gen = gen
        self.length = length

    def __len__(self):
        return self.length

    def __iter__(self):
        return self.gen


class FilePoller(object):

    """ Define polling function """

    def __init__(self, files, callback, args=None, kwargs=None, remove_after_callback=False,
                 setup=None, setup_args=tuple(), setup_kwargs=dict(),
                 teardown=None, teardown_args=tuple(), teardown_kwargs=dict()):
        self._manager = multiprocessing.Manager()

        self.files = files
        self.args = args
        if args is None:
            self.args = [list()] * len(files)

        self.kwargs = kwargs
        if kwargs is None:
            self.kwargs = [dict()] * len(files)

        self.callback = callback

        self.th = None

        self.remove_flag = remove_after_callback
        self.completed = self._manager.list()
        self.setup = setup
        self.setup_args = setup_args
        self.setup_kwargs = setup_kwargs
        self.teardown = teardown
        self.teardown_args = teardown_args
        self.teardown_kwargs = teardown_kwargs
        self._traceback = self._manager.list()

    # watch function, which scans over the 'to_poll' list
    def watch(self, completed, tb, timeout=None, interval=POLL_INTERVAL):
        try:
            if self.setup:
                self.setup(*self.setup_args, **self.setup_kwargs)
            to_poll = set(range(len(self.files)))
            start = time.time()
            while True:
                last_poll = time.time()
                for i in list(to_poll):
                    if os.path.isfile(self.files[i]):
                        self.callback(*self.args[i], **self.kwargs[i])
                        if self.remove_flag:
                            os.remove(self.files[i])
                        to_poll.remove(i)
                        completed.append(i)

                if len(to_poll) == 0:
                    break

                now = time.time()
                if timeout is not None:
                    if now - start > timeout:
                        raise RuntimeError('Timeout expired (%f seconds)' % (timeout,))

                delta = now - last_poll
                if delta < interval:
                    time.sleep(interval - delta)

        except KeyboardInterrupt:
            pass

        except:
            tb.append(traceback.format_exc())

        finally:
            if self.teardown:
                try:
                    self.teardown(*self.teardown_args, **self.teardown_kwargs)
                except:
                    stb = traceback.format_exc()
                    try:
                        # the tb manager could already be down
                        tb.append(stb)
                    except:
                        print(stb)    
                    
    def watch_async(self, timeout=None, interval=POLL_INTERVAL):
        self.th = multiprocessing.Process(target=self.watch, args=(self.completed, self._traceback, timeout, interval))
        self.th.start()

    def wait(self, timeout=None):
        self.th.join(timeout)
        if len(self._traceback):
            raise RuntimeError('\n'.join(self._traceback))

    def _enumerate(self):
        lastc = 0
        while True:
            #print('lastdc = ' + str(lastc))     # LB
            if len(self._traceback):
                    self.th.join()
                    raise RuntimeError('\n'.join(self._traceback))

            if lastc == len(self.files):
                if self.th:
                    self.th.join()
                break

            if len(self.completed) > lastc:
                lastc += 1
                yield self.completed[lastc - 1]

            else:
                time.sleep(POLL_INTERVAL)

    def enumerate(self):
        return GeneratorLen(self._enumerate(), len(self.files))
