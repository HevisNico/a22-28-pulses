"""F01: READY has domain 0 <= q <= 1, including initial charges below r.

The exact return section establishes q=r, but the READY mode flag alone
does not.  This adapter changes no archived source: install() explicitly
redirects the A20 helper used dynamically by A21 and its scalar bounds.
"""
import validation_A15 as b
from intervalles_decimaux import I, D


def ready_endpoint(end):
    """Keep the physical no-fire endpoint domain, without assuming q>=r.

    Nonnegative initial charge, nonnegative inputs and relaxation toward
    positive r imply q>=0.  A trajectory with no first threshold before
    the endpoint has q<=1.  Intersection with this closed domain cannot
    remove such a trajectory; equality is deliberately retained.
    """
    q = end['q']
    if q.hi < 0 or q.lo > 1:
        return None
    out = end.copy()
    out['q'] = q.intersect(I(0, 1))
    return out


def scalar_root(q, j, horizon, key):
    """An optional first ascending root bound of the scalar comparison.

    None means no usable root bound, not a proved absence of a guard.
    In particular it leaves the outer guard cover untrimmed.  The formula
    is q(u)=r+aa*exp(-k*u)-bb*exp(-a*u), bb=j/(a-k).
    When aa is not strictly positive we avoid the logarithmic peak formula.
    For aa<=0 the scalar trajectory increases toward r<1; when interval
    signs are undecided declining to bound the root is conservative.
    """
    if q >= 1:
        return I(0)
    if j <= 0 or horizon <= 0:
        return None
    qi, ji = I(q), I(j)
    bb = ji / (b.A - b.K)
    aa = qi - b.R + bb
    if aa.lo <= 0:
        return None
    peak = (b.A * bb / (b.K * aa)).ln() / (b.A - b.K)
    upper = min(horizon, max(D(0), peak.lo))
    if upper <= 0:
        return None
    f = lambda u: b.v.ready(qi, ji, u) - 1
    if f(I(upper)).lo <= 0:
        return None
    df = lambda u: (-b.K * aa * (-b.K*u).exp()
                    + b.A * bb * (-b.A*u).exp())
    return b.v.root(f, df, D(0), upper, b.v.guessroot(f, upper))


def peak_upper(s, tt):
    """Upper bound on all pre-event READY charges, valid also below r.

    The equation is monotone in starting charge and incoming amplitude.
    A direct interval bound is used whenever the usual peak logarithm
    lacks its positive denominator; it may be loose but never truncates
    the represented trajectory.  Endpoints are always included.
    """
    current, _, _ = b.coefficients(s)
    horizon = tt.minus(s['t']).nonnegative().hi
    q = I(s['q'].hi)
    if current.hi <= 0:
        return max(q.hi, b.R.hi)
    j = I(current.hi)
    bb = j / (b.A - b.K)
    aa = q - b.R + bb
    if aa.lo <= 0:
        return b.v.ready(q, j, I(0, horizon)).hi
    peak = (b.A * bb / (b.K * aa)).ln() / (b.A - b.K)
    at = I(min(horizon, max(D(0), peak.lo)),
           min(horizon, max(D(0), peak.hi)))
    return max(q.hi, b.v.ready(q, j, I(horizon)).hi,
               b.v.ready(q, j, at).hi)


def ready_to(x, tt, key):
    """Runtime adapter for A20/A21 calls, using the corrected elapsed cover."""
    from garde_relative_A22 import ready_to as elapsed_ready_to
    return elapsed_ready_to(x, tt, key)


def install():
    """Install explicitly before executing any A20/A21/A22 continuation."""
    import cycle_local_A20 as cyc
    cyc._ready_to = ready_to
    cyc._scalar_root = scalar_root
    cyc._peak_upper = peak_upper
    return dict(ready_helper='ready_general_A22.ready_to',
                endpoint_domain='[0,1]; no inferred q>=r invariant',
                archived_sources_modified=False)
