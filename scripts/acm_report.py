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
:root {
    /* warm industrial base */
    --bg: #f0ede9;
    --paper: #f8f6f3;
    --panel: #eae5e0;
    --panel2: #e0d9d3;
    --card: #f5f2ee;

    /* ink and muted text */
    --ink: #12100e;
    --text: #1e1916;
    --muted: #72685f;
    --soft: #a4998f;

    /* borders */
    --line: #d5cec7;
    --line2: #c4bdb5;

    /* dark command surfaces */
    --dark: #0d0c0b;
    --dark2: #161311;
    --dark3: #221c19;
    --darkLine: #3d3229;

    /* semantic accents */
    --blue: #1d55d4;
    --blue-light: #3b7df5;
    --green: #15783f;
    --orange: #c84e00;
    --amber: #a87800;
    --red: #c93426;
    --purple: #6842c2;

    /* geometry */
    --radius: 8px;

    /* typography */
    --font: 'Satoshi', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    --mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Consolas, monospace;

    --shadow: 0 1px 0 rgba(255,255,255,.7) inset, 0 1px 2px rgba(18,16,14,.08);
    --shadow-deep: 0 1px 0 rgba(255,255,255,.6) inset, 0 3px 10px rgba(18,16,14,.10);
    --shadow-inset: inset 0 1px 3px rgba(18,16,14,.18);
}

* {
    box-sizing: border-box;
}

html {
    scroll-behavior: smooth;
}

body {
    font-family: var(--font);
    font-size: 20px;
    line-height: 1.6;
    color: var(--text);
    background: var(--bg);
    margin: 0;
    padding: 0;
}

/* ---- Header: dark command band ---- */
.header {
    background: linear-gradient(180deg, var(--dark2), var(--dark));
    border-bottom: 3px solid var(--orange);
    padding: 36px 44px;
}

.header-content {
    max-width: 1360px;
    margin: 0 auto;
}

.header h1 {
    margin: 0 0 12px 0;
    font-size: 56px;
    font-weight: 800;
    color: #faf7f3;
    letter-spacing: -0.02em;
}

.header-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 32px;
    margin-top: 16px;
    font-size: 22px;
    font-weight: 600;
    color: #ddd3c8;
}

.header-meta span {
    display: flex;
    align-items: center;
    gap: 10px;
}

.meta-label {
    font-family: var(--mono);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 15.5px;
    color: #9a8d7d;
}

.container {
    max-width: 1360px;
    margin: 0 auto;
    padding: 36px 44px 8px;
}

section {
    margin-bottom: 48px;
}

h2 {
    margin: 0 0 24px 0;
    font-size: 30px;
    font-weight: 800;
    color: var(--ink);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding-bottom: 14px;
    border-bottom: 3px solid var(--dark);
}

h3 {
    margin: 30px 0 18px 0;
    font-size: 25px;
    font-weight: 800;
    color: var(--ink);
}

h4 {
    margin: 0 0 6px 0;
    font-size: 23px;
    font-weight: 800;
    color: var(--ink);
    letter-spacing: -0.01em;
}

p {
    margin: 8px 0;
    color: var(--text);
}

.text-muted {
    color: var(--muted);
    font-style: italic;
    margin: 12px 0;
}

/* ---- KPI strip: tactile raised cards on a recessed rail ---- */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 14px;
    margin: 0 0 8px 0;
    background: var(--panel2);
    padding: 14px;
    border: 1px solid var(--line2);
    border-radius: var(--radius);
    box-shadow: var(--shadow-inset);
}

