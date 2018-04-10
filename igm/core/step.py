from __future__ import division, print_function
from functools import partial
import os
import sys
import numpy as np
import json
import hashlib
import traceback
import os.path

from ..parallel import Controller
from ..utils import HmsFile
from alabtools.analysis import HssFile
from .job_tracking import StepDB

class Step(object):
    def __init__(self, cfg):
        """
        base Step class implements parallel system
        """
        
        self.controller = Controller(cfg)
        self.cfg = cfg
        self.tmp_extensions = []

        self.tmp_dir = self.cfg["tmp_dir"] if "tmp_dir" in self.cfg["tmp_dir"] else "./tmp/"
        self.tmp_dir = os.path.abspath(self.tmp_dir)
        self.keep_temporary_files = True
        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)

        # Keep track of step execution in a database
        # set a unique id for the step
        # set a default name 
        if 'current_iteration_name' not in cfg['runtime']:
            cfg['runtime']['current_iteration_name'] = 'iteration'

        self.name = cfg['runtime']['current_iteration_name']

        self.db = StepDB( cfg )

        self.uid = hashlib.md5(json.dumps(self.cfg)).hexdigest()

    def setup(self):
        """
        setup everything before run
        """
        self.argument_list = []
        pass
        
    @staticmethod
    def task(struct_id, cfg, tmp_dir):
        """
        actual serial function that supposed to be in the worker
        """
        
        raise NotImplementedError()
    
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
        
        
        """
        dbdata = {
            'uid': self.uid,
            'name': self.name,
            'cfg': self.cfg,
        }

        past_history = self.db.get_history(self.uid)
        past_substeps = { x['status'] for x in past_history }
        if 'completed' in past_substeps:
            return

        try:

            dbdata['status'] = 'entry'
            self.db.record(**dbdata)
        
            self.setup()
            serial_function = partial(self.__class__.task, 
                                      cfg=self.cfg, 
                                      tmp_dir=self.tmp_dir)

            dbdata['status'] = 'setup'
            self.db.record(**dbdata)

            if 'mapped' not in past_substeps:
                dbdata['status'] = 'map'
                self.db.record(**dbdata)

                self.controller.map(serial_function, self.argument_list)

                dbdata['status'] = 'mapped'
                self.db.record(**dbdata)

            if 'reduced' not in past_substeps:                
                self.reduce()
                dbdata['status'] = 'reduced'
                self.db.record(**dbdata)

            if 'cleanup' not in past_substeps:
                self.cleanup()
                dbdata['status'] = 'cleanup'
                self.db.record(**dbdata)

            dbdata['status'] = 'completed'
            self.db.record(**dbdata)
     
        except:

            dbdata['status'] = 'failed'
            dbdata['data'] = { 'exception' : traceback.format_exc() }
            self.db.record(**dbdata)
            raise
        

#==

class StructGenStep(Step):
    
    def __init__(self, cfg):
        super(StructGenStep, self).__init__(cfg)
        
        self.argument_list = list(range(self.cfg["population_size"]))
        
        dname = os.path.join(self.tmp_dir, self.cfg["optimization"]["tmp_dir"])
        self.tmp_dir = os.path.abspath(dname)
        self.cfg["optimization"]["tmp_files_dir"] = self.tmp_dir
        
        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)
        
        self.tmp_extensions.append(".hms")
        self.keep_temporary_files = self.cfg["optimization"]["keep_temporary_files"]
        self.tmp_file_prefix = "tmp"
        
    def setup(self):
        
        self.tmp_file_prefix = "NewTempName"
        
    def reduce(self):
        """
        Collect all structure coordinates together to put hssFile
        """
        hssfilename = self.cfg["structure_output"]
        hss = HssFile(hssfilename, 'a', driver='core')
        
        #iterate all structure files and 
        total_restraints = 0.0
        total_violations = 0.0
        print("REDUCE:Collecting hms >>",end='')
        sys.stdout.flush()
        for i in range(hss.nstruct):
            if (i+1) % (hss.nstruct//20) == 0:
                print("=", end='')
                sys.stdout.flush()
            fname = "{}_{}.hms".format(self.tmp_file_prefix, i)
            hms = HmsFile( os.path.join( self.tmp_dir, fname ) )
            crd = hms.get_coordinates()
            total_restraints += hms.get_total_restraints()
            total_violations += hms.get_total_violations()
            
            hss.set_struct_crd(i, crd)
        #-
        print("Done.\n")
        if (total_violations == 0) and (total_restraints == 0):
            hss.set_violation(np.nan)
        else:
            hss.set_violation(total_violations / total_restraints)
        
        hss.close()
        
