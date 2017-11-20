import igm
from alabtools.utils import Index
import numpy as np

model = igm.model.Model()
cfg = igm.Config("config_test.json")

for i in range(500):
    model.addParticle(np.random.randn(3)*500, 200, 0)

ex = igm.restraints.Steric(cfg.model['evfactor'])
model.addRestraint(ex)

ev = igm.restraints.Envelope(cfg.model['nucleus_shape'], 
                             cfg.model['nucleus_radius'], 
                             cfg.model['contact_kspring'])
model.addRestraint(ev)
    
index = Index(chrom=[0]*500, start=[0]*500, end=[0]*500)

pp = igm.restraints.Polymer(index,
                            cfg.model['contact_range'],
                            cfg.model['contact_kspring'])
model.addRestraint(pp)



model.optimize(cfg.optimization)
