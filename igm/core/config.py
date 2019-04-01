from __future__ import division, print_function

import json
import hashlib
from configparser import ConfigParser
import os, os.path
from copy import deepcopy
from six import string_types, raise_from
from ..utils.files import make_absolute_path

from . import defaults
schema_file = os.path.join(
    os.path.dirname(os.path.abspath(defaults.__file__)),
    'config_schema.json'
)
schema = json.load(open(schema_file, 'r'))

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

def make_default_dict(group):
    out = dict()
    for k, item in group.items():
        if not isinstance(item, dict):
            continue
        if ('role' in item) and (item['role'] == 'group'):
            out[k] = make_default_dict(group[k])
        elif ('role' in item) and (item['role'] in ['optional-group', 'optional_input']):
            pass
        else:
            try:
                out[k] = item['default']
            except KeyError:
                pass
    return out

RAISE = object()

class Config(dict):
    """
    Config is the class which holds all static parameters
    e.g. # structures, hic file, SPRITE file etc.
    and dynamic parameters e.g. activation distance and cluster assignment.
    """
    RAISE = RAISE

    def __init__(self, cfg=None):

        super(Config, self).__init__()

        # create default dictionary
        self.update(make_default_dict(schema))

        # runtime is a required key, and is home to all the generated parameters
        self['runtime'] = dict()

        # update with user files in ${HOME}/.igm
        user_defaults_file = os.environ['HOME'] + '/.igm/user_defaults.cfg'
        if os.path.isfile(user_defaults_file):
            user_defaults = ConfigParser()
            user_defaults.read(user_defaults_file)
            for s in user_defaults.sections() + ['DEFAULT']:
                for k in user_defaults[s]:
                    self.set(k, user_defaults[s][k])

        # update the default dictionary with the provided file
        if cfg is not None:
            if isinstance(cfg, string_types):
                with open(cfg) as f:
                    self.update(json.load(f))
            elif isinstance(cfg, dict):
                self.update(deepcopy(cfg))
            else:
                raise TypeError('Config argument needs to be a path or a dictionary.')

        self.igm_parameter_abspath()

        # fix optimizer arguments
        self.preprocess_optimization_arguments()

        for k in self['restraints']:
            if k not in self['runtime']:
                self['runtime'][k] = dict()

    def get(self, keypath, default=RAISE):
        split_path = keypath.split("/")

        try:
            d = self
            for p in split_path:
                d = d[p]
        except KeyError:
            if default is not RAISE:
                return default
            d = schema
            for p in split_path:
                if p in d:
                    d = d[p]
                else:
                    raise_from(KeyError("{} does not exist".format(keypath)), None)
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


