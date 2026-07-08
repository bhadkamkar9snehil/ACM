"""Prognostics (S8, gem C5): failure-time distributions from health drift.

The health index is the windowed mean surprise - already standardized,
already conditional. A healthy asset's index is stationary; a degrading
one's drifts upward. Model the index as a Wiener process with drift
(estimated robustly from increments); the first-passage time to the
critical level is then Inverse Gaussian - a closed-form failure-time
distribution with credible intervals, from the asset's own trajectory.
Classical degradation theory, no labels, no tuning.

SELF-GATING (D8, absolute): a horizon is exposed ONLY when
- the upward trend is real (Kendall tau over the trend window clears the
  drift threshold - the same statistic the shape classifier trusts), and
- there is enough trajectory to estimate drift (MIN_INDEX_SAMPLES), and
- the estimated drift is positive.
Otherwise the verdict carries trend evidence WITHOUT a date. Never show an
uncalibrated horizon; never hide a calibrated one.

Critical level: derived from the asset's own ledger when possible (the
lowest health-index level at which a past episode alarmed); until the
first episode exists, a provisional structural default (healthy center +
CRIT_SIGMAS spreads) is used and REPORTED AS PROVISIONAL in the output.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from acm2.novelty import DRIFT_TAU, kendall_tau

MIN_INDEX_SAMPLES = 24
CRIT_SIGMAS = 6.0  # provisional critical level: center + 6 spreads
_IG_QUANTILE_GRID = 4096


@dataclass(frozen=True)
class Horizon:
    gated: bool  # False = do not display a date (trend evidence only)
    reason: str
    median_steps: float | None = None
    p10_steps: float | None = None
    p90_steps: float | None = None
    critical_level: float | None = None
    provisional_level: bool = True
    drift_per_step: float | None = None

    def to_dict(self) -> dict:
        return {
            "gated": self.gated,
            "reason": self.reason,
            "median_steps": self.median_steps,
            "p10_steps": self.p10_steps,
            "p90_steps": self.p90_steps,
            "critical_level": self.critical_level,
            "provisional_level": self.provisional_level,
            "drift_per_step": self.drift_per_step,
        }


def critical_level(
    healthy_center: float,
    healthy_spread: float,
    ledger_onset_levels: list[float] | None = None,
) -> tuple[float, bool]:
    """(level, provisional). Prefers the asset's own episode history."""
    if ledger_onset_levels:
        return float(min(ledger_onset_levels)), False
    return healthy_center + CRIT_SIGMAS * max(healthy_spread, 1e-9), True


def _ig_quantiles(mu_fp: float, lam: float, qs: np.ndarray) -> np.ndarray:
    """Inverse Gaussian quantiles by numeric CDF inversion (scipy-free).

    CDF(t) = Phi(sqrt(lam/t)(t/mu - 1)) + exp(2 lam / mu) *
             Phi(-sqrt(lam/t)(t/mu + 1))
    """
    from math import erf

    def phi(x: np.ndarray) -> np.ndarray:
        return 0.5 * (1.0 + np.vectorize(erf)(x / np.sqrt(2.0)))

    t = np.linspace(mu_fp / 50.0, mu_fp * 20.0, _IG_QUANTILE_GRID)
    a = np.sqrt(lam / t) * (t / mu_fp - 1.0)
    b = -np.sqrt(lam / t) * (t / mu_fp + 1.0)
    # log-domain guard for the exp term
    log_term = np.minimum(2.0 * lam / mu_fp, 700.0)
    cdf = phi(a) + np.exp(log_term) * phi(b)
    cdf = np.clip(cdf, 0.0, 1.0)
    return np.interp(qs, cdf, t)


def horizon(
    index: np.ndarray,
    healthy_center: float,
    healthy_spread: float,
    ledger_onset_levels: list[float] | None = None,
) -> Horizon:
    """Failure-time distribution (in index steps) or a gated refusal."""
    h = np.asarray(index, dtype=np.float64)
    h = h[np.isfinite(h)]
    if h.size < MIN_INDEX_SAMPLES:
        return Horizon(False, "insufficient trajectory")
    tau = kendall_tau(h[-min(h.size, 400) :])
    if tau <= DRIFT_TAU:
        return Horizon(False, f"no significant upward trend (tau={tau:.2f})")
    inc = np.diff(h)
    mu = float(np.median(inc))  # robust drift
    sigma = 1.4826 * float(np.median(np.abs(inc - mu)))
    sigma = max(sigma, 1e-9)
    if mu <= 0:
        return Horizon(False, "drift estimate not positive")
    level, provisional = critical_level(
        healthy_center, healthy_spread, ledger_onset_levels
    )
    remaining = level - float(h[-1])
    if remaining <= 0:
        return Horizon(
            True,
            "critical level already reached",
            median_steps=0.0,
            p10_steps=0.0,
            p90_steps=0.0,
            critical_level=level,
            provisional_level=provisional,
            drift_per_step=mu,
        )
    mu_fp = remaining / mu  # mean first-passage time (steps)
    lam = (remaining / sigma) ** 2
    p10, p50, p90 = _ig_quantiles(mu_fp, lam, np.array([0.1, 0.5, 0.9]))
    return Horizon(
        True,
        "drift-calibrated",
        median_steps=float(p50),
        p10_steps=float(p10),
        p90_steps=float(p90),
        critical_level=level,
        provisional_level=provisional,
        drift_per_step=mu,
    )