.kpi-box {
    background: linear-gradient(180deg, #ffffff, var(--card));
    border: 1px solid var(--line);
    border-radius: 6px;
    box-shadow: var(--shadow);
    padding: 22px 24px;
}

.kpi-label {
    font-family: var(--mono);
    font-size: 16px;
    color: var(--muted);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-bottom: 14px;
}

.kpi-value {
    font-size: 64px;
    font-weight: 800;
    color: var(--ink);
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.02em;
    line-height: 1;
}

.kpi-value.success { color: var(--green); }
.kpi-value.error { color: var(--red); }
.kpi-value.warn { color: var(--amber); }

.kpi-desc {
    font-size: 17px;
    font-weight: 600;
    color: var(--muted);
    margin-top: 10px;
}

/* ---- Tables: white inset surface, mono headers, dense industrial rows ---- */
table {
    border-collapse: collapse;
    width: 100%;
    margin: 0;
    font-size: 20px;
    background: var(--paper);
}

td, th {
    padding: 16px 20px;
    text-align: left;
    border-bottom: 1px solid var(--line);
    vertical-align: top;
}

th {
    background: var(--panel2);
    font-family: var(--mono);
    font-weight: 700;
    color: var(--text);
    text-transform: uppercase;
    font-size: 15.5px;
    letter-spacing: 0.06em;
    border-bottom: 2px solid var(--line2);
}

tbody tr:last-child td {
    border-bottom: none;
}

tbody tr:hover {
    background: var(--panel);
}

.rules-text {
    display: block;
    font-size: 20px;
    font-weight: 600;
    color: var(--ink);
    line-height: 1.5;
}

.diag-line {
    display: block;
    font-family: var(--mono);
    font-size: 17px;
    color: var(--muted);
    margin-top: 8px;
    line-height: 1.5;
}

/* ---- Card frame: raised panel, layered shadow, no flat slab ---- */
.card {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    box-shadow: var(--shadow-deep);
    padding: 0;
    margin: 0 0 24px 0;
    overflow: hidden;
}

.card > table {
    margin: 0;
}

/* ---- Diagnostic block: labelled inset panel, NOT a colored accent stripe ---- */
.diag-box {
    background: var(--paper);
    border: 1px solid var(--line);
    border-radius: 6px;
    box-shadow: var(--shadow-inset);
    padding: 16px 20px;
    margin-top: 16px;
    font-size: 19px;
    font-weight: 600;
    color: var(--text);
    line-height: 1.5;
}

.diag-box + .diag-box {
    margin-top: 12px;
}

.diag-label {
    display: block;
    font-family: var(--mono);
    font-size: 14.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--soft);
    margin-bottom: 8px;
}

/* ---- Status pills: tactile, filled, semantic ---- */
.badge {
    display: inline-block;
    padding: 8px 16px;
    border-radius: 5px;
    font-size: 16px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border: 1px solid rgba(0,0,0,.12);
    box-shadow: 0 1px 0 rgba(255,255,255,.25) inset, 0 1px 2px rgba(18,16,14,.18);
}

.badge-detected, .badge-clean {
    background: var(--green);
    color: #f3fbf6;
}

.badge-missed {
    background: var(--red);
    color: #fdf3f1;
}

.badge-false_alarm, .badge-false-alarm {
    background: var(--amber);
    color: #fdf8ec;
}

.badge:not([class*="badge-"]) {
    background: var(--soft);
    color: #fff;
}

/* ---- Asset timeline cards ---- */
.timeline-cards {
    display: flex;
    flex-direction: column;
    gap: 24px;
}

.timeline-cards .card {
    padding: 22px 26px 24px;
}

.timeline-cards .card img {
    width: 100%;
    height: auto;
    display: block;
    margin: 12px 0 0;
    border: 1px solid var(--line);
    border-radius: 6px;
    image-rendering: -webkit-optimize-contrast;
}

/* ---- Logs ---- */
.logs-section {
    display: flex;
    flex-direction: column;
    gap: 1px;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    overflow: hidden;
    box-shadow: var(--shadow-deep);
}

.logs-section details {
    padding: 0;
    background: var(--paper);
    border-bottom: 1px solid var(--line);
}

.logs-section details:last-child {
    border-bottom: none;
}

.logs-section details[open] {
    background: var(--card);
}

.logs-section summary {
    cursor: pointer;
    font-weight: 700;
    font-size: 20px;
    padding: 16px 20px;
    user-select: none;
    color: var(--ink);
    list-style: none;
}

.logs-section summary::-webkit-details-marker {
    display: none;
}

.logs-section summary:hover {
    background: var(--panel);
}

.log-summary {
    font-family: var(--mono);
    font-size: 17px;
    color: var(--muted);
    font-weight: 500;
    margin-left: 10px;
}

.logs-section pre {
    margin: 0;
    padding: 18px 20px 20px;
    background: var(--dark3);
    border-top: 1px solid var(--darkLine);
    font-size: 16.5px;
    line-height: 1.6;
    overflow-x: auto;
    font-family: var(--mono);
    white-space: pre-wrap;
    color: #e7ded3;
}

