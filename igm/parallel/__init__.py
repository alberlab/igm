from __future__ import division, print_function

from .parallel_controller import SerialController
    
from .ipyparallel_controller import BasicIppController

from .slurm_controller import SlurmController

controller_class = {
    "serial" : SerialController,
    "slurm" : SlurmController,
    "ipyparallel" : BasicIppController,
    "ipyparallel_basic" : BasicIppController, 
}

def Controller(cfg):
    parallel_cfg = cfg.get("parallel", dict())
    pctype = parallel_cfg.get("controller", "ipyparallel")
    pcopts = parallel_cfg.get("controller_options", dict()).get(pctype, dict())
    return controller_class[pctype](**pcopts)
