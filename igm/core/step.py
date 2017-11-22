from __future__ import division, print_function
from functools import partial

class Step(object):
    def __init__(self, controller, cfg):
        """
        base Step class implements parallel system
        """
        
        self.controller = controller
        self.cfg = cfg
        
    def setup(self):
        """
        setup everything before run
        """
        
        pass
    
    @staticmethod
    def task(struct_id, cfg):
        """
        actual serial function that supposed to be in the worker
        """
        
        raise NotImplementedError()
    
    def cleanup(self):
        """
        Do something after parallel jobs
        """
        
        pass
    
    def run(self):
        """
        
        
        """
        self.setup()
        
        serial_function = partial(self.__class__.task, cfg = self.cfg)
        argument_list = list(range(self.cfg["population_size"]))

        self.controller.map(serial_function, argument_list)
        
        self.cleanup()
