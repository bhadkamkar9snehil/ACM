"""Service-layer tests: feed/cache, readiness gate, scheduler tick, API.

Everything runs against SQLite + CSV sources in tmp_path; the scheduler loop
itself is never started (ticks are driven directly), so tests are
deterministic and fast.
"""
from __future__ import annotations

import asyncio
import re
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.pipeline import score_asset                                  # noqa: E402
from scripts import acm_service                                        # noqa: E402
from scripts.acm_feed import (                                         # noqa: E402
    SourceSpec, cache_path, readiness, update_cache,
)
from scripts.acm_store import (                                        # noqa: E402
    DDL_MSSQL, DDL_SQLITE, Store, ack_alarm, ingest_result,
)
from tests.test_ml import make_plant                                   # noqa: E402


def plant_csv(tmp_path: Path, name: str, n: int, seed: int = 7,
              fault: bool = False) -> Path:
    df = make_plant(n, seed=seed).reset_index().rename(
        columns={"EntryDateTime": "time_stamp"})
    if fault:
        k = min(n, 800)
        df.loc[df.index[-k:], "temp_a"] = (
            df["temp_a"].iloc[-k:].to_numpy() + np.linspace(0, 15, k))
    path = tmp_path / f"{name}.csv"
    df.to_csv(path, index=False)
    return path


# ------------------------------------------------------------------- feed --
class TestFeed:
    def test_cache_is_incremental(self, tmp_path):
        csv = plant_csv(tmp_path, "p1", 2880)
        spec = SourceSpec("P1", "csv", str(csv), timestamp_col="time_stamp",
                          status_col=None)
        info1 = update_cache(spec, tmp_path / "cache")
        assert info1.n_rows == 2880 and info1.pulled_rows == 2880

        df = pd.read_csv(csv, parse_dates=["time_stamp"])
        extra = df.tail(100).copy()
        extra["time_stamp"] += pd.Timedelta(minutes=10) * 100
        pd.concat([df, extra]).to_csv(csv, index=False)
        info2 = update_cache(spec, tmp_path / "cache")
        assert info2.pulled_rows == 100, "second pull must be the increment only"
        assert info2.n_rows == 2980

    def test_cache_trailing_window_cap(self, tmp_path):
        csv = plant_csv(tmp_path, "p2", 2880)   # 20 days @10min
        spec = SourceSpec("P2", "csv", str(csv), timestamp_col="time_stamp",
                          status_col=None)
        info = update_cache(spec, tmp_path / "cache", train_window_days=10.0)
        assert info.span_days <= 10.01, "cache must trim to the trailing window"
        assert cache_path(tmp_path / "cache", "P2").exists()

    def test_readiness_gate_is_time_aware(self):
        now = pd.Timestamp("2026-06-01 12:00")
        fresh = now - pd.Timedelta(hours=1)
        assert readiness(30.0, fresh, now) == "READY"
        assert readiness(3.0, fresh, now) == "MATURING", \
            "3 days of history is not a baseline"
        assert readiness(30.0, None, now) == "MATURING"
        assert readiness(30.0, now - pd.Timedelta(days=3), now) == "STALE", \
            "a dead feed must surface as STALE, not get scored"


# ------------------------------------------------------------------ store --
class TestAlarmAcks:
    def _scored(self):
        train = make_plant(4000)
        score = make_plant(800, start=str(train.index[-1] + pd.Timedelta(minutes=10)),
                           seed=3)
        score["temp_a"] += np.linspace(0, 15, 800)
        return score_asset(train_raw=train, score_raw=score,
                           train_status=np.zeros(4000, dtype=int),
                           score_status=np.zeros(800, dtype=int))

    def test_ack_survives_reingest(self, tmp_path):
        store = Store("sqlite", db=str(tmp_path / "t.db"))
        res = self._scored()
        assert res.decision.alarm.any(), "fixture fault must alarm"
        ingest_result(store, "g", "A1", res, keep_history=True)
        eps = store.fetch("SELECT start_ts FROM alarms WHERE asset_key='g/A1'")
        assert eps
        n = ack_alarm(store, "g/A1", eps[0]["start_ts"], "snehil", "checked it")
        assert n == 1
        ingest_result(store, "g", "A1", res, keep_history=True)
        acked = store.fetch("SELECT ack_by, ack_note FROM alarms "
                            "WHERE asset_key='g/A1' AND ack_at IS NOT NULL")
        assert acked and acked[0]["ack_by"] == "snehil", \
            "acknowledgement lost across re-ingest"
        runs = store.fetch("SELECT * FROM runs WHERE asset_key='g/A1'")
        assert len(runs) == 2, "keep_history must append run records"
        store.close()

    def test_default_ingest_unchanged(self, tmp_path):
        store = Store("sqlite", db=str(tmp_path / "t.db"))
        res = self._scored()
        ingest_result(store, "g", "A1", res)
        ingest_result(store, "g", "A1", res)
        n = store.fetch("SELECT COUNT(*) AS n FROM scores")[0]["n"]
        assert n == len(res.fused), "batch path must replace, not accumulate"
        assert len(store.fetch("SELECT * FROM runs")) == 1
        store.close()


