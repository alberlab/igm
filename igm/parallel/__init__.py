from __future__ import division, print_function

from .parallel_controller import SerialController
    
from .ipyparallel_controller import BasicIppController

controller_class = {
    "serial" : SerialController,
    "ipyparallel" : BasicIppController,
    "ipyparallel_basic" : BasicIppController, 
}

def Controller(cfg):
    pctype = cfg["parallel"]["controller"]
    pcopts = cfg["parallel"]["options"]
        
    return controller_class[pctype](**pcopts)
