from __future__ import division, print_function
import numpy as np
import os, os.path

from math import acos, sin, cos, pi

from ..core import StructGenStep
from ..utils import HmsFile
from alabtools.analysis import HssFile

class RandomInit(StructGenStep):

    def setup(self):
        self.tmp_file_prefix = "random"
        self.argument_list = range(self.cfg["model"]["population_size"])

    @staticmethod
    def task(struct_id, cfg, tmp_dir):
        """
        generate one random structure with territories
        """
        k = np.random.randint(0, 2**32)
        np.random.seed( (k*struct_id) % (2**32) )
        hssfilename    = cfg["optimization"]["structure_output"]
        nucleus_radius = cfg.get("model/init_radius")

        with HssFile(hssfilename,'r') as hss:
            index = hss.index

        crd = generate_territories(index, nucleus_radius)

        ofname = os.path.join(tmp_dir, 'random_%d.hms' % struct_id)
        with HmsFile(ofname, 'w') as hms:
            hms.saveCoordinates(struct_id, crd)

    def intermediate_name(self):
        return '.'.join([
            self.cfg["optimization"]["structure_output"],
            'randomInit'
        ])
    #-


def uniform_sphere(R):
    """
    Generates uniformly distributed points in a sphere

    Arguments:
        R (float): radius of the sphere
    Returns:
        np.array:
            triplet of coordinates x, y, z
    """
    phi = np.random.uniform(0, 2 * pi)
    costheta = np.random.uniform(-1, 1)
    u = np.random.uniform(0, 1)

    theta = acos( costheta )
    r = R * ( u**(1./3.) )

    x = r * sin( theta) * cos( phi )
    y = r * sin( theta) * sin( phi )
    z = r * cos( theta )

    return np.array([x,y,z])



def generate_territories(index, R=5000.0):
    '''
    Creates a single random structure with chromosome territories.
    Each "territory" is a sphere with radius 0.75 times the average
    expected radius of a chromosome.
    Arguments:
        chrom : alabtools.utils.Index
            the bead index for the system.
        R : float
            radius of the cell

    Returns:
        np.array : structure coordinates
    '''

    # chromosome ends are detected when
    # the name is changed
    n_tot = len(index)
    n_chrom = len(index.chrom_sizes)

    crds = np.empty((n_tot, 3))
    # the radius of the chromosome is set as 75% of its
    # "volumetric sphere" one. This is totally arbitrary.
    # Note: using float division of py3
    chr_radii = [0.75 * R * (float(nb)/n_tot)**(1./3) for nb in index.chrom_sizes]
    crad = np.average(chr_radii)
    k = 0
    for i in range(n_chrom):
        center = uniform_sphere(R - crad)
        for j in range(index.chrom_sizes[i]):
            crds[k] = uniform_sphere(crad) + center
            k += 1

    return crds


def generate_random_in_sphere(radii, R=5000.0):
    '''
    Returns:
        np.array : structure coordinates
    '''
    return np.array([uniform_sphere(R-r) for r in radii])
