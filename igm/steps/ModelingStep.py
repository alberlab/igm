from __future__ import division, print_function

import os
import os.path
import numpy as np
from copy import deepcopy
from shutil import copyfile
import shutil
import json
from subprocess import Popen, PIPE
import traceback

from alabtools.analysis import HssFile

from ..core import StructGenStep
from ..model import Model, Particle
from ..restraints import Polymer, Envelope, Steric, intraHiC, interHiC, Sprite, Damid, Nucleolus, GenEnvelope, Fish
from ..utils import HmsFile
from ..utils.files import h5_create_group_if_not_exist, h5_create_or_replace_dataset, make_absolute_path
from ..parallel.async_file_operations import FilePoller
from ..utils.log import logger, bcolors
from .RandomInit import generate_random_in_sphere
from tqdm import tqdm

# specifying violation histogram properties
DEFAULT_HIST_BINS = 100
DEFAULT_HIST_MAX = 0.1


class ModelingStep(StructGenStep):

    def name(self):

        """ This explains verbatim which optimization is performed, is printed to the logger """

        s = 'ModelingStep'
        additional_data = []
        if "Hi-C" in self.cfg['restraints']:
            additional_data .append(
                'inter_sigma={:.2f}%'.format(
                    self.cfg['runtime']['Hi-C']['inter_sigma'] * 100.0
                )
            )

            additional_data .append(
                'intra_sigma={:.2f}%'.format(
                    self.cfg['runtime']['Hi-C']['intra_sigma'] * 100.0
                )
            )

        if "DamID" in self.cfg['restraints']:
            additional_data .append(
                'damid={:.2f}'.format(
                    self.cfg.get('runtime/DamID/sigma', -1.0)
                )
            )

        if "sprite" in self.cfg['restraints']:
            additional_data .append(
                'sprite={:.1f}%'.format(
                    self.cfg['runtime']['sprite']['volume_fraction'] * 100.0
                )
            )

        if "FISH" in self.cfg['restraints']:
            additional_data .append(
                'FISH={:.1f}'.format(
                    self.cfg['runtime']['FISH']['tol']
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
    #-


    def setup(self):

        """ Read in parameters from cfg file """

        self.tmp_extensions = [".hms", ".data", ".lam", ".lammpstrj", ".ready"]
        self.tmp_file_prefix = "mstep"
        self.argument_list = range(self.cfg["model"]["population_size"])
        self.hssfilename = self.cfg["optimization"]["structure_output"] + '.T'
        self.file_poller = None
    #-

    def _run_poller(self):

        """ Setup, run and teardown polling function (See also RelaxInit.py script) """

        readyfiles = [
            os.path.join(self.tmp_dir, '%s.%d.ready' % (self.uid, struct_id))
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
    #-


    def before_map(self):
        """
        This runs only if map step is not skipped
        """
        # clean up ready files (those that arae there and spotter by the poller) if we want a clean restart of the modeling step
        readyfiles = [
            os.path.join(self.tmp_dir, '%s.%d.ready' % (self.uid, struct_id))
            for struct_id in self.argument_list
        ]
        if self.cfg.get('optimization/clean_restart', False):
            for f in readyfiles:
                if os.path.isfile(f):
                    os.remove(f)

        self._run_poller()
    #-


    def before_reduce(self):
        """
        This runs only if reduce step is not skipped
        """
        # if we don't have a poller, set it up
        if self.file_poller is None:
            self._run_poller()
    #-


    @staticmethod
    def task(struct_id, cfg, tmp_dir):

        """
        Do single structure modeling (i.e., run LAMMPS) with restraint assignment from A-step
        """

        # the static method modifications to the cfg should only be local,
        # use a copy of the config file
        cfg = deepcopy(cfg)

        # extract structure information
        step_id = cfg.get('runtime/step_hash', 'xxxx')

        readyfile = os.path.join(tmp_dir, '%s.%d.ready' % (step_id, struct_id))

        # if the ready file exists it does nothing, unless it is a clear run
        if not cfg.get('optimization/clean_restart', False):
            if os.path.isfile(readyfile):
                return

        hssfilename = cfg["optimization"]["structure_output"]

        # read index, radii, coordinates
        with HssFile(hssfilename, 'r') as hss:
            index = hss.index
            radii = hss.radii
            chrom = hss.get_index().chrom
            if cfg.get('optimization/random_shuffling', False):
                crd = generate_random_in_sphere(radii, cfg.get('model/restraints/envelope/nucleus_radius'))
            else:
                crd = hss.get_struct_crd(struct_id)

        # init Model class (igm.model)
        model = Model(uid=struct_id)

        # get the chain ids
        chain_ids = np.concatenate( [ [i]*s for i, s in enumerate(index.chrom_sizes) ] )

        # add particles into model
        n_particles = len(crd)
        for i in range(n_particles):
            model.addParticle(crd[i], radii[i], Particle.NORMAL, chainID=chain_ids[i])

        # Add restraints
        monitored_restraints = []

        # ---- POLYMER STRUCTURAL INTEGRITY INTRINSIC restraints ----- #

        # add excluded volume restraint
        ex = Steric(cfg.get("model/restraints/excluded/evfactor"))
        model.addRestraint(ex)

        # add nucleus envelope restraint
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
        elif cfg['model']['restraints']['envelope']['nucleus_shape'] == 'exp_map':
            
            env_idx = struct_id % 4

            volume_file  = cfg['model']['restraints']['envelope']['input_map'][env_idx]
            ev = GenEnvelope(shape, volume_file, envelope_k)

        model.addRestraint(ev)
        monitored_restraints.append(ev)

        # add consecutive bead polymer restraint to ensure chain connectivity
        if cfg.get('model/restraints/polymer/polymer_bonds_style') != 'none':
            contact_probabilities = cfg['runtime'].get('consecutive_contact_probabilities', None)
            pp = Polymer(index,
                         cfg['model']['restraints']['polymer']['contact_range'],
                         cfg['model']['restraints']['polymer']['polymer_kspring'],
                         contact_probabilities=contact_probabilities)
            model.addRestraint(pp)
            monitored_restraints.append(pp)

        # LB: add nuclear body excluded volume restraints
        if "nucleolus" in cfg['restraints']:

            # read in nucle lus coordinates and radius from cfg file

            for mappa  in cfg['restraints']['nucleolus']['input_map']:

                    nucl = GenEnvelope(cfg['restraints']['nucleolus']['shape'], mappa,
                                       cfg['restraints']['nucleolus']['k_spring'])
                    model.addRestraint(nucl)
                    monitored_restraints.append(nucl)

        # ---- IGM MODELING RESTRAINTS FROM EXPERIMENTAL DATA ---- #

        # add Hi-C restraint
        if "Hi-C" in cfg['restraints']:
            
            # read parameters from cfg file
            actdist_file  = cfg.get('runtime/Hi-C/actdist_file')
            contact_range = cfg.get('restraints/Hi-C/contact_range', 2.0)
            k             = cfg.get('restraints/Hi-C/contact_kspring', 0.05)

            # effectively add inter  HiC restraints (bonds)
            interhic           = interHiC(actdist_file, chrom, contact_range, k)   # LB, add chrom option
            model.addRestraint(interhic)
            monitored_restraints.append(interhic)

            intrahic           = intraHiC(actdist_file, chrom, contact_range, k)   # LB, add chrom option
            model.addRestraint(intrahic)
            monitored_restraints.append(intrahic)


        # add DAMID restraint
        if "DamID" in cfg['restraints']:

            # read parameters from cfg file
            actdist_file  = cfg.get('runtime/DamID/damid_actdist_file')
            contact_range = cfg.get('restraints/DamID/contact_range', 2.0)
            k             = cfg.get('restraints/DamID/contact_kspring', 0.05)

            # effectively add DAMID restraints
            damid         = Damid(damid_file=actdist_file, contact_range=contact_range,
                          nuclear_radius=radius, k=k,
                          shape=shape, semiaxes=semiaxes)
            model.addRestraint(damid)
            monitored_restraints.append(damid)

        # add SPRITE restraint
        if "sprite" in cfg['restraints']:

            # read parameters from cfg file
            sprite_tmp = make_absolute_path(
                cfg.get('restraints/sprite/tmp_dir', 'sprite'),
                cfg.get('parameters/tmp_dir')
            )
            sprite_assignment_filename = make_absolute_path(
                cfg.get('restraints/sprite/assignment_file', 'sprite_assignment.h5'),
                sprite_tmp
            )

            kspring = cfg['restraints']['sprite']['kspring']
            vol_fraction = cfg['runtime']['sprite']['volume_fraction']

            # effectively add SPRITE retraints 
            sprite = Sprite(
                sprite_assignment_filename,
                volume_occupancy = vol_fraction,
                struct_id = struct_id,
                k = kspring
            )

            model.addRestraint(sprite)
            monitored_restraints.append(sprite)

        if "FISH" in cfg['restraints']:

            # read parameters from cfg file
            FISH_tmp = make_absolute_path(
                cfg.get('restraints/FISH/tmp_dir', 'FISH'),
                cfg.get('parameters/tmp_dir')
            )
            fish_assignment_file = make_absolute_path(
                cfg.get('restraints/FISH/fish_file', 'fish_assignment.h5'),
                FISH_tmp
            )

            kspring   = cfg['restraints']['FISH']['kspring']
            tolerance = cfg['runtime']['FISH']['tol']
            rtype     = cfg['restraints']['FISH']['rtype']

            # effectively add FISH restraints (index e' definito, check polymer restraint)
            fish      = Fish(fish_assignment_file = fish_assignment_file, index = index, struct_id = struct_id,
                        kspring = kspring, tolerance = tolerance, rtype = rtype) 

            model.addRestraint(fish)
            monitored_restraints.append(fish) 
        
        # ========Optimization
        cfg['runtime']['run_name'] = cfg.get('runtime/step_hash') + '_' + str(struct_id)
        optinfo = model.optimize(cfg)

        # tolerance parameter: if violation score is smaller than tolerance, then restraint is satisfied
        tol = cfg.get('optimization/violation_tolerance', 0.01)

        # save optimized configuration and violation results to .hms file
        ofname = os.path.join(tmp_dir, 'mstep_%d.hms' % struct_id)
        with HmsFile(ofname, 'w') as hms:
            hms.saveModel(struct_id, model)

            # create violations statistics and save all of that into the "vstat" dictionary
            vstat = {}
            for r in monitored_restraints:
                vs = []
                n_imposed = 0
                for fid in r.forceID:
                    f = model.forces[fid]
                    n_imposed += f.rnum
                    if f.rnum > 1:
			# a list of values is appended to vs = [] at once
                        vs += f.getViolationRatios(model.particles).tolist()
                    else:
			# one value is appended at the time to vs = []
                        vs.append(f.getViolationRatio(model.particles))

                vs = np.array(vs)
                H, edges = get_violation_histogram(vs)
                violated_restr = np.count_nonzero(vs)          # how many violations
                num_violations = np.count_nonzero(vs > tol)    # the same 'tol' value is used to compute the number of violations across different restraint kinds...is that too easy?
                vstat[repr(r)] = {
                    'histogram': {
                        'edges': edges.tolist(),
                        'counts': H.tolist()
                    },
                    'violated_restr': violated_restr,
                    'n_violations': num_violations,
                    'n_imposed': n_imposed
                }

            # add violation dictionary to hms file
            h5_create_or_replace_dataset(hms, 'violation_stats', json.dumps(vstat))

            if isinstance(optinfo, dict):
                grp = h5_create_group_if_not_exist(hms, 'opt_info')
                for k, v in optinfo.items():
                    if not isinstance(v, dict):
                        h5_create_or_replace_dataset(grp, k, data=v)
                h5_create_or_replace_dataset(hms, 'opt_info_dict', data=json.dumps(optinfo))

        # double check it has been written correctly
        with HmsFile(ofname, 'r') as hms:
            if not np.all(hms.get_coordinates() == model.getCoordinates()):
                raise RuntimeError('error writing the file %s' % ofname)

        # generat;e the .ready file, which signals to the poller that optimization for that structure has been completed
        readyfile = os.path.join(tmp_dir, '%s.%d.ready' % (step_id, struct_id))
        open(readyfile, 'w').close()  # touch the ready-file
    #-



    def setup_poller(self):

        """ Set up polling function: define coordinate master matrix and a dictionary summarizing statistics from run"""
        
        _hss = HssFile(self.hssfilename, 'r')
        #self._hss = HssFile(self.hssfilename, 'r+')

        self._hss_crd = _hss.coordinates
        _hss.close()

        self._summary_data = {
            'n_imposed': 0.0,
            'n_violations': 0.0,
            'violated_restr': 0.0,
            'histogram': {
                'counts': np.zeros(DEFAULT_HIST_BINS + 1),
                'edges': np.arange(0, DEFAULT_HIST_MAX, DEFAULT_HIST_MAX / DEFAULT_HIST_BINS).tolist() + [DEFAULT_HIST_MAX, np.inf]
            },
            'bystructure': {
                'n_imposed':      np.zeros(self.cfg["model"]["population_size"], dtype=np.float32),
                'n_violations':   np.zeros(self.cfg["model"]["population_size"], dtype=np.float32),
                'violated_restr': np.zeros(self.cfg["model"]["population_size"], dtype=np.float32),
                'total_energies': np.zeros(self.cfg["model"]["population_size"], dtype=np.float32),
                'pair_energies':  np.zeros(self.cfg["model"]["population_size"], dtype=np.float32),
                'bond_energies':  np.zeros(self.cfg["model"]["population_size"], dtype=np.float32),
                'thermo': {}
            },
            'byrestraint': {}
        }
    #-



    def set_structure(self, i):

        """ This is the function run the in the poller, coordinates and statistics are updated for i-th configuration """

        fname = "{}_{}.hms".format(self.tmp_file_prefix, i)
        with HmsFile(os.path.join(self.tmp_dir, fname), 'r') as hms:

            # extract coordinates from .hms file and update master matrix
            crd = hms.get_coordinates()

            # hss and summary_data are globals
            #self._hss.set_struct_crd(i, crd)
            self._hss_crd[:,i,:] = crd

            # collect violation statistics
            try:
                vstat = json.loads(hms['violation_stats'][()])
            except:
                vstat = {}

            n_tot = 0        # number of violations (violation_score > tol)
            n_vio = 0        # total number of restraints
            ex_vio = 0       # number of violated restraints (violation_score > 0)

            hist_tot = np.zeros(DEFAULT_HIST_BINS + 1)
            for k, cstat in vstat.items():
                if k not in self._summary_data['byrestraint']:
                    self._summary_data['byrestraint'][k] = {
                        'histogram': {
                            'counts': np.zeros(DEFAULT_HIST_BINS + 1)
                        },
                        'n_violations': 0,
                        'violated_restr': 0,
                        'n_imposed': 0
                    }

                n_tot += cstat.get('n_imposed', 0)
                n_vio += cstat.get('n_violations', 0)
                ex_vio += cstat.get('violated_restr', 0)

                hist_tot += cstat['histogram']['counts']
                self._summary_data['byrestraint'][k]['n_violations'] += cstat.get('n_violations', 0)
                self._summary_data['byrestraint'][k]['n_imposed'] += cstat.get('n_imposed', 0)
                self._summary_data['byrestraint'][k]['violated_restr'] += cstat.get('violated_restr', 0)
                self._summary_data['byrestraint'][k]['histogram']['counts'] += cstat['histogram']['counts']

            self._summary_data['n_imposed'] += n_tot
            self._summary_data['n_violations'] += n_vio
            self._summary_data['violated_restr'] += ex_vio
            self._summary_data['histogram']['counts'] += hist_tot
            self._summary_data['bystructure']['n_imposed'][i] = n_tot
            self._summary_data['bystructure']['n_violations'][i] = n_vio
            self._summary_data['bystructure']['violated_restr'][i] = ex_vio

            # collect optimization statistics
            try:
                self._summary_data['bystructure']['total_energies'][i] = hms['opt_info']['final-energy'][()]
                self._summary_data['bystructure']['pair_energies'][i] = hms['opt_info']['pair-energy'][()]
                self._summary_data['bystructure']['bond_energies'][i] = hms['opt_info']['bond-energy'][()]
            except KeyError:
                pass

            # detailed optimization stats
            if 'opt_info_dict' in hms:
                infodict = json.loads(hms['opt_info_dict'][()])
                for k, v in infodict['thermo'].items():
                    if k not in self._summary_data['bystructure']['thermo']:
                        self._summary_data['bystructure']['thermo'][k] = np.zeros(self._hss_crd.shape[1])   # LB replaced hss.n_struct
                    self._summary_data['bystructure']['thermo'][k][i] = v
    #-




    def teardown_poller(self):

        """ Teardown poller, after all coodinates and statistics have been updated for the whole population """

        total_violations, total_restraints  = self._summary_data['n_violations'], self._summary_data['n_imposed']
        non_zero_violations = self._summary_data['violated_restr']

        if total_restraints == 0:
            violation_score = 0
        else:
            # percentage of restraint violations
            violation_score = total_violations / total_restraints

        # open HSS population file
        self._hss = HssFile(self.hssfilename, 'r+')     # LB

        # store violation score, all the coordinates and the restraint violation summary into the HSS file
        self._hss.set_violation(violation_score)
        self._hss.set_coordinates(self._hss_crd)   # LB
        h5_create_or_replace_dataset(self._hss, 'summary', data=json.dumps(self._summary_data, default=lambda a: a.tolist()))
        
        # close HSS file
        self._hss.close()
    #-


    def reduce(self):
        """
        Collect all structure coordinates together to assemble a hssFile
        """

        # wait for poller to finish (see also RelaxInit.py script)
        for _ in tqdm(self.file_poller.enumerate(), desc='(REDUCE)'):
            pass

        # read and log details, and save the runtime variables
        with HssFile(self.hssfilename, 'r+') as hss:
            n_struct = hss.nstruct
            n_beads = hss.nbead
            violation_score = log_stats(hss, self.cfg)
            self.cfg['runtime']['violation_score'] = violation_score
            h5_create_or_replace_dataset(hss, 'config_data',
                                         data=json.dumps(self.cfg, default=lambda a: a.tolist()))

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

        logger.info('Repacking...')
        sp = Popen(cmd, stderr=PIPE, stdout=PIPE)
        stdout, stderr = sp.communicate()
        if sp.returncode != 0:
            print(' '.join(cmd))
            print('O:', stdout.decode('utf-8'))
            print('E:', stderr.decode('utf-8'))
            raise RuntimeError('repacking failed. error code: %d' % sp.returncode)
        logger.info('...done!')

        # save the output file with a unique file name if requested (see 'intermediate_name' function below)
        if self.keep_intermediate_structures:
            copyfile(
                self.hssfilename + '.swap',
                self.intermediate_name() + '.hss'
            )

        # finally replace output file
        shutil.move(self.hssfilename + '.swap', self.cfg.get("optimization/structure_output"))
    #-




    def skip(self):
        fn = self.intermediate_name() + '.hss'
        if os.path.isfile(fn):
            with HssFile(fn, 'r') as hss:
                violation_score = log_stats(hss, self.cfg)
                self.cfg['runtime']['violation_score'] = violation_score
    #-



    def intermediate_name(self):

        """ Define unique intermediate name for HSS file associated with this modeling step """
        
        additional_data = []
        
        if "DamID" in self.cfg['runtime']:
            additional_data.append(
                'damid_{:.4f}'.format(
                    self.cfg.get('runtime/DamID/sigma', -1.0)
                )
            )
        if "Hi-C" in self.cfg['runtime']:
            additional_data.append(
                'inter_sigma_{:.4f}'.format(
                    self.cfg['runtime']['Hi-C'].get('inter_sigma', -1.0)
                )
            )

            additional_data.append(
                'intra_sigma_{:.4f}'.format(
                    self.cfg['runtime']['Hi-C'].get('intra_sigma', -1.0)
                )
            )

        if "sprite" in self.cfg['restraints']:
            additional_data.append(
                'sprite_{:.1f}'.format(
                    self.cfg['runtime']['sprite']['volume_fraction'] * 100.0
                )
            )

        if "FISH" in self.cfg['restraints']:
            additional_data .append(
                'FISH_{:.1f}'.format(
                    self.cfg['runtime']['FISH']['tol']
                )
            )

        if 'opt_iter' in self.cfg['runtime']:
            additional_data.append(
                'iter_{}'.format(
                    self.cfg['runtime']['opt_iter']
                )
            )
        additional_data.append(str(self.uid))

        return '.'.join([
            self.cfg.get("optimization/structure_output"),
        ] + additional_data)

    #-


#----- these following functions do not belong to the ModelingStep class

def get_violation_histogram(v, nbins=DEFAULT_HIST_BINS, vmax=1):

    """ Get numpy histogram (H, edges) of violations """

    v = np.array(v)
    over = np.count_nonzero(v > vmax)
    inner = v[v <= vmax]
    H, edges = np.histogram(inner, bins=nbins, range=(0, vmax))
    H = np.concatenate([H, [over]])
    edges = np.concatenate([edges, [np.inf]])
    return H, edges


def log_stats(hss, cfg):

    """ Recapitulate average (per-bead) thermodynamic quantities, and print information to logger to finally conclude this M step; detail violations and break 'em down for each restraint class. Colors are only used when printing to terminal, otherwise color code strings show at the beginning and end of the line to be colored]

        INPUT: hss population file (master file generated by A/M step)
	       cfg configuration file 

	OUTPUT: violation score 
    """

    try:
        n_struct = hss.nstruct
        n_beads  = hss.nbead
        summary  = json.loads(hss['summary'][()])
    except:
        logger.info(bcolors.WARNING + 'No summary data' + bcolors.ENDC)
        return

    total_violations, total_restraints, non_zero_violations = summary['n_violations'], summary['n_imposed'], summary['violated_restr']
  
    logger.info(' \n ')

    # breaking down the different violations to check on the fly
    logger.info(bcolors.OKBLUE     + '          ================= Violation breakdown ==================  ' + bcolors.ENDC)
    for q, ss in summary['byrestraint'].items():
                logger.info(bcolors.OKBLUE + '  Restraint %s: %d (exactly %d) violated out of %d total  ' + bcolors.ENDC, q,
                    ss['n_violations'], ss['violated_restr'],
                    ss['n_imposed']
                )
    logger.info(bcolors.OKBLUE     + '          ========================================================  ' + bcolors.ENDC)

    logger.info(' \n ')

    if total_restraints == 0:
        violation_score = 0
    else:
        violation_score = total_violations / total_restraints

    if 'thermo' in summary['bystructure'] and len(summary['bystructure']['thermo']):
        logger.info(bcolors.HEADER + '          ========== Average thermodynamic info per bead =========  ' + bcolors.ENDC)
        for k, arr in summary['bystructure']['thermo'].items():
            vv = np.array(arr) / n_beads
            logger.info(
                bcolors.HEADER + '  %s:  %f +/- %f  ' + bcolors.ENDC,
                k, np.mean(vv), np.std(vv)
            )

    e_tot = np.array(summary['bystructure']['total_energies']) / n_beads
    e_pair = np.array(summary['bystructure']['pair_energies']) / n_beads
    e_bond = np.array(summary['bystructure']['bond_energies']) / n_beads

    logger.info(
        bcolors.HEADER + '  Average energies per bead:  total: %f +/- %f | pair: %f +/- %f | bond: %f +/- %f  ' + bcolors.ENDC,
        np.mean(e_tot), np.std(e_tot),
        np.mean(e_pair), np.std(e_pair),
        np.mean(e_bond), np.std(e_bond)
    )

    logger.info(bcolors.HEADER +     '          ========================================================  ' + bcolors.ENDC)

    logger.info(' \n')

    logger.info(
        bcolors.OKBLUE + '  Average number of restraints per bead: %f  ' + bcolors.ENDC,
        total_restraints / n_struct / n_beads
    )

    c = bcolors.WARNING if violation_score >= cfg.get('optimization/max_violations') else bcolors.OKGREEN
    logger.info(
        c + '                    Violation score: %d (%d) / %d =  ' + bcolors.BOLD + '  %f  ' + bcolors.ENDC,
        total_violations, non_zero_violations,
        total_restraints,
        violation_score
    )

    logger.info(' \n ')

    return violation_score
