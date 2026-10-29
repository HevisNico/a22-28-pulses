"""Fix P (v3.3): one affine symbol per physical port, used only for that port.

The model gives every cell independent auxiliary constants per port
i in {0,1,2}: LM_i, LS_i, LE_i, M_i (and C_i).  v3.2 used ONE symbol per cell
for each constant (too strong: it forced LM_0 = LM_1 = LM_2).  The fresh-launch
package replaced them by plain interval boxes (sound, but every evaluation then
forgets that a port's constant is the same at every pulse, and the enclosures
grow ~5-10x by layer 17).

Here each port j gets its own symbol eps_{cell,name,j} in [-1,1]:
    LM_j = LM_nom (1 + 1e-4 eps_{LM,j})   (same for LS, LE, M)
and that symbol is used ONLY where the kernel evaluates a quantity of port j:
  * event timing of port j in unit():   D0_j (from M_j), DM_j, DS_j, DE_j;
  * coefficients(): the mark current of port j (LM_j) and the error-deposit
    current of port j (LE_j);
  * actuation (recovery actuator b): every mark segment s uses LM_{s.port}
    (its charge, increment, transfer, primitive and DM test);
  * deposits: the history of port j uses LE_j.
Every other use keeps the plain box of the fresh-launch package (b.settings).
C is kept as a plain box everywhere.

Soundness.  A trajectory of the model is a choice of the 15 port constants of
the cell.  Setting eps_{name,j} to the value that gives port j's constant, and
giving every remaining plain-box occurrence that same constant (it lies in the
box), reproduces the trajectory inside every affine form.  A symbol never
stands for two different physical quantities, so no non-existent correlation
is imposed.  Mixed use (symbol in one place, plain box in another) only adds
freedom.

Implementation.  The kernel's actuation and deposit functions read the module
globals LAM/DM/MU (actuations_A19) and LAM (depot_A19) at call time.  The
wrappers below set them to port j's values for the duration of one segment's
evaluation and restore the plain box afterwards.  No kernel file is modified.
"""
from decimal import Decimal as D
from experiment_parameters import PHYSICAL_EPSILON

PORTS = range(3)
# Tests that pin every symbol to radius 0 (exact-parameter sampling) turn this
# off; a campaign always runs with it on.
COVER_CHECK = True
ORIGINAL = {}


