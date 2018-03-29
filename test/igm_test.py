#!/usr/bin/env python

import igm
from alabtools.analysis import HssFile

def checkViolations(cfg):
    hss = HssFile(cfg["structure_output"])
    vio = hss.get_violation()
    if "sigma" in cfg["restraints"]["Hi-C"]:
        print(cfg["restraints"]["Hi-C"]["sigma"], vio)
        if vio < 0.01:
            if len(cfg["restraints"]["Hi-C"]["sigma_list"]) > 0:
                cfg["restraints"]["Hi-C"]["sigma"] = cfg["restraints"]["Hi-C"]["sigma_list"].pop(0)
            else:
                return False
    else:
        print("Start", vio)
        cfg["restraints"]["Hi-C"]["sigma"] = cfg["restraints"]["Hi-C"]["sigma_list"].pop(0)
    #-
    return True
#===start pipeline with configure file
cfg = igm.Config("config_test.json")

#Preprocess genome, index and allocate disk space for genome structures
igm.Preprocess(cfg)



#===Run steps
randomStep = igm.RandomInit(cfg)
randomStep.run()

relaxStep = igm.RelaxInit(cfg)
relaxStep.run()


while checkViolations(cfg):
    actdistStep = igm.ActivationDistanceStep(cfg)
    actdistStep.run()

    modelStep = igm.ModelingStep(cfg)
    modelStep.run()


#cfg['restraints']['Hi-C']['sigma'] = 0.2

#actdistStep = igm.ActivationDistanceStep(cfg)
#actdistStep.run()

#modelStep = igm.ModelingStep(cfg)
#modelStep.run()


"""
import igm
import numpy as np
from alabtools.utils import Index
n_particles = 1000
model = igm.model.Model()
cfg = igm.Config("config_test.json")

for i in range(n_particles):
    model.addParticle(np.random.randn(3)*n_particles, 200, 0)
    

ex = igm.restraints.Steric(cfg['model']['evfactor'])
model.addRestraint(ex)

ev = igm.restraints.Envelope(cfg['model']['nucleus_shape'], 
                             cfg['model']['nucleus_radius'], 
                             cfg['model']['contact_kspring'])
model.addRestraint(ev)
    
index = Index(chrom=[0]*n_particles, start=[0]*n_particles, end=[0]*n_particles)

pp = igm.restraints.Polymer(index,
                            cfg['model']['contact_range'],
                            cfg['model']['contact_kspring'])
model.addRestraint(pp)


cfg['optimization']['tmp_files_dir']="./tmp/"

model.optimize(cfg['optimization'])
"""
