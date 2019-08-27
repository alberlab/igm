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
        # clean up ready files (those that have been generated) if we want a clean restart of the modeling step
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
         
        """ Load Hss population file, store all coordinates into numpy array, close file"""

        _hss = HssFile(self.hssfilename, 'r')
        self._hss_crd = _hss.coordinates
        _hss.close()

    def teardown_poller(self):

        """ Reopen HSS file, overwrite ALL coordinates, close file """

        _hss = HssFile(self.hssfilename, 'r+')
        _hss.set_coordinates(self._hss_crd)
        _hss.close()
        
    def _run_poller(self):

        """ This is the (asyncrhonous) polling function: if .ready file is there, then execute function "set_structure """

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

        # set "run_name" variable into "runtime" dictionary 
        cfg['runtime']['run_name'] = cfg['runtime']['step_hash'] + '_' + str(struct_id)
        
        # run optimization
        model.optimize(cfg)

        # save optimization results (both optimized coordinates and violations) into a .hms file
        ofname = os.path.join(tmp_dir, 'relax_%d.hms' % struct_id)
        with HmsFile(ofname, 'w') as hms:
            hms.saveModel(struct_id, model)
            hms.saveViolations(pp)

        # make sure write was successful
        with HmsFile(ofname, 'r') as hms:
            if not np.all(hms.get_coordinates() == model.getCoordinates()):
                raise RuntimeError('error writing the file %s' % ofname)

        # create .ready file, which signals to the poller that optimization went to completion
        readyfile = ofname + '.ready'
        open(readyfile, 'w').close()  # touch the ready-file

    def intermediate_name(self):
        return '.'.join([
            self.cfg["optimization"]["structure_output"],
            'relaxInit'
        ])

    def set_structure(self, i):
       
        """ Update the coordinates of the i-th structure in the population matrix (extracted from HSS), this is executed
            in the polling function, once the .ready file is found """

        # name of hms file associated with i-th structure
        fname = "{}_{}.hms".format(self.tmp_file_prefix, i)

        # load hms file, extract coordinates and update master matrix
        with HmsFile(os.path.join(self.tmp_dir, fname), 'r') as hms:
            crd = hms.get_coordinates()
            self._hss_crd[:,i,:] = crd
            
    def reduce(self):
        """
        Collect all structure coordinates together to assemble a hssFile, using the polling function, and repack
        """

        # update structure coordinates
        for i in tqdm(self.file_poller.enumerate(), desc='(REDUCE)'):
            pass

        with HssFile(self.hssfilename, 'r+') as hss:
            n_struct = hss.nstruct
            n_beads = hss.nbead

        logger.info('Coordinates in master file updated for ALL structures; repacking starts...')
        
        # repack hss file (this is a syntax proper to h5df files)
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
        logger.info('repacking done.')

        # save the output file with a unique file name if requested
        if self.keep_intermediate_structures:
            copyfile(
                self.hssfilename + '.swap',
                self.intermediate_name() + '.hss'
            )
 
        # get rid of temporary .swap file
        os.rename(self.hssfilename + '.swap', self.cfg.get("optimization/structure_output"))
