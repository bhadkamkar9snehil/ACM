"""ML correctness tests — synthetic data with KNOWN injected faults.

These tests exist to catch real regressions in detection behaviour:
  - injected faults MUST raise alarms (sensitivity)
  - clean continuations MUST stay quiet (specificity)
  - detectors must produce informative, non-degenerate scores
  - the self-tuned rules must derive sane operating points
Every test runs in seconds on synthetic data; no SQL, no network.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.alarm_rules import apply_alarm_rules, self_tune_alarm_rule, sustained_alarm_mask
from core.ar1_detector import AR1Detector
from core.correlation import PCASubspaceDetector
from core.fast_features import detect_channel_roles
from core.pipeline import score_asset

RNG = np.random.RandomState(7)


def make_plant(n: int, start: str = "2025-01-01", seed: int = 7,
               phase0: int = 0, ambient_offset: float = 0.0) -> pd.DataFrame:
    """Synthetic 9-channel plant: ambient + load drive correlated sensors.

    phase0 keeps the daily cycle CONTINUOUS across train/score boundaries —
    real plants do not teleport between operating points.
    ambient_offset models weather: temps follow it (an EXPLAINED shift).
    """
    rng = np.random.RandomState(seed)
    idx = pd.date_range(start, periods=n, freq="10min")
    phase = (np.arange(n) + phase0) * 2 * np.pi / 144
    load = 50 + 30 * np.sin(phase) + rng.normal(0, 3, n)
    ambient = ambient_offset + 15 + 5 * np.sin(phase / 6) + rng.normal(0, 0.5, n)
    df = pd.DataFrame(index=idx)
    df["load"] = load
    df["ambient"] = ambient
    df["temp_a"] = 25 + ambient + 0.5 * load + rng.normal(0, 1.5, n)
    df["temp_b"] = 23 + ambient + 0.48 * load + rng.normal(0, 1.5, n)
    df["pressure"] = 10 + 0.1 * load + rng.normal(0, 0.4, n)
    df["vibration"] = 1.0 + 0.01 * load + rng.normal(0, 0.08, n)
    df["current"] = 5 + 0.2 * load + rng.normal(0, 0.8, n)
    df["flow"] = 100 + 0.8 * load + rng.normal(0, 4, n)
    df["aux"] = rng.normal(0, 1, n)
    df.index.name = "EntryDateTime"
    return df


TRAIN_N = 6000     # ~6 weeks at 10-min
SCORE_N = 1500     # ~10 days


def _run(score_mutator=None, ambient_offset: float = 0.0) -> tuple:
    train = make_plant(TRAIN_N, seed=7)
    score = make_plant(SCORE_N, start=str(train.index[-1] + pd.Timedelta(minutes=10)),
                       seed=11, phase0=TRAIN_N, ambient_offset=ambient_offset)
    if score_mutator:
        score = score_mutator(score)
    res = score_asset(train_raw=train, score_raw=score)
    return res, score


class TestFaultSensitivity:
    """Injected faults the product MUST catch."""

    def test_bearing_style_drift_detected(self):
        # temp_a decouples from load and ramps +12C over the last 5 days
        def hot_bearing(s):
            n = len(s)
            ramp = np.linspace(0, 12, n // 2)
            s.iloc[n // 2:, s.columns.get_loc("temp_a")] += ramp
            return s
        res, _ = _run(hot_bearing)
        assert res.decision.alarm.any(), \
            f"12C decoupled temperature ramp missed (rule={res.decision.rule_fired})"
        # the alarm must start INSIDE the faulty half
        first = int(np.argmax(res.decision.alarm))
        assert first >= SCORE_N // 4, "alarm fired before the fault began"

    def test_correlation_break_detected(self):
        # temp_b stops following load entirely (sensor/coupling failure)
        def decouple(s):
            n = len(s)
            s.iloc[n // 3:, s.columns.get_loc("temp_b")] = \
                55 + RNG.normal(0, 1.5, n - n // 3)
            return s
        res, _ = _run(decouple)
        assert res.decision.alarm.any(), \
            f"correlation break missed (rule={res.decision.rule_fired})"

    def test_intermittent_spiking_detected(self):
        # vibration spikes under high load only — intermittent, rate-rule shape
        def spiky(s):
            high = s["load"].to_numpy() > 65
            bump = np.where(high, 1.2, 0.0) + RNG.normal(0, 0.05, len(s))
            s.iloc[len(s) // 4:, s.columns.get_loc("vibration")] += bump[len(s) // 4:]
            return s
        res, _ = _run(spiky)
        assert res.decision.alarm.any(), \
            f"intermittent vibration spiking missed (rule={res.decision.rule_fired})"


class TestFalseAlarmResistance:
    """Clean continuations the product MUST NOT alarm on."""

    def test_clean_continuation_quiet(self):
        res, _ = _run(None)
        frac = float(res.decision.alarm.mean())
        assert frac < 0.02, f"alarms on clean data: {frac:.1%} of window " \
                            f"(rule={res.decision.rule_fired})"

    def test_seasonal_shift_tolerated(self):
        # +3C of MEASURED ambient, temps follow physically: an explained
        # regime change the residual models must absorb, not a fault.
        res, _ = _run(None, ambient_offset=3.0)
        assert float(res.decision.alarm.mean()) < 0.10, \
            "explained ambient shift treated as a fault"


class TestDetectorHealth:
    """Detectors must produce informative, non-degenerate output."""

    def test_no_head_is_constant(self):
        res, _ = _run(None)
        for z in res.scores.columns:
            v = res.scores[z].to_numpy()
            v = v[np.isfinite(v)]
            assert v.size and float(np.nanstd(v)) > 1e-6, f"{z} is a dead constant stream"

    def test_calibration_centres_healthy_data(self):
        res, _ = _run(None)
        med = float(np.nanmedian(res.fused))
        assert abs(med) < 1.5, f"healthy fused median {med:.2f} far from 0 (calibration bias)"

    def test_ar1_excludes_degenerate_channels(self):
        train = make_plant(3000)
        train["stuck"] = 42.0                      # fully constant
        det = AR1Detector({}).fit(train)
        assert "stuck" not in det.phimap, "constant channel not excluded from AR1"
        score = make_plant(500, seed=3)
        score["stuck"] = 42.0 + RNG.normal(0, 1e-9, 500)   # sub-LSB wiggle
        fused = det.score(score)
        assert float(np.nanmax(fused)) < 50, "degenerate channel exploded AR1 z-scores"

    def test_pca_spe_not_saturated(self):
        train = make_plant(4000)
        train["quantized"] = np.round(train["load"] / 25) * 25   # IQR-degenerate
        det = PCASubspaceDetector({})
        det.fit(train)
        spe, t2 = det.score(make_plant(800, seed=5).assign(
            quantized=lambda d: np.round(d["load"] / 25) * 25))
        assert float(np.mean(np.asarray(spe) >= 1e6)) < 0.01, "PCA-SPE saturated at clip"


class TestChannelRoles:
    def test_raw_feed_untouched(self):
        roles = detect_channel_roles(make_plant(2000))
        assert roles["derived"] == [], "raw-sensor feed wrongly classified as derived"

    def test_verified_derived_detected(self):
        df = make_plant(2000)
        df["temp_a_min"] = df["temp_a"] - abs(RNG.normal(1, 0.2, len(df)))
        df["temp_a_max"] = df["temp_a"] + abs(RNG.normal(1, 0.2, len(df)))
        roles = detect_channel_roles(df)
        assert set(roles["derived"]) == {"temp_a_min", "temp_a_max"}

    def test_lying_names_rejected(self):
        df = make_plant(2000)
        df["temp_a_min"] = df["temp_a"] + 10     # violates min <= base
        roles = detect_channel_roles(df)
        assert "temp_a_min" not in roles["derived"], "unverified 'min' channel trusted by name"


class TestAlarmRules:
    def test_self_tuned_threshold_above_holdout(self):
        tf = RNG.normal(0, 1, 5000)
        thr, persist = self_tune_alarm_rule(tf)
        assert thr >= 3.0 and persist >= 6
        assert not sustained_alarm_mask(tf, thr, persist).any(), \
            "rule alarms on its own calibration data"

    def test_contaminated_history_conservative(self):
        tf = RNG.normal(0, 1, 5000)
        tf[2000:2300] += 8.0    # a past fault inside the history
        thr_dirty, _ = self_tune_alarm_rule(tf)
        thr_clean, _ = self_tune_alarm_rule(RNG.normal(0, 1, 5000))
        assert thr_dirty >= thr_clean, "contamination LOWERED the alarm threshold"

    def test_availability_rule_fires_on_outage(self):
        train_status = np.zeros(20000, dtype=int)
        train_status[5000:5050] = 4                       # one 8h healthy stop
        score_status = np.zeros(2000, dtype=int)
        score_status[500:] = 4                            # 10-day outage
        d = apply_alarm_rules(
            fused=np.zeros(2000), train_fused=RNG.normal(0, 1, 5000),
            score_status=score_status, train_status=train_status)
        assert d.alarm_avail.any(), "extended outage not flagged by availability rule"
        assert not d.alarm_avail[:500 + 287].any(), "availability fired before 48h of outage"

    def test_distrust_gate_discards_always_on(self):
        n = 3000
        head = np.full(n, 9.0)                            # head pegged the whole window
        d = apply_alarm_rules(
            fused=np.zeros(n), train_fused=RNG.normal(0, 1, 5000),
            head_z_score={"omr_z": head},
            head_z_train={"omr_z": RNG.normal(0, 1, 5000)})
        assert not d.alarm.any(), "always-on head not discarded"
        assert any("heads" in x for x in d.distrusted)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
