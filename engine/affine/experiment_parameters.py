"""Frozen physical-box width for a fresh research campaign.

The runner records this value in the campaign identity. Spawned workers and
the separate verifier inherit it. Initial-state uncertainty stays at 1e-5.
"""
import os
from decimal import Decimal


def validate_epsilon(value):
    number = Decimal(value)
    if not number.is_finite() or not Decimal(0) < number < Decimal(1):
        raise ValueError('epsilon must be finite and strictly between 0 and 1')
    return str(number.normalize())


PHYSICAL_EPSILON = validate_epsilon(os.environ.get('A22_PHYSICAL_EPSILON', '1e-4'))
