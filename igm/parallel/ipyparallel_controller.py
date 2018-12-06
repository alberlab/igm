from __future__ import print_function, division

import threading
import multiprocessing
import traceback
import os
import sys
import zmq
import sqlite3
import time
import six
from .parallel_controller import ParallelController
from ..utils.log import logger
from tqdm import tqdm

#from .globals import default_log_formatter
#log_fmt = '[%(name)s] %(asctime)s (%(levelname)s) %(message)s'
#default_log_formatter = logging.Formatter(log_fmt, '%d %b %Y %H:%M:%S')

class IppFunctionWrapper(object):
    def __init__(self, inner, timeout=None):
        self.inner = inner
        self.timeout = timeout

    def run(self, *args, **kwargs):
        try:
            from time import time
            tstart = time()
            res = self.inner(*args, **kwargs)
            self._q.put( (0, res, time()-tstart) )
        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            tb_str = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            self._q.put( (-1, tb_str, None) )

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
        except Empty:
            rval = (-1, 'Processing time exceeded (%f)' % self.timeout, None)
            p.terminate()
        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            tb_str = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            rval = (-1, tb_str, None)
        return rval



class BasicIppController(ParallelController):
    def __init__(self, timeout=None, max_tasks=-1):
        self.max_tasks = max_tasks
        self.timeout=timeout

    def map(self, parallel_task, args):
        from ipyparallel import Client, TimeoutError

        chunksize = 1
        if self.max_tasks > 0 and len(args) > self.max_tasks:
            chunksize = len(args) // self.max_tasks
            if chunksize*self.max_tasks < len(args):
                chunksize += 1
        client = None
        try:
            client = Client()
        except TimeoutError:
            raise RuntimeError('Cannot connect to the ipyparallel client. Is it running?')
        
        ar = None
        try:
            client[:].use_cloudpickle()
            lbv = client.load_balanced_view()
            ar = lbv.map_async(
                IppFunctionWrapper(parallel_task, self.timeout),
                args,
                chunksize=chunksize
            )
            try:
                r = []
                for k, z in enumerate(tqdm(ar, desc="(IPYPARALLEL)", total=len(args))):
                    if z[0] == -1:
                        logger.error(z[1])
                        engine = ar.engine_id[k]
                        client.abort(ar)
                        client.close()
                        raise RuntimeError('remote failure (task %d of %d on engine %d)' % (k+1, len(ar), engine))
                    elif z[0] == 0:
                        r.append(z[1])
            except KeyboardInterrupt:
                client.abort(ar)
                raise
        finally:
            # always close the client to release resources
            if ar:
                client.abort(ar)
            if client:
                client.close()
        return r

class BasicAsyncIppController(BasicIppController):
    def map(self, parallel_task, args):
        return self.lbv.map_async(parallel_task, args)

def pretty_tdelta(seconds):
    '''
    Prints the *seconds* in the format h mm ss
    '''
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return "%dh %02dm %02ds" % (h, m, s)

#TODO: execution time