class TestSchemaParity:
    def _tables(self, ddl: str, mssql: bool) -> dict:
        pat = (r"CREATE TABLE dbo\.acm_(\w+) \((.*?)\);" if mssql
               else r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\);")
        out = {}
        for name, body in re.findall(pat, ddl, flags=re.S):
            cols = re.findall(
                r"(?:^|,)\s*(\w+)\s+(?:TEXT|INTEGER|REAL|NVARCHAR|INT\b|FLOAT|DATETIME2)",
                body)
            out[name] = set(cols)
        return out

    def test_sqlite_mssql_same_tables_and_columns(self):
        lite, ms = self._tables(DDL_SQLITE, False), self._tables(DDL_MSSQL, True)
        assert set(lite) == set(ms), f"table sets diverge: {set(lite) ^ set(ms)}"
        for t in lite:
            assert lite[t] == ms[t], f"columns diverge in '{t}': {lite[t] ^ ms[t]}"


# ---------------------------------------------------------------- service --
@pytest.fixture
def app_env(tmp_path, monkeypatch):
    """create_app on a tmp store with a tmp copy of the config CSV."""
    cfg_copy = tmp_path / "config_table.csv"
    shutil.copy(ROOT / "configs" / "config_table.csv", cfg_copy)
    monkeypatch.setattr(acm_service, "CONFIG_CSV", cfg_copy)
    app = acm_service.create_app("sqlite", db=str(tmp_path / "svc.db"),
                                 run_scheduler=False)
    svc = app.state.service
    svc.cache_dir = tmp_path / "cache"
    svc.workers = 1
    svc.score_days = 5.0
    svc.stale_after_hours = 1e9     # synthetic timestamps live in the past
    yield app, svc, tmp_path
    svc.store.close()


class TestServiceTick:
    def test_tick_scores_gates_and_records(self, app_env):
        app, svc, tmp_path = app_env
        long_csv = plant_csv(tmp_path, "PUMP7", 5000, fault=True)
        short_csv = plant_csv(tmp_path, "NEWPUMP", 400, seed=8)
        for key, src in [("PUMP7", long_csv), ("NEWPUMP", short_csv)]:
            svc.store.execute(
                "INSERT INTO monitored_assets (asset_key, grp, enabled, source_kind, "
                "source_ref, timestamp_col, added_at, state) VALUES (?,?,?,?,?,?,?,?)",
                (key, "fleet", 1, "csv", str(src), "time_stamp", "2026-01-01", "NEW"))
        svc.store.commit()

        counts = asyncio.run(svc.tick_once())
        assert counts["scored"] == 1 and counts["skipped"] == 1, counts
        states = {r["asset_key"]: r["state"] for r in svc.monitored()}
        assert states["NEWPUMP"] == "MATURING"
        assert states["PUMP7"] in ("OK", "ALARM")
        assert svc.store.fetch("SELECT * FROM scores WHERE asset_key='fleet/PUMP7'")
        from scripts.acm_store import get_service_state
        assert get_service_state(svc.store)["last_tick_at"] is not None

    def test_tick_marks_broken_source_error(self, app_env):
        app, svc, tmp_path = app_env
        svc.store.execute(
            "INSERT INTO monitored_assets (asset_key, grp, enabled, source_kind, "
            "source_ref, timestamp_col, added_at, state) VALUES (?,?,?,?,?,?,?,?)",
            ("GHOST", "fleet", 1, "csv", str(tmp_path / "missing.csv"),
             "time_stamp", "2026-01-01", "NEW"))
        svc.store.commit()
        counts = asyncio.run(svc.tick_once())
        assert counts["errors"] == 1
        row = svc.monitored()[0]
        assert row["state"] == "ERROR" and row["state_detail"]
        runs = svc.store.fetch("SELECT * FROM runs WHERE asset_key='fleet/GHOST'")
        assert runs and runs[0]["status"] == "ERROR"


