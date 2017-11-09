
#!/usr/bin/env python

# Copyright (C) 2016 University of Southern California and
#                        Guido Polles
# 
# Authors: Guido Polles
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

'''
The **lammps** module provides function to interface
with LAMMPS in order to perform the modeling
of the chromosome structures.

To perform a full modeling step, you may
want to check out the higher level wrappers
in the wrappers module.
'''


from __future__ import print_function, division
import os
import os.path
import math
import numpy as np
from io import StringIO
from itertools import groupby

from subprocess import Popen, PIPE

from .lammps_io import get_info_from_log, get_last_frame
from .lammps_model import *

__author__  = "Guido Polles"
__license__ = "GPL"
__version__ = "0.0.1"
__email__   = "polles@usc.edu"


INFO_KEYS = ['final-energy', 'pair-energy', 'bond-energy', 'md-time', 'n_restr', 'n_hic_restr']


ARG_DEFAULT = [
    ('nucleus_radius', 5000.0, float, 'default nucleus radius'),
    ('occupancy', 0.2, float, 'default volume occupancy (from 0.0 to 1.0)'),
    ('sprite_size', 5.0, float, 'inverse of volume occupancy'),
    ('sprite_kspring', 1.0, float, 'SPRITE spring constant'),
    ('out', 'out.lammpstrj', str, 'Temporary lammps trajectory file name'),
    ('data', 'input.data', str, 'Temporary lammmps input data file name'), 
    ('lmp', 'minimize.lam', str, 'Temporary lammps script file name'), 
    ('contact_kspring', 1.0, float, 'HiC contacts spring constant'),
    ('contact_range', 2.0, float, 'HiC contact range (in radius units)'),
    ('fish_type', 'rRpP', str, 'FISH restraints type'),
    ('fish_kspring', 1.0, float, 'FISH restraints spring constant'),
    ('fish_tol', 0.0, float, 'FISH restraints tolerance (nm)'),
    ('damid_kspring', 1.0, float, 'lamina DamID restr. spring constant'),
    ('damid_tol', 50.0, float, 'lamina DamID restraint tolerance (nm)'),
    ('mdsteps', 20000, int, 'Number of MD steps per round'),
    ('timestep', 0.25, float, 'MD timestep'),
    ('tstart', 20.0, float, 'MD initial temperature'),
    ('tstop', 1.0, float, 'MD final temperature'),
    ('damp', 50.0, float, 'MD damp parameter'),
    ('seed', np.random.randint(100000000), int, 'RNG seed'),
    ('write', -1, int, 'Dump coordinates every <write> MD timesteps'),
    ('thermo', 1000, int, 'Output thermodynamic info every <thermo>' 
                          ' MD timesteps'),
    ('max_velocity', 5.0, float, 'Cap particle velocity'),
    ('evfactor', 1.0, float, 'Scale excluded volume by this factor'),
    ('max_neigh', 2000, int, 'Maximum numbers of neighbors per particle'),
    ('max_cg_iter', 500, int, 'Maximum # of Conjugate Gradient steps'),
    ('max_cg_eval', 500, int, 'Maximum # of Conjugate Gradient evaluations'),
    ('etol', 1e-4, float, 'Conjugate Gradient energy tolerance'),
    ('ftol', 1e-6, float, 'Conjugate Gradient force tolerance'),
    ('soft_min', 0, int, 'perform a soft minimization of lenght <> timesteps'),
    ('ev_start', 0.0, float, 'initial excluded volume factor'),
    ('ev_stop', 0.0, float, 'final excluded volume factor'),
    ('ev_step', 0, int, 'If larger than zero, performs <n> rounds scaling '
                        'excluded volume factors from ev_start to ev_stop'),
]


def validate_user_args(kwargs):
    args = {k: v for k, v, _, _ in ARG_DEFAULT}
    atypes = {k: t for k, _, t, _ in ARG_DEFAULT}
    for k, v in kwargs.items():
        if k not in args:
            raise ValueError('Keywords argument \'%s\' not recognized.' % k)
        if v is not None:
            args[k] = atypes[k](v)

    if args['write'] == -1:
        args['write'] = args['mdsteps']  # write only final step
    
    return args

