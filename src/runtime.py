"""Service runtime: hosts any number of independent per-asset monitors.

Ties the spine together per asset - episodic monitor over lifetime memory,
verdict cache, governed rebuild scheduling - and keeps the multi-asset
construction principle: one asset's tick never touches another's state.
One asset is a fleet of one; there is no single-asset mode.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

import fleet_workers as _fw
import verdict as V
from episodes import EpisodicMonitor
from hardware import Governor, probe, record_asset_cost, record_stage_cost
from memory.ledger import EpisodeLedger
from monitor import AssetMonitor
from store.raw import TIMESTAMP_COL, RawStore

REBUILD_EVERY_TICKS = 7 * 24  # weekly at hourly ticks (D3); staggered below
IMMUNE_EVERY_TICKS = 7 * 24  # weekly immune pass per asset; staggered
IMMUNE_SAMPLE_ROWS = 12000  # recent healthy rows used per immune pass


@dataclass
class Runtime:
    store: RawStore
    data_root: Path
    governor: Governor | None = None
    # evidence-lane override (#91): force a scorer class regardless of the
    # probed tier - verdict semantics are tier-free, so cross-tier
    # comparisons run the SAME runtime with only this swapped
    scorer_cls_override: type | None = None
    # #133: onboard/bootstrap fan out across a ProcessPoolExecutor when
    # > 1. Defaults to 1 (sequential, today's exact behavior) everywhere
    # a Runtime is constructed except the live service, which explicitly
    # passes the hardware-probed worker count - tests, the evidence
    # lane, and the soak are deliberately unaffected by default (tiny
    # synthetic fixtures have nothing to gain from pool-spawn overhead,
    # and a silent default-on would make the test suite flaky/slow).
    fleet_worker_count: int = 1
    monitors: dict[str, EpisodicMonitor] = field(default_factory=dict)
    verdicts: dict[str, V.Verdict] = field(default_factory=dict)
    previous_verdicts: dict[str, V.Verdict] = field(default_factory=dict)
    immune_results: dict[str, dict] = field(default_factory=dict)
    live_sources: dict[str, object] = field(default_factory=dict)
    _last_seen: dict[str, object] = field(default_factory=dict)
    _tick_counts: dict[str, int] = field(default_factory=dict)
    # asset_key -> current background activity ("bootstrapping"): an asset
    # being worked on must be visible in the fleet view, not silently absent
    busy: dict[str, str] = field(default_factory=dict)
    # rolling activity stream: WHAT the service is doing, step by step -
    # a status pill says "onboarding", this says "training channel 40/81".
    # on_activity (set by the service) pushes each event to the UI live.
    activity: object = None
    on_activity: object = None

    def __post_init__(self) -> None:
        from collections import deque

        self.activity = deque(maxlen=500)
        # per-asset evidence trajectory: one point per scoring event
        # ({at, state, domains: {name: evidence}}), rolling. The health
        # index shows surprise over life; THIS shows the decision layer's
        # own accumulation - evidence climbing toward the alarm line is
        # the product's central motion and was previously unplottable.
        self.evidence_history: dict[str, object] = {}
        self._evidence_history_len = 2000
        if self.governor is None:
            self.governor = Governor.from_probe(probe())
        self.ledger = EpisodeLedger(Path(self.data_root) / "ledger.json")
        self.cache_root = Path(self.data_root) / "memcache"
        # durable first-contact record: {asset_key: iso_utc_completed_at}.
        # "Virgin" means "never bootstrapped", NOT "no ledger windows" -
        # a clean asset never gains windows, so a windows-based test would
        # re-run the full multi-pass bootstrap on EVERY service start
        # (found by test: the tick loop sat behind a redundant bootstrap).
        self._bootstrapped_path = Path(self.data_root) / "bootstrapped.json"
        self._bootstrapped: dict[str, str] = {}
        if self._bootstrapped_path.exists():
            self._bootstrapped = json.loads(
                self._bootstrapped_path.read_text(encoding="utf-8")
            )

    # ----------------------------------------------------------- assets
    def _select_scorer_cls(self):
        """Tier-aware scorer selection (implementation plan 1.1): the
        world model at T2/T2-S when torch is importable; the conditional
        ridge everywhere else. Verdict semantics identical across tiers -
        only power differs; the guarantee is tier-free."""
        if self.scorer_cls_override is not None:
            return self.scorer_cls_override
        if self.governor.tier in ("T2", "T2-S"):
            try:
                from scoring.worldmodel import TorchWorldModel

                import torch  # noqa: F401

                return TorchWorldModel
            except ImportError:
                # a GPU-tier deployment silently degrading to the ridge
                # scorer must be VISIBLE - the tier badge alone would
                # keep claiming T2 while every asset scores at Tier 0
                if not getattr(self, "_fallback_logged", False):
                    self._fallback_logged = True
                    self.log(
                        "-", "service",
                        f"tier {self.governor.tier} but torch is not "
                        f"importable - FALLING BACK to "
                        f"ConditionalSurpriseScorer for all assets",
                    )
        from scoring.surprise import ConditionalSurpriseScorer

        return ConditionalSurpriseScorer

    def log(self, asset_key: str, kind: str, msg: str, at: str | None = None) -> None:
        """Append one activity event and push it to any live observer.
        kind is a short slug (onboard/bootstrap/tick/train/...) the UI
        colors by; msg is the human-readable step. `at` lets a caller
        replay a worker-process log line with its TRUE wall-clock
        timestamp (#133: a parallel worker's steps are buffered and
        replayed here only once the worker returns - the timestamp
        should reflect when the step actually happened, not when it
        was relayed)."""
        event = {
            "at": at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "asset_key": asset_key,
            "kind": kind,
            "msg": msg,
        }
        self.activity.append(event)
        if self.on_activity is not None:
            try:
                self.on_activity(event)
            except Exception:  # noqa: BLE001 - observer must never break work
                pass

    def _train_observer(self, asset_key: str):
        """Progress hook for the world-model training loop - logs
        periodically so a minutes-long fit is visibly alive."""

        def hook(done: int, total: int) -> None:
            self.log(
                asset_key,
                "train",
                f"world model: epoch {done}/{total} "
                f"(all channels batched)",
            )

        return hook

    # ---------------------------------------- calibrated-monitor cache
    # A service restart (or PC reboot) must never redo minutes of GPU
    # training: the fitted monitor is pickled to memcache, keyed by
    # everything that would change the fit - store content, ledger fault
    # windows, scorer class. Any mismatch = silent recalibration.
    def _monitor_fingerprint(self, asset_key: str, scorer_cls) -> str:
        # delegates to fleet_workers.monitor_fingerprint (#133) - the
        # SAME algorithm a worker process uses (no Runtime instance
        # available there), so the two can never drift apart. hashlib,
        # never hash(): builtin hash is salted per process, so a
        # hash()-based fingerprint can never match across a restart (or
        # a worker process) - which is the only time this cache matters.
        return _fw.monitor_fingerprint(self.store, self.ledger, asset_key, scorer_cls)

    @staticmethod
    def _stagger(asset_key: str, salt: int = 0) -> int:
        """Deterministic, restart-stable spread value for staggering
        rebuild/immune-pass timing across the fleet. Must be hashlib, never
        the builtin hash() - salted per process, so a hash()-based stagger
        silently reshuffles every asset's schedule offset on every restart
        (the exact failure mode _monitor_fingerprint's own docstring warns
        against, found reused here on a later read of this file)."""
        import hashlib

        digest = hashlib.sha1(f"{asset_key}:{salt}".encode()).hexdigest()
        return int(digest[:8], 16)

    def _monitor_cache_path(self, asset_key: str, scorer_cls) -> Path:
        return _fw.monitor_cache_path(
            self.cache_root, asset_key, self._monitor_fingerprint(asset_key, scorer_cls)
        )

    def _save_monitor_cache(self, asset_key: str) -> None:
        em = self.monitors[asset_key]
        try:
            fp = self._monitor_fingerprint(asset_key, em.monitor.scorer_cls)
            _fw.save_monitor_cache(em.monitor, self.cache_root, asset_key, fp)
        except Exception as exc:  # noqa: BLE001 - cache is an optimization
            self.log(asset_key, "service",
                     f"monitor cache save failed ({exc}) - will recalibrate "
                     f"on next start")

    def _load_monitor_cache(self, asset_key: str, scorer_cls):
        monitor = _fw.load_monitor_cache(
            self.cache_root, asset_key, scorer_cls, self.store, self.ledger
        )
        if monitor is not None and monitor.asset_key != asset_key:
            return None
        return monitor

    def onboard(self, asset_key: str) -> bool:
        scorer_cls = self._select_scorer_cls()
        cached = self._load_monitor_cache(asset_key, scorer_cls)
        if cached is not None:
            self.monitors[asset_key] = EpisodicMonitor(cached, self.ledger)
            self._tick_counts[asset_key] = 0
            self.log(
                asset_key,
                "onboard",
                "restored calibrated monitor from cache (store and ledger "
                "unchanged since last calibration)",
            )
            return True
        t0 = time.monotonic()
        monitor, ok = _fw.run_onboard(
            asset_key, self.store, self.ledger, self.cache_root, scorer_cls,
            progress=self._train_observer(asset_key),
            log=lambda kind, msg: self.log(asset_key, kind, msg),
        )
        em = EpisodicMonitor(monitor, self.ledger)
        self.monitors[asset_key] = em
        self._tick_counts[asset_key] = 0
        if not ok:
            self.verdicts[asset_key] = em.process(pl.DataFrame())
        else:
            self._save_monitor_cache(asset_key)
        dt = time.monotonic() - t0
        record_stage_cost(asset_key, "onboard", dt)
        self.log(
            asset_key,
            "onboard",
            f"{'calibrated' if ok else 'insufficient history'} "
            f"in {dt:.0f}s",
        )
        return ok

    def onboard_all(self, on_progress=None) -> dict[str, bool]:
        keys = list(self.store.assets())
        self.log(
            "-", "service",
            f"discovered {len(keys)} asset(s) in the raw store",
        )
        # every discovered asset is visible from the first moment: a
        # fleet being calibrated must never render as an empty fleet
        for key in keys:
            if key not in self.monitors:
                self.busy.setdefault(key, "queued")
        if on_progress is not None:
            on_progress()

        # cache hits are a pickle load, not worth a worker process - only
        # genuine calibration work (#133's actual cost) gets parallelized
        out: dict[str, bool] = {}
        to_calibrate: list[str] = []
        scorer_cls = self._select_scorer_cls()
        for key in keys:
            if self._load_monitor_cache(key, scorer_cls) is not None:
                self.busy[key] = "onboarding"
                if on_progress is not None:
                    on_progress()
                out[key] = self.onboard(key)
                self.busy.pop(key, None)
                if on_progress is not None:
                    on_progress()
            else:
                to_calibrate.append(key)

        out.update(self._onboard_parallel(to_calibrate, scorer_cls, on_progress))
        return out

    def _onboard_parallel(
        self, keys: list[str], scorer_cls, on_progress=None
    ) -> dict[str, bool]:
        """Fans calibrate_from_lifetime out across fleet_worker_count
        worker processes (#133). Falls back to the exact sequential loop
        when there is nothing to gain (fleet_worker_count<=1, or a
        single asset - pool-spawn overhead would only lose)."""
        out: dict[str, bool] = {}
        if not keys:
            return out
        if self.fleet_worker_count <= 1 or len(keys) <= 1:
            for key in keys:
                self.busy[key] = "onboarding"
                if on_progress is not None:
                    on_progress()
                out[key] = self.onboard(key)
                self.busy.pop(key, None)
                if on_progress is not None:
                    on_progress()
            return out

        from concurrent.futures import ProcessPoolExecutor, as_completed
        from concurrent.futures.process import BrokenProcessPool

        for key in keys:
            self.busy[key] = "onboarding"
        if on_progress is not None:
            on_progress()
        try:
            with ProcessPoolExecutor(
                max_workers=self.fleet_worker_count,
                mp_context=_fw.spawn_context(), initializer=_fw.worker_init,
            ) as pool:
                futures = {
                    pool.submit(
                        _fw.onboard_worker, key, str(self.store.root),
                        str(self.cache_root), scorer_cls,
                    ): key
                    for key in keys
                }
                for fut in as_completed(futures):
                    key = futures[fut]
                    try:
                        res = fut.result()
                    except BrokenProcessPool:
                        # pool-WIDE catastrophe (e.g. workers crashed at
                        # their own startup) - NOT a per-asset failure.
                        # Escalate rather than silently mis-reporting
                        # every asset as insufficient-history (found live:
                        # a caller without the multiprocessing spawn
                        # module's required `__main__` guard makes every
                        # worker crash before running any real work).
                        raise
                    except Exception as exc:  # noqa: BLE001
                        self.log(key, "service", f"onboard worker FAILED: {exc}")
                        em = EpisodicMonitor(
                            AssetMonitor(key, scorer_cls=scorer_cls), self.ledger
                        )
                        self.monitors[key] = em
                        self._tick_counts[key] = 0
                        self.verdicts[key] = em.process(pl.DataFrame())
                        out[key] = False
                    else:
                        for at, kind, msg in res["log_lines"]:
                            self.log(key, kind, msg, at=at)
                        if res["ok"]:
                            cached = self._load_monitor_cache(key, scorer_cls)
                            em = EpisodicMonitor(cached, self.ledger)
                        else:
                            em = EpisodicMonitor(
                                AssetMonitor(key, scorer_cls=scorer_cls), self.ledger
                            )
                        self.monitors[key] = em
                        self._tick_counts[key] = 0
                        if not res["ok"]:
                            self.verdicts[key] = em.process(pl.DataFrame())
                        record_stage_cost(key, "onboard", res["dt"])
                        out[key] = res["ok"]
                    self.busy.pop(key, None)
                    if on_progress is not None:
                        on_progress()
        except BrokenProcessPool as exc:
            self.log(
                "-", "service",
                f"parallel onboard pool failed to start ({exc}) - falling "
                "back to sequential for the remaining assets. If Runtime "
                "is constructed and onboard_all()/bootstrap_virgin() are "
                "called from a standalone script (not `python -m "
                "service`), that code needs an `if __name__ == "
                "'__main__':` guard - required by Python's multiprocessing "
                "spawn context (docs: 'Safe importing of main module').",
            )
            for key in keys:
                if key in out:
                    continue
                self.busy[key] = "onboarding"
                if on_progress is not None:
                    on_progress()
                out[key] = self.onboard(key)
                self.busy.pop(key, None)
                if on_progress is not None:
                    on_progress()
        return out

    def bootstrap_virgin(self, on_progress=None) -> dict[str, dict]:
        """First-contact cleaning for every never-bootstrapped asset:
        the detect->mask->re-detect loop (H1 fix: bootstrap existed but was
        never wired into the service path - contaminated first contact
        would never have been cleaned in production).

        Runs ONCE per asset lifetime, recorded in bootstrapped.json.
        Pre-marker data roots: existing ledger windows are accepted as
        evidence of a prior first contact (and back-filled into the
        marker), so old deployments are not re-bootstrapped either."""
        pending: list[str] = []
        out = {}
        for key in self.monitors:
            if key in self._bootstrapped:
                continue
            if self.ledger.windows(key):
                self._mark_bootstrapped(key)
                continue
            pending.append(key)
        out.update(self._bootstrap_parallel(pending, on_progress))
        return out

    def _bootstrap_parallel(
        self, keys: list[str], on_progress=None
    ) -> dict[str, dict]:
        """Fans first-contact bootstrap out across fleet_worker_count
        worker processes (#133) - the stage that dominates a fresh
        fleet's first minutes. Falls back to the exact sequential loop
        when there is nothing to gain."""
        out: dict[str, dict] = {}
        if not keys:
            return out
        if self.fleet_worker_count <= 1 or len(keys) <= 1:
            for key in keys:
                self.busy[key] = "bootstrapping"
                if on_progress is not None:
                    on_progress()
                try:
                    out[key] = self.bootstrap(key)
                finally:
                    self.busy.pop(key, None)
                    if on_progress is not None:
                        on_progress()
            return out

        from concurrent.futures import ProcessPoolExecutor, as_completed
        from concurrent.futures.process import BrokenProcessPool
        from dataclasses import asdict

        from memory.ledger import Episode

        scorer_cls = self._select_scorer_cls()
        for key in keys:
            self.busy[key] = "bootstrapping"
        if on_progress is not None:
            on_progress()
        try:
            with ProcessPoolExecutor(
                max_workers=self.fleet_worker_count,
                mp_context=_fw.spawn_context(), initializer=_fw.worker_init,
            ) as pool:
                futures = {
                    pool.submit(
                        _fw.bootstrap_worker, key, str(self.store.root),
                        str(self.cache_root), scorer_cls,
                        [
                            asdict(e) for e in self.ledger.episodes
                            if e.asset_key == key
                        ],
                    ): key
                    for key in keys
                }
                for fut in as_completed(futures):
                    key = futures[fut]
                    try:
                        res = fut.result()
                    except BrokenProcessPool:
                        # pool-WIDE catastrophe, not a per-asset failure -
                        # escalate (see _onboard_parallel's identical
                        # guard for why)
                        raise
                    except Exception as exc:  # noqa: BLE001
                        self.log(key, "service", f"bootstrap worker FAILED: {exc}")
                        # do not retry forever on a poison asset - a
                        # repeated crash on every service restart is worse
                        # than one asset staying in its pre-bootstrap state
                        self._mark_bootstrapped(key)
                        out[key] = {"asset": key, "error": str(exc)}
                    else:
                        for at, kind, msg in res["log_lines"]:
                            self.log(key, kind, msg, at=at)
                        # the parent is the ONLY ledger/marker writer -
                        # apply the worker's diff sequentially here, never
                        # inside a worker (fleet_workers.py module docstring)
                        for e in res["added_episodes"]:
                            self.ledger.add(Episode(**e))
                        for e in res["removed_episodes"]:
                            self.ledger.remove(Episode(**e))
                        self._last_seen[key] = res["last_seen"]
                        self._mark_bootstrapped(key)
                        if res["final_calibration"]:
                            cached = self._load_monitor_cache(key, scorer_cls)
                            if cached is not None:
                                self.monitors[key] = EpisodicMonitor(cached, self.ledger)
                                self._tick_counts[key] = 0
                        record_stage_cost(
                            key, "bootstrap", res["dt"], res["history_rows"]
                        )
                        out[key] = {
                            "asset": key,
                            "passes": res["passes"],
                            "final_calibration": res["final_calibration"],
                            "dropped_self_refuting_windows":
                                res["dropped_self_refuting_windows"],
                        }
                    self.busy.pop(key, None)
                    if on_progress is not None:
                        on_progress()
        except BrokenProcessPool as exc:
            self.log(
                "-", "service",
                f"parallel bootstrap pool failed to start ({exc}) - falling "
                "back to sequential for the remaining assets. If Runtime "
                "is constructed and onboard_all()/bootstrap_virgin() are "
                "called from a standalone script (not `python -m "
                "service`), that code needs an `if __name__ == "
                "'__main__':` guard - required by Python's multiprocessing "
                "spawn context (docs: 'Safe importing of main module').",
            )
            for key in keys:
                if key in out:
                    continue
                self.busy[key] = "bootstrapping"
                if on_progress is not None:
                    on_progress()
                try:
                    out[key] = self.bootstrap(key)
                finally:
                    self.busy.pop(key, None)
                    if on_progress is not None:
                        on_progress()
        return out

    def _mark_bootstrapped(self, asset_key: str) -> None:
        self._bootstrapped[asset_key] = datetime.now(timezone.utc).isoformat()
        self._bootstrapped_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._bootstrapped_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._bootstrapped, indent=1), encoding="utf-8"
        )
        tmp.replace(self._bootstrapped_path)

    def reanchor(self, asset_key: str) -> bool:
        """Governed episode close + recalibration, exposed for the UI."""
        em = self.monitors[asset_key]
        v = self.verdicts.get(asset_key)
        if v is None:
            return False
        ok = em.reanchor(self.store, v, cache_root=self.cache_root)
        if ok:
            self.previous_verdicts[asset_key] = v
            self.log(asset_key, "service",
                     "re-anchored: episode closed, baseline recalibrated")
            self._save_monitor_cache(asset_key)
        return ok

    def health_series(self, asset_key: str) -> list[float]:
        em = self.monitors.get(asset_key)
        return list(em._health_index) if em is not None else []

    def domains(self, asset_key: str) -> dict:
        """Per-domain bank states for the UI evidence panel.

        Includes each domain's per-block-size member wealth (`members`),
        not just the aggregate evidence/alarmed rollup: a verdict's own
        evidence_trail only ever carries member detail for whichever ONE
        domain won the state-priority resolution (monitor.py's
        aux_states loop) - a tick decided by, say, dynamics-drift shows
        NO block-size breakdown for any bank at all, including the
        magnitude bank that lost. domains() reads bank.state() live and
        independently of that resolution, so it is the one place every
        bank's own timescale detail is visible on every tick regardless
        of which domain's alarm actually drove the verdict."""
        m = self.monitors[asset_key].monitor
        out = {}
        pairs = [
            ("magnitude", m.bank),
            # getattr: monitors unpickled from a pre-#115 cache
            ("channel-local", getattr(m, "chan_bank", None)),
            ("availability", m.avail_bank),
            ("horizon-gap", m.gap_bank),
            ("predictability-band", m.band_bank),
            ("transient-response", m.trans_bank),
            ("dynamics-drift", m.dyn_bank),
        ]
        for name, bank in pairs:
            if bank is None:
                out[name] = {"enabled": False}
            else:
                st = bank.state()
                out[name] = {
                    "enabled": True,
                    "alarmed": st.alarmed,
                    "evidence": round(st.evidence, 4),
                    # >0 = the guarantee armed with residual correlation
                    # left at the block scale: QUALIFIED, not clean (#114)
                    "exchangeability_acf": getattr(
                        bank, "exchangeability_acf", 0.0
                    ),
                    "members": {
                        str(block_size): {
                            "log_wealth": round(lw, 3),
                            "alarmed": al,
                        }
                        for block_size, (lw, al) in st.member_states.items()
                    },
                }
        return out

    def cost_summary(self) -> dict:
        """Last-tick wall-clock cost per asset (hardware.MEASURED_COSTS),
        worst-first - which assets are actually expensive to score, not
        just which ones exist. Computed at every tick in Runtime.tick()
        but never surfaced anywhere before this (#113)."""
        from hardware import MEASURED_COSTS

        rows = sorted(
            (
                {
                    "asset_key": key,
                    "wall_s": round(cost["wall_s"], 4),
                    "rows": int(cost["rows"]),
                    "rows_per_s": (
                        round(cost["rows"] / cost["wall_s"], 1)
                        if cost["wall_s"] > 0
                        else None
                    ),
                }
                for key, cost in MEASURED_COSTS.items()
                if key in self.monitors
            ),
            key=lambda d: -d["wall_s"],
        )
        return {
            "rows": rows,
            "total_wall_s": round(sum(r["wall_s"] for r in rows), 4),
        }

    def stage_cost_summary(self) -> dict:
        """Wall-clock cost per (asset, stage), worst-first (#132): unlike
        cost_summary() above (tick only, overwritten every tick),
        this covers onboard and bootstrap too - the stages that
        dominate a fleet's first minutes and previously had NO
        visibility at all (the Tick-cost card reads empty for the
        entire time a fleet is bootstrapping)."""
        from hardware import STAGE_COSTS

        rows = sorted(
            (
                {
                    "asset_key": row["asset_key"],
                    "stage": row["stage"],
                    "wall_s": round(row["wall_s"], 4),
                    "rows": int(row["rows"]),
                    "rows_per_s": (
                        round(row["rows"] / row["wall_s"], 1)
                        if row["wall_s"] > 0 and row["rows"] > 0
                        else None
                    ),
                }
                for row in STAGE_COSTS.values()
                if row["asset_key"] in self.monitors
            ),
            key=lambda d: -d["wall_s"],
        )
        return {
            "rows": rows,
            "total_wall_s": round(sum(r["wall_s"] for r in rows), 4),
        }

    def _record_evidence_point(self, asset_key: str, verdict) -> None:
        """One evidence-trajectory point per scoring event: timestamp,
        state word, and every enabled domain's current evidence."""
        from collections import deque

        hist = self.evidence_history.get(asset_key)
        if hist is None:
            hist = self.evidence_history[asset_key] = deque(
                maxlen=self._evidence_history_len
            )
        doms = self.domains(asset_key)
        hist.append(
            {
                "at": str(verdict.at),
                "state": verdict.state,
                "domains": {
                    name: d["evidence"]
                    for name, d in doms.items()
                    if d.get("enabled")
                },
            }
        )

    def evidence_series(self, asset_key: str) -> list[dict]:
        return list(self.evidence_history.get(asset_key, ()))

    def telemetry(
        self,
        asset_key: str,
        channels: list[str] | None = None,
        rows: int = 20000,
        max_points: int = 1500,
    ) -> dict:
        """A recent window of the RAW telemetry, downsampled for display.

        Channel selection when none are requested: the current verdict's
        attribution first (the channels carrying the surprise are the
        ones worth looking at), then the first numeric columns as a
        fallback - capped at 6 so the chart stays readable. Values are
        returned raw; scaling for display is the UI's concern."""
        frame = self.store.read_tail(asset_key, rows)
        if frame.is_empty():
            return {"ts": [], "channels": {}}
        numeric = [
            c
            for c, dt in frame.schema.items()
            if c != TIMESTAMP_COL and dt.is_numeric()
        ]
        if channels:
            picked = [c for c in channels if c in numeric][:6]
        else:
            v = self.verdicts.get(asset_key)
            attributed = [
                c for c in (v.attribution if v else ()) if c in numeric
            ]
            picked = list(
                dict.fromkeys(list(attributed) + numeric)
            )[:6]
        stride = max(1, frame.height // max_points)
        thin = frame.gather_every(stride)
        return {
            "ts": [str(t) for t in thin.get_column(TIMESTAMP_COL).to_list()],
            "channels": {
                c: [
                    (float(x) if x is not None else None)
                    for x in thin.get_column(c).to_list()
                ]
                for c in picked
            },
        }

    def fleet_cases(self) -> list[dict]:
        """Every episode across the fleet - ledgered (closed) AND open -
        for the fleet case timeline. The ledger is the fleet's case
        history; an invisible case history is a wasted one."""
        import json as _json

        out = []
        for e in self.ledger.episodes:
            note = {}
            if e.note:
                try:
                    note = _json.loads(e.note)
                except _json.JSONDecodeError:
                    pass
            out.append(
                {
                    "asset_key": e.asset_key,
                    "start": e.start,
                    "end": e.end,
                    "state": e.state,
                    "shape": note.get("shape"),
                    "channels": (note.get("channels") or [])[:4],
                    "peak_evidence": note.get("peak_evidence"),
                }
            )
        for key, em in self.monitors.items():
            if em.open_episode_start:
                v = self.verdicts.get(key)
                out.append(
                    {
                        "asset_key": key,
                        "start": em.open_episode_start,
                        "end": None,  # open
                        # the asset's own latest observation - open means
                        # "through the last thing we saw", never through
                        # wall-clock now (asset clocks can lag by months
                        # on backfilled or time-compressed feeds)
                        "last_at": str(v.at) if v else None,
                        "state": v.state if v else "alarm",
                        "shape": None,
                        "channels": list(v.attribution[:4]) if v else [],
                        "peak_evidence": v.evidence if v else None,
                    }
                )
        out.sort(key=lambda d: str(d["start"]))
        return out

    def attach_live_source(self, asset_key: str, db_path) -> None:
        """Attach a SQLite buffer (bridge/sim-fed) to an asset; drained
        on every tick before scoring."""
        from ingest.buffer_source import BufferSource

        self.live_sources[asset_key] = BufferSource(
            db_path=db_path, asset_key=asset_key
        )

    # ------------------------------------------------------------ ticks
    def tick(self, asset_key: str) -> V.Verdict | None:
        """Score any new rows for one asset; returns the verdict if new
        data was seen. Rebuilds are staggered by asset-index offset so a
        fleet never rebuilds at once."""
        em = self.monitors[asset_key]
        started = time.monotonic()
        src = self.live_sources.get(asset_key)
        if src is not None:
            src.drain(self.store)  # live buffer -> immortal store, then read
        since = self._last_seen.get(asset_key)
        frame = self.store.read(asset_key, start=since)
        if since is not None and not frame.is_empty():
            frame = frame.filter(pl.col(TIMESTAMP_COL) > since)
        verdict = None
        if not frame.is_empty():
            self._last_seen[asset_key] = frame.get_column(TIMESTAMP_COL).max()
            verdict = em.process(frame)
            if asset_key in self.verdicts:
                self.previous_verdicts[asset_key] = self.verdicts[asset_key]
            self.verdicts[asset_key] = verdict
            self._record_evidence_point(asset_key, verdict)
            prev = self.previous_verdicts.get(asset_key)
            self.log(
                asset_key,
                "tick",
                f"scored {frame.height} new rows -> {verdict.state} "
                f"(evidence {verdict.evidence:.2f})"
                + (
                    f" [was {prev.state}]"
                    if prev is not None and prev.state != verdict.state
                    else ""
                ),
            )
            if self._change_ripe_for_absorption(em, verdict):
                # governed auto-absorption (#89): the verdict's own
                # re-baseline proposal, executed - unattended operation
                # cannot wait for a human to click Re-anchor. Only while
                # the CURRENT classification is still change-not-fault;
                # a drift reclassification blocks it (the definition of
                # normal never moves during accumulating degradation).
                if em.reanchor(
                    store=self.store,
                    last_verdict=verdict,
                    cache_root=self.cache_root,
                ):
                    self.previous_verdicts[asset_key] = verdict
                    self.log(
                        asset_key, "service",
                        "change-not-fault absorbed: baseline re-anchored",
                    )
                    self._save_monitor_cache(asset_key)
        self._tick_counts[asset_key] += 1
        stagger = self._stagger(asset_key, salt=0) % REBUILD_EVERY_TICKS
        if (
            self._tick_counts[asset_key] + stagger
        ) % REBUILD_EVERY_TICKS == 0 and em.open_episode_start == "":
            # governed rebuild: never while an episode is open (the
            # definition of normal does not move during accumulating
            # evidence of degradation)
            self.log(asset_key, "service",
                     "scheduled rebuild: recalibrating from lifetime")
            em.monitor.calibrate_from_lifetime(
                self.store, ledger=self.ledger, cache_root=self.cache_root
            )
            self._save_monitor_cache(asset_key)
        stagger_i = self._stagger(asset_key, salt=1) % IMMUNE_EVERY_TICKS
        if (self._tick_counts[asset_key] + stagger_i) % IMMUNE_EVERY_TICKS == 0:
            self.immune_pass(asset_key)
        dt = time.monotonic() - started
        record_asset_cost(asset_key, dt, frame.height)
        record_stage_cost(asset_key, "tick", dt, frame.height)
        return verdict

    @staticmethod
    def _change_ripe_for_absorption(em, verdict: V.Verdict) -> bool:
        """True when an open change-not-fault episode's plateau has held
        for CHANGE_ABSORB_ANCHOR_PERIODS anchor periods (#89)."""
        if verdict.state != V.STATE_CHANGE or not em.open_episode_start:
            return False
        from constants import get as const

        anchor_s = (
            365.25 * 24 * 3600.0 / float(const("REANCHORS_PER_YEAR"))
        ) * float(const("CHANGE_ABSORB_ANCHOR_PERIODS"))
        try:
            start = datetime.fromisoformat(em.open_episode_start)
            now = datetime.fromisoformat(str(verdict.at))
        except ValueError:
            return False
        return (now - start).total_seconds() >= anchor_s

    def tick_all(self) -> int:
        moved = 0
        t0 = time.monotonic()
        for key in list(self.monitors):
            if self.tick(key) is not None:
                moved += 1
        # heartbeat: a pass where nothing had new data is still a pass -
        # a silent loop is indistinguishable from a dead one
        self.log(
            "-", "tick",
            f"fleet pass: {moved}/{len(self.monitors)} asset(s) had new "
            f"data ({time.monotonic() - t0:.1f}s)",
        )
        return moved

    # -------------------------------------------------------- bootstrap
    def bootstrap(self, asset_key: str, max_iters: int = 4) -> dict:
        """First contact with an asset's history: DETECT -> MASK ->
        RE-DETECT to convergence (rethink plan bootstrap requirement).

        Delegates the algorithm to fleet_workers.run_bootstrap (#133) -
        the SAME function a parallel worker process runs, parameterized
        with THIS runtime's real store/ledger/cache_root instead of a
        worker's private throwaway ledger. Sequential callers (this
        method, used by bootstrap_virgin's fallback and the single-asset
        /api/bootstrap/{key} trigger) need no diff-and-apply step since
        self.ledger IS the real ledger - writes land directly.
        """
        _bootstrap_started = time.monotonic()
        em = self.monitors[asset_key]
        result = _fw.run_bootstrap(
            asset_key, self.store, self.ledger, em, self.cache_root,
            max_iters, log=lambda kind, msg: self.log(asset_key, kind, msg),
            progress=self._train_observer(asset_key),
        )
        self._last_seen[asset_key] = result["last_seen"]
        self._mark_bootstrapped(asset_key)
        record_stage_cost(
            asset_key, "bootstrap",
            time.monotonic() - _bootstrap_started, result["history_rows"],
        )
        return {
            "asset": asset_key,
            "passes": result["passes"],
            "final_calibration": result["final_calibration"],
            "dropped_self_refuting_windows": result["dropped_self_refuting_windows"],
        }

    # ----------------------------------------------------- immune path
    def immune_pass(self, asset_key: str) -> dict:
        """Scheduled self-validation (S2 harness + PIT conformance), the
        unattended answer to 'is the detector still alive?'. Failures are
        first-class events: the finding is recorded, and a rebuild is
        triggered immediately (the governed response to a sick model)."""
        em = self.monitors[asset_key]
        # "healthy" here matches the baseline's definition: fault windows
        # excluded, absorbed change-not-fault regimes kept
        from memory.ledger import FAULT_STATES

        frame = self.ledger.mask(
            asset_key, self.store.read(asset_key), states=FAULT_STATES
        )
        if frame.height > IMMUNE_SAMPLE_ROWS:
            frame = frame.tail(IMMUNE_SAMPLE_ROWS)

        from immune import degeneracy_check, sensitivity_profile
        from scoring.surprise import classify_pit_distortion

        report = sensitivity_profile(asset_key, frame)
        result = report.to_dict()

        # THE LIVE-INSTANCE CHECK: the harness profiles the pipeline RECIPE
        # (fresh monitors fit on the sample) - it cannot see a dead LIVE
        # scorer. Found by test: a zeroed deployed scorer passed the recipe
        # profile. The live scorer's own recent output is checked directly.
        live = self.monitors[asset_key].monitor.scorer
        live_dead = True
        if live is not None and frame.height > 0:
            live_dead = degeneracy_check(
                live.score(frame.tail(min(frame.height, 2000)))
            )
        result["live_degenerate"] = live_dead

        # PIT conformance is an immune signal ONLY while not alarmed
        # (during a real fault, coupled distortion is expected)
        current = self.verdicts.get(asset_key)
        not_alarmed = current is None or current.state in (
            V.STATE_HEALTHY,
            V.STATE_WATCH,
            V.STATE_INSUFFICIENT,
        )
        pit_verdict = "n/a"
        scorer = em.monitor.scorer
        if not_alarmed and scorer is not None and hasattr(scorer, "pit"):
            tail = frame.tail(min(frame.height, 4000))
            pits = scorer.pit(tail)
            pit_verdict, _ks = classify_pit_distortion(pits, scorer.channels)
        result["pit"] = pit_verdict

        # C8: rehearse the LIVE pipeline against self-imagined coherent
        # faults - the measured sensitivity floor, refreshed weekly
        live = self.monitors[asset_key].monitor.scorer
        bank = self.monitors[asset_key].monitor.bank
        if (
            live is not None
            and bank is not None
            and hasattr(live, "betas")
            and frame.height > 1000
        ):
            from immune.rehearsal import rehearse

            rmap = rehearse(
                live,
                frame.tail(min(frame.height, 2500)),
                # the RAW calibration stream - a member's _calib_sorted is
                # sorted, which reads ~0.9 autocorrelated and made every
                # rehearsal bank derive blocks over a monotone staircase
                # (latent bug exposed by the #114 exchangeability audit)
                getattr(bank, "calibration_scores", None)
                if getattr(bank, "calibration_scores", None) is not None
                else bank.members[0]._calib_sorted,
            )
            result["rehearsal"] = {
                "floors": rmap.floors,
                "overall_floor": rmap.overall_floor,
                "detected_fraction": round(rmap.detected_fraction, 3),
                "scope": rmap.scope,
                "skipped_reason": rmap.skipped_reason,
            }

        # Conformance (like PIT) is an immune signal ONLY while the asset
        # is not alarmed: during an active episode the 'recent healthy
        # tail' assumption is violated by the fault itself, and a rebuild
        # here would move the definition of normal DURING accumulating
        # evidence - the exact thing the tick-path rebuild gate forbids.
        # Found by review: an actively-faulted pilot was being flagged
        # 'model sick' and rebuilt mid-episode.
        sick = report.scorer_dead or live_dead or (
            not_alarmed
            and (not report.conformance_ok or pit_verdict == "model")
        )
        result["sick"] = sick
        if not not_alarmed and (not report.conformance_ok):
            result["conformance_note"] = (
                "conformance failure observed during an ACTIVE episode - "
                "expected (the fault is in the sample); deferred to the "
                "post-reanchor pass"
            )
        result["action"] = "rebuild" if sick else "none"
        if sick:
            em.monitor.calibrate_from_lifetime(
                self.store, ledger=self.ledger, cache_root=self.cache_root
            )
        self.immune_results[asset_key] = result
        return result

    def narrative_sections(self, asset_key: str) -> list[dict] | None:
        from narrative import build_narrative_sections

        v = self.verdicts.get(asset_key)
        if v is None:
            return None
        return build_narrative_sections(
            v,
            previous=self.previous_verdicts.get(asset_key),
            immune=self.immune_results.get(asset_key),
        )

    @staticmethod
    def _budget_summary() -> dict:
        """The alpha ledger: the promised false-alarm budget and its split
        across evidence domains (union bound - shares sum to 1.0)."""
        import monitor as M
        from constants import get as const

        return {
            "alpha_per_asset_year": float(const("ALPHA_PER_ASSET_YEAR")),
            "reanchors_per_year": int(const("REANCHORS_PER_YEAR")),
            "shares": {
                "magnitude": M.MAGNITUDE_ALPHA_SHARE,
                "channel-local": M.CHANNEL_LOCAL_ALPHA_SHARE,
                "availability": M.AVAILABILITY_ALPHA_SHARE,
                "horizon-gap": M.HORIZON_GAP_ALPHA_SHARE,
                "predictability-band": M.BAND_ALPHA_SHARE,
                "transient-response": M.TRANSIENT_ALPHA_SHARE,
                "dynamics-drift": M.DYNAMICS_ALPHA_SHARE,
            },
        }

    # -------------------------------------------------------- aggregates
    def summary(self) -> dict:
        counts: dict[str, int] = {}
        for v in self.verdicts.values():
            counts[v.state] = counts.get(v.state, 0) + 1
        # onboarded assets with no verdict yet: background work in progress.
        # They MUST appear in the fleet view - an invisible asset looks
        # exactly like a missing one (same lesson as the live-buffer pill)
        pending = {
            key: self.busy.get(key, "queued")
            for key in self.monitors
            if key not in self.verdicts
        }
        # assets still being onboarded have no monitor yet - they are
        # visible via the busy map alone
        for key, state in self.busy.items():
            if key not in self.monitors:
                pending[key] = state
        for state in pending.values():
            counts[state] = counts.get(state, 0) + 1
        worst_order = [
            V.STATE_ESCALATING,
            V.STATE_ALARM,
            V.STATE_CHANGE,
            V.STATE_WATCH,
            V.STATE_INSUFFICIENT,
            V.STATE_HEALTHY,
        ]
        rank = {s: i for i, s in enumerate(worst_order)}
        rows = sorted(
            (
                {
                    **v.to_dict(),
                    # a live-fed asset must be recognizable in the fleet
                    # view - a silent buffer otherwise looks exactly like
                    # a healthy quiet asset (#90 lesson)
                    "live": key in self.live_sources,
                }
                for key, v in self.verdicts.items()
            ),
            key=lambda d: (rank.get(d["state"], 99), -d["evidence"]),
        )
        rows += [
            {
                "asset_key": key,
                "state": state,
                "evidence": 0.0,
                "confidence": 0.0,
                "at": None,
                "live": key in self.live_sources,
            }
            for key, state in sorted(pending.items())
        ]
        immune_sick = sum(
            1 for r in self.immune_results.values() if r.get("sick")
        )
        return {
            "assets": len(set(self.monitors) | set(self.busy)),
            "counts": counts,
            "tier": self.governor.tier,
            # the SCORER ACTUALLY IN USE, not what the tier implies - a
            # torch import failure at T2 silently degrades to the ridge
            # scorer, and that mismatch must be visible in the UI
            "scorer": self._select_scorer_cls().__name__,
            "immune": {
                "checked": len(self.immune_results),
                "sick": immune_sick,
            },
            # the ONE dial and how it is allocated - the guarantee is the
            # product, so the UI must be able to show it, not just imply it
            "budget": self._budget_summary(),
            "rows": rows,
        }
