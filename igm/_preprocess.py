from __future__ import division, print_function

from alabtools.utils import Genome, get_index_from_bed, make_diploid, make_multiploid
from alabtools.analysis import HssFile
from alabtools import Contactmatrix
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
    _43pi = 4./3*np.pi

    # compute volume of the nucleus
    if cfg['model']['nucleus_shape'] == 'sphere':
        nucleus_radius = cfg['model']['nucleus_radius']
        nucleus_volume = _43pi * (nucleus_radius**3)
    elif cfg['model']['nucleus_shape'] == 'ellipsoid':
        sx = cfg['model']['nucleus_semiaxes']
        nucleus_volume = _43pi * sx[0] * sx[1] * sx[2]
    else:
        raise NotImplementedError(
            "Cannot compute volume for shape %s" % cfg['model']['nucleus_shape']
        )

    # compute model radius
    occupancy = cfg['model']['occupancy']

    # compute volume per basepair
    rho = occupancy * nucleus_volume / (sum(index.end - index.start))
    bp_sizes = index.end - index.start
    sphere_volumes = [rho * s for s in bp_sizes]
    radii = ( np.array(sphere_volumes) / _43pi )**(1./3)

    # prepare Hss
    if not os.path.isfile(cfg['structure_output']):
        hss = HssFile(cfg['structure_output'], 'a')

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

    # prepare tmp file dir
    if not os.path.exists(cfg['tmp_dir']):
        os.makedirs(cfg['tmp_dir'])

    # if we have a Hi-C probability matrix, use it to determine the consecutive
    # beads distances
    pbs = cfg.get('polymer_bonds_style', 'simple')
    if pbs == 'hic':
        if "Hi-C" not in cfg['restraints']:
            raise RuntimeError('Hi-C restraints specifications are missing in the cfg, but "polymer_bond_style" is set to "hic"')
        # read the HiC matrix and get the first diagonal.
        m = Contactmatrix(cfg['restraints']['Hi-C']['data']).matrix
        cps = np.zeros(len(index) - 1)
        for i in range(m.shape[0] - 1):
            f = m[i][i+1]
            for j in index.copy_index[i]:
                cps[j] = f
        cpfname = os.path.join(cfg['tmp_dir'], 'consecutive_contacts.npy')
        np.save(cpfname, cps)
        cfg['runtime']['consecutive_contact_probabilities'] = cpfname







