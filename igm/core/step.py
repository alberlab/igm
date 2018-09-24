from __future__ import division, print_function
from functools import partial
import os
import sys
import numpy as np
import json
import hashlib
import traceback
import os.path

from shutil import copyfile
from tqdm import tqdm

from ..parallel import Controller
from ..utils import HmsFile
from alabtools.analysis import HssFile
from .job_tracking import StepDB
from ..utils.log import print_progress, logger
from ..parallel.async_file_operations import FutureFilePoller
from ..utils.files import make_absolute_path
from hashlib import md5

class Step(object):
    def __init__(self, cfg):
        """
        This is the Base Step class.
        Any computation in a IGM pipeline should be a subclass of this class.

        Important
        ---------

        The base step class init and cleanup methods *MUST BE CALLED* from
        subclasses if they overload them (e.g. with

        class MyStep(Step):
            def __init__(self, cfg):
                super(MyStep, self).__init__(cfg)

            def cleanup(self):
                super(MyStep, self).cleanup()

        This is because they set up common variables to track execution, setup
        parallel runs pipeline and allow restart runs, and they take care of
        temporary files handling.

        The `Step.run()` method *MUST NOT BE OVERLOADED*. It only takes care
        of registering the application status for future restarts.

        Member functions to overload
        ----------------------------

        The call to run() execute, in order:

        - setup()
        - before_map()
        - parallel map of static function task(struct_id, cfg, tmp_dir)
        - before_reduce()
        - reduce()
        - cleanup()

        all those methods can be overloaded ( with the caveat noted in the
        previous paragraph for setup() and cleanup() )

        If the whole step is skipped, the `skip()` member function is called.

        The `name()` function returns the name of the class. It is used mainly
        for logging and visualization purposes. Overloading it to add information
        may simplify the understanding of the output.

        Description of functions:

        setup():
            The role of setup is to prepare folders, files, data for the step.
            In particular, it needs to set the `self.argument_list` special
            variable, which contains the argument to be mapped in parallel.
            It may also modify the self.tmp_dir or modify the "runtime"
            section of the configuration object, stored in `self.cfg`.
            Also, automatic temporary files deletion can be specified,
            see the `Special member variables` section below.
            Note that this function will be called also on restart runs,
            if the whole step was not completed.

        before_map():
            This function is executed just before mapping. It is intended
            to setup resources which are needed ONLY in case of mapping.
            in a restart run, it is skipped if mapping has already been
            completed.

        task(arg, cfg, tmp_dir):
            The static `task` method is executed on parallel workers.
            Each run of the task method gets as first parameter one of
            the arguments in `argument_list`. The second and third parameters
            are the same for each run and are the configuration object
            and the temporary directory. Note that any value returned by
            task is ignored because of a design choice. Any data processed
            and further needed should be stored on a accessible location, like
            a shared file system or server.
            [ In general, large amounts of data or complex objects can be
            difficult to save properly. This means additional complexity in
            the restart design if something fails, which is better handled
            by delegating the data transport/storage to each specific case. ]

        before_reduce():
            This function is executed just before reducing. It is intended
            to setup resources which are needed only for the reduce step,
            for example initializing in-memory resources if the mapping step
            is skipped.
            In a restart run, it is skipped if reduce() has already been
            completed.

        reduce():
            This is executed only on the master node after mapping, and
            it is intended for either serial steps which do not require
            a mapping, or to collect, reduce, and atomically write
            the results.

        cleanup():
            This is the last step, intended to cleanup temporary files
            and resources, and update the runtime environment. In general,
            overriding this method is unnecessary and not suggested.

        skip():
            When the step is skipped in a restart run, this function is
            called. It is intended for possibly setting runtime variables

        Special Member Variables
        ------------------------

        cfg : Config
            configuration object
        db : StepDB
            database object
        argument_list : list
            arguments to be mapped in parallel
        tmp_dir : str
            path of the directory where temporary files will be saved
        tmp_extensions : list
            list of extensions of temporary files. All files with the
            listed extensions in tmp_dir are removed at the cleanup()
            call if `keep temporary files` is True
        keep_temporary_files: bool
            if True, it deletes temporary files during cleanup
        uid : str
            a unique string identifying the current step

        Runtime Configuration Modifications
        -----------------------------------

        The Step class uses the "runtime" key of the Configuration object
        to store status variables:

        step_no : int
            the step number. Each step which is run is increased by one.
        step_hash : str
            the unique identifier of the step same of `uid` special member
        current_iteration_name : str
            the name of the step.

        """

        self.controller = Controller(cfg)
        self.cfg = cfg
        self.tmp_extensions = []

        self.tmp_dir = self.cfg["parameters"].get("tmp_dir", "tmp/")
        self.tmp_dir = make_absolute_path(self.tmp_dir, cfg["parameters"]["workdir"])
        self.keep_temporary_files = True
        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)

        # Keep track of step execution in a database
        # set a unique id for the step
        # set a default name
        if 'current_iteration_name' not in cfg['runtime']:
            self.cfg['runtime']['current_iteration_name'] = self.name()

        if cfg['runtime'].get('step_no') is None:
            self.cfg['runtime']['step_no'] = -1

        self.cfg['runtime']['step_no'] += 1

        self._db = StepDB( cfg )

        self.uid = md5('{:s}:{:d}'.format( self.name(), self.cfg['runtime']['step_no'] ).encode()).hexdigest()

        self.cfg['runtime']['step_hash'] = self.uid

    def setup(self):
        """
        setup everything before run
        """
        self.argument_list = []
        pass

    def before_map(self):
        return

    @staticmethod
    def task(struct_id, cfg, tmp_dir):
        """
        actual serial function that supposed to be in the worker
        """
        pass

    def before_reduce(self):
        return

    def reduce(self):
        """
        Do something after parallel jobs
        """

        pass

    def cleanup(self):
        """
        Clean up temp files
        """

        if not self.keep_temporary_files:
            for f in os.listdir(self.tmp_dir):
                if os.path.splitext(f)[1] in self.tmp_extensions:
                    os.remove(self.tmp_dir + '/' + f)
        #=

    def run(self):
        """
        Responsible for running/restarting the step, and keeping track
        of the progress.
        *DO NOT OVERLOAD*
        """

        dbdata = {
            'uid': self.uid,
            'name': self.name(),
            'cfg': self.cfg,
        }

        past_history = self._db.get_history(self.uid)
        past_substeps = { x['status'] : x['cfg'] for x in past_history }
        if 'completed' in past_substeps:
            self.cfg['runtime'].update(past_substeps['completed']['runtime'])
            logger.info('step %s already completed, skipping.' % self.name())
            self.skip()
            return

        try:
            logger.info('%s - starting' % self.name())

            dbdata['status'] = 'entry'
            self._db.record(**dbdata)

            self.setup()
            serial_function = partial(self.__class__.task,
                                      cfg=self.cfg,
                                      tmp_dir=self.tmp_dir)

            dbdata['status'] = 'setup'
            self._db.record(**dbdata)

            if 'mapped' not in past_substeps:

                self.before_map()

                logger.info('%s - mapping' % self.name())
                dbdata['status'] = 'map'
                self._db.record(**dbdata)

                self.controller.map(serial_function, self.argument_list)

                dbdata['status'] = 'mapped'
                self._db.record(**dbdata)

            else:
                self.cfg.update(past_substeps['mapped'])

            if 'reduced' not in past_substeps:

                self.before_reduce()

                logger.info('%s - reducing' % self.name())
                self.reduce()
                dbdata['status'] = 'reduced'
                self._db.record(**dbdata)

            else:
                self.cfg.update(past_substeps['reduced'])

            if 'cleanup' not in past_substeps:

                logger.debug('%s - cleaning up' % self.name())
                self.cleanup()
                dbdata['status'] = 'cleanup'
                self._db.record(**dbdata)

            else:
                self.cfg.update(past_substeps['cleanup'])

            logger.info('%s - completed' % self.name())
            dbdata['status'] = 'completed'
            if 'step_hash' in self.cfg['runtime']:
                del self.cfg['runtime']['step_hash']
            self._db.record(**dbdata)

        except:

            dbdata['status'] = 'failed'
            dbdata['data'] = { 'exception' : traceback.format_exc() }
            self._db.record(**dbdata)
            logger.error( '%s\n%s - failed' % ( self.name(), traceback.format_exc() ) )
            raise

    def name(self):
        return self.__class__.__name__

    def skip(self):
        return None




