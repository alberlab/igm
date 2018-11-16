from __future__ import division, print_function

import os
import os.path
import numpy as np
from copy import deepcopy
from shutil import copyfile
import shutil
import json
from subprocess import Popen, PIPE, STDOUT

from alabtools.analysis import HssFile

from ..core import StructGenStep
from ..model import Model, Particle
from ..restraints import Polymer, Envelope, Steric, HiC, Sprite, Damid
from ..utils import HmsFile
from ..utils.files import h5_create_group_if_not_exist, h5_create_or_replace_dataset
from ..parallel.async_file_operations import FilePoller
from ..utils.log import logger, bcolors
from .RandomInit import generate_random_in_sphere
from tqdm import tqdm

DEFAULT_HIST_BINS = 100
DEFAULT_HIST_MAX = 0.1

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

        if "DamID" in self.cfg['restraints']:
            additional_data .append(
                'damid={:.2f}'.format(
                    self.cfg.get('runtime/DamID/sigma', -1.0)
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
        self.argument_list = range(self.cfg["model"]["population_size"])

        self.out_data = {
            'n_imposed': 0.0,
            'n_violations': 0.0,
            'histogram': {
                'counts': np.zeros(DEFAULT_HIST_BINS + 1),
                'edges': np.arange(0, DEFAULT_HIST_MAX, DEFAULT_HIST_MAX/DEFAULT_HIST_BINS).tolist() + [DEFAULT_HIST_MAX, np.inf]
            },
            'bystructure': {
                'n_imposed': np.zeros(self.cfg["model"]["population_size"], dtype=np.float32),
                'n_violations': np.zeros(self.cfg["model"]["population_size"], dtype=np.float32),
                'total_energies': np.zeros(self.cfg["model"]["population_size"], dtype=np.float32),
                'pair_energies': np.zeros(self.cfg["model"]["population_size"], dtype=np.float32),
                'bond_energies': np.zeros(self.cfg["model"]["population_size"], dtype=np.float32),
            },
            'byrestraint': {}
        }

        #self.hssfilename = self.cfg["optimization"]["structure_output"] + '.tmp'
        self.hssfilename = self.cfg["optimization"]["structure_output"] + '.T'
        self.hss = HssFile(self.hssfilename, 'a')
        self.file_poller = None

    def _run_poller(self):
        self.readyfiles = [
            os.path.join(self.tmp_dir, '%s.%d.ready' % (self.cfg.runtime_hash(), struct_id) )
            for struct_id in self.argument_list
        ]
        self.file_poller = FilePoller(
            self.readyfiles,
            callback=self.set_structure,
            args=[[self.hss, i, self.out_data] for i in self.argument_list],
        )
        self.file_poller.watch_async()

    def before_map(self):
        """
        This runs only if map step is not skipped
        """

        # clean up ready files if we want a clean restart of the modeling step
        readyfiles = [
            os.path.join(self.tmp_dir, '%s.%d.ready' % (self.cfg.runtime_hash(), struct_id))
            for struct_id in self.argument_list
        ]
        if self.cfg.get('optimization/clean_restart', False):
            for f in readyfiles:
                if os.path.isfile(f):
                    os.remove(f)

        self._run_poller()


    def before_reduce(self):
        """
        This runs only if reduce step is not skipped
        """
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

        readyfile = os.path.join(tmp_dir, '%s.%d.ready' % (step_id, struct_id))

        # if the ready file exists it does nothing, unless it is a clear run
        if not cfg.get('optimization/clean_restart', False):
            if os.path.isfile(readyfile):
                return

        hssfilename    = cfg["optimization"]["structure_output"]

        #read index, radii, coordinates
        with HssFile(hssfilename,'r') as hss:
            index = hss.index
            radii = hss.radii
            if cfg.get('optimization/random_shuffling', False):
                crd = generate_random_in_sphere(radii, cfg.get('model/restraints/envelope/nucleus_radius'))
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
        ex = Steric(cfg.get("model/restraints/excluded/evfactor"))
        model.addRestraint(ex)

        #add nucleus envelop restraint
        shape = cfg.get('model/restraints/envelope/nucleus_shape')
        envelope_k = cfg.get('model/restraints/envelope/nucleus_kspring')
        radius = 0
        semiaxes = (0, 0, 0)
        if shape == 'sphere':
            radius = cfg.get('model/restraints/envelope/nucleus_radius')
            ev = Envelope(shape, radius, envelope_k)
        elif cfg['model']['restraints']['envelope']['nucleus_shape'] == 'ellipsoid':
            semiaxes = cfg.get('model/restraints/envelope/nucleus_semiaxes')
            ev = Envelope(shape, semiaxes, envelope_k)
        model.addRestraint(ev)
        monitored_restraints.append(ev)

        #add consecutive polymer restraint
        if cfg.get('model/restraints/polymer/polymer_bonds_style') != 'none':
            contact_probabilities = cfg['runtime'].get('consecutive_contact_probabilities', None)
            pp = Polymer(index,
                         cfg['model']['restraints']['polymer']['contact_range'],
                         cfg['model']['restraints']['polymer']['polymer_kspring'],
                         contact_probabilities=contact_probabilities)
            model.addRestraint(pp)
            monitored_restraints.append(pp)

        #add Hi-C restraint
        if "Hi-C" in cfg['restraints']:
            actdist_file = cfg.get('runtime/Hi-C/actdist_file')
            contact_range = cfg.get( 'restraints/Hi-C/contact_range', 2.0 )
            k = cfg.get( 'restraints/Hi-C/contact_kspring', 0.05)

            hic = HiC(actdist_file, contact_range, k)
            model.addRestraint(hic)
            monitored_restraints.append(hic)

        if "DamID" in cfg['restraints']:
            actdist_file = cfg.get('runtime/DamID/damid_actdist_file')
            contact_range = cfg.get('restraints/DamID/contact_range', 2.0 )
            k = cfg.get( 'restraints/DamID/contact_kspring', 0.05)

            damid = Damid(damid_file=actdist_file, contact_range=contact_range, nuclear_radius=radius, k=k,
                          shape=shape, semiaxes=semiaxes)
            model.addRestraint(damid)
            monitored_restraints.append(damid)


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
        optinfo = model.optimize(cfg)

        tol = cfg.get('optimization/violation_tolerance', 0.01)

        ofname = os.path.join(tmp_dir, 'mstep_%d.hms' % struct_id)
        with HmsFile(ofname, 'w') as hms:
            hms.saveModel(struct_id, model)

            # create violations statistics
            vstat = {}
            for r in monitored_restraints:
                vs = []
                n_imposed = 0
                for fid in r.forceID:
                    f = model.forces[fid]
                    n_imposed += f.rnum
                    if f.rnum > 1:
                        vs += f.getViolationRatios(model.particles).tolist()
                    else:
                        vs.append(f.getViolationRatio(model.particles))
                vs = np.array(vs)
                H, edges = get_violation_histogram(vs)
                num_violations = np.count_nonzero(vs > tol)
                vstat[repr(r)] = {
                    'histogram': {
                        'edges' : edges.tolist(),
                        'counts' : H.tolist()
                    },
                    'n_violations' : num_violations,
                    'n_imposed':  n_imposed
                }

            h5_create_or_replace_dataset(hms, 'violation_stats', json.dumps(vstat))

            if isinstance(optinfo, dict):
                grp = h5_create_group_if_not_exist(hms, 'opt_info')
                for k, v in optinfo.items():
                    h5_create_or_replace_dataset(grp, k, data=v)

        # double check it has been written correctly
        with HmsFile(ofname, 'r') as hms:
            if not np.all( hms.get_coordinates() == model.getCoordinates() ):
                raise RuntimeError('error writing the file %s' % ofname)

        readyfile = os.path.join(tmp_dir, '%s.%d.ready' % (step_id, struct_id) )
        open(readyfile, 'w').close() # touch the ready-file

    #-

    def set_structure(self, hss, i, summary_data):
        fname = "{}_{}.hms".format(self.tmp_file_prefix, i)
        with HmsFile( os.path.join( self.tmp_dir, fname ), 'r' ) as hms:

            # set coordinates
            crd = hms.get_coordinates()
            hss.set_struct_crd(i, crd)

            # collect violation statistics
            try:
                vstat = json.loads(hms['violation_stats'][()])
            except:
                vstat = {}

            n_tot = 0
            n_vio = 0
            hist_tot = np.zeros(DEFAULT_HIST_BINS + 1)
            for k, cstat in vstat.items():
                if k not in summary_data['byrestraint']:
                    summary_data['byrestraint'][k] = {
                        'histogram': {
                            'counts': np.zeros(DEFAULT_HIST_BINS + 1)
                        },
                        'n_violations': 0,
                        'n_imposed': 0
                    }

                n_tot += cstat.get('n_imposed', 0)
                n_vio += cstat.get('n_violations', 0)
                hist_tot += cstat['histogram']['counts']
                summary_data['byrestraint'][k]['n_violations'] += cstat.get('n_violations', 0)
                summary_data['byrestraint'][k]['n_imposed'] += cstat.get('n_imposed', 0)
                summary_data['byrestraint'][k]['histogram']['counts'] += cstat['histogram']['counts']

            summary_data['n_imposed'] += n_tot
            summary_data['n_violations'] += n_vio
            summary_data['histogram']['counts'] += hist_tot
            summary_data['bystructure']['n_imposed'][i] = n_tot
            summary_data['bystructure']['n_violations'][i] = n_vio

            # collect optimization statistics
            try:
                summary_data['bystructure']['total_energies'][i] = hms['opt_info']['final-energy'][()]
                summary_data['bystructure']['pair_energies'][i] = hms['opt_info']['pair-energy'][()]
                summary_data['bystructure']['bond_energies'][i] = hms['opt_info']['bond_energy'][()]
            except:
                pass

    def reduce(self):
        """
        Collect all structure coordinates together to assemble a hssFile
        """

        # create a temporary file if does not exist.
        # hssfilename = self.cfg["optimization"]["structure_output"] + '.tmp'
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

        for _ in tqdm(self.file_poller.enumerate(), desc='(REDUCE)'):
            pass



        total_violations, total_restraints = self.out_data['n_violations'], self.out_data['n_imposed']

        if (total_violations == 0) and (total_restraints == 0):
            violation_score = 0
        else:
            violation_score = total_violations / total_restraints

        self.hss.set_violation(violation_score)

        h5_create_or_replace_dataset(self.hss, 'summary', data=json.dumps(self.out_data, default=lambda a: a.tolist()))

        n_struct = self.hss.nstruct
        n_beads = self.hss.nbead
        self.hss.close()
        logger.info(
            bcolors.HEADER + 'Average number of restraints per bead: %f' + bcolors.ENDC,
            total_restraints / n_struct / n_beads
        )
        c = bcolors.WARNING if violation_score >= self.cfg.get('optimization/max_violations') else bcolors.OKGREEN
        logger.info(
            c + 'Violation score: %d / %d = ' + bcolors.BOLD + '%f' + bcolors.ENDC,
            total_violations,
            total_restraints,
            violation_score
        )
        # swap temporary and current hss files
        # os.rename(self.hssfilename, self.hssfilename + '.swap')
        # os.rename(self.cfg["optimization"]["structure_output"], self.hssfilename)
        # os.rename(self.hssfilename + '.swap', self.cfg["optimization"]["structure_output"])

        PACK_SIZE = 1e6
        pack_beads = max(1, int( PACK_SIZE / n_struct / 3 ) )
        pack_beads = min(pack_beads, n_beads)
        cmd = [
            'h5repack',
            '-i', self.hssfilename,
            '-o', self.hssfilename + '.swap',
            '-l', 'coordinates:CHUNK={:d}x{:d}x3'.format(pack_beads, n_struct),
            '-v'
        ]
        sp = Popen(cmd, stderr=PIPE, stdout=PIPE)
        # cmd = 'h5repack -l coordinates:CHUNK={:d}x{:d}x3 {:s} {:s}'.format(
        #     pack_beads, n_struct, self.hssfilename, self.hssfilename + '.swap'
        # )
        logger.info('repacking...')
        stdout, stderr = sp.communicate()
        if sp.returncode != 0:
            print(' '.join(cmd))
            print('O:', stdout.decode('utf-8'))
            print('E:', stderr.decode('utf-8'))
            raise RuntimeError('repacking failed. error code: %d' % sp.returncode)
        logger.info('done.')
        shutil.move(self.hssfilename + '.swap', self.cfg.get("optimization/structure_output"))

        # save the output file with a unique file name if requested
        if self.keep_intermediate_structures:
            copyfile(
                self.cfg["optimization"]["structure_output"],
                self.intermediate_name() + '.hss'
            )

        # finally set the violation score in the runtime
        self.cfg['runtime']['violation_score'] = violation_score



    def intermediate_name(self):

        additional_data = []
        if "DamID" in self.cfg['runtime']:
            additional_data .append(
                'damid_{:.4f}'.format(
                    self.cfg.get('runtime/DamID/sigma', -1.0)
                )
            )
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
            self.cfg["optimization"]["structure_output"],
        ] + additional_data )

    def __del__(self):
        try:
            self.hss.close()
        except:
            pass
#==

def get_violation_histogram(v, nbins=DEFAULT_HIST_BINS, vmax=1):
    v = np.array(v)
    over = np.count_nonzero(v>vmax)
    inner = v[v<=vmax]
    H, edges = np.histogram(inner, bins=nbins, range=(0, vmax))
    H = np.concatenate([H, [over]])
    edges = np.concatenate([edges, [np.inf]])
    return H, edges
