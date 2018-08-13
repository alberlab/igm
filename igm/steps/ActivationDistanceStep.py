from __future__ import division, print_function
import numpy as np
import h5py
import scipy.io
import scipy.sparse
import os
import os.path

from alabtools import Contactmatrix
from alabtools.analysis import HssFile

from tqdm import tqdm

from ..core import Step
from ..utils.files import make_absolute_path
#from ..parallel.utils import batch

try:
    # python 2 izip
    from itertools import izip as zip
except ImportError:
    pass


actdist_shape = [
    ('row', 'int32'),
    ('col', 'int32'),
    ('dist', 'float32'),
    ('prob', 'float32')
]
actdist_fmt_str = "%6d %6d %10.2f %.5f"


class ActivationDistanceStep(Step):
    def __init__(self, cfg):
        super(ActivationDistanceStep, self).__init__(cfg)
        
        # prepare the list of sigmas in the runtime status
        if 'sigma_list' not in cfg["runtime"]["Hi-C"]:
            cfg["runtime"]["Hi-C"]['sigma_list'] = cfg["restraints"]["Hi-C"]["sigma_list"][:]
        if "sigma" not in cfg["runtime"]["Hi-C"]:
            cfg["runtime"]["Hi-C"]["sigma"] = cfg["runtime"]["Hi-C"]["sigma_list"].pop(0)
            
    def name(self):
        s = 'ActivationDistanceStep (sigma={:.2f}%, iter={:s})'
        return s.format(
            self.cfg['runtime']['Hi-C']['sigma'] * 100.0,
            str( self.cfg['runtime'].get('opt_iter', 'N/A') )
        )

    def setup(self):
        dictHiC = self.cfg['restraints']['Hi-C']
        sigma = self.cfg['runtime']['Hi-C']["sigma"]
        input_matrix = Contactmatrix(dictHiC["input_matrix"]).matrix
        n = input_matrix.shape[0]
        last_actdist_file = self.cfg['runtime']['Hi-C'].get("actdist_file", None)
        batch_size = dictHiC.get('batch_size', 1000)

        self.tmp_extensions = [".npy", ".tmp"]

        self.tmp_dir = make_absolute_path(
            self.cfg['restraints']['Hi-C'].get('tmp_dir', 'actdist'),
            self.cfg['parameters']['tmp_dir']
        )

        self.keep_temporary_files = dictHiC.get("keep_temporary_files", False)

        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)
        #---

        # get the last iteration corrected probabilities.
        # TODO: find a way not to read all to memory?
        if last_actdist_file is not None:
            with h5py.File(last_actdist_file) as h5f:
                row = h5f["row"][()]
                col = h5f["col"][()]
                ii = np.logical_and( row < n, col < n )
                row = row[ii]
                col = col[ii]
                data = h5f["prob"][ii][()]

                plast = scipy.sparse.coo_matrix(
                    ( data, ( row, col ) ),
                    shape=input_matrix.shape
                ).tolil()
        else:
            plast = scipy.sparse.lil_matrix(input_matrix.shape)

        # write parameters to process to files, split in batches
        n_args_batches = 0
        k = 0
        curr_batch = []
        for i, j, pwish in input_matrix.coo_generator():
            if pwish >= sigma:
                curr_batch.append( ( i, j, pwish, plast[i, j] ) )
                k += 1
            if k == batch_size:
                fname = os.path.join(self.tmp_dir, '%d.in.npy' % n_args_batches)
                np.save(fname, curr_batch)
                k = 0
                n_args_batches += 1
                curr_batch = []
        fname = os.path.join(self.tmp_dir, '%d.in.npy' % n_args_batches)
        np.save(fname, curr_batch)
        n_args_batches += 1

        self.argument_list = range(n_args_batches)

    @staticmethod
    def task(batch_id, cfg, tmp_dir):

        dictHiC = cfg['restraints']['Hi-C']
        hss     = HssFile(cfg["optimization"]["structure_output"], 'r')

        # read params
        fname = os.path.join(tmp_dir, '%d.in.npy' % batch_id)
        params = np.load(fname)

        results = []
        for i, j, pwish, plast in params:
            res = get_actdist(
                int(i), int(j), pwish, plast, hss,
                contactRange = dictHiC.get('contact_range', 2.0)
            )

            for r in res:
                results.append(r) #(i, j, actdist, p)
            #-
        #--
        hss.close()
        fname = os.path.join(tmp_dir, '%d.out.tmp' % batch_id)
        with open(fname, 'w') as f:
            f.write('\n'.join([actdist_fmt_str % x for x in results]))

    def reduce(self):
        actdist_file = os.path.join(self.tmp_dir, "actdist.hdf5")
        last_actdist_file = self.cfg['runtime']['Hi-C'].get("actdist_file", None)
        row = []
        col = []
        dist = []
        prob = []

        for i in tqdm(self.argument_list, desc='(REDUCE)'):
            fname = os.path.join(self.tmp_dir, '%d.out.tmp' % i)
            partial_actdist = np.genfromtxt( fname, dtype=actdist_shape )
            row.append(partial_actdist['row'])
            col.append(partial_actdist['col'])
            dist.append(partial_actdist['dist'])
            prob.append(partial_actdist['prob'])

        additional_data = []
        if "Hi-C" in self.cfg['runtime']:
            additional_data .append(
                'sigma_{:.4f}'.format(
                    self.cfg['runtime']['Hi-C'].get('sigma', -1.0)
                )
            )
        if 'opt_iter' in self.cfg['runtime']:
            additional_data.append(
                'iter_{}'.format(
                    self.cfg['runtime']['opt_iter']
                )
            )

        tmp_actdist_file = actdist_file+'.tmp'

        with h5py.File(tmp_actdist_file, "w") as h5f:
            h5f.create_dataset("row", data=np.concatenate(row))
            h5f.create_dataset("col", data=np.concatenate(col))
            h5f.create_dataset("dist", data=np.concatenate(dist))
            h5f.create_dataset("prob", data=np.concatenate(prob))
        #-
        swapfile = '.'.join( [actdist_file,] + additional_data )
        if last_actdist_file is not None:
            os.rename(last_actdist_file, swapfile)
        os.rename(tmp_actdist_file, actdist_file)
        self.cfg['runtime']['Hi-C']["actdist_file"] = actdist_file

    def skip(self):
        '''
        Fix the dictionary values when already completed
        '''
        self.tmp_dir = make_absolute_path(
            self.cfg['restraints']['Hi-C'].get('actdist_dir', 'actdist'),
            self.cfg['optimization']['tmp_dir']
        )
        self.actdist_file = os.path.join(self.tmp_dir, "actdist.hdf5")
        self.cfg['runtime']['Hi-C']["actdist_file"] = self.actdist_file


