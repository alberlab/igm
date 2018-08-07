from __future__ import division, print_function

import os
import os.path
import numpy as np
import sys
from copy import deepcopy
from shutil import copyfile

from alabtools.analysis import HssFile

from ..core import StructGenStep
from ..model import Model, Particle
from ..restraints import Polymer, Envelope, Steric, HiC, Sprite
from ..utils import HmsFile
from ..parallel.async_file_operations import FileLock, FutureFilePoller
from ..utils.log import print_progress, logger
from .RandomInit import generate_random_in_sphere
from tqdm import tqdm


class ModelingStep(StructGenStep):

    def name(self):
        s = 'ModelingStep'
        additional_data = []
        if "Hi-C" in self.cfg['restraints']:
            additional_data .append(
                'sigma={:.2f}%'.format(
                    self.cfg['runtime']['Hi-C']['sigma'] * 100.0
                )
            )
        if 'opt_iter' in self.cfg['runtime']:
            additional_data.append(
                'iter={}'.format(
                    self.cfg['runtime'].get('opt_iter', 'N/A')
                )
            )

        if len(additional_data):
            s += ' (' + ', '.join(additional_data) + ')'
        return s

    def setup(self):
        self.tmp_extensions = [".hms", ".data", ".lam", ".lammpstrj", ".ready"]
        self.tmp_file_prefix = "mstep"
        self.argument_list = range(self.cfg["population_size"])

        self.out_data = {
            'restraints': 0.0,
            'violations': 0.0
        }

        self.hssfilename = self.cfg["structure_output"] + '.tmp'
        self.hss = HssFile(self.hssfilename, 'a', driver='core')
        self.file_poller = None

    def _run_poller(self):
        self.lockfiles = [
            os.path.join(self.tmp_dir, '%s.%d.ready' % (self.cfg.runtime_hash(), struct_id) )
            for struct_id in self.argument_list
        ]
        self.file_poller = FutureFilePoller(
            self.lockfiles,
            callback=self.set_structure,
            args=[[self.hss, i, self.out_data] for i in self.argument_list],
        )
        self.file_poller.watch_async()

    def before_map(self):
        '''
        This runs only if map step is not skipped
        '''
        self._run_poller()


    def before_reduce(self):
        '''
        This runs only if reduce step is not skipped
        '''
        # if we don't have a poller, set it up
        if self.file_poller is None:
            self._run_poller()


    @staticmethod
    def task(struct_id, cfg, tmp_dir):
        """
        Do single structure modeling with bond assignment from A-step
        """
        # the static method modifications to the cfg should only be local,
        # use a copy of the config file
        cfg = deepcopy(cfg)

        #extract structure information
        step_id = cfg.runtime_hash()

        hssfilename    = cfg["structure_output"]

        #read index, radii, coordinates
        with HssFile(hssfilename,'r') as hss:
            index = hss.index
            radii = hss.radii
            if cfg.get('random_shuffling', False):
                crd = generate_random_in_sphere(radii, cfg['model']['nucleus_radius'])
            else:
                crd = hss.get_struct_crd(struct_id)

        #init Model
        model = Model(uid=struct_id)

        # get the chain ids
        chain_ids = np.concatenate( [ [i]*s for i, s in enumerate(index.chrom_sizes) ] )

        #add particles into model
        n_particles = len(crd)
        for i in range(n_particles):
            model.addParticle(crd[i], radii[i], Particle.NORMAL, chainID=chain_ids[i])

        #========Add restraint
        monitored_restraints = []

        #add excluded volume restraint
        ex = Steric(cfg['model']['evfactor'])
        model.addRestraint(ex)

        #add nucleus envelop restraint
        if cfg['model']['nucleus_shape'] == 'sphere':
            ev = Envelope(cfg['model']['nucleus_shape'],
                          cfg['model']['nucleus_radius'],
                          cfg['model']['nucleus_kspring'])
        elif cfg['model']['nucleus_shape'] == 'ellipsoid':
            ev = Envelope(cfg['model']['nucleus_shape'],
                          cfg['model']['nucleus_semiaxes'],
                          cfg['model']['nucleus_kspring'])
        model.addRestraint(ev)

        #add consecutive polymer restraint
        contact_probabilities = cfg['runtime'].get('consecutive_contact_probabilities', None)
        pp = Polymer(index,
                     cfg['model']['contact_range'],
                     cfg['model']['contact_kspring'],
                     contact_probabilities=contact_probabilities)
        model.addRestraint(pp)
        monitored_restraints.append(pp)

        #add Hi-C restraint
        if "Hi-C" in cfg['restraints']:
            dictHiC = cfg['restraints']['Hi-C']
            actdist_file = cfg['runtime']['Hi-C']['actdist_file']
            contact_range = dictHiC.get( 'contact_range', 2.0 )
            k = dictHiC.get( 'contact_kspring', 1.0 )

            hic = HiC(actdist_file, contact_range, k)
            model.addRestraint(hic)
            monitored_restraints.append(hic)

        if "sprite" in cfg['restraints']:
            sprite_opt = cfg['restraints']['sprite']
            sprite = Sprite(
                sprite_opt['assignment_file'],
                sprite_opt['volume_fraction'],
                struct_id,
                sprite_opt['kspring']
            )
            model.addRestraint(sprite)
            monitored_restraints.append(sprite)


        #========Optimization
        #optimize model
        cfg['runtime']['run_name'] = cfg['runtime']['step_hash'] + '_' + str(struct_id)
        model.optimize(cfg)

        tol = cfg.get('violation_tolerance', 0.01)
        lockfile = os.path.join(tmp_dir, '%s.%d.ready' % (step_id, struct_id) )
        with FileLock(lockfile):
            open(lockfile, 'w').close() # touch the ready-file
            ofname = os.path.join(tmp_dir, 'mstep_%d.hms' % struct_id)
            with HmsFile(ofname, 'w') as hms:
                hms.saveModel(struct_id, model)

                for r in monitored_restraints:
                    hms.saveViolations(r, tolerance=tol)

            # double check it has been written correctly
            with HmsFile(ofname, 'r') as hms:
                if np.all( hms.get_coordinates() == model.getCoordinates() ):
                    raise RuntimeError('error writing the file %s' % ofname)


    #-

    def set_structure(self, hss, i, data):
        fname = "{}_{}.hms".format(self.tmp_file_prefix, i)
        # dammit, some times the nfs is not in sync, no matter the poller
        hms = HmsFile( os.path.join( self.tmp_dir, fname ), 'r' )
        crd = hms.get_coordinates()
        hss.set_struct_crd(i, crd)
        data['restraints'] += hms.get_total_restraints()
        data['violations'] += hms.get_total_violations()


    def reduce(self):
        """
        Collect all structure coordinates together to assemble a hssFile
        """

        # create a temporary file if does not exist.
        # hssfilename = self.cfg["structure_output"] + '.tmp'
        # hss = HssFile(hssfilename, 'a', driver='core')

        # #iterate all structure files and


        # for i in print_progress(range(hss.nstruct), timeout=1, every=None, fd=sys.stderr):
        #     fname = "{}_{}.hms".format(self.tmp_file_prefix, i)
        #     hms = HmsFile( os.path.join( self.tmp_dir, fname ) )
        #     crd = hms.get_coordinates()
        #     total_restraints += hms.get_total_restraints()
        #     total_violations += hms.get_total_violations()

        #     hss.set_struct_crd(i, crd)
        # #-

        for i in tqdm(self.file_poller.enumerate(), desc='(REDUCE)'):
            pass

        total_violations, total_restraints = self.out_data['violations'], self.out_data['restraints']

        if (total_violations == 0) and (total_restraints == 0):
            violation_score = 0
        else:
            violation_score = total_violations / total_restraints

        self.hss.set_violation(violation_score)

        self.hss.close()

        # swap temporary and current hss files
        os.rename(self.hssfilename, self.hssfilename + '.swap')
        os.rename(self.cfg["structure_output"], self.hssfilename)
        os.rename(self.hssfilename + '.swap', self.cfg["structure_output"])

        # save the output file with a unique file name if requested
        if self.keep_intermediate_structures:
            copyfile(
                self.cfg["structure_output"],
                self.intermediate_name()
            )

        # finally set the violation score in the runtime
        self.cfg['runtime']['violation_score'] = violation_score
        logger.info('Violation score: %d / %d = %f' % (total_violations, total_restraints, violation_score))


    def intermediate_name(self):

        additional_data = []
        if "Hi-C" in self.cfg['runtime']:
            additional_data .append(
                'sigma_{:.4f}'.format(
                    self.cfg['runtime']['Hi-C'].get('sigma', -1.0)
                )
            )
        if 'opt_iter' in self.cfg['runtime']:
            additional_data.append(
                'iter_{}'.format(
                    self.cfg['runtime']['opt_iter']
                )
            )
        additional_data.append(str(self.uid))

        return '.'.join( [
            self.cfg["structure_output"],
        ] + additional_data )


#==
