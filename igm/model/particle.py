from __future__ import division, absolute_import, print_function
import numpy as np

POSDTYPE = np.float32

# define "Particle" class

class Particle(object):

    NORMAL = 0
    DUMMY_STATIC = 1
    DUMMY_DYNAMIC = 2
    
    PTYPES = ["NORMAL","DUMMY_STATIC","DUMMY_DYNAMIC"]
    
    def __init__(self, pos, r, t, **kwargs):
        self.pos = np.array(pos).astype(POSDTYPE)     # particle coordinates
        self.r = POSDTYPE(r)                          # particle radius (if 0, then no excluded voluem)
        self.ptype = t                                # particle type (see PTYPES list)
        for k in kwargs:
            setattr(self, k, kwargs[k])
    
    def __str__(self):
        return "({} {} {}, {}):{}".format(self.pos[0], self.pos[1], self.pos[2],
                                          self.r,
                                          Particle.PTYPES[self.ptype])
    __repr__ = __str__
    
    def getCoordinates(self):
        return self.pos
    
    def setCoordinates(self, pos):
        self.pos = pos
    
    def __sub__(self, other):
        return np.linalg.norm(self.pos - other.pos)
    
    
