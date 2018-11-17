from __future__ import division, print_function

import os.path
import numpy as np
from alabtools.analysis import HssFile
from tqdm import tqdm
from copy import deepcopy
from shutil import copyfile
from subprocess import Popen, PIPE

from ..core import StructGenStep
from ..model import Model, Particle
from ..restraints import Polymer, Envelope, Steric
from ..utils import HmsFile
from ..parallel.async_file_operations import FilePoller
from ..utils.log import logger


class RelaxInit(StructGenStep):

    def setup(self):
        self.tmp_extensions = [".hms", ".data", ".lam", ".lammpstrj", ".ready"]
        self.tmp_file_prefix = "relax"
        self.file_poller = None
        self.argument_list = range(self.cfg["model"]["population_size"])
        self.hssfilename = self.cfg["optimization"]["structure_output"] + '.T'

    def before_map(self):
        '''
        This runs only if map step is not skipped
        '''
        # clean up ready files if we want a clean restart of the modeling step
        readyfiles = [
            os.path.join(self.tmp_dir, 'relax_%d.hms.ready' % struct_id)
            for struct_id in self.argument_list
        ]
        if self.cfg.get('optimization/clean_restart', False):
            for f in readyfiles:
                if os.path.isfile(f):
                    os.remove(f)
        self._run_poller()

    def setup_poller(self):
        self._hss = HssFile(self.hssfilename, 'r+')

    def teardown_poller(self):
        self._hss.close()

    def _run_poller(self):
        readyfiles = [
            os.path.join(self.tmp_dir, 'relax_%d.hms.ready' % struct_id)
            for struct_id in self.argument_list
        ]

        self.file_poller = FilePoller(
            readyfiles,
            callback=self.set_structure,
            args=[[i] for i in self.argument_list],
            setup=self.setup_poller,
            teardown=self.teardown_poller
        )
        self.file_poller.watch_async()

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
        relax one random structure chromosome structures
        """
        cfg = deepcopy(cfg)

        readyfile = os.path.join(tmp_dir, 'relax_%d.hms.ready' % struct_id)

        # if the ready file exists it does nothing, unless it is a clear run
        if not cfg.get('optimization/clean_restart', False):
            if os.path.isfile(readyfile):
                return

        # extract structure information
        hssfilename = cfg["optimization"]["structure_output"]

        # read index, radii, coordinates
        with HssFile(hssfilename, 'r') as hss:
            index = hss.index
            radii = hss.radii
            crd = hss.get_struct_crd(struct_id)

        # init Model
        model = Model(uid=struct_id)

        # add particles into model
        n_particles = len(crd)
        for i in range(n_particles):
            model.addParticle(crd[i], radii[i], Particle.NORMAL)

        # ========Add restraint
        # add excluded volume restraint
        ex = Steric(cfg.get("model/restraints/excluded/evfactor"))
        model.addRestraint(ex)

        # add nucleus envelop restraint
        if cfg['model']['restraints']['envelope']['nucleus_shape'] == 'sphere':
            ev = Envelope(cfg['model']['restraints']['envelope']['nucleus_shape'],
                          cfg['model']['restraints']['envelope']['nucleus_radius'],
                          cfg['model']['restraints']['envelope']['nucleus_kspring'])
        elif cfg['model']['restraints']['envelope']['nucleus_shape'] == 'ellipsoid':
            ev = Envelope(cfg['model']['restraints']['envelope']['nucleus_shape'],
                          cfg['model']['restraints']['envelope']['nucleus_semiaxes'],
                          cfg['model']['restraints']['envelope']['nucleus_kspring'])
        model.addRestraint(ev)

        # add consecutive polymer restraint
        contact_probabilities = cfg['runtime'].get('consecutive_contact_probabilities', None)
        pp = Polymer(index,
                     cfg['model']['restraints']['polymer']['contact_range'],
                     cfg['model']['restraints']['polymer']['polymer_kspring'],
                     contact_probabilities=contact_probabilities)
        model.addRestraint(pp)

        # ========Optimization
        # optimize model
        cfg['runtime']['run_name'] = cfg['runtime']['step_hash'] + '_' + str(struct_id)
        model.optimize(cfg)

        ofname = os.path.join(tmp_dir, 'relax_%d.hms' % struct_id)
        with HmsFile(ofname, 'w') as hms:
            hms.saveModel(struct_id, model)
            hms.saveViolations(pp)

        # make sure write was successful
        with HmsFile(ofname, 'r') as hms:
            if not np.all(hms.get_coordinates() == model.getCoordinates()):
                raise RuntimeError('error writing the file %s' % ofname)

        readyfile = ofname + '.ready'
        open(readyfile, 'w').close()  # touch the ready-file

    def intermediate_name(self):
        return '.'.join([
            self.cfg["optimization"]["structure_output"],
            'relaxInit'
        ])

    def set_structure(self, i):
        fname = "{}_{}.hms".format(self.tmp_file_prefix, i)
        with HmsFile(os.path.join(self.tmp_dir, fname), 'r') as hms:
            crd = hms.get_coordinates()
            self._hss.set_struct_crd(i, crd)

    def reduce(self):
        """
        Collect all structure coordinates together to assemble a hssFile
        """

        for i in tqdm(self.file_poller.enumerate(), desc='(REDUCE)'):
            pass

        with HssFile(self.hssfilename, 'r+') as hss:
            n_struct = hss.nstruct
            n_beads = hss.nbead

        # repack hss file
        PACK_SIZE = 1e6
        pack_beads = max(1, int(PACK_SIZE / n_struct / 3))
        pack_beads = min(pack_beads, n_beads)
        cmd = [
            'h5repack',
            '-i', self.hssfilename,
            '-o', self.hssfilename + '.swap',
            '-l', 'coordinates:CHUNK={:d}x{:d}x3'.format(pack_beads, n_struct),
            '-v'
        ]

        sp = Popen(cmd, stderr=PIPE, stdout=PIPE)
        logger.info('repacking...')
        stdout, stderr = sp.communicate()
        if sp.returncode != 0:
            print(' '.join(cmd))
            print('O:', stdout.decode('utf-8'))
            print('E:', stderr.decode('utf-8'))
            raise RuntimeError('repacking failed. error code: %d' % sp.returncode)
        logger.info('done.')

        # save the output file with a unique file name if requested
        if self.keep_intermediate_structures:
            copyfile(
                self.hssfilename + '.swap',
                self.intermediate_name() + '.hss'
            )

        os.rename(self.hssfilename + '.swap', self.cfg.get("optimization/structure_output"))
