#!/usr/bin/env python
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
import tornado.ioloop
import tornado.web
import os.path
import sys
import json
import uuid
import glob
import subprocess
import traceback
import igm.core.defaults
from igm.core.config import Config
from igm.core.job_tracking import StepDB
from tornado import template
template_dir = os.path.join( os.path.dirname( os.path.abspath(__file__) ),  'templates' )
loader = template.Loader(template_dir)

def render(template, data):
    return loader.load(template).generate(**data)

#from igm.ui.views import history, config_form, config_form_process



if len(sys.argv) > 1:
    cfg = sys.argv[1]
else:
    cfg = None

if len(sys.argv)>2:
    port = int(sys.argv[2])
else:
    port = 43254

cwd = os.getcwd()
schema_file = os.path.join(
    os.path.dirname( os.path.abspath(igm.core.defaults.__file__) ),
    'config_schema.json'
)
schema = json.load(open(schema_file, 'r'))

# create a secure token
# token = str(uuid.uuid4()).replace('-', '')
# secret = str(uuid.uuid4()).replace('-', '')
token = 'd188f1a53ba548d8a5c87cd84063a842'
secret = 'xxxxx'

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

def save_cfg(data):
    warnings = []
    errors = []
    cfg = {}
    for path, value in data.items():

        try:
            sitem = get_item(schema, split_path(path))
        except KeyError:
            set_item(cfg, split_path(path), value)
            warnings.append('key "%s" not in schema' % path)
            continue

        if sitem.get('blank', False):
            if value is None or value == '':
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
                path, value, dtypes))
            continue

        if dtype in ['path', 'path-dir', 'str'] and not sitem.get('required', False):
            if sval.strip() == "":
                continue

        if dtype == 'path' and sitem.get('role', '') == 'input':
            if not os.path.isfile(sval):
                warnings.append('%s: cannot find input file "%s"' % (path, sval))

        if sitem.get('allowed_values') is not None:
            if sval not in sitem['allowed_values']:
                errors.append('%s: invalid value "%s". Valid values are "%s" ' % (
                    path, value, sitem['allowed_values']))
                continue

        set_item(cfg, split_path(path), sval)

    r = {'errors': errors, 'warnings': warnings}
    if len(errors):
        r['status'] = 'failed'
        r['cfg'] = None
        return r
    else:
        with open('igm-config.json', 'w') as f:
            json.dump(cfg, f, indent=4)
        r['status'] = 'ok'
        r['cfg'] = cfg
        return r

def history():
    cfg = json.load(open('igm-config.json', 'r'))
    db = StepDB(cfg, mode='r')
    h = db.get_history()
    # to avoid excessive data exchange
    for i in range(len(h)):
        del h[i]['cfg']
    return h

def readlog(logfile):
    # read in binary mode, so will keep carriage returns
    lines = open(logfile, 'rb').readlines()
    # remove all the unnecessary carriage returns and reassemble
    log = '\n'.join([ l.decode('utf-8').split('\r')[-1].strip('\n') for l in lines ])
    return log

def igm_is_running():
    if os.path.isfile('.igm-pid.txt'):
        pid = int(open('.igm-pid.txt').read())
        try:
            # sending a 0 signal fails if the process does not exist
            # does nothing otherwise
            os.kill(pid, 0)
            status = 'yes'
        except OSError:
            # In this case the machine running the server
            # may be different from the machine running the igm script,
            # or something exploded before calling the atexit functions
            status = 'maybe'
    else:
        status = 'no'
    return status

def kill_igm():
    if os.path.isfile('.igm-pid.txt'):
        pid = int(open('.igm-pid.txt').read())
        os.kill(pid, 9)
        os.remove('.igm-pid.txt')

class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        return self.get_secure_cookie("user")