def install(engine):
    b, I, iv, v = engine.b, engine.I, engine.iv, engine.v
    ac, dz = b.ac, b.dz
    plain_settings = engine.settings_cell

    def settings(cell):
        plain_settings(cell)          # plain boxes everywhere + checks
        A, K, RM = b.A, b.K, b.RM
        sym = lambda name, j: 1 + I.symbol(f'{cell}:{name}:{j}', PHYSICAL_EPSILON)
        LM = tuple(v.LM * sym('LM', j) for j in PORTS)
        LS = tuple(v.LS * sym('LS', j) for j in PORTS)
        LE = tuple(v.LE * sym('LE', j) for j in PORTS)
        M = tuple(v.M * sym('M', j) for j in PORTS)

        def hh(u): return A / (A - K) * ((-K * u).exp() - (-A * u).exp())

        def dh(u): return A / (A - K) * (A * (-A * u).exp() - K * (-K * u).exp())
        D0 = []
        for j in PORTS:
            f = lambda u, m=M[j]: RM + m * hh(u) - 1
            D0.append(v.root(f, lambda u, m=M[j]: m * dh(u), D(0), D('.1'), .02))
        b.D0_PORTS = tuple(D0)
        b.DM_PORTS = tuple(I('1.25').ln() / x for x in LM)
        b.DS_PORTS = tuple(I(8).ln() / x for x in LS)
        b.DE_PORTS = tuple(I(4).ln() / x for x in LE)
        b.LM_PORTS, b.LE_PORTS = LM, LE
        ac.PORT_LAM = LM
        ac.PORT_DM = b.DM_PORTS
        ac.PORT_MU = tuple((1 - 4 * I('1.25').ln()) / x for x in LM)
        dz.PORT_LAM = LE
        # Each port constant covers the model's whole parameter box (the plain
        # box encodes the same set; the affine form is wider by coefficient
        # rounding only), derived durations agree with the plain enclosures,
        # and the kernel's own timing inequalities hold for every port.
        for j in PORTS:
            for name, x, box in (('LM', LM[j], b.LM), ('LS', LS[j], b.LS), ('LE', LE[j], b.LE), ('M', M[j], b.M)):
                if COVER_CHECK and not (x.lo <= box.lo and box.hi <= x.hi):
                    raise RuntimeError(f'port_symbols: {name}_{j} does not cover the parameter box')
            for name, x, box in (('D0', D0[j], b.D0), ('DM', b.DM_PORTS[j], b.DM), ('DS', b.DS_PORTS[j], b.DS),
                                 ('DE', b.DE_PORTS[j], b.DE)):
                if not (x.lo <= box.hi and box.lo <= x.hi):
                    raise RuntimeError(f'port_symbols: {name}_{j} inconsistent with its plain enclosure')
            assert (b.D1 + b.DM_PORTS[j] + b.DS_PORTS[j] + b.DE_PORTS[j]).hi < D('1.3')
            assert (D0[j] + b.DM_PORTS[j] + b.DS_PORTS[j] + b.DE_PORTS[j]).lo > 1
            assert (D0[j] + b.DM_PORTS[j] + b.DS_PORTS[j]).lo > 1 and (b.D1 + b.DM_PORTS[j] + b.DS_PORTS[j]).lo > 1
            assert ac.PORT_DM[j].hi < 1
    engine.settings_cell = settings

    # ---- actuation: per-segment port context --------------------------
    def with_port(port, fn, *args):
        saved = ac.LAM, ac.DM, ac.MU
        ac.LAM, ac.DM, ac.MU = ac.PORT_LAM[port], ac.PORT_DM[port], ac.PORT_MU[port]
        try:
            return fn(*args)
        finally:
            ac.LAM, ac.DM, ac.MU = saved
    o_charge, o_increment, o_transfer = ac.charge, ac.increment, ac.transfer
    o_final = ac.final_potential
    ac.charge = lambda s, t: with_port(s.port, o_charge, s, t)
    ac.increment = lambda s, t, live=False: with_port(s.port, o_increment, s, t, live)
    ac.transfer = lambda s: with_port(s.port, o_transfer, s)
    ac.final_potential = lambda s: with_port(s.port, o_final, s)

    def raw_dose(h, t, live=False):
        """actuations_A19.raw_dose, each mark evaluated with its own port."""
        assert h.fire is not None
        section = h.fire.plus(1); elapsed = t.minus(section).nonnegative()
        if elapsed.hi == 0: return I(0)
        out = ac.baseline(h) * elapsed
        for s in h.marks:
            def contribution(s=s):
                if not s.full_start:
                    assert ac.DM.hi < 1
                    return ac.final_potential(s) * elapsed
                initial_age = section.minus(s.origin)
                before_section = (s.end is not None and section.minus(s.end).lo >= 0)
                if before_section or initial_age.lo >= ac.DM.hi:
                    return ac.STEP * elapsed
                return ac.primitive(t.minus(s.origin), live and s.full_end) - ac.primitive(initial_age)
            out = out + with_port(s.port, contribution)
        return out
    ORIGINAL['raw_dose'] = ac.raw_dose
    ac.raw_dose = raw_dose

    # ---- deposits: a history of port j uses LE_j ---------------------
    def port_of(h):
        ports = {s.port for s in h.partial} | ({h.active.port} if h.active is not None else set())
        return ports.pop() if len(ports) == 1 else None

    def with_deposit_port(h, fn, *args):
        p = port_of(h)
        if p is None: return fn(*args)
        saved = dz.LAM; dz.LAM = dz.PORT_LAM[p]
        try:
            return fn(*args)
        finally:
            dz.LAM = saved
    o_offered = dz.offered
    dz.offered = lambda h, t: with_deposit_port(h, o_offered, h, t)
    o_fold = engine._fold
    engine._fold = lambda h: with_deposit_port(h, o_fold, h) if isinstance(h, dz.History) else o_fold(h)

    return dict(fix='P (v3.3): per-port symbols for LM, LS, LE, M; C plain',
                scope='Symbol of port j used only for quantities of port j; plain box elsewhere')
