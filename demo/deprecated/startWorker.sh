mkdir logs
mkdir tmp
for i in `seq 280`
do
qsub ipworkernode.pbs >> worker_job_ids.log
done 
touch .workers.restart

