from __future__ import division, print_function

from .restraint import Restraint
from ..model.forces import HarmonicUpperBound

class HiC(Restraint):
    """
    Object handles Hi-C restraint
    
    Parameters
    ----------
    actdist : object
        
    contactRange : int
        defining contact range between 2 particles as contactRange*(r1+r2)
    """
    
    def __init__(self, actdist, contactRange=2, k=1.0):
        
        self.contactRange = contactRange
        self.k = k
        self.forceID = []
