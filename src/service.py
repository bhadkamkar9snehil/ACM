"""ACM service: verdict-first assets UI + JSON API.

Zero-build vanilla UI by decision (Section 7 of the implementation plan):
one HTML page, no bundler, no framework - a genuine virtue for air-gapped
industrial deployment. The assets view is the ONLY view; one asset is
simply a list of one. Every verdict field of the frozen contract is shown on
drill-down; nothing is a bare number.

Run: uv run python -m service [--root <data_root>] [--port 8899]
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
)

from runtime import Runtime

DEFAULT_TICK_SECONDS = 300.0
UI_PATH = Path(__file__).with_name("ui.html")
VENDOR_DIR = Path(__file__).with_name("vendor")


class _WsHub:
    """Fan-out of fleet snapshots to connected UI clients. Push happens
    after every tick (loop or API-triggered) so the UI is real-time
    without polling; a dead socket is dropped silently (the client
    reconnects with backoff and falls back to polling)."""

    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()

    async def broadcast(self, payload: dict) -> None:
        dead = []
        for ws in self.clients:
            try:
                await ws.send_json(payload)
            except Exception:  # noqa: BLE001 - any send failure = gone
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)




def create_app(
    runtime: Runtime, tick_seconds: float | None = None,
    deferred_setup=None,
) -> FastAPI:
    """tick_seconds=None disables the built-in loop (tests drive ticks
    explicitly); any positive value makes the service self-ticking -
    implement and forget.

    deferred_setup: optional callable run in the loop BEFORE bootstrap -
    onboarding deep histories takes minutes and must never keep the
    port unbound (the browser sees connection-refused, which looks like
    a dead service, not a busy one)."""

    hub = _WsHub()

    async def push_fleet() -> None:
        if hub.clients:
            await hub.broadcast({"type": "fleet", "data": runtime.summary()})

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = None
        if tick_seconds:
            async def loop() -> None:
                # first-contact cleaning runs IN the loop, not before the
                # server binds: a multi-pass bootstrap over deep histories
                # must never block the UI from coming up (found by review -
                # the page was black for minutes on a fresh data root)
                #
                # every step is guarded: an unhandled exception in an
                # unsupervised create_task dies SILENTLY while the API
                # keeps serving - monitoring stops and nothing says so
                # (found by the #90 soak: one bad tick killed the loop
                # for the whole run). Log, wait, try again - a repeating
                # failure is visible in the log and in staleness, a dead
                # loop is visible nowhere.
                import traceback

                # background work runs in worker threads; progress pushes
                # hop back to the event loop so the UI always shows WHICH
                # asset is being worked on instead of an empty fleet
                ev_loop = asyncio.get_running_loop()

                def _progress() -> None:
                    asyncio.run_coroutine_threadsafe(push_fleet(), ev_loop)

                # live activity stream: every runtime.log() event lands in
                # connected UIs immediately, whatever thread produced it
                def _push_activity(event: dict) -> None:
                    if hub.clients:
                        asyncio.run_coroutine_threadsafe(
                            hub.broadcast(
                                {"type": "activity", "data": event}
                            ),
                            ev_loop,
                        )

                runtime.on_activity = _push_activity

                if deferred_setup is not None:
                    try:
                        await asyncio.to_thread(deferred_setup, _progress)
                        await push_fleet()
                    except Exception:  # noqa: BLE001
                        print(
                            "[acm] deferred setup failed:\n"
                            + traceback.format_exc()
                        )
                try:
                    await asyncio.to_thread(
                        runtime.bootstrap_virgin, on_progress=_progress
                    )
                except Exception:  # noqa: BLE001
                    print("[acm] bootstrap failed:\n" + traceback.format_exc())
                await push_fleet()
                while True:
                    try:
                        await asyncio.to_thread(runtime.tick_all)
                        await push_fleet()  # real-time UI: push, not poll
                    except Exception:  # noqa: BLE001
                        print("[acm] tick failed:\n" + traceback.format_exc())
                    await asyncio.sleep(tick_seconds)

            task = asyncio.create_task(loop())
        yield
        if task is not None:
            task.cancel()

    app = FastAPI(title="ACM", version="2.0.0a0", lifespan=lifespan)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return UI_PATH.read_text(encoding="utf-8")

    @app.get("/api/assets")
    def assets_view() -> JSONResponse:
        return JSONResponse(runtime.summary())

    @app.get("/api/activity")
    def activity_view() -> JSONResponse:
        """Rolling activity stream (last 500 events) - everything the
        service is doing or has done, newest last. The WS pushes the
        same events live; this endpoint backfills on page load."""
        return JSONResponse({"events": list(runtime.activity)})

    @app.get("/api/asset/{asset_key:path}")
    def asset(asset_key: str) -> JSONResponse:
        v = runtime.verdicts.get(asset_key)
        if v is None:
            return JSONResponse({"error": "unknown asset"}, status_code=404)
        return JSONResponse(v.to_dict())

    @app.get("/api/narrative/{asset_key:path}")
    def narrative(asset_key: str) -> JSONResponse:
        sections = runtime.narrative_sections(asset_key)
        if sections is None:
            return JSONResponse({"error": "unknown asset"}, status_code=404)
        text = "\n".join(s["text"] for s in sections)
        return JSONResponse(
            {"asset_key": asset_key, "sections": sections, "narrative": text}
        )

    @app.post("/api/tick")
    async def tick() -> JSONResponse:
        moved = await asyncio.to_thread(runtime.tick_all)
        await push_fleet()
        return JSONResponse({"assets_moved": moved})

    @app.post("/api/tick/{asset_key:path}")
    async def tick_one(asset_key: str) -> JSONResponse:
        if asset_key not in runtime.monitors:
            return JSONResponse({"error": "unknown asset"}, status_code=404)
        v = await asyncio.to_thread(runtime.tick, asset_key)
        await push_fleet()
        return JSONResponse({"moved": v is not None,
                             "state": v.state if v else None})

    @app.post("/api/reanchor/{asset_key:path}")
    async def reanchor(asset_key: str) -> JSONResponse:
        if asset_key not in runtime.monitors:
            return JSONResponse({"error": "unknown asset"}, status_code=404)
        ok = await asyncio.to_thread(runtime.reanchor, asset_key)
        await push_fleet()
        return JSONResponse({"ok": ok})

    @app.post("/api/bootstrap/{asset_key:path}")
    async def bootstrap(asset_key: str) -> JSONResponse:
        if asset_key not in runtime.monitors:
            return JSONResponse({"error": "unknown asset"}, status_code=404)
        out = await asyncio.to_thread(runtime.bootstrap, asset_key)
        await push_fleet()
        return JSONResponse(out)

    @app.get("/api/episodes/{asset_key:path}")
    def episodes(asset_key: str) -> JSONResponse:
        """The asset's case history: every ledgered episode - faults AND
        absorbed changes (#89 absorptions must be visible, not silent) -
        plus the currently open episode, if any."""
        import json as _json

        em = runtime.monitors.get(asset_key)
        if em is None:
            return JSONResponse({"error": "unknown asset"}, status_code=404)
        eps = []
        for e in runtime.ledger.episodes:
            if e.asset_key != asset_key:
                continue
            note = {}
            if e.note:
                try:
                    note = _json.loads(e.note)
                except _json.JSONDecodeError:
                    pass
            eps.append(
                {
                    "start": e.start,
                    "end": e.end,
                    "state": e.state,
                    "channels": note.get("channels"),
                    "shape": note.get("shape"),
                    "peak_evidence": note.get("peak_evidence"),
                    "source": note.get("source"),
                }
            )
        return JSONResponse(
            {"episodes": eps, "open_since": em.open_episode_start}
        )

    @app.get("/vendor/{name}")
    def vendor(name: str):
        """Vendored assets (Apache ECharts) - served locally, never a
        CDN: the zero-build UI must work air-gapped."""
        path = VENDOR_DIR / name
        if not path.is_file() or path.suffix != ".js":
            return JSONResponse({"error": "not found"}, status_code=404)
        return FileResponse(path, media_type="application/javascript")

    @app.websocket("/api/ws")
    async def ws(websocket: WebSocket) -> None:
        """Real-time fleet stream: a snapshot on connect, then a push
        after every tick or action."""
        await websocket.accept()
        hub.clients.add(websocket)
        try:
            await websocket.send_json(
                {"type": "fleet", "data": runtime.summary()}
            )
            while True:
                await websocket.receive_text()  # keepalive pings
        except WebSocketDisconnect:
            pass
        finally:
            hub.clients.discard(websocket)

    @app.get("/api/report")
    def report() -> PlainTextResponse:
        """Fleet report (markdown), worst-first - the S6 report flow;
        render_report existed since S1 but was never exposed."""
        from monitor import render_report

        rows = runtime.summary()["rows"]
        ordered = [
            runtime.verdicts[r["asset_key"]]
            for r in rows
            if r["asset_key"] in runtime.verdicts
        ]
        return PlainTextResponse(
            render_report(ordered), media_type="text/markdown; charset=utf-8"
        )

    @app.get("/api/health/{asset_key:path}")
    def health(asset_key: str) -> JSONResponse:
        if asset_key not in runtime.monitors:
            return JSONResponse({"error": "unknown asset"}, status_code=404)
        return JSONResponse({"series": runtime.health_series(asset_key)})

    @app.get("/api/domains/{asset_key:path}")
    def domains(asset_key: str) -> JSONResponse:
        if asset_key not in runtime.monitors:
            return JSONResponse({"error": "unknown asset"}, status_code=404)
        return JSONResponse(runtime.domains(asset_key))

    @app.get("/api/cost")
    def cost() -> JSONResponse:
        """Fleet-wide last-tick wall-clock cost, worst-first (#113)."""
        return JSONResponse(runtime.cost_summary())

    @app.get("/api/immune/{asset_key:path}")
    def immune(asset_key: str) -> JSONResponse:
        r = runtime.immune_results.get(asset_key)
        if r is None:
            return JSONResponse(
                {"status": "not yet checked"}, status_code=404
            )
        return JSONResponse(r)

    @app.post("/api/immune-pass/{asset_key:path}")
    def immune_now(asset_key: str) -> JSONResponse:
        if asset_key not in runtime.monitors:
            return JSONResponse({"error": "unknown asset"}, status_code=404)
        return JSONResponse(runtime.immune_pass(asset_key))

    return app


def attach_live_sources(runtime: Runtime, specs: list[str]) -> None:
    """Wire `--live ASSET_KEY=BUFFER_DB` specs into the runtime (#90: the
    live path was Python-only and unreachable from the CLI). An unknown
    asset key fails loudly at startup - a silently unattached buffer
    would look exactly like a healthy quiet asset."""
    for spec in specs:
        key, sep, db = spec.partition("=")
        if not sep or not key or not db:
            raise SystemExit(f"--live expects ASSET_KEY=BUFFER_DB, got: {spec}")
        if key not in runtime.monitors:
            raise SystemExit(
                f"--live: unknown asset key {key!r} (onboarded: "
                f"{sorted(runtime.monitors)})"
            )
        runtime.attach_live_source(key, Path(db).resolve())


def main() -> None:  # pragma: no cover - manual entrypoint
    import argparse

    import uvicorn

    from hardware import set_thread_caps
    from store.raw import RawStore

    set_thread_caps(1)
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="acm_data")
    parser.add_argument("--port", type=int, default=8899)
    parser.add_argument(
        "--tick-seconds", type=float, default=DEFAULT_TICK_SECONDS
    )
    parser.add_argument(
        "--live",
        action="append",
        default=[],
        metavar="ASSET_KEY=BUFFER_DB",
        help="attach a live SQLite buffer to an asset (repeatable); "
        "drained into the store on every tick",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()
    runtime = Runtime(store=RawStore(root / "raw"), data_root=root)

    def deferred_setup(on_progress=None) -> None:
        # onboarding calibrates every asset from its lifetime history -
        # minutes on deep histories - so it runs in the tick loop, after
        # the port binds. The UI comes up instantly and watches assets
        # appear instead of staring at connection-refused.
        runtime.onboard_all(on_progress=on_progress)
        attach_live_sources(runtime, args.live)

    if args.tick_seconds:
        app = create_app(
            runtime,
            tick_seconds=args.tick_seconds,
            deferred_setup=deferred_setup,
        )
    else:  # no loop to defer into - set up synchronously
        deferred_setup()
        app = create_app(runtime, tick_seconds=args.tick_seconds)
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":  # pragma: no cover
    main()
