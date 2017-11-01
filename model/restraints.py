from __future__ import division, absolute_import, print_function

class Restraint(Object):
    """
    Define Basic Restraint type
    """
    
    EXCLUDED_VOLUME = 0
    HARMONIC_UPPER_BOUND = 1
    HARMONIC_LOWER_BOUND = 2
    
    RTYPES = ["EXCLUDED_VOLUME","HARMONIC_UPPER_BOUND","HARMONIC_LOWER_BOUND"]
    
    def __init__(self,rtype, particles, para, note):
        self.rtype = rtype
        self.particles = particles
        self.parameters = para
        self.note = note
    
    def __str__(self):
        return "{} {}".format(RTYPES[self.rtype], note)
        
    def getViolation(self):
        pass

class ExcludedVolume(Restraint):
    rtype = Restraint.EXCLUDED_VOLUME
    
    def __init__(self, particles, k=1.0, note=""):
        self.particles = particles
        self.k = k
        self.note = note
        
#-
    
class HarmonicUpperBound(Restraint):
    rtype = Restraint.HARMONIC_UPPER_BOUND
    
    def __init__(self, particles, d=0.0, k=1.0, note=""):
        if len(particles) != 2:
            raise ValueError("Two particles required")
        else:
            self.i, self.j = particles
        
        self.d = d
        self.k = k
        self.note = note
#-

class HarmonicLowerBound(Restraint):
    rtype = Restraint.HARMONIC_LOWER_BOUND
    
    def __init__(self, particles, d=0.0, k=1.0, note=""):
        if len(particles) != 2:
            raise ValueError("Two particles required")
        else:
            self.i, self.j = particles
        
        self.d = d
        self.k = k
        self.note = note
#-
