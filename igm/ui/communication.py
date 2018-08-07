import json
import os, os.path

from igm.core.job_tracking import StepDB

def history():
    cfg = json.load(open('igm-config.json', 'r'))
    db = StepDB(cfg, mode='r')
    h = db.get_history()
    # to avoid excessive data exchange
    for i in range(len(h)):
        del h[i]['cfg']
    return h

def readlog():

    # select the file
    if os.path.isfile('igm-log.txt'):
        f = 'igm-log.txt'
    elif os.path.isfile('igm-config.json'):
        current_cfg = json.load(open('igm-config.json'))
        f = current_cfg['log']
    else:
        return None

    # read in binary mode, so will keep carriage returns
    lines = open(f, 'rb').readlines()
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


def clear_previous_runs():

    # this is ultra dangerous, one could change the config and 
    # remove arbitrary files, should check they are files
    # inside the current directory
    cfg = json.load(open('igm-config.json', 'r'))
    os.remove(cfg['step_db'])
    os.remove(cfg['structure_output'])
    os.remove(cfg['structure_output'] + '.tmp')
    os.remove(cfg['log'])