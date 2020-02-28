#!/bin/bash

#----------------------------------------#
#- IGM SUBMISSION SCRIPT, multi-threaded JOB
#----------------------------------------#

#$ -M bonimba@g.ucla.edu
#$ -m ea
#$ -N volume
#$ -l h_data=8G
#$ -l h_rt=10:00:00
#$ -l highp
#$ -cwd
#$ -o out_igm
#$ -e err_igm
#$ -V 
#$ -pe shared 2

export PATH="$PATH"
ulimit -s 8192

# -----------------------
# print JOB ID, can be useful for keeping track of status
echo $JOB_ID

# print PATH pointing to directory the job is run from
echo $SGE_O_WORKDIR


# shared memory parallelization: same node, more cores, export number of threads
export OMP_NUM_THREADS=2
echo "submitting IGM optimization..."

# execute job
igm-run conf_nucleolus.json >> igm_output.txt

