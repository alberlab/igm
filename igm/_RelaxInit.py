from __future__ import division, print_function
import numpy as np

from .core import StructGenStep
from .model import Model, Particle
from .restraints import Polymer, Envelope, Steric 
from .utils import HmsFile
from alabtools.analysis import HssFile

class RelaxInit(StructGenStep):
    
    def setup(self):
        self.tmp_extensions = [".hms", ".data", ".lam", ".lammpstrj"]
        self.tmp_file_prefix = "relax"
        
    @staticmethod
    def task(struct_id, cfg, tmp_dir):
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
        
        hms = HmsFile("{}/relax_{}.hms".format(tmp_dir, struct_id),'w')
        hms.saveModel(struct_id, model)
        
        hms.saveViolations(pp)
    #-

