"""Focused Preprocess regression without importing the optional modeling stack.

Execute the complete, unmodified Preprocess function from the source AST.
Mock only genome preparation and the HSS writer to inspect initialized radii.
Run with: python -m unittest discover -s tests -p 'test_radii.py' -v
"""
import ast
import logging
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import warnings

import numpy as np


class IndexStub:
    def __init__(self, start, end):
        self.start = np.array(start, dtype=np.int32)
        self.end = np.array(end, dtype=np.int32)

    def __len__(self):
        return len(self.start)


class TestOccupancyRadii(unittest.TestCase):
    def test_lengths_and_occupancy_without_overflow(self):
        source = Path(__file__).resolve().parents[1] / "igm" / "_preprocess.py"
        tree = ast.parse(source.read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "Preprocess")
        code = compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec")
        cases = {
            "small_irregular": ([0, 0, 50], [100, 250, 750]),
            "above_int32_total": ([0, 0], [1_500_000_000, 1_000_000_000]),
            "above_uint32_irregular": ([0, 0, 0], [1_500_000_000, 2_000_000_000, 1_000_000_000]),
            "endpoint_subtraction": ([-2_000_000_000, 0], [2_000_000_000, 100]),
            "reported_run": ([0] * 10397, [500_000] * 10397),
        }

        for name, (starts, ends) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                index = IndexStub(starts, ends)
                before = (index.start.copy(), index.end.copy())
                writer = Mock()
                namespace = dict(np=np, os=os, logger=logging.getLogger(__name__),
                                 PrepareGenomeIndex=lambda cfg: (None, index), prepareHss=writer)
                exec(code, namespace)
                cfg = {
                    "model": {"population_size": 2, "occupancy": 0.2},
                    "model/restraints/envelope/nucleus_shape": "sphere",
                    "model/restraints/envelope/nucleus_radius": 7000.0,
                    "optimization": {"structure_output": os.path.join(tmp, "population.hss")},
                    "parameters": {"tmp_dir": os.path.join(tmp, "work")},
                }
                with warnings.catch_warnings():
                    warnings.simplefilter("error", RuntimeWarning)
                    namespace["Preprocess"](cfg)
                lengths = [int(e) - int(s) for s, e in zip(starts, ends)]
                total = sum(lengths)  # Python integer reference, independent of NumPy promotion.
                expected = np.array([(0.2 * 7000.0**3 * b / total)**(1.0/3.0) for b in lengths])
                self.assertEqual(writer.call_count, 2)
                for call in writer.call_args_list:
                    radii = call.args[5]
                    np.testing.assert_allclose(radii, expected, rtol=1e-12)
                    self.assertEqual(radii.dtype, np.dtype("float64"))
                    self.assertAlmostEqual(float(np.sum(radii**3) / 7000.0**3), 0.2, places=12)
                self.assertEqual(index.start.dtype, np.dtype("int32"))
                self.assertEqual(index.end.dtype, np.dtype("int32"))
                np.testing.assert_array_equal(index.start, before[0])
                np.testing.assert_array_equal(index.end, before[1])
                if name == "reported_run":
                    self.assertEqual(total, 5_198_500_000)
                    self.assertAlmostEqual(float(expected[0]), 187.5593377290677, places=9)


if __name__ == "__main__":
    unittest.main()
