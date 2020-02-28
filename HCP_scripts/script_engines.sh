#!/bin/bash
#$ -M bonimba@g.ucla.edu
#$ -m ea
#$ -N ipycluster
#$ -l h_data=2G
#$ -l h_rt=200:59:59
#$ -l highp
#$ -cwd
#$ -o out_engines
#$ -e err_engines
#$ -V
#$ -pe dc* 100 


export PATH="/u/home/b/bonimba/miniconda3/bin:/u/home/b/bonimba/miniconda3/condabin:/u/local/compilers/intel/18.0.4/parallel_studio_xe_2018/bin:/u/local/compilers/intel/18.0.4/compilers_and_libraries_2018.5.274/linux/mpi/intel64/bin:/u/local/compilers/intel/18.0.4/compilers_and_libraries_2018.5.274/linux/bin/intel64:/u/local/compilers/intel/18.0.4/clck/2018.3/bin/intel64:/u/local/compilers/intel/18.0.4/itac/2018.4.025/intel64/bin:/u/local/compilers/intel/18.0.4/inspector/bin64:/u/local/compilers/intel/18.0.4/vtune_amplifier_2018/bin64:/u/local/compilers/intel/18.0.4/advisor_2018/bin64:/u/systems/UGE8.6.4/bin/lx-amd64:/u/local/bin:/u/local/sbin:/usr/lib64/qt-3.3/bin:/usr/local/bin:/bin:/usr/bin:/usr/local/sbin:/usr/sbin:/sbin:/u/home/b/bonimba/bin"
ulimit -s 8192

cd 

# let the scheduler setup finish
sleep 10
MONITOR=
if [[ ! -z "" ]]; then
    mpirun --n=100 monitor_process --wtype W ipengine
else
    mpirun --n=100 ipengine
fi


