from __future__ import division, print_function

from .parallel_controller import SerialController
    
from .ipyparallel import BasicIppController, AdvancedIppController

controller_class = {
    "serial" : SerialController,
    "ipyparallel" : AdvancedIppController,
    "ipyparallel_basic" : BasicIppController, 
}

def Controller(cfg):
    pctype = cfg["controller"]
    pcopts = cfg["options"]
        
    return controller_class[pctype](**pcopts)
