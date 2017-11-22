from __future__ import division, print_function
import numpy
import numpy.random
import time
from math import acos, sin, cos, pi

from .core import Step

class RandomInit(Step):
    
    @staticmethod
    def task(struct_id, cfg):
        """
        generate one random structure with territories
        """
        index = cfg['runtime']['index']
        R = cfg['model']['nucleus_radius']
        crd = generate_territories(index, R)
        
        numpy.save("%s/current_%s.npy"%(cfg['optimization']['tmp_files_dir'], struct_id), crd)
    #-
            
    def cleanup(self):
        """
        Collect all structure coordinates together to put hssFile
        """
        
        

def uniform_sphere(R):
    '''
    Generates uniformly distributed points in a sphere
    
    Arguments:
        R (float): radius of the sphere
    Returns:
        numpy.array:
            triplet of coordinates x, y, z 
    '''
    phi = numpy.random.uniform(0, 2 * pi)
    costheta = numpy.random.uniform(-1, 1)
    u = numpy.random.uniform(0, 1)

    theta = acos( costheta )
    r = R * ( u**(1./3.) )

    x = r * sin( theta) * cos( phi )
    y = r * sin( theta) * sin( phi )
    z = r * cos( theta )

    return numpy.array([x,y,z])



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
        numpy.array : structure coordinates
    '''
    
    # chromosome ends are detected when
    # the name is changed
    n_tot = len(index)
    n_chrom = len(index.chrom_sizes)
    
    crds = numpy.empty((n_tot, 3))
    # the radius of the chromosome is set as 75% of its
    # "volumetric sphere" one. This is totally arbitrary. 
    # Note: using float division of py3
    chr_radii = [0.75 * R * (float(nb)/n_tot)**(1./3) for nb in index.chrom_sizes]
    crad = numpy.average(chr_radii)
    k = 0
    for i in range(n_chrom):    
        center = uniform_sphere(R - crad)
        for j in range(index.chrom_sizes[i]):
            crds[k] = uniform_sphere(crad) + center
            k += 1

    return crds
