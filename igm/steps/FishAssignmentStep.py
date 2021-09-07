from __future__ import division, print_function
import numpy as np
import h5py
import os
import os.path
import shutil
from tqdm import tqdm

from alabtools.analysis import HssFile

from ..core import Step
from ..utils.log import logger

try:
    # python 2 izip
    from itertools import izip as zip
except ImportError:
    pass

# dictionaries for the activation distance files
fish_restr = {'probes': [], 'pairs' : [], 'pair_min': [], 'radial_min' : [] , 'pair_max': [], 'radial_max' : [] }

def get_pair_dists(ii, jj, n_bead, n_conf, crd):
    
    """
    Compute all diploid distances between (pair) annotations
    INPUT:  ii, jj, list of diploid annotations for the i-j pair
    OUTPUT: dists, array (4, n_conf), all diploid distances across all configs in popuations 
    """

    dists = np.empty((4, n_conf))
    
    x1 = crd[ii[0], :, :][()]
    y1 = crd[jj[0], :, :][()]
    x2 = crd[ii[1], :, :][()]
    y2 = crd[jj[1], :, :][()]
        
    dists[0] = np.linalg.norm( x1-y1, axis=1 )
    dists[1] = np.linalg.norm( x1-y2, axis=1 )
    dists[2] = np.linalg.norm( x2-y1, axis=1 )
    dists[3] = np.linalg.norm( x2-y2, axis=1 )

    return dists        # compute the four diploid distances, across all structures
                            # (i,j), (i,j+n_hapl), (i+n_hapl, j), (i+n_hapl, j+n_hapl)


