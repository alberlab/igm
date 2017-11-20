from __future__ import division, print_function

from .restraint import Restraint
from ..model.particle import Particle
from ..model.forces import HarmonicUpperBound
try:
    UNICODE_EXISTS = bool(type(unicode))
except NameError:
    unicode = lambda s: str(s)
    
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
    
    def __init__(self, shape="sphere", nucRadius=5000.0, k=1.0):
        self.shape = unicode(shape)
        
        if self.shape == u"sphere":
            self.nucRadius = nucRadius
        elif self.shape == u"ellipsoid":
            self.a, self.b, self.c = nucRadius
        
        self.k = k
        self.forceID = []
    
    def _apply_sphere_envelop(self, model):
        
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
        
    def _apply(self, model):
        
        if self.shape == u"sphere":
            self._apply_sphere_envelop(model)
    #=
