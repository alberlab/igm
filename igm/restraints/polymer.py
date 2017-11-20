from __future__ import division, print_function

from .restraint import Restraint
from ..model.forces import HarmonicUpperBound

class Polymer(Restraint):
    """
    Object handles consecutive beed restraint
    
    Parameters
    ----------
    index : alabtools.index object
        chromosome chain index
    contactRange : int
        defining contact range between 2 particles as contactRange*(r1+r2)
    k : float
        spring constant
        
    """
    
    def __init__(self, index, contactRange=2, k=1.0):
        self.index = index
        self.contactRange = contactRange
        self.k = k
        self.forceID = []
        
    def _apply(self, model):
               
        for i in range(len(self.index) - 1):
            if (self.index.chrom[i] == self.index.chrom[i+1] and 
                self.index.copy[i] == self.index.copy[i+1]):
                dij = self.contactRange*(model.particles[i].r + 
                                         model.particles[i+1].r)
                
                f = model.addForce(HarmonicUpperBound((i, i+1), dij, self.k, 
                                                      note=Restraint.CONSECUTIVE))
                self.forceID.append(f)
            #-
        #--
    #=
    
        
