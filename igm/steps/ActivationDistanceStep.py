from __future__ import division, print_function
import numpy as np
import h5py
import scipy.io
import scipy.sparse
import os
import os.path
import shutil

from alabtools import Contactmatrix
from alabtools.analysis import HssFile

from tqdm import tqdm

from ..core import Step
from ..utils.files import make_absolute_path

try:
    # python 2 izip
    from itertools import izip as zip
except ImportError:
    pass

# dictionary for the actdist file
actdist_shape = [
    ('row', 'int32'),
    ('col', 'int32'),
    ('dist', 'float32'),
    ('prob', 'float32')
]
actdist_fmt_str = "%6d %6d %10.2f %.5f"


class ActivationDistanceStep(Step):
    def __init__(self, cfg):

	
	""" The value of HiC sigma to be used this time around is defined and stored """

        if 'intra_sigma_list' not in cfg["runtime"]["Hi-C"]:
            cfg["runtime"]["Hi-C"]['intra_sigma_list'] = cfg["restraints"]["Hi-C"]["intra_sigma_list"][:]
        if 'inter_sigma_list' not in cfg["runtime"]["Hi-C"]:
            cfg["runtime"]["Hi-C"]['inter_sigma_list'] = cfg["restraints"]["Hi-C"]["inter_sigma_list"][:]

        logger.info(cfg.get('runtime/Hi-C/inter_sigma_list'))

        logger.info(cfg.get('runtime/Hi-C/intra_sigma_list'))
        logger.info('GUIDO')

        #logger.info(cfg.get('runtime/Hi-C/inter_sigma'))
        #logger.info(cfg.get('runtime/Hi-C/inter_sigma'))


        # 'sigma' indicates the current HiC sigma to use in the Activation Step. 
        # Once 'sigma' is defined, the value is automatically removed from 'inter_sigma_list' and 'intra_sigma_list'
        if ("inter_sigma" not in cfg["runtime"]["Hi-C"]) and ("intra_sigma" not in cfg["runtime"]["Hi-C"]):
            inters = cfg.get('runtime/Hi-C/inter_sigma_list')
            intras = cfg.get('runtime/Hi-C/intra_sigma_list')

            # as of now, assume inters and intras need to have the same lenght
            if len(inters) and len(intras):
                # go to the next sigma, the larger between the intra and inter
                # LB: changed this, let inter and intra be different if inters[0] == intras[0]:
                    cfg.set("runtime/Hi-C/inter_sigma", inters.pop(0))
                    cfg.set("runtime/Hi-C/intra_sigma", intras.pop(0))
                    intra_sigma = cfg.get('runtime/Hi-C/intra_sigma')
                    inter_sigma = cfg.get('runtime/Hi-C/inter_sigma')
                #elif inters[0] > intras[0]:
                #    cfg.set("runtime/Hi-C/inter_sigma", inters.pop(0))
                #    sigma = cfg.get("runtime/Hi-C/inter_sigma")
                #else:
                #    cfg.set("runtime/Hi-C/intra_sigma", intras.pop(0))
                #    sigma = cfg.get("runtime/Hi-C/intra_sigma")

            #elif len(intras):
            #    cfg.set("runtime/Hi-C/intra_sigma", intras.pop(0))
            #    sigma = cfg.get("runtime/Hi-C/intra_sigma")

            #else:
            #    cfg.set("runtime/Hi-C/inter_sigma", inters.pop(0))
            #    sigma = cfg.get("runtime/Hi-C/inter_sigma")

            # set sigma value in cfg["runtime"]
            cfg.set("runtime/Hi-C/inter_sigma", inter_sigma)
            cfg.set("runtime/Hi-C/intra_sigma", intra_sigma)

	
        super(ActivationDistanceStep, self).__init__(cfg)

    # this is printed into the logger file and indicates that the HiC activationdistance step for a given sigma, at a given iteration, starts
    def name(self):
        s = 'ActivationDistanceStep (INTER sigma={:.2f}%, INTRA sigma={:.2f}%, iter={:s})'
        return s.format(
            self.cfg.get('runtime/Hi-C/inter_sigma') * 100.0,
            self.cfg.get('runtime/Hi-C/intra_sigma') * 100.0,
            str(self.cfg.get('runtime/opt_iter', 'NA'))
        )

    def setup(self):

        """ Reading parameters from cfg and actdist files, split into batches and save to tmp files """

        dictHiC        = self.cfg['restraints']['Hi-C']
        #sigma          = self.cfg['runtime']['Hi-C']["sigma"]
        inter_sigma    = self.cfg.get('runtime/Hi-C/inter_sigma', False)
        intra_sigma    = self.cfg.get('runtime/Hi-C/intra_sigma', False)
        contact_matrix = Contactmatrix(dictHiC["input_matrix"])
        input_matrix   = contact_matrix.matrix
        n              = input_matrix.shape[0]

        last_actdist_file = self.cfg.get('runtime/Hi-C').get("actdist_file", None)
        batch_size        = self.cfg.get('restraints/Hi-C/batch_size', 1000)

        self.tmp_extensions = [".npy", ".tmp"]

        self.tmp_dir = make_absolute_path(
            self.cfg.get('restraints/Hi-C/tmp_dir', 'actdist'),
            self.cfg.get('parameters/tmp_dir')
        )

        self.keep_temporary_files = dictHiC.get("keep_temporary_files", False)

        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)

        # get the last iteration corrected probabilities from last_actdist_file...
        # TODO: find a way not to read all to memory?
        if last_actdist_file is not None:
            with h5py.File(last_actdist_file) as h5f:   #-- NB: to get keys, one can use h5f.keys()
                row = h5f["row"][()]
                col = h5f["col"][()]
                ii = np.logical_and(row < n, col < n)
                row = row[ii]
                col = col[ii]
                data = h5f["prob"][ii][()]

                plast = scipy.sparse.coo_matrix(
                    (data, (row, col)),
                    shape=input_matrix.shape
                ).tolil()
        else:
            # ... if there are no corrected probabilities from last iteration (aka, the current iteration is the first iteration)
            # initialize empty sparse lil matrix
            plast = scipy.sparse.lil_matrix(input_matrix.shape)

        # initialize parameters for batch processing
        n_args_batches = 0
        k = 0
        curr_batch = []
        chrom = contact_matrix.index.chrom
        n_keep_intra = 0
        n_keep_inter = 0

        # prepare batches by mapping the plast matrix into a number of .in.npy files
        for i, j, pwish in input_matrix.coo_generator():
            keep1 = (intra_sigma is not False) and (chrom[i] == chrom[j]) and (pwish >= intra_sigma)
            keep2 = (inter_sigma is not False) and (chrom[i] != chrom[j]) and (pwish >= inter_sigma)
            n_keep_intra += keep1
            n_keep_inter += keep2
            if keep1 or keep2:
                curr_batch.append((i, j, pwish, plast[i, j]))
                k += 1

            # if one batch is completed, save to file, reset increment k to 0, augment number of batches
            if k == batch_size:
                fname = os.path.join(self.tmp_dir, '%d.in.npy' % n_args_batches)
                np.save(fname, curr_batch)
                k = 0
                n_args_batches += 1
                curr_batch = []
        # save to file
        fname = os.path.join(self.tmp_dir, '%d.in.npy' % n_args_batches)
        np.save(fname, curr_batch)
        n_args_batches += 1

        # this list [0, 1, ..., n_args_batches] will be passed as a parameter
        self.argument_list = range(n_args_batches)

    @staticmethod
    def task(batch_id, cfg, tmp_dir):

        """ Compute activation distances for batch identified by parameter batch_id """

        dictHiC = cfg['restraints']['Hi-C']
        hss     = HssFile(cfg.get("optimization/structure_output"), 'r')

        # read params
        fname   = os.path.join(tmp_dir, '%d.in.npy' % batch_id)
        params  = np.load(fname)

        # initialize result list
        results = []

        # compute activation distances for all pairs of locus indexes, append to "results" list
        for i, j, pwish, plast in params:
            res = get_actdist(
                int(i), int(j), pwish, plast, hss,
                contactRange=dictHiC.get('contact_range', 2.0)
            )

            for r in res:
                results.append(r)  # (i, j, actdist, p)
            # -

        hss.close()

        # save activation distances from current batch to a batch-unique output file, using format specifier 'actdist_fmt_str'
        fname = os.path.join(tmp_dir, '%d.out.tmp' % batch_id)
        with open(fname, 'w') as f:
            f.write('\n'.join([actdist_fmt_str % x for x in results]))



    def reduce(self):

        """ Concatenate data from all batches into a single hdf5 'actdist' file """

        actdist_file      = os.path.join(self.tmp_dir, "actdist.hdf5")
        last_actdist_file = self.cfg['runtime']['Hi-C'].get("actdist_file", None)
        row = []
        col = []
        dist = []
        prob = []

        # poll all files and strap them together into a single file output
        for i in tqdm(self.argument_list, desc='(REDUCE)'):

            fname           = os.path.join(self.tmp_dir, '%d.out.tmp' % i)
            partial_actdist = np.genfromtxt(fname, dtype=actdist_shape)

            if partial_actdist.ndim == 0:
                partial_actdist = np.array([partial_actdist], dtype=actdist_shape)

            row.append(partial_actdist['row'])
            col.append(partial_actdist['col'])
            dist.append(partial_actdist['dist'])
            prob.append(partial_actdist['prob'])
        #-

       # build suffix to append to actdist file (code does not overwrite actdist files)
        additional_data = []
        if "Hi-C" in self.cfg['runtime']:
            additional_data.append(
                'INTERsigma_{:.4f}'.format(
                    self.cfg['runtime']['Hi-C'].get('inter_sigma', -1.0)
                )
            )

            additional_data.append(
                'INTRAsigma_{:.4f}'.format(
                    self.cfg['runtime']['Hi-C'].get('intra_sigma', -1.0)
                )
            )
        if 'opt_iter' in self.cfg['runtime']:
            additional_data.append(
                'iter_{}'.format(
                    self.cfg['runtime']['opt_iter']
                )
            )


        # this is the activation distance tmp file storing the information about the currect act step
        tmp_actdist_file = actdist_file + '.tmp'

        # concatenate all the information and saeve to file
        with h5py.File(tmp_actdist_file, "w") as h5f:
            h5f.create_dataset("row",  data=np.concatenate(row))
            h5f.create_dataset("col",  data=np.concatenate(col))
            h5f.create_dataset("dist", data=np.concatenate(dist))
            h5f.create_dataset("prob", data=np.concatenate(prob))
        # -

        swapfile = os.path.realpath('.'.join([actdist_file, ] + additional_data))
        if last_actdist_file is not None:
            shutil.move(last_actdist_file, swapfile)
        shutil.move(tmp_actdist_file, actdist_file)

        # update runtime entry in dictionary, for next iteration/step
        self.cfg['runtime']['Hi-C']["actdist_file"] = actdist_file

    def skip(self):
        '''
        Fix the dictionary values when already completed
        '''
        self.tmp_dir = make_absolute_path(
            self.cfg.get('restraints/Hi-C/tmp_dir', 'actdist'),
            self.cfg.get('parameters/tmp_dir')
        )
        self.actdist_file = os.path.join(self.tmp_dir, "actdist.hdf5")
        self.cfg['runtime']['Hi-C']["actdist_file"] = self.actdist_file
