from __future__ import division, print_function

import numpy as np
from .restraint import Restraint
from ..model.forces import HarmonicUpperBound

MIN_CONSECUTIVE = 0.5

class Polymer(Restraint):
    """
    Object handles consecutive bead restraint

    Parameters
    ----------
    index : alabtools.index object
        chromosome chain index
    contactRange : int
        defining contact range between 2 particles as contactRange*(r1+r2)
    k : float
        spring constant

    """

    def __init__(self, index, contactRange=2, k=1.0, contact_probabilities=None):
        self.index = index
        self.contactRange = contactRange
        self.k = k
        self.forceID = []
        self.cp = np.load(contact_probabilities) if (contact_probabilities is not None) else None

    def _apply(self, model):

        for i in range(len(self.index) - 1):
            
            # if i and i+1 belong to the same chromosome (and copy)
            if (self.index.chrom[i] == self.index.chrom[i+1] and
                self.index.copy[i] == self.index.copy[i+1]):

                # do we have contact probabiities?
                if self.cp is None:
                    dij = self.contactRange*(model.particles[i].r +
                                             model.particles[i+1].r)
                else:
                    d0 = (model.particles[i].r + model.particles[i+1].r)
                    d1 = self.contactRange * d0
                    f = self.cp[i]
                    # if we have inconsistent or no data, just assume MIN_CONSECUTIVE contact
                    if f < MIN_CONSECUTIVE or f > 1:
                        f = MIN_CONSECUTIVE
                    x3 = ( d1**3 + ( f - 1 )*d0**3 ) / f
                    dij = x3**(1./3)

                f = model.addForce(HarmonicUpperBound((i, i+1), dij, self.k,
                                                      note=Restraint.CONSECUTIVE))
                self.forceID.append(f)
            #-
        #--
    #=


