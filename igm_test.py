import igm
from alabtools.utils import Index
import numpy as np

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



model.optimize(cfg['optimization'])
