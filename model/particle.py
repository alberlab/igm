from __future__ import division, absolute_import, print_function

class Particle(Object):
    NORMAL = 0
    DUMMY_STATIC = 1
    DUMMY_DYNAMIC = 2
    
    PTYPES = ["NORMAL","DUMMY_STATIC","DUMMY_DYNAMIC"]
    
    def __init__(self,x,y,z,r,t):
        self.x, self.y, self.z = x, y, z
        self.r = r
        self.t = t
    
    def __str__(self):
        return "({} {} {}, {}):{}".format(self.x, self.y, self.z.
                                          self.r,
                                          PTYPES[self.t])
    
    def getCoordinate(self):
        return (self.x,self.y,self.z)
    
    def setCoordinate(self,x,y,z):
        self.x, self.y, self.z = x, y, z
    
