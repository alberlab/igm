from __future__ import division, print_function

import json
import hashlib
import numpy as np
import os, os.path
from copy import deepcopy
from six import string_types
from ..utils.files import make_absolute_path

MOD_DEFAULT = [

    ('nucleus_radius', 5000.0, float, 'default nucleus radius'),
    ('nucleus_shape', 'sphere', str, 'default nucleus shape'),
    ('nucleus_kspring', 1.0, float, 'default nucleus elastic constant'),
    ('nucleus_semiaxes', (5000.0, 5000.0, 5000.0), tuple, 'default nucleus axes'),
    ('occupancy', 0.2, float, 'default volume occupancy (from 0.0 to 1.0)'),
    ('contact_range', 2.0, float, 'Consecutive contact range (in radius units)'),
    ('contact_kspring', 1.0, float, 'Consecutive contact spring constant'),
    ('evfactor', 1.0, float, 'Scale excluded volume by this factor'),

]

OPT_DEFAULT = [

    ('nucleus_radius', 5000.0, float, 'default nucleus radius'),

    ('out', 'out.lammpstrj', str, 'Temporary lammps trajectory file name'),
    ('data', 'input.data', str, 'Temporary lammmps input data file name'),
    ('lmp', 'minimize.lam', str, 'Temporary lammps script file name'),

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
    ('max_neigh', 2000, int, 'Maximum numbers of neighbors per particle'),
    ('max_cg_iter', 500, int, 'Maximum # of Conjugate Gradient steps'),
    ('max_cg_eval', 500, int, 'Maximum # of Conjugate Gradient evaluations'),
    ('etol', 1e-4, float, 'Conjugate Gradient energy tolerance'),
    ('ftol', 1e-6, float, 'Conjugate Gradient force tolerance'),
    ('soft_min', 0, int, 'perform a soft minimization of lenght <> timesteps'),
    ('ev_factor', 1.0, float, 'static excluded volume factor'),
    ('ev_start', 0.0, float, 'initial excluded volume factor'),
    ('ev_stop', 0.0, float, 'final excluded volume factor'),
    ('ev_step', 0, int, 'If larger than zero, performs <n> rounds scaling '
                        'excluded volume factors from ev_start to ev_stop'),
    ('use_gpu', 0, int, 'use gpu options for pair potential'),

]

SPRITE_DEFAULT = [

    ('volume_fraction', 0.05, float, 'volume fraction in sprite clusters'),
    ('tmp_dir', 'sprite', str, 'temporary directory'),
    ('assignment_file', 'testassign.h5', str, 'assignment file'),
    ('clusters', 'clusters.h5', str, 'input clusters file'),
    ('batch_size', 100, int, 'batch size for parallel job'),
    ('keep_best', 50, int, 'keep n best candidates for assignment'),
    ('max_chrom_in_cluster', 6, int, 'do not consider cluster with more than n chromosomes'),
    ('radius_kt', 100.0, float, 'the difference in radius of gyration which result in one unit penalization'),
    ('kspring', 100.0, float, 'strength of contacts'),
    ('keep_temporary_files', False, bool, 'whether it keeps temporary files'),

]



class Config(dict):
    """
    Config is the class which holds all static parameters
    e.g. # structures, hic file, SPRITE file etc.
    and dynamic parameters e.g. activation distance and cluster assignment.
    """

    def __init__(self, cfg=None):

        #put static config into config object
        #dynamic config like genome object can be other members
        self['model'] = dict()
        self['model']['restraints'] = dict()
        self['optimization'] = dict()
        self['optimization']['optimizer_options'] = dict()

        if cfg is not None:
            if isinstance(cfg, string_types):
                with open(cfg) as f:
                    self.update(json.load(f))
            elif isinstance(cfg, dict):
                self.update(deepcopy(cfg))
            else:
                raise ValueError()

        self['model'] = validate_user_args(self['model'], MOD_DEFAULT)

        # if a working directory is not specified, we set it to the
        # current directory.
        self['workdir'] = make_absolute_path( self.get('workdir', os.getcwd()) )

        # We use absolute paths because workers may be running on different
        # directories.
        self['tmp_dir'] = make_absolute_path( self.get('tmp_dir', 'tmp'), self['workdir'] )
        self['structure_output'] = make_absolute_path( self['structure_output'], self['workdir'])

        # fix optimizer arguments
        self.preprocess_optimization_arguments()

        # fix sprite arguments
        self.preprocess_sprite_arguments()

        #runtime should be including all generated parameters
        self['runtime'] = dict()

        for k in self['restraints']:
            self['runtime'][k] = dict()
    #-

    def preprocess_optimization_arguments(self):

        if self['model']['nucleus_shape'] == 'sphere':
            self['optimization']['optimizer_options']['nucleus_radius'] = self['model']['nucleus_radius']
        elif self['model']['nucleus_shape'] == 'ellipsoid':
            self['optimization']['optimizer_options']['nucleus_radius'] = max(self['model']['nucleus_semiaxes'])

        if 'ev_factor' not in self['optimization']['optimizer_options']:
            self['optimization']['optimizer_options']['ev_factor'] = self['model']['evfactor']

        self['optimization']['optimizer_options'] = validate_user_args(self['optimization']['optimizer_options'], OPT_DEFAULT)
        opt = self['optimization']['optimizer_options']
        try:
            if opt['write'] == -1:
                opt['write'] = opt['mdsteps']  # write only final step
        except:
            pass

    def preprocess_sprite_arguments(self):
        if 'sprite' not in self['restraints']:
            return
        self['restraints']['sprite'] = validate_user_args(self['restraints']['sprite'], SPRITE_DEFAULT)
        opt = self['restraints']['sprite']
        opt['tmp_dir'] = make_absolute_path(opt['tmp_dir'], self['tmp_dir'])
        opt['assignment_file'] = make_absolute_path(opt['assignment_file'], opt['tmp_dir'])
        opt['clusters'] = make_absolute_path(opt['clusters'], self['workdir'])

    def static_hash(self):
        '''
        Returns a hash for the static run options
        '''
        return hashlib.md5(
            json.dumps({
                self[k] for k in self if k != 'runtime'
            }).encode()
        ).hexdigest()

    def runtime_hash(self):
        '''
        Returns a hash for the current configuration,
        including runtime status.
        '''
        return hashlib.md5(
            json.dumps(self).encode()
        ).hexdigest()

    def save(self, fname):
        with open(fname, 'w') as f:
            json.dump(self, f, indent=4)

#==

def validate_user_args(inargs, defaults, strict=True):
    args = {k: v for k, v, _, _ in defaults}
    atypes = {k: t for k, _, t, _ in defaults}
    for k, v in inargs.items():
        if k not in args and strict is True:
            raise ValueError('Keywords argument \'%s\' not recognized.' % k)
        if v is not None:
            args[k] = atypes[k](v)

    return args