def get_rad_dists(ii, n_bead, n_conf, crd):
    
    """
    Compute radial distances of diploid annotations
    INPUT: ii, list of diploid annotations for the i-th probe
    OUTPUT: dists, array (2, n_conf), all diploid radial distances across all configs in popuations 
    """

    x1 = crd[ii[0], :, :][()]
    x2 = crd[ii[1], :, :][()]    # from haploid to diploid annotation
    
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

        """ This is printed to logger, and indicates that the FISH assignment step has started (and tol and iteration)  """

        s = 'FishAssignmentStep (tol={:.2f}, iter={:s})'
        return s.format(
            self.cfg.get('runtime/FISH/tol', -1),
            str( self.cfg.get('runtime/opt_iter', 'N/A') )
        )


    def setup(self):

        """ Prepare parameters, read in FISH input file and preprocess by spitting that into batches, produce tmp files """

        # read in FISH tolerance, and the filename containing raw FISH data
        tol           = self.cfg.get("runtime/FISH/tol")


        self.tmp_extensions = [".npz"]
        self.set_tmp_path()

        self.keep_temporary_files = self.cfg.get("restraints/FISH/keep_temporary_files", False)

        # create folder
        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)

        # batch size and initialize empty batch list
        batch_size = self.cfg.get('restraints/FISH/batch_size')
        batches = []

        fish_input_file = self.cfg.get('restraints/FISH/input_fish')
       
        # this works for all scenarios: only pairs, only probes, both of them even in different numbers 
        with h5py.File(fish_input_file, 'r') as h5:

            dict_entries = list(h5.keys())

            if 'pairs' in dict_entries:
                 logger.info('pairs are in FISH input!')
                 pairs = h5['pairs'][()]
        
                 for i in range(0, len(pairs), batch_size):
                      batches.append((len(batches), 'pair', pairs[i: i+batch_size]))

            if 'probes' in dict_entries:
                 logger.info('probes are in FISH input')
                 probes = h5['probes'][()]
        
                 for i in range(0, len(probes), batch_size):
                      batches.append((len(batches), 'probe', probes[i: i+batch_size]))

        self.argument_list = batches


    @staticmethod
    def task(batch, cfg, tmp_dir):


        # initialize empty dictionary to be populated later in loop
        fish_restr = {'pair_min': [], 'radial_min' : [] , 'pair_max': [], 'radial_max' : [] }

        
        # read in population file and extract coordinates
        hss = HssFile(cfg.get("optimization/structure_output"), 'r')
        crd = hss['coordinates']
    
        # number of configurations, number of domains
        n_conf = crd.shape[1]
        n_bead = crd.shape[0]

        # from haploid to multiploid representation
        copy_index = hss.index.copy_index

        assert(crd.shape[2] == 3)    # check consistency in array sizes
  
        fish_input_file = cfg.get('restraints/FISH/input_fish')

        # load input file with distributions (maybe check if number of distances = number of poluation structures)
        with h5py.File(fish_input_file, 'r') as ftf:

            # extract dictionary, and check which entries there are
            target_entries = list(ftf.keys())

        # load batches
        batch_id, entry_type, entries = batch

        if entry_type == 'pair':
            for pair in entries:
                i, j = pair
                ii = copy_index[i]
                jj = copy_index[j]

                # Compute all radial and motual distances across all configurations
                pairs_dists =  get_pair_dists(ii, jj,  n_bead, n_conf, crd)

                # min & max distances,   sorting indexes
                (mindists, maxdists, idxmin, idxmax) = get_min_max_and_idx(pairs_dists)

                with h5py.File(fish_input_file, 'r') as ftf:

                    # find pair index (from batch back to the full list)
                    pair_index = list(np.all(ftf['pairs'][()] == pair, axis=1)).index(True)

                    logger.info(pair_index)

                    if (pair_index is None):
                        raise ValueError(f"Cannot find pair: {pair}")

                    if 'pair_min' in  target_entries:
                        target_min = ftf['pair_min'][pair_index][()]
                        fish_restr['pair_min'].append((pair_index, target_min[idxmin]))
                    if 'pair_max' in  target_entries:
                        target_max = ftf['pair_max'][pair_index][()]
                        fish_restr['pair_max'].append((pair_index, target_max[idxmax]))


        if entry_type == 'probe':
            for probe in entries:

                ii = copy_index[probe]

                # Compute all radial and motual distances across all configurations
                rad_dists = get_rad_dists(ii, n_bead, n_conf, crd)

                # min & max radials,   sorting indexes  
                (mindists, maxdists, idxmin, idxmax) = get_min_max_and_idx(rad_dists)

                with h5py.File(fish_input_file, 'r') as ftf:
                    probe_index = np.where(ftf['probes'][()] == probe)[0]   # htis is an array of indices

                    if (len(probe_index) != 1):
                        raise ValueError(f"Cannot find probe: {probe}")
                    
                    probe_index = probe_index[0]

                    if 'radial_min' in  target_entries:
                        target_min = ftf['radial_min'][probe_index][()]
                        fish_restr['radial_min'].append((probe_index, target_min[idxmin]))
                    if 'radial_max' in  target_entries:
                        target_max = ftf['radial_max'][probe_index][()]
                        fish_restr['radial_max'].append((probe_index, target_max[idxmax]))

        #-

        # out of if else, statements, then save stuff into a bunch of different npz files

        # intermediate file, create database, save npz file with features of the chunk (some entries might be empty lists)
        auxiliary_file = os.path.join(tmp_dir, 'tmp.%d.fish_targeting.npz' % batch_id)

        np.savez(auxiliary_file,           
                             pair_min   = np.array(fish_restr['pair_min']),      
                             pair_max   = np.array(fish_restr['pair_max']),
                             radial_min = np.array(fish_restr['radial_min']),  
                             radial_max = np.array(fish_restr['radial_max'])      
               )


    def reduce(self):

        """ Concatenate data from all batches into a single hdf5 fish_actdist file """

        # build suffix to append to actdist file (code does not overwrite actdist files)
        additional_data = []
        if "FISH" in self.cfg['runtime']:
            additional_data.append(
                'tol_{:.4f}'.format(
                    self.cfg['runtime']['FISH']['tol']
                )
            )
        if 'opt_iter' in self.cfg['runtime']:
            additional_data.append(
                'iter_{}'.format(
                    self.cfg['runtime']['opt_iter']
                )
            )


        # create filename
        fish_assignment_file = os.path.join(self.tmp_dir, "fish_assignment.h5")
        last_actdist_file = self.cfg['runtime']['FISH'].get("fish_assignment_file", None)


        # again, read in pairs and probes
        fish_input_file = self.cfg.get('restraints/FISH/input_fish')
        with h5py.File(fish_input_file, 'r') as h5:

            dict_entries = list(h5.keys())

            if 'pairs' in dict_entries:

                   pairs   = h5['pairs'][()]
                   n_pairs = len(pairs)

                   minpairdists = [None] * n_pairs
                   maxpairdists = [None] * n_pairs

            if 'probes' in dict_entries:

                   probes = h5['probes'][()]
                   n_probes = len(probes)

                   minraddists = [None] * n_probes
                   maxraddists = [None] * n_probes

        # (also see 'reduce' step in ActivationDistanceStep.py) Read in all *fish.npz files and concatenate all data into a single
        # 'fish_actdist_file' file, of type h5df (see 'create-dataset attributes)
 
        # concatenate: loop over chunks
        for batch_id, _, _  in self.argument_list:
            
            # load auxiliary files and fill in lists
            auxiliary_file = os.path.join(self.tmp_dir, 'tmp.%d.fish_targeting.npz' % batch_id)
 
            t = np.load(auxiliary_file, allow_pickle=True)

            for pair_index, dists in t['pair_min']:
                minpairdists[pair_index] = dists
            for pair_index, dists in t['pair_max']:
                maxpairdists[pair_index] = dists
            for probe_index, dists in t['radial_min']:
                minraddists[probe_index] = dists
            for probe_index, dists in t['radial_max']:
                maxraddists[probe_index] = dists            


        tmp_assignment_file = fish_assignment_file + '.tmp'

        # write fish actdist file for current iteration: need to distinguish if pairs or not, things are out
        with h5py.File(tmp_assignment_file, "w") as o5f:

            with h5py.File(fish_input_file, 'r') as h5:

                  dict_entries = list(h5.keys())

                  if 'pairs' in dict_entries:
                       o5f.create_dataset('pairs',      data =   pairs,  dtype='i4')

                  if 'pair_min' in dict_entries:
                       o5f.create_dataset('pair_min',   data =  minpairdists,  dtype='f4')

                  if 'pair_max' in dict_entries:
                       o5f.create_dataset('pair_max',   data =  maxpairdists,  dtype='f4')

                  if 'probes' in dict_entries:
                       o5f.create_dataset('probes',     data =  probes,  dtype='i4')

                  if 'radial_min' in dict_entries:
                       o5f.create_dataset('radial_min', data =  minraddists,  dtype='f4')

                  if 'radial_max' in dict_entries:
                       o5f.create_dataset('radial_max', data =  maxraddists,  dtype='f4')
        
        # save file temporary with appends
        swapfile = os.path.realpath('.'.join([fish_assignment_file, ] + additional_data))
        if last_actdist_file is not None:
            shutil.move(last_actdist_file, swapfile)
        shutil.move(tmp_assignment_file, fish_assignment_file)


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
