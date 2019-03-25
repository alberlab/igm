import logging
import traceback
import numpy as np
from scipy.stats import pearsonr
from alabtools import Contactmatrix, HssFile
from alabtools.analysis import get_simulated_hic

from alabtools.plots import plot_comparison, red

from .plots import logloghist2d, density_histogram_2d
from .utils import create_folder

import matplotlib.pyplot as plt


def report_hic(hssfname, input_matrix, inter_sigma, intra_sigma, contact_range, run_label=''):
    if run_label:
        run_label = '-' + run_label
    logger = logging.getLogger("HiC")
    logger.info('Executing HiC report')

    # if all sigmas are none, we just skip, I guess
    if intra_sigma is None and inter_sigma is None:
        logger.error('HiC sigmas are not specified. Skipping the step.')
        return

    correlations = {
        'intra': {
            'restrained': [],
            'non_restrained': [],
            'all': []
        },

        'inter': {
            'restrained': 0,
            'non_restrained': 0,
            'all': 0
        },

        'all': {
            'restrained': 0,
            'non_restrained': 0,
            'all': 0
        },

    }

    try:
        cm = Contactmatrix(input_matrix)
        create_folder("matrix_comparison")
        outmap = get_simulated_hic(hssfname, float(contact_range))
        outmap.save(f"matrix_comparison/outmap{run_label}.hcs")

        with HssFile(hssfname, 'r') as hss:
            genome = hss.genome

        minsigma = None

        for c in genome.chroms:
            x1 = cm[c]
            x2 = outmap[c]
            x1d = x1.matrix.toarray()
            x2d = x2.matrix.toarray()

            correlations['intra']['all'].append(pearsonr(x1d.ravel(), x2d.ravel())[0])

            if intra_sigma:
                mask = x1d >= intra_sigma
                correlations['intra']['restrained'].append(pearsonr(x1d[mask].ravel(), x2d[mask].ravel())[0])
                correlations['intra']['non_restrained'].append(pearsonr(x1d[~mask].ravel(), x2d[~mask].ravel())[0])
                cutoff = intra_sigma
                minsigma = intra_sigma
            else:
                # using a large plotting cutoff when nothing is imposed, so that nothing will be shown
                cutoff = 2.0

            fig = plot_comparison(x1, x2, file=f'matrix_comparison/{c}{run_label}.pdf',
                                  labels=['INPUT', 'OUTPUT'], title=c, cmap=red, vmax=0.2)
            fig.savefig(f'matrix_comparison/{c}{run_label}.png')
            plt.close(fig)

            x1.matrix.data[x1.matrix.data < cutoff] = 0
            fig = plot_comparison(x1, x2, file=f'matrix_comparison/imposed_{c}{run_label}.pdf',
                                  labels=['INPUT', 'OUTPUT'], title=c, cmap=red, vmax=0.2)
            fig.savefig(f'matrix_comparison/imposed_{c}{run_label}.png')
            plt.close(fig)

        with open(f'matrix_comparison/intra_correlations{run_label}.txt', 'w') as f:
            f.write('# chrom all imposed non_imposed\n')
            for c, x, y, z in zip(genome.chroms,
                                  correlations['intra']['all'],
                                  correlations['intra']['restrained'],
                                  correlations['intra']['non_restrained']):
                f.write(f'{c:6s} {x:8.5f} {y:8.5f} {z:8.5f}\n')

        # using dense representations and masks. A LOT of memory used.
        x = cm.toarray()
        y = outmap.toarray()
        intermask = np.triu(cm.getInterMask())
        correlations['inter']['all'] = pearsonr(x[intermask].ravel(), y[intermask].ravel())[0]

        if inter_sigma:
            # get interchromsomal correlations
            correlations['inter']['restrained'] = pearsonr(x[intermask & (x >= inter_sigma)].ravel(),
                                                           y[intermask & (x >= inter_sigma)].ravel())[0]
            correlations['inter']['non_restrained'] = pearsonr(x[intermask & (x < inter_sigma)].ravel(),
                                                               y[intermask & (x < inter_sigma)].ravel())[0]

            cutoff = inter_sigma
            if minsigma:
                minsigma = min(minsigma, inter_sigma)
            else:
                minsigma = inter_sigma
        else:
            # set a large cutoff when nothing is imposed, so that nothing will be shown
            cutoff = 2.0

        # free some of the memory
        del x
        del y
        del intermask

        # write correlations
        with open(f'matrix_comparison/inter_correlations{run_label}.txt', 'w') as f:
            f.write('# all imposed non_imposed\n')
            f.write('{:8.5f} {:8.5f} {:8.5f}\n'.format(
                correlations['inter']['all'],
                correlations['inter']['restrained'],
                correlations['inter']['non_restrained']
            ))

        # create a scatter plot of probabilities:
        f, _, _, _, _ = logloghist2d(
            cm.matrix.toarray().ravel(),
            outmap.matrix.toarray().ravel(),
            bins=(100, 100),
            outfile=f'matrix_comparison/log_histogram2d{run_label}.pdf',
            nlevels=10,
            sigma=minsigma,
            xlabel='INPUT',
            ylabel='OUTPUT',
            smooth={'sigma': 1, 'truncate': 2}
        )
        f.savefig(f'matrix_comparison/log_histogram2d{run_label}.png')
        plt.close(f)

        f, _, _, _, _ = density_histogram_2d(
            cm.matrix.toarray().ravel(),
            outmap.matrix.toarray().ravel(),
            bins=(100, 100),
            outfile=f'matrix_comparison/linear_histogram2d{run_label}.pdf',
            nlevels=10,
            sigma=minsigma,
            xlabel='INPUT',
            ylabel='OUTPUT',
            smooth={'sigma': 1, 'truncate': 2}
        )
        f.savefig(f'matrix_comparison/linear_histogram2d{run_label}.png')
        plt.close(f)

        f = plot_comparison(cm, outmap, file=f'matrix_comparison/inter_chromosomal{run_label}.pdf',
                            labels=['INPUT', 'OUTPUT'], title=f'inter-chromosomal{run_label}',
                            cmap=red, vmax=0.05)
        f.savefig(f'matrix_comparison/inter_chromosomal{run_label}.png')
        plt.close(f)
        cm.matrix.data[cm.matrix.data < cutoff] = 0

        f = plot_comparison(cm, outmap, file=f'matrix_comparison/inter_chromosomal_imposed{run_label}.pdf',
                            labels=['INPUT', 'OUTPUT'], title=f'inter-chromosomal (restrained only){run_label}',
                            cmap=red, vmax=0.05)
        f.savefig(f'matrix_comparison/inter_chromosomal_imposed{run_label}.png')
        plt.close(f)

    except KeyboardInterrupt:
        logger.error('User interrupt. Exiting.')
        exit(1)

    except Exception:
        traceback.print_exc()
        logger.error('Error in HiC step\n==============================')
