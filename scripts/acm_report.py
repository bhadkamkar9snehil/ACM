#!/usr/bin/env python3
"""
ACM visual report — one module, any selection of assets, full timeline.

Reads the canonical SQL results store (scripts/acm_store.py; SQLite file or
SQL Server) and renders a self-contained HTML report: per asset the fused
anomaly timeline start-to-end with the self-tuned threshold and alarm
shading, a per-detector z heat strip, and the verdict; a fleet summary table
on top. No server required — open the file in a browser.

Usage:
  # everything in the store
  python scripts/acm_report.py --db acm_results.db --out report.html

  # one farm
  python scripts/acm_report.py --db acm_results.db --farm A --out a.html

  # specific assets (asset_key, bare event id, or substring match)
  python scripts/acm_report.py --db acm_results.db --assets A/40 B/34 --out picks.html
  python scripts/acm_report.py --db acm_results.db --assets 40 71 --farm A --out t10.html

  # list what's available
  python scripts/acm_report.py --db acm_results.db --list

  # SQL Server backend
  python scripts/acm_report.py --backend mssql --conn "DRIVER={...};SERVER=...;DATABASE=ACM" --out report.html
"""
from __future__ import annotations

import argparse
import base64
import io
import sqlite3
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

Z_COLS = ["ar1_z", "pca_spe_z", "pca_t2_z", "iforest_z", "gmm_z", "omr_z"]
VERDICT_COLOR = {"DETECTED": "#1a7f37", "CLEAN": "#1a7f37",
                 "MISSED": "#cf222e", "FALSE_ALARM": "#bf8700"}


def connect(backend: str, db: str, conn_str: Optional[str]):
    if backend == "sqlite":
        return sqlite3.connect(db), ""
    import pyodbc
    return pyodbc.connect(conn_str), "dbo.acm_"


def read_sql(con, sql: str, params: tuple = ()) -> pd.DataFrame:
    return pd.read_sql(sql, con, params=params)


def select_assets(assets: pd.DataFrame, picks: Optional[list[str]], farm: Optional[str]) -> pd.DataFrame:
    if farm:
        assets = assets[assets["farm"] == farm]
    if not picks:
        return assets
    keep = pd.Series(False, index=assets.index)
    for p in picks:
        keep |= (assets["asset_key"] == p)
        if p.isdigit():
            # bare number: exact event id (key suffix) or exact asset id
            keep |= assets["asset_key"].str.endswith(f"/{p}")
            keep |= (assets["asset_id"] == int(p))
        else:
            keep |= assets["asset_key"].str.contains(p, regex=False)
    return assets[keep]


def fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=85, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def asset_figure(s: pd.DataFrame, meta: pd.Series) -> str:
    ts = pd.to_datetime(s["ts"])
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(11, 3.6), sharex=True,
        gridspec_kw={"height_ratios": [3, 1.2], "hspace": 0.08})

    ax1.plot(ts, s["fused"], lw=0.6, color="#0969da")
    thr = meta.get("alert_z")
    if pd.notna(thr):
        ax1.axhline(thr, color="#bf8700", lw=0.8, ls="--", label=f"self-tuned z={thr:.2f}")
    alarm = s["alarm"].to_numpy().astype(bool)
    if alarm.any():
        ax1.fill_between(ts, 0, 1, where=alarm, transform=ax1.get_xaxis_transform(),
                         color="#cf222e", alpha=0.18, label="alarm")
    ax1.set_ylabel("fused z")
    ax1.legend(loc="upper left", fontsize=7, ncol=3, frameon=False)
    ax1.set_title(f"{meta['asset_key']}  asset={meta['asset_id']}  "
                  f"{meta.get('description') or meta.get('label') or ''}",
                  fontsize=9, loc="left")

    zmat = np.vstack([np.nan_to_num(pd.to_numeric(s[z], errors="coerce").to_numpy(), nan=0.0)
                      for z in Z_COLS])
    ax2.imshow(np.clip(zmat, 0, 8), aspect="auto", cmap="inferno", vmin=0, vmax=8,
               extent=[mdates.date2num(ts.iloc[0]), mdates.date2num(ts.iloc[-1]), len(Z_COLS), 0])
    ax2.set_yticks(np.arange(len(Z_COLS)) + 0.5)
    ax2.set_yticklabels([z.replace("_z", "") for z in Z_COLS], fontsize=6)
    ax2.xaxis_date()
    fig.autofmt_xdate()
    return fig_to_b64(fig)


