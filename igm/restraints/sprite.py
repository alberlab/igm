from __future__ import division, print_function

import numpy as np
import h5py

from ..model.particle import Particle
from .restraint import Restraint
from ..model.forces import HarmonicUpperBound

class Sprite(Restraint):
    """
    Add SPRITE restraint as a DUMMY DYNAMIC particle is introduced and all beads assigned to a given
    cluster are connected to it via harmonic springs
    
    Parameters
    ----------
    assignment_file : SPRITE activation distance file
        
    volume_occupancy : float
        defining contact range between 2 particles as contactRange*(r1+r2)

    k (float): elastic constant for restraining
    """
    
    def __init__(self, assignment_file, volume_occupancy, struct_id, k=1.0):
        
        """ Initialize SPRITE parameters and input file """

        self.volume_occupancy = volume_occupancy
        self.struct_id        = struct_id
        self.k                = k
        self.forceID          = []
        self.assignment_file  = h5py.File(assignment_file, 'r')
    #-
    
    def _apply(self, model):

        """ Apply SPRITE restraints """ 

        assignment     = self.assignment_file['assignment'][()]
        indptr         = self.assignment_file['indptr'][()]
        selected_beads = self.assignment_file['selected']
        clusters_ids   = np.where(assignment == self.struct_id)[0]
        radii          = model.getRadii()
        coord          = model.getCoordinates()

        # loop over indexes in 'assignment' (see SpriteAcrivationStep.py) referring to structure 'struct_id'
        for i in clusters_ids:
            beads      = selected_beads[ indptr[i] : indptr[i+1] ]
            crad       = radii[beads]
            ccrd       = coord[beads]
            csize      = len(beads)
            csize      = get_cluster_size(crad, self.volume_occupancy)
            
            # add a centroid for the cluster, in the geometric center
            centroid_pos = np.mean(ccrd, axis=0)
            centroid     = model.addParticle(centroid_pos, 0, Particle.DUMMY_DYNAMIC) # no excluded volume

            for b in beads:
                # apply harmonic restraint(s) to all beads making up the cluster, using the position of the centroid as "origin" (one-body terms)
                f = model.addForce(HarmonicUpperBound(
                    (b, centroid), float(csize-radii[b]), self.k, 
                    note=Restraint.SPRITE))
                self.forceID.append(f)
                
    
def cbrt(x):
    return (x)**(1./3.)

def get_cluster_size(radii, volume_occupancy):
    return cbrt(np.sum(radii**3)/volume_occupancy)
