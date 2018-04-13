from __future__ import division, print_function

from alabtools.utils import Genome, get_index_from_bed, make_diploid, make_multiploid
from alabtools.analysis import HssFile
from six import string_types
import numpy as np
import os
from shutil import copyfile

#===prepare genome and index instances
def PrepareGenomeIndex(cfg):

    gcfg = cfg['genome']
    if 'usechr' not in gcfg:
        gcfg['usechr'] = ['#', 'X', 'Y']

    genome = Genome(gcfg['genome'], usechr=gcfg['usechr'])
    
    if isinstance(gcfg['segmentation'], string_types):
        index = get_index_from_bed(gcfg['segmentation'], genome, 
                                    usecols=(0,1,2,3))
    else:
        index = genome.bininfo(gcfg['segmentation'])
    
    if gcfg['ploidy'] == 'male': 
        gcfg['ploidy'] = {
            '#': 2,
            'X': 1,
            'Y': 1
        }

    if gcfg['ploidy'] == 'diploid':
        index = make_diploid(index)
    elif gcfg['ploidy'] == 'haploid':
        pass
    elif isinstance(gcfg['ploidy'], dict):
        chrom_ids = []
        chrom_mult = []
        for c in sorted(gcfg['ploidy'].keys()):
            if c == '#':
                autosomes = [ i for i, x in enumerate(genome.chroms) 
                              if x[-1].isdigit() ]
                chrom_ids += autosomes
                chrom_mult += [ gcfg['ploidy'][c] ] * len(autosomes)
            else:
                cn = genome.chroms.tolist().index('chr%s' % c)
                chrom_ids += [ cn ]
                chrom_mult += [ gcfg['ploidy'][c] ]         
        index = make_multiploid(index, chrom_ids, chrom_mult)
    
    return genome, index


def Preprocess(cfg):
    
    #Generate genome, index objects
    genome, index = PrepareGenomeIndex(cfg)
    
    nstruct = cfg['population_size']
    nbead = len(index)
    
    occupancy = cfg['model']['occupancy']
    nucleus_radius = cfg['model']['nucleus_radius']
    
    rho = occupancy * nucleus_radius**3 / (sum(index.end - index.start))
    radii = np.array([(rho * (idx['end'] - idx['start'])) ** (1.0/3.0) for idx in index])
    
    if not os.path.isfile(cfg['structure_output']):
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

    # now create a temporary file for runtime use
    if not os.path.isfile(cfg['structure_output'] + '.tmp'):
        copyfile( cfg['structure_output'], cfg['structure_output'] + '.tmp' )
    
    #prepare tmp file dir
    if not os.path.exists(cfg['tmp_dir']):
        os.makedirs(cfg['tmp_dir'])
    
    
    
    
    
    
