from __future__ import division, print_function
from functools import partial

class Step(object):
    def __init__(self, controller, cfg):
        """
        base Step class implements parallel system
        """
        
        self.controller = controller
        self.config = cfg
        
    def setup(self):
        """
        setup everything before run
        """
        
        raise NotImplementedError()
    
    def task(self, struct_id):
        """
        actual serial function that supposed to be in the worker
        """
        
        raise NotImplementedError()
    
    def run(self):
        """
        
        
        """
        
        serial_function = partial(self.task)
        argument_list = list(range(self.config["population_size"]))
        
        self.controller.map(serial_function, argument_list)
    
