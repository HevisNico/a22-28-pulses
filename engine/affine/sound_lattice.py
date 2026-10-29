"""Sound affine min/max for the kernel's clip/cap/clamp reconstructions.

The kernel writes pointwise minima as I(min(x.lo,y.lo),min(x.hi,y.hi)).
On affine forms that rebuilds an uncorrelated interval.  Here:

    amin(x,y) = x            if x.hi <= y.lo   (x(eps) <= y(eps) for every eps)
              = y            if y.hi <= x.lo
              = I(min(x.lo,y.lo), min(x.hi,y.hi))   otherwise (original result)

and symmetrically for amax.  The dominance test compares the two global
ranges, so it never infers an order from endpoints alone (the counterexample
x=eps, y=.1-eps of the audit takes the third branch).  Without symbols
every branch returns exactly the original interval.

Only the listed expressions are substituted in the listed functions; the
substitution is checked textually and refused if the source differs.
"""
import inspect, textwrap
from decimal import Decimal as D
from affine_iv import I


def amin(x, y):
    x = I(x); y = I(y)
    if x.hi <= y.lo:
        return x
    if y.hi <= x.lo:
        return y
    return I(min(x.lo, y.lo), min(x.hi, y.hi))


def amax(x, y):
    x = I(x); y = I(y)
    if x.lo >= y.hi:
        return x
    if y.lo >= x.hi:
        return y
    return I(max(x.lo, y.lo), max(x.hi, y.hi))


# (module, function, [(original text, replacement text), ...])
_EDITS = (
    ('actuations_A19', 'gain', [
        ("age=I(max(D(0),age.lo),max(D(0),age.hi))", "age=amax(I(0),age)"),
        ("return I(min(STEP.lo,max(D(0),x.lo)),min(STEP.hi,max(D(0),x.hi)))", "return amin(STEP,amax(I(0),x))")]),
    ('actuations_A19', 'increment', [
        ("return I(max(D(0),min(x.lo,cap.lo)),max(D(0),min(x.hi,cap.hi)))", "return amax(I(0),amin(x,cap))")]),
    ('actuations_A19', 'clip', [
        ("return I(min(BMAX.lo,x.lo),min(BMAX.hi,x.hi))", "return amin(BMAX,x)")]),
    ('depot_A19', 'value', [
        ("return I(min(x.lo,TARGET.lo),min(x.hi,TARGET.hi))", "return amin(x,TARGET)")]),
    ('dependances_A17', 'tail', [
        ("admitted=I(min(elapsed.lo,duration.lo),min(elapsed.hi,duration.hi))", "admitted=amin(elapsed,duration)"),
        ("after=I(max(D(0),(elapsed-duration).lo),max(D(0),(elapsed-duration).hi))", "after=amax(I(0),elapsed-duration)")]),
)


def install(modules):
    """modules: name -> imported kernel module.  Returns the list of edits."""
    done = []
    for name, func, edits in _EDITS:
        mod = modules[name]
        src = textwrap.dedent(inspect.getsource(getattr(mod, func)))
        for old, new in edits:
            if src.count(old) != 1:
                raise RuntimeError(f'sound_lattice: unexpected source for {name}.{func}')
            src = src.replace(old, new)
        mod.__dict__['amin'] = amin; mod.__dict__['amax'] = amax
        exec(compile(src, mod.__file__, 'exec'), mod.__dict__)
        done.append(f'{name}.{func}')
    return done
