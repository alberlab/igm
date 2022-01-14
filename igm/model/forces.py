from __future__ import division, absolute_import, print_function
import numpy as np

# Define "Force" class, and then all the force instances


class Force(object):
    """
    Define Basic Force type
    """

    EXCLUDED_VOLUME = 0
    HARMONIC_UPPER_BOUND = 1
    HARMONIC_LOWER_BOUND = 2
    ENVELOPE = 3
    GENERAL_ENVELOPE = 4
    NUCL_EXCLUDED_VOLUME = 5

    FTYPES = ["EXCLUDED_VOLUME","HARMONIC_UPPER_BOUND","HARMONIC_LOWER_BOUND", "ENVELOPE", "GENERAL_ENVELOPE", "NUCL_EXCLUDED_VOLUME"]

    def __init__(self, ftype, particles, para, note=""):
        self.ftype = ftype
        self.particles = particles
        self.parameters = para
        self.note = note
        self.rnum = 1 # rnum is used in case of "collective" forces

    def __str__(self):
        return "FORCE: {} {}".format(Force.FTYPES[self.ftype],
                                        self.note)

    def __repr__(self):
        return self.__str__()

    def getScore(self, particles):
        return 0

    def getViolationRatio(self, particles):
        return 0

class ExcludedVolume(Force):

    """
    Exluded Volume Restraint, for a pair of particles check if they overlap (violation) or not

    e = ri + rj - d_ij if ri + rj - d_ij >0, otherwise 0

    Parameters
    ----------
    particles : tuple(int, int)
        Two particle indexes
    note : str
        additional information
    """

    ftype = Force.EXCLUDED_VOLUME

    def __init__(self, particles, k=1.0, note=""):
        self.particles = particles
        self.k = k
        self.note = note
        self.rnum = len(particles) * len(particles)

    def __str__(self):
        return "FORCE: {} (NATOMS: {}) {}".format(Force.FTYPES[self.ftype],
                                                  len(self.particles),
                                                  self.note)

    def getScore(self, particles):
        return self.getScores(particles).sum()

    def getScores(self, particles):

        # scipy.spatial.distance takes an array X (m, n); m = observations, n = space dimensionality
        from scipy.spatial import distance

        crd = np.array([particles[i].pos for i in self.particles])
        rad = np.array([[particles[i].r for i in self.particles]]).T

        dist = distance.pdist(crd)

        # distance is computed by plain sum
        cap = distance.pdist(rad, lambda u, v: u + v)

        # if (r_i + r_j) - d_ij < 0, then no penalty, so clip value to 0, otherwise, keep number
        s = (cap - dist).clip(min=0)

        return s.ravel()

#-

class HarmonicUpperBound(Force):
    """
    Harmonic upper bound force

    e = 1/2*k*(x-d)^2 if x > d; otherwise 0

    Parameters
    ----------
    particles : tuple(int, int)
        Two particle indexes
    d : float
        mean distance
    k : float
        spring constant
    note : str
        additional information
    """

    ftype = Force.HARMONIC_UPPER_BOUND

    def __init__(self, particles, d=0.0, k=1.0, note=""):
        if len(particles) != 2:
            raise ValueError("Two particles required")
        else:
            self.i, self.j = particles

        self.d = d
        self.k = k
        self.note = note
        self.rnum = 1

    def __str__(self):
        return "FORCE: {} {} {} {}".format(Force.FTYPES[self.ftype],
                                        self.i, self.j,
                                        self.note)

    def getScore(self, particles):

        dist = particles[self.i] - particles[self.j]

        return 0 if dist <= self.d else self.k*(dist - self.d)

    def getViolationRatio(self, particles):

        return 0 if self.d == 0 else self.getScore(particles) / (self.k * self.d)

#-

class HarmonicLowerBound(Force):
    """
    Harmonic lower bound force

    e = 1/2*k*(x-d)^2 if x < d; otherwise 0

    Parameters
    ----------
    particles : tuple(int, int)
        Two particle indexes
    d : float
        mean distance
    k : float
        spring constant
    note : str
        additional information
    """
    ftype = Force.HARMONIC_LOWER_BOUND

    def __init__(self, particles, d=0.0, k=1.0, note=""):
        if len(particles) != 2:
            raise ValueError("Two particles required")
        else:
            self.i, self.j = particles


        self.d = d
        self.k = k
        self.note = note
        self.rnum = 1

    def __str__(self):
        return "FORCE: {} {} {} {}".format(Force.FTYPES[self.ftype],
                                        self.i, self.j,
                                        self.note)

    def getScore(self, particles):

        dist = particles[self.i] - particles[self.j]

        return 0 if dist >= self.d else self.k*(self.d - dist)

    def getViolationRatio(self, particles):

        return 0 if self.d == 0 else self.getScore(particles) / (self.k * self.d)
