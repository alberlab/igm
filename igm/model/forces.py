from __future__ import division, absolute_import, print_function
import numpy as np

class Force(object):
    """
    Define Basic Force type
    """

    EXCLUDED_VOLUME = 0
    HARMONIC_UPPER_BOUND = 1
    HARMONIC_LOWER_BOUND = 2
    ENVELOPE = 3

    FTYPES = ["EXCLUDED_VOLUME","HARMONIC_UPPER_BOUND","HARMONIC_LOWER_BOUND"]

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
        from scipy.spatial import distance

        crd = np.array([particles[i].pos for i in self.particles])
        rad = np.array([[particles[i].r for i in self.particles]]).T

        dist = distance.pdist(crd)
        cap = distance.pdist(rad, lambda u, v: u + v)

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

        return self.getScore(particles) / (self.k * self.d)
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

        return self.getScore(particles) / (self.k * self.d)
#-

class EllipticEnvelope(Force):

    ftype = Force.ENVELOPE

    def __init__(self, particle_ids,
                 center=(0, 0, 0),
                 semiaxes=(5000.0, 5000.0, 5000.0),
                 k=1.0, note=""):

        self.shape = 'ellipsoid'
        self.center = np.array(center)
        self.semiaxes = np.array(semiaxes)
        self.particle_ids = particle_ids
        self.k = k
        self.note = note
        self.rnum = len(particle_ids)

    def getScore(self, particles):

        E = 0
        for i in self.particle_ids:
            p = particles[i]
            if self.k > 0:
                s2 = np.square(self.semiaxes - p.r)
            else:
                s2 = np.square(self.semiaxes + p.r)
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
            if self.k > 0:
                s2 = np.square(self.semiaxes - p.r)
            else:
                s2 = np.square(self.semiaxes + p.r)
            x = p.pos
            x2 = x**2
            k2 = np.sqrt(np.sum(x2 / s2))

            # note that those scores are somewhat approximate
            if k2 > 1 and self.k > 0:
                t = ( 1.0 - 1.0/np.sqrt(k2) )*np.linalg.norm(x)
            elif k2 < 1 and self.k < 0:
                t = ( 1.0 - 1.0/np.sqrt(k2) )*np.linalg.norm(x)
            else:
                t = 0

            scores[k] = max(0, t * self.k)

        return scores

    def getViolationRatio(self, particles):
        ave_t = np.sqrt(2 * self.getScore(particles) / self.k)
        ave_ax = np.sqrt(np.sum(np.square(self.semiaxes)))
        return ave_t/ave_ax

    def getViolationRatios(self, particles):
        return self.getScores(particles) / (self.k * np.sqrt(np.sum(np.square(self.semiaxes))))
