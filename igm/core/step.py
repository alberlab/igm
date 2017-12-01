from __future__ import division, print_function
from functools import partial
import os
import numpy as np

from ..parallel import Controller
from alabtools.analysis import HssFile

class Step(object):
    def __init__(self, cfg):
        """
        base Step class implements parallel system
        """
        
        self.controller = Controller(cfg)
        self.cfg = cfg
        self.tmp_extensions = []

        self.tmp_dir = self.cfg["tmp_dir"] if "tmp_dir" in self.cfg["tmp_dir"] else "./tmp/"
        self.keep_temporary_files = True
        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)
            
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
        self.setup()
        
        serial_function = partial(self.__class__.task, cfg = self.cfg, tmp_dir = self.tmp_dir)
        

        self.controller.map(serial_function, self.argument_list)
        
        self.reduce()
        
        self.cleanup()
#==

class StructGenStep(Step):
    
    def __init__(self, cfg):
        super(StructGenStep, self).__init__()
        
        self.argument_list = list(range(self.cfg["population_size"]))
        
        self.tmp_dir = "{}/{}".format(self.tmp_dir, 
                                      self.cfg["optimization"]["tmp_files_dir"])
        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)
        
        self.tmp_extensions.append(".npy")
        self.keep_temporary_files = self.cfg["optimization"]["keep_temporary_files"]
        self.tmp_file_prefix = "tmp"
        
    def setup(self):
        
        self.tmp_file_prefix = "NewTempName"
        
    def reduce(self):
        """
        Collect all structure coordinates together to put hssFile
        """
        hssfilename = self.cfg["structure_output"]
        hss = HssFile(hssfilename,'a')
        
        #iterate all structure files and 
        for i in range(hss.nstruct):
            crd = np.load("{}/{}_{}.npy".format(self.tmp_dir, self.tmp_file_prefix, i))
            
            hss.set_struct_crd(i, crd)
        #-