class AdvancedIppController(ParallelController):
    '''
    A wrapper class to deal with monitoring and logging
    parallel jobs activity.

    Note that functions should -at least for now- accept only one parameter,
    (which could be a structure anyway).
    '''
    NOT_STARTED = None
    FAILED = -1
    RUNNING = 0
    SUCCESS = 1

    def __init__(self,
                 name='ParallelController',
                 serial_fun=None,
                 args=None,
                 const_vars=None,
                 chunksize=1,
                 logfile=None,
                 loglevel=None,
                 poll_interval=60,
                 max_batch=None,
                 max_exec_time=None,
                 dbfile=None,
                 fresh_run=False,
                 retry=3,
                 commit_timeout=30):

        self.name = name
        self._serial_fun = serial_fun # serial function to be mapped
        self._args = args # arguments to be mapped
        self.const_vars = const_vars # consts for the function
        self.chunksize = chunksize
        self.logfile = logfile
        self.loglevel = loglevel
        self.poll_interval = poll_interval # poll for status every
                                           # poll_interval seconds
        self.results = []
        self._status = []
        self._to_process = []
        self._ok = False # flag for successfull completion
        self.chunksize
        self._client = None # ipyparallel client
        self._view = None # ipyparallel load balanced view
        self._logger = None # logger
        self._ar = None # async results
        #self._fwrapper = None # function wrapper
        self._max_batch = max_batch
        self.max_exec_time = max_exec_time
        self.retry = retry
        self._queue = multiprocessing.Queue()
        self.commit_timeout = commit_timeout
        if self._args is None:
            self._args = list()
        if self.const_vars is None:
            self.const_vars = dict()
        if dbfile is None:
            self.dbfile = '%s.db' % name
        else:
            self.dbfile = dbfile
        if fresh_run:
            if os.path.isfile(self.dbfile):
                os.remove(self.dbfile)

    def get_status(self):
        return self._status

    def set_function(self, value):
        self._serial_fun = value

    def get_function(self):
        return self._serial_fun

    def set_const(self, name, val):
        self.const_vars[name] = val

    def set_args(self, args):
        self._args = args
        self._status = [AdvancedIppController.NOT_STARTED] * len(args)
        self.results = [None] * len(self._args)

    def get_args(self):
        return self._args

    def _setup_logger(self, batch_no=None):
        # setup logger
        if batch_no is None:
            self._logger = logging.getLogger(self.name)
        else:
            self._logger = logging.getLogger(self.name + '/batch%d' % batch_no )
        # keep only stream handlers
        fnames = [fh.baseFilename for fh in self._logger.handlers]

        if self.logfile is not None and self.logfile not in fnames:
            fh = logging.FileHandler(self.logfile)
            fh.setFormatter(default_log_formatter)
            self._logger.addHandler(fh)
        self._logger.setLevel(self.loglevel)

        # prepare the remote function
        #self._fwrapper = FunctionWrapper(self._serial_fun, self.const_vars)

    def _setup_ipp(self):
        # get client and view instances, and use cloudpickle
        from ipyparallel import Client
        self._client = Client(context=zmq.Context())
        self._ids = self._client.ids
        self._dview = self._client[self._ids]
        self._dview.use_cloudpickle()
        self._view = self._client.load_balanced_view(targets=self._ids)

    def _cleanup(self):
        if self._client:
            self._client.close()

    def _handle_errors(self):
        failed = [i for i, x in enumerate(self._status)
                  if x == AdvancedIppController.FAILED]
        n_failed = len(failed)
        self._logger.error('%d tasks have failed.', n_failed)
        print('%s: %d tasks have failed.' % (self.name, n_failed),
              file=sys.stderr)
        for cnt, i in enumerate(failed):
            if cnt > 2:
                self._logger.error('... %d more errors ...', n_failed - 3)
                print('... %d more errors ...' % (n_failed - 3),
                      file=sys.stderr)
                break
            self._logger.error('JOB# %d:\n %s \n' + '-'*40, i,
                               self.results[i])
            print('JOB# %d:\n %s' % (i, self.results[i]),
                  file=sys.stderr)
            print('-'*40, file=sys.stderr)
        return n_failed

    def _split_batches(self):
        if self._max_batch is None:
            return [(0, len(self._to_process))]
        else:
            num_batch = len(self._to_process) // self._max_batch
            if len(self._to_process) % self._max_batch != 0:
                num_batch += 1
            return [(b*self._max_batch,
                     min(len(self._to_process), (b+1)*self._max_batch))
                    for b in range(num_batch)]

    def _check_db(self):
        create_table = False if os.path.isfile(self.dbfile) else True

        with sqlite3.connect(self.dbfile) as conn:
            if create_table:
                conn.execute('CREATE TABLE completed (jid INT, '
                    'completed_time INT, run_time REAL)')
            query = 'SELECT jid FROM completed'
            c = conn.execute(query)
            completed = {x[0] for x in c.fetchall()}
            not_completed = set(self._args) - completed
            self._to_process = list(not_completed)
            for i in completed:
                self.results[i] = 0
                self._status[i] = AdvancedIppController.SUCCESS

    def _run_all(self):
        self._setup_logger()
        self.results = [None] * len(self._args)
        self._status = [AdvancedIppController.RUNNING] * len(self._args)
        self._check_db()

        tot_time = 0
        trial = 0
        error_count = 0
        last_commit = time.time()
        self._start_time = time.time()
        with sqlite3.connect(self.dbfile) as conn:
            while trial < self.retry and len(self._to_process):
                now_completed = []
                error_count = 0
                self.job_batches = self._split_batches()
                self._logger.info('Starting %s - %d jobs, divided in %d batches (trial %d)',
                                  self.name, len(self._to_process), len(self.job_batches), trial)
                for batch_no, (batch_start, batch_end) in enumerate(self.job_batches):
                    p = multiprocessing.Process(target=self._run_batch,
                                                args=(batch_no,))
                    p.start()

                    while True:
                        # keep the db file updated, so we can read the situation from outside
                        if time.time() - last_commit > self.commit_timeout:
                            conn.commit()
                            last_commit = time.time()

                        i, result = self._queue.get()
                        if i >= 0:
                            self.results[i] = result
                            if result[0] == -1:
                                error_count += 1
                                self.results[i] = result[1]
                                self._status[i] = AdvancedIppController.FAILED
                            elif result[0] == 0:
                                self._status[i] = AdvancedIppController.SUCCESS
                                self.results[i] = result[1]
                                etime = result[2]
                                conn.execute('INSERT INTO completed VALUES (?, ?, ?)',
                                             (i, int(time.time()), etime))
                                now_completed.append(i)

                        elif i == -2:
                            p.join()
                            raise RuntimeError('Process raised error', result)
                        elif i == -3: # batch finished signal
                            tot_time += result
                            break
                    p.join()
                for i in now_completed:
                    self._to_process.remove(i)

                if error_count:
                    self._logger.warning('Got %d errors during the execution, retrying...', error_count)
                trial += 1

        # handle errors if any occurred
        if error_count:
            n_failed = self._handle_errors()
            raise RuntimeError('%d jobs failed. Log file: %s' %
                               (n_failed, self.logfile))
        else:
            self._logger.info('Done. Time elapsed: %s',
            pretty_tdelta(tot_time))
            self._ok = True



    def _run_batch(self, batch_no):
        self._setup_logger(batch_no)

        batch_start, batch_end = self.job_batches[batch_no]
        self._logger.info('Starting batch %d of %d: %d tasks',
                          batch_no + 1, len(self.job_batches),
                          batch_end - batch_start)
        self._setup_ipp()
        self._logger.info('Working on %d worker engines', len(self._ids))

        # maps asyncronously on workers
        fwrapper = IppFunctionWrapper(self._serial_fun, self.const_vars,
                                      self.max_exec_time)
        self._ar = self._view.map_async(fwrapper,
                                        self._to_process[batch_start:batch_end],
                                        chunksize=self.chunksize)

        # start a thread to monitor progress
        self._monitor_flag = True
        monitor_thread = threading.Thread(target=self._monitor)

        monitor_thread.start()

        try:
            # collect results
            for i, r in enumerate(self._ar):
                self._queue.put((self._to_process[i + batch_start], r))
        except:
            self._monitor_flag = False
            exc_type, exc_value, exc_traceback = sys.exc_info()
            tb_str = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            self._queue.put((-2, tb_str))

        self._queue.put((-3, self._ar.elapsed))

        # close the monitor thread and print details
        self._logger.info('Batch completed. Time elapsed: %s',
            pretty_tdelta(self._ar.elapsed))

        monitor_thread.join()


    def _monitor(self):
        while not self._ar.ready() and self._monitor_flag:
            n_tasks = len(self._ar)
            if self._ar.progress > 0:
                time_per_task = float(self._ar.elapsed) / self._ar.progress
                eta = (n_tasks - self._ar.progress)*time_per_task
                etastr = pretty_tdelta(eta)
            else:
                etastr = 'N/A'
            self._logger.info('Completed %d of %d tasks. Time elapsed: %s  Remaining: %s',
                        self._ar.progress,
                        n_tasks,
                        pretty_tdelta(self._ar.elapsed),
                        etastr)
            elapsed = 0
            while elapsed < self.poll_interval:
                if not self._monitor_flag:
                    break
                self._ar.wait(1)
                elapsed += 1

    def submit(self):
        if not self._serial_fun:
            raise RuntimeError('AdvancedIppController.serial_fun not set')
        if not self._args:
            raise RuntimeError('AdvancedIppController.args not set')
        try:
            self._run_all()
        finally:
            self._cleanup()

    def success(self):
        return self._ok

    def map(self, parallel_task, args):
        self.serial_fun = parallel_task
        self.args = args
        self.submit()
        return self.results

    status = property(get_status, None, None)
    serial_fun = property(get_function, set_function, None)
    args = property(get_args, set_args, None)
