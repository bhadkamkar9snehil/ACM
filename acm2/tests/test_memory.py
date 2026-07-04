"""S3 acceptance: mergeability exactness, derivability, ledger hygiene,
and THE FROG TEST - a slow undetected drift must not eat the baseline."""

from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl

from acm2.memory import (
    Episode,
    EpisodeLedger,
    LifetimeBaseline,
    build_period_summary,
    merge_summaries,
)
from acm2.monitor import AssetMonitor
from acm2.store.raw import TIMESTAMP_COL, RawStore

UTC = timezone.utc


def month_frame(year, month, n=1000, seed=0, offset=0.0):
    rng = np.random.default_rng(seed)
    start = datetime(year, month, 1, tzinfo=UTC)
    ts = [start + timedelta(minutes=30 * i) for i in range(n)]
    return pl.DataFrame(
        {
            TIMESTAMP_COL: pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
            "temp": rng.normal(loc=offset, size=n),
            "vib": rng.normal(loc=5.0 + offset, scale=2.0, size=n),
        }
    )


# ------------------------------------------------------- mergeability
def test_merge_matches_full_computation():
    """count/mean/variance merge must be EXACT; quantiles within grid error."""
    a = month_frame(2025, 1, seed=1)
    b = month_frame(2025, 2, seed=2, offset=1.0)
    full = pl.concat([a, b])
    merged = merge_summaries(
        [build_period_summary("a", a), build_period_summary("b", b)]
    )
    cs = merged.channels["temp"]
    x = full.get_column("temp").to_numpy()
    assert cs.count == x.size
    np.testing.assert_allclose(cs.mean, x.mean(), rtol=1e-10)
    np.testing.assert_allclose(cs.variance, x.var(), rtol=1e-6)
    np.testing.assert_allclose(cs.quantile(0.5), np.median(x), atol=0.05)
    np.testing.assert_allclose(
        cs.quantile(0.9), np.quantile(x, 0.9), atol=0.08
    )


def test_merge_is_associative_enough():
    """Merging in any grouping converges to the same statistics."""
    parts = [
        build_period_summary(str(i), month_frame(2025, i + 1, seed=i))
        for i in range(4)
    ]
    left = merge_summaries([merge_summaries(parts[:2]), merge_summaries(parts[2:])])
    flat = merge_summaries(parts)
    np.testing.assert_allclose(
        left.channels["vib"].mean, flat.channels["vib"].mean, rtol=1e-10
    )
    np.testing.assert_allclose(
        left.channels["vib"].variance,
        flat.channels["vib"].variance,
        rtol=1e-6,
    )


# ---------------------------------------------------------- ledger
def test_ledger_masks_episode_windows(tmp_path):
    ledger = EpisodeLedger(tmp_path / "ledger.json")
    ledger.add(
        Episode(
            asset_key="a1",
            start="2025-01-05T00:00:00+00:00",
            end="2025-01-10T00:00:00+00:00",
            state="alarm",
        )
    )
    frame = month_frame(2025, 1, n=2000)
    masked = ledger.mask("a1", frame)
    assert masked.height < frame.height
    ts = masked.get_column(TIMESTAMP_COL)
    gap_start = datetime(2025, 1, 5, tzinfo=UTC)
    gap_end = datetime(2025, 1, 10, tzinfo=UTC)
    assert masked.filter((ts >= gap_start) & (ts <= gap_end)).is_empty()
    # persistence roundtrip
    reloaded = EpisodeLedger(tmp_path / "ledger.json")
    assert len(reloaded.episodes) == 1


