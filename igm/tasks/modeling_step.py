from __future__ import division, print_function

import numpy as np
import os

from functools import partial
from alabtools.analysis import HssFile, COORD_DTYPE

from ..model import Model, Particle
from ..parallel.ipyparallel_controller import BasicIppController, AdvancedIppController
from ..parallel.parallel_controller import SerialController
from ..core.config import Config
from ..restraints import Polymer, Envelope, Steric 
from ..kernel import lammps
from ..util import resolve_templates

controller_class = {
    u'serial' : SerialController,
    u'ipyparallel' : AdvancedIppController,
    u'ipyparallel_basic' : BasicIppController, 
}

kernel_class = {
    u'lammps' : lammps
}


def modeling_task(struct_id, cfg_file):
    '''
    Serial function to be mapped in parallel. //
    It is a wrapper intended to be used only internally by the parallel map
    function. Will be called as a partial with all the constant variables
    set, except i.
    Resolve the templates, obtains input data,
    runs the minimization routines and finally communicates back results.

    Parameters
    ---------- 
    i : int
        number of the structure 
    cfg_file : str 
        configuration filename for the task
    
    Returns
    -------
    None
    '''
    cfg = Config(cfg_file)
    
    # importing here so it will be called on the parallel workers
    local_vars = resolve_templates(cfg['mstep']['templates'], [struct_id])
    
    model = Model()
    with HssFile(cfg['mstep']['input_hss'], 'r') as f:
        radii = f.radii
        index = f.index
        crd = f['coordinates'][:, struct_id, :][()]

    n_particles = len(crd)
    for i in range(n_particles):
        model.addParticle(crd[i], radii[i], Particle.NORMAL)
        
    ee = Envelope(cfg['model']['nucleus_geometry'])
    model.addRestraint(ee)

    ex = Steric(cfg['model']['evfactor'])
    model.addRestraint(ex)
    
    pp = Polymer(index,
                 cfg['model']['contact_range'],
                 cfg['model']['contact_kspring'])
    model.addRestraint(pp)

    kernel = kernel_class[cfg['mstep']['kernel']]
    info = kernel.optimize(model, cfg['optimization'])
    
    new_crd = np.array([p.pos for p in model.particles], dtype=COORD_DTYPE) 
    np.save(local_vars['crd_out'], new_crd)

    # make sure that is readable
    np.load(local_vars['crd_out'])

    with open(local_vars['info_out'], 'w') as f: 
        for k in kernel.INFO_KEYS:
            if isinstance(info[k], float):
                out_str = '{:9.2f}'.format(info[k])
            elif isinstance(info[k], int):
                out_str = '{:7d}'.format(info[k])
            else:
                out_str = str(info[k])
            f.write(out_str + '\t')

def modeling_step(model, cfg):
    
    with HssFile(cfg['mstep']['input_hss'], 'r') as f:
        radii = f.radii
        index = f.index
        genome = f.genome

    n_struct = cfg['mstep']['n_struct']
    n_beads = cfg['mstep']['n_beads']

    basepath = os.path.join(cfg['mstep']['workdir'], cfg['mstep']['run_name'])
    cfg['mstep']['templates'] = {
        'crd_out' : basepath + '.outcrd.{}.npy',
        'info_out' : basepath + '.info.{}.txt'
    }
    cfg.save(basepath + '.config')

    serial_function = partial(modeling_task, cfg_file=basepath + '.config')
    pctype = cfg['parallel_controller']
    pcopts = cfg['parallel_controller_options']
    controller = controller_class[pctype](**pcopts)
    argument_list = list(range(n_struct))

    controller.map(serial_function, argument_list)

    # write coordinates
    crd_shape = (n_beads, n_struct, 3)
    with HssFile(cfg['mstep']['output_hss'], 'w') as hss:
        hss.index = index
        hss.genome = genome
        hss.radii = radii
        all_crd = hss.create_dataset('coordinates', shape=crd_shape, dtype=COORD_DTYPE)
        for i in range(n_struct):
            local_vars = resolve_templates(cfg['mstep']['templates'], [i])
            crd = np.load(local_vars['crd_out'])
            all_crd[:, i, :] = crd # note that we discard all the positions of added atoms

        # write info
        kernel = kernel_class[cfg['mstep']['kernel']]
        with open(cfg['mstep']['info_out'], 'w') as outf:
            outf.write('#')
            for k in kernel.INFO_KEYS:
                outf.write(k + '\t')
            outf.write('\n')
            for i in range(n_struct):
                local_vars = resolve_templates(cfg['mstep']['templates'], [i])
                with open(local_vars['info_out']) as inf:
                    outf.write(inf.read() + '\n')

    # cleanup
    for i in range(n_struct):
        local_vars = resolve_templates(cfg['mstep']['templates'], [i])
        os.remove(local_vars['crd_out'])
        os.remove(local_vars['info_out'])






