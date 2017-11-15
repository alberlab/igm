from __future__ import division, print_function

import json
import numpy as np


OPT_DEFAULT = [

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
        self.optimization['optimizer_options'] = validate_user_args(self.optimization['optimizer_options'], OPT_DEFAULT)
    #-
    
    
#==
    
def validate_user_args(inargs, defaults):
    args = {k: v for k, v, _, _ in defaults}
    atypes = {k: t for k, _, t, _ in defaults}
    for k, v in inargs.items():
        if k not in args:
            raise ValueError('Keywords argument \'%s\' not recognized.' % k)
        if v is not None:
            args[k] = atypes[k](v)

    if args['write'] == -1:
        args['write'] = args['mdsteps']  # write only final step
    
    return args
        
        