# =



def cleanProbability(pij, pexist):

    """ Clean probabilities by correcting for the number of restraints applied already.
        Procedure is detailed in Nan's PhD proposal, section 2 """

    if pexist < 1:
        pclean = (pij - pexist) / (1.0 - pexist)
    else:
        pclean = pij
    return max(0, pclean)



def get_actdist(i, j, pwish, plast, hss, contactRange=2, option=0):

    '''
    Serial function to compute the activation distance for a pair of loci.

    Parameters
    ----------
        i, j : int
            index of the first, second locus
        pwish : float
            target contact probability
        plast : float
            the last refined probability
        hss : alabtools.analysis.HssFile
            file containing coordinates
        contactRange : int
            contact range of sum of radius of beads
        option : int
            calculation option:
            (0) intra chromosome contacts are considered intra
            (1) intra chromosome contacts are assigned intra/inter equally
    Returns
    -------
	List res of [i, j, ad, p] arrays

        i (int): index of first locus
        j (int): index of second locus
        ad (float): the activation distance
        p (float): the corrected probability
    '''

    # import here in case is executed on a remote machine
    import numpy as np

    # there is no contact between i and i (even between homologous locii on different copies of the same chromosome)
    if i == j:
        return []

    n_struct = hss.get_nstruct()
    copy_index = hss.get_index().copy_index

    # extract for each locus the chromosome index it belongs to
    chrom = hss.get_index().chrom

    # extract indexes of homologous locii
    ii = copy_index[i]    # ii = [a, b], a is index on first chromosome, b is index on other copy
    jj = copy_index[j]

    #n_combinations = len(ii) * len(jj)
    ## n_possible_contacts = np.max(hss.index.copy) + 1
    #n_possible_contacts = min(len(ii), len(jj))
    ## for diploid cell n_combinations = 2*2 =4
    ## n_possible_contacts = 2

    radii = hss.get_radii()
    ri, rj = radii[ii[0]], radii[jj[0]]

    if chrom[i] == chrom[j]:   # intrachromosomal

        n_combinations = len(ii)
        n_possible_contacts = min(len(ii), len(jj))   # consider diploid and haploid
        d_sq = np.empty((n_combinations, n_struct))

        it = 0

        for k, m in zip(ii, jj):    # loop over the (i,j) and (i',j') 

            x = hss.get_bead_crd(k)
            y = hss.get_bead_crd(m)

            d_sq[it] = np.sum(np.square(x - y), axis=1)
            it += 1

    else:      # interchromosomal

        n_combinations = len(ii) * len(jj)
        n_possible_contacts = len(ii) * len(jj)    # consider diploid and haploid
        d_sq = np.empty((n_combinations, n_struct))

        it = 0
        for k in ii:
            for m in jj:
               # extract array coordinates [ii[0], ii[1]], [jj[0], jj[1]]
               x = hss.get_bead_crd(k)
               y = hss.get_bead_crd(m)

               # compute (i-j) distances for all structures in population
               d_sq[it] = np.sum(np.square(x - y), axis=1)
               it += 1
		

    # define i-j contact value
    rcutsq = np.square(contactRange * (ri + rj))

    # sort distance arrays along the 'number of pairs' axis (along each column)
    d_sq.sort(axis=0)

    # compute absolute number of contacts on a matrix subset (n_poss_cont, n_struct)
    contact_count = np.count_nonzero(d_sq[0:n_possible_contacts, :] <= rcutsq)
    
    # probability of i-j contact (diploid!) as from structures in hss file
    pnow = float(contact_count) / (n_possible_contacts * n_struct)

    # now, sort the whole matrix along both axes, and reshape that into a vector
    sortdist_sq = np.sort(d_sq[0:n_possible_contacts, :].ravel())

    # iterative correction to the probability (see Nan's PhD proposal)

    # compute the fraction of excess contacts imposed 
    t = cleanProbability(pnow, plast)

    # compute the 'corrected probability' of contacts to be assigned, to be used to 
    # determine the activation distances for Hi-C restraints
    p = cleanProbability(pwish, t)

    res = []

    if p > 0:

        # identify the index pointing to what it is understood as activation distance
        o = min(n_possible_contacts * n_struct - 1,
                int(round(n_possible_contacts * p * n_struct)))
        
        # identify the activation distance as the o-th quantile
        activation_distance = np.sqrt(sortdist_sq[o])

        # if locii from same chromosome, there is a flag...if flag == 0, then
        # contacts between different copies are discarded (WHY?)
        if (chrom[i] == chrom[j]) and (option == 0):
            res = [(i0, i1, activation_distance, p) for i0, i1 in zip(ii, jj)]
        else:
            # if locii on different chromosomes, then we have 4 pairs of distances
            res = [(i0, i1, activation_distance, p) for i0 in ii for i1 in jj]

    # return a list (n_pairs, 4), n_pairs = number of independent pairs
    return res


# this seems to be DEPRECATED, not used
def newton_prob(p_wish, x_now, x_last, p_now, p_last):
    # value of the functions
    f_now = p_now - p_wish
    f_last = p_last - p_wish
    derivative = (f_now - f_last) / (x_now - x_last)
    x_new = x_now - f_now / derivative
    return x_new
