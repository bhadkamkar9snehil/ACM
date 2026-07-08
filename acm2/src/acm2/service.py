"""ACM2 service: verdict-first assets UI + JSON API.

Zero-build vanilla UI by decision (Section 7 of the implementation plan):
one HTML page, no bundler, no framework - a genuine virtue for air-gapped
industrial deployment. The assets view is the ONLY view; one asset is
simply a list of one. Every verdict field of the frozen contract is shown on
drill-down; nothing is a bare number.

Run: uv run python -m acm2.service [--root <data_root>] [--port 8899]
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from acm2.runtime import Runtime

DEFAULT_TICK_SECONDS = 300.0
UI_PATH = Path(__file__).with_name("ui.html")




def create_app(
    runtime: Runtime, tick_seconds: float | None = None
) -> FastAPI:
    """tick_seconds=None disables the built-in loop (tests drive ticks
    explicitly); any positive value makes the service self-ticking -
    implement and forget."""

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

                try:
                    await asyncio.to_thread(runtime.bootstrap_virgin)
                except Exception:  # noqa: BLE001
                    print("[acm2] bootstrap failed:\n" + traceback.format_exc())
                while True:
                    try:
                        await asyncio.to_thread(runtime.tick_all)
                    except Exception:  # noqa: BLE001
                        print("[acm2] tick failed:\n" + traceback.format_exc())
                    await asyncio.sleep(tick_seconds)

            task = asyncio.create_task(loop())
        yield
        if task is not None:
            task.cancel()

    app = FastAPI(title="ACM2", version="2.0.0a0", lifespan=lifespan)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return UI_PATH.read_text(encoding="utf-8")

    @app.get("/api/assets")
    def assets_view() -> JSONResponse:
        return JSONResponse(runtime.summary())

    @app.get("/api/asset/{asset_key:path}")
    def asset(asset_key: str) -> JSONResponse:
        v = runtime.verdicts.get(asset_key)
        if v is None:
            return JSONResponse({"error": "unknown asset"}, status_code=404)
        return JSONResponse(v.to_dict())

    @app.get("/api/narrative/{asset_key:path}")
    def narrative(asset_key: str) -> JSONResponse:
        text = runtime.narrative(asset_key)
        if text is None:
            return JSONResponse({"error": "unknown asset"}, status_code=404)
        return JSONResponse({"asset_key": asset_key, "narrative": text})

    @app.post("/api/tick")
    def tick() -> JSONResponse:
        return JSONResponse({"assets_moved": runtime.tick_all()})

    @app.post("/api/tick/{asset_key:path}")
    def tick_one(asset_key: str) -> JSONResponse:
        if asset_key not in runtime.monitors:
            return JSONResponse({"error": "unknown asset"}, status_code=404)
        v = runtime.tick(asset_key)
        return JSONResponse({"moved": v is not None,
                             "state": v.state if v else None})

    @app.post("/api/reanchor/{asset_key:path}")
    def reanchor(asset_key: str) -> JSONResponse:
        if asset_key not in runtime.monitors:
            return JSONResponse({"error": "unknown asset"}, status_code=404)
        return JSONResponse({"ok": runtime.reanchor(asset_key)})

    @app.post("/api/bootstrap/{asset_key:path}")
    def bootstrap(asset_key: str) -> JSONResponse:
        if asset_key not in runtime.monitors:
            return JSONResponse({"error": "unknown asset"}, status_code=404)
        return JSONResponse(runtime.bootstrap(asset_key))

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

    from acm2.hardware import set_thread_caps
    from acm2.store.raw import RawStore

    set_thread_caps(1)
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="../acm2_data")
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
    runtime.onboard_all()  # fast; bootstrap + scoring run in the lifespan loop
    attach_live_sources(runtime, args.live)
    app = create_app(runtime, tick_seconds=args.tick_seconds)
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":  # pragma: no cover
    main()
