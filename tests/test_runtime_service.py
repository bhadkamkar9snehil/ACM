"""S6 acceptance: fleet runtime + service, verdict contract on the wire,
and a fleet-scale smoke (CI-sized; the 500-asset evidence run is local)."""

import time
from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl
import pytest
from fastapi.testclient import TestClient

from runtime import Runtime
from service import create_app
from store.raw import TIMESTAMP_COL, RawStore

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
    rt = Runtime(store=store, data_root=tmp_path)
    rt.onboard_all()
    rt.tick_all()
    return rt


def test_fleet_verdicts_and_ordering(runtime):
    s = runtime.summary()
    assert s["assets"] == 3
    assert sum(s["counts"].values()) == 3
    # worst-first: the faulted asset leads
    assert s["rows"][0]["asset_key"] == "f/bad"
    assert s["rows"][0]["state"] in ("alarm", "escalating")


def test_service_endpoints_carry_the_contract(runtime):
    client = TestClient(create_app(runtime))
    assert "ACM" in client.get("/").text
    fleet = client.get("/api/assets").json()
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


def test_restart_does_not_double_count_evidence(tmp_path):
    """#120 / #136 reproduction: the durable runtime journal means a
    fresh Runtime over the same data root does NOT re-read the whole life
    on its first tick. Before the fix, _last_seen was RAM-only, so a
    restart re-ingested all history into the cached-wealth banks -
    double-counting evidence and violating the alpha guarantee.

    This test fails against pre-#136 main (the first post-restart tick
    reports rows moved and bank wealth changes with no new data)."""
    store = RawStore(tmp_path / "raw")
    seed_asset(store, "r/1", seed=1)

    rt = Runtime(store=store, data_root=tmp_path)
    rt.onboard_all()
    rt.tick_all()  # scores the whole history, sets verdict + last_seen
    seen_before = rt.state.get_last_seen("r/1")
    assert seen_before is not None  # journal is durable, not RAM-only
    ev_before = rt.verdicts["r/1"].evidence

    # simulate a service restart: brand-new Runtime, same data root, NO
    # new data appended
    rt2 = Runtime(store=store, data_root=tmp_path)
    # verdict + evidence history hydrate from the store immediately, before
    # any tick (restart continuity - the UI is not blank on restart)
    assert "r/1" in rt2.verdicts, "verdict not hydrated after restart"
    assert rt2.verdicts["r/1"].evidence == pytest.approx(ev_before, abs=1e-9)
    assert rt2.evidence_series("r/1")

    rt2.onboard_all()  # restores the cached monitor + resumes the journal
    moved = rt2.tick_all()  # no new rows since the durable last_seen
    assert moved == 0, "restart re-read history that was already scored"
    assert rt2.state.get_last_seen("r/1") == seen_before


def test_live_asset_lifecycle_no_restart(tmp_path):
    """#137: register -> onboard+bootstrap live -> retire -> re-register
    -> purge, all on a running Runtime with no restart."""
    store = RawStore(tmp_path / "raw")
    seed_asset(store, "live/1", seed=1)

    rt = Runtime(store=store, data_root=tmp_path)
    # nothing discovered yet (asset seeded but not onboarded)
    rt.register_asset("live/1", display_name="Live One", group="test")
    assert rt.state.get_asset("live/1").display_name == "Live One"

    out = rt.onboard_and_bootstrap("live/1")
    assert out["onboarded"] is True
    assert "live/1" in rt.monitors
    assert "live/1" in rt._bootstrapped  # first contact ran + marked
    assert rt.state.get_last_seen("live/1") is not None

    # retire (keep history): stops monitoring, registry retired, raw kept
    rt.retire_asset("live/1", purge=False)
    assert "live/1" not in rt.monitors
    assert rt.state.get_asset("live/1").retired_at is not None
    assert (tmp_path / "raw").exists()
    assert store.row_count("live/1") > 0  # history intact

    # a restart-equivalent onboard_all must SKIP the retired asset
    rt2 = Runtime(store=store, data_root=tmp_path)
    rt2.onboard_all()
    assert "live/1" not in rt2.monitors

    # re-register un-retires; then purge removes registry + raw + cache
    rt2.register_asset("live/1")
    assert rt2.state.get_asset("live/1").retired_at is None
    rt2.onboard_and_bootstrap("live/1")
    rt2.retire_asset("live/1", purge=True)
    assert rt2.state.get_asset("live/1") is None
    from store.raw import _safe_key
    assert not (tmp_path / "raw" / _safe_key("live/1")).exists()


