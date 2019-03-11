import numpy as np
import logging
import traceback
from alabtools import HssFile

from .utils import create_folder


def render_structures(hssfname, n=4, random=True):
    logger = logging.getLogger('Render')
    logger.info('Starting render... (it may take a while)')

    try:
        create_folder('images')
        with HssFile(hssfname, 'r') as h:

            if random:
                ii = np.random.choice(range(h.nstruct), size=n, replace=False)
            else:
                ii = list(range(min(n, h.nstruct)))

            h.dump_pdb(ii, fname='images/structure_%d.pdb', render=True, high_quality=True)
        logger.info('Done.')

    except KeyboardInterrupt:
        logger.error('User interrupt. Exiting.')
        exit(1)

    except Exception:
        traceback.print_exc()
        logger.error('Error in rendering step\n==============================')

