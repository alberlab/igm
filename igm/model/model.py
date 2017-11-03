from __future__ import division, absolute_import, print_function

import numpy as np
from .forces import Force, ExcludedVolume, HarmonicUpperBound, HarmonicLowerBound
from .particle import Particle

class Particles(object):
    
    def __init__(self):
        self.particles = []
    
    def addParticle(self,x,y,z,r,t):
        """
        Add particle to particles
        """
        self.particles.append(Particle(x,y,z,r,t))
        return len(self.particles)-1
    
    def getParticle(self,i):
        """
        Get particle in the system
        """
        
        return self.particles[i]

    def __getitem__(self, key):
        
        return self.particles[key]
    
    def __iter__(self):
        return self.particles.__iter__()
    
    def __len__(self):
        return len(self.particles)
    
#====

class Forces(object):
    
    def __init__(self):
        self.forces = []
    
    def addForce(self, f):
        """
        Add a basic force
        """
        assert isinstance(f, Force), "Argument should be a Force"
        
        self.forces.append(f) 
        return len(self.forces)-1
    
    def getForce(self, i):
        """
        get a force
        """
        
        return self.forces[i]
    
    def __getitem__(self, key):
        
        return self.forces[key]
    
    def __iter__(self):
        return self.forces.__iter__()
    
    def __len__(self):
        return len(self.forces)
#====

class Model(object):
    """
    
    Modeling target system
    
    """
    def __init__(self):
        self.particles = Particles()
        self.forces = Forces()
        
    def addParticle(self,x,y,z,r,t):
        """
        Add particle to system
        """
        return self.particles.addParticle(x,y,z,r,t)
        
    
    def getParticle(self,i):
        """
        Get particle in the system
        """
        
        return self.particles[i]
    
    def addForce(self, f):
        """
        Add a basic force
        """
        
        return self.forces.addForce(f)
    
    def getForce(self, i):
        """
        get a force
        """
        
        return self.forces[i]
    
    def evalForce(self, i):
        """
        get force score
        """
        
        return self.forces[i].getScore(self.particles)
        
    def addRestraint(self, res):
        """
        Add a type of restraint to model
        """
        
        res._apply(self)
    
        
    def optimize(self, cfg):
        """
        optimize the model by selected kernel
        """
        
        if cfg["kernel"] == "lammps":
            from .kernel import lammps
            lammps.optimize(self, cfg)
            
        
#=