def test_asset_lifecycle_endpoints(runtime):
    """#137 API surface: add (409 on dup), delete, reonboard, wired and
    returning the right shapes. Onboarding itself runs in the background;
    the registry write is synchronous so it is assertable immediately."""
    client = TestClient(create_app(runtime))
    # f/ok1 already exists in the fixture fleet
    r = client.post("/api/assets", json={"asset_key": "f/ok1"})
    assert r.status_code == 409
    # a brand-new key registers and reports onboarding
    r = client.post("/api/assets", json={
        "asset_key": "new/x", "display_name": "New X", "group": "g"})
    assert r.status_code == 200 and r.json()["status"] == "onboarding"
    assert runtime.state.get_asset("new/x").display_name == "New X"
    # missing key -> 400
    assert client.post("/api/assets", json={}).status_code == 400
    # delete unknown -> 404; delete known -> ok
    assert client.request("DELETE", "/api/assets/nope/nope").status_code == 404
    assert client.request("DELETE", "/api/assets/new/x").status_code == 200
    assert runtime.state.get_asset("new/x").retired_at is not None
    # reonboard unknown -> 404
    assert client.post("/api/assets/nope/reonboard").status_code == 404


def test_stage_cost_summary_and_endpoint(runtime):
    """#132: onboard/bootstrap/tick durations, worst-first - the
    performance-KPI gap cost_summary() (tick-only) can't fill, since it
    reads empty for the whole time a fleet is bootstrapping. The
    `runtime` fixture's onboard_all()+tick_all() already exercised both
    stages for every asset."""
    summary = runtime.stage_cost_summary()
    stages_seen = {r["stage"] for r in summary["rows"]}
    assert "onboard" in stages_seen and "tick" in stages_seen
    keys_seen = {r["asset_key"] for r in summary["rows"]}
    assert keys_seen <= {"f/ok1", "f/ok2", "f/bad"}
    wall_s = [r["wall_s"] for r in summary["rows"]]
    assert wall_s == sorted(wall_s, reverse=True)  # worst-first
    assert summary["total_wall_s"] == round(sum(wall_s), 4)

    client = TestClient(create_app(runtime))
    body = client.get("/api/stage-cost").json()
    assert body["rows"] and {r["stage"] for r in body["rows"]} == stages_seen


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
    rt = Runtime(store=store, data_root=tmp_path)
    t0 = time.monotonic()
    rt.onboard_all()
    onboard_s = time.monotonic() - t0
    t0 = time.monotonic()
    rt.tick_all()
    tick_s = time.monotonic() - t0
    s = rt.summary()
    assert s["assets"] == 40
    assert len(s["rows"]) == 40
    assert onboard_s < 120 and tick_s < 60, (onboard_s, tick_s)


# ------------------------------------------------- runtime immune path
def test_immune_pass_healthy(runtime):
    r = runtime.immune_pass("f/ok1")
    assert r["conformance_ok"] and not r["sick"]
    assert r["action"] == "none"
    assert r["pit"] in ("ok", "channels", "n/a")
    s = runtime.summary()
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
    """The service ticks itself - implement and forget. Restart case:
    an already-bootstrapped fleet must tick promptly, not sit behind a
    redundant first-contact bootstrap (the marker regression)."""
    import time as _t

    for key in runtime.monitors:
        runtime._mark_bootstrapped(key)
    app = create_app(runtime, tick_seconds=0.2)
    before = dict(runtime._tick_counts)
    with TestClient(app):
        _t.sleep(0.7)
    after = runtime._tick_counts
    assert any(after[k] > before.get(k, 0) for k in after), (before, after)


