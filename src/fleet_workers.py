"""Parallel fleet onboard/bootstrap workers (#133).

Every asset is an independent world (own scorer, banks, ledger-masked
baseline) - the architecture principle that makes per-asset parallelism
SAFE in principle. What is NOT safe is naive fan-out: EpisodeLedger and
the bootstrapped-marker are each a SINGLE SHARED FILE for the whole
fleet, loaded fully into memory and rewritten whole on every write
(memory.ledger.EpisodeLedger._save(), runtime.Runtime._mark_bootstrapped()).
Two OS processes writing either concurrently is a lost-update race: each
holds its own in-memory copy, and whichever process's full-list rewrite
lands last silently drops the other's addition.

The fix used here: workers never touch a shared file.
  - Read-only shared state (the raw store; the ledger during ONBOARD,
    which never writes to it) is opened directly by the worker - safe,
    many readers, no writer.
  - Write-needing shared state (the ledger during BOOTSTRAP's multi-pass
    detect loop) is instead a PRIVATE, per-worker, throwaway ledger
    seeded with a snapshot of just that asset's own episodes. The worker
    runs the full algorithm against its private copy and returns only
    the DIFF (episodes added/removed) as plain picklable dicts. The
    PARENT process is the only writer of the real ledger and
    bootstrapped-marker files, applying each worker's diff sequentially
    as futures complete.
  - Fitted monitor state crosses the boundary through the EXISTING
    on-disk cache file (runtime.py's monitor-cache pickle), not through
    ad-hoc pickling of a live scorer object: cache paths are already
    keyed per-asset (safe for concurrent writers to DIFFERENT files),
    so a worker leaves exactly the artifact the parent already knows
    how to load - no new serialization format, no risk from an
    odd-to-pickle fitted model (e.g. a Tier-2 torch net).

BLAS thread-count guard: worker_init() runs once per worker process,
BEFORE the pool's first task (and therefore before numpy is imported -
a spawned worker only imports the task's module, and therefore numpy,
when it unpickles the first submitted callable). Unconstrained BLAS
thread pools forking under load were the predecessor system's
documented, hard-won deadlock (CLAUDE.md mistake #44: large ELAPSED,
near-zero CPU, workers parked in futex_do_wait - OpenBLAS holding an
internal lock in the parent, copied mid-lock into a forked child).
spawn_context() (spawn, never fork) is a second, independent line of
defense: a freshly spawned interpreter never inherits a partially
locked BLAS state from the parent to begin with.

Runtime.fleet_workers defaults to 1 (sequential, today's behavior,
unchanged) everywhere except the live service, which explicitly passes
the hardware-probed worker count - tests, the evidence lane, and the
soak are deliberately unaffected by default.
"""

from __future__ import annotations

import json
import multiprocessing
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from store.raw import TIMESTAMP_COL


def worker_init() -> None:
    """Runs once per worker process, before any task's module (and
    therefore numpy) is imported. Reuses hardware.set_thread_caps - the
    SAME guard the entrypoint sets, so worker and parent can never
    disagree - as a second, independent line of defense: even if a
    worker's environment somehow didn't inherit the parent's already-set
    vars, this still catches it before the worker's first numpy import."""
    from hardware import set_thread_caps

    set_thread_caps(1)


def spawn_context():
    """spawn, never fork - see module docstring."""
    return multiprocessing.get_context("spawn")


def scan_contamination(
    ts_col, scores, window: int = 256, mads: float = 4.0
) -> list[tuple[str, str]]:
    """Contiguous elevated blocks in the lifetime score trace.

    The e-process cannot detect contamination sitting INSIDE its own
    calibration reference. The discriminator (inherited from the lab's
    contamination-filter post-mortem): genuine contamination is a
    CONTIGUOUS block of elevated surprise; legitimate rare operation is
    scattered tail values. Percentile trimming is banned (it deletes
    healthy variance); block scanning flags only sustained runs.

    Moved here from Runtime._scan_contamination (#133) so run_bootstrap
    below can call it without importing runtime.py (which imports THIS
    module - a cycle).
    """
    import numpy as np

    s = np.asarray(scores, dtype=np.float64)
    n = s.size
    if n < 4 * window:
        return []
    k = n // window
    wm = s[: k * window].reshape(k, window).mean(axis=1)
    med = float(np.median(wm))
    mad = 1.4826 * float(np.median(np.abs(wm - med)))
    mad = max(mad, 1e-9)
    hot = wm > med + mads * mad
    regions, start = [], None
    for i, h in enumerate(hot):
        if h and start is None:
            start = i
        elif not h and start is not None:
            regions.append((start, i))
            start = None
    if start is not None:
        regions.append((start, k))
    out = []
    for a, b in regions:
        t0 = str(ts_col[a * window])
        t1 = str(ts_col[min(b * window, n - 1)])
        out.append((t0, t1))
    return out


