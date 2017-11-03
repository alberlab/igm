from __future__ import division, print_function

from .restraint import Restraint
from ..model.forces import HarmonicUpperBound

class Polymer(Restraint):
    """
    Object handles consecutive beed restraint
    """
    
    def __init__(self, index, contactRange=2, k=1.0):
        self.index = index
        self.contactRange = contactRange
        self.k = k
        self.forceID = []
        
    def _apply(self, model, override=False):
        
        self._apply_model(model, override)
        
        for i in range(len(self.index)-1):
            if index.chrom[i] == index.chrom[i+1]:
                dij = self.contactRange*(model.particles[i].r + model.particles[i+1].r)
                
                f = model.addForce(HarmonicUpperBound((i,i+1), dij, self.k, note="Consecutive_chain"))
                self.forceID.append(f)
            #-
        #--
    #=
    
        
