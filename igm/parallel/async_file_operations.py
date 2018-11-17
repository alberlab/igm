import os
import os.path
import time
import threading
import traceback
import multiprocessing


POLL_INTERVAL = 0.5 # check every half second


class FileLock(object):
    def __init__(self, name):

        self.lockname = os.path.abspath( name + '.lock')
        open(self.lockname,  'w').close()

    def __enter__(self):
        return self.lockname

    def __exit__(self, type, value, traceback):
        os.remove(self.lockname)
        return True

class FutureFile(object):
    def __init__(self, name):
        self.name = os.path.abspath(name)
        self.lockname = os.path.abspath( name + '.lock')

    def ready(self):
        return os.path.isfile(self.name) and not os.path.isfile(self.lockname)

    def wait(self, timeout=None):
        start = time.time()
        while True:
            if self.ready():
                return
            if timeout is not None:
                now = time.time()
                if now - start > timeout:
                    raise RuntimeError('%s is not ready after %f seconds' % (self.name, timeout) )
                time.sleep(POLL_INTERVAL)


class GeneratorLen(object):
    def __init__(self, gen, length):
        self.gen = gen
        self.length = length

    def __len__(self):
        return self.length

    def __iter__(self):
        return self.gen

class FutureFilePoller(object):
    def __init__(self, files, callback, args=None, kwargs=None, remove_after_callback=False):

        self._manager = multiprocessing.Manager()

        self.files = files
        self.args = args
        if args is None:
            self.args = [ list() ] * len(files)

        self.kwargs = kwargs
        if kwargs is None:
            self.kwargs = [ dict() ] * len(files)

        self.callback = callback
        self.futures = [ FutureFile(f) for f in files]
        self.to_poll = {i: None for i in range(len(files))}
        self.running = False
        self.th = None
        self.remove_flag = remove_after_callback
        self.completed = self._manager.list()

    def watch(self, timeout=None, interval=POLL_INTERVAL):
        start = time.time()
        self.running = True
        while True:
            last_poll = time.time()
            for i in list(self.to_poll):
                future = self.futures[i]
                if future.ready():
                    try:
                        self.callback(*self.args[i], **self.kwargs[i])
                        if self.remove_flag:
                            os.remove(self.futures[i].name)
                        del self.to_poll[i]
                        self.completed.append(i)
                    except:
                        # hate to do this, but sometimes the nfs
                        # is not in sync and the callbacks may fail
                        # TODO: set a max_error or something?
                        pass

            if len(self.to_poll) == 0:
                self.running = False
                return

            now = time.time()
            if timeout is not None:
                if now - start > timeout:
                    raise RuntimeError('Timeout expired (%f seconds)' % (timeout,) )

            delta = now - last_poll
            if delta < interval:
                time.sleep(interval - delta)

    def watch_async(self, timeout=None, interval=POLL_INTERVAL):
        self.th = multiprocessing.Process(target=self.watch, args=(timeout, POLL_INTERVAL), daemon=True)
        self.th.start()

    def wait(self, timeout=None):
        self.th.join(timeout)

    def _enumerate(self):
        lastc = 0
        while True:
            if lastc == len(self.futures):
                break
            if len(self.completed) > lastc:
                lastc += 1
                yield self.completed[lastc-1]
            else:
                time.sleep(POLL_INTERVAL)

    def enumerate(self):
        return GeneratorLen(self._enumerate(), len(self.futures))

class FilePoller(object):
    def __init__(self, files, callback, args=None, kwargs=None, remove_after_callback=False,
                 setup=None, setup_args=tuple(), setup_kwargs=dict(),
                 teardown=None, teardown_args=tuple(), teardown_kwargs=dict()):
        self._manager = multiprocessing.Manager()

        self.files = files
        self.args = args
        if args is None:
            self.args = [ list() ] * len(files)

        self.kwargs = kwargs
        if kwargs is None:
            self.kwargs = [ dict() ] * len(files)

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

    def watch(self, completed, tb, timeout=None, interval=POLL_INTERVAL):
        try:
            if self.setup:
                self.setup(*self.setup_args, **self.setup_kwargs)
            to_poll = set( range( len(self.files) ) )
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

        except:
            try:
                tb.append(traceback.format_exc())
            except:
                pass
            pass

        finally:
            if self.teardown:
                self.teardown(*self.teardown_args, **self.teardown_kwargs)

    def watch_async(self, timeout=None, interval=POLL_INTERVAL):
        self.th = multiprocessing.Process(target=self.watch, args=(self.completed, self._traceback, timeout, interval))
        self.th.start()

    def wait(self, timeout=None):
        self.th.join(timeout)
        if len(self._traceback):
            raise RuntimeError(self.traceback)

    def _enumerate(self):
        lastc = 0
        while True:
            if lastc == len(self.files):
                if self.th:
                    self.th.join()
                break

            if len(self.completed) > lastc:
                lastc += 1
                yield self.completed[lastc - 1]

            else:
                if len(self._traceback):
                    raise RuntimeError(self.traceback)
                time.sleep(POLL_INTERVAL)

    def enumerate(self):
        return GeneratorLen(self._enumerate(), len(self.files))
