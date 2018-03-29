from __future__ import division, print_function
import numpy as np
import h5py
import scipy.io
import os
import os.path

from .core import Step, StructGenStep
from .model import Model, Particle
from .restraints import Polymer, Envelope, Steric, HiC
from .utils import get_actdist, HmsFile

from alabtools.analysis import HssFile

try:
    from itertools import izip as zip
except ImportError: 
    pass

actdist_shape = [('row', 'int32'), ('col', 'int32'), ('dist', 'float32'), ('prob', 'float32')]
actdist_fmt_str = "%6d %6d %10.2f %.5f"

class ActivationDistanceStep(Step):
    
    def setup(self):
        dictHiC = self.cfg['restraints']['Hi-C']
        sigma = dictHiC["sigma"]
        input_matrix = dictHiC["input_matrix"]
        
        self.tmp_extensions = [".npy", ".tmp"]
        self.tmp_dir = "{}/{}".format(self.cfg["tmp_dir"],
                                      dictHiC["actdist_dir"] if "actdist_dir" in dictHiC else "actdist")
        self.keep_temporary_files = False
        
        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)
        #---
        
        probmat = scipy.io.mmread(input_matrix)
        mask    = probmat.data >= sigma
        ii      = probmat.row[mask]
        jj      = probmat.col[mask]
        pwish   = probmat.data[mask]
        
        if "actdist_file" in dictHiC:
            with h5py.File(dictHiC["actdist_file"]) as h5f:
                last_prob = {(i, j) : p for i, j, p in zip(h5f["row"], h5f["col"], h5f["prob"])}
        else:
            last_prob = {}
        
        batch_size = 100
        n_args_batches = len(ii) // batch_size
        
        
        if len(ii) % batch_size != 0:
            n_args_batches += 1
        for b in range(n_args_batches):
            start = b * batch_size
            end = min((b+1) * batch_size, len(ii))
            params = np.array([(ii[k], jj[k], pwish[k], last_prob.get((ii[k], jj[k]), 0.))
                            for k in range(start, end)], dtype=np.float32)
            np.save('%s/%d.in.npy' % (self.tmp_dir, b), params)
        
        self.argument_list = range(n_args_batches)
            
    @staticmethod
    def task(batch_id, cfg, tmp_dir):
        
        dictHiC = cfg['restraints']['Hi-C']
        hss     = HssFile(cfg["structure_output"], 'r+')
        
        # read params
        params = np.load('%s/%d.in.npy' % (tmp_dir, batch_id))
        
        results = []
        for i, j, pwish, plast in params:
            res = get_actdist(int(i), int(j), pwish, plast, hss, 
                              contactRange = dictHiC['contact_range'] if 'contact_range' in dictHiC else 2.0)
            
            for r in res:
                results.append(r) #(i, j, actdist, p)
            #-
        #--
        hss.close()
        with open("%s/%d.out.tmp" % (tmp_dir, batch_id), 'w') as f:
            f.write('\n'.join([actdist_fmt_str % x for x in results]))
        
    def reduce(self):
        actdist_file = "actdist.hdf5"
        
        row = []
        col = []
        dist = []
        prob = []
        
        for i in self.argument_list:
            partial_actdist = np.genfromtxt("%s/%d.out.tmp" % (self.tmp_dir, i), dtype = actdist_shape)
            row.append(partial_actdist['row'])
            col.append(partial_actdist['col'])
            dist.append(partial_actdist['dist'])
            prob.append(partial_actdist['prob'])
        
        with h5py.File("{}/{}".format(self.tmp_dir, actdist_file),"w") as h5f:
            h5f.create_dataset("row", data=np.concatenate(row))
            h5f.create_dataset("col", data=np.concatenate(col))
            h5f.create_dataset("dist", data=np.concatenate(dist))
            h5f.create_dataset("prob", data=np.concatenate(prob))
        #-
        self.cfg['restraints']['Hi-C']["actdist_file"] = "{}/{}".format(self.tmp_dir, actdist_file)
#=



class ModelingStep(StructGenStep):
    
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
        
        hms = HmsFile("{}/mstep_{}.hms".format(tmp_dir, struct_id),'w')
        hms.saveModel(struct_id, model)
        
        hms.saveViolations(pp)
        
        if "Hi-C" in cfg['restraints']:
            hms.saveViolations(hic)
    #-
#==
