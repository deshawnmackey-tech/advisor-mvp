"""
Monte Carlo DCF valuation.

Uses plain NumPy — no Numba/JIT dependency.  8,000 simulations run in
under 10ms on a single core, which is fast enough for any advisory use case.
"""

import numpy as np


def _monte_carlo_dcf(
    cashflows: np.ndarray,
    discount_rate: float,
    n: int = 8000,
) -> np.ndarray:
    """Vectorised Monte Carlo DCF — no JIT needed."""
    t = cashflows.shape[0]
    # (n, t) shock matrix
    shocks = np.random.default_rng().normal(1.0, 0.08, size=(n, t))
    adj = cashflows * shocks                            # (n, t)
    periods = np.arange(1, t + 1, dtype=float)
    discount = (1 + discount_rate) ** periods           # (t,)
    discounted = adj / discount                         # (n, t)
    return discounted.sum(axis=1)                       # (n,)


def run_valuation(
    ebitda_ttm: float,
    growth: float,
    discount_rate: float = 0.08,
) -> dict:
    """
    5-year Monte Carlo DCF valuation.

    Returns a dict with ev_mean, ev_low (5th pct), and ev_high (95th pct).
    """
    years = np.arange(1, 6)
    cashflows = ebitda_ttm * ((1 + growth) ** years) * 0.75
    sims = _monte_carlo_dcf(cashflows, discount_rate)

    return {
        "ev_mean": round(float(np.mean(sims)), 2),
        "ev_low":  round(float(np.percentile(sims, 5)), 2),
        "ev_high": round(float(np.percentile(sims, 95)), 2),
    }
