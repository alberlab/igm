from __future__ import division, print_function

from .restraint import Restraint
from ..model.particle import Particle
from ..model.forces import HarmonicUpperBound, EllipticEnvelope
try:
    UNICODE_EXISTS = bool(type(unicode))
except NameError:
    unicode = lambda s: str(s)

class Envelope(Restraint):
    """
    A object handles nuclear envelope restraints

    Parameters
    ----------
    nucRadius : float or list
        nuclear radius or the length of the three semiaxes, in nm
    k : float
        spring constant
    """
    def __init__(self, shape="sphere", nuclear_radius=5000.0, k=1.0):
        self.shape = unicode(shape)

        if self.shape == u"sphere":
            self.a = self.b = self.c = nuclear_radius
        elif self.shape == u"ellipsoid":
            self.a, self.b, self.c = nuclear_radius

        self.k = k
        self.forceID = []


    def _apply_sphere_envelop(self, model):
        center = model.addParticle([0., 0., 0.], 0., Particle.DUMMY_STATIC)

        normal_particles = [
            i for i, p in enumerate(model.particles)
            if p.ptype == Particle.NORMAL
        ]
        f = model.addForce(
            EllipticEnvelope(
                normal_particles,
                center,
                (self.a, self.b, self.c),
                self.k
            )
        )
        self.forceID.append(f)


    def _apply(self, model):
        self._apply_sphere_envelop(model)


    def __repr__(self):
        return 'Envelope[shape={},k={},a={},b={},c={}]'.format(self.shape, self.k, self.a, self.b, self.c)
    #=
