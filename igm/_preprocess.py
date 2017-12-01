from __future__ import division, print_function

from alabtools.utils import Genome, get_index_from_bed, make_diploid
from alabtools.analysis import HssFile
import numpy as np
import os

#===prepare genome and index instances
def PrepareGenomeIndex(cfg):
    genome = Genome(cfg['genome']['genome'])
    index = get_index_from_bed(cfg['genome']['segmentation'], genome, usecols=(0,1,2,3))
    
    if cfg['genome']['ploidy'] == 'diploid':
        index = make_diploid(index)
    
    return genome, index
                                   

def Preprocess(cfg):
    
    #Generate genome, index objects
    genome, index = PrepareGenomeIndex(cfg)
    
    nstruct = cfg['population_size']
    nbead = len(index)
    
    hss = HssFile(cfg['structure_output'], 'a')
    
    
    #Generate model radius
    occupancy = cfg['model']['occupancy']
    nucleus_radius = cfg['model']['nucleus_radius']
    
    rho = occupancy * nucleus_radius**3 / (sum(index.end - index.start))
    radii = np.array([(rho * (idx['end'] - idx['start'])) ** (1.0/3.0) for idx in index])
    
    #put everything into hssFile
    hss.set_nbead(nbead)
    hss.set_nstruct(nstruct)
    hss.set_genome(genome)
    hss.set_index(index)
    hss.set_radii(radii)
    hss.set_coordinates(np.zeros((nbead,nstruct,3)))
    hss.close()
    
    #prepare tmp file dir
    if not os.path.exists(cfg['tmp_dir']):
        os.makedirs(cfg['tmp_dir'])
    
    
    
    
    
    
