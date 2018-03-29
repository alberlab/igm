from __future__ import print_function, division 

from dask.distributed import Client

import traceback

from .parallel_controller import ParallelController 

class TimedFunction(object):
    '''
    Utility wrapper for a remote task. Allows to avoid 
    '''
    def __init__(self, func, timeout=None):
        self.func = func
        self.timeout = timeout

    def run(self, *args, **kwargs):
        try:
            from time import time
            tstart = time()
            res = self.func(*args, **kwargs)
            self._q.put( (0, res, time()-tstart) )
        except:
            self._q.put( (-1, traceback.format_exc()) )

    def __call__(self, *args, **kwargs):
        # runs on a child process to terminate execution if timeout exceedes 
        try:
            import multiprocessing
            try:
                from Queue import Empty
            except:
                from queue import Empty
                
            self._q = multiprocessing.Queue()
            p = multiprocessing.Process(target=self.run, args=args, kwargs=kwargs)
            p.start()
            rval = self._q.get(block=True, timeout=self.timeout)
            p.join()
            if rval[0] == -1:
                raise RuntimeError(rval[1])

        except Empty:
            p.terminate()
            raise RuntimeError('Processing time exceeded (%f)' % self.timeout)         

        return rval[1]


class DaskController(ParallelController):
    def __init__(self):
        self.client = None
        super(DaskController, self).__init__()

    def setup(self, cfg):
        if 'ip' not in cfg:
            pass
            # TODO: check some kind of default file
        self.client = Client(cfg['ip'])

    def map(self, parallel_task, args):
        futures = self.client.map(parallel_task, args)
        results = []
        for f in futures:
            results.append(f.result())
        return results

    def reduce(self, reduce_task, outs):
        return reduce_task(outs)
