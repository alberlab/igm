from __future__ import division, absolute_import, print_function

from .forces import Force
from .particle import Particle

class Model(object):
    """
    
    Modeling target system
    
    This is an abstract mid-layer between data-restraints and minization kernel.
    
    The Model holds all information about the target system by particles and
    harmonic forces.
    
    """
    def __init__(self):
        self.particles = []
        self.forces = []
        
    def addParticle(self, pos, r, t):
        """
        Add particle to system
        """
        
        self.particles.append(Particle(pos, r, t))
        
        return len(self.particles)-1
        
    
    def getParticle(self,i):
        """
        Get particle in the system
        """
        return self.particles[i]
    
    def addForce(self, f):
        """
        Add a basic force
        """
        
        self.forces.append(f)
        
        return len(self.forces)-1
    
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
            from ..kernel import lammps
            return lammps.optimize(self, cfg)
            
        
#=


