from __future__ import division, print_function

from .restraint import Restraint
from ..model.particle import Particle
from ..model.forces import NuclExcludedVolume

class SpeckleVolume(Restraint):
    """
    A object handles Speckle Volume Excluded Volume Restraint.
    
    Parameters
    ----------
    speckles: list of speckles of the current structure
              list of tuples (spe_crd, spe_rad)
    k : float
        spring constant
    """
    
    def __init__(self, speckles, k=1.0):
        self.speckles = speckles
        self.k = k
        self.forceID = []
        
    def _apply(self, model):
      
        """ Apply force """
      
        plist = [i for i, p in enumerate(model.particles) if p.ptype == Particle.NORMAL]
        
        for spe in self.speckles:
            spe_crd, spe_rad = spe
            f = model.addForce(NuclExcludedVolume(plist, spe_crd, spe_rad, self.k),
                               note=Restraint.SPECKLE_EXCLUDED_VOLUME)
        self.forceID.append(f)
        #-
    #=
