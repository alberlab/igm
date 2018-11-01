import json
import os, os.path

import igm.core.defaults


schema_file = os.path.join(
    os.path.dirname( os.path.abspath(igm.core.defaults.__file__) ),
    'config_schema.json'
)
schema = json.load(open(schema_file, 'r'))

def set_item(d, path, val):
    if len(path) == 1:
        d[path[0]] = val
    else:
        if path[0] not in d:
            d[path[0]] = dict()
        set_item(d[path[0]], path[1:], val)

def get_item(d, path):
    if len(path) == 1:
        return d[ path[0] ]
    return get_item(d[ path[0] ], path[1:])

def split_path(path, sep='__'):
    return path.split(sep)

def type_or_json(vtype, val):
    from six import raise_from
    if isinstance(val, vtype):
        return val
    if not isinstance(val, str):
        raise ValueError()
    try:
        v = json.loads(val)
        return v
    except json.JSONDecodeError:
        raise_from(ValueError(), None)
    if isinstance(val, vtype):
        return val
    raise ValueError()

def validate_value(value, dtype, subdtype=None, alen=None):
    if dtype == 'int':
        return int(value)
    elif dtype == 'float':
        return float(value)
    elif dtype == 'bool':
        return bool(value)
    elif dtype == 'list':
        sval = type_or_json(list, value)
        for i in range(len(sval)):
            if subdtype == 'list':
                if not isinstance(sval[i], list):
                    raise ValueError()
            else:
                sval[i] = validate_value(sval[i], subdtype)
        return sval
    elif dtype == 'array':
        sval = type_or_json(list, value)
        if len(sval) != alen:
            raise ValueError('array length does not match')
        for i in range(len(sval)):
            sval[i] = validate_value(sval[i], subdtype)
        return sval
    elif dtype == 'dict':
        return type_or_json(dict, value)
    elif dtype == 'str' or  dtype == 'path' or dtype == 'path-dir':
        return(str(value))
    else:
        raise ValueError()

def save_cfg(data, folder='.'):
    warnings = []
    errors = []
    cfg = {}
    for path, value in data.items():

        try:
            sitem = get_item(schema, split_path(path))
        except KeyError:
            set_item(cfg, split_path(path), value)
            warnings.append('key "%s" not in schema' % path.replace('__', ' > '))
            continue

        if sitem.get('blank', False):
            if value is None or (isinstance(value, str) and value.strip() == ''):
                continue

        dtypes = sitem['dtype']

        if not isinstance(dtypes, list):
            dtypes = [dtypes]

        sval = None
        for dtype in dtypes:
            try:
                sval = validate_value(value, dtype,
                    subdtype=sitem.get('subdtype'),
                    alen=sitem.get('length'))
                break
            except ValueError:
                pass
        if sval is None:
            errors.append('%s: invalid data "%s". Valid data type are "%s" ' % (
                path.replace('__', ' > '), value, dtypes))
            continue

        if dtype in ['path', 'path-dir', 'str'] and not sitem.get('required', False):
            if sval.strip() == "":
                continue

        if dtype == 'path' and sitem.get('role', '') == 'input':
            if not os.path.isfile(sval):
                warnings.append('%s: cannot find input file "%s"' % (path.replace('__', ' > '), sval))

        if sitem.get('allowed_values') is not None:
            if sval not in sitem['allowed_values']:
                errors.append('%s: invalid value "%s". Valid values are "%s" ' % (
                    path.replace('__', ' > '), value, sitem['allowed_values']))
                continue

        set_item(cfg, split_path(path), sval)

    r = {'errors': errors, 'warnings': warnings}
    if len(errors):
        r['status'] = 'failed'
        r['cfg'] = None
        return r
    else:
        cfgf = os.path.join(folder, 'igm-config.json')
        with open(cfgf, 'w') as f:
            json.dump(cfg, f, indent=4)
        r['status'] = 'ok'
        r['cfg'] = cfg
        return r
