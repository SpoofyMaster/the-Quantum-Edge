"""Time-to-event tools for trade paths: competing-risks cumulative incidence (Aalen-Johansen).

For a trade, the first of {target, stop, time-exit} ends the path. Treating stop hits as simple
censoring (plain Kaplan-Meier) would overstate P(target by t); the Aalen-Johansen cumulative
incidence function (CIF) handles the competing risk correctly. Time-exit = administrative censoring.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def cumulative_incidence(durations, causes, horizon: int | None = None) -> pd.DataFrame:
    """durations: bars until the path ended (>=1). causes: 1 = target, -1 = stop, 0 = censored.

    Returns a DataFrame indexed by t = 1..T with columns: at_risk, surv (no event yet),
    cif_target, cif_stop.
    """
    d = np.asarray(durations, int)
    c = np.asarray(causes, int)
    T = int(horizon or d.max())
    n_at_risk = len(d)
    surv = 1.0
    cif_t = cif_s = 0.0
    rows = []
    for t in range(1, T + 1):
        at_t = d == t
        dt = int((at_t & (c == 1)).sum())
        ds = int((at_t & (c == -1)).sum())
        cens = int((at_t & (c == 0)).sum())
        if n_at_risk > 0:
            cif_t += surv * dt / n_at_risk
            cif_s += surv * ds / n_at_risk
            surv *= 1.0 - (dt + ds) / n_at_risk
        rows.append((t, n_at_risk, surv, cif_t, cif_s))
        n_at_risk -= dt + ds + cens
    return pd.DataFrame(rows, columns=["t", "at_risk", "surv", "cif_target", "cif_stop"]).set_index("t")


def median_time_to(cif: pd.Series, level: float) -> float:
    """First t at which the CIF reaches `level` (NaN if never)."""
    hit = cif[cif >= level]
    return float(hit.index[0]) if len(hit) else float("nan")
