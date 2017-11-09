from __future__ import division, print_function

from .restraint import Restraint
from ..model.particle import Particle
from ..model.forces import HarmonicUpperBound

class Envelope(Restraint):
    """
    A object handles nuclear envelope restraints
    
    Parameters
    ----------
    nucRadius : float
        nuclear radius in unit of nm.
    k : float
        spring constant
    """
    
    def __init__(self, nucRadius=5000.0, k=1.0):
        self.nucRadius = nucRadius
        self.k = k
        self.forceID = []
        
    def _apply(self, model, override=False):
        
        self._apply_model(model, override)
        
        center = model.addParticle([0., 0., 0.], 0., Particle.DUMMY_STATIC)
        
        for i, p in enumerate(model.particles):
            if p.ptype != Particle.NORMAL:
                continue
            
            f = model.addForce(HarmonicUpperBound((i, center), 
                                                  d=self.nucRadius - p.r, 
                                                  k=self.k, 
                                                  note=Restraint.ENVELOPE))
            
            self.forceID.append(f)
        #-
    #=
