"""The judging harness: case truth, scoring rules and the baseline."""

from __future__ import annotations

import numpy as np

from bench import cases as C
from bench.methods import Advisory, RunningZ
from bench.score import GRACE_ROWS, replay, score_case, summarize


def test_case_is_reproducible_and_fault_starts_at_onset():
    a = C.make_case("pump", 0, C.SENSOR, "offset", "hours")
    b = C.make_case("pump", 0, C.SENSOR, "offset", "hours")
    clean = C.make_case("pump", 0, healthy_rows=a.n)
    assert np.array_equal(a.x, b.x, equal_nan=True)
    start = a.event.start
    assert start == C.ONSET_AGES["hours"]
    j = a.columns.index(a.event.channels[0])
    assert np.array_equal(a.x[:start], clean.x[:start])
    shift = np.mean(a.x[start:, j] - clean.x[start:, j])
    assert abs(shift - C.SENSOR_OFFSET_SD * a.noise_sd[j]) < 1e-6
    other = [k for k in range(a.x.shape[1]) if k != j]
    assert np.array_equal(a.x[:, other], clean.x[:, other])


def test_machine_fault_moves_several_channels():
    a = C.make_case("motor", 0, C.MACHINE, "step", "hours")
    clean = C.make_case("motor", 0, healthy_rows=a.n)
    moved = np.abs(a.x[a.event.start:] - clean.x[a.event.start:]).mean(axis=0)
    assert (moved > a.noise_sd).sum() >= 3


def test_splits_do_not_share_types_or_seeds():
    dev = {c.asset_type for c in C.suite("dev", stages=("hours",), seeds=(0,))}
    judge = {t for t, (_, s) in C.GENERATORS.items() if s == "judge"}
    assert dev and judge and not (dev & judge)
    assert not (set(C.DEV_SEEDS) & set(C.JUDGE_SEEDS))


def test_scoring_separates_detection_from_false_advisories():
    case = C.make_case("pump", 0, C.DATA, "nan_block", "hours")
    ev = case.event
    adv = [Advisory(ev.start - 5, None), Advisory(ev.start + 3, C.DATA, ev.channels),
           Advisory(ev.end + GRACE_ROWS + 1, None)]
    rec = score_case(case, adv)
    assert rec["false_advisories"] == 2
    assert rec["detected"] and rec["delay_h"] == 3 / 60
    assert rec["reported_kind"] == C.DATA and rec["channel_hit"]


def test_new_state_needs_the_right_kind():
    case = C.make_case("pump", 0, C.NEW_STATE, "level", "hours")
    rec = score_case(case, [Advisory(case.event.start + 10, None)])
    assert not rec["detected"] and rec["misread"]
    rec = score_case(case, [Advisory(case.event.start + 10, C.NEW_STATE)])
    assert rec["detected"] and not rec["misread"]


def test_baseline_replays_and_summary_counts_exposure(tmp_path):
    case = C.make_case("motor", 0, healthy_rows=2 * C.DAY)
    rec = replay(RunningZ(), case, tmp_path)
    s = summarize([rec])
    assert rec["healthy_rows"] == case.n
    assert abs(s["healthy_asset_years"] - 2 / 365.25) < 1e-9
    assert s["false_advisories"] == rec["false_advisories"]
