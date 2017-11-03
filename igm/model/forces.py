from __future__ import division, absolute_import, print_function

class Force(object):
    """
    Define Basic Force type
    """
    
    EXCLUDED_VOLUME = 0
    HARMONIC_UPPER_BOUND = 1
    HARMONIC_LOWER_BOUND = 2
    
    FTYPES = ["EXCLUDED_VOLUME","HARMONIC_UPPER_BOUND","HARMONIC_LOWER_BOUND"]
    
    def __init__(self,ftype, particles, para, note):
        self.ftype = ftype
        self.particles = particles
        self.parameters = para
        self.note = note
    
    def __str__(self):
        return "{} {}".format(Force.FTYPES[self.ftype], self.note)
    
    __repr__ = __str__
    
    def getScore(self, particles):
        return 0

class ExcludedVolume(Force):
    ftype = Force.EXCLUDED_VOLUME
    
    def __init__(self, particles, k=1.0, note=""):
        self.particles = particles
        self.k = k
        self.note = note
        
#-
    
class HarmonicUpperBound(Force):
    ftype = Force.HARMONIC_UPPER_BOUND
    
    def __init__(self, particles, d=0.0, k=1.0, note=""):
        if len(particles) != 2:
            raise ValueError("Two particles required")
        else:
            self.i, self.j = particles
        
        self.d = d
        self.k = k
        self.note = note
    
    def getScore(self, particles):
        
        dist = particles[self.i] - particles[self.j]
        
        return 0 if dist <= self.d else (dist - self.d)
#-

class HarmonicLowerBound(Force):
    ftype = Force.HARMONIC_LOWER_BOUND
    
    def __init__(self, particles, d=0.0, k=1.0, note=""):
        if len(particles) != 2:
            raise ValueError("Two particles required")
        else:
            self.i, self.j = particles
        
        self.d = d
        self.k = k
        self.note = note
    
    def getScore(self, particles):
        
        dist = particles[self.i] - particles[self.j]
        
        return 0 if dist >= self.d else (self.d - dist)
#-