.logs-section .info { color: #7fb3ff; }
.logs-section .warning { color: #e0b04a; font-weight: 700; }
.logs-section .error { color: #f0786a; font-weight: 700; }
.logs-section .debug { color: #9a8d7d; }

.timestamp {
    font-family: var(--mono);
    font-size: 18px;
    color: var(--muted);
}

a {
    color: var(--blue);
    text-decoration: none;
    font-weight: 700;
}

a:hover {
    text-decoration: underline;
}

/* ---- Footer ---- */
.footer {
    border-top: 3px solid var(--dark);
    background: var(--paper);
    padding: 24px 44px;
    margin-top: 16px;
}

.footer-content {
    max-width: 1360px;
    margin: 0 auto;
}

.footer p {
    margin: 0;
    font-size: 17px;
    font-weight: 600;
    color: var(--muted);
}

.footer p strong {
    color: var(--ink);
}

/* ---- Responsive ---- */
@media (max-width: 768px) {
    .header {
        padding: 24px 22px;
    }

    .container {
        padding: 26px 22px 8px;
    }

    .kpi-grid {
        grid-template-columns: 1fr 1fr;
    }

    .header-meta {
        flex-direction: column;
        gap: 10px;
    }

    h2 {
        font-size: 24px;
    }

    .kpi-value {
        font-size: 42px;
    }

    table {
        font-size: 17px;
    }

    td, th {
        padding: 11px 13px;
    }
}

/* ---- Print ---- */
@media print {
    body {
        background: #ffffff;
    }

    .header {
        background: var(--dark2);
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }

    table, .card, details {
        page-break-inside: avoid;
    }

    a {
        color: var(--ink);
    }
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
    """Convert matplotlib figure to base64-encoded PNG at print-grade resolution."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=170, bbox_inches="tight")
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




def format_data_quality_human(dq_json: Optional[str]) -> Optional[str]:
    """Convert a run's data_quality_json into one human-readable line."""
    if not dq_json or pd.isna(dq_json):
        return None
    try:
        dq = json.loads(dq_json)
    except (json.JSONDecodeError, TypeError):
        return None
    parts = []
    if dq.get("train_rows") is not None:
        parts.append(f"{dq['train_rows']:,} training rows")
    if dq.get("score_rows") is not None:
        parts.append(f"{dq['score_rows']:,} scored rows")
    if dq.get("channels") is not None:
        parts.append(f"{dq['channels']} channels")
    if dq.get("nan_density") is not None:
        parts.append(f"{dq['nan_density'] * 100:.2f}% missing")
    if dq.get("duplicate_ts"):
        parts.append(f"{dq['duplicate_ts']} duplicate timestamps")
    if dq.get("cadence_s"):
        cadence = dq["cadence_s"]
        parts.append(f"{cadence / 60:.0f}-min cadence" if cadence >= 60 else f"{cadence:.0f}s cadence")
    return ", ".join(parts) if parts else None


def format_calibration_human(calib_json: Optional[str]) -> Optional[str]:
    """Convert a run's calibration_json (fusion weights) into one human-readable line."""
    if not calib_json or pd.isna(calib_json):
        return None
    try:
        calib = json.loads(calib_json)
    except (json.JSONDecodeError, TypeError):
        return None
    weights = calib.get("weights_used") or {}
    if not weights:
        return None
    parts = [f"{detector_label(k)} {v:.2f}" for k, v in weights.items()]
    tuned = "auto-tuned from this run's data" if calib.get("auto_tuned") else "fixed weights"
    return f"Fusion weights ({tuned}): " + ", ".join(parts)


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
        2, 1, figsize=(13, 5.2), sharex=True,
        gridspec_kw={"height_ratios": [3, 1.2], "hspace": 0.14})

    # Plot fused score
    ax1.plot(ts, s["fused"], lw=0.9, color="#0969da", label="Fused score")

    # Plot alert threshold
    thr = meta.get("alert_z")
    if pd.notna(thr):
        ax1.axhline(thr, color="#9a6700", lw=1.2, ls="--",
                    label=f"Alert threshold: {thr:.2f}")

    # Shade alarm regions
    alarm = s["alarm"].to_numpy().astype(bool)
    if alarm.any():
        ax1.fill_between(ts, 0, s["fused"].max() * 1.1, where=alarm,
                         color="#cf222e", alpha=0.14, label="Alarm period")

    ax1.set_ylabel("Anomaly Score (Z)", fontsize=12, fontweight=600)
    ax1.legend(loc="upper left", fontsize=10, ncol=3, frameon=True, fancybox=False,
              edgecolor="#d0d7de")
    ax1.tick_params(axis="both", labelsize=10)

    # Title with full description
    desc = meta.get("description") or meta.get("label") or ""
    if desc:
        title = f"{meta['asset_key']} (ID: {meta['asset_id']}) — {desc}"
    else:
        title = f"{meta['asset_key']} (ID: {meta['asset_id']})"
    ax1.set_title(title, fontsize=12, loc="left", fontweight=700)
    ax1.grid(True, alpha=0.2)

    # Detector heatmap
    zmat = np.vstack([np.nan_to_num(pd.to_numeric(s[z], errors="coerce").to_numpy(), nan=0.0)
                      for z in Z_COLS])
    im = ax2.imshow(np.clip(zmat, 0, 8), aspect="auto", cmap="inferno", vmin=0, vmax=8,
                    extent=[mdates.date2num(ts.iloc[0]), mdates.date2num(ts.iloc[-1]),
                           len(Z_COLS), 0])

    # Detector labels with full names
    ax2.set_yticks(np.arange(len(Z_COLS)) + 0.5)
    ax2.set_yticklabels([detector_label(z) for z in Z_COLS], fontsize=10)
    ax2.set_ylabel("Detectors", fontsize=11, fontweight=600)
    ax2.xaxis_date()
    ax2.set_xlabel("Time", fontsize=11, fontweight=600)
    ax2.tick_params(axis="x", labelsize=10)

    # Add colorbar
    cbar = fig.colorbar(im, ax=ax2, orientation="vertical", pad=0.02, fraction=0.05)
    cbar.set_label("Score", fontsize=10)
    cbar.ax.tick_params(labelsize=9)

    fig.autofmt_xdate(rotation=30, ha='right')
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

    # KPI metrics are derived strictly from the assets selected for THIS report
    # (never from the fleet-wide summary table) so a scoped report — one asset,
    # a handful of assets, a single farm — never bleeds in fleet-wide numbers.
    verdicts = assets["verdict"].fillna("UNKNOWN").astype(str).str.upper()
    kpi_metrics = {
        "total_assets": int(len(assets)),
        "detected": int((verdicts == "DETECTED").sum()),
        "clean": int((verdicts == "CLEAN").sum()),
        "missed": int((verdicts == "MISSED").sum()),
        "false_alarms": int((verdicts == "FALSE_ALARM").sum()),
    }

    # Get runs for operations table
    runs = read_sql(con, f"SELECT * FROM {prefix}runs ORDER BY started_at DESC")
    runs = runs[runs["asset_key"].isin(assets["asset_key"])]

    # Latest run per asset (runs is already DESC by started_at) for diagnostic boxes
    latest_runs = (runs.drop_duplicates(subset="asset_key", keep="first")
                        .set_index("asset_key"))

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
            f"<td><span class='rules-text'>{html.escape(rules_display)}</span></td>"
            f"</tr>")

        # Asset timeline figure
        fig_b64, data_quality_fallback = asset_figure(s, meta)

        run_row = latest_runs.loc[meta["asset_key"]] if meta["asset_key"] in latest_runs.index else None
        data_quality = (format_data_quality_human(run_row.get("data_quality_json")) if run_row is not None else None) \
            or data_quality_fallback
        calibration = format_calibration_human(run_row.get("calibration_json")) if run_row is not None else None

        diag_boxes = f"<div class='diag-box'><span class='diag-label'>Data Quality</span>{html.escape(data_quality)}</div>"
        if calibration:
            diag_boxes += f"<div class='diag-box'><span class='diag-label'>Calibration</span>{html.escape(calibration)}</div>"

        figs_html.append(
            f"<div class='card' id='{html.escape(meta['asset_key'])}'>"
            f"<h4>{html.escape(meta['asset_key'])}</h4>"
            f"<img src='data:image/png;base64,{fig_b64}' alt='Timeline for {html.escape(meta['asset_key'])}'/>"
            f"{diag_boxes}"
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
                for rule_name, rule_info in diag.items():
                    if isinstance(rule_info, dict):
                        if rule_info.get("active"):
                            train_n = rule_info.get("train_n", "?")
                            thr = rule_info.get("thr", "?")
                            diag_html += f"<div class='diag-line'>{html.escape(rule_name)}: armed (n={train_n}, thr={thr})</div>"
                        else:
                            train_n = rule_info.get("train_n", "?")
                            diag_html += f"<div class='diag-line'>{html.escape(rule_name)}: disarmed (n={train_n})</div>"
            except (json.JSONDecodeError, TypeError):
                pass

        data_quality_line = format_data_quality_human(getattr(r, "data_quality_json", None))
        calibration_line = format_calibration_human(getattr(r, "calibration_json", None))
        if data_quality_line:
            diag_html += f"<div class='diag-line'>Data: {html.escape(data_quality_line)}</div>"
        if calibration_line:
            diag_html += f"<div class='diag-line'>{html.escape(calibration_line)}</div>"

        ops_rows.append(
            f"<tr>"
            f"<td>{html.escape(r.asset_key)}</td>"
            f"<td class='timestamp'>{html.escape(r.started_at or '')}</td>"
            f"<td>{duration_str}</td>"
            f"<td>{html.escape(r.status or '')}</td>"
            f"<td>{alert_z_str}</td>"
            f"<td><span class='rules-text'>{html.escape(rules_exp)}</span>{diag_html}</td>"
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

    # KPI section — always derived from `assets` above, so this is exact for
    # whatever scope (single asset / a handful / a farm / the whole fleet) was requested.
    total = kpi_metrics["total_assets"]
    detected = kpi_metrics["detected"]
    clean = kpi_metrics["clean"]
    missed = kpi_metrics["missed"]
    false_alarms = kpi_metrics["false_alarms"]

    kpi_html = f"""
    <div class='kpi-grid'>
        <div class='kpi-box'>
            <div class='kpi-label'>Assets in Scope</div>
            <div class='kpi-value'>{total}</div>
        </div>
        <div class='kpi-box'>
            <div class='kpi-label'>Detected</div>
            <div class='kpi-value success'>{detected}</div>
            <div class='kpi-desc'>Confirmed anomaly, flagged</div>
        </div>
        <div class='kpi-box'>
            <div class='kpi-label'>Clean</div>
            <div class='kpi-value success'>{clean}</div>
            <div class='kpi-desc'>No anomaly, no flag</div>
        </div>
        <div class='kpi-box'>
            <div class='kpi-label'>Missed</div>
            <div class='kpi-value error'>{missed}</div>
            <div class='kpi-desc'>Confirmed anomaly, not flagged</div>
        </div>
        <div class='kpi-box'>
            <div class='kpi-label'>False Alarms</div>
            <div class='kpi-value warn'>{false_alarms}</div>
            <div class='kpi-desc'>Flagged, no confirmed anomaly</div>
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
    <title>ACM Condition Monitor Report — {html.escape(scope)}</title>
    <style>
{CSS}
    </style>
</head>
<body>
    <div class='header'>
        <div class='header-content'>
            <h1>Condition Monitor Report</h1>
            <div class='header-meta'>
                <span><span class='meta-label'>Scope:</span> {html.escape(scope)}</span>
                <span><span class='meta-label'>Assets Analyzed:</span> {len(assets)}</span>
                <span><span class='meta-label'>Generated:</span> {html.escape(timestamp)}</span>
            </div>
        </div>
    </div>

    <div class='container'>
        <section>
            <h2>Performance Summary</h2>
            {kpi_html}
        </section>

        <section>
            <h2>Assets Overview</h2>
            <div class='card'>
                <table>
                    <thead>
                        <tr>
                            <th>Asset Key</th>
                            <th>ID</th>
                            <th>Label</th>
                            <th>Description</th>
                            <th>Verdict</th>
                            <th>Lead Time</th>
                            <th>Rules Fired</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rows_html)}
                    </tbody>
                </table>
            </div>
        </section>

        <section>
            <h2>Detailed Analysis</h2>
            <div class='timeline-cards'>
                {''.join(figs_html)}
            </div>
        </section>

        <section>
            <h2>Scoring Operations</h2>
            <div class='card'>
                <table>
                    <thead>
                        <tr>
                            <th>Asset</th>
                            <th>Run Started</th>
                            <th>Duration</th>
                            <th>Status</th>
                            <th>Alert Z</th>
                            <th>Rules & Diagnostics</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(ops_rows)}
                    </tbody>
                </table>
            </div>
        </section>

        <section>
            <h2>Execution Logs</h2>
            <div class='logs-section'>
                {log_html if log_html else '<p class="text-muted">No logs available</p>'}
            </div>
        </section>
    </div>

    <div class='footer'>
        <div class='footer-content'>
            <p>ACM Condition Monitor | Professional Asset Assessment Report</p>
            <p style='margin-top: 8px;'>
                Data from canonical SQL results store — {html.escape(timestamp)}
            </p>
        </div>
    </div>
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
