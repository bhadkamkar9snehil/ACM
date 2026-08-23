"""S2 acceptance: the immune harness catches what code review cannot.

The decisive case is the OMR-class test: a scorer that runs, passes unit
tests, and contributes NOTHING must be flagged by behavior alone.
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl
import pytest

from immune import degeneracy_check, inject, sensitivity_profile
from monitor import AssetMonitor
from store.raw import TIMESTAMP_COL
from tests.marginal_scorer import MarginalRobustZScorer

UTC = timezone.utc
pytestmark = pytest.mark.statistical


def healthy_frame(n=8000, seed=1):
    rng = np.random.default_rng(seed)
    ts = [
        datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=10 * i)
        for i in range(n)
    ]
    base = rng.normal(size=(n, 4))
    base[:, 1] = 0.6 * base[:, 0] + 0.8 * base[:, 1]  # correlated pair
    return pl.DataFrame(
        {
            TIMESTAMP_COL: pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
            "temp": base[:, 0],
            "vib": base[:, 1],
            "press": base[:, 2],
            "flow": base[:, 3],
        }
    )


class ZeroScorerMonitor(AssetMonitor):
    """The OMR incident, reconstructed: calibrates fine, scores nothing."""

    def calibrate(self, calib_frame, seed=0):
        ok = super().calibrate(calib_frame, seed=seed)
        if ok:
            scorer = self.scorer
            scorer.score = lambda frame: np.zeros(frame.height)  # dead
        return ok


def test_profile_detects_canonical_faults():
    report = sensitivity_profile("synt/ok", healthy_frame())
    assert report.conformance_ok, "clean holdout must not alarm"
    assert not report.degenerate
    assert not report.scorer_dead
    for fc in ("drift", "step", "variance"):
        assert report.floors[fc] is not None, f"{fc} never detected"
    assert report.floors["step"] <= 2.0


def test_marginal_scorer_is_blind_to_correlation_break():
    """A per-channel marginal scorer cannot see a correlation break.

    This negative control is the permanent reason the production scorer is
    conditional. The production flip is pinned in test_surprise.py.
    """

    def marginal_monitor(key):
        return AssetMonitor(key, scorer_cls=MarginalRobustZScorer)

    report = sensitivity_profile(
        "synt/blind", healthy_frame(), monitor_cls=marginal_monitor
    )
    assert report.floors["correlation_break"] is None


def test_omr_class_dead_scorer_is_caught():
    report = sensitivity_profile(
        "synt/dead", healthy_frame(), monitor_cls=ZeroScorerMonitor
    )
    assert report.degenerate
    assert report.scorer_dead
    assert all(f is None for f in report.floors.values())


def test_degeneracy_check_direct():
    assert degeneracy_check(np.zeros(1000))
    assert degeneracy_check(np.full(1000, 3.14))
    assert not degeneracy_check(np.random.default_rng(0).normal(size=1000))


def test_injectors_preserve_clean_prefix():
    frame = healthy_frame(n=2000)
    for fc in ("drift", "step", "variance", "correlation_break"):
        faulty, col = inject(frame, fc, magnitude=3.0)
        onset = int(2000 * 0.2)
        pre_orig = frame.get_column(col).to_numpy()[: onset - 1]
        pre_fault = faulty.get_column(col).to_numpy()[: onset - 1]
        np.testing.assert_array_equal(pre_orig, pre_fault)


def test_report_serializes():
    report = sensitivity_profile("synt/ser", healthy_frame(n=4000))
    d = report.to_dict()
    assert d["asset_key"] == "synt/ser"
    assert "profile" in d and "floors" in d and "scorer_dead" in d
