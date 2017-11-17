from __future__ import division, print_function

import json
import numpy as np
from copy import deepcopy
    
MOD_DEFAULT = [
    ('nucleus_radius', 5000.0, float, 'default nucleus radius'),
    ('nucleus_shape', 'sphere', str, 'default nucleus shape'),
    ('nucleus_axes', (5000.0, 5000.0, 5000.0), tuple, 'default nucleus axes'),
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
    ('ev_start', 0.0, float, 'initial excluded volume factor'),
    ('ev_stop', 0.0, float, 'final excluded volume factor'),
    ('ev_step', 0, int, 'If larger than zero, performs <n> rounds scaling '
                        'excluded volume factors from ev_start to ev_stop'),
]
class Config(object):
    """
    Config is the class which holds all static parameters 
    e.g. # structures, hic file, SPRITE file etc. 
    and dynamic parameters e.g. activation distance and cluster assignment.
    """
    
    def __init__(self, cfgfile, **kwargs):
        
        
        #put static config into config object
        #dynamic config like genome object can be other members
        with open(cfgfile) as f:
            cfg = json.load(f)
        
        self.__dict__.update(cfg)
        self.model = validate_user_args(self.model, MOD_DEFAULT)
        if self.model['nucleus_shape'] == 'sphere':
            self.optimization['optimizer_options']['nucleus_radius'] = self.model['nucleus_radius']
        elif self.model['nucleus_shape'] == 'ellipsoid':
            self.optimization['optimizer_options']['nucleus_radius'] = max(self.model['nucleus_axes'])
        self.optimization['optimizer_options'] = validate_user_args(self.optimization['optimizer_options'], OPT_DEFAULT)
    #-

    def copy(self):
        return deepcopy(self)

    def save(self, fname):
        with open(fname, 'w') as f:
            json.dump(self.__dict__, f)
    
    
#==
    
def validate_user_args(inargs, defaults):
    args = {k: v for k, v, _, _ in defaults}
    atypes = {k: t for k, _, t, _ in defaults}
    for k, v in inargs.items():
        if k not in args:
            raise ValueError('Keywords argument \'%s\' not recognized.' % k)
        if v is not None:
            args[k] = atypes[k](v)
    try:
        if args['write'] == -1:
            args['write'] = args['mdsteps']  # write only final step
    except:
        pass
    return args
        
        
