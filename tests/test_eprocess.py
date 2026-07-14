"""E-process acceptance + the D12 gating spike (empirical alpha conformance).

The Ville bound must HOLD EMPIRICALLY, including under serial dependence
with block aggregation - this is the one gate nothing may pass in parallel
(implementation plan 10.4).
"""

import numpy as np
import pytest

from decision import EProcess, EProcessBank

RNG = np.random.default_rng(42)


def ar1(n, phi=0.7, rng=None):
    rng = rng or RNG
    x = np.empty(n)
    x[0] = rng.normal()
    innovations = rng.normal(size=n) * np.sqrt(1 - phi**2)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + innovations[i]
    return x


# ---------------------------------------------------------------- validity
def test_ville_bound_iid_healthy():
    """False-alarm rate over many iid-healthy runs must be <= alpha
    (with slack for Monte Carlo noise: bound 2x alpha at alpha=0.05)."""
    alpha, runs, alarms = 0.05, 200, 0
    for r in range(runs):
        rng = np.random.default_rng(1000 + r)
        ep = EProcess(rng.normal(size=500), alpha=alpha, seed=r)
        ep.update(rng.normal(size=2000))
        alarms += ep.alarmed
    assert alarms / runs <= 2 * alpha, f"{alarms}/{runs} false alarms"


def test_ville_bound_ar1_with_blocks():
    """THE D12 GATE: AR(1)-correlated healthy scores, block aggregation on.
    Blocks (size 24) far exceed the phi=0.7 correlation length (~3)."""
    alpha, runs, alarms = 0.05, 150, 0
    for r in range(runs):
        rng = np.random.default_rng(5000 + r)
        calib = ar1(3000, phi=0.7, rng=rng)
        ep = EProcess(calib, alpha=alpha, block_size=24, seed=r)
        ep.update(ar1(6000, phi=0.7, rng=rng))
        alarms += ep.alarmed
    assert alarms / runs <= 2 * alpha, f"{alarms}/{runs} false alarms under AR(1)"


def test_ar1_without_blocks_is_invalid_hence_blocks_required():
    """Documents WHY blocks exist: raw-tick betting on AR(1) data inflates
    false alarms. If this ever stops failing-without-blocks, revisit D12."""
    alpha, runs, alarms = 0.05, 60, 0
    for r in range(runs):
        rng = np.random.default_rng(9000 + r)
        calib = ar1(3000, phi=0.95, rng=rng)
        ep = EProcess(calib, alpha=alpha, block_size=1, seed=r)
        ep.update(ar1(6000, phi=0.95, rng=rng))
        alarms += ep.alarmed
    # strongly autocorrelated raw ticks: expect a materially inflated rate
    assert alarms / runs > 2 * alpha, (
        "raw-tick AR(1) no longer violates the bound; block-size rationale "
        "may need re-derivation"
    )


# ------------------------------------------------------------------ power
def test_detects_one_sigma_shift():
    rng = np.random.default_rng(7)
    ep = EProcess(rng.normal(size=1000), alpha=0.05, block_size=6, seed=7)
    ep.update(rng.normal(size=600))  # healthy prefix
    assert not ep.alarmed
    ep.update(rng.normal(loc=1.0, size=1200))  # shifted regime
    assert ep.alarmed, "1-sigma persistent shift must be detected"


def test_detects_slow_drift():
    rng = np.random.default_rng(8)
    ep = EProcess(rng.normal(size=1000), alpha=0.05, block_size=6, seed=8)
    drift = rng.normal(size=3000) + np.linspace(0, 1.5, 3000)
    ep.update(drift)
    assert ep.alarmed, "slow drift to 1.5 sigma must accumulate to alarm"


def test_alarm_latches():
    rng = np.random.default_rng(9)
    ep = EProcess(rng.normal(size=1000), alpha=0.05, seed=9)
    ep.update(rng.normal(loc=3.0, size=500))
    assert ep.alarmed
    ep.update(rng.normal(size=2000))  # back to normal
    assert ep.alarmed, "alarm must latch until episode re-anchor"


# ------------------------------------------------------------------- bank
def test_bank_budget_and_multiscale():
    rng = np.random.default_rng(10)
    bank = EProcessBank(
        rng.normal(size=3000), alpha=0.05, block_sizes=(1, 6, 36), seed=10
    )
    state = bank.update(rng.normal(size=1000))
    assert not state.alarmed
    assert 0.0 <= state.evidence < 1.0
    state = bank.update(rng.normal(loc=1.5, size=2000))
    assert state.alarmed
    assert state.evidence >= 1.0
    assert set(state.member_states) == {1, 6, 36}


def test_bank_derives_blocks_from_autocorrelation():
    """No hardcoded block sizes: an AR(1) calibration must yield a base
    block larger than its correlation length; iid yields base 1."""
    rng = np.random.default_rng(20)
    iid_bank = EProcessBank(rng.normal(size=3000), alpha=0.05, seed=20)
    assert iid_bank.block_sizes[0] <= 2
    corr_bank = EProcessBank(ar1(6000, phi=0.9, rng=rng), alpha=0.05, seed=21)
    assert corr_bank.block_sizes[0] >= 5
    # derived members always retain >= 30 calibration blocks each
    for m in corr_bank.members:
        assert m._calib_sorted.size >= 30


def test_derived_bank_holds_ville_bound_on_ar1():
    """The self-derived block size must itself pass the D12 gate."""
    alpha, runs, alarms = 0.05, 100, 0
    for r in range(runs):
        rng = np.random.default_rng(30_000 + r)
        calib = ar1(4000, phi=0.85, rng=rng)
        bank = EProcessBank(calib, alpha=alpha, seed=r)
        bank.update(ar1(8000, phi=0.85, rng=rng))
        alarms += bank.state().alarmed
    assert alarms / runs <= 2 * alpha, f"{alarms}/{runs} false alarms"


def test_calibration_too_small_rejected():
    with pytest.raises(ValueError, match="calibration"):
        EProcess(np.arange(10.0), alpha=0.05)