def build_report(con, prefix: str, out: Path, farm: Optional[str], picks: Optional[list[str]]) -> None:
    assets = read_sql(con, f"SELECT * FROM {prefix}assets ORDER BY farm, label DESC, asset_id")
    assets = select_assets(assets, picks, farm)
    if assets.empty:
        print("No matching assets in store.")
        return

    rows_html, figs_html = [], []
    for _, meta in assets.iterrows():
        s = read_sql(con, f"SELECT * FROM {prefix}scores WHERE asset_key = ? ORDER BY ts",
                     (meta["asset_key"],))
        if s.empty:
            continue
        color = VERDICT_COLOR.get(meta["verdict"], "#57606a")
        lead = f"{meta['lead_h']:+.1f} h" if pd.notna(meta["lead_h"]) else "—"
        rows_html.append(
            f"<tr><td><a href='#{meta.asset_key}'>{meta.asset_key}</a></td>"
            f"<td>{meta.asset_id}</td><td>{meta.label or ''}</td>"
            f"<td>{(meta.description or '')[:48]}</td>"
            f"<td style='color:{color};font-weight:600'>{meta.verdict}</td>"
            f"<td>{lead}</td><td>{meta.rules_fired or ''}</td></tr>")
        figs_html.append(
            f"<div class='card' id='{meta.asset_key}'>"
            f"<img src='data:image/png;base64,{asset_figure(s, meta)}'/></div>")

    summaries = read_sql(con, f"SELECT * FROM {prefix}summary ORDER BY ingested_at DESC")
    if farm:
        summaries = summaries[summaries["farm"] == farm]
    kpi = summaries.iloc[0]["metrics_json"] if not summaries.empty else "{}"

    scope = f"farm {farm}" if farm else (f"{len(assets)} selected assets" if picks else "fleet")
    html = f"""<!doctype html><html><head><meta charset='utf-8'>
<title>ACM results — {scope}</title><style>
body{{font:13px/1.45 system-ui,sans-serif;margin:24px;color:#1f2328}}
table{{border-collapse:collapse;margin:12px 0}}
td,th{{border:1px solid #d0d7de;padding:4px 9px;font-size:12px}}
th{{background:#f6f8fa;text-align:left}}
.card{{margin:14px 0;border:1px solid #d0d7de;border-radius:6px;padding:6px}}
img{{width:100%}} pre{{background:#f6f8fa;padding:10px;border-radius:6px;font-size:11px}}
</style></head><body>
<h2>ACM — asset condition results ({scope})</h2>
<p>Unsupervised, cold-start, self-tuned. Generated from the canonical SQL results store.</p>
<h3>Latest run summary</h3><pre>{kpi}</pre>
<h3>Assets</h3>
<table><tr><th>asset</th><th>id</th><th>label</th><th>event</th><th>verdict</th>
<th>lead</th><th>rules fired</th></tr>{''.join(rows_html)}</table>
<h3>Timelines (start to end)</h3>
{''.join(figs_html)}
</body></html>"""
    out.write_text(html)
    print(f"Report written: {out} ({len(figs_html)} assets, {out.stat().st_size/1e6:.1f} MB)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", choices=["sqlite", "mssql"], default="sqlite")
    ap.add_argument("--db", default="acm_results.db")
    ap.add_argument("--conn", default=None, help="pyodbc connection string (mssql)")
    ap.add_argument("--out", default="acm_report.html")
    ap.add_argument("--farm", default=None)
    ap.add_argument("--assets", nargs="*", default=None,
                    help="asset_key, bare event id, or substring; default: all")
    ap.add_argument("--list", action="store_true", help="list available assets and exit")
    args = ap.parse_args()

    con, prefix = connect(args.backend, args.db, args.conn)
    try:
        if args.list:
            a = read_sql(con, f"SELECT asset_key, asset_id, farm, label, verdict FROM {prefix}assets ORDER BY farm, asset_id")
            print(a.to_string(index=False))
            return 0
        build_report(con, prefix, Path(args.out), args.farm, args.assets)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
