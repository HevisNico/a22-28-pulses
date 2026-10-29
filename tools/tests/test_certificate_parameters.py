"""Certificate widths must agree across inputs, arguments and generated reports."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from certificate_parameters import resolve_epsilon


class ParameterTests(unittest.TestCase):
    def setUp(self):
        self.terminal = {'campaign': {'parameters': {'epsilon_relative': '0.001'}}}
        self.certificate = dict(copy.deepcopy(self.terminal), eps='1/1000')

    def test_default_uses_campaign_and_equivalent_exact_spellings(self):
        for explicit in (None, '1e-3', '0.001', '1/1000'):
            self.assertEqual(resolve_epsilon(self.terminal, explicit, self.certificate), Fraction(1, 1000))

    def test_explicit_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, 'explicit epsilon'):
            resolve_epsilon(self.terminal, '1e-4', self.certificate)

    def test_certificate_width_and_campaign_width_both_checked(self):
        for field in ('eps', 'campaign'):
            bad = copy.deepcopy(self.certificate)
            if field == 'eps':
                bad['eps'] = '1e-4'
            else:
                bad['campaign']['parameters']['epsilon_relative'] = '1e-4'
            with self.assertRaisesRegex(ValueError, 'certificate epsilon'):
                resolve_epsilon(self.terminal, certificate=bad)

    def test_missing_or_invalid_width_never_uses_a_fallback(self):
        for value in ('NaN', 'Infinity', '0', '-0.001', '1', '2', '1/0', 0.001, True):
            bad = {'campaign': {'parameters': {'epsilon_relative': value}}}
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve_epsilon(bad)
        with self.assertRaisesRegex(ValueError, 'missing campaign'):
            resolve_epsilon({}, '1e-3')
        with self.assertRaisesRegex(ValueError, 'missing certificate'):
            resolve_epsilon(self.terminal, certificate=self.terminal)

    def test_mismatch_is_exact_even_below_decimal_context_precision(self):
        with self.assertRaises(ValueError):
            resolve_epsilon(self.terminal, '0.0010000000000000000000000000000000000001')


class CommandTests(unittest.TestCase):
    terminal = ROOT / 'terminal' / 'all_terminal_exact.json'
    certificate = ROOT / 'terminal' / 'future_certificate.json'

    def run_tool(self, script, *args):
        return subprocess.run([sys.executable, '-I', str(ROOT / 'tools' / script), *map(str, args)],
                              capture_output=True, text=True, timeout=120)

    def test_independent_default_matches_explicit_current_width(self):
        with tempfile.TemporaryDirectory() as tmp:
            default, explicit = Path(tmp) / 'default.json', Path(tmp) / 'explicit.json'
            for dest, args in ((default, ()), (explicit, ('1e-3',))):
                result = self.run_tool('verify_future.py', self.terminal, self.certificate, dest, *args)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(default.read_bytes(), explicit.read_bytes())
            self.assertEqual(json.loads(default.read_text())['eps'], '1/1000')

    def test_both_commands_reject_explicit_mismatch_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            for script in ('certify_future.py', 'verify_future.py'):
                dest = Path(tmp) / (script + '.json')
                inputs = [self.terminal] + ([self.certificate] if script == 'verify_future.py' else [])
                result = self.run_tool(script, *inputs, dest, '1e-4')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('explicit epsilon does not match', result.stderr)
                self.assertFalse(dest.exists())

    def test_verifier_and_domain_reject_inconsistent_certificate_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            cert = json.loads(self.certificate.read_text())
            cert['eps'] = '1/10000'
            changed = Path(tmp) / 'certificate.json'
            changed.write_text(json.dumps(cert))
            for script in ('verify_future.py', 'build_q_domain.py'):
                dest = Path(tmp) / (script + '.json')
                result = self.run_tool(script, self.terminal, changed, dest)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('certificate epsilon does not match', result.stderr)
                self.assertFalse(dest.exists())


if __name__ == '__main__':
    unittest.main()