#-

class EllipticEnvelope(Force):

    ftype = Force.ENVELOPE

    def __init__(self, particle_ids,
                 center=(0, 0, 0),
                 semiaxes=(5000.0, 5000.0, 5000.0),
                 k=1.0, note="", scale=100.0):

        self.shape = 'ellipsoid'
        self.center = np.array(center)
        self.semiaxes = np.array(semiaxes)
        self.particle_ids = particle_ids
        self.k = k
        self.scale = scale  # pff. This is to actually give a
                            # "relative  measure" for violation ratios.
        self.note = note
        self.rnum = len(particle_ids)

    def getScore(self, particles):

        E = 0
        for i in self.particle_ids:
            p = particles[i]
            s2 = np.square(self.semiaxes - p.r)
            x = p.pos
            x2 = x**2
            k2 = np.sum(x2 / s2)
            if k2 > 1:
                t = ( 1.0 - 1.0/np.sqrt(k2) )*np.linalg.norm(x)
                E += 0.5 * (t**2) * self.k
        return E

    def getScores(self, particles):

        scores = np.zeros(len(self.particle_ids))
        for k, i in enumerate(self.particle_ids):
            p = particles[i]
            s2 = np.square(self.semiaxes - p.r)
            x = p.pos
            x2 = x**2
            k2 = np.sqrt(np.sum(x2 / s2))

            # note that those scores are somewhat approximate
            if k2 > 1 and self.k > 0:
                t = ( 1.0 - 1.0/np.sqrt(k2) )*np.linalg.norm(x)/self.scale

            elif k2 < 1 and self.k < 0:
                t = ( 1.0 - np.sqrt(k2))

            else:
                t = 0

            scores[k] = max(0, t * self.k)

        return scores

    def getViolationRatio(self, particles):
        ave_t = np.sqrt(2 * self.getScore(particles) / self.k)
        ave_ax = np.sqrt(np.sum(np.square(self.semiaxes)))
        return ave_t/ave_ax

    def getViolationRatios(self, particles):
        return self.getScores(particles) / (self.k * self.scale)