class TestServiceAPI:
    def test_api_lifecycle(self, app_env):
        from fastapi.testclient import TestClient
        app, svc, tmp_path = app_env
        csv = plant_csv(tmp_path, "PUMP9", 5000, fault=True)
        client = TestClient(app)

        # onboard: bad source must 422, good source lands as NEW
        r = client.post("/api/monitored-assets", json={
            "asset_key": "BAD", "source_kind": "csv",
            "source_ref": str(tmp_path / "nope.csv")})
        assert r.status_code == 422
        r = client.post("/api/monitored-assets", json={
            "asset_key": "PUMP9", "source_kind": "csv", "source_ref": str(csv),
            "timestamp_col": "time_stamp"})
        assert r.status_code == 200, r.text
        assert r.json()["state"] == "NEW"
        r = client.post("/api/monitored-assets", json={
            "asset_key": "PUMP9", "source_kind": "csv", "source_ref": str(csv),
            "timestamp_col": "time_stamp"})
        assert r.status_code == 409

        fleet = client.get("/api/fleet").json()
        assert any(a["asset_key"] == "fleet/PUMP9" and a["state"] == "NEW"
                   for a in fleet)

        asyncio.run(svc.tick_once())

        # engineer surface
        series = client.get("/api/assets/fleet/PUMP9/series?days=5").json()
        assert series["rows"] and "fused" in series["columns"]
        assert client.get("/api/assets/fleet/PUMP9/daily").json()
        assert client.get("/api/assets/fleet/PUMP9/runs").json()
        assert client.get("/api/assets/fleet/PUMP9/runlog").json()

        # alarm ack workflow
        eps = client.get("/api/assets/fleet/PUMP9/alarms").json()
        if eps:
            r = client.post("/api/alarms/ack", json={
                "asset_key": "fleet/PUMP9", "start_ts": eps[0]["start_ts"],
                "ack_by": "op1", "note": "known issue"})
            assert r.status_code == 200

        # run control
        assert client.post("/api/service/pause").json()["paused"] is True
        assert client.get("/api/service").json()["paused"] == 1
        assert client.post("/api/service/resume").json()["paused"] is False
        assert client.put("/api/service/tick", json={"tick_minutes": 5}
                          ).json()["tick_minutes"] == 5
        assert client.put("/api/service/tick", json={"tick_minutes": 0}
                          ).status_code == 422
        assert client.post("/api/service/run-now", json={}).status_code == 200
        assert client.post("/api/service/run-now",
                           json={"assets": ["NOPE"]}).status_code == 404

        # disable + retire
        assert client.patch("/api/monitored-assets/PUMP9",
                            json={"enabled": False}).status_code == 200
        assert client.delete("/api/monitored-assets/PUMP9").status_code == 200
        assert client.get("/api/monitored-assets").json() == []

    def test_config_editing_with_audit(self, app_env):
        from fastapi.testclient import TestClient
        app, svc, tmp_path = app_env
        client = TestClient(app)

        # ML categories are code — hard-rejected
        r = client.put("/api/config", json={
            "category": "models", "param_path": "pca.n_components",
            "value": "9", "changed_by": "snehil"})
        assert r.status_code == 422
        assert "ML behaviour is code" in r.json()["detail"]

        r = client.put("/api/config", json={
            "category": "runtime", "param_path": "tick_minutes",
            "value": "20", "changed_by": "snehil", "note": "denser polling"})
        assert r.status_code == 200, r.text

        # CSV write-back + config table + audit trail
        csv_txt = (tmp_path / "config_table.csv").read_text()
        assert re.search(r"runtime,tick_minutes,20", csv_txt)
        cfg = client.get("/api/config").json()
        row = [c for c in cfg if c["category"] == "runtime"
               and c["param_path"] == "tick_minutes"][0]
        assert row["param_value"] == "20"
        audit = client.get("/api/config/audit").json()
        assert audit and audit[0]["new_value"] == "20" \
            and audit[0]["changed_by"] == "snehil"

        # unknown param: 404, no silent row creation
        assert client.put("/api/config", json={
            "category": "runtime", "param_path": "no.such.param",
            "value": "1", "changed_by": "x"}).status_code == 404


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
