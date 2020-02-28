from __future__ import division, print_function

from .restraint import Restraint
from ..model.particle import Particle
from ..model.forces import NuclExcludedVolume

class Nucleolus(Restraint):
    """
    A object handles nucleolus excluded volume restraints
    
    Parameters
    ----------
    body_pos, body_r: center coordinates and radius of nucleolus
    k : float
        spring constant
    """
    
    def __init__(self, body_pos, body_r, k=1.0):

        """ Class initialization"""

        self.body_pos = body_pos     # coordinates of nucleolus center
        self.body_r   = body_r         # radius of spherical nucleulus
        self.k        = k
        self.forceID  = []
        
    def _apply(self, model):
      
        """ Apply force """
      
        plist = [i for i, p in enumerate(model.particles) if p.ptype == Particle.NORMAL]
        
        f = model.addForce(NuclExcludedVolume(plist, self.body_pos, self.body_r, self.k))
        self.forceID.append(f)
        #-
    #=