#=

def newton_prob(p_wish, x_now, x_last, p_now, p_last):
    # value of the functions
    f_now = p_now - p_wish
    f_last = p_last - p_wish
    derivative = ( f_now - f_last ) / ( x_now - x_last )
    x_new = x_now - f_now / derivative
    return x_new

def cleanProbability(pij, pexist):
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
        i (int)
        j (int)
        ad (float): the activation distance
        p (float): the corrected probability
    '''

    # import here in case is executed on a remote machine
    import numpy as np

    if (i==j):
        return []

    n_struct = hss.get_nstruct()
    copy_index = hss.get_index().copy_index
    chrom = hss.get_index().chrom

    ii = copy_index[i]
    jj = copy_index[j]

    n_combinations      = len(ii) * len(jj)
    #n_possible_contacts = np.max(hss.index.copy) + 1
    n_possible_contacts = min(len(ii), len(jj))
    #for diploid cell n_combinations = 2*2 =4
    #n_possible_contacts = 2

    radii  = hss.get_radii()
    ri, rj = radii[ii[0]], radii[jj[0]]

    d_sq = np.empty((n_combinations, n_struct))

    it = 0
    for k in ii:
        for m in jj:
            x = hss.get_bead_crd(k)
            y = hss.get_bead_crd(m)
            d_sq[it] = np.sum(np.square(x - y), axis=1)
            it += 1
    #=

    rcutsq = np.square(contactRange * (ri + rj))
    d_sq.sort(axis=0)

    contact_count = np.count_nonzero(d_sq[0:n_possible_contacts, :] <= rcutsq)
    pnow        = float(contact_count) / (n_possible_contacts * n_struct)
    sortdist_sq = np.sort(d_sq[0:n_possible_contacts, :].ravel())

    t = cleanProbability(pnow, plast)
    p = cleanProbability(pwish, t)

    res = []
    if p>0:
        o = min(n_possible_contacts * n_struct - 1,
                int(round(n_possible_contacts * p * n_struct)))
        activation_distance = np.sqrt(sortdist_sq[o])

        if (chrom[i] == chrom[j]) and (option == 0):
            res = [(i0, i1, activation_distance, p) for i0,i1 in zip(ii,jj)]
        else:
            res = [(i0, i1, activation_distance, p) for i0 in ii for i1 in jj]
    return res


