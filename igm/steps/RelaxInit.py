from __future__ import division, print_function

import os.path
import numpy as np
from alabtools.analysis import HssFile
from tqdm import tqdm
from copy import deepcopy
from shutil import copyfile

from ..core import StructGenStep
from ..model import Model, Particle
from ..restraints import Polymer, Envelope, Steric
from ..utils import HmsFile
from ..parallel.async_file_operations import FilePoller

class RelaxInit(StructGenStep):

    def setup(self):
        self.tmp_extensions = [".hms", ".data", ".lam", ".lammpstrj", ".ready"]
        self.tmp_file_prefix = "relax"
        self.file_poller = None
        self.argument_list = range(self.cfg["model"]["population_size"])
        self.hssfilename = self.cfg["optimization"]["structure_output"] + '.tmp'
        self.hss = HssFile(self.hssfilename, 'a', driver='core')
        self.out_data = {
            'restraints': 0.0,
            'violations': 0.0
        }

    def _run_poller(self):
        self.readyfiles = [
            os.path.join(self.tmp_dir, 'relax_%d.hms.ready' %  struct_id )
            for struct_id in self.argument_list
        ]
        self.file_poller = FilePoller(
            self.readyfiles,
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
        relax one random structure chromosome structures
        """
        cfg = deepcopy(cfg)

        #extract structure information
        hssfilename    = cfg["optimization"]["structure_output"]

        #read index, radii, coordinates
        with HssFile(hssfilename,'r') as hss:
            index = hss.index
            radii = hss.radii
            crd = hss.get_struct_crd(struct_id)

        #init Model
        model = Model(uid=struct_id)

        #add particles into model
        n_particles = len(crd)
        for i in range(n_particles):
            model.addParticle(crd[i], radii[i], Particle.NORMAL)

        #========Add restraint
        #add excluded volume restraint
        ex = Steric(cfg.get("model/restraints/excluded/evfactor"))
        model.addRestraint(ex)

        #add nucleus envelop restraint
        if cfg['model']['restraints']['envelope']['nucleus_shape'] == 'sphere':
            ev = Envelope(cfg['model']['restraints']['envelope']['nucleus_shape'],
                          cfg['model']['restraints']['envelope']['nucleus_radius'],
                          cfg['model']['restraints']['envelope']['nucleus_kspring'])
        elif cfg['model']['restraints']['envelope']['nucleus_shape'] == 'ellipsoid':
            ev = Envelope(cfg['model']['restraints']['envelope']['nucleus_shape'],
                          cfg['model']['restraints']['envelope']['nucleus_semiaxes'],
                          cfg['model']['restraints']['envelope']['nucleus_kspring'])
        model.addRestraint(ev)

        #add consecutive polymer restraint
        contact_probabilities = cfg['runtime'].get('consecutive_contact_probabilities', None)
        pp = Polymer(index,
                     cfg['model']['restraints']['polymer']['contact_range'],
                     cfg['model']['restraints']['polymer']['polymer_kspring'],
                     contact_probabilities=contact_probabilities)
        model.addRestraint(pp)

        #========Optimization
        #optimize model
        cfg['runtime']['run_name'] = cfg['runtime']['step_hash'] + '_' + str(struct_id)
        model.optimize(cfg)

        ofname = os.path.join(tmp_dir, 'relax_%d.hms' % struct_id)
        hms = HmsFile(ofname, 'w')
        hms.saveModel(struct_id, model)

        hms.saveViolations(pp)
        hms.close()

        # make sure write was successful
        with HmsFile(ofname, 'r') as hms:
            if not np.all( hms.get_coordinates() == model.getCoordinates() ):
                raise RuntimeError('error writing the file %s' % ofname)

        readyfile = ofname + '.ready'
        open(readyfile, 'w').close() # touch the ready-file

    def intermediate_name(self):
        return '.'.join([
            self.cfg["optimization"]["structure_output"],
            'relaxInit'
        ])
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
        os.rename(self.cfg["optimization"]["structure_output"], self.hssfilename)
        os.rename(self.hssfilename + '.swap', self.cfg["optimization"]["structure_output"])

        # save the output file with a unique file name if requested
        if self.keep_intermediate_structures:
            copyfile(
                self.cfg["optimization"]["structure_output"],
                self.intermediate_name()
            )
