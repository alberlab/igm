from __future__ import division, print_function

import numpy as np
from numpy.linalg import norm
from .restraint import Restraint
from ..model.forces import HarmonicUpperBound, HarmonicLowerBound
from ..model.particle import Particle

import h5py

# helper functions
def sort_radially(ii, crd):
    ii = np.array(ii)
    dists = [ norm(crd[i]) for i in ii ]
    return ii[np.argsort(dists)]

def sort_pairs_by_distance(ii, jj, crd):
    n_combinations = len(ii)*len(jj)
    dists = np.zeros(n_combinations)
    pairs = np.zeros((n_combinations, 2))
    it = 0
    for m in ii:
        for n in jj:
            x = crd[m]
            y = crd[n] 
            dists[it] = norm(x - y)
            pairs[it, :] = [m, n]
            it += 1
    return pairs[np.argsort(dists), :]


class FISH(Restraint):
    """
    Object handles Hi-C restraint
    
    Parameters
    ----------
    actdist_file : activation distance file
        
    contactRange : int
        defining contact range between 2 particles as contactRange*(r1+r2)
    """
    
    def __init__(self, 
                 fish_file,
                 index, 
                 struct_id,
                 rtype='',
                 tol=0.0, 
                 k=1.0):
        
        self.fish_file = fish_file
        self.rtype = rtype
        self.index = index
        self.struct_id = struct_id
        self.tol = tol
        self.k = k
        self.forceID = []

   
        
    def _apply(self, model):
        
        copy_index = self.index.copy_index

        hff = h5py.File(self.fish_file, 'r')
        minradial = 'r' in self.rtype
        maxradial = 'R' in self.rtype
        minpair = 'p' in self.rtype
        maxpair = 'P' in self.rtype

        struct_id = self.struct_id

        ck = self.k
        tol = self.tol
        crd = model.getCoordinates()
        
        # if we use radial restraint we want to define the center
        if minradial or maxradial:
            center = model.addParticle([0., 0., 0.], 0., Particle.DUMMY_STATIC)

        if minradial or maxradial:
            probes = hff['probes']
            targets = hff['radial_min'][:, struct_id]
            for k, i in enumerate(probes):
                
                # get all the copies of locus i
                ii = copy_index[i]  
                target_dist = targets[k]

                # find the closest to the center
                particle = sort_radially(ii, crd)[0]

                # add a lower bound on that bead
                f = HarmonicLowerBound((center, particle), 
                                       k=ck,
                                       d=max(0, target_dist - tol),
                                       note=Restraint.FISH_RADIAL)
                f = model.addForce(f)
                self.forceID.append(f)

                # add a upper bound on that bead
                f = HarmonicUpperBound((center, particle), 
                                       k=ck,
                                       d=target_dist + tol,
                                       note=Restraint.FISH_RADIAL)
                f = model.addForce(f)
                self.forceID.append(f)

        if maxradial:
            probes = hff['probes']
            targets = hff['radial_max'][:, struct_id]
            for k, i in enumerate(probes):
                # get all the copies of locus i
                ii = copy_index[i]
                target_dist = targets[k]

                # find the futhest away from the center
                particle = sort_radially(ii, crd)[-1]

                # add a lower bound on that bead
                f = HarmonicLowerBound((center, particle), 
                                       k=ck,
                                       d=max(0, target_dist - tol),
                                       note=Restraint.FISH_RADIAL)
                f = model.addForce(f)
                self.forceID.append(f)

                # add a upper bound on that bead
                f = HarmonicUpperBound((center, particle), 
                                       k=ck,
                                       d=target_dist + tol,
                                       note=Restraint.FISH_RADIAL)
                f = model.addForce(f)
                self.forceID.append(f)

        if minpair:
            pairs = hff['pairs']
            targets = hff['pair_min'][:, struct_id]
            for k, (i, j) in enumerate(pairs):
                assert (i != j)

                target_dist = targets[k]

                # get all the copies
                ii = copy_index[i]
                jj = copy_index[j]

                # sort all the possible pairs by distance
                sorted_pairs = sort_pairs_by_distance(ii, jj, crd)
                
                # restraint all the pairs not to be too close

                for m, n in sorted_pairs:    
                    f = HarmonicLowerBound((m, n), 
                                           k=ck,
                                           d=min(0, target_dist - tol),
                                           note=Restraint.FISH_PAIR)
                    f = model.addForce(f)
                    self.forceID.append(f)
            

                # find the closest pair and keep it from getting
                # too far apart

                m, n = sorted_pairs[0]
                f = HarmonicUpperBound((m, n), 
                                       k=ck,
                                       d=target_dist + tol,
                                       note=Restraint.FISH_PAIR)
                f = model.addForce(f)
                self.forceID.append(f)
                
        if maxpair:
            pairs = hff['pairs']
            targets = hff['pair_max'][:, struct_id]
            for k, (i, j) in enumerate(pairs):
                
                assert (i != j)
                target_dist = targets[k]

                # get all the copies
                ii = copy_index[i]
                jj = copy_index[j]

                # sort all the possible pairs by distance
                sorted_pairs = sort_pairs_by_distance(ii, jj, crd)
                
                # restraint all the pairs not to be too far
                for m, n in sorted_pairs:    
                    f = HarmonicUpperBound((m, n), 
                                           k=ck,
                                           d=target_dist + tol,
                                           note=Restraint.FISH_PAIR)
                    f = model.addForce(f)
                    self.forceID.append(f)
            

                # find the furthest pair and keep it from getting
                # too close

                m, n = sorted_pairs[0]
                f = HarmonicLowerBound((m, n), 
                                       k=ck,
                                       d=min(0, target_dist - tol),
                                       note=Restraint.FISH_PAIR)
                f = model.addForce(f)
                self.forceID.append(f)

        hff.close()
    
    
#==
