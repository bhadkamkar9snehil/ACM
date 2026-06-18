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
import html
import io
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

Z_COLS = ["ar1_z", "pca_spe_z", "pca_t2_z", "iforest_z", "gmm_z", "omr_z"]

# Detector display names
DETECTOR_NAMES = {
    "ar1_z": "AR1",
    "pca_spe_z": "PCA-SPE",
    "pca_t2_z": "PCA-T2",
    "iforest_z": "IForest",
    "gmm_z": "GMM",
    "omr_z": "OMR",
}

VERDICT_COLOR = {
    "DETECTED": "#1a7f37",
    "CLEAN": "#1a7f37",
    "MISSED": "#cf222e",
    "FALSE_ALARM": "#bf8700",
}

CSS = """
body {
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 15px;
    line-height: 1.5;
    margin: 32px;
    color: #1f2328;
    background: #ffffff;
}
h2 { margin-top: 0; margin-bottom: 8px; font-size: 28px; font-weight: 600; }
h3 { margin-top: 24px; margin-bottom: 12px; font-size: 18px; font-weight: 600; border-bottom: 2px solid #eaeef2; padding-bottom: 6px; }
h4 { margin-top: 12px; margin-bottom: 6px; font-size: 15px; font-weight: 600; }
p { margin: 8px 0; }
table {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
    font-size: 14px;
}
td, th {
    border: 1px solid #d0d7de;
    padding: 8px 12px;
    text-align: left;
}
th {
    background: #f6f8fa;
    font-weight: 600;
    color: #24292f;
}
tr:nth-child(even) { background: #fafbfc; }
tr:hover { background: #f0f3f6; }
.card {
    margin: 16px 0;
    border: 1px solid #d0d7de;
    border-radius: 8px;
    padding: 12px;
    background: #fafbfc;
}
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin: 16px 0;
}
.kpi-box {
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 16px;
    background: #ffffff;
    text-align: center;
}
.kpi-label { font-size: 13px; color: #57606a; font-weight: 500; }
.kpi-value { font-size: 28px; font-weight: 700; color: #1f2328; margin: 8px 0; }
.kpi-desc { font-size: 12px; color: #6e7781; margin-top: 4px; }
img { width: 100%; max-width: 100%; }
pre {
    background: #f6f8fa;
    padding: 12px;
    border-radius: 6px;
    font-size: 13px;
    overflow-x: auto;
    border: 1px solid #e1e4e8;
    line-height: 1.4;
}
.diagnostic-box {
    background: #f6f8fa;
    border-left: 4px solid #0969da;
    padding: 12px;
    margin: 12px 0;
    border-radius: 4px;
    font-size: 14px;
}
.diagnostic-item {
    margin: 4px 0;
}
.info { color: #0969da; }
.warn { color: #bf8700; }
.error { color: #cf222e; }
.success { color: #1a7f37; }
details {
    margin: 8px 0;
    padding: 8px;
    background: #f6f8fa;
    border: 1px solid #d0d7de;
    border-radius: 4px;
}
summary {
    cursor: pointer;
    font-weight: 600;
    padding: 4px;
    user-select: none;
}
summary:hover { background: #eaeef2; }
.badge {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 24px;
    font-size: 13px;
    font-weight: 600;
}
.badge-detected { background: #d3f9d8; color: #1a7f37; }
.badge-clean { background: #d3f9d8; color: #1a7f37; }
.badge-missed { background: #ffd6d6; color: #cf222e; }
.badge-false-alarm { background: #fff8c5; color: #bf8700; }
.log-summary { font-size: 13px; color: #6e7781; font-weight: 500; }
.timestamp { color: #6e7781; font-size: 12px; font-family: monospace; }
a { color: #0969da; text-decoration: none; }
a:hover { text-decoration: underline; }
@media print {
    body { margin: 0; }
    .no-print { display: none; }
    table { page-break-inside: avoid; }
    .card { page-break-inside: avoid; }
    details { page-break-inside: avoid; }
}
"""