class ExpEnvelope(Force):

    """
    Envelope/Nuclear body restraint from experimental map
    e = ||x - r||/R_eff - 1 if particle outside of map, 0 otherwise

    Parameters
    ---------
    particles : tuple(int, int, ...)
        N particle indexes
    volume_file: string
        filename, contains all the information about the imaging map (voxels, grid spacings, occupancy)
    k: float
        force scaling amplitude
    note : str
        additional information
    scale: float (DEPRECATED)
    """

    ftype = Force.GENERAL_ENVELOPE

    def __init__(self, particle_ids,
                 volume_file,
                 k=1.0, note="", scale=100.0):

        self.shape = 'exp_map'
        self.volume_file = volume_file
        self.particle_ids = particle_ids
        self.k = k
        self.scale = scale  # pff. This is to actually give a
                            # "relative  measure" for violation ratios.
        self.note = note
        self.rnum = len(particle_ids)


    def getScores(self, particles):

        scores = np.zeros(len(self.particle_ids))

        # load file with volumetric information and parameters
        f = open(self.volume_file)

        # read in nucleus/nuclear body switch
        body_idx = [int(x) for x in next(f).split()][0]

    	# compute number of voxels per size
        nvoxel = np.array([int(x) for x in next(f).split()])

        # "geometric center of the grid"
        center = np.array([float(x) for x in next(f).split()])
 
        # float information about grid features (origin and grid)
        origin = np.array([float(x) for x in next(f).split()])
        grid   = np.array([float(x) for x in next(f).split()])  
    
        matrice = np.zeros((nvoxel[0], nvoxel[1], nvoxel[2]))
    
        for i in range(nvoxel[0] * nvoxel[1] * nvoxel[2]):

            # read quadruplet, (i,j,k) and the binary value entry
            a, b, c, q = [int(x) for x in next(f).split()]
        
            # cast that into matrix
            matrice[a,b,c] = q
       
        # at the end of loop , check if number of remaining lines is consistent with number of map voxels
        if (i != (nvoxel[0] * nvoxel[1] * nvoxel[2] - 1)):
                print(nvoxel[0] * nvoxel[1] * nvoxel[2])
                print("ACHTUNG!")
                stop	

        # discriminate between nucleolus and nucleus
        if body_idx == False:

          # compute effective map radius as geometric mean of the axes
          R_eff = np.abs((origin[0] * origin[1] * origin[2])) ** (1./3)

          for k, i in enumerate(self.particle_ids):

              idx = np.zeros(3)
              id_int = np.zeros(3).astype('int')

              p = particles[i]

              # find indexes
              idx = (p.pos - origin)/grid
	    
              # are indexes outside of the three d volume spanned by the map box? If yes, set index to -1
              if (idx[0] < 0) or (idx[0] >= nvoxel[0]):
               	id_int[0] = -1.0
                #print("I mean 0")
              else:
                id_int[0] = int(idx[0])

              if (idx[1] < 0) or (idx[1] >= nvoxel[1]):
                id_int[1] = -1.0
                #print("I mean 1")
              else:
                id_int[1] = int(idx[1])

              if (idx[2] < 0) or (idx[2] >= nvoxel[2]):
                id_int[2] = -1.0
                #print("I mean 2")
              else:
                id_int[2] = int(idx[2])

              if ((id_int[0] < 0) or (id_int[1] < 0) or (id_int[2] < 0) or (matrice[id_int[0], id_int[1], id_int[2]] == 1)):
                
                scores[k] = np.abs((np.linalg.norm(p.pos - center))/R_eff - 1.0)   # the closest to the envelope

        if body_idx == True:

          for k, i in enumerate(self.particle_ids):

              idx = np.zeros(3)
              id_int = np.zeros(3).astype('int')

              p = particles[i]

              # find indexes
              idx = (p.pos - origin)/grid

              # are indexes outside of the three d volume spanned by the map box? If yes, set index to -1
              if (idx[0] < 0) or (idx[0] >= nvoxel[0]):
                id_int[0] = -1.0
                #print("I mean 0")
              else:
                id_int[0] = int(idx[0])

              if (idx[1] < 0) or (idx[1] >= nvoxel[1]):
                id_int[1] = -1.0
                #print("I mean 1")
              else:
                id_int[1] = int(idx[1])

              if (idx[2] < 0) or (idx[2] >= nvoxel[2]):
                id_int[2] = -1.0
                #print("I mean 2")
              else:
                id_int[2] = int(idx[2])

              if ((id_int[0] >= 0) and (id_int[1] >= 0) and (id_int[2] >= 0) and (matrice[id_int[0], id_int[1], id_int[2]] == 1)):

                scores[k] = np.linalg.norm(p.pos - center)  # the closest to the envelope

        return scores

    def getViolationRatios(self, particles):
        return self.getScores(particles) / (self.k * self.scale)
#---------

class NuclExcludedVolume(Force):

    """ Define penalty term for nucleolus excluded volume. If compenetrazione, return a positive value, 
        if no violations, return 0, easy """

    ftype = Force.NUCL_EXCLUDED_VOLUME

    def __init__(self, particles, body_pos, body_r, k=1.0, note=""):
    
        self.particles  = particles
        self.body_pos   = np.array([body_pos])     # coordinates of nucleolus center (has to be a (3,1) array)
        self.body_r     = body_r                   # radius of spherical nucleulus
        self.k          = k
        self.note       = note

    def __str__(self):
        return "FORCE: {} (NATOMS: {}) {}".format(Force.FTYPES[self.ftype],
                                                  len(self.particles),
                                                  self.note)

    def getScore(self, particles):
        return self.getScores(particles).sum()

    def getScores(self, particles):

        """ Define penalty term for nucleolus excluded volume. If nucleolus - bead compenetration, return a 
            positive penalty value equalling (r_n + r_i - d(n,i)); otherwise, return 0"""

        # scipy.spatial.distance takes an array X (m, n); m = observations, n = space dimensionality
        from scipy.spatial import distance

        crd = np.array([particles[i].pos for i in self.particles])
        dist = distance.cdist(crd, self.body_pos)   # distance between all particle centers and nucleulus center
                                               # it is a (n,1) array, n = number of particles
        rad = np.array([[particles[i].r for i in self.particles]]).T
        cap = rad + self.body_r     # sum of radii

        # if (r_i + r_j) - d_ij < 0, then no penalty, so clip value to 0, otherwise, keep number
        s = (cap - dist).clip(min=0)

        # get rid of extra dimensions, turn this into a (n) array
        return s.ravel()

#-

