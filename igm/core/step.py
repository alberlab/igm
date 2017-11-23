from __future__ import division, print_function
from functools import partial
import os

from ..parallel import Controller

class Step(object):
    def __init__(self, cfg):
        """
        base Step class implements parallel system
        """
        
        self.controller = Controller(cfg)
        self.cfg = cfg
        self.tmp_extensions = []
        
    def setup(self):
        """
        setup everything before run
        """
        self.argument_list = list(range(self.cfg["population_size"]))
        
    
    @staticmethod
    def task(struct_id, cfg):
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
        
        if not self.cfg["optimization"]["keep_temporary_files"]:
            tmp_dir = self.cfg["optimization"]["tmp_files_dir"]
            for f in os.listdir(tmp_dir):
                if os.path.splitext(f)[1] in self.tmp_extensions:
                    os.remove(tmp_dir + '/' + f)
        #=
    
    def run(self):
        """
        
        
        """
        self.setup()
        
        serial_function = partial(self.__class__.task, cfg = self.cfg)
        

        self.controller.map(serial_function, self.argument_list)
        
        self.reduce()
        
        self.cleanup()
