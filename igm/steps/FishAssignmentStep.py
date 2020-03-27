from __future__ import division, print_function
import numpy as np
import h5py
import os
import os.path

from alabtools.analysis import HssFile

from ..core import Step
from ..utils.log import logger

try:
    # python 2 izip
    from itertools import izip as zip
except ImportError:
    pass

# dictionaries for the activation distance files
fish_restr = { 'pair_min': [], 'radial_min' : [] , 'pair_max': [], 'radial_max' : [] }

def get_pair_dists(pair, n_bead, n_conf, crd):
    
    """
    Compute all diploid distances between (pair) annotations
    INPUT:  pair, 2-uple i,j
    OUTPUT: dists, array (4, n_conf), all diploid distances across all configs in popuations 
    """

    n_hapl = int(n_bead/2)   # haploid domains

    (i1, j1) = pair
    i2 = i1+ n_hapl   # from haploid to diploid annotations
    j2 = j1+ n_hapl

    dists = np.empty((4, n_conf))
    
    x1 = crd[i1, :, :]
    y1 = crd[j1, :, :]
    x2 = crd[i2, :, :]
    y2 = crd[j2, :, :]
        
    dists[0] = np.linalg.norm( x1-y1, axis=1 )
    dists[1] = np.linalg.norm( x1-y2, axis=1 )
    dists[2] = np.linalg.norm( x2-y1, axis=1 )
    dists[3] = np.linalg.norm( x2-y2, axis=1 )

    return dists        # compute the four diploid distances, across all structures
                            # (i,j), (i,j+n_hapl), (i+n_hapl, j), (i+n_hapl, j+n_hapl)


def get_rad_dists(i, n_bead, n_conf, crd):
    
    """
    Compute radial distances of diploid annotations
    INPUT: i, integer  (haploid annotation)
    OUTPUT: dists, array (2, n_conf), all diploid radial distances across all configs in popuations 
    """

    n_hapl = int(n_bead/2)
    
    x1 = crd[i, :, :]
    x2 = crd[i+n_hapl, :, :]    # from haploid to diploid annotation
    
    dists = np.empty((2, n_conf))
    dists[0] = np.linalg.norm( x1, axis=1 )
    dists[1] = np.linalg.norm( x2, axis=1 )
    
    return dists


def get_min_max_and_idx(dists):
    
    """ Among the diploid distances (either radial or pairwise) find the min and max for each structure, and
        ordering indexes...those indexes are used to order the target distances from the distributions """
    
    # find extrema among diploid distances, for each structure in population separately
    mindists = np.min(dists, axis = 0)
    maxdists = np.max(dists, axis = 0)
    
    # sort across population structures and store sorting indexes...will be used later
    
    pairs_replica_min_position = np.argsort(np.argsort(mindists))
    pairs_replica_max_position = np.argsort(np.argsort(maxdists))
    
    return (mindists, maxdists, pairs_replica_min_position, pairs_replica_max_position)


#--------

