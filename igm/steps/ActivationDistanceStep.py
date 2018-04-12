from __future__ import division, print_function
import numpy as np
import h5py
import scipy.io
import os
import os.path

from alabtools.analysis import HssFile

from ..core import Step

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

    def name(self):
        s = 'ActivationDistanceStep (sigma={:.2f}%, iter={:s})' 
        return s.format(
            self.cfg['restraints']['Hi-C']['sigma'] * 100.0,
            str( self.cfg['runtime'].get('opt_iter', 'N/A') )
        )

    def setup(self):
        dictHiC = self.cfg['restraints']['Hi-C']
        sigma = dictHiC["sigma"]
        input_matrix = dictHiC["input_matrix"]
        
        self.tmp_extensions = [".npy", ".tmp"]
        
        self.set_tmp_path()

        self.keep_temporary_files = ("keep_temporary_files" in dictHiC and 
                                     dictHiC["keep_temporary_files"] is True)
        
        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)
        #---
        
        probmat = scipy.io.mmread(input_matrix)
        mask    = np.logical_and( 
            probmat.data >= sigma,
            np.abs( probmat.row - probmat.col ) > 1
        )
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
            fname = os.path.join(self.tmp_dir, '%d.in.npy' % b)
            np.save(fname, params)
        
        self.argument_list = range(n_args_batches)
            
    @staticmethod
    def task(batch_id, cfg, tmp_dir):
        
        dictHiC = cfg['restraints']['Hi-C']
        hss     = HssFile(cfg["structure_output"], 'r+')
        
        # read params
        fname = os.path.join(tmp_dir, '%d.in.npy' % batch_id)
        params = np.load(fname)
        
        results = []
        for i, j, pwish, plast in params:
            res = get_actdist(int(i), int(j), pwish, plast, hss, 
                              contactRange = dictHiC['contact_range'] if 'contact_range' in dictHiC else 2.0)
            
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
        
        row = []
        col = []
        dist = []
        prob = []
        
        for i in self.argument_list:
            fname = os.path.join(self.tmp_dir, '%d.out.tmp' % i)
            partial_actdist = np.genfromtxt( fname, dtype=actdist_shape )
            row.append(partial_actdist['row'])
            col.append(partial_actdist['col'])
            dist.append(partial_actdist['dist'])
            prob.append(partial_actdist['prob'])
        
        with h5py.File(actdist_file, "w") as h5f:
            h5f.create_dataset("row", data=np.concatenate(row))
            h5f.create_dataset("col", data=np.concatenate(col))
            h5f.create_dataset("dist", data=np.concatenate(dist))
            h5f.create_dataset("prob", data=np.concatenate(prob))
        #-
        self.cfg['restraints']['Hi-C']["actdist_file"] = actdist_file

    def skip(self):
        '''
        Fix the dictionary values when already completed
        '''
        self.set_tmp_path()
        actdist_file = os.path.join(self.tmp_dir, "actdist.hdf5")
        self.cfg['restraints']['Hi-C']["actdist_file"] = actdist_file
#=  
    def set_tmp_path(self):
        dictHiC = self.cfg['restraints']['Hi-C']
        hic_tmp_dir = dictHiC["actdist_dir"] if "actdist_dir" in dictHiC else "actdist"
        
        if os.path.isabs(hic_tmp_dir):
            self.tmp_dir = hic_tmp_dir
        else:    
            self.tmp_dir = os.path.join( self.cfg["tmp_dir"], hic_tmp_dir )
            self.tmp_dir = os.path.abspath(self.tmp_dir)


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


