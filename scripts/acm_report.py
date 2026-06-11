#!/usr/bin/env python3
"""
ACM visual report — one self-contained HTML file per farm/fleet.

Reads the canonical SQLite results store (scripts/acm_store.py) and renders,
per asset: the fused anomaly timeline with alarm shading and (when known) the
labelled event window, per-detector z heat strip, and the verdict. A fleet
summary table sits on top. No server, no Grafana, no SQL Server — open the
file in a browser.

Usage:
  python scripts/acm_report.py --db acm_results.db --out acm_report.html [--farm A]
"""
from __future__ import annotations

import argparse
import base64
import io
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

Z_COLS = ["ar1_z", "pca_spe_z", "pca_t2_z", "iforest_z", "gmm_z", "omr_z"]

VERDICT_COLOR = {"DETECTED": "#1a7f37", "CLEAN": "#1a7f37",
                 "MISSED": "#cf222e", "FALSE_ALARM": "#bf8700"}


def fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=85, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def asset_figure(s: pd.DataFrame, meta: pd.Series, event_window) -> str:
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
    if event_window is not None:
        ax1.axvspan(event_window[0], event_window[1], color="#8250df", alpha=0.12,
                    label="labelled event")
    ax1.set_ylabel("fused z")
    ax1.legend(loc="upper left", fontsize=7, ncol=3, frameon=False)
    ax1.set_title(f"{meta['asset_key']}  asset={meta['asset_id']}  "
                  f"{meta.get('description') or meta.get('label') or ''}", fontsize=9, loc="left")

    # per-detector heat strip
    zmat = np.vstack([np.nan_to_num(s[z].to_numpy(), nan=0.0) for z in Z_COLS])
    ax2.imshow(np.clip(zmat, 0, 8), aspect="auto", cmap="inferno", vmin=0, vmax=8,
               extent=[mdates.date2num(ts.iloc[0]), mdates.date2num(ts.iloc[-1]), len(Z_COLS), 0])
    ax2.set_yticks(np.arange(len(Z_COLS)) + 0.5)
    ax2.set_yticklabels([z.replace("_z", "") for z in Z_COLS], fontsize=6)
    ax2.xaxis_date()
    fig.autofmt_xdate()
    return fig_to_b64(fig)


def build_report(db: Path, out: Path, farm: str | None) -> None:
    con = sqlite3.connect(db)
    where = f"WHERE farm = '{farm}'" if farm else ""
    assets = pd.read_sql(f"SELECT * FROM assets {where} ORDER BY farm, label DESC, asset_id", con)
    if assets.empty:
        print("No assets in store" + (f" for farm {farm}" if farm else ""))
        return

    # Optional labelled event windows (benchmark mode): pull from summary json?
    # Stored per-asset lead/rules suffice; event window comes from event_info if
    # present next to the store - kept simple: shade only alarms.

    rows_html, figs_html = [], []
    for _, meta in assets.iterrows():
        s = pd.read_sql("SELECT * FROM scores WHERE asset_key = ? ORDER BY ts", con,
                        params=(meta["asset_key"],))
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
        img = asset_figure(s, meta, None)
        figs_html.append(
            f"<div class='card' id='{meta.asset_key}'>"
            f"<img src='data:image/png;base64,{img}'/></div>")

    summaries = pd.read_sql(f"SELECT * FROM summary {where} ORDER BY ingested_at DESC", con)
    kpi = summaries.iloc[0]["metrics_json"] if not summaries.empty else "{}"
    con.close()

    html = f"""<!doctype html><html><head><meta charset='utf-8'>
<title>ACM results {farm or 'fleet'}</title><style>
body{{font:13px/1.45 system-ui,sans-serif;margin:24px;color:#1f2328}}
table{{border-collapse:collapse;margin:12px 0}}
td,th{{border:1px solid #d0d7de;padding:4px 9px;font-size:12px}}
th{{background:#f6f8fa;text-align:left}}
.card{{margin:14px 0;border:1px solid #d0d7de;border-radius:6px;padding:6px}}
img{{width:100%}} pre{{background:#f6f8fa;padding:10px;border-radius:6px;font-size:11px}}
</style></head><body>
<h2>ACM — asset condition results {('— Wind Farm ' + farm) if farm else ''}</h2>
<p>Unsupervised, cold-start, self-tuned. Generated from the canonical results store.</p>
<h3>Benchmark summary</h3><pre>{kpi}</pre>
<h3>Fleet</h3>
<table><tr><th>asset</th><th>id</th><th>label</th><th>event</th><th>verdict</th>
<th>lead</th><th>rules fired</th></tr>{''.join(rows_html)}</table>
<h3>Per-asset timelines</h3>
{''.join(figs_html)}
</body></html>"""
    out.write_text(html)
    print(f"Report written: {out} ({len(figs_html)} assets, {out.stat().st_size/1e6:.1f} MB)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="acm_results.db")
    ap.add_argument("--out", default="acm_report.html")
    ap.add_argument("--farm", default=None)
    args = ap.parse_args()
    build_report(Path(args.db), Path(args.out), args.farm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
