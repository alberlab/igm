#!/usr/bin/env python

import igm
import numpy as np

#===start pipeline with configure file
cfg = igm.Config("config_test.json")

#Preprocess genome, index and allocate disk space for genome structures
igm.Preprocess(cfg)



#===Run steps
randomStep = igm.RandomInit(cfg)
randomStep.run()

relaxStep = igm.RelaxInit(cfg)
relaxStep.run()

cfg['restraints']['Hi-C']['sigma'] = 1.0

actdistStep = igm.ActivationDistanceStep(cfg)
actdistStep.run()

modelStep = igm.ModelingStep(cfg)
modelStep.run()


cfg['restraints']['Hi-C']['sigma'] = 0.2

actdistStep = igm.ActivationDistanceStep(cfg)
actdistStep.run()

modelStep = igm.ModelingStep(cfg)
modelStep.run()

import igm
import numpy as np
from alabtools.utils import Index
n_particles = 1000
model = igm.model.Model()


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
