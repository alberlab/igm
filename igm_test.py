import igm
from alabtools.utils import Index
import numpy as np

model = igm.model.Model()
cfg = igm.Config("config_test.json")

for i in range(500):
    model.addParticle(np.random.randn(3)*500, 200, 0)

ex = igm.restraints.Steric()
model.addRestraint(ex)

ee = igm.restraints.Envelope(5000, 1)
model.addRestraint(ee)
    
index = Index(chrom=[0]*500, start=[0]*500, end=[0]*500)

pp = igm.restraints.Polymer(index)
model.addRestraint(pp)

import igm.kernel.lammps

info = igm.kernel.lammps.optimize(model, cfg.optimization)
