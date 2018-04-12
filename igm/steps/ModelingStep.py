from __future__ import division, print_function

import os
import os.path

from alabtools.analysis import HssFile

from ..core import StructGenStep
from ..model import Model, Particle
from ..restraints import Polymer, Envelope, Steric, HiC
from ..utils import HmsFile


class ModelingStep(StructGenStep):

    def name(self):
        s = 'ModelingStep'
        additional_data = []
        if "Hi-C" in self.cfg['restraints']:
            additional_data .append(
                'sigma={:.2f}%'.format(
                    self.cfg['restraints']['Hi-C']['sigma'] * 100.0
                )
            )
        if 'opt_iter' in self.cfg['runtime']:
            additional_data.append(
                'iter={}'.format( 
                    self.cfg['runtime'].get('opt_iter', 'N/A') 
                )
            )

        if len(additional_data):
            s += ' (' + ' ,'.join(additional_data) + ')' 
        return s
    
    def setup(self):
        self.tmp_extensions = [".hms", ".data", ".lam", ".lammpstrj"]
        self.tmp_file_prefix = "mstep"
        
    @staticmethod
    def task(struct_id, cfg, tmp_dir):
        """
        Do single structure modeling with bond assignment from A-step
        """
        #extract structure information
        hssfilename    = cfg["structure_output"]
        
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
            
            hic = HiC(actdist_file, contact_range, k)
            model.addRestraint(hic)
                    
        
        #========Optimization
        #optimize model
        cfg['optimization']['run_name'] += '_' + str(struct_id)
        model.optimize(cfg['optimization'])
        
        ofname = os.path.join(tmp_dir, 'mstep_%d.hms' % struct_id)
        hms = HmsFile(ofname, 'w')
        hms.saveModel(struct_id, model)
        
        hms.saveViolations(pp)
        
        if "Hi-C" in cfg['restraints']:
            hms.saveViolations(hic)
    #-

    def intermediate_name(self):

        additional_data = []
        if "Hi-C" in self.cfg['restraints']:
            additional_data .append(
                'sigma_{:.4f}'.format(
                    self.cfg['restraints']['Hi-C']['sigma']
                )
            )
        if 'opt_iter' in self.cfg['runtime']:
            additional_data.append(
                'iter_{}'.format( 
                    self.cfg['runtime']['opt_iter'] 
                )
            )
        additional_data.append(str(self.uid))

        return '.'.join( [
            self.cfg["structure_output"],   
        ] + additional_data ) 


#==
