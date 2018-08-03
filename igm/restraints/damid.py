from __future__ import division, print_function

import numpy as np
from numpy.linalg import norm

from .restraint import Restraint
from ..model.forces import HarmonicLowerBound
from ..model import Particle

import h5py

class Damid(Restraint):
    """
    Object handles Hi-C restraint
    
    Parameters
    ----------
    damid_file : activation distance file for damid
        
    contactRange : int
        defining contact range between 2 particles as contactRange*(r1+r2)
    """
    
    def __init__(self, damid_file, contactRange=2, nuclear_radius=5000.0, k=1.0):
        
        self.contactRange = contactRange
        self.nuclear_radius = nuclear_radius
        self.k = k
        self.forceID = []
        self._load_actdist(damid_file)
    #-
    
    def _load_actdist(self,damid_actdist):
        self.damid_actdist = DamidActivationDistanceDB(damid_actdist)
    
    def _apply(self, model):
        
        center = model.addParticle([0., 0., 0.], 0., Particle.DUMMY_STATIC)

        for (i, d) in self.damid_actdist:
            
            # if particle is far enough from the center
            # apply restraint
            if norm(model.particles[i].pos) >= d : 
                
                d0 = (self.nuclear_radius - 
                      self.contactRange*model.particles[i].r)
                
                f = model.addForce(HarmonicLowerBound((i, center), d0, self.k, 
                                                      note=Restraint.DAMID))
                self.forceID.append(f)
            #-
        #-
    #=
    
    
#==

class DamidActivationDistanceDB(object):
    """
    HDF5 activation distance iterator
    """
    
    def __init__(self, damid_file, chunk_size = 10000):
        self.h5f = h5py.File(damid_file,'r')
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
                    self._chk_data[self._chk_i])
        else:
            self._i = 0
            self._chk_i = self.chunk_size
            self._chk_end = 0
            raise StopIteration()

    def next(self):
        return self.__next__()
    
    def _load_next_chunk(self):
        self._chk_row = self.h5f['row'][self._chk_end : self._chk_end + self.chunk_size]
        self._chk_data = self.h5f['dist'][self._chk_end : self._chk_end + self.chunk_size]
        self._chk_end += self.chunk_size
        self._chk_i = 0
    
    def __del__(self):
        self.h5f.close()
        
