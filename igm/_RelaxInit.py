from __future__ import division, print_function
import numpy as np

from .core import Step
from .model import Model, Particle
from .restraints import Polymer, Envelope, Steric 

from alabtools.analysis import HssFile

class RelaxInit(Step):
    
    def setup(self):
        self.tmp_extensions = [".npy", ".data", ".lam", ".lammpstrj"]
        self.argument_list = list(range(self.cfg["population_size"]))
        
    @staticmethod
    def task(struct_id, cfg):
        """
        relax one random structure chromosome structures
        """
        
        #extract structure information
        hssfilename    = cfg["structure_output"]
        nucleus_radius = cfg['model']['nucleus_radius']
        
        #read index, radii, coordinates
        with HssFile(hssfilename,'r') as hss:
            index = hss.index
            radii = hss.radii
            crd = hss.get_struct_crd(struct_id)
        
        #init Model 
        model = Model()
        
        #add particles into model
        n_particles = len(crd)
        for i in range(n_particles):
            model.addParticle(crd[i], radii[i], Particle.NORMAL)
        
        #========Add restraint
        #add excluded volume restraint
        ex = Steric(cfg['model']['evfactor'])
        model.addRestraint(ex)
        
        #add nucleus envelop restraint
        ev = Envelope(cfg['model']['nucleus_shape'], 
                      cfg['model']['nucleus_radius'], 
                      cfg['model']['contact_kspring'])
        model.addRestraint(ev)
        
        #add consecutive polymer restraint
        pp = Polymer(index,
                     cfg['model']['contact_range'],
                     cfg['model']['contact_kspring'])
        model.addRestraint(pp)
        
        #========Optimization
        #optimize model
        cfg['optimization']['run_name'] += '_' + str(struct_id)
        model.optimize(cfg['optimization'])
        
        
        model.saveCoordinates("%s/relax_%s.npy"%(cfg['optimization']['tmp_files_dir'], struct_id))
    #-
            
    def reduce(self):
        """
        Collect all structure coordinates together to put hssFile
        """
        hssfilename = self.cfg["structure_output"]
        hss = HssFile(hssfilename,'a')
        
        #iterate all structure files and 
        for i in range(hss.nstruct):
            crd = np.load("%s/relax_%s.npy"%(self.cfg['optimization']['tmp_files_dir'], i))
            
            hss.set_struct_crd(i, crd)
        #-
