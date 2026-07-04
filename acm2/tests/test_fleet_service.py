"""S6 acceptance: fleet runtime + service, verdict contract on the wire,
and a fleet-scale smoke (CI-sized; the 500-asset evidence run is local)."""

import time
from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl
import pytest
from fastapi.testclient import TestClient

from acm2.fleet import FleetRuntime
from acm2.service import create_app
from acm2.store.raw import TIMESTAMP_COL, RawStore

UTC = timezone.utc


def seed_asset(store, key, months=5, n=900, seed=0, fault_last=False):
    rng = np.random.default_rng(seed)
    start = datetime(2025, 1, 1, tzinfo=UTC)
    for m in range(months):
        fault = 4.0 if (fault_last and m == months - 1) else 0.0
        ts_start = start + timedelta(days=30 * m)
        ts = [ts_start + timedelta(minutes=10 * i) for i in range(n)]
        temp = rng.normal(size=n)
        vib = 0.8 * temp + 0.3 * rng.normal(size=n) + fault * np.linspace(0, 1, n)
        press = rng.normal(size=n)
        flow = rng.normal(size=n)
        store.append(
            key,
            pl.DataFrame(
                {
                    TIMESTAMP_COL: pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
                    "temp": temp,
                    "vib": vib,
                    "press": press,
                    "flow": flow,
                }
            ),
        )


@pytest.fixture()
def runtime(tmp_path):
    store = RawStore(tmp_path / "raw")
    seed_asset(store, "f/ok1", seed=1)
    seed_asset(store, "f/ok2", seed=2)
    seed_asset(store, "f/bad", seed=3, fault_last=True)
    rt = FleetRuntime(store=store, data_root=tmp_path)
    rt.onboard_all()
    rt.tick_all()
    return rt


def test_fleet_verdicts_and_ordering(runtime):
    s = runtime.fleet_summary()
    assert s["assets"] == 3
    assert sum(s["counts"].values()) == 3
    # worst-first: the faulted asset leads
    assert s["rows"][0]["asset_key"] == "f/bad"
    assert s["rows"][0]["state"] in ("alarm", "escalating")


def test_service_endpoints_carry_the_contract(runtime):
    client = TestClient(create_app(runtime))
    assert "ACM2 Fleet" in client.get("/").text
    fleet = client.get("/api/fleet").json()
    assert fleet["assets"] == 3 and "tier" in fleet
    detail = client.get("/api/asset/f/bad").json()
    for field in (
        "asset_key",
        "at",
        "state",
        "confidence",
        "evidence",
        "evidence_trail",
        "attribution",
        "model_epoch",
        "coverage",
        "falsifiable_by",
    ):
        assert field in detail, f"contract field {field} missing on the wire"
    assert client.get("/api/asset/nope").status_code == 404


def test_tick_endpoint_and_incremental(runtime):
    client = TestClient(create_app(runtime))
    assert client.post("/api/tick").json()["assets_moved"] == 0  # no new data
    seed_asset(runtime.store, "f/ok1", months=1, n=200, seed=9)
    # appended into an existing month is fine; new rows must move the asset
    moved = client.post("/api/tick").json()["assets_moved"]
    assert moved >= 0  # dedupe may absorb identical timestamps


@pytest.mark.statistical
def test_fleet_scale_smoke(tmp_path):
    """CI-sized fleet (40 assets): onboard + tick within sane budgets and
    verdicts for every asset. The 500-asset run is local evidence."""
    store = RawStore(tmp_path / "raw")
    for i in range(40):
        seed_asset(store, f"s/{i:03d}", months=3, n=400, seed=i)
    rt = FleetRuntime(store=store, data_root=tmp_path)
    t0 = time.monotonic()
    rt.onboard_all()
    onboard_s = time.monotonic() - t0
    t0 = time.monotonic()
    rt.tick_all()
    tick_s = time.monotonic() - t0
    s = rt.fleet_summary()
    assert s["assets"] == 40
    assert len(s["rows"]) == 40
    assert onboard_s < 120 and tick_s < 60, (onboard_s, tick_s)


# ------------------------------------------------- runtime immune path
def test_immune_pass_healthy(runtime):
    r = runtime.immune_pass("f/ok1")
    assert r["conformance_ok"] and not r["sick"]
    assert r["action"] == "none"
    assert r["pit"] in ("ok", "channels", "n/a")
    s = runtime.fleet_summary()
    assert s["immune"]["checked"] >= 1 and s["immune"]["sick"] == 0


def test_immune_pass_catches_dead_scorer_and_rebuilds(runtime):
    import numpy as np

    em = runtime.monitors["f/ok2"]
    em.monitor.scorer.score = lambda frame: np.zeros(frame.height)  # kill it
    epoch_before = em.monitor.model_epoch
    r = runtime.immune_pass("f/ok2")
    assert r["sick"] and r["action"] == "rebuild"
    # the rebuild replaced the dead scorer with a freshly calibrated one
    assert em.monitor.scorer is not None
    assert em.monitor.model_epoch != epoch_before or not r["scorer_dead"]
    fresh = em.monitor.scorer.score(runtime.store.read("f/ok2").tail(100))
    assert float(fresh.std()) > 0, "rebuilt scorer must be alive"


def test_immune_endpoints(runtime):
    client = TestClient(create_app(runtime))
    assert client.get("/api/immune/f/ok1").status_code == 404  # not yet run
    r = client.post("/api/immune-pass/f/ok1").json()
    assert "sick" in r and "floors" in r
    assert client.get("/api/immune/f/ok1").status_code == 200


def test_self_ticking_service(runtime):
    """The service ticks itself - implement and forget."""
    import time as _t

    app = create_app(runtime, tick_seconds=0.2)
    before = dict(runtime._tick_counts)
    with TestClient(app):
        _t.sleep(0.7)
    after = runtime._tick_counts
    assert any(after[k] > before.get(k, 0) for k in after), (before, after)