def create_lammps_data(model, user_args):
    
    n_atom_types = len(model.atom_types)
    n_bonds = len(model.bonds)
    n_bondtypes = len(model.bond_types)
    n_atoms = len(model.atoms)

    with open(user_args['data'], 'w') as f:

        print('LAMMPS input\n', file=f)

        print(n_atoms, 'atoms\n', file=f)
        print(n_atom_types, 'atom types\n', file=f)
        print(n_bondtypes, 'bond types\n', file=f)
        print(n_bonds, 'bonds\n', file=f)

        # keeping some free space to be sure
        boxdim = user_args['nucleus_radius']*1.2
        print('-{} {} xlo xhi\n'.format(boxdim, boxdim),
              '-{} {} ylo yhi\n'.format(boxdim, boxdim),
              '-{} {} zlo zhi'.format(boxdim, boxdim), file=f)

        print('\nAtoms\n', file=f)
        # index, molecule, atom type, x y z.
        for atom in model.atoms:
            print(atom, file=f)
        
        # bonds
        # Harmonic Upper Bond Coefficients are one for each bond type
        # and coded as:
        #   Bond_type_id kspring activation_distance
        # Each bond is coded as:
        #   Bond_id Bond_type_id ibead jbead

        if n_bonds > 0:
            print('\nBond Coeffs\n', file=f)
            for bt in model.bond_types:
                print(bt, file=f)

            print('\nBonds\n', file=f)
            for bond in model.bonds:
                print(bond, file=f)

        # Excluded volume coefficients
        atom_types = list(model.atom_types.values())

        print('\nPairIJ Coeffs\n', file=f)
        for i in range(len(atom_types)):
            a1 = atom_types[i]
            for j in range(i, len(atom_types)):
                a2 = atom_types[j]
                id1 = min(a1.id+1, a2.id+1)
                id2 = max(a1.id+1, a2.id+1)
                if (a1.atom_category == AtomType.BEAD and
                    a2.atom_category == AtomType.BEAD):
                    ri = a1.radius
                    rj = a2.radius
                    dc = (ri + rj)
                    A = (dc/math.pi)**2
                    #sigma = dc / 1.1224 #(2**(1.0/6.0))
                    #print(i+1, user_args['evfactor'], sigma, dc, file=f)
                    
                    print(id1, id2, A*user_args['evfactor'], dc, file=f)
                else:
                    print(id1, id2, 0.0, 0.0, file=f)
        
def create_lammps_script(model, user_args):
    maxrad = max([at.radius for at in model.atom_types if 
                  at.atom_category == AtomType.BEAD])

    with open(user_args['lmp'], 'w') as f:
        print('units                 lj', file=f)
        print('atom_style            bond', file=f)
        print('bond_style  hybrid',
              'harmonic_upper_bound',
              'harmonic_lower_bound', file=f)
        print('boundary              f f f', file=f)

        # Needed to avoid calculation of 3 neighs and 4 neighs
        print('special_bonds lj/coul 1.0 1.0 1.0', file=f)


        # excluded volume
        print('pair_style soft', 2.0 * maxrad, file=f)  # global cutoff

        print('read_data', user_args['data'], file=f)
        print('mass * 1.0', file=f)

        # groups atom types by atom_category
        sortedlist = list(sorted(model.atom_types, key=lambda x: x.atom_category))
        groupedlist = {k: list(v) for k, v in groupby(sortedlist, 
                                                key=lambda x: x.atom_category)}

        bead_types = [str(x) for x in groupedlist[AtomType.BEAD]]
        dummy_types = [str(x) for x in groupedlist.get(AtomType.FIXED_DUMMY, [])]
        centroid_types = [str(x) for x in groupedlist.get(AtomType.CLUSTER_CENTROID, [])]
        print('group beads type', ' '.join(bead_types), file=f)

        if dummy_types:
            print('group dummy type', ' '.join(dummy_types) , file=f)
            print('neigh_modify exclude group dummy all', file=f)
        if centroid_types:
            print('group centroid type', ' '.join(centroid_types), file=f)
            print('neigh_modify exclude group centroid all', file=f)

        print('group nonfixed type', ' '.join(centroid_types
                                            + bead_types), file=f)

        print('neighbor', maxrad, 'bin', file=f)  # skin size
        print('neigh_modify every 1 check yes', file=f)
        print('neigh_modify one', user_args['max_neigh'],
              'page', 20 * user_args['max_neigh'], file=f)

        
        # Freeze dummy atom
        if dummy_types:
            print('fix 1 dummy setforce 0.0 0.0 0.0', file=f)

        # Integration
        # select the integrator
        print('fix 2 nonfixed nve/limit', user_args['max_velocity'], file=f)
        # Impose a thermostat - Tstart Tstop tau_decorr seed
        print('fix 3 nonfixed langevin', user_args['tstart'], user_args['tstop'],
              user_args['damp'], user_args['seed'], file=f)
        print('timestep', user_args['timestep'], file=f)

        # Region
        # print('region mySphere sphere 0.0 0.0 0.0',
        #       user_args['nucleus_radius'] + 2 * maxrad, file=f)
        # print('fix wall beads wall/region mySphere harmonic 10.0 1.0 ',
        #       2 * maxrad, file=f)

        #print('pair_modify shift yes mix arithmetic', file=f)

        # outputs:
        print('dump   crd_dump all custom',
              user_args['write'],
              user_args['out'],
              'id type x y z fx fy fz', file=f)

        # Thermodynamic info style for output
        print('thermo_style custom step temp epair ebond', file=f)
        print('thermo_modify norm no', file=f)
        print('thermo', user_args['thermo'], file=f)

        # ramp excluded volume
        if user_args['ev_step'] > 1:
            ev_val_step = float(user_args['ev_stop'] - user_args['ev_start']) / (user_args['ev_step'] - 1)
            for step in range(user_args['ev_step']):
                print('variable evprefactor equal ',
                      user_args['ev_start'] + ev_val_step*step,
                      file=f)
                #'ramp(%f,%f)' % (user_args['ev_start'], user_args['ev_stop']),
                print('fix %d all adapt 0',
                      'pair soft a * * v_evprefactor scale yes',
                      'reset yes' % 4 + step, file=f)
                print('run', user_args['mdsteps'], file=f)
                print('unfix 4', file=f)
        else:
        # Run MD
            print('run', user_args['mdsteps'], file=f)

        # Run CG
        print('min_style cg', file=f)
        print('minimize', user_args['etol'], user_args['ftol'],
              user_args['max_cg_iter'], user_args['max_cg_eval'], file=f)


