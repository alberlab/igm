from __future__ import division, print_function

from .restraint import Restraint
from ..model.particle import Particle
from ..model.forces import ExcludedVolume

class Steric(Restraint):
    """
    A object handles nuclear envelope restraints
    
    Parameters
    ----------
    nucRadius : float
        nuclear radius in unit of nm.
    k : float
        spring constant
    """
    
    def __init__(self, k=1.0):
        self.k = k
        self.forceID = []
        
    def _apply(self, model):
        
        plist = [i for i, p in enumerate(model.particles) if p.ptype == Particle.NORMAL]
        
        f = model.addForce(ExcludedVolume(plist, self.k))
        
        self.forceID.append(f)
        #-
    #=
