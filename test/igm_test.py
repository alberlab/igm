import igm
import numpy as np

#===start pipeline with configure file
cfg = igm.Config("config_test.json")

#Preprocess genome, index and allocate disk space for genome structures
igm.Preprocess(cfg)



#===Run steps
randomStep = igm.RandomInit(cfg)
randomStep.run()

relaxStep = igm.RelaxInit(cfg)
relaxStep.run()