# ------------------------------------------------------- monitor cache
# Free-function equivalents of Runtime's cache instance methods (#133):
# usable from a worker process, which has no Runtime instance. Runtime
# delegates to these too, so there is exactly one cache algorithm.
def monitor_fingerprint(store, ledger, asset_key: str, scorer_cls) -> str:
    import hashlib

    from _version import __version__ as _ver
    from memory.ledger import FAULT_STATES

    windows = tuple(ledger.windows(asset_key, states=FAULT_STATES))
    span = store.span(asset_key)
    raw = (
        store.row_count(asset_key),
        str(span[1]) if span else "",
        windows,
        scorer_cls.__name__,
        _ver,
    )
    # hashlib, NEVER hash(): builtin hash is salted per process, so a
    # hash()-based fingerprint can never match across a restart (or a
    # different worker process) - which is the only time this matters
    return hashlib.sha1(repr(raw).encode()).hexdigest()[:16]


def monitor_cache_path(cache_root, asset_key: str, fingerprint: str) -> Path:
    from store.raw import _safe_key

    d = Path(cache_root) / _safe_key(asset_key)
    d.mkdir(parents=True, exist_ok=True)
    return d / f"monitor-{fingerprint}.pkl"


def save_monitor_cache(
    monitor, cache_root, asset_key: str, fingerprint: str
) -> None:
    import pickle

    path = monitor_cache_path(cache_root, asset_key, fingerprint)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(pickle.dumps(monitor))
    tmp.replace(path)
    # stale fingerprints of this asset are dead weight
    for old in path.parent.glob("monitor-*.pkl"):
        if old != path:
            old.unlink(missing_ok=True)


def load_monitor_cache(cache_root, asset_key: str, scorer_cls, store, ledger):
    import pickle

    fingerprint = monitor_fingerprint(store, ledger, asset_key, scorer_cls)
    path = monitor_cache_path(cache_root, asset_key, fingerprint)
    if not path.exists():
        return None
    try:
        return pickle.loads(path.read_bytes())
    except Exception:  # noqa: BLE001 - a corrupt cache must not crash onboard
        return None


# --------------------------------------------------- shared algorithms
def run_onboard(asset_key, store, ledger, cache_root, scorer_cls, progress=None, log=None):
    """calibrate_from_lifetime for one asset. Returns (AssetMonitor, ok).
    Shared verbatim by Runtime.onboard() (sequential) and onboard_worker
    (parallel) - one algorithm, two callers."""
    from monitor import AssetMonitor
    from scoring import worldmodel as _wm

    if log is None:
        log = lambda kind, msg: None  # noqa: E731

    log("onboard", f"calibrating from lifetime history (scorer {scorer_cls.__name__})")
    m = AssetMonitor(asset_key, scorer_cls=scorer_cls)
    _wm.on_progress = progress
    try:
        ok = m.calibrate_from_lifetime(store, ledger=ledger, cache_root=cache_root)
    finally:
        _wm.on_progress = None
    return m, ok


