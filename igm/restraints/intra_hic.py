from __future__ import division, print_function

import numpy as np

from .restraint import Restraint
from ..model.forces import HarmonicUpperBound
from ..utils.log import logger

import h5py

class intraHiC(Restraint):

    """
    Object handles Hi-C restraint
    
    Parameters
    ----------
    actdist_file : activation distance file (generated from ActivationDistanceStep.py)
        
    contactRange : int
        defining contact range between 2 particles as contactRange*(r1+r2)

    k: float
	elastic constant for harmonic restraint
    """
    
    def __init__(self, actdist_file, chrom, contactRange=2, k=1.0):
        
        self.contactRange = contactRange
        self.k = k
        self.chrom = chrom
        self.forceID = []
        self._load_actdist(actdist_file)
    #-
   
    def _load_actdist(self,actdist):
        self.actdist = ActivationDistanceDB(actdist)
    
    def _apply(self, model):

        """ Apply harmonic restraint to those distances smaller than d_{act}""" 
       
        for (i, j, d) in self.actdist:
            
            # calculate particle distances for i, j
            # if ||i-j|| <= d then assign a bond for i, j
            if ((model.particles[i] - model.particles[j] <= d) and (self.chrom[i] == self.chrom[j])) : 

                # harmonic mean distance
                dij = self.contactRange*(model.particles[i].r + 
                                         model.particles[j].r)
                
                # add harmonic bond between i-th and j-th beads
                f = model.addForce(HarmonicUpperBound((i, j), dij, self.k, 
                                                      note=Restraint.INTRA_HIC))
                self.forceID.append(f)
            #-
        #-
    #=
    
    
#==

class ActivationDistanceDB(object):

    """ HDF5 activation distance iterator: read in file of activation distances, in chunks """
        
    def __init__(self, actdist_file, chunk_size = 10000):
        self.h5f = h5py.File(actdist_file,'r')
        self._n = len(self.h5f['row'])
        
        self.chunk_size = min(chunk_size, self._n)
        
        self._i = 0
        self._chk_i = chunk_size
        self._chk_end = 0
        
    def __len__(self):
        return self._n
    
    def __iter__(self):
        return self
    
    def __next__(self):
        if self._i < self._n:
            self._i += 1
            self._chk_i += 1
            
            if self._chk_i >= self.chunk_size:
                self._load_next_chunk()
            
            return (self._chk_row[self._chk_i],
                    self._chk_col[self._chk_i],
                    self._chk_data[self._chk_i])
        else:
            self._i = 0
            self._chk_i = self.chunk_size
            self._chk_end = 0
            raise StopIteration()
    def next(self):
        return self.__next__()
    
    # probabilities are not needed now, since they are already encoded in the list of activation distances
    def _load_next_chunk(self):
        self._chk_row = self.h5f['row'][self._chk_end : self._chk_end + self.chunk_size]
        self._chk_col = self.h5f['col'][self._chk_end : self._chk_end + self.chunk_size]
        self._chk_data = self.h5f['dist'][self._chk_end : self._chk_end + self.chunk_size]
        self._chk_end += self.chunk_size
        self._chk_i = 0
    
    def __del__(self):
        self.h5f.close()
        