def _check_violations(model, crd, i, tol=0.05):
    violations = []
    for bond in model.bonds:
        rv = bond.get_relative_violation(crd)
        if rv > tol:
            bt = bond.bond_type
            violations.append(np.array([i, bond.restraint_type, 
                                       bond.i.id, bond.j.id,
                                       bt.style_id, rv], dtype=np.float32))
    return np.array(violations)

def optimize(model, cfg):
    '''
    Lammps interface for minimization.
    
    It first creates input and data files for lammps, then
    runs the lammps executable in a process (using subprocess.Popen).

    When the program returns, it parses the output and returns the 
    new coordinates, along informations on the run and on violations.

    The files created are 
    - input file: `tmp_files_dir`/`run_name`.lam
    - data file: `tmp_files_dir`/`run_name`.input
    - trajectory file: `tmp_files_dir`/`run_name`.lammpstrj

    The function tries to remove the temporary files after the run, both in 
    case of failure and success (unless `keep_temporary_files` is set to 
    `False`). If the interpreter is killed without being able to catch 
    exceptions (for example because of a walltime limit) some files could be 
    left behind.

    Parameters
    ----------
    crd : numpy.ndarray 
        Initial coordinates (n_beads x 3 array).
    radii : numpy.ndarray
        Radius for each particle in the system.
    index : `alabtools.Index`
        Index for the system.
    run_name : str
        Name of the run. It determines only the name of temporary files.
    tmp_files_dir : str
        Location of temporary files. Needs writing permissions. The default 
        value, /dev/shm, is usually a in-memory file system, useful to 
        share data between processes without the overhead of actually 
        writing to a physical disk.
    check_violations : bool
        Performs a check on the violations of the assigned bonds. If set 
        to `False`, the check is skipped and the violation output will be 
        an empty list.
    keep_temporary_files : bool
        If set to `True`, does not try to remove the temporary files 
        generated by the run.
    \*\*kwargs : dict 
        Optional keyword arguments for minimization. 
        See docs for `lammps.generate_input`.

    Returns
    -------
    new_crd : numpy ndarray 
        Coordinates after minimization.
    info : dict 
        Dictionary with summarized info for the run, as returned 
        by `lammps.get_info_from_log`.
    violations : list
        List of violations. If the `check_violations` parameter is set 
        to `False`, returns an empty list.

    Raises
    ------
    RuntimeError 
        If the lammps executable return code is different from 0, it raises 
        a RuntimeError with the contents of the standard error.
    '''

    tmp_files_dir = cfg['tmp_files_dir']
    run_name = cfg['run_name']
    keep_temporary_files = cfg['keep_temporary_files'] 
    lammps_executable = cfg['lammps_executable']
    run_opts = validate_user_args(cfg['optimizer_options'])

    data_fname = os.path.join(tmp_files_dir, run_name + '.data')
    script_fname = os.path.join(tmp_files_dir, run_name + '.lam')
    traj_fname = os.path.join(tmp_files_dir, run_name + '.lammpstrj')

    try:

        # prepare input
        io_opts = {'out': traj_fname, 'data': data_fname, 'lmp': script_fname}
        run_opts.update(io_opts)

        m = LammpsModel(model)

        create_lammps_data(m, run_opts)
        create_lammps_script(m, run_opts)

        # run the lammps minimization
        with open(script_fname, 'r') as lamfile:
            proc = Popen([lammps_executable, '-log', '/dev/null'],
                         stdin=lamfile,
                         stdout=PIPE,
                         stderr=PIPE)
            output, error = proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError('LAMMPS exited with non-zero exit code: %d\nStandard Error:\n%s\n', 
                               proc.returncode, 
                               error)

        # get results
        info = get_info_from_log(StringIO(unicode(output)))
        
        with open(traj_fname, 'r') as fd:
            new_crd = get_last_frame(fd)

        for i, p in enumerate(model.particles):
            p.pos = new_crd[m.imap[i]]

        if not keep_temporary_files:
            if os.path.isfile(data_fname):
                os.remove(data_fname)
            if os.path.isfile(script_fname):
                os.remove(script_fname)
            if os.path.isfile(traj_fname):
                os.remove(traj_fname)

    except:
        if not keep_temporary_files:
            if os.path.isfile(data_fname):
                os.remove(data_fname)
            if os.path.isfile(script_fname):
                os.remove(script_fname)
            if os.path.isfile(traj_fname):
                os.remove(traj_fname)
        raise


    return info

