import numpy as np
import matplotlib.pyplot as plt
import logging
import traceback
from alabtools import HssFile
from .utils import create_folder


def rg(points):
    '''
    Get the radius of gyration for a set of points
    :param points: np.ndarray
        set of points (n_points x 3)
    :return: float
        Rg(points)
    '''
    ave = np.average(points, axis=0)
    v = points - ave
    return np.sqrt(np.sum(np.square(v)) / len(v))


def get_chroms_rgs(crds, index):
    '''
    Get the average radius of gyration for each chromosome chain in the
    index. Returns a list of size n_struct*n_copies for each chromosome.
    :param crds: np.ndarray
        coordinates in bead-major format
    :param index: alabtools.Index
        index of genomic locations
    :return: list[np.ndarray]
    '''
    rgs = []
    for chrom in index.get_chromosomes():
        copies = index.get_chrom_copies(chrom)
        data = list()
        for copy in copies:
            ii = index.get_chrom_pos(chrom, copy)
            for crd in crds[ii, :].swapaxes(0, 1):
                data.append(rg(crd))
        rgs.append(np.array(data))
    return rgs


def set_box_colors(bp, clr):
    if not isinstance(clr, (list, tuple, np.ndarray)):
        clr = [clr] * len(bp['boxes'])
    for i in range(len(clr)):
        plt.setp(bp['boxes'][i], facecolor=clr[i])
        plt.setp(bp['medians'][i], color='black')


def boxplots_group(data, group_labels, n_per_row=6, subplot_width=10,
                   subplot_height=2.5, vmin=800, vmax=3500, outfile=None,
                   title='', color='#fb7b04'):
    '''
    Splits a large number of boxex across multiple rows
    '''
    n_groups = len(group_labels)
    n_rows = n_groups // n_per_row if n_groups % n_per_row == 0 else n_groups // n_per_row + 1
    f, plots = plt.subplots(n_rows, 1, figsize=(subplot_width, subplot_height * n_rows), sharey=True)
    f.suptitle(title)
    for ip, i in enumerate(range(0, n_groups, n_per_row)):

        # select data subset
        boxdata = data[i:i + n_per_row]
        plots[ip].set_ylim(vmin, vmax)
        bp = plots[ip].boxplot(boxdata, labels=group_labels[i:i + n_per_row], patch_artist=True, showfliers=False)
        set_box_colors(bp, color)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    if outfile is not None:
        plt.savefig(outfile)
    return f, plots


def report_radius_of_gyration(hssfname, run_label=''):

    if run_label:
        run_label = '-' + run_label

    logger = logging.getLogger('GyrRadius')
    try:

        logger.info('Executing Radius of Gyration report...')
        create_folder("radius_of_gyration")
        with HssFile(hssfname, 'r') as hss:
            chroms = hss.genome.chroms
            rgs = get_chroms_rgs(hss.coordinates, hss.index)
            np.savez(f'radius_of_gyration/chromosomes{run_label}.npz',
                     **{c: arr for c, arr in zip(hss.genome.chroms, rgs)})
        fig, _ = boxplots_group(rgs, chroms,
                                title=f'Chromosomes Radii of Gyration {run_label}',
                                outfile=f'radius_of_gyration/rgs{run_label}.pdf')
        fig.savefig(f'radius_of_gyration/rgs{run_label}.png')
        plt.close(fig)
        logger.info('Done.')

    except KeyboardInterrupt:
        logger.error('User interrupt. Exiting.')
        exit(1)

    except Exception:
        traceback.print_exc()
        logger.error('Error in radius of gyration step\n==============================')