class AjaxHandler(BaseHandler):
    def post(self):

        if not self.current_user:
            return

        reqdata = json.loads(self.get_argument('data'))
        if reqdata['request'] == 'navigate':
            self.write(
                json.dumps(
                    list_directory(reqdata['path'], cwd)
                )
            )
        if reqdata['request'] == 'get_tree':
            self.write(
                { root.replace(cwd, '') : {'dirs': dirs, 'files': files}
                for root, dirs, files in os.walk(cwd) }
            )
        if reqdata['request'] == 'save_cfg':
            try:
                r = save_cfg(reqdata['cfgdata'])
                self.write(json.dumps(r))
            except:
                self.write({'status': 'failed', 'reason': traceback.format_exc()})

        if reqdata['request'] == 'get_cfg':
            try:
                current_cfg = json.load(open('igm-config.json'))
            except:
                current_cfg = None;
            self.write(json.dumps(current_cfg))

        if reqdata['request'] == 'get_log':
            try:
                # try to read the real-time log with the statusbar first, the
                # boring old one if it cannot find it
                if os.path.isfile('igm-log.txt'):
                    log = readlog('igm-log.txt')
                elif os.path.isfile('igm-config.json'):
                    current_cfg = json.load(open('igm-config.json'))
                    logfile = current_cfg['log']
                    log = readlog(logfile)
                else:
                    log = None
            except:
                log = None;
            self.write(json.dumps({'log' : log}))

        if reqdata['request'] == 'is_running':
            try:
                status = igm_is_running()
            except:
                status = 'fail';
            self.write(json.dumps({'status' : status}))

        if reqdata['request'] == 'get_history':
            try:
                h = history()
            except:
                h = []
            self.write(json.dumps({'history' : h}))

        if reqdata['request'] == 'start_pipeline':
            try:
                if igm_is_running() == 'yes':
                    raise RuntimeError('IGM is already running')
                import subprocess
                subprocess.Popen(['nohup igm-run igm-config.json &> igm-log.txt < /dev/null &'], shell=True)
                out = 'ok'
            except:
                out = traceback.format_exc()
            self.write(json.dumps({'status' : out}))

        if reqdata['request'] == 'kill_pipeline':
            try:
                kill_igm()
                out = 'ok'
            except:
                out = traceback.format_exc()
            self.write(json.dumps({'status' : out}))


class MainHandler(BaseHandler):

    def get(self):
        if not self.current_user:
            if self.get_argument("q") == token:
                self.set_secure_cookie("user", self.get_argument("q"))
            else:
                self.redirect("/login")
                return

        if os.path.isfile('igm-config.json'):
            current_cfg = json.load(open('igm-config.json'))
        else:
            current_cfg = 'undefined';

        self.render( 'main.html',
            schema=json.dumps(schema),
            current_cfg=json.dumps(current_cfg),
            root_directory=cwd,
        )


class LoginHandler(BaseHandler):
    def get(self):
        self.write('<html><body><form action="/login" method="post">'
                   'Secure token: <input type="text" name="name">'
                   '<input type="submit" value="Sign in">'
                   '</form></body></html>')

    def post(self):
        if self.get_argument("name") == token:
            self.set_secure_cookie("user", self.get_argument("name"))
        self.redirect("/")

class CfgFormHandler(tornado.web.RequestHandler):
    @tornado.web.authenticated
    def get(self):
        schema_file = os.path.join(
            os.path.dirname( os.path.abspath(igm.__file__) ),
            'config_schema.json'
        )
        schema = open(schema, 'r').read()
        self.write(config_form(schema))

    @tornado.web.authenticated
    def post(self):
        self.set_header("Content-Type", "text/plain")
        postdata = { k: self.get_argument(k) for k in self.request.arguments }
        cfg = config_form_process(postdata)
        self.write( json.dumps(cfg, indent=4) )

if __name__ == "__main__":

    settings = {
        "static_path": os.path.join(os.path.dirname(__file__), "static"),
        "cookie_secret": secret,
        "login_url": "/login",
        "xsrf_cookies": False,
        "template_path" : template_dir,
        "debug" : True,
        "gzip" : True,
    }

    application = tornado.web.Application([
        (r"/", MainHandler),
        (r"/configure/", CfgFormHandler),
        (r"/login", LoginHandler),
        (r"/ajax/", AjaxHandler),

    ], **settings)

    try:
        ips = subprocess.check_output(['hostname', '-I']).decode('utf-8').strip().split()
    except:
        ips = []

    print('The list of ips for this machine is: ', ips)

    print('The way to connect to the server depends on the platform.')
    if len(ips):
        print('If the machine is accessible, my educated guess is:')
        print('     ', ips[-1] + ':' + str(port) + '?q=' + token)
        print('Copy and paste this address in your browser')

    print('The secure token for this session is:', token)

    application.listen(port)
    tornado.ioloop.IOLoop.current().start()



def list_directory(path, root):

    dname = root + '/' + path

    if not os.path.abspath(dname).startswith(root) or not os.path.isdir(dname):
        return {}

    dname = os.path.abspath(dname)

    content = glob.glob(dname + '/*')
    if os.path.abspath(dname) != os.path.abspath(root):
        dirs = [ path + '/..']
    else:
        dirs = []
    n = len(root)
    dirs += [c[n:] for c in content if os.path.isdir(c)]
    files = [c[n:] for c in content if os.path.isfile(c)]
    return {
        'path': dname,
        'dirs': dirs,
        'files': files,
    }








