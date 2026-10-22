import numpy as np

CURVES = {
    "SI": (0.14, 0.02),
    "VI": (13.5, 1.0),
    "EI": (80.0, 2.0),
    "LTI": (120.0, 1.0),
}


def trip_time(I, pickup, tms, curve="SI", inst=None):
    k, a = CURVES[curve]
    I = np.asarray(I, dtype=float)
    m = I / pickup
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(m > 1.0, tms * k / (m ** a - 1.0), np.inf)
    if inst is not None:
        t = np.where(I >= inst, np.minimum(t, 0.05), t)
    return t
