from dataclasses import dataclass
import math
import numpy as np
from .curves import trip_time, CURVES

CT_PRIMARIES = [50, 100, 150, 200, 300, 400, 600, 800, 1000, 1200, 1500, 2000]
T_INST = 0.05


@dataclass
class RelaySetting:
    name: str
    bus: int
    load_a: float
    ct: int
    pickup: float
    tms: float
    curve: str
    inst: float | None


def pickup_setting(load_a, overload, step=0.05):
    ct = next(c for c in CT_PRIMARIES if c >= load_a)
    ps = math.ceil(overload * load_a / ct / step - 1e-9) * step
    return ct, round(ps * ct, 3)


def _unit_time(I, pickup, curve):
    k, a = CURVES[curve]
    return k / ((I / pickup) ** a - 1.0)


def fault_beyond(feeder, relay):
    return feeder.fault_3ph(relay.bus, "max")


def constraints(feeder, up, down):
    imax = fault_beyond(feeder, down)
    pts = [(imax, float(trip_time(imax, down.pickup, down.tms, down.curve, down.inst)))]
    if down.inst is not None and down.inst < imax:
        i_idmt = down.inst * 0.999
        pts.append((i_idmt, float(trip_time(i_idmt, down.pickup, down.tms, down.curve))))
    return pts


def grade(feeder, curve="SI", cti=0.3, tms_min=0.05, tms_step=0.01, inst_factor=1.3):
    rel = feeder.relays
    n = len(rel)
    out = [None] * n
    for k in reversed(range(n)):
        name, bus, load, ovl = rel[k]
        ct, ps = pickup_setting(load, ovl)
        inst = None
        if k < n - 1 and rel[k + 1][1] > bus:
            inst = inst_factor * feeder.fault_3ph(rel[k + 1][1], "max")
            if inst >= feeder.fault_3ph(bus, "max"):
                inst = None
        s = RelaySetting(name, bus, load, ct, ps, tms_min, curve, inst)
        if k < n - 1:
            need = max((t + cti) / _unit_time(I, ps, curve) for I, t in constraints(feeder, s, out[k + 1]))
            s.tms = round(max(tms_min, math.ceil(need / tms_step - 1e-9) * tms_step), 9)
        out[k] = s
    return out


def grade_lp(feeder, settings, cti=0.3, tms_min=0.05):
    from scipy.optimize import linprog
    n = len(settings)
    A, b = [], []
    for k in range(n - 1):
        up, dn = settings[k], settings[k + 1]
        imax = fault_beyond(feeder, dn)
        pts = [imax]
        if dn.inst is not None and dn.inst < imax:
            pts.append(dn.inst * 0.999)
        for I in pts:
            row = np.zeros(n)
            row[k] = -_unit_time(I, up.pickup, up.curve)
            rhs = -cti
            if dn.inst is not None and I >= dn.inst:
                rhs -= T_INST
            else:
                row[k + 1] = _unit_time(I, dn.pickup, dn.curve)
            A.append(row)
            b.append(rhs)
    res = linprog(np.ones(n), A_ub=A, b_ub=b, bounds=[(tms_min, None)] * n, method="highs")
    if not res.success:
        raise RuntimeError(res.message)
    return res.x


def check_margins(feeder, settings, points=600):
    lo = feeder.fault_2ph_min(len(feeder.buses) - 1)
    out = []
    for k in range(len(settings) - 1):
        up, dn = settings[k], settings[k + 1]
        I = np.geomspace(lo, fault_beyond(feeder, dn), points)
        tu = trip_time(I, up.pickup, up.tms, up.curve, up.inst)
        td = trip_time(I, dn.pickup, dn.tms, dn.curve, dn.inst)
        ok = np.isfinite(td)
        out.append(float(np.min(tu[ok] - td[ok])))
    return out


def sensitivity(feeder, settings):
    last = len(feeder.buses) - 1
    out = []
    for s in settings:
        end = s.bus if s.name.startswith("Incomer") else min(s.bus + 1, last)
        out.append((feeder.buses[end], feeder.fault_2ph_min(end) / s.pickup))
    return out