#==

class StructGenStep(Step):

    def __init__(self, cfg):
        super(StructGenStep, self).__init__(cfg)

        self.argument_list = list(range(self.cfg["model"]["population_size"]))

        self.tmp_extensions.append(".hms")
        self.keep_temporary_files = cfg["optimization"]["keep_temporary_files"]
        self.keep_intermediate_structures = cfg["optimization"]["keep_intermediate_structures"]

    def reduce(self):
        """
        Collect all structure coordinates together to assemble a hssFile
        """

        # create a temporary file if does not exist.
        hssfilename = self.cfg["optimization"]["structure_output"] + '.tmp'
        hss = HssFile(hssfilename, 'a', driver='core')

        #iterate all structure files and
        total_restraints = 0.0
        total_violations = 0.0

        for i in tqdm(range(hss.nstruct), desc='(REDUCE)'):
            fname = "{}_{}.hms".format(self.tmp_file_prefix, i)
            hms = HmsFile( os.path.join( self.tmp_dir, fname ) )
            crd = hms.get_coordinates()
            total_restraints += hms.get_total_restraints()
            total_violations += hms.get_total_violations()

            hss.set_struct_crd(i, crd)
        #-
        if (total_violations == 0) and (total_restraints == 0):
            hss.set_violation(np.nan)
        else:
            hss.set_violation(total_violations / total_restraints)

        hss.close()

        # swap files
        os.rename(hssfilename, hssfilename + '.swap')
        os.rename(self.cfg["optimization"]["structure_output"], hssfilename)
        os.rename(hssfilename + '.swap', self.cfg["optimization"]["structure_output"])

        if self.keep_intermediate_structures:
            copyfile(
                self.cfg["optimization"]["structure_output"],
                self.intermediate_name()
            )

    def intermediate_name(self):
        return self.cfg["optimization"]["structure_output"] + '.' + self.uid
