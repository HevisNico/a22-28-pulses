"""Audited time difference for A22; archived A20 files remain unchanged.

No container-key shortcut: cancellation uses complete affine expressions.
This does not establish the physical identity of an atom named by a caller.
"""
import dependances_A17 as dep
import intervalles_decimaux as iv
from intervalles_decimaux import I
from temps_symboliques_A22 import relative, fraction_to_decimal_exact
import flux_charge_A19 as flux
_ORIGINAL_TRANSFER = flux.transfer

# Bounded, exact numerical reuse. Keys include endpoint REPRESENTATIONS and
# every Decimal context setting/trap. Values are immutable endpoints and the
# flags raised by the original operation, never a mutable interval.
_TRANSCENDENTAL_CACHE = {}
_CACHE_LIMIT = 8192

def _context_key(context):
    return (context.prec, context.rounding, context.Emin, context.Emax,
            context.capitals, context.clamp, tuple(context.traps.items()))

def _decimal_transcendental(value, kind, context, settings):
    key = (kind, str(value), settings)
    cached = _TRANSCENDENTAL_CACHE.get(key)
    if cached is None:
        local = context.copy()
        local.clear_flags()
        try:
            result = local.exp(value) if kind == 'exp' else local.ln(value)
        finally:
            raised = tuple(signal for signal, flag in local.flags.items() if flag)
            for signal in raised:
                context.flags[signal] = True
        cached = (result, raised)
        if len(_TRANSCENDENTAL_CACHE) >= _CACHE_LIMIT:
            _TRANSCENDENTAL_CACHE.clear()
        _TRANSCENDENTAL_CACHE[key] = cached
    else:
        for signal in cached[1]:
            context.flags[signal] = True
    return cached[0]

def _transcendental(self, kind):
    if kind == 'exp' and self.lo == self.hi == 0:
        return I(1)
    if kind == 'ln':
        assert self.lo > 0
        if self.lo == self.hi == 1:
            return I(0)
    context = iv.NEAR
    settings = _context_key(context)
    # Same operations and evaluation order as the original interval methods.
    # Only the costly correctly-rounded exp/ln calls are reused.
    lo = context.next_minus(_decimal_transcendental(self.lo, kind, context, settings))
    hi = context.next_plus(_decimal_transcendental(self.hi, kind, context, settings))
    return I(lo, hi)

def exact_exp(self):
    return _transcendental(self, 'exp')

def exact_ln(self):
    return _transcendental(self, 'ln')

_DIFFERENCE_CACHE = {}
_TRANSFER_CACHE = {}

def _memo_interval(cache, key, contexts, function, arguments):
    cached = cache.get(key)
    if cached is None:
        previous = tuple(dict(ctx.flags) for ctx in contexts)
        for ctx in contexts:
            ctx.clear_flags()
        try:
            result = function(*arguments)
        finally:
            raised = tuple(tuple(signal for signal, flag in ctx.flags.items() if flag)
                           for ctx in contexts)
            for ctx, old in zip(contexts, previous):
                for signal, flag in old.items():
                    if flag:
                        ctx.flags[signal] = True
        cached = result.lo, result.hi, raised
        if len(cache) >= _CACHE_LIMIT:
            cache.clear()
        cache[key] = cached
    else:
        for ctx, raised in zip(contexts, cached[2]):
            for signal in raised:
                ctx.flags[signal] = True
    return I(cached[0], cached[1])

def _difference_reference(constant, terms):
    result=I(fraction_to_decimal_exact(constant))
    for key,coefficient,bounds in terms:
        result=result+coefficient*I(*bounds)
    return result

def safe_minus(self,other):
    # Validation ALWAYS runs before reuse; mutable endpoints and registry
    # deletions/changes cannot be hidden behind a cached numerical result.
    constant,terms=relative(self,other)
    contexts=(iv.DOWN,iv.UP)
    key=(constant,terms,tuple(_context_key(ctx) for ctx in contexts))
    return _memo_interval(_DIFFERENCE_CACHE,key,contexts,
                          _difference_reference,(constant,terms))

def exact_transfer(s,lam,high,low,scale):
    if type(lam) is not I:
        return _ORIGINAL_TRANSFER(s,lam,high,low,scale)
    high=I(high);low=I(low);scale=I(scale)
    # Preserve the original early maximum calculation and its exceptions.
    maximum=scale*(high-low)
    assert s.end is not None
    if s.full_start and s.full_end:
        return maximum
    # Only the relative expressions actually used by the original formula
    # enter the key. Every one is validated afresh, including zero terms.
    if s.full_end:
        times=(relative(s.start,s.origin),)
    elif s.full_start:
        times=(relative(s.end,s.origin),)
    else:
        times=(relative(s.start,s.origin),relative(s.end,s.start))
    lam_value=I(lam)
    contexts=(iv.DOWN,iv.UP,iv.NEAR)
    key=(bool(s.full_start),bool(s.full_end),times,
         tuple(tuple(value.pair()) for value in (lam_value,high,low,scale)),
         tuple(_context_key(ctx) for ctx in contexts))
    return _memo_interval(_TRANSFER_CACHE,key,contexts,_ORIGINAL_TRANSFER,
                          (s,lam,high,low,scale))

def install():
    import identite_temps_A22
    identite_temps_A22.install()
    dep.Time.minus=safe_minus
    I.exp=exact_exp
    I.ln=exact_ln
    import actuations_A19 as ac
    import depot_A19 as depot
    flux.transfer=exact_transfer
    # Recovery keeps transfer(s), which supplies its physical parameters.
    # Only its imported generic five-argument dependency is replaced.
    ac.charge_transfer=exact_transfer
    depot.transfer=exact_transfer

def require_certifier_assertions():
    # The inherited hybrid kernel uses assertions as proof obligations.
    # Fixing exact arithmetic alone does not make that kernel safe under -O.
    if not __debug__:
        raise RuntimeError('Hybrid certification requires assertions enabled; Python -O/-OO is not supported')
