import igm
import sys
import os.path
from igm.utils.log import set_log, logger
from alabtools.analysis import HssFile


#===start pipeline with configure file
cfgfile = os.path.abspath(sys.argv[1]) 
cfg = igm.Config(cfgfile)

logger.info('Starting pipeline. Configuration from ' + cfgfile)

if 'log' in cfg:
    set_log(cfg['log'])

# Preprocess genome, index and allocate disk space for genome structures

igm.Preprocess(cfg)

# Generate random initial configuration

randomStep = igm.RandomInit(cfg)
randomStep.run()

relaxStep = igm.RelaxInit(cfg)
relaxStep.run()

# step serial number
step_no = 0
# optimization iteration
opt_iter = 0
# max unsuccessful optimization iterations before stopping
max_iter = cfg.get('max_iterations', None) 

# main optimization loop
while True:
    cfg['runtime']['opt_iter'] = opt_iter

    # setup the needed steps for this optimization iteration
    iter_steps = [] 
    if 'Hi-C' in cfg['restraints']:
        if "sigma" not in cfg["restraints"]["Hi-C"]:
            cfg["restraints"]["Hi-C"]["sigma"] = cfg["restraints"]["Hi-C"]["sigma_list"].pop(0)
        iter_steps.append(igm.ActivationDistanceStep)
    if 'FISH' in cfg['restraints']:
        iter_steps.append(igm.FishAssignmentStep)
    if 'SPRITE' in cfg['restraints']:
        iter_steps.append(igm.SpriteAssignmentStep)
    if 'DamID' in cfg['restraints']:
        iter_steps.append(igm.DamidActivationDistanceStep)
    iter_steps.append(igm.ModelingStep)

    # run the required steps
    for StepClass in iter_steps:
        step_no += 1
        cfg['runtime']['step_no'] = step_no
        step = StepClass(cfg)
        step.run()

    # check the violations
    hss = HssFile(cfg["structure_output"])
    vio = hss.get_violation()
    logger.info('Violation score: %f' % vio)
    if vio < 0.01:
        # no violations, go to next step or finish
        opt_iter = 0
        if 'Hi-C' in cfg['restraints'] and len( cfg["restraints"]["Hi-C"]["sigma_list"] ) != 0:
            # we are done with this sigma but still have more to go
            del cfg["restraints"]["Hi-C"]["sigma"] 
        else:
            # no violations, no more work to do
            logger.info('Pipeline completed')
            break
    else:
        # if there are violations, try to optimize again
        opt_iter += 1
        if max_iter is not None:
            if opt_iter >= max_iter:
                logger.critical('Maximum number of iterations reached (%d)' % max_iter)
                break
        logger.info('iteration # %d' % opt_iter)


