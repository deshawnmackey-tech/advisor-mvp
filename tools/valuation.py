from typing import Dict

import numpy as np
from numba import njit


@njit
def _monte_carlo_dcf(cashflows, discount_rate, n=8000):
    """Numba-accelerated Monte Carlo DCF sampler."""
    t = cashflows.shape[0]
    results = np.empty(n)

    for i in range(n):
        shocks = np.random.normal(1.0, 0.08, size=t)
        adj = cashflows * shocks
        discounted = adj / ((1 + discount_rate) ** np.arange(1, t + 1))
        results[i] = discounted.sum()

    return results


def run_valuation(
    ebitda_ttm: float,
    growth: float,
    discount_rate: float = 0.08,
) -> Dict[str, float]:
    years = np.arange(1, 6)
    cashflows = ebitda_ttm * ((1 + growth) ** years) * 0.75
    sims = _monte_carlo_dcf(cashflows, discount_rate)

    return {
        "ev_mean": float(np.mean(sims)),
        "ev_low": float(np.percentile(sims, 5)),
        "ev_high": float(np.percentile(sims, 95)),
    }
