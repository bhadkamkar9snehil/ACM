"""Store + runner integration tests: SQL round-trip, views, config sync.

Everything runs against SQLite (same schema as SQL Server); no server needed.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.pipeline import score_asset                                # noqa: E402
from scripts.acm_run import infer_score_days, parse_timestamp_col    # noqa: E402
from scripts.acm_store import Store, ingest_result, sync_config      # noqa: E402
from tests.test_ml import make_plant                                 # noqa: E402


@pytest.fixture
def store(tmp_path):
    s = Store("sqlite", db=str(tmp_path / "t.db"))
    yield s
    s.close()


def _scored():
    train = make_plant(4000)
    score = make_plant(800, start=str(train.index[-1] + pd.Timedelta(minutes=10)), seed=3)
    score["temp_a"] += np.linspace(0, 15, 800)   # fault so alarms exist
    return score_asset(train_raw=train, score_raw=score,
                       train_status=np.zeros(4000, dtype=int),
                       score_status=np.zeros(800, dtype=int))


class TestStoreRoundTrip:
    def test_ingest_result_full_round_trip(self, store, tmp_path):
        res = _scored()
        ingest_result(store, "plant1", "PUMP7", res)
        con = sqlite3.connect(tmp_path / "t.db")

        assets = pd.read_sql("SELECT * FROM assets", con)
        assert list(assets.asset_key) == ["plant1/PUMP7"]
        assert assets.iloc[0].verdict in ("ALARM", "OK")

        scores = pd.read_sql("SELECT * FROM scores WHERE asset_key='plant1/PUMP7'", con)
        assert len(scores) == len(res.fused)
        # full timeline, start to end, every head present
        for z in ("ar1_z", "pca_spe_z", "omr_z"):
            assert scores[z].notna().any(), f"{z} column empty in store"

        runs = pd.read_sql("SELECT * FROM runs", con)
        assert len(runs) == 1 and runs.iloc[0].status == "OK"
        logs = pd.read_sql("SELECT * FROM run_log", con)
        assert {"channels", "features", "fit", "rules"} <= set(logs.stage), \
            "observability stages missing from run_log"

    def test_views_live_monitoring(self, store, tmp_path):
        ingest_result(store, "plant1", "PUMP7", _scored())
        con = sqlite3.connect(tmp_path / "t.db")
        now = pd.read_sql("SELECT * FROM v_asset_now", con)
        assert len(now) == 1
        assert now.iloc[0].last_ts is not None and now.iloc[0].last_fused is not None
        daily = pd.read_sql("SELECT * FROM v_daily_stats", con)
        assert len(daily) >= 5
        assert (daily.availability == 1.0).all()

    def test_reingest_replaces_not_duplicates(self, store, tmp_path):
        res = _scored()
        ingest_result(store, "plant1", "PUMP7", res)
        ingest_result(store, "plant1", "PUMP7", res)
        con = sqlite3.connect(tmp_path / "t.db")
        n = pd.read_sql("SELECT COUNT(*) AS n FROM scores", con).iloc[0].n
        assert n == len(res.fused), "re-ingest duplicated score rows"


class TestConfigSync:
    def test_file_to_db_sync(self, store, tmp_path):
        sync_config(store, ROOT / "configs" / "config_table.csv")
        con = sqlite3.connect(tmp_path / "t.db")
        cfg = pd.read_sql("SELECT * FROM config", con)
        assert len(cfg) > 50
        assert {"data", "sql", "runtime"} <= set(cfg.category)
        # no ML categories may leak back into human config
        assert not ({"models", "thresholds", "fusion", "regimes"} & set(cfg.category)), \
            "ML parameters found in human config - they belong in core/ml_defaults.py"

    def test_sync_is_idempotent(self, store, tmp_path):
        sync_config(store, ROOT / "configs" / "config_table.csv")
        sync_config(store, ROOT / "configs" / "config_table.csv")
        con = sqlite3.connect(tmp_path / "t.db")
        cfg = pd.read_sql("SELECT category, param_path, COUNT(*) n FROM config "
                          "GROUP BY category, param_path HAVING n > 1", con)
        assert cfg.empty, "config sync duplicated rows"


class TestRunnerCSV:
    def test_infer_score_days_uses_dataset_span(self):
        ts = pd.Series(pd.date_range("2025-01-01", periods=201, freq="D"))
        assert infer_score_days(ts) == pytest.approx(200 / 3)

    def test_infer_score_days_keeps_minimum_training_baseline(self):
        ts = pd.Series(pd.date_range("2025-01-01", periods=16, freq="D"))
        assert infer_score_days(ts) == pytest.approx(1.0)

    def test_parse_timestamp_col_accepts_mixed_iso_precision(self):
        ts = parse_timestamp_col(pd.Series([
            "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:00.100000Z",
        ]))
        assert ts.notna().all()
        assert ts.iloc[1] > ts.iloc[0]

    def test_parse_timestamp_col_resolves_day_first_ambiguity(self):
        # day<=12 rows are ambiguous (could be read month-first); day=13/31
        # rows are not. A correct parse must read every row day-first and
        # land in chronological order; the pre-fix code silently swapped
        # day/month on the ambiguous rows instead.
        ts = parse_timestamp_col(pd.Series([
            "01-04-2018 00:00",
            "02-04-2018 00:00",
            "13-04-2018 00:00",
            "31-07-2018 00:00",
        ]))
        assert ts.notna().all()
        assert ts.is_monotonic_increasing
        assert ts.iloc[0] == pd.Timestamp("2018-04-01 00:00:00")
        assert ts.iloc[-1] == pd.Timestamp("2018-07-31 00:00:00")

    @pytest.mark.slow
    def test_acm_run_csv_end_to_end(self, tmp_path):
        import subprocess
        df = make_plant(5000).reset_index().rename(columns={"EntryDateTime": "time_stamp"})
        df["status"] = 0
        csv = tmp_path / "PUMP7.csv"
        df.to_csv(csv, index=False)
        db = tmp_path / "r.db"
        p = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "acm_run.py"),
             "--csv", str(csv), "--timestamp-col", "time_stamp", "--status-col", "status",
             "--score-days", "5", "--db", str(db), "--group", "plant1"],
            capture_output=True, text=True, timeout=600)
        assert p.returncode == 0, p.stderr[-1500:]
        con = sqlite3.connect(db)
        now = pd.read_sql("SELECT * FROM v_asset_now", con)
        assert list(now.asset_key) == ["plant1/PUMP7"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
