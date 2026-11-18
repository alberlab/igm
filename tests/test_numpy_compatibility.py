import tempfile
import unittest
import warnings
from pathlib import Path

import h5py
import numpy as np

from igm.model import Model, Particle
from igm.model.forces import ExcludedVolume
from igm.restraints.sprite import Sprite


def make_model():
    model = Model()
    for x, radius in [(0, 1), (1, 2), (5, 0.5)]:
        model.addParticle([x, 0, 0], radius, Particle.NORMAL)
    return model


class TestNumpyScalarCompatibility(unittest.TestCase):
    def test_excluded_volume_scores(self):
        model = make_model()
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            scores = ExcludedVolume([0, 1, 2]).getScores(model.particles)
        np.testing.assert_array_equal(scores, [2, 0, 0])

    def test_sprite_restraint_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "assignment.h5"
            with h5py.File(path, "w") as assignment:
                assignment["assignment"] = [0]
                assignment["indptr"] = [0, 3]
                assignment["selected"] = [0, 1, 2]
            model = make_model()
            restraint = Sprite(str(path), 0.5, 0)
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", DeprecationWarning)
                    model.addRestraint(restraint)
            finally:
                restraint.assignment_file.close()

        cluster_radius = ((1**3 + 2**3 + 0.5**3) / 0.5)**(1.0 / 3.0)
        self.assertEqual(len(model.forces), 3)
        self.assertTrue(all(isinstance(force.d, float) for force in model.forces))
        np.testing.assert_allclose(
            [force.d for force in model.forces],
            [cluster_radius - radius for radius in [1, 2, 0.5]],
            rtol=1e-6,
        )


if __name__ == "__main__":
    unittest.main()
