"""Static identities and loaded-runtime checks have separate acceptance conditions."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import verify


class EngineIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.engine = self.root / 'engine'
        for name in ('run.py', 'build_native.py', 'build_all_native.py', 'launch_fresh.py',
                     'reference/full_model_reference.md', 'affine/affine_iv.py',
                     'kernel/native/a22_native.c'):
            path = self.engine / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('KMAX = 256\nraise RuntimeError("must not execute during a static check")\n')
        self.binaries = {}
        for name in ('affine/_rounding_native.cpython-313.so', 'kernel/native/_a22_native.cpython-313.so'):
            path = self.engine / name
            path.write_bytes(b'fixture native binary')
            self.binaries[name] = verify.sha(path)
        self.campaign = {
            'environment': {'python': '3.13.17', 'numpy': '2.3.5', 'scipy': '1.17.0',
                            'arithmetic_backend': 'native',
                            'native_sha256': self.binaries['affine/_rounding_native.cpython-313.so']},
            'parameters': {'epsilon_relative': '0.001'},
        }
        self.campaign['kernel_id'] = verify.archived_kernel_id(self.engine, self.campaign)
        (self.root / 'campaign').mkdir()
        self.config = self.root / 'campaign' / 'campaign.json'
        self.config.write_text(json.dumps(self.campaign))
        verify.RESULTS.clear()
        self.addCleanup(verify.RESULTS.clear)

    def check_engine(self, runtime=False):
        with patch.object(verify, 'REPO', self.root), contextlib.redirect_stdout(io.StringIO()):
            verify.engine_checks(self.engine, runtime)
        return list(verify.RESULTS)

    def test_static_check_never_imports_or_executes_engine(self):
        with patch.object(verify.subprocess, 'run', side_effect=AssertionError('unexpected execution')):
            self.assertEqual(self.check_engine(), [True, True])

    def test_python_fallback_and_wrong_interpreter_fail_runtime_check(self):
        loaded = {'environment': dict(self.campaign['environment'], python='3.12.14', arithmetic_backend='python'),
                  'native_files': {}}
        loaded['environment'].pop('native_sha256')
        with patch.object(verify, 'runtime_environment', return_value=loaded):
            self.assertEqual(self.check_engine(True), [True, True, False])

    def test_matching_loaded_runtime_passes(self):
        loaded = {'environment': self.campaign['environment'], 'native_files': self.binaries}
        with patch.object(verify, 'runtime_environment', return_value=loaded):
            self.assertEqual(self.check_engine(True), [True, True, True])

    def test_wrong_dependency_or_native_binary_is_rejected(self):
        for kind in ('numpy', 'scipy', 'native_sha256', 'kernel_binary'):
            verify.RESULTS.clear()
            loaded = copy.deepcopy({'environment': self.campaign['environment'], 'native_files': self.binaries})
            if kind == 'kernel_binary':
                loaded['native_files']['kernel/native/_a22_native.cpython-313.so'] = 'wrong'
            else:
                loaded['environment'][kind] = 'wrong'
            with self.subTest(kind=kind), patch.object(verify, 'runtime_environment', return_value=loaded):
                self.assertEqual(self.check_engine(True), [True, True, False])

    def test_failed_static_identity_prevents_runtime_loading(self):
        (self.engine / 'run.py').write_text('raise RuntimeError("changed")\n')
        with patch.object(verify, 'runtime_environment') as runtime:
            self.assertEqual(self.check_engine(True), [True, False, False])
            runtime.assert_not_called()

    def test_literal_symbol_limit_required(self):
        (self.engine / 'affine' / 'affine_iv.py').write_text('KMAX = int("256")\n')
        with self.assertRaises(ValueError):
            verify.archived_kernel_id(self.engine, self.campaign)

    def test_static_source_hash_matches_the_runner(self):
        spec = importlib.util.spec_from_file_location('a22_runner_identity_test', ROOT / 'engine' / 'run.py')
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        self.assertEqual(verify.source_identity(ROOT / 'engine'), runner.identity())

    def test_runtime_option_requires_an_engine(self):
        result = subprocess.run([sys.executable, '-I', str(ROOT / 'tools' / 'verify.py'), '--check-runtime'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn('--check-runtime requires --engine', result.stderr)


if __name__ == '__main__':
    unittest.main()