class FishAssignmentStep(Step):

    def __init__(self, cfg):

        """ The value of FISH tolerances to be used this time around is computed and stored """

        # prepare the list of FISH tolerances in the "runtime" status, unless already there
        if 'tol_list' not in cfg.get("runtime/FISH"):
            cfg["runtime"]["FISH"]["tol_list"] = cfg.get("restraints/FISH/tol_list")[:]

        # compute current FISH tolerance and save that to "runtime" status
        if     'tol'  not in cfg.get("runtime/FISH"):
            cfg["runtime"]["FISH"]["tol"]      = cfg.get("runtime/FISH/tol_list").pop(0)

        super(FishAssignmentStep, self).__init__(cfg)


    def name(self):

        """ This is printed to logger, and indicates that the FISH assignment step has started """

        s = 'FishAssignmentStep (cut={:.2f}%, iter={:s})'
        return s.format(
            self.cfg.get('runtime/FISH/tol', -1) * 100.0,
            str( self.cfg.get('runtime/opt_iter', 'N/A') )
        )


    def setup(self):

        """ Prepare parameters, read in FISH input file and preprocess by spitting that into batches, produce tmp files """

        # read in damid sigma activation, and the filename containing raw damid data
        #FISH_tol           = self.cfg.get("runtime/FISH/FISH_tol")
        #input_FISH         = self.cfg.get("restraints/FISH/fish_file")

        self.tmp_extensions = [".npy", ".tmp"]
        self.set_tmp_path()
        self.keep_temporary_files = self.cfg.get("restraints/FISH/keep_temporary_files", False)

        # create folder
        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)

        fish_input_file = self.cfg.get('restraints/FISH/input_fish')
        
        # read target distribution file, extract "pairs" and "probes"
        with h5py.File(fish_input_file, 'r') as h5:
         
                pairs  = h5['pairs'][()]
                probes = h5['probes'][()]

                n_pairs = len(pairs)
                n_probes = len(probes)

        # open hss population file
        with HssFile(self.cfg.get("optimization/structure_output"), 'r') as hss:
            self.n_struct = hss.nstruct

        """
        # need to define some sort of batches? Assume n_pairs = n_probes If yes
        batch_size = self.cfg.get('restraints/sprite/batch_size', 10)
        n_batches = n_pairs // batch_size

        if n_clusters % batch_size != 0:
            n_batches += 1

        self.n_batches     = n_batches
        self.n_pairs       = n_pairs
        self.n_beads       = n_beads
        self.argument_list = range(n_batches)
        """

        n_batches = 3

        self.n_batches     = n_batches
        self.n_pairs       = n_pairs
        self.argument_list = range(n_batches)


    @staticmethod
    def task(batch_id, cfg, tmp_dir):

        """ Read in temporary in.tmp files, generated list of Damid activation distances, produce out.tmp files """

        #batch_size = cfg.get('restraints/FISH/batch_size', 2)
        batch_size = 1

        # define starting and ending point of current batch
        start = batch_id * batch_size
        stop  = (batch_id + 1) * batch_size
 
        # initialize empty dictionary to be used later in loop
        fish_restr = { 'pair_min': [], 'radial_min' : [] , 'pair_max': [], 'radial_max' : [] }
        
        # read in population file and extract coordinates
        hss = HssFile(cfg.get("optimization/structure_output"), 'r')
        crd = hss['coordinates'][()]
    
        # number of configurations, number of domains
        n_conf = crd.shape[1]
        n_bead = crd.shape[0]

        assert(crd.shape[2] == 3)    # check consistency in array sizes
  
        fish_input_file = cfg.get('restraints/FISH/input_fish')

        # load input file with distributions (maybe check if number of distances = number of poluation structures)
        ftf = h5py.File(fish_input_file, 'r')

        # extract dictionary, and check which entries there are
        dict_entries = list(ftf.keys())

        # if we have pairs information
        if 'pairs' in dict_entries:
            pairs  =  ftf['pairs'][()][start:stop]

            pairs_replica_min_position = []
            pairs_replica_max_position = []
    
            for k, p in enumerate(pairs):

                # Compute all radial and motual distances across all configurations
                pairs_dists =  get_pair_dists(pairs[k],  n_bead, n_conf, crd)

                res = get_min_max_and_idx(pairs_dists)
                
                # min & max distances,   sorting indexes
                (mindists, maxdists, idxmin, idxmax) = res

                pairs_replica_min_position.append(idxmin)   # these are configuration idx
                pairs_replica_max_position.append(idxmax)   # this is configuration idx

                if 'pair_min' in  dict_entries:
                    dtmin = ftf['pair_min'][k][()]      # minimum distances
                    fish_restr['pair_min'].append(dtmin[pairs_replica_min_position[k]])

                if 'pair_max' in  dict_entries:
                    dtmax = ftf['pair_max'][k][()]
                    fish_restr['pair_max'].append(dtmax[pairs_replica_max_position[k]])


        if 'probes' in dict_entries:
            probes = ftf['probes'][()][start:stop]

            raddist_replica_min_position = []
            raddist_replica_max_position = []
    
            for k, i in enumerate(probes):

               # Compute all radial and motual distances across all configurations
               rad_dists   =   get_rad_dists(probes[k], n_bead, n_conf, crd)

               res = get_min_max_and_idx(rad_dists)

               # min & max radials,   sorting indexes  
               (mindists, maxdists, idxmin, idxmax) = res

               raddist_replica_min_position.append(idxmin)   # sequence of ordering indexes for minimum distances
               raddist_replica_max_position.append(idxmax)
    
               if 'radial_min' in dict_entries:
                   dtmin = ftf['radial_min'][k][()]
                   fish_restr['radial_min'].append(dtmin[raddist_replica_min_position[k]])
        
               if 'radial_max' in dict_entries:
                   dtmax = ftf['radial_max'][k][()]
                   fish_restr['radial_max'].append(dtmax[raddist_replica_max_position[k]])
          


        # intermediate file, create database, save npz file with features of the chunk (some entries might be empty lists)
        auxiliary_file = os.path.join(tmp_dir, 'tmp.%d.target.npz' % batch_id)

        np.savez(auxiliary_file,     pairs = pairs,                            probes = probes,
                                 pair_min = np.array(fish_restr['pair_min']),      pair_max = np.array(fish_restr['pair_max']),
                               radial_min = np.array(fish_restr['radial_min']),  radial_max = np.array(fish_restr['radial_max'])      
               )



    def reduce(self):

        """ Concatenate data from all batches into a single hdf5 fish_actdist file """

        # create filename
        fish_assignment_file = os.path.join(self.tmp_dir, "fish_assignment.h5")

        # we start with one empty element to avoid errors in np.concatenate
        target_pairs       = []
        target_raddist     = []
        minpairdists       = []
        maxpairdists       = []
        minraddists        = []
        maxraddists        = []

        # (also see 'reduce' step in ActivationDistanceStep.py) Read in all .out.tmp files and concatenate all data into a single
        # 'damid_actdist_file' file, of type h5df (see 'create-dataset attributes)
        
        # concatenate: loop over chunks
        for i in self.argument_list:
            
            # load auxiliary files and fill in lists
            auxiliary_file = os.path.join(self.tmp_dir, 'tmp.%d.target.npz' % i)
 
            t = np.load(auxiliary_file)

            target_pairs.append(t['pairs'][()])
            target_raddist.append(t['probes'][()])

            minpairdists.append(t['pair_min'][()])
            maxpairdists.append(t['pair_max'][()])

            minraddists.append(t['radial_min'][()])
            maxraddists.append(t['radial_max'][()])


        # write fish actdist file for current iteration, create datasets and smoothly concatenate stuff
        with h5py.File(fish_assignment_file + '.tmp', "w") as o5f:
            o5f.create_dataset('pairs',      data =   np.concatenate(target_pairs),  dtype='i4')
            o5f.create_dataset('probes',     data = np.concatenate(target_raddist),  dtype='i4')
            o5f.create_dataset('pair_min',   data =   np.concatenate(minpairdists),  dtype='f4')
            o5f.create_dataset('pair_max',   data =   np.concatenate(maxpairdists),  dtype='f4')
            o5f.create_dataset('radial_min', data =   np.concatenate( minraddists),  dtype='f4')
            o5f.create_dataset('radial_max', data =   np.concatenate( maxraddists),  dtype='f4')
        
        #o5f.close()

        os.rename(fish_assignment_file + '.tmp', fish_assignment_file)

        # ... update runtime parameter for next iteration/sigma value
        self.cfg['runtime']['FISH']["fish_assignment_file"] = fish_assignment_file


    def skip(self):
        """
        Fix the dictionary values when already completed
        """
        self.set_tmp_path()

        # place file into the tmp_path folder
        fish_assignment_file = os.path.join(self.tmp_dir, "fish_assignment.h5")
        self.cfg['runtime']['FISH']["fish_assignment_file"] = fish_assignment_file


    def set_tmp_path(self):

        """ Auxiliary function to play around with paths and directories """

        curr_cfg = self.cfg['restraints']['FISH']
        fish_tmp_dir = curr_cfg.get('fish_dir', 'fish_actdist')

        if os.path.isabs(fish_tmp_dir):
            self.tmp_dir = fish_tmp_dir
        else:
            self.tmp_dir = os.path.join( self.cfg['parameters']['tmp_dir'], fish_tmp_dir )
            self.tmp_dir = os.path.abspath(self.tmp_dir)

#----
