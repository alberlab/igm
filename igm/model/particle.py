from __future__ import division, absolute_import, print_function
import numpy as np

class Particle(object):
    NORMAL = 0
    DUMMY_STATIC = 1
    DUMMY_DYNAMIC = 2
    
    PTYPES = ["NORMAL","DUMMY_STATIC","DUMMY_DYNAMIC"]
    
    def __init__(self, pos, r, t):
        self.pos = np.array(pos)
        self.r = r
        self.ptype = t
    
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
    
    
