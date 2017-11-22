mkdir logs
mkdir tmp
for i in `seq 10`
do
qsub ipworkernode.pbs >> worker_job_ids.log
done 
