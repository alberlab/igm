import json
import os, os.path
from alabtools.analysis import HssFile
from igm.core.job_tracking import StepDB
from igm import Config
from .folders_database import register_folder
import glob


def history(folder='.'):
    cfg = json.load(open(os.path.join(folder, 'igm-config.json'), 'r'))
    try:
        db = StepDB(cfg, mode='r')
        h = db.get_history()
    except OSError:
        h = []
    # to avoid excessive data exchange
    for i in range(len(h)):
        del h[i]['cfg']
    return h

def readlog(folder='.'):

    # select the file
    logf = os.path.join(folder, 'igm-log.txt')
    cfgf = os.path.join(folder, 'igm-config.json')
    if os.path.isfile(logf):
        f = logf
    elif os.path.isfile(cfgf):
        current_cfg = json.load(open(cfgf))
        f = current_cfg['log']
    else:
        return None

    # read in binary mode, so will keep carriage returns
    lines = open(f, 'rb').readlines()
    # remove all the unnecessary carriage returns and reassemble
    log = '\n'.join([ l.decode('utf-8').split('\r')[-1].strip('\n') for l in lines ])
    return log

def igm_is_running(folder='.'):
    pidf = os.path.join(folder, '.igm-pid.txt')
    if os.path.isfile(pidf):
        pid = int(open(pidf).read())
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

def kill_igm(folder='.'):
    '''
    Try to kindly ask to terminate, then kill the process
    if it is not done in 5 seconds.
    '''
    pidf = os.path.join(folder, '.igm-pid.txt')
    import time, multiprocessing
    if os.path.isfile(pidf):
        pid = int(open(pidf).read())
        os.kill(pid, 2)
        def real_kill(pid):
            time.sleep(5)
            if os.path.isfile(pidf):
                os.kill(pid, 9)
                os.remove(pidf)
        p = multiprocessing.Process(target=real_kill, args=(pid,), daemon=True)
        p.start()


def clear_previous_runs(folder='.'):
    cfgf = os.path.join(folder, 'igm-config.json')
    # this is ultra dangerous, one could change the config and
    # remove arbitrary files, should check they are files
    # inside the current directory
    cfg = Config(cfgf)
    os.remove(cfg['step_db'])
    os.remove(cfg['structure_output'])
    os.remove(cfg['structure_output'] + '.tmp')
    os.remove(cfg['log'])

def get_structure(path, n, folder='.'):
    path = os.path.join(folder, path)

    with HssFile(path, 'r') as f:
        crd = f.get_struct_crd(n).tolist()
        chrom = f.genome.chroms[f.index.chrom].tolist()
        radius = f.radii.tolist()
        nstruct = f.nstruct
        cstarts = f.index.offset.tolist()

    return {
        'crd' : [crd[cstarts[i]:cstarts[i+1]] for i in range(len(cstarts)-1)],
        'idx' : chrom,
        'rad' : [radius[cstarts[i]:cstarts[i+1]] for i in range(len(cstarts)-1)],
        'n' : int(nstruct),
        'cstarts': cstarts,
        'chroms': [str(v) for i, v in enumerate(chrom) if i == 0 or v != chrom[i-1]],
    }

def save_metadata(data, cwd):
    folder = data.pop('folder')
    if os.path.realpath(folder) != os.path.realpath(cwd):
        raise ValueError('Invalid folder %s' % folder)
    if 'notes' in data:
        if data['notes']:
            with open(os.path.realpath(folder) + '/IGM_NOTES.TXT', 'w') as f:
                f.write(data['notes'])
    register_folder(cwd, **data)
