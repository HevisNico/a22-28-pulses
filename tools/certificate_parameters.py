"""Exact parameter agreement for certificate metadata; no interval arithmetic."""
from fractions import Fraction


def parse_epsilon(value):
    if not isinstance(value, (str, int, Fraction)) or isinstance(value, bool):
        raise ValueError('epsilon must be an exact decimal or rational value')
    try:
        epsilon = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError('epsilon must be finite and strictly between 0 and 1') from exc
    if not 0 < epsilon < 1:
        raise ValueError('epsilon must be finite and strictly between 0 and 1')
    return epsilon


def campaign_epsilon(document):
    try:
        value = document['campaign']['parameters']['epsilon_relative']
    except (KeyError, TypeError) as exc:
        raise ValueError('missing campaign epsilon_relative') from exc
    return parse_epsilon(value)


def resolve_epsilon(terminal, explicit=None, certificate=None):
    """Use the terminal campaign width and reject every conflicting declaration."""
    epsilon = campaign_epsilon(terminal)
    if explicit is not None and parse_epsilon(explicit) != epsilon:
        raise ValueError('explicit epsilon does not match the terminal campaign')
    if certificate is not None:
        if 'eps' not in certificate:
            raise ValueError('missing certificate eps')
        if parse_epsilon(certificate['eps']) != epsilon or campaign_epsilon(certificate) != epsilon:
            raise ValueError('certificate epsilon does not match the terminal campaign')
    return epsilon
