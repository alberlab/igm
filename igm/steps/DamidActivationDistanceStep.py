from __future__ import division, print_function
import numpy as np
import h5py
import os
import os.path

from alabtools.analysis import HssFile

from ..core import Step

try:
    # python 2 izip
    from itertools import izip as zip
except ImportError: 
    pass


damid_actdist_shape = [
    ('index', 'int32'), 
    ('dist', 'float32'), 
    ('prob', 'float32')
]
damid_actdist_fmt_str = "%6d %6d %10.2f %.5f"


class DamidActivationDistanceStep(Step):

    def name(self):
        s = 'DamidActivationDistanceStep (sigma={:.2f}%, iter={:s})' 
        return s.format(
            self.cfg['restraints']['DAM-ID']['sigma'] * 100.0,
            str( self.cfg['runtime'].get('opt_iter', 'N/A') )
        )


    def setup(self):
        curr_cfg = self.cfg['restraints']['DAM-ID']
        sigma = curr_cfg["sigma"]
        input_profile = curr_cfg["input_profile"]
        
        self.tmp_extensions = [".npy", ".tmp"]
        
        self.set_tmp_path()

        self.keep_temporary_files = ("keep_temporary_files" in curr_cfg and 
                                     curr_cfg["keep_temporary_files"] is True)
        
        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)
        #---
        
        profile = np.readtxt(input_profile, dtype='float32')

        mask    = profile >= sigma,
        ii      = np.where(mask)[0]
        pwish   = profile[mask]
        
        if "damid_actdist_file" in curr_cfg:
            with h5py.File(curr_cfg["damid_actdist_file"]) as h5f:
                last_prob = {i : p for i, p in zip(h5f["index"], h5f["prob"])}
        else:
            last_prob = {}
        
        batch_size = curr_cfg.get('batch_size', 100)
        n_args_batches = len(ii) // batch_size
        if len(ii) % batch_size != 0:
            n_args_batches += 1

        for b in range(n_args_batches):
            start = b * batch_size
            end = min((b+1) * batch_size, len(ii))
            params = np.array( 
                [ 
                    ( ii[k], pwish[k], last_prob.get(ii[k], 0.) ) 
                    for k in range(start, end)
                ], 
                dtype=np.float32
            )
            fname = os.path.join(self.tmp_dir, '%d.damid.in.npy' % b)
            np.save(fname, params)
        
        self.argument_list = range(n_args_batches)
            
    @staticmethod
    def task(batch_id, cfg, tmp_dir):
        
        curr_cfg = cfg['restraints']['DAM-ID']
        hss     = HssFile(cfg["parameters"]["structure_output"], 'r')
        
        # read params
        fname = os.path.join(tmp_dir, '%d.damid.in.npy' % batch_id)
        params = np.load(fname)
        
        results = []
        for i, pwish, plast in params:
            res = get_damid_actdist(
                int(i), pwish, plast, hss, 
                contactRange=curr_cfg.get('contact_range', 2.0) 
            )
            results.append(res) #(i, damid_actdist, p)
            #-
        #--
        hss.close()
        fname = os.path.join(tmp_dir, '%d.out.tmp' % batch_id)
        with open(fname, 'w') as f:
            f.write('\n'.join([damid_actdist_fmt_str % x for x in results]))
        

    def reduce(self):
        damid_actdist_file = os.path.join(self.tmp_dir, "damid_actdist.hdf5")
        
        index = []
        dist = []
        prob = []
        
        for i in self.argument_list:
            fname = os.path.join(self.tmp_dir, '%d.out.tmp' % i)
            partial_damid_actdist = np.genfromtxt( fname, dtype=damid_actdist_shape )
            index.append(partial_damid_actdist['index'])
            dist.append(partial_damid_actdist['dist'])
            prob.append(partial_damid_actdist['prob'])
        
        with h5py.File(damid_actdist_file + '.tmp', "w") as h5f:
            h5f.create_dataset("index", data=np.concatenate(index))
            h5f.create_dataset("dist", data=np.concatenate(dist))
            h5f.create_dataset("prob", data=np.concatenate(prob))
        
        os.rename(damid_actdist_file + '.tmp', damid_actdist_file)
        
        self.cfg['restraints']['DAM-ID']["damid_actdist_file"] = damid_actdist_file

    def skip(self):
        '''
        Fix the dictionary values when already completed
        '''
        self.set_tmp_path()
        damid_actdist_file = os.path.join(self.tmp_dir, "damid_actdist.hdf5")
        self.cfg['restraints']['DAM-ID']["damid_actdist_file"] = damid_actdist_file
#=  
    def set_tmp_path(self):
        curr_cfg = self.cfg['restraints']['DAM-ID']
        hic_tmp_dir = curr_cfg.get('damid_actdist_dir', 'damid_actdist')
        
        if os.path.isabs(hic_tmp_dir):
            self.tmp_dir = hic_tmp_dir
        else:    
            self.tmp_dir = os.path.join( self.cfg['parameters']['tmp_dir'], hic_tmp_dir )
            self.tmp_dir = os.path.abspath(self.tmp_dir)


def cleanProbability(pij, pexist):
    if pexist < 1:
        pclean = (pij - pexist) / (1.0 - pexist)
    else:
        pclean = pij
    return max(0, pclean)

def get_damid_actdist(i, pwish, plast, hss, contactRange=2):
    '''
    Serial function to compute the damid activation distance for a locus.
        
    Parameters
    ----------
        i : int
            index of the first locus
        pwish : float
            target contact probability
        plast : float
            the last refined probability
        hss : alabtools.analysis.HssFile 
            file containing coordinates
        contactRange : int
            contact range of sum of radius of beads
    Returns
    -------
        i (int): the locus index
        ad (float): the activation distance
        p (float): the corrected probability
    '''

    # import here in case is executed on a remote machine
    import numpy as np
    
    n_struct = hss.get_nstruct()
    copy_index = hss.get_index().copy_index
              
    ii = copy_index[i]
    n_copies = len(ii)
    
    r = hss.get_radii()[ ii[0] ]
    
    d_sq = np.empty(n_copies*n_struct)  
    
    for i in range(n_copies):
        x = hss.get_bead_crd( ii[ i ] )
        d_sq[ i*n_struct: (i+1)*n_struct ] = np.sum(np.square(x), axis=1)
    #=
    
    rcutsq = np.square( contactRange * r )
    d_sq.sort()

    contact_count = np.count_nonzero(d_sq <= rcutsq)
    pnow        = float(contact_count) / (n_copies * n_struct)
    sortdist_sq = np.sort(d_sq)

    t = cleanProbability(pnow, plast)
    p = cleanProbability(pwish, t)

    if p>0:
        o = min(n_copies * n_struct - 1, 
                int( round(n_copies * n_struct * p ) ) )
        activation_distance = np.sqrt(sortdist_sq[o])
        
    return (i, activation_distance, p)


