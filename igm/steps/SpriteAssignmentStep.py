from __future__ import division, print_function
import numpy as np
import h5py
import os
import os.path
import sys

from alabtools.analysis import HssFile
from ..cython_compiled.sprite import compute_gyration_radius

from ..utils.log import print_progress
from ..core import Step

from tqdm import tqdm

try:
    # python 2 izip
    from itertools import izip as zip
except ImportError: 
    pass

class SpriteAssignmentStep(Step):

    def name(self):
        s = 'SpriteAssignmentStep (volume_fraction={:.1f}%)' 
        return s.format(
            self.cfg['restraints']['sprite']['volume_fraction'] * 100.0
        )

    def setup(self):

        opt = self.cfg['restraints']['sprite'] 
        
        self.tmp_extensions = [".npy", ".npz"]
        
        self.tmp_dir = opt['tmp_dir']

        self.keep_temporary_files = opt['keep_temporary_files']
        
        if not os.path.isdir(self.tmp_dir):
            os.makedirs(self.tmp_dir)
        #---

        clusters_file = opt['clusters']
        with h5py.File(clusters_file, 'r') as h5:
            n_clusters = len(h5['indptr']) - 1

        with HssFile(self.cfg.get("optimization/structure_output"), 'r') as hss:
            self.n_struct = hss.nstruct

        batch_size = opt['batch_size']
        n_batches = n_clusters // batch_size
        if n_clusters % batch_size != 0:
            n_batches += 1

        self.n_batches = n_batches
        self.n_clusters = n_clusters
        self.argument_list = range(n_batches)
            
    @staticmethod
    def task(batch_id, cfg, tmp_dir):
        
        opt = cfg['restraints']['sprite'] 
        clusters_file = cfg.get('restraints/sprite/clusters')
        batch_size = cfg.get('restraints/sprite/batch_size', 150)
        keep_best = cfg.get('restraints/sprite/keep_best', 50)

        # read the clusters
        with h5py.File(clusters_file, 'r') as h5:
            start = batch_id*batch_size
            stop = (batch_id+1)*batch_size + 1
            ii = h5['indptr'][start:stop][()]
            data = h5['data'][ii[0]:ii[-1]] #load everything for performance
            ii -= ii[0]
            clusters = [
                data[ ii[i-1] : ii[i] ]
                for i in range(1, len(ii))
            ]
            del data

        # open the structure file and read index
        hss     = HssFile(cfg.get("optimization/structure_output"), 'r')
        index = hss.index
            
        indexes, values, selected_beads = [], [], []
        
        for cluster in clusters:
            n_chrom = len(np.unique(index.chrom[cluster]))
            if n_chrom > cfg.get('restraints/sprite/max_chrom_in_cluster', 6):
                selected_beads.append( 
                    np.zeros( ( keep_best, len(cluster) ), dtype='i4' ) - 1
                )
                indexes.append(np.array([-1]*keep_best))
                values.append(np.array([-1]*keep_best))
                continue
            rg2s, _, current_selected_beads = compute_gyration_radius(
                hss['coordinates'], 
                cluster, 
                index, 
                index.copy_index
            )
            ind = np.argpartition(rg2s, keep_best)[:keep_best] # this is O(n_struct)
            ind = ind[np.argsort(rg2s[ind])] # sorting is O(keep_best ln(keep_best))
            best_rg2s = rg2s[ind]
            #print(len(ind))
            current_selected_beads = current_selected_beads[ind]
            selected_beads.append(current_selected_beads)
            indexes.append(ind)
            values.append(best_rg2s)
        
        idx_file = os.path.join(tmp_dir, 'tmp.%d.idx.npy' % batch_id )
        val_file = os.path.join(tmp_dir, 'tmp.%d.values.npy' % batch_id )
        sel_file = os.path.join(tmp_dir, 'tmp.%d.selected.npz' % batch_id )

        np.save(val_file, values)
        np.save(idx_file, np.array(indexes, dtype=np.int32))
        np.savez(sel_file, *selected_beads)

        # verify pickle integrity, sometimes weird io problems happen
        values = np.load(val_file)
        indexes = np.load(idx_file)
        selected_beads = np.load(sel_file)
        
    def reduce(self):

        # using random order, to minimize biases
        random_order = np.random.permutation(self.argument_list)
        opt = self.cfg['restraints']['sprite'] 
        clusters_file = opt['clusters']
        batch_size = opt['batch_size']
        kT = opt['radius_kt']

        occupancy = np.zeros(self.n_struct, dtype=np.int32)
        assignment = np.zeros(self.n_clusters, dtype=np.int32)
        aveN = float(self.n_clusters) / self.n_struct
        stdN = np.sqrt(aveN)

        with h5py.File(clusters_file, 'r') as h5:
            indptr = h5['indptr'][()]
            
        assignment_file = h5py.File(opt['assignment_file'])
        if not 'assignment' in assignment_file:
            assignment_file.create_dataset('assignment', (self.n_clusters, ), dtype=np.int32)

        if not 'selected' in assignment_file:
            assignment_file.create_dataset('selected', (indptr[-1], ), dtype=np.int32)

        if not 'indptr' in assignment_file:
            assignment_file.create_dataset('indptr', data=indptr)

        for batch_id in tqdm(random_order, desc='(REDUCE)'):
            idx_file = os.path.join(self.tmp_dir, 'tmp.%d.idx.npy' % batch_id )
            val_file = os.path.join(self.tmp_dir, 'tmp.%d.values.npy' % batch_id )
            sel_file = os.path.join(self.tmp_dir, 'tmp.%d.selected.npz' % batch_id )
            structure_indexes = np.load(idx_file)
            rg2_values = np.load(val_file)
            selected_beads_zip = np.load(sel_file)
            results = zip(rg2_values, structure_indexes)

            assigned_beads = []

            for i, (best_rg2s, curr_idx) in enumerate(results):
                ci = i + batch_id*batch_size # cluster id
                    
                if best_rg2s[0] < 0:
                    pos = 0
                    si = -1
                else:
                    best_rgs = np.sqrt(best_rg2s)
                    structure_penalizations = np.clip(occupancy[curr_idx] - aveN, 0., None) / stdN
                    E = (best_rgs-best_rgs[0])/kT + structure_penalizations
                    P = np.cumsum(np.exp(-(E-E[0])))
                    Z = P[-1]
                    e = np.random.rand()*Z
                    pos = np.searchsorted(P, e, side='left')
                    si = curr_idx[pos]
                    occupancy[si] += 1
                
                assignment[ci] = si
                assigned_beads.append(selected_beads_zip[ 'arr_%i' % i][pos])

            start = indptr[ batch_id * batch_size ]
            stop = indptr[ batch_id * batch_size + len(assigned_beads) ]

            assignment_file['selected'][start:stop] = np.concatenate(assigned_beads)
        
        assignment_file['assignment'][...] = assignment
        assignment_file.close()
#=  
    