def run_bootstrap(asset_key, store, ledger, em, cache_root, max_iters=4, log=None, progress=None) -> dict:
    """First contact: DETECT -> MASK -> RE-DETECT to convergence.

    Moved verbatim from Runtime.bootstrap() (#133) - identical algorithm,
    parameterized instead of reading self.*, so Runtime.bootstrap()
    (sequential) and bootstrap_worker (parallel) share one implementation.
    Ledger/cache writes happen on whatever `ledger`/`cache_root` the
    caller passed - for the sequential caller that is the REAL shared
    ledger (safe, single-threaded); for a worker caller it is the
    worker's own private, throwaway ledger (see module docstring).
    Callers are responsible for _last_seen/_mark_bootstrapped/
    record_stage_cost - all parent-only, module-global, or shared-file
    concerns this function must not touch directly.
    """
    if log is None:
        log = lambda kind, msg: None  # noqa: E731

    import verdict as V
    from memory.ledger import Episode
    from scoring import worldmodel as _wm

    history = store.read(asset_key)
    log("bootstrap",
        f"first contact: detect->mask->re-detect over {history.height} "
        f"rows (max {max_iters} passes)")
    passes = []
    for it in range(max_iters):
        log("bootstrap", f"pass {it + 1}: recalibrating on ledger-masked lifetime")
        _wm.on_progress = progress
        try:
            # audit=False: a scan pass's calibration EXPECTEDLY contains
            # the contamination the pass exists to find - a contiguous
            # fault block reads as huge autocorrelation and the
            # exchangeability audit would refuse the instrument that
            # cures the cause. The FINAL calibration below runs fully
            # audited: that is the one that arms the guarantee.
            ok = em.monitor.calibrate_from_lifetime(
                store, ledger=ledger, cache_root=cache_root, audit=False,
            )
        finally:
            _wm.on_progress = None
        if not ok:
            passes.append({"pass": it + 1, "status": "insufficient"})
            log("bootstrap", f"pass {it + 1}: insufficient history - stopping")
            break
        em.open_episode_start = ""
        em._episode_scores = []
        episodes_before = len(ledger.episodes)

        # each pass analyses only the not-yet-explained life: rows
        # already inside ledger windows are excluded, so a pass can
        # only find NEW structure (this is what makes the loop converge
        # instead of re-finding the same fault forever)
        unexplained = ledger.mask(asset_key, history)
        if unexplained.is_empty():
            passes.append({"pass": it + 1, "new_episodes": 0})
            log("bootstrap", f"pass {it + 1}: whole life explained - converged")
            break
        log("bootstrap",
            f"pass {it + 1}: contamination scan + e-process replay of "
            f"{unexplained.height} unexplained rows")

        # DETECT part 1 - contamination scan of the score trace (catches
        # faults sitting inside the calibration reference, which the
        # e-process structurally cannot)
        scores_full = em.monitor.scorer.score(unexplained)
        ts_col = unexplained.get_column(TIMESTAMP_COL).to_list()
        existing = ledger.windows(asset_key)
        for w0, w1 in scan_contamination(ts_col, scores_full):
            overlaps = any(not (w1 < e0 or w0 > e1) for e0, e1 in existing)
            if not overlaps:
                ledger.add(Episode(
                    asset_key=asset_key, start=w0, end=w1, state="alarm",
                    note='{"source": "bootstrap-scan"}',
                ))

        # DETECT part 2 - e-process replay of the unexplained life
        last_verdict = None
        for chunk_start in range(0, unexplained.height, 4000):
            if chunk_start and chunk_start % 20000 == 0:
                log("bootstrap",
                    f"pass {it + 1}: replayed {chunk_start}/{unexplained.height} rows")
            chunk = unexplained.slice(chunk_start, 4000)
            v = em.process(chunk)
            if v.state in (V.STATE_ALARM, V.STATE_ESCALATING, V.STATE_CHANGE):
                last_verdict = v
            elif em.open_episode_start and last_verdict is not None:
                # evidence latched but state recovered -> close episode
                em.reanchor(store=store, last_verdict=last_verdict, cache_root=cache_root)
                last_verdict = None
        if em.open_episode_start and last_verdict is not None:
            em.reanchor(store=store, last_verdict=last_verdict, cache_root=cache_root)
        found = len(ledger.episodes) - episodes_before
        passes.append({"pass": it + 1, "new_episodes": found})
        log("bootstrap",
            f"pass {it + 1} done: {found} new episode(s) ledgered"
            + ("" if found else " - converged"))
        if found == 0:
            break

    # leave the monitor calibrated on the final masked baseline; a
    # failure here means a DEAD monitor, so it is reported, not dropped
    final_ok = em.monitor.calibrate_from_lifetime(store, ledger=ledger, cache_root=cache_root)
    dropped: list[dict] = []
    if not final_ok:
        # SELF-REFUTING MASK guard (#92): a ledger mask that leaves the
        # calibration with nothing cannot be right - a baseline must
        # exist for "unhealthy" to mean anything. Drop the WIDEST
        # bootstrap-created fault window and recalibrate, repeating
        # until calibration succeeds or none remain.
        from datetime import datetime as _dt

        from memory.ledger import FAULT_STATES

        def _span(e) -> float:
            try:
                s = _dt.fromisoformat(e.start)
                t1 = _dt.fromisoformat(e.end or "9999-12-31T00:00:00+00:00")
                return (t1 - s).total_seconds()
            except ValueError:
                return 0.0

        while not final_ok:
            candidates = [
                e for e in ledger.episodes
                if e.asset_key == asset_key and e.state in FAULT_STATES
            ]
            if not candidates:
                break  # genuinely thin data: insufficient is honest
            widest = max(candidates, key=_span)
            ledger.remove(widest)
            dropped.append({"start": widest.start, "end": widest.end})
            final_ok = em.monitor.calibrate_from_lifetime(
                store, ledger=ledger, cache_root=cache_root
            )

    last_seen = history.get_column(TIMESTAMP_COL).max() if not history.is_empty() else None
    if final_ok:
        fp = monitor_fingerprint(store, ledger, asset_key, em.monitor.scorer_cls)
        save_monitor_cache(em.monitor, cache_root, asset_key, fp)
    log("bootstrap",
        f"first contact complete: {len(passes)} pass(es), "
        f"{sum(p.get('new_episodes', 0) for p in passes)} episode(s), "
        f"final calibration {'ok' if final_ok else 'FAILED'}")
    return {
        "asset": asset_key,
        "passes": passes,
        "final_calibration": bool(final_ok),
        "dropped_self_refuting_windows": dropped,
        "history_rows": history.height,
        "last_seen": last_seen,
    }


