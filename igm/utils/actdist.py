from __future__ import division, print_function

import numpy as np

def cleanProbability(pij, pexist):
    if pexist < 1:
        pclean = (pij - pexist) / (1.0 - pexist)
    else:
        pclean = pij
    return max(0, pclean)

def get_actdist(i, j, pwish, plast, hss, contactRange=2):
    '''
    Serial function to compute the activation distances for a pair of loci 
    It expects some variables to be defined in its scope:
        
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
            
        copy_index :dictionary int -> list
            a dict specifying the indices of all the copies of each locus
    Returns
    -------
        i (int)
        j (int)
        ad (float): the activation distance
        p (float): the corrected probability
    '''
    import numpy as np
    
    n_struct = hss.get_nstruct()
    copy_index = hss.get_index().copy_index
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
        res = [(i, j, activation_distance, p) for i in ii for j in jj]
    return res
