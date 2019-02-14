from __future__ import division, print_function

import json
import hashlib
import numpy as np
import os, os.path
from copy import deepcopy
from six import string_types
from ..utils.files import make_absolute_path

from . import defaults
schema_file = os.path.join(
    os.path.dirname( os.path.abspath(defaults.__file__) ),
    'config_schema.json'
)
schema = json.load(open(schema_file, 'r'))

#OPT_DEFAULT = [
    #('mdsteps', 40000, int, 'Number of MD steps per round'),
    #('timestep', 0.25, float, 'MD timestep'),
    #('tstart', 500.0, float, 'MD initial temperature'),
    #('tstop', 1.0, float, 'MD final temperature'),
    #('damp', 50.0, float, 'MD damp parameter'),
    #('write', -1, int, 'Dump coordinates every <write> MD timesteps'),
    #('thermo', 1000, int, 'Output thermodynamic info every <thermo>'
                          #' MD timesteps'),
    #('max_velocity', 5.0, float, 'Cap particle velocity'),
    #('max_cg_iter', 500, int, 'Maximum # of Conjugate Gradient steps'),
    #('max_cg_eval', 500, int, 'Maximum # of Conjugate Gradient evaluations'),
    #('etol', 1e-4, float, 'Conjugate Gradient energy tolerance'),
    #('ftol', 1e-6, float, 'Conjugate Gradient force tolerance'),
    #('soft_min', 0, int, 'perform a soft minimization of lenght <> timesteps'),
    #('ev_factor', 1.0, float, 'static excluded volume factor'),
    #('ev_start', 0.0, float, 'initial excluded volume factor'),
    #('ev_stop', 0.0, float, 'final excluded volume factor'),
    #('ev_step', 0, int, 'If larger than zero, performs <n> rounds scaling '
                        #'excluded volume factors from ev_start to ev_stop'),
    #('use_gpu', 0, int, 'use gpu options for pair potential'),

#]

#SPRITE_DEFAULT = [

    #('volume_fraction', 0.05, float, 'volume fraction in sprite clusters'),
    #('tmp_dir', 'sprite', str, 'temporary directory'),
    #('assignment_file', 'testassign.h5', str, 'assignment file'),
    #('clusters', 'clusters.h5', str, 'input clusters file'),
    #('batch_size', 100, int, 'batch size for parallel job'),
    #('keep_best', 50, int, 'keep n best candidates for assignment'),
    #('max_chrom_in_cluster', 6, int, 'do not consider cluster with more than n chromosomes'),
    #('radius_kt', 100.0, float, 'the difference in radius of gyration which result in one unit penalization'),
    #('kspring', 100.0, float, 'strength of contacts'),
    #('keep_temporary_files', False, bool, 'whether it keeps temporary files'),

#]

##TODO
#use walk_schema to validate user args
def walk_schema(n, w, group_callback, post_group_callback,
                item_callback):
    if isinstance(w, dict):
        if w.get("role") is not None and "group" in w["role"]:
                group_callback(n, w)
                for x in w:
                    walk_tree(n + '/' + x, w[x],
                              group_callback, post_group_callback,
                              item_callback)
                exit_group_callback(n, w)
                return
        if w.get("dtype") is not None:
            item_callback(n, w)

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
        self['restraints'] = dict()
        self['optimization'] = dict()
        self['optimization']['optimizer_options'] = dict()
        self['parameters'] = dict()

        if cfg is not None:
            if isinstance(cfg, string_types):
                with open(cfg) as f:
                    self.update(json.load(f))
            elif isinstance(cfg, dict):
                self.update(deepcopy(cfg))
            else:
                raise ValueError()

        #self['model'] = validate_user_args(self['model'], MOD_DEFAULT)

        self.igm_parameter_abspath()

        # fix optimizer arguments
        self.preprocess_optimization_arguments()

        # fix sprite arguments
        #self.preprocess_sprite_arguments()

        #runtime should be including all generated parameters
        self['runtime'] = dict()

        for k in self['restraints']:
            self['runtime'][k] = dict()
    #-
    def get(self, keypath, default=None):

        split_path = keypath.split("/")

        try:
            d = self
            for p in split_path:
                d = d[p]
        except KeyError:
            if default is not None:
                return default
            d = schema
            for p in split_path:
                if p in d:
                    d = d[p]
                else:
                    raise KeyError("{} does not exist".format(keypath)) from None
            d = d.get("default")
        return d

    def set(self, keypath, val):

        split_path = keypath.split("/")

        d = self
        for p in split_path[:-1]:
            if p not in d:
                d[p] = dict()
            d = d[p]
        d[split_path[-1]] = val

        return val

    def igm_parameter_abspath(self):
        # if a working directory is not specified, we set it to the
        # current directory.
        self['parameters']['workdir'] = make_absolute_path( self.get("parameters/workdir", os.getcwd()) )

        # We use absolute paths because workers may be running on different
        # directories.
        self['parameters']['tmp_dir'] = make_absolute_path( self.get("parameters/tmp_dir", 'tmp'), self['parameters']['workdir'] )
        self['parameters']['log']     = make_absolute_path( self.get("parameters/log", 'igm.log'), self['parameters']['workdir'] )
        self['optimization']['structure_output'] = make_absolute_path( self['optimization']['structure_output'], self['parameters']['workdir'])

    def preprocess_optimization_arguments(self):

        #if self['model']['nucleus_shape'] == 'sphere':
            #self['optimization']['optimizer_options']['nucleus_radius'] = self['model']['nucleus_radius']
        #elif self['model']['nucleus_shape'] == 'ellipsoid':
            #self['optimization']['optimizer_options']['nucleus_radius'] = max(self['model']['nucleus_semiaxes'])

        #if 'ev_factor' not in self['optimization']['optimizer_options']:
            #self['optimization']['optimizer_options']['ev_factor'] = self['model']['evfactor']

        #self['optimization']['optimizer_options'] = validate_user_args(self['optimization']['optimizer_options'], OPT_DEFAULT)
        opt = self['optimization']['optimizer_options']
        opt['ev_step'] = 0
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


