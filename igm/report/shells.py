import numpy as np
import matplotlib.pyplot as plt
import logging
import traceback
from alabtools import HssFile
from .utils import create_folder


def report_shells(hssfname, semiaxes=None, nshell=5, hvmax=1.5, hnbins=150, run_label=''):
    if run_label:
        run_label = '-' + run_label
    logger = logging.getLogger('Shells')

    try:
        logger.info('Executiong Shells report')
        create_folder("shells")
        with HssFile(hssfname, 'r') as hss:
            crd = np.swapaxes(hss.coordinates, 0, 1)
            if semiaxes is None:
                # see if we have information about semiaxes in the file
                try:
                    semiaxes = hss['envelope']['params'][()]
                    if len(semiaxes.shape) == 0:  # is scalar
                        semiaxes = np.array([semiaxes, semiaxes, semiaxes])
                except KeyError:
                    semiaxes = np.array([5000., 5000., 5000.])

            n = hss.nbead
            kth = [int(k * n / nshell) for k in range(0, nshell)]
            bds = kth + [n]
            ave_shell_rad = np.empty((hss.nstruct, nshell))
            pos_histos = np.zeros((nshell, hnbins))
            edges = None
            for i in range(hss.nstruct):
                radials = np.sqrt(np.sum(np.square(crd[i] / semiaxes), axis=1))
                radials = np.partition(radials, kth)
                for j in range(nshell):
                    h, edges = np.histogram(radials[bds[j]:bds[j + 1]], bins=hnbins,
                                            range=(0, hvmax))
                    pos_histos[j] += h
                    ave_shell_rad[i][j] = np.average(radials[bds[j]:bds[j + 1]])

            np.savetxt(f'shells/ave_radial{run_label}.txt', np.average(ave_shell_rad, axis=0))
            midpoints = (edges[:-1] + edges[1:]) / 2
            fig = plt.figure()
            plt.title('Radial position distributions per shell')
            for j in range(nshell):
                plt.bar(midpoints, height=pos_histos[j], alpha=.6, width=hvmax/hnbins, label='shell {:d}'.format(j+1))
            plt.legend()
            fig.savefig(f'shells/positions_histograms_by_shell{run_label}.pdf')
            fig.savefig(f'shells/positions_histograms_by_shell{run_label}.png')
            plt.close(fig)
        logger.info('Done.')

    except KeyboardInterrupt:
        logger.error('User interrupt. Exiting.')
        exit(1)

    except Exception:
        traceback.print_exc()
        logger.error('Error in shells step\n==============================')
