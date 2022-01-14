#
#
# This code performs the ASSIGNEMET STEP for single cell SPRITE data (Quinodoz, 2018). THe numerics is detailed in the Supporting Information under
# "Assignment/SPRITE"
#
# --------------------------------
# --------------------------------


from __future__ import division, print_function
import numpy as np
import h5py
import os
import os.path

from alabtools.analysis import HssFile
from ..cython_compiled.sprite import compute_gyration_radius
from ..utils.files import make_absolute_path
from ..core import Step

from tqdm import tqdm

try:
    # python 2 izip
    from itertools import izip as zip
except ImportError: 
    pass

class SpriteAssignmentStep(Step):

    def __init__(self, cfg):

        """ The value of SPRITE SCALING to be used this time around is computed and stored """

        # prepare the list of SPRITE tolerances in the "runtime" status, unless already there
        if 'volume_fraction_list' not in cfg.get("runtime/sprite"):
            cfg["runtime"]["sprite"]["volume_fraction_list"] = cfg.get("restraints/sprite/volume_fraction_list")[:]

        # compute current SPRITE tolerance and save that to "runtime" status
        if     'volume_fraction'  not in cfg.get("runtime/sprite"):
            cfg["runtime"]["sprite"]["volume_fraction"]      = cfg.get("runtime/sprite/volume_fraction_list").pop(0)

        super(SpriteAssignmentStep, self).__init__(cfg)


    def name(self):

        """ Define auxiliary name for the igm step """

        s = 'SpriteAssignmentStep (volume_fraction={:.1f}%, iter={:s})'
        return s.format(
            self.cfg.get('runtime/sprite/volume_fraction', -1),
            str( self.cfg.get('runtime/opt_iter', 'N/A') )
        )


    def setup(self):

        opt = self.cfg['restraints']['sprite'] 
        
        self.tmp_extensions = [".npy", ".npz"]

        self.tmp_dir = make_absolute_path(
            self.cfg.get('restraints/sprite/tmp_dir', 'sprite'),
            self.cfg.get('parameters/tmp_dir')
        )
        
        self.keep_temporary_files = self.cfg.get('restraints/sprite/keep_temporary_files', False)
        
        if not os.path.isdir(self.tmp_dir):
            os.makedirs(self.tmp_dir)
        #---

        clusters_file = self.cfg.get('restraints/sprite/clusters')
        with h5py.File(clusters_file, 'r') as h5:
            n_clusters = len(h5['indptr']) - 1

        with HssFile(self.cfg.get("optimization/structure_output"), 'r') as hss:
            self.n_struct = hss.nstruct

        batch_size = self.cfg.get('restraints/sprite/batch_size', 10)
        n_batches = n_clusters // batch_size
        if n_clusters % batch_size != 0:
            n_batches += 1

        self.n_batches = n_batches
        self.n_clusters = n_clusters
        self.argument_list = range(n_batches)
            
    @staticmethod
    def task(batch_id, cfg, tmp_dir):

        clusters_file = cfg.get('restraints/sprite/clusters')
        batch_size = cfg.get('restraints/sprite/batch_size', 10)
        keep_best = cfg.get('restraints/sprite/keep_best', 50)

        # read the clusters
        with h5py.File(clusters_file, 'r') as h5:
            start = batch_id*batch_size
            stop = (batch_id+1)*batch_size + 1
            ii = h5['indptr'][start:stop][()]
            data = h5['data'][ii[0]:ii[-1]] #load everything for performance
            ii -= ii[0]   # subtract offset (ii[0]) from the full ii array

            # generate a list of arrays of 'stop-start' length
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

            # effective number of different chromosomes involved in current cluster (no repetition)
            n_chrom = len(np.unique(index.chrom[cluster]))

            # if max_chrom_in_cluster exceeeded, then append arrays full of -1 entries
            if n_chrom > cfg.get('restraints/sprite/max_chrom_in_cluster', 6):
                selected_beads.append( 
                    np.zeros( ( keep_best, len(cluster) ), dtype='i4' ) - 1    # matrix (keep_best, len(cluster)) of -1s
                )
                indexes.append(np.array([-1]*keep_best))    # array with "keep_best" -1 entries
                values.append(np.array([-1]*keep_best))     # array with "keep_best" -1 entries
                continue

            # compute radius**2 of giration for a set of genomic segments, across population (three outputs)
            # NB: current_selected_beads = the bead indexes making up the cluster after considering the possible combinations of chromosome copies.
            rg2s, _, current_selected_beads = compute_gyration_radius(
                hss['coordinates'], 
                cluster, 
                index, 
                index.copy_index
            )

            # rg2s = array of size (n_struct), one radius of gyration for each structure, for a given cluster
            # current_selected_beads = array/list of (n_struct, len(cluster)), each row pertains to a different configuration

            # ind is the array of indexes which would sort the array, aka rg2s[ind[0]] <= rgs2[ind[1]] <= ...
	    # sorting out radii of gyration array, from smallest to largest
            # (using argpartition & argsort is suggested on stackoverflow, in order to maximize efficiency)

            ind = np.argpartition(rg2s, keep_best)[:keep_best] # this is O(n_struct)
            ind = ind[np.argsort(rg2s[ind])] # sorting is O(keep_best ln(keep_best))
            
            # extract sorted arrays (smallest keep_best entries)
            best_rg2s = rg2s[ind]
            current_selected_beads = current_selected_beads[ind]    # select the indices of "keep_best" configurations, and correpsonding beads
                                                                    # for each configuration, we have the bead indexes associated to rg.. the numnber
                                                                    # of beads is determined by the size of the cluster
            # append quantities to master lists, which sweeps over the different clusters in batch
            selected_beads.append(current_selected_beads)
            indexes.append(ind)
            values.append(best_rg2s)    # append keep_best best values of radii of gyration
        
        #------- saving step into a batch-dependent set of files
        sel_file = os.path.join(tmp_dir, 'tmp.%d.selected.npz' % batch_id )
        idx_file = os.path.join(tmp_dir, 'tmp.%d.idx.npy' % batch_id )
        val_file = os.path.join(tmp_dir, 'tmp.%d.values.npy' % batch_id )

        np.savez(sel_file, *selected_beads)    # for each configuration in batch, save list of beads making up the cluster (batch_size, keep_best, n_beads)
                                               # n_beads is different from cluster to cluster (different cluster sizes)
        np.save(idx_file, np.array(indexes, dtype=np.int32))  # save indices of configurations explored in current batch (batch_size, keep_best)
        np.save(val_file, values)     # save radius of gyration values for each of the configutations explored in current batch (batch_size, rg)

        # verify pickle integrity, sometimes weird io problems happen
        selected_beads = np.load(sel_file)
        indexes = np.load(idx_file)        
        values = np.load(val_file)
        
    def reduce(self):

        # using random order, to minimize biases
        random_order = np.random.permutation(self.argument_list)
        clusters_file = self.cfg.get('restraints/sprite/clusters')
        batch_size = self.cfg.get('restraints/sprite/batch_size', 10)
        kT = self.cfg.get('restraints/sprite/radius_kt', 100.0)

        # initialize stuff
        occupancy = np.zeros(self.n_struct, dtype=np.int32)
        assignment = np.zeros(self.n_clusters, dtype=np.int32)
        aveN = float(self.n_clusters) / self.n_struct
        stdN = np.sqrt(aveN)

        with h5py.File(clusters_file, 'r') as h5:
            indptr = h5['indptr'][()]
            
        assignment_filename = make_absolute_path(
            self.cfg.get('restraints/sprite/assignment_file', 'assignment.h5'),
            self.tmp_dir
        )


        with h5py.File(assignment_filename, 'w') as assignment_file:    # LB ---  turned 'r+' to 'w', 08/22

            if not 'assignment' in assignment_file:
                assignment_file.create_dataset('assignment', (self.n_clusters, ), dtype=np.int32)

            if not 'selected'   in assignment_file:
                assignment_file.create_dataset('selected', (indptr[-1], ), dtype=np.int32)

            if not 'indptr'     in assignment_file:
                assignment_file.create_dataset('indptr', data = indptr)

            # loop over different batches, with progress status bar
            for batch_id in tqdm(random_order, desc='(REDUCE)'):

                # load all files for current batch
                idx_file = os.path.join(self.tmp_dir, 'tmp.%d.idx.npy' % batch_id )
                structure_indexes = np.load(idx_file)    # indices of configurations in batch

                val_file = os.path.join(self.tmp_dir, 'tmp.%d.values.npy' % batch_id )
                rg2_values = np.load(val_file)           # value of radii of giration for configurations in batch     

                sel_file = os.path.join(self.tmp_dir, 'tmp.%d.selected.npz' % batch_id )
                selected_beads_zip = np.load(sel_file)   # set of beads (diploid numbering) used to compute Rg for each configuration in batch 

                # map results using zip (Rg values and indexes of corresponding configurations)
                results = zip(rg2_values, structure_indexes)

                assigned_beads = []

                # use a Gibbs distribution with penalty to establish which structure should express which cluster
                for i, (best_rg2s, curr_idx) in enumerate(results):   # i is a counter
                    
                    # 'best_rg2s' and 'curr_idx' are arrays, each pertaining a given cluster in current batch
                    ci = i + batch_id*batch_size # cluster id

                    if best_rg2s[0] < 0:    # negative radius of gyration squared (should not happen)
                        pos = 0
                        si = -1
                    else:
                        # compute radius of gyration (lenght value)
                        best_rgs = np.sqrt(best_rg2s)

                        # given an interval, values outside the interval are clipped to the lowest edge (no upper limit)
                        structure_penalizations = np.clip(occupancy[curr_idx] - aveN, 0., None) / stdN
                        E = (best_rgs-best_rgs[0])/kT + structure_penalizations

                        # cumulative sum of the exponent, returns an array
                        P = np.cumsum(np.exp(-(E-E[0])))     # P is sorted per construction

                        # last element, which is the sum of all the exponents = partition function
                        Z = P[-1]

                        # scale partition function by random numebr
                        e = np.random.rand()*Z

                        # In which position shall we add 'e' to array 'P such that 'P' is still sorted?
                        pos = np.searchsorted(P, e, side='left')
                        si = curr_idx[pos]    # 'si' is the index of structure that occupies pos-th place in curr_idx array
                        occupancy[si] += 1

                    # array 'n_cluster' long, contains the index of structure each cluster is assigned to
                    assignment[ci] = si
                    
                    # select the (diploid) bead indexes associated with cluster identified by 'pos'
                    assigned_beads.append(selected_beads_zip[ 'arr_%i' % i][pos])

                # look above: clustering partitioning
                start = indptr[ batch_id * batch_size ]
                stop  = indptr[ batch_id * batch_size + len(assigned_beads) ]
  
                # (diploid) bead indexes associated with each cluster, cluster range 'start' to 'stop'
                assignment_file['selected'][start:stop] = np.concatenate(assigned_beads)

            assignment_file['assignment'][...] = assignment
#=  
    