def connect(backend: str, db: str, conn_str: Optional[str]):
    """Connect to database and return connection + table prefix."""
    if backend == "sqlite":
        return sqlite3.connect(db), ""
    import pyodbc
    return pyodbc.connect(conn_str), "dbo.acm_"


def read_sql(con, sql: str, params: tuple = ()) -> pd.DataFrame:
    """Execute SQL and return DataFrame."""
    return pd.read_sql(sql, con, params=params)


def select_assets(assets: pd.DataFrame, picks: Optional[list[str]], farm: Optional[str]) -> pd.DataFrame:
    """Filter assets by farm and/or specific picks."""
    if farm:
        assets = assets[assets["farm"] == farm]
    if not picks:
        return assets
    keep = pd.Series(False, index=assets.index)
    for p in picks:
        keep |= (assets["asset_key"] == p)
        if p.isdigit():
            keep |= assets["asset_key"].str.endswith(f"/{p}")
            keep |= (assets["asset_id"] == int(p))
        else:
            keep |= assets["asset_key"].str.contains(p, regex=False)
    return assets[keep]


def fig_to_b64(fig) -> str:
    """Convert matplotlib figure to base64-encoded PNG."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=85, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def detector_label(col_name: str) -> str:
    """Expand detector column name to display name."""
    return DETECTOR_NAMES.get(col_name, col_name)


def escape_and_format_log(msg: str) -> str:
    """Strip ANSI codes and HTML-escape log message."""
    if pd.isna(msg):
        return ""
    msg = str(msg)
    # Strip ANSI escape sequences
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    msg = ansi_escape.sub('', msg)
    return html.escape(msg)


def format_rules_human(rules_str: Optional[str], alert_z: Optional[float], fused_max: Optional[float]) -> str:
    """
    Convert technical rules_fired string to human-readable explanation.

    Example:
      Input: "sustained+rate(distrusted:heads:omr_z)"
      Output: "Sustained fused deviation detected (5.23 > 4.15). Rate rule triggered.
               OMR detector marked unreliable (baseline too uncertain)."
    """
    if not rules_str or pd.isna(rules_str):
        return "No rules triggered"

    rules_str = str(rules_str).strip()
    if not rules_str:
        return "No rules triggered"

    explanations = []

    # Parse main rules
    has_sustained = "sustained" in rules_str.lower()
    has_rate = "rate" in rules_str.lower()
    has_per_head = "per_head" in rules_str.lower() or "heads:" in rules_str.lower()
    has_availability = "avail" in rules_str.lower()

    if has_sustained:
        if pd.notna(alert_z) and pd.notna(fused_max):
            explanations.append(f"Sustained fused deviation detected (score {fused_max:.2f} exceeded threshold {alert_z:.2f})")
        else:
            explanations.append("Sustained fused deviation detected")

    if has_rate:
        explanations.append("Rate rule triggered (anomaly developing over time)")

    if has_availability:
        explanations.append("Availability rule triggered (downtime or missing data)")

    # Parse distrusted detectors
    distrusted_match = re.search(r'distrusted:heads:([a-z_,]+)', rules_str)
    if distrusted_match:
        detectors_str = distrusted_match.group(1)
        detectors = [d.strip().replace("_z", "") for d in detectors_str.split(",")]
        detector_names = [detector_label(d + "_z").upper() if d else "" for d in detectors]
        detector_names = [d for d in detector_names if d]
        if detector_names:
            detectors_display = ", ".join(detector_names)
            explanations.append(f"Detectors marked unreliable (baseline uncertain): {detectors_display}")

    if has_per_head and not distrusted_match:
        # Individual detector rules without distrust
        explanations.append("Individual detector thresholds exceeded")

    return ". ".join(explanations) + "." if explanations else "No rules triggered"


def parse_metrics_json(metrics_json: str) -> dict:
    """Parse metrics JSON string and extract key metrics."""
    if not metrics_json or pd.isna(metrics_json):
        return {}
    try:
        return json.loads(metrics_json)
    except (json.JSONDecodeError, TypeError):
        return {}


def format_verdict_badge(verdict: Optional[str]) -> str:
    """Return HTML badge for verdict."""
    if pd.isna(verdict):
        verdict = "UNKNOWN"
    verdict_clean = str(verdict).upper().strip()
    badge_class = f"badge-{verdict_clean.lower()}" if verdict_clean in VERDICT_COLOR else "badge"
    return f"<span class='badge {badge_class}'>{html.escape(verdict_clean)}</span>"


def asset_figure(s: pd.DataFrame, meta: pd.Series) -> tuple[str, str]:
    """
    Create matplotlib figure with timeline and heatmap.
    Returns: (base64_image, data_quality_text)
    """
    ts = pd.to_datetime(s["ts"])

    # Compute data quality metrics
    data_rows = len(s)
    data_nans = s[Z_COLS].isna().sum().sum() / (len(s) * len(Z_COLS)) * 100 if len(s) > 0 else 0

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 4.2), sharex=True,
        gridspec_kw={"height_ratios": [3, 1.2], "hspace": 0.12})

    # Plot fused score
    ax1.plot(ts, s["fused"], lw=0.7, color="#0969da", label="Fused score")

    # Plot alert threshold
    thr = meta.get("alert_z")
    if pd.notna(thr):
        ax1.axhline(thr, color="#bf8700", lw=1.0, ls="--",
                    label=f"Alert threshold: {thr:.2f}")

    # Shade alarm regions
    alarm = s["alarm"].to_numpy().astype(bool)
    if alarm.any():
        ax1.fill_between(ts, 0, s["fused"].max() * 1.1, where=alarm,
                         color="#cf222e", alpha=0.12, label="Alarm period")

    ax1.set_ylabel("Anomaly Score (Z)", fontsize=11, fontweight=600)
    ax1.legend(loc="upper left", fontsize=9, ncol=3, frameon=True, fancybox=True)

    # Title with full description
    desc = meta.get("description") or meta.get("label") or ""
    if desc:
        title = f"{meta['asset_key']} (ID: {meta['asset_id']}) — {desc}"
    else:
        title = f"{meta['asset_key']} (ID: {meta['asset_id']})"
    ax1.set_title(title, fontsize=10, loc="left", fontweight=600)
    ax1.grid(True, alpha=0.2)

    # Detector heatmap
    zmat = np.vstack([np.nan_to_num(pd.to_numeric(s[z], errors="coerce").to_numpy(), nan=0.0)
                      for z in Z_COLS])
    im = ax2.imshow(np.clip(zmat, 0, 8), aspect="auto", cmap="inferno", vmin=0, vmax=8,
                    extent=[mdates.date2num(ts.iloc[0]), mdates.date2num(ts.iloc[-1]),
                           len(Z_COLS), 0])

    # Detector labels with full names
    ax2.set_yticks(np.arange(len(Z_COLS)) + 0.5)
    ax2.set_yticklabels([detector_label(z) for z in Z_COLS], fontsize=8)
    ax2.set_ylabel("Detectors", fontsize=10, fontweight=600)
    ax2.xaxis_date()
    ax2.set_xlabel("Time", fontsize=10, fontweight=600)

    # Add colorbar
    cbar = fig.colorbar(im, ax=ax2, orientation="vertical", pad=0.02, fraction=0.05)
    cbar.set_label("Score", fontsize=9)

    fig.autofmt_xdate(rotation=45, ha='right')
    fig.tight_layout()

    b64 = fig_to_b64(fig)

    data_quality = f"Data: {data_rows} rows, {len(Z_COLS)} detectors, {data_nans:.1f}% missing"

    return b64, data_quality


def build_report(con, prefix: str, out: Path, farm: Optional[str], picks: Optional[list[str]]) -> None:
    """Build HTML report from database."""
    assets = read_sql(con, f"SELECT * FROM {prefix}assets ORDER BY farm, label DESC, asset_id")
    assets = select_assets(assets, picks, farm)
    if assets.empty:
        print("No matching assets in store.")
        return

    # Get KPI metrics
    summaries = read_sql(con, f"SELECT * FROM {prefix}summary ORDER BY ingested_at DESC")
    if farm:
        summaries = summaries[summaries["farm"] == farm]

    kpi_metrics = {}
    if not summaries.empty:
        kpi_metrics = parse_metrics_json(summaries.iloc[0]["metrics_json"])

    # Get runs for operations table
    runs = read_sql(con, f"SELECT * FROM {prefix}runs ORDER BY started_at DESC")
    runs = runs[runs["asset_key"].isin(assets["asset_key"])]

    # Get logs
    logs = read_sql(con, f"SELECT * FROM {prefix}run_log ORDER BY asset_key, ts")
    logs = logs[logs["asset_key"].isin(assets["asset_key"])]

    # Build asset rows and figures
    rows_html = []
    figs_html = []

    for _, meta in assets.iterrows():
        s = read_sql(con, f"SELECT * FROM {prefix}scores WHERE asset_key = ? ORDER BY ts",
                     (meta["asset_key"],))
        if s.empty:
            continue

        # Asset table row
        lead = f"{meta['lead_h']:+.1f}h" if pd.notna(meta["lead_h"]) else "—"
        rules_display = format_rules_human(meta.get("rules_fired"),
                                          meta.get("alert_z"),
                                          s["fused"].max() if len(s) > 0 else None)

        rows_html.append(
            f"<tr>"
            f"<td><a href='#{html.escape(meta['asset_key'])}'><strong>{html.escape(meta['asset_key'])}</strong></a></td>"
            f"<td>{meta['asset_id']}</td>"
            f"<td>{html.escape(meta.get('label') or '')}</td>"
            f"<td>{html.escape(meta.get('description') or '')}</td>"
            f"<td>{format_verdict_badge(meta.get('verdict'))}</td>"
            f"<td>{lead}</td>"
            f"<td><small>{html.escape(rules_display)}</small></td>"
            f"</tr>")

        # Asset timeline figure
        fig_b64, data_quality = asset_figure(s, meta)
        figs_html.append(
            f"<div class='card' id='{html.escape(meta['asset_key'])}'>"
            f"<h4>{html.escape(meta['asset_key'])}</h4>"
            f"<img src='data:image/png;base64,{fig_b64}' alt='Timeline for {html.escape(meta['asset_key'])}'/>"
            f"<div class='diagnostic-box'><strong>Data Quality:</strong> {html.escape(data_quality)}</div>"
            f"</div>")

    # Build operations table
    ops_rows = []
    for r in runs.itertuples():
        alert_z_str = f"{r.alert_z:.2f}" if pd.notna(r.alert_z) else "—"
        duration_str = f"{r.duration_s:.0f}s" if pd.notna(r.duration_s) else "—"
        rules_exp = format_rules_human(r.rules_fired, r.alert_z, None)

        # Parse diagnostics if available
        diag_html = ""
        if pd.notna(r.rules_diagnostic_json):
            try:
                diag = json.loads(r.rules_diagnostic_json)
                diag_html = "<small>"
                for rule_name, rule_info in diag.items():
                    if isinstance(rule_info, dict):
                        if rule_info.get("active"):
                            train_n = rule_info.get("train_n", "?")
                            thr = rule_info.get("thr", "?")
                            diag_html += f"<div>{html.escape(rule_name)}: armed (n={train_n}, thr={thr})</div>"
                        else:
                            train_n = rule_info.get("train_n", "?")
                            diag_html += f"<div>{html.escape(rule_name)}: disarmed (n={train_n})</div>"
                diag_html += "</small>"
            except (json.JSONDecodeError, TypeError):
                pass

        ops_rows.append(
            f"<tr>"
            f"<td>{html.escape(r.asset_key)}</td>"
            f"<td class='timestamp'>{html.escape(r.started_at or '')}</td>"
            f"<td>{duration_str}</td>"
            f"<td>{html.escape(r.status or '')}</td>"
            f"<td>{alert_z_str}</td>"
            f"<td><small>{html.escape(rules_exp)}</small>{diag_html}</td>"
            f"</tr>")

    # Build logs section
    log_html = ""
    for key, grp in logs.groupby("asset_key"):
        # Count by level
        level_counts = grp["level"].value_counts().to_dict()
        level_str = ", ".join(f"{count} {level}" for level, count in sorted(level_counts.items()))

        # Filter to WARNING/ERROR by default
        grp_filtered = grp[grp["level"].isin(["WARNING", "ERROR"])]
        if len(grp_filtered) == 0:
            grp_filtered = grp.head(5)  # Show first 5 if no warnings/errors

        lines_html = "".join(
            f"<div class='{escape_and_format_log(str(l.level).lower())}'>"
            f"<strong>[{escape_and_format_log(l.stage)}]</strong> {escape_and_format_log(l.message)}"
            f"</div>"
            for l in grp_filtered.itertuples())

        log_html += (
            f"<details>"
            f"<summary>{html.escape(key)} — <span class='log-summary'>{level_str}</span></summary>"
            f"<pre>{lines_html}</pre>"
            f"</details>")

    # KPI section
    kpi_html = ""
    if kpi_metrics:
        total = kpi_metrics.get("total_assets", 0)
        detected = kpi_metrics.get("detected", 0)
        missed = kpi_metrics.get("missed", 0)
        false_alarms = kpi_metrics.get("false_alarms", 0)

        kpi_html = f"""
        <div class='kpi-grid'>
            <div class='kpi-box'>
                <div class='kpi-label'>Total Assets</div>
                <div class='kpi-value'>{total}</div>
            </div>
            <div class='kpi-box'>
                <div class='kpi-label'>Detected</div>
                <div class='kpi-value success'>{detected}</div>
                <div class='kpi-desc'>Anomalies found</div>
            </div>
            <div class='kpi-box'>
                <div class='kpi-label'>Missed</div>
                <div class='kpi-value error'>{missed}</div>
                <div class='kpi-desc'>Not detected</div>
            </div>
            <div class='kpi-box'>
                <div class='kpi-label'>False Alarms</div>
                <div class='kpi-value warn'>{false_alarms}</div>
                <div class='kpi-desc'>False positives</div>
            </div>
        </div>
        """

    scope = f"farm {farm}" if farm else (f"{len(assets)} selected assets" if picks else "fleet")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html_content = f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ACM Results — {html.escape(scope)}</title>
    <style>
{CSS}
    </style>
</head>
<body>
    <h2>ACM Results</h2>
    <p><strong>Scope:</strong> {html.escape(scope)} | <strong>Generated:</strong> <span class='timestamp'>{html.escape(timestamp)}</span></p>

    <h3>Summary</h3>
    {kpi_html}

    <h3>Assets ({len(assets)})</h3>
    <table>
        <tr>
            <th>Asset Key</th>
            <th>ID</th>
            <th>Label</th>
            <th>Description</th>
            <th>Verdict</th>
            <th>Lead Time</th>
            <th>Rules Fired</th>
        </tr>
        {''.join(rows_html)}
    </table>

    <h3>Timelines</h3>
    {''.join(figs_html)}

    <h3>Operations</h3>
    <table>
        <tr>
            <th>Asset</th>
            <th>Run Started</th>
            <th>Duration</th>
            <th>Status</th>
            <th>Alert Z</th>
            <th>Rules & Diagnostics</th>
        </tr>
        {''.join(ops_rows)}
    </table>

    <h3>Logs</h3>
    {log_html if log_html else '<p><em>No logs available</em></p>'}

    <hr>
    <p style="font-size: 12px; color: #6e7781; margin-top: 32px;">
        Generated by ACM Report Tool. Data from canonical SQL results store.
    </p>
</body>
</html>"""

    out.write_text(html_content)
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
