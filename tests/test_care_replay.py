"""Evidence-lane runner smoke (issue #86): a tiny synthetic CARE-shaped
farm through the FULL replay path - adapter, first contact, chunked ticks,
evaluation, artifacts. Real CARE replays are the manual evidence lane;
this pins the machinery in the fast lane without any download."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import polars as pl

from acm.evidence.care_replay import (
    load_event_frames,
    replay_farm,
)

UTC = timezone.utc


def _write_event_csv(
    path: Path, seed: int, n_train: int = 4500, n_pred: int = 1500,
    fault: float = 0.0,
) -> None:
    """CARE dataset shape: naive time_stamp strings, meta/label columns,
    sensor channels. The fault (if any) starts at the prediction split."""
    rng = np.random.default_rng(seed)
    n = n_train + n_pred
    start = datetime(2025, 1, 1, tzinfo=UTC)
    ts = [
        (start + timedelta(minutes=10 * i)).strftime("%Y-%m-%d %H:%M:%S")
        for i in range(n)
    ]
    temp = rng.normal(size=n)
    vib = 0.8 * temp + 0.3 * rng.normal(size=n)
    if fault:
        ramp = np.zeros(n)
        ramp[n_train:] = fault * np.linspace(0.2, 1.0, n_pred)
        vib = vib + ramp
    frame = pl.DataFrame(
        {
            "time_stamp": ts,
            "asset_id": [7] * n,
            "id": list(range(n)),
            "train_test": ["train"] * n_train + ["prediction"] * n_pred,
            "status_type_id": [0] * n,
            "sensor_0_avg": temp,
            "sensor_1_avg": vib,
            "sensor_2_avg": rng.normal(size=n),
            "sensor_3_avg": rng.normal(size=n),
        }
    )
    frame.write_csv(path, separator=";")  # real CARE is semicolon-delimited


def _make_farm(tmp_path: Path) -> Path:
    farm = tmp_path / "Wind Farm T"
    (farm / "datasets").mkdir(parents=True)
    # event_start = first prediction row (CARE convention allows this)
    ev_start = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(minutes=10 * 4500)
    pl.DataFrame(
        {
            "event_id": [1, 2],
            "event_label": ["anomaly", "normal"],
            "event_start": [ev_start.strftime("%Y-%m-%d %H:%M:%S")] * 2,
            "event_end": [
                (ev_start + timedelta(minutes=10 * 1499)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            ]
            * 2,
        }
    ).write_csv(farm / "event_info.csv", separator=";")
    _write_event_csv(farm / "datasets" / "1.csv", seed=1, fault=5.0)
    _write_event_csv(farm / "datasets" / "2.csv", seed=2, fault=0.0)
    return farm


def test_adapter_declares_utc_and_drops_labels(tmp_path):
    farm = _make_farm(tmp_path)
    train, predict = load_event_frames(farm, 1)
    for f in (train, predict):
        assert "status_type_id" not in f.columns  # label never enters
        assert "train_test" not in f.columns
        assert "asset_id" not in f.columns and "id" not in f.columns
        assert f.schema["timestamp"].time_zone == "UTC"  # declared, never guessed
    assert train.height == 4500 and predict.height == 1500


def test_replay_farm_hits_fault_and_keeps_normal_clean(tmp_path):
    farm = _make_farm(tmp_path)
    out = tmp_path / "out"
    summary = replay_farm(farm, out, chunk_rows=288)
    assert summary["events"] == 2
    assert summary["hits"] == 1 and summary["misses"] == 0, summary
    assert summary["false_alarms"] == 0 and summary["clean"] == 1, summary
    # artifacts: per-event records + summary, both parseable
    rec = json.loads((out / "event_1.json").read_text(encoding="utf-8"))
    assert rec["outcome"] == "hit" and rec["lag_h"] is not None
    assert rec["lag_h"] >= 0.0
    assert not rec["insufficient"]
    assert json.loads((out / "summary.json").read_text(encoding="utf-8"))


def test_replay_event_selection(tmp_path):
    farm = _make_farm(tmp_path)
    out = tmp_path / "out_sel"
    summary = replay_farm(farm, out, events=["2"], chunk_rows=500)
    assert summary["events"] == 1
    assert summary["records"][0]["event_id"] == 2