# -------------------------------------------------------- worker entry
# These are the two callables submitted to the ProcessPoolExecutor.
# Plain module-level functions with only picklable args/return values
# (strings, Paths-as-strings, lists of dicts) - required for spawn, and
# the same "nothing unpicklable crosses process boundaries" discipline
# the lab's own ProcessPool workers used.
def onboard_worker(asset_key: str, store_root: str, cache_root: str, scorer_cls) -> dict:
    from memory.ledger import EpisodeLedger
    from store.raw import RawStore

    started = time.monotonic()
    log_lines: list[tuple] = []

    def log(kind: str, msg: str) -> None:
        log_lines.append((datetime.now(timezone.utc).isoformat(timespec="seconds"), kind, msg))

    def progress(done: int, total: int) -> None:
        log("train", f"world model: epoch {done}/{total} (all channels batched)")

    store = RawStore(store_root)
    # onboard never writes to the ledger (calibrate_from_lifetime only
    # reads windows()/mask()) - many concurrent readers of the real
    # shared file is safe, no private copy needed
    ledger = EpisodeLedger(Path(cache_root).parent / "ledger.json")
    monitor, ok = run_onboard(
        asset_key, store, ledger, Path(cache_root), scorer_cls,
        progress=progress, log=log,
    )
    if ok:
        fp = monitor_fingerprint(store, ledger, asset_key, scorer_cls)
        save_monitor_cache(monitor, cache_root, asset_key, fp)
    dt = time.monotonic() - started
    log("onboard", f"{'calibrated' if ok else 'insufficient history'} in {dt:.0f}s")
    return {"asset_key": asset_key, "ok": ok, "dt": dt, "log_lines": log_lines}


def bootstrap_worker(
    asset_key: str, store_root: str, cache_root: str, scorer_cls,
    episodes_snapshot: list[dict], max_iters: int = 4,
) -> dict:
    from episodes import EpisodicMonitor
    from memory.ledger import Episode, EpisodeLedger
    from monitor import AssetMonitor
    from store.raw import RawStore

    started = time.monotonic()
    log_lines: list[tuple] = []

    def log(kind: str, msg: str) -> None:
        log_lines.append((datetime.now(timezone.utc).isoformat(timespec="seconds"), kind, msg))

    def progress(done: int, total: int) -> None:
        log("train", f"world model: epoch {done}/{total} (all channels batched)")

    store = RawStore(store_root)
    initial = [Episode(**e) for e in episodes_snapshot]
    with TemporaryDirectory() as td:
        priv_path = Path(td) / "episodes.json"
        priv_path.write_text(json.dumps([asdict(e) for e in initial]), encoding="utf-8")
        ledger = EpisodeLedger(priv_path)
        em = EpisodicMonitor(AssetMonitor(asset_key, scorer_cls=scorer_cls), ledger)
        result = run_bootstrap(
            asset_key, store, ledger, em, Path(cache_root), max_iters,
            log=log, progress=progress,
        )
        added = [asdict(e) for e in set(ledger.episodes) - set(initial)]
        removed = [asdict(e) for e in set(initial) - set(ledger.episodes)]
    dt = time.monotonic() - started
    result["asset_key"] = asset_key
    result["added_episodes"] = added
    result["removed_episodes"] = removed
    result["log_lines"] = log_lines
    result["dt"] = dt
    return result
