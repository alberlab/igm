from __future__ import division, print_function
import numpy as np
import h5py
import scipy.io
import scipy.sparse
import os
import os.path

from alabtools import Contactmatrix
from alabtools.analysis import HssFile
from alabtools.plots import plot_comparison

import matplotlib.pyplot as plt

from tqdm import tqdm

from ..core import Step
from ..utils.files import make_absolute_path
from ..utils.log import logger
from ..parallel.utils import split_evenly
# tolerance on contact probabilities
eps = 0.05

# approx number of i,j per batch
batch_size = 400

class HicEvaluationStep(Step):

    def setup(self):

        # prepare arguments
        # with HssFile(self.cfg.get('optimization/structure_output'), 'r') as hss:
        #     n_beads = hss.nbeads

        # linsize = int(batch_size**0.5)
        # k = 0
        # for i in range(0, n_beads, linsize):
        #     for j in range(i, n_beads, linsize):
        #         np.save(
        #             os.path.join(self.tmp_dir, 'hic_ev_in_%d.npy' % k),
        #             (i, j, linsize)
        #         )
        #         k += 1

        # self.argument_list = list(range(k))

        # prepare out dir
        self.out_dir = os.path.join(
            self.cfg.get('parameters/workdir'),
            'evaluation',
            'Hi-C',
            'sigma_{:.2f}.iter_{:s}'.format(
                self.cfg.get('runtime/Hi-C/sigma') * 100.0,
                str( self.cfg.get('runtime/opt_iter', 'NA') )
            )
        )

        if not os.path.isdir(self.out_dir):
            os.makedirs(self.out_dir)

        self.argument_list = []


    def name(self):
        s = 'HicEvaluationStep (sigma={:.2f}%, iter={:s})'
        return s.format(
            self.cfg.get('runtime/Hi-C/sigma') * 100.0,
            str( self.cfg.get('runtime/opt_iter', 'N/A') )
        )

    @staticmethod
    def task(struct_id, cfg, tmp_dir):
        # I, J, linsize = np.load( os.path.join(tmp_dir, 'hic_ev_in_%d.npy' % struct_id) )
        # cr = cfg.get('restraints/Hi-C/contact_range', 2.0) * (1 + eps)
        # with HssFile(cfg.get('optimization/structure_output'), 'r') as hss:
        #     r = hss.radii
        #     n = hss.nbeads
        #     nstruct = hss.nstruct
        #     maxi = min(I+linsize, nbeads)
        #     maxj = min(J+linsize, nbeads)
        #     si, sj = maxi-I, maxj-J
        #     res = np.zeros((maxi, maxj))
        #     for i in range(I, maxi):
        #         for j in range(J, maxj):
        #             if j <= i:
        #                 continue
        #             x = hss['coordinates'][i]
        #             y = hss['coordinates'][j]
        #             r0 = cr * (r[i] + r[j])
        #             res[i - I, j - J] = np.count_nonzero(
        #                 np.linalg.norm(x-y, axis=1) < r0
        #             ) / nstruct
        # np.save('hic_ev_out_%d.npy' % struct_id, res)
        return

    def reduce(self):

        # reconstruct contacts full map
        # ii = []
        # jj = []
        # data = []
        # with HssFile(self.cfg.get('optimization/structure_output')) as structure_output:

        out_dir = self.out_dir
        sigma = self.cfg.get('runtime/Hi-C/sigma')

        input_matrix = Contactmatrix(self.cfg.get('restraints/Hi-C/input_matrix'))
        with HssFile(self.cfg.get('optimization/structure_output')) as structure_output:
            output_matrix = structure_output.buildContactMap(contactRange=self.cfg.get('restraints/Hi-C/contact_range')*(1+eps)) # give some tolerance. only in one direction though.
        output_matrix.save( os.path.join( out_dir, 'full_matrix.hcs') )
        output_matrix = output_matrix.sumCopies()
        output_matrix.matrix.data[:] = output_matrix.matrix.data.clip(0, 1)
        output_matrix.save( os.path.join( out_dir, 'out_matrix.hcs') )
        plot_comparison(input_matrix, output_matrix,
            labels=['input', 'output'],
            file=os.path.join(out_dir, 'matrix_comparison.pdf'),
            vmax=0.2)
        for c in input_matrix.index.get_chrom_names():
            plot_comparison(input_matrix[c], output_matrix[c],
                labels=['input', 'output'],
                file=os.path.join(out_dir, 'matrix_comparison_%s.pdf' % c),
                title=c,
                vmax=0.2)
        with np.errstate(divide='ignore', invalid='ignore'):
            diffmat = np.log2( output_matrix.matrix.toarray() / input_matrix.matrix.toarray() )
        maxv = np.percentile(np.abs(diffmat[np.isfinite(diffmat)]), 99)
        plt.figure()
        plt.imshow(diffmat, vmax=maxv, vmin=-maxv, cmap='RdBu_r')
        plt.title('difference_matrix')
        plt.colorbar()
        plt.savefig(os.path.join(out_dir, 'diffmat.pdf'))
        plt.close()
        for c in input_matrix.genome.chroms:
            ii = input_matrix.index.chrom == input_matrix.genome.getchrnum(c)
            plt.figure()
            xmat = diffmat[ii][:, ii]
            plt.imshow(xmat, vmax=maxv, vmin=-maxv, cmap='RdBu_r')
            plt.colorbar()
            plt.savefig( os.path.join(out_dir, 'diffmap_'+ c +'.pdf') )
            plt.close()

        input_matrix = { (i, j): pwish for i, j, pwish in input_matrix.matrix.coo_generator() if pwish >= sigma and i != j}
        diffs = []
        reldiffs = []
        totp = 0
        for i, j, pout in output_matrix.matrix.coo_generator():
            p = input_matrix.get( (i, j) )
            if p is not None:
                diffs.append(pout-p)
                reldiffs.append((pout-p)/p)
                totp += p
        del output_matrix
        del input_matrix
        diffs = np.array(diffs)
        reldiffs = np.array(reldiffs)

        f, ax = plt.subplots(2, 2)
        ax[0,0].set_title('Absolute matrix differences')
        ax[0,0].hist(diffs, bins=100, range=(-1,1))
        ax[0,1].set_title('Relative matrix differences')
        ax[0,1].hist(reldiffs, bins=100, range=(-1,1))
        ax[1,0].set_title('Absolute matrix differences (log)')
        ax[1,0].hist(diffs, bins=100, log=True, range=(-1,1))
        ax[1,1].set_title('Relative matrix differences (log)')
        ax[1,1].hist(reldiffs, bins=100, log=True, range=(-1,1))

        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, 'difference_histograms.pdf'))

        tol = self.cfg.get('restraints/Hi-C/evaluation_tolerance', 0.01)
        n = np.count_nonzero(np.abs(diffs)>tol)
        self.score =np.abs(reldiffs).mean()
        #self.ok = n < 0.01 * len(diffs)
        #self.score = float(n)/len(diffs)
        #self.cfg['runtime']['violation_score'] = self.score
        with open(os.path.join(out_dir, 'stats.txt'), 'w') as f:
            print("#score ave_differences ave_relative_differences", file=f)
            print(self.score, np.average(diffs), np.average(reldiffs), file=f)
        logger.info('>>>  Average relative difference: {:6.3f}%  <<<'.format(self.score*100))
