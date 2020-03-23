from __future__ import division, print_function

import numpy as np

from .restraint import Restraint
from ..model.particle import Particle
from ..model.forces import ExpEnvelope

try:
    UNICODE_EXISTS = bool(type(unicode))
except NameError:
    unicode = lambda s: str(s)

class GenEnvelope(Restraint):
    """
    This class handles a (non ideal) nuclear envelope restraint from a density map

    Parameters
    ----------
    volume_file: string
        name of file containing the binary density map we would like to fit the genome into
    k : float
        spring constant
    """

    def __init__(self, shape, volume_file="", k=1.0):

        self.shape = unicode(shape)
        self.volume_file = volume_file     # file containing the binary density map information
        self.k = k                         # elastic restraining constant (>0 attractive, <0 repulsive)

        self.forceID = []


    def _apply_sphere_envelop(self, model):

        normal_particles = [
            i for i, p in enumerate(model.particles)
            if p.ptype == Particle.NORMAL
        ]

        f = model.addForce(
            ExpEnvelope(
                normal_particles,
                self.volume_file,
                self.k,
                scale= 0.5
                # set arbitrary scale: 100% violation ratio if extend inside by
                # 1/10 of the nucleus radius. With usual parameters, it means
                # that will be noticed as violated when the bond is stretched
                # by 25nm.
            )
        )
        self.forceID.append(f)


    def _apply(self, model):
        self._apply_sphere_envelop(model)


    def __repr__(self):
        return 'ExpEnvelope[shape={},k={}]'.format(self.shape, self.k)
    #=
