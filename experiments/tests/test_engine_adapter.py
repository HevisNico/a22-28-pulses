"""Integration check; requires engine dependencies and locally built extensions."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('comparison_integration', ROOT / 'experiments' / 'learning_comparison.py')
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


class EngineAdapterTests(unittest.TestCase):
    def test_original_horizon_equivalence_and_frozen_initial_gains(self):
        os.environ['A22_PHYSICAL_EPSILON'] = '1e-3'
        sys.path.insert(0, str(ROOT / 'engine'))
        import run
        with tempfile.TemporaryDirectory() as tmp:
            engine, artifacts, temporal = run.initialize(Path(tmp))
            temporal.begin_producer('integration/source')
            clock = temporal.Time('canonical-initial-clock', engine.I(0))
            trains = [tuple(clock.plus(8 * k) for k in range(28))] + [()] * 11

            def calculate():
                return engine.compute_cell(1, 0, trains, 'integration/cell/1/0')

            def scientific_hash(result):
                return artifacts.canonical_hash(artifacts.Encoder().encode(
                    dict(outputs=result['outputs'], state=result['state'])))

            original = calculate()
            original_hash = scientific_hash(original)
            comparison.install_variant(engine, 'adaptive', '230')
            adaptive = calculate()
            self.assertEqual(scientific_hash(adaptive), original_hash)
            recovery_bounds = engine.b.ac.bounds
            comparison.install_variant(engine, 'frozen_gains', '230')
            frozen = calculate()
            self.assertIs(engine.b.ac.bounds, recovery_bounds)
            self.assertGreater(len(adaptive['outputs']), 0)
            self.assertEqual(len(frozen['outputs']), 0)
            for j, nominal in enumerate(('.3', '1.2', '.3')):
                expected = engine.I(nominal).ln() + engine.b.INIT['z'][j]
                final = frozen['state']['terminal_affine']['z'][j]
                self.assertEqual(final.fingerprint(), expected.fingerprint())
                for history in frozen['state']['terminal_affine']['depot'][j]:
                    self.assertFalse(history.full or history.partial or history.active or history.clamped)


if __name__ == '__main__':
    unittest.main()
