from __future__ import division, absolute_import, print_function

from .forces import Force
from .particle import Particle
try:
    from itertools import izip as zip
except ImportError: 
    pass

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
    
    
    #====Particle methods
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
    
    def setParticlePos(self, i, pos):
        """
        set particle coordinates
        """
        
        self.particles[i].setCoordinates(pos)
    #====
    
    
    #===bulk particle methods
    def initParticles(self, crd, rad):
        """
        initialize particles using numpy array
        
        Parameters
        ----------
        crd : 2D numpy array (float), N*3
            Numpy array of coordinates for each particle, N is the number of particles
        rad : 2D numpy array (float), N*1
            particle radius
        """
        assert crd.shape[0] == rad.shape[0]
        
        for pos, r in zip(crd, rad):
            self.addParticle(pos, r, Particle.NORMAL)
    #====
    
    
    #====bulk get methods
    def getCoordinates(self):
        """
        Get all particles' Coordinates in numpy array form
        """
        return np.array([p.pos for p in self.particles if p.t == Particle.NORMAL])
    
    
    def getRadii(self):
        """
        Get all particles' radii in numpy array vector form
        """
        return np.array([[p.r for p in self.particles if p.t == Particle.NORMAL]]).T
    #====
    
    
    #====force methods
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
    #====
        
        
    #====restraint methods
    def addRestraint(self, res, override=False):
        """
        Add a type of restraint to model
        """
        res._apply_model(self, override)
        
        res._apply(self)
    
        
    def optimize(self, cfg):
        """
        optimize the model by selected kernel
        """
        
        if cfg["kernel"] == "lammps":
            from ..kernel import lammps
            return lammps.optimize(self, cfg)
            
        
#=


