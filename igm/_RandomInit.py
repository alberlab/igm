from __future__ import division, print_function
import numpy as np
from math import acos, sin, cos, pi

from .core import Step

from alabtools.analysis import HssFile

class RandomInit(Step):
    
    def setup(self):
        self.tmp_extensions.append(".npy")
        self.argument_list = list(range(self.cfg["population_size"]))
        
    @staticmethod
    def task(struct_id, cfg):
        """
        generate one random structure with territories
        """
        hssfilename    = cfg["structure_output"]
        nucleus_radius = cfg['model']['nucleus_radius']
        
        with HssFile(hssfilename,'r') as hss:
            index = hss.index
        
        crd = generate_territories(index, nucleus_radius)
        
        np.save("%s/random_%s.npy"%(cfg['optimization']['tmp_files_dir'], struct_id), crd)
    #-
            
    def reduce(self):
        """
        Collect all structure coordinates together to put hssFile
        """
        hssfilename = self.cfg["structure_output"]
        hss = HssFile(hssfilename,'a')
        
        #iterate all structure files and 
        for i in range(hss.nstruct):
            crd = np.load("%s/random_%s.npy"%(self.cfg['optimization']['tmp_files_dir'], i))
            
            hss.set_struct_crd(i, crd)
        #-
        

def uniform_sphere(R):
    '''
    Generates uniformly distributed points in a sphere
    
    Arguments:
        R (float): radius of the sphere
    Returns:
        np.array:
            triplet of coordinates x, y, z 
    '''
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
