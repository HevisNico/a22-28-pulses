import importlib.util
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'learning_comparison.py'
spec = importlib.util.spec_from_file_location('comparison', SCRIPT)
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


class Interval:
    def __init__(self, lo, hi=None):
        self.lo = D(lo)
        self.hi = D(hi) if hi is not None else self.lo

    def __sub__(self, other):
        return Interval(self.lo - other, self.hi - other)


class Time:
    def __init__(self, lo, hi=None):
        self.value = Interval(lo, hi)

    def box(self):
        return self.value

    def plus(self, delta):
        return Time(self.value.lo + delta, self.value.hi + delta)

    def minus(self, other):
        return Interval(self.value.lo - other.value.hi, self.value.hi - other.value.lo)


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.future = [D(230), D(250), D(281)]
        self.horizon = D(301)

    def test_protocol_has_28_training_pulses_and_irregular_future(self):
        training, future, horizon = comparison.protocol(['20', '31', '40', '25'])
        self.assertEqual(training, [D(8 * k) for k in range(28)])
        self.assertEqual(future, list(map(D, [230, 250, 281, 321, 346])))
        self.assertEqual(horizon, D(366))

    def test_invalid_gap_never_reaches_engine(self):
        for gap in ['19.99', '-20', 'NaN', 'Infinity']:
            with self.subTest(gap=gap), self.assertRaises(ValueError):
                comparison.protocol([gap])

    def test_constant_latency_preserves_irregular_intervals(self):
        report = comparison.measure([Time(t + D('.4')) for t in self.future], self.future, self.horizon)
        self.assertTrue(report['reference_pattern_matched'])
        self.assertEqual(D(report['max_abs_interval_error_upper']), 0)

    def test_jitter_is_measured_instead_of_subtracting_absolute_latencies(self):
        report = comparison.measure([Time('230.4'), Time('250.6'), Time('281.3')], self.future, self.horizon)
        self.assertEqual(D(report['max_abs_interval_error_upper']), D('.3'))

    def test_missing_or_extra_emissions_suppress_interval_score(self):
        for output in [[Time(231), Time(282)], [Time(231), Time(232), Time(251), Time(282)]]:
            with self.subTest(output=output):
                report = comparison.measure(output, self.future, self.horizon)
                self.assertFalse(report['reference_pattern_matched'])
                self.assertNotIn('max_abs_interval_error_upper', report)

    def test_boundary_overlap_is_ambiguous_not_a_missing_or_valid_response(self):
        report = comparison.measure([Time(249, 251), Time(282)], self.future, self.horizon)
        self.assertEqual(report['ambiguous_emissions'], 1)
        self.assertFalse(report['reference_pattern_matched'])
        self.assertNotIn('interval_error_boxes', report)

    def test_silent_reference_does_not_count_as_missing(self):
        report = comparison.measure([], self.future, self.horizon, expected_response=False)
        self.assertTrue(report['reference_pattern_matched'])
        self.assertEqual(report['missing_responses'], 0)
        report = comparison.measure([Time(231)], self.future, self.horizon, expected_response=False)
        self.assertFalse(report['reference_pattern_matched'])
        self.assertEqual(report['extra_emissions'], 1)

    def test_freeze_removes_gain_current_and_deposits_but_keeps_recovery(self):
        source = "def unit():\n return D(230), I(230), ('clock','2.3E+2')\n"
        recovery = object()
        coefficients = lambda state: ('main current', ['learning'], recovery)
        b = SimpleNamespace(dz=SimpleNamespace(), coefficients=coefficients)
        engine = SimpleNamespace(b=b, I=lambda x: x, _src=source)
        comparison.install_variant(engine, 'frozen_gains', D(366))
        history = SimpleNamespace(initial='initial log gain')
        self.assertEqual(b.dz.value(history, None), 'initial log gain')
        self.assertIs(b.dz.open_gate(history, 0, None, None, True), history)
        self.assertIs(b.dz.close_gate(history, None, True), history)
        self.assertIs(b.dz.refresh(history, None), history)
        self.assertFalse(b.dz.certain_cap(history, None))
        main, gain, actual_recovery = b.coefficients(None)
        self.assertEqual(main, 'main current')
        self.assertEqual(gain, [0, 0, 0])
        self.assertIs(actual_recovery, recovery)

    def test_changed_horizon_source_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, 'unsupported engine'):
            comparison.install_variant(SimpleNamespace(b=object(), I=None, _src='changed'), 'adaptive', D(366))


if __name__ == '__main__':
    unittest.main()
