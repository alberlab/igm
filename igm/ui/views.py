
import os, os.path
from tornado import template
from ..core.config import Config
from ..core.job_tracking import StepDB
from ..utils.log import pretty_time
import time

template_dir = os.path.join( os.path.dirname( os.path.abspath(__file__) ),  'templates' ) 
loader = template.Loader(template_dir)

def render(template, data):
    return loader.load(template).generate(**data)


def history(cfgf):
    cfgf = os.path.abspath(cfgf)
    cfg = Config(cfgf)
    db = StepDB(cfg)
    h = db.get_history()
    for i in range(len(h)):
        h[i]['elapsed'] = pretty_time(h[i]['time'] - h[0]['time'])
        h[i]['step_no'] = i
        h[i]['consumed'] = pretty_time(h[i]['time'] - h[max(i-1, 0)]['time'])
        h[i]['strtime'] = time.strftime('%c', time.localtime(h[i]['time']))
        
    return render( 'history.html', { 
        'history': h,
        'directory': os.path.dirname(cfgf),
        'cfg_fname': os.path.basename(cfgf) 
    })
