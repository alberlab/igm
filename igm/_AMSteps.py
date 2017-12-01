from __future__ import division, print_function
import numpy as np

from .core import Step
from .model import Model, Particle
from .restraints import Polymer, Envelope, Steric, HiC


from alabtools.analysis import HssFile


class AStep(Step):
    
    def setup(self):
        pass
    
    @staticmethod
    def task(task_id, cfg):
        pass
    
    def reduce(self):
        pass
    
#=

class MStep(Step):
    
    def setup(self):
        self.tmp_extensions = [".npy", ".data", ".lam", ".lammpstrj"]
        self.argument_list = list(range(self.cfg["population_size"]))
        self.structure_prefix = "mstep"
        
    @staticmethod
    def task(struct_id, cfg):
        """
        Do single structure modeling with bond assignment from A-step
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
        
        
        #add Hi-C restraint
        if "Hi-C" in cfg['restraints']:
            dictHiC = cfg['restraints']['Hi-C']
            actdist_file = dictHiC['actdist_file']
            contact_range = dictHiC['contact_range'] if 'contact_range' in dictHiC else 2.0
            k = dictHiC['contact_kspring'] if 'contact_kspring' in dictHiC else 1.0
            
            hic = HiC(actdist_file, contact_range, contact_kspring)
            model.addRestraint(hic)
                    
        
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
            crd = np.load("{}/{}_{}.npy".format(self.cfg['optimization']['tmp_files_dir'], self.structure_prefix, i))
            
            hss.set_struct_crd(i, crd)
        #-