# ------------------------------------------------------ derivability
def test_rebuild_with_cache_equals_without(tmp_path):
    store = RawStore(tmp_path / "raw")
    for m in range(1, 7):
        store.append("d1", month_frame(2025, m, seed=m))
    no_cache = LifetimeBaseline.build(store, "d1")
    cache_root = tmp_path / "memcache"
    first = LifetimeBaseline.build(store, "d1", cache_root=cache_root)
    second = LifetimeBaseline.build(store, "d1", cache_root=cache_root)  # cached
    for col in no_cache.medians:
        np.testing.assert_allclose(first.medians[col], no_cache.medians[col], rtol=1e-9)
        np.testing.assert_allclose(second.medians[col], first.medians[col], rtol=1e-12)
        np.testing.assert_allclose(second.scales[col], first.scales[col], rtol=1e-12)
    assert (cache_root / "d1").exists()  # closed periods cached


# -------------------------------------------------------- THE FROG TEST
def test_frog_slow_drift_cannot_eat_the_baseline(tmp_path):
    """12 healthy months, then 2 months of undetected upward drift in
    'temp'. The lifetime baseline must stay anchored near the healthy
    median; a recent-window baseline (the old ACM behavior) absorbs it.
    THE acceptance test of S3."""
    store = RawStore(tmp_path / "raw")
    for m in range(1, 13):
        store.append("frog", month_frame(2025, m, seed=m))
    # drifting recent months: +2 sigma by the end
    store.append("frog", month_frame(2026, 1, seed=101, offset=1.0))
    store.append("frog", month_frame(2026, 2, seed=102, offset=2.0))

    lifetime = LifetimeBaseline.build(store, "frog")

    # recent-window-only baseline (what the 180-day trim used to do)
    recent = pl.concat(
        [
            store.read(
                "frog",
                start=datetime(2026, 1, 1, tzinfo=UTC),
            )
        ]
    )
    recent_median = float(np.median(recent.get_column("temp").to_numpy()))

    healthy_median = 0.0  # true healthy center of 'temp'
    assert abs(lifetime.medians["temp"] - healthy_median) < 0.25, (
        f"lifetime baseline absorbed the drift: {lifetime.medians['temp']}"
    )
    assert abs(recent_median - healthy_median) > 0.9, (
        "test setup broken: recent window should sit on the drifted level"
    )


def test_lifetime_monitor_alarms_on_the_drift_the_baseline_resisted(tmp_path):
    """End-to-end S3 payoff: because the baseline did NOT absorb the drift,
    the monitor calibrated from lifetime memory ALARMS on the drifted
    recent data."""
    store = RawStore(tmp_path / "raw")
    for m in range(1, 13):
        store.append("frog2", month_frame(2025, m, seed=m, n=1500))
    store.append("frog2", month_frame(2026, 1, seed=101, offset=1.5, n=1500))
    store.append("frog2", month_frame(2026, 2, seed=102, offset=2.5, n=1500))

    mon = AssetMonitor("frog2")
    assert mon.calibrate_from_lifetime(store, seed=3)
    assert mon.model_epoch.startswith("s3-lifetime")
    drifted = store.read("frog2", start=datetime(2026, 1, 1, tzinfo=UTC))
    verdict = mon.process(drifted)
    assert verdict.state == "alarm"
    assert "temp" in verdict.attribution[:2]


def test_ledger_masked_baseline_ignores_fault_period(tmp_path):
    """Baseline hygiene: a ledgered fault month contributes nothing."""
    store = RawStore(tmp_path / "raw")
    for m in range(1, 6):
        store.append("h1", month_frame(2025, m, seed=m))
    store.append("h1", month_frame(2025, 6, seed=99, offset=5.0))  # fault month
    ledger = EpisodeLedger(tmp_path / "ledger.json")
    ledger.add(
        Episode(
            asset_key="h1",
            start="2025-06-01T00:00:00+00:00",
            end="2025-07-01T00:00:00+00:00",
            state="alarm",
        )
    )
    clean = LifetimeBaseline.build(store, "h1", ledger=ledger)
    dirty = LifetimeBaseline.build(store, "h1")
    assert abs(clean.medians["temp"]) < abs(dirty.medians["temp"]), (
        "masking must pull the baseline back toward healthy"
    )
    assert abs(clean.medians["temp"]) < 0.15
