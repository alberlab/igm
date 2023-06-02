# This script prepares the controller/engines environment, using the MONITOR option 
# which allows to keep track of how the tasks are split among the different engines
# On the top of this, the serial IGM job will be submitted

# number of workers
NTASKS=200
# memory per worker
MEM=$2
# walltime
WTIME=$3
# conda env to use
CONDA=$4
# scheduler memory, usual a little larger than workers
SMEM=$5

let NTOT=${NTASKS}+1
if [[ -z "$2" ]]; then
    MEM=2G
fi
if [[ -z "$3" ]]; then
    WTIME=96:00:00
fi

if [[ -z "$4" ]]; then
    CONDA=py3
fi

if [[ -z "$5" ]]; then
    SMEM=10G
fi

echo "requesting ${NTASKS} processes, ${MEM} per cpu, walltime: ${WTIME}" 

CURRDIR=`pwd`

TMPFILE=`mktemp` || exit 1
# write the slurm script
cat > $TMPFILE <<- EOF
#!/bin/bash
#$ -M fmusella@g.ucla.edu
#$ -m ea
#$ -N ipycontroller
#$ -l h_data=${SMEM},h_vmem=INFINITY
#$ -l h_rt=${WTIME}
#$ -l highp
#$ -cwd
#$ -o out_controller
#$ -e err_controller
#$ -V 

export PATH="$PATH"
ulimit -s 8192


cd $SGE_O_WORKDIR

#myip=\$(getent hosts \$(hostname) | awk '{print \$1}')

# extract one ip-address:they messeup up things with the upgrade to CentOS7, so we needed to adapt this
myip=\$(getent ahosts \$(hostname) | awk 'NR==1 {print \$1}')


MONITOR=$(command -v monitor_process)
if [[ ! -z "$MONITOR" ]]; then
    monitor_process --wtype S ipcontroller --nodb --ip=\$myip 
else
    ipcontroller --nodb --ip=\$myip
fi
EOF

cat $TMPFILE >> 'script1.sh'

#SCHEDJOB=$(qsub $TMPFILE | awk '{print $4}')
#echo 'scheduler job submitted:' $SCHEDJOB

# upgrade to CentOS7 modified what 'qsub' command returns to the prompt...needed to change that
SCHEDJOB=$(qsub $TMPFILE | grep -o '[0-9]\+')
echo 'scheduler job submitted:' $SCHEDJOB


TMPFILE=`mktemp` || exit 1
# write the slurm script
cat > $TMPFILE <<- EOF
#!/bin/bash
#$ -M fmusella@g.ucla.edu
#$ -m ea
#$ -N ipycluster
#$ -l h_data=${MEM},h_vmem=INFINITY
#$ -l h_rt=${WTIME}
#$ -l highp
#$ -cwd
#$ -o out_engines
#$ -e err_engines
#$ -V
#$ -pe dc* ${NTASKS} 


export PATH="$PATH"
ulimit -s 8192

cd $SGE_O_WORKDIR

# let the scheduler setup finish
sleep 10
MONITOR=$(command -v monitor_process)
if [[ ! -z "$MONITOR" ]]; then
    mpirun --n=${NTASKS} monitor_process --wtype W ipengine
else
    mpirun --n=${NTASKS} ipengine
fi

EOF

#cat $TMPFILE
sleep 1
cat $TMPFILE >> 'script_engines.sh'

echo "The engines will start only after the controller job $SCHEDJOB starts..."
#qsub -W depend=afterok:$SCHEDJOB $TMPFILE
#rm $TMPFILE 

echo "Need to manually submit $NTASKS engines on the top of the controller!"
