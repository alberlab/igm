import os
import numpy as np

from igm.model import *
from igm.model.kernel.lammps_model import LammpsModel
from igm.steps.ModelingStep import ModelingStep
from igm.core import Config
from igm.core.job_tracking import StepDB
from alabtools.analysis import HssFile
from igm.restraints import Polymer, Envelope, Steric, HiC, Sprite
from igm.utils import HmsFile

def debug_minimization(cfg, struct_id, rname, **kwargs):
    if not isinstance(cfg, dict):
        cfg = Config(cfg)
    if os.path.isfile(cfg['step_db']):
        db = StepDB(cfg)
        h = db.get_history()
        cfg.update(h[-1])

    cfg['optimization']['optimizer_options'].update(kwargs)
    cfg['optimization']['keep_temporary_files'] = True

    step_id = rname

    hssfilename    = cfg['structure_output']

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
                      cfg['model']['contact_kspring'])
    elif cfg['model']['nucleus_shape'] == 'ellipsoid':
        ev = Envelope(cfg['model']['nucleus_shape'],
                      cfg['model']['nucleus_semiaxes'],
                      cfg['model']['contact_kspring'])
    else:
        raise NotImplementedError('Invalid nucleus shape')
    model.addRestraint(ev)

    #add consecutive polymer restraint
    pp = Polymer(index,
                 cfg['model']['contact_range'],
                 cfg['model']['contact_kspring'])
    model.addRestraint(pp)
    monitored_restraints.append(pp)

    #add Hi-C restraint
    # if "Hi-C" in cfg['restraints']:
    #     dictHiC = cfg['restraints']['Hi-C']
    #     actdist_file = cfg['runtime']['Hi-C']['actdist_file']
    #     contact_range = dictHiC.get( 'contact_range', 2.0 )
    #     k = dictHiC.get( 'contact_kspring', 1.0 )

    #     hic = HiC(actdist_file, contact_range, k)
    #     model.addRestraint(hic)
    #     monitored_restraints.append(hic)

    # if "sprite" in cfg['restraints']:
    #     sprite_opt = cfg['restraints']['sprite']
    #     sprite = Sprite(
    #         sprite_opt['assignment_file'],
    #         sprite_opt['volume_fraction'],
    #         struct_id,
    #         sprite_opt['kspring']
    #     )
    #     model.addRestraint(sprite)
    #     monitored_restraints.append(sprite)

    #========Optimization
    #optimize model
    cfg['runtime']['run_name'] = rname
    model.optimize(cfg)

    tol = cfg.get('violation_tolerance', 0.01)
    lockfile = os.path.join('.', '%s.%d.ready' % (step_id, struct_id) )
    with FileLock(lockfile):
        open(lockfile, 'w').close() # touch the ready-file
        ofname = os.path.join('.', 'mstep_%d.hms' % struct_id)
        with HmsFile(ofname, 'w') as hms:
            hms.saveModel(struct_id, model)

            for r in monitored_restraints:
                hms.saveViolations(r, tolerance=tol)

        # double check it has been written correctly
        with HmsFile(ofname, 'r') as hms:
            if np.all( hms.get_coordinates() == model.getCoordinates() ):
                raise RuntimeError('error writing the file %s' % ofname)
