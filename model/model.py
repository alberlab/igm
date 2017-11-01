from __future__ import division, absolute_import, print_function

import numpy as np
from .restraints import Restraint, ExcludedVolume, HarmonicUpperBound, HarmonicLowerBound
from .particle import Particle


class Model(Object):
    """
    
    Modeling target system
    
    """
    def __init__(self):
        self.Particles=[]
        self.Restraints=[]
        self.Chains=[]
        
    def addParticle(self,x,y,z,r,t):
        """
        Add particle to system
        """
        self.Particles.append(Particle(x,y,z,r,t))
        
    
    def getParticle(self,i):
        """
        Get particle in the system
        """
        
        return Particles[i]
    
    def addChain(self, plist):
        """
        Define a new polymer chain
        """
        
        self.Chains.append([])
        for p in plist:
            self.Chains[-1].append(p)
    
    def addRestraint(self, res):
        """
        Add a basic restraint
        """
        assert(isinstance(res,Restraint), "Argument should be a Restraint")
        
        self.Restraints.append(res)
        
    def optimize(self, cfg):
        """
        optimize the model by selected kernel
        """
        
        if cfg["kernel"] == "lammps":
            import .kernel.lammps as lammps
            lammps.optimize(self, cfg)
            
        
#=


