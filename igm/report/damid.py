import numpy as np
import matplotlib.pyplot as plt
import logging
import traceback
from alabtools import HssFile
from scipy.stats import pearsonr
from .utils import create_folder, snormsq_ellipse


# noinspection PyTypeChecker
def report_damid(hssfname, damid_file, contact_range, semiaxes=None, run_label=''):
    logger = logging.getLogger("DamID")
    logger.info('Executing DamID report')

    if run_label:
        run_label = '-' + run_label
    try:
        create_folder("damid")

        with HssFile(hssfname, 'r') as hss:
            index = hss.index
            radii = hss.radii
            if semiaxes is None:
                # see if we have information about semiaxes in the file
                try:
                    semiaxes = hss['envelope']['params'][()]
                    if len(semiaxes.shape) == 0:  # is scalar
                        semiaxes = np.array([semiaxes, semiaxes, semiaxes])
                except KeyError:
                    semiaxes = np.array([5000., 5000., 5000.])

            out_damid_prob = np.zeros(len(index.copy_index))
            for locid in index.copy_index.keys():
                ii = index.copy_index[locid]
                n_copies = len(ii)

                r = radii[ii[0]]

                # rescale pwish considering the number of copies
                # pwish = np.clip(pwish/n_copies, 0, 1)

                d_sq = np.empty(n_copies * hss.nstruct)

                for i in range(n_copies):
                    x = hss.get_bead_crd(ii[i])
                    nuc_rad = np.array(semiaxes) * (1 - contact_range)
                    d_sq[i * hss.nstruct:(i + 1) * hss.nstruct] = snormsq_ellipse(x, nuc_rad, r)

                contact_count = np.count_nonzero(d_sq >= 1)
                out_damid_prob[locid] = float(contact_count) / hss.nstruct / n_copies
            np.savetxt('damid/output.txt', out_damid_prob)

        if damid_file:
            damid_profile = np.loadtxt(damid_file, dtype='float32')
            np.savetxt(f'damid/input{run_label}.txt', damid_profile)
            fig = plt.figure(figsize=(4, 4))
            plt.title(f'DamID{run_label}')
            vmax = max(np.nanmax(damid_profile), np.nanmax(out_damid_prob))
            vmin = min(np.nanmin(damid_profile), np.nanmin(out_damid_prob))
            corr = pearsonr(damid_profile, out_damid_prob)
            np.savetxt(f'damid/pearsonr{run_label}.txt', corr)
            plt.scatter(damid_profile, out_damid_prob, s=6)
            plt.xlim(vmin, vmax)
            plt.ylim(vmin, vmax)
            plt.text(vmin * 1.01, vmax * 0.95, f'pearson correlation: {corr[0]:.5f}')
            plt.plot([vmin, vmax], [vmin, vmax], 'k--')
            plt.xlabel('input')
            plt.ylabel('output')
            fig.savefig(f'damid/scatter{run_label}.pdf')
            fig.savefig(f'damid/scatter{run_label}.png')
            plt.close(fig)
        logger.info('Done.')

    except KeyboardInterrupt:
        logger.error('User interrupt. Exiting.')
        exit(1)

    except Exception:
        traceback.print_exc()
        logger.error('Error in DamID step\n==============================')
