from __future__ import print_function, division

from six import raise_from

import os
import time
from .parallel_controller import ParallelController 
from tqdm import tqdm
from .utils import split_evenly
import subprocess
import shutil


import cloudpickle
from uuid import uuid4

base_template = '''#!/bin/bash
#SBATCH --ntasks=1
#SBATCH --mem-per-cpu={{mem}} 
#SBATCH --time={{walltime}}
#SBATCH --partition=cmb
#SBATCH --job-name={{jname}}
#SBATCH --output={{out}}
#SBATCH --error={{err}}

echo $(which python)
#source /auto/cmb-08/fa/local/setup.sh
umask 002

{{interpreter}} -c 'from igm.parallel.slurm_controller import SlurmController; SlurmController.execute("{{sfile}}", {{i}})'

'''

default_args = {
    'mem' : '2GB',
    'walltime' : '6:00:00',
    'interpreter' : 'python'
}

def parse_template(template, **kwargs):
        for k, v in kwargs.items():
            template = template.replace('{{' + k + '}}', v)
        return template
    
class SlurmController(ParallelController): 
    def __init__(self, template=None, max_tasks=4000, tmp_dir='tmp', simultaneous_tasks=430, **kwargs):

        sargs = {}
        sargs.update(default_args)
        sargs.update(kwargs)

        self.max_tasks = max_tasks
        self.sim_tasks = simultaneous_tasks
        if template is not None:
            self.template = open(template).read()
        else:
            self.template = base_template
        self.template = parse_template(self.template, **sargs)
        if not os.path.isdir(tmp_dir):
            os.makedirs(tmp_dir)
        self.tmp_dir = os.path.abspath(tmp_dir)

    
    def send_job(self, outd, i):
        slurmscript = os.path.join(outd, '%d.slurm' % i)
        with open(slurmscript, 'w') as f:
            f.write( 
                parse_template(
                    self.template, 
                    i=str(i), 
                    jname=str(i),
                    out=os.path.join(outd, '%d.out' % i),
                    err=os.path.join(outd, '%d.err' % i)
                ) 
            )

        # writes "Submitted batch job XXXXXXX"
        jid = subprocess.check_output(['sbatch', slurmscript]).split()[3]
        return jid

    def job_was_successful(self, outd, i):
        if os.path.isfile(os.path.join(outd, '%d.complete' % i )):
            return True
        return False

    def job_is_completed(self, outd, i, jid):
        try:
            out = subprocess.check_output(['squeue', '-j', jid]).decode('utf-8').split('\n')
            keys, vals, _ = out
            kv = {k: v for k, v in zip(keys.split(), vals.split())}
            if kv['ST'] == 'CD':
                return True
            else:
                return False
        except (subprocess.CalledProcessError, ValueError):
            if not self.job_was_successful(outd, i):
                raise_from(RuntimeError('(SLURM): Remote error. Error file:' + os.path.join(outd, '%d.err' % i)), None)
            return True
        return False


    def poll_loop(self, n_tasks, outd, timeout=1):
        to_send = set(range(n_tasks))
        processing = dict()
        
        while len(to_send) > 0 or len(processing) > 0 :
            just_completed = set()
            for i, jid in processing.items():
                if self.job_is_completed(outd, i, jid):
                    just_completed.add(i)
                    yield i

            while len(processing) < self.sim_tasks and len(to_send) > 0:
                i = to_send.pop()
                processing[i] = self.send_job(outd, i)

            for i in just_completed:
                del processing[i]

            time.sleep(timeout)

        raise StopIteration


    def map(self, parallel_task, args):
        uid = 'slurmc.' + str(uuid4())
        outd = os.path.join(self.tmp_dir, uid)
        os.makedirs(outd)

        batches = list(split_evenly(args, self.max_tasks))

        sfile = os.path.join(outd, 'exdata.cloudpickle')
        with open(sfile, 'wb') as f:
            cloudpickle.dump({'f': parallel_task, 'args': batches, 'outd': outd}, f)

        self.template = parse_template(self.template, sfile=sfile)

        n_tasks = len(batches)

        ar = self.poll_loop(n_tasks, outd)
        for i in tqdm(ar, desc="(SLURM)", total=n_tasks):
            pass
        shutil.rmtree(outd)

    @staticmethod
    def execute(sfile, i):
        v = cloudpickle.load(open(sfile, 'rb'))
        for x in v['args'][i]:
            v['f'](x)
        open(os.path.join(v['outd'], '%d.complete' % i), 'w').close()
