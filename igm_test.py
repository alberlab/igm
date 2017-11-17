import igm
from alabtools.utils import Index
import numpy as np

n_particles = 1000
model = igm.model.Model()

for i in range(n_particles):
    model.addParticle(np.random.randn(3)*n_particles, 200, 0)
    
ee = igm.restraints.Envelope(5000, 1)
model.addRestraint(ee)
    
index = Index(chrom=[0]*n_particles, start=[0]*n_particles, end=[0]*n_particles)

pp = igm.restraints.Polymer(index)
model.addRestraint(pp)

import igm.kernel.lammps
info = igm.kernel.lammps.optimize(model, {
                                    'tmp_files_dir':'.', 
                                    'run_name':'test', 
                                    'keep_temporary_files': True, 
                                    'lammps_executable': 'lmp_serial_mod', 
                                    'optimizer_options':{} })