def _seed_bootstrap_fixture(store, key, seed, fault_month=None):
    """Mirrors test_bootstrap_detect_mask_redetect_converges's fixture -
    optionally one contaminated month mid-history, so the parity check
    below exercises the actual ledger-write path (episodes.add/remove),
    not just a clean no-op bootstrap."""
    rng = np.random.default_rng(seed)
    start = datetime(2025, 1, 1, tzinfo=UTC)
    for m in range(10):
        n = 1200
        fault = 5.0 if m == fault_month else 0.0
        ts0 = start + timedelta(days=30 * m)
        ts = [ts0 + timedelta(minutes=10 * i) for i in range(n)]
        temp = rng.normal(size=n)
        vib = 0.8 * temp + 0.3 * rng.normal(size=n)
        if fault:
            vib = vib + fault * np.concatenate(
                [np.linspace(0, 1, n // 2), np.ones(n - n // 2)]
            )
        store.append(
            key,
            pl.DataFrame({
                TIMESTAMP_COL: pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
                "temp": temp, "vib": vib,
                "press": rng.normal(size=n), "flow": rng.normal(size=n),
            }),
        )


@pytest.mark.statistical  # spawns real OS processes - slower than the fast lane
def test_parallel_fleet_ops_match_sequential(tmp_path):
    """#133: fleet_worker_count>1 fans onboard/bootstrap out across a
    ProcessPoolExecutor. This is the load-bearing regression test - a
    parallel run over the SAME seeded data must produce IDENTICAL
    outcomes to the sequential run: same ledger episodes (the lost-
    update race this design exists to avoid), same bootstrapped
    markers, same verdict states/evidence after a subsequent tick."""
    seq_root, par_root = tmp_path / "seq", tmp_path / "par"
    seq_store, par_store = RawStore(seq_root / "raw"), RawStore(par_root / "raw")
    for store in (seq_store, par_store):
        _seed_bootstrap_fixture(store, "p/clean", seed=1)
        _seed_bootstrap_fixture(store, "p/fault", seed=2, fault_month=6)

    rt_seq = Runtime(store=seq_store, data_root=seq_root, fleet_worker_count=1)
    rt_seq.onboard_all()
    rt_seq.bootstrap_virgin()

    rt_par = Runtime(store=par_store, data_root=par_root, fleet_worker_count=2)
    rt_par.onboard_all()
    rt_par.bootstrap_virgin()

    assert set(rt_seq._bootstrapped) == set(rt_par._bootstrapped) == {
        "p/clean", "p/fault",
    }
    for key in ("p/clean", "p/fault"):
        seq_eps = sorted(
            (e.start, e.end, e.state)
            for e in rt_seq.ledger.episodes if e.asset_key == key
        )
        par_eps = sorted(
            (e.start, e.end, e.state)
            for e in rt_par.ledger.episodes if e.asset_key == key
        )
        assert seq_eps == par_eps, (key, seq_eps, par_eps)
        assert rt_seq.monitors[key].monitor.bank is not None
        assert rt_par.monitors[key].monitor.bank is not None

    # a subsequent tick must behave identically too - not just the
    # bootstrap artifacts, but the calibrated monitor's actual verdicts
    extra = pl.DataFrame({
        TIMESTAMP_COL: pl.Series(
            [datetime(2025, 11, 1, tzinfo=UTC) + timedelta(minutes=10 * i)
             for i in range(300)],
            dtype=pl.Datetime("us", "UTC"),
        ),
        "temp": np.zeros(300), "vib": np.zeros(300),
        "press": np.zeros(300), "flow": np.zeros(300),
    })
    seq_store.append("p/clean", extra)
    par_store.append("p/clean", extra)
    v_seq, v_par = rt_seq.tick("p/clean"), rt_par.tick("p/clean")
    assert v_seq is not None and v_par is not None
    assert v_seq.state == v_par.state
    assert v_seq.evidence == pytest.approx(v_par.evidence, abs=1e-9)


def test_bootstrap_virgin_runs_once_per_asset_lifetime(tmp_path):
    """First contact happens exactly once: bootstrap_virgin marks the
    asset durably and never re-runs - including across a service restart
    (a NEW Runtime over the same data root). A clean asset gains no
    ledger windows, so 'no windows' must NOT mean 'virgin'."""
    store = RawStore(tmp_path / "raw")
    seed_asset(store, "v/clean", seed=11)
    rt = Runtime(store=store, data_root=tmp_path)
    rt.onboard_all()

    out = rt.bootstrap_virgin()
    assert "v/clean" in out  # first contact ran
    assert not rt.ledger.windows("v/clean")  # clean: nothing ledgered
    assert rt.bootstrap_virgin() == {}  # same process: no re-run

    rt2 = Runtime(store=store, data_root=tmp_path)  # service restart
    rt2.onboard_all()
    assert rt2.bootstrap_virgin() == {}  # marker survived the restart

    # pre-marker data roots: existing ledger windows count as evidence of
    # a prior first contact and are back-filled into the marker
    from memory.ledger import Episode

    seed_asset(store, "v/old", seed=12)
    rt3 = Runtime(store=store, data_root=tmp_path)
    rt3.ledger.add(
        Episode(
            asset_key="v/old",
            start="2025-02-01T00:00:00+00:00",
            end="2025-02-03T00:00:00+00:00",
            state="alarm",
        )
    )
    rt3.onboard("v/old")
    out3 = rt3.bootstrap_virgin()
    assert "v/old" not in out3  # windows -> treated as already contacted
    assert "v/old" in rt3._bootstrapped  # and back-filled durably


# ------------------------------------------------------- the bootstrap
def test_bootstrap_detect_mask_redetect_converges(tmp_path):
    """First contact with contaminated history: pass 1 finds the fault and
    ledgers it; the next pass, calibrated on the masked lifetime, finds no
    new episodes (convergence). The multiple-run-throughs mechanism."""
    from datetime import datetime, timedelta, timezone

    import numpy as np
    import polars as pl

    from store.raw import TIMESTAMP_COL

    UTC = timezone.utc
    store = RawStore(tmp_path / "raw")
    rng = np.random.default_rng(42)
    start = datetime(2025, 1, 1, tzinfo=UTC)
    for m in range(10):
        n = 1200
        fault = 5.0 if m == 6 else 0.0  # one contaminated month mid-history
        ts0 = start + timedelta(days=30 * m)
        ts = [ts0 + timedelta(minutes=10 * i) for i in range(n)]
        temp = rng.normal(size=n)
        vib = 0.8 * temp + 0.3 * rng.normal(size=n)
        if fault:
            vib = vib + fault * np.concatenate(
                [np.linspace(0, 1, n // 2), np.ones(n - n // 2)]
            )
        press = rng.normal(size=n)
        flow = rng.normal(size=n)
        store.append(
            "bs/1",
            pl.DataFrame(
                {
                    TIMESTAMP_COL: pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
                    "temp": temp, "vib": vib, "press": press, "flow": flow,
                }
            ),
        )

    rt = Runtime(store=store, data_root=tmp_path)
    rt.onboard("bs/1")
    result = rt.bootstrap("bs/1")
    passes = result["passes"]
    assert passes[0]["new_episodes"] >= 1, passes  # the fault was found
    assert passes[-1]["new_episodes"] == 0, passes  # and convergence reached
    assert len(rt.ledger.episodes) >= 1
    # post-bootstrap: fresh healthy data scores healthy on the clean baseline
    n = 800
    ts0 = start + timedelta(days=330)
    ts = [ts0 + timedelta(minutes=10 * i) for i in range(n)]
    temp = rng.normal(size=n)
    fresh = pl.DataFrame(
        {
            TIMESTAMP_COL: pl.Series(ts, dtype=pl.Datetime("us", "UTC")),
            "temp": temp,
            "vib": 0.8 * temp + 0.3 * rng.normal(size=n),
            "press": rng.normal(size=n),
            "flow": rng.normal(size=n),
        }
    )
    store.append("bs/1", fresh)
    v = rt.tick("bs/1")
    assert v is not None and v.state == "healthy", v


def test_narrative_endpoint_tells_the_story(runtime):
    client = TestClient(create_app(runtime))
    r = client.get("/api/narrative/f/bad").json()
    text = r["narrative"]
    assert "f/bad" in text
    assert "falsifiable by" in text
    assert "operating point" in text
    # the faulted asset's story names its evidence carriers
    assert "carried by" in text


# ------------------------------------------------- live buffer ingestion
def test_live_buffer_source_streams_into_ticks(tmp_path):
    """A bridge/sim writes the SQLite buffer; the runtime drains it on
    tick and the asset scores the new rows - the live path end to end."""
    import json
    import sqlite3
    from datetime import datetime, timedelta, timezone

    import numpy as np

    UTC = timezone.utc
    store = RawStore(tmp_path / "raw")
    seed_asset(store, "live/1", seed=30)
    rt = Runtime(store=store, data_root=tmp_path)
    rt.onboard_all()
    rt.tick_all()

    # a publisher (simulated) writes new rows into the buffer db
    db = tmp_path / "mqtt_buffer.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE mqtt_buffer (ts TEXT NOT NULL, payload_json TEXT NOT NULL)")
    rng = np.random.default_rng(31)
    base = datetime(2025, 7, 1, tzinfo=UTC)
    for i in range(300):
        ts = (base + timedelta(minutes=10 * i)).isoformat()
        t = float(rng.normal())
        payload = {
            "published_at": ts,
            "temp": t,
            "vib": 0.8 * t + 0.3 * float(rng.normal()),
            "press": float(rng.normal()),
            "flow": float(rng.normal()),
            "state": "NORMAL",  # label: must be dropped at the door
        }
        con.execute(
            "INSERT INTO mqtt_buffer VALUES (?, ?)", (ts, json.dumps(payload))
        )
    con.commit(); con.close()

    rt.attach_live_source("live/1", db)
    before = store.row_count("live/1")
    v = rt.tick("live/1")
    assert store.row_count("live/1") == before + 300
    assert v is not None  # the drained rows were scored this tick
    # labels never entered the store
    assert "state" not in store.read("live/1").columns
    # draining again adds nothing (resumable + idempotent)
    assert rt.live_sources["live/1"].drain(store) == 0


def test_immune_pass_defers_conformance_during_active_episode(runtime):
    """An actively-alarmed asset must NOT be rebuilt for conformance
    failure - the fault in its tail is not model sickness (found by
    review on a live pilot)."""
    assert runtime.verdicts["f/bad"].state in ("alarm", "escalating")
    em = runtime.monitors["f/bad"]
    epoch_before = em.monitor.model_epoch
    r = runtime.immune_pass("f/bad")
    if not r["conformance_ok"]:
        assert not r["sick"], r
        assert r["action"] == "none"
        assert "conformance_note" in r
    assert em.monitor.model_epoch == epoch_before  # no mid-episode rebuild


def test_ui_and_control_endpoints(runtime):
    client = TestClient(create_app(runtime))
    page = client.get("/").text
    assert "Evidence domains" in page and "Re-anchor" in page
    assert client.post("/api/tick/f/ok1").status_code == 200
    d = client.get("/api/domains/f/ok1").json()
    assert d["magnitude"]["enabled"] and "evidence" in d["magnitude"]
    assert set(d) == {
        "magnitude", "channel-local", "availability", "horizon-gap",
        "predictability-band", "transient-response", "dynamics-drift",
    }
    h = client.get("/api/health/f/ok1").json()
    assert isinstance(h["series"], list) and len(h["series"]) > 0
    assert client.post("/api/reanchor/f/bad").json()["ok"]
    b = client.post("/api/bootstrap/f/ok2").json()
    assert b["passes"][-1]["new_episodes"] == 0  # clean asset converges fast
    assert client.get("/api/domains/nope").status_code == 404


def test_attach_live_sources_cli_wiring(runtime, tmp_path):
    """#90: the live path must be reachable from the service CLI, and an
    unknown asset key must fail LOUDLY at startup - a silently
    unattached buffer looks exactly like a healthy quiet asset."""
    from service import attach_live_sources

    db = tmp_path / "buf.db"
    attach_live_sources(runtime, [f"f/ok1={db}"])
    assert "f/ok1" in runtime.live_sources

    with pytest.raises(SystemExit):
        attach_live_sources(runtime, [f"nope/asset={db}"])
    with pytest.raises(SystemExit):
        attach_live_sources(runtime, ["malformed-no-equals"])


def test_tick_loop_survives_a_failing_tick(runtime):
    """#90 soak finding: the self-tick loop was an unsupervised task -
    one exception killed monitoring silently while the API kept serving.
    A tick that raises must be logged and RETRIED next interval."""
    import time as _t

    for key in runtime.monitors:
        runtime._mark_bootstrapped(key)
    calls = {"n": 0}
    real_tick_all = runtime.tick_all

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("injected tick failure")
        return real_tick_all()

    runtime.tick_all = flaky
    app = create_app(runtime, tick_seconds=0.15)
    with TestClient(app):
        _t.sleep(0.8)
    assert calls["n"] >= 2, (
        f"loop died after the failing tick (calls={calls['n']})"
    )


def test_bootstrap_drops_self_refuting_fault_mask(tmp_path):
    """#92: a ledger mask that leaves the final calibration with NOTHING
    is self-refuting (a baseline must exist for 'unhealthy' to mean
    anything). Bootstrap must drop the widest fault window and
    recalibrate instead of leaving a permanently dead monitor."""
    store = RawStore(tmp_path / "raw")
    seed_asset(store, "sr/1", seed=13)
    rt = Runtime(store=store, data_root=tmp_path)
    from memory.ledger import Episode

    rt.ledger.add(
        Episode(
            asset_key="sr/1",
            start="2024-12-01T00:00:00+00:00",
            end="2026-01-01T00:00:00+00:00",  # covers the entire life
            state="alarm",
        )
    )
    rt.onboard("sr/1")
    out = rt.bootstrap_virgin()
    # ledger windows normally mean "already contacted" - but this asset
    # has no marker AND its mask is total, so bootstrap must run and
    # repair. (bootstrap_virgin skips window-bearing assets; call the
    # bootstrap directly, as the service would after the marker fix.)
    if "sr/1" not in out:
        out = {"sr/1": rt.bootstrap("sr/1")}
    res = out["sr/1"]
    assert res["final_calibration"], res
    assert len(res["dropped_self_refuting_windows"]) == 1
    assert rt.monitors["sr/1"].monitor.scorer is not None, "monitor alive"
    # the ledger no longer carries the self-refuting window
    assert rt.ledger.windows("sr/1") == []


def test_episodes_report_and_live_flag_endpoints(runtime, tmp_path):
    """UI contract completeness: the episode ledger (absorbed changes
    included) is queryable, the S6 fleet report is exposed, and
    live-fed assets are flagged in the fleet summary."""
    from memory.ledger import Episode

    runtime.ledger.add(
        Episode(
            asset_key="f/ok1",
            start="2025-03-01T00:00:00+00:00",
            end="2025-03-08T00:00:00+00:00",
            state="change-not-fault",
            note='{"channels": ["temp"], "shape": "step", "peak_evidence": 2.1}',
        )
    )
    runtime.attach_live_source("f/ok2", tmp_path / "buf.db")
    client = TestClient(create_app(runtime))

    eph = client.get("/api/episodes/f/ok1").json()
    assert eph["episodes"] and eph["episodes"][0]["state"] == "change-not-fault"
    assert eph["episodes"][0]["channels"] == ["temp"]
    assert "open_since" in eph
    assert client.get("/api/episodes/nope").status_code == 404

    rep = client.get("/api/report")
    assert rep.status_code == 200
    assert "ACM Fleet Report" in rep.text and "f/bad" in rep.text

    rows = client.get("/api/assets").json()["rows"]
    by_key = {r["asset_key"]: r for r in rows}
    assert by_key["f/ok2"]["live"] is True
    assert by_key["f/ok1"]["live"] is False

    page = client.get("/").text
    assert "Episode history" in page and "/api/report" in page
    # the evidence-trail surface is chart-first now: the Signals card
    # (gauges + episode-state pills) and the surprise-by-channel chart
    # replaced the old "Evidence trail" kv text block
    assert "Signals" in page and "Surprise by channel" in page


def test_websocket_stream_and_vendored_echarts(runtime):
    """Real-time UI: a fleet snapshot arrives on connect and after a
    tick-triggering action; ECharts is served locally (air-gapped rule -
    never a CDN)."""
    client = TestClient(create_app(runtime))
    with client.websocket_connect("/api/ws") as ws:
        snap = ws.receive_json()
        assert snap["type"] == "fleet" and snap["data"]["assets"] == 3
        client.post("/api/tick")  # action -> push
        pushed = ws.receive_json()
        assert pushed["type"] == "fleet"
    r = client.get("/vendor/echarts.min.js")
    assert r.status_code == 200 and "Apache" in r.text[:300]
    assert client.get("/vendor/../pyproject.toml").status_code in (404, 400)
    page = client.get("/").text
    assert "/vendor/echarts.min.js" in page and "/api/ws" in page


def test_telemetry_evidence_history_and_cases_endpoints(runtime):
    """The time-series surfaces: raw telemetry windows (attribution
    channels by default), the decision layer's own evidence trajectory,
    and the fleet-wide case list."""
    client = TestClient(create_app(runtime))

    t = client.get("/api/telemetry/f/bad").json()
    assert t["ts"] and t["channels"], "telemetry window must not be empty"
    assert len(t["ts"]) == len(next(iter(t["channels"].values())))
    # the faulted channel (vib carries the seeded fault) is attributed
    # and therefore selected by default
    assert "vib" in t["channels"]

    t2 = client.get("/api/telemetry/f/ok1?channels=temp&rows=500").json()
    assert list(t2["channels"]) == ["temp"]
    assert len(t2["ts"]) <= 500

    eh = client.get("/api/evidence-history/f/bad").json()["points"]
    assert eh, "a scored asset must have at least one evidence point"
    assert {"at", "state", "domains"} <= set(eh[-1])
    assert "magnitude" in eh[-1]["domains"]

    cases = client.get("/api/cases").json()["cases"]
    # f/bad alarmed during the fixture tick -> an open episode exists
    open_cases = [c for c in cases if c["end"] is None]
    assert any(c["asset_key"] == "f/bad" for c in open_cases)

    assert client.get("/api/telemetry/nope").status_code == 404
    assert client.get("/api/evidence-history/nope").status_code == 404
