"""ACM2 service (S6): verdict-first fleet UI + JSON API.

Zero-build vanilla UI by decision (Section 7 of the implementation plan):
one HTML page, no bundler, no framework - a genuine virtue for air-gapped
industrial deployment. The fleet view is the ONLY view; one asset renders
as a fleet of one. Every verdict field of the frozen contract is shown on
drill-down; nothing is a bare number.

Run: uv run python -m acm2.service [--root <data_root>] [--port 8899]
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from acm2.fleet import FleetRuntime

DEFAULT_TICK_SECONDS = 300.0

PAGE = """<!DOCTYPE html>
<html><head><meta charset="ascii"><title>ACM2 Fleet</title>
<style>
 body{font-family:Consolas,monospace;background:#101418;color:#d8dee6;margin:24px}
 h1{font-size:18px} .pill{display:inline-block;padding:2px 10px;margin:0 6px 0 0;
 border-radius:10px;font-size:12px;background:#22303c}
 .escalating,.alarm{background:#7c2d2d}.change-not-fault{background:#7c5c2d}
 .watch{background:#6b6b2d}.healthy{background:#2d5c3c}.insufficient-history{background:#3c4450}
 table{border-collapse:collapse;width:100%;margin-top:14px;font-size:13px}
 td,th{padding:6px 10px;border-bottom:1px solid #22303c;text-align:left}
 tr:hover{background:#182028;cursor:pointer}
 #detail{white-space:pre-wrap;background:#0b0e12;padding:12px;margin-top:14px;
 border:1px solid #22303c;font-size:12px;display:none}
 .muted{color:#7c8894;font-size:12px}
</style></head><body>
<h1>ACM2 Fleet <span class="muted" id="meta"></span></h1>
<div id="pills"></div>
<table><thead><tr><th>asset</th><th>state</th><th>evidence</th>
<th>confidence</th><th>attribution</th><th>model epoch</th></tr></thead>
<tbody id="rows"></tbody></table>
<div id="detail"></div>
<script>
async function refresh(){
 const r = await fetch('/api/fleet'); const f = await r.json();
 document.getElementById('meta').textContent =
   f.assets + ' assets | tier ' + f.tier;
 document.getElementById('pills').innerHTML = Object.entries(f.counts)
  .map(([s,n]) => '<span class="pill '+s+'">'+s+': '+n+'</span>').join('');
 document.getElementById('rows').innerHTML = f.rows.map(v =>
  '<tr onclick="detail(\\''+encodeURIComponent(v.asset_key)+'\\')">'+
  '<td>'+v.asset_key+'</td><td><span class="pill '+v.state+'">'+v.state+
  '</span></td><td>'+v.evidence+'</td><td>'+v.confidence+'</td><td>'+
  (v.attribution||[]).slice(0,3).join(', ')+'</td><td>'+v.model_epoch+
  '</td></tr>').join('');
}
async function detail(key){
 const r = await fetch('/api/asset/'+key); const d = await r.json();
 const el = document.getElementById('detail');
 el.style.display = 'block';
 el.textContent = JSON.stringify(d, null, 1);
}
refresh(); setInterval(refresh, 5000);
</script></body></html>"""


def create_app(
    runtime: FleetRuntime, tick_seconds: float | None = None
) -> FastAPI:
    """tick_seconds=None disables the built-in loop (tests drive ticks
    explicitly); any positive value makes the service self-ticking -
    implement and forget."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = None
        if tick_seconds:
            async def loop() -> None:
                while True:
                    await asyncio.to_thread(runtime.tick_all)
                    await asyncio.sleep(tick_seconds)

            task = asyncio.create_task(loop())
        yield
        if task is not None:
            task.cancel()

    app = FastAPI(title="ACM2", version="2.0.0a0", lifespan=lifespan)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return PAGE

    @app.get("/api/fleet")
    def fleet() -> JSONResponse:
        return JSONResponse(runtime.fleet_summary())

    @app.get("/api/asset/{asset_key:path}")
    def asset(asset_key: str) -> JSONResponse:
        v = runtime.verdicts.get(asset_key)
        if v is None:
            return JSONResponse({"error": "unknown asset"}, status_code=404)
        return JSONResponse(v.to_dict())

    @app.post("/api/tick")
    def tick() -> JSONResponse:
        return JSONResponse({"assets_moved": runtime.tick_all()})

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
    args = parser.parse_args()
    root = Path(args.root).resolve()
    runtime = FleetRuntime(store=RawStore(root / "raw"), data_root=root)
    runtime.onboard_all()
    runtime.tick_all()
    app = create_app(runtime, tick_seconds=args.tick_seconds)
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":  # pragma: no cover
    main()
