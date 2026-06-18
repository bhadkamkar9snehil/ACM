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
* {
    box-sizing: border-box;
}

html {
    scroll-behavior: smooth;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
    font-size: 15px;
    line-height: 1.6;
    color: #2c3e50;
    background: linear-gradient(135deg, #f5f7fa 0%, #f9fafb 100%);
    margin: 0;
    padding: 0;
    min-height: 100vh;
}

.header {
    background: #ffffff;
    border-bottom: 1px solid #e1e8ed;
    padding: 28px 40px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.03);
    margin-bottom: 32px;
}

.header-content {
    max-width: 1400px;
    margin: 0 auto;
}

.header h1 {
    margin: 0 0 4px 0;
    font-size: 32px;
    font-weight: 700;
    color: #1a202c;
    letter-spacing: -0.5px;
}

.header-meta {
    display: flex;
    gap: 24px;
    margin-top: 12px;
    font-size: 13px;
    color: #6e7681;
}

.header-meta span {
    display: flex;
    align-items: center;
    gap: 6px;
}

.meta-label {
    font-weight: 600;
    color: #2c3e50;
}

.container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 40px;
}

h2 {
    margin: 40px 0 24px 0;
    font-size: 26px;
    font-weight: 700;
    color: #1a202c;
    border-bottom: 3px solid #2c3e50;
    padding-bottom: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-size: 20px;
}

h3 {
    margin: 32px 0 20px 0;
    font-size: 18px;
    font-weight: 700;
    color: #1a202c;
}

h4 {
    margin: 16px 0 12px 0;
    font-size: 15px;
    font-weight: 700;
    color: #2c3e50;
}

p {
    margin: 8px 0;
    color: #555;
}

/* KPI Grid */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 20px;
    margin: 24px 0 32px 0;
}

.kpi-box {
    background: #ffffff;
    border: 1px solid #e1e8ed;
    border-radius: 12px;
    padding: 24px;
    text-align: center;
    transition: all 0.3s ease;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.kpi-box:hover {
    border-color: #2c3e50;
    box-shadow: 0 4px 12px rgba(44, 62, 80, 0.1);
    transform: translateY(-2px);
}

.kpi-label {
    font-size: 12px;
    color: #6e7681;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 12px;
}

.kpi-value {
    font-size: 42px;
    font-weight: 800;
    color: #1a202c;
    margin: 12px 0 8px 0;
    font-variant-numeric: tabular-nums;
}

.kpi-desc {
    font-size: 13px;
    color: #6e7681;
    margin-top: 8px;
}

/* Tables */
table {
    border-collapse: collapse;
    width: 100%;
    margin: 24px 0;
    font-size: 14px;
    background: #ffffff;
    border: 1px solid #e1e8ed;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

td, th {
    padding: 14px 16px;
    text-align: left;
    border-bottom: 1px solid #e1e8ed;
}

th {
    background: #f5f7fa;
    font-weight: 700;
    color: #2c3e50;
    text-transform: uppercase;
    font-size: 12px;
    letter-spacing: 0.3px;
}

tbody tr:last-child td {
    border-bottom: none;
}

tbody tr {
    transition: background-color 0.2s ease;
}

tbody tr:nth-child(odd) {
    background: #ffffff;
}

tbody tr:nth-child(even) {
    background: #f9fafb;
}

tbody tr:hover {
    background: #f0f4f8;
}

/* Cards */
.card {
    background: #ffffff;
    border: 1px solid #e1e8ed;
    border-radius: 12px;
    padding: 24px;
    margin: 24px 0;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    transition: box-shadow 0.3s ease;
}

.card:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.card img {
    width: 100%;
    max-width: 100%;
    border-radius: 8px;
    margin: 16px 0;
    border: 1px solid #e1e8ed;
}

/* Diagnostic Box */
.diagnostic-box {
    background: #f0f4f8;
    border-left: 4px solid #3b82f6;
    padding: 16px;
    margin: 16px 0;
    border-radius: 6px;
    font-size: 14px;
    color: #2c3e50;
}

.diagnostic-item {
    margin: 6px 0;
    display: flex;
    align-items: center;
    gap: 8px;
}

.diagnostic-item strong {
    color: #1a202c;
}

/* Status Indicators */
.status-indicator {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    font-weight: 600;
    padding: 6px 12px;
    border-radius: 6px;
    background: #f0f4f8;
    color: #2c3e50;
}

.status-armed { background: #dbeafe; color: #1e40af; }
.status-disarmed { background: #fecaca; color: #991b1b; }

/* Badges */
.badge {
    display: inline-block;
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.3px;
}

.badge-detected {
    background: #dcfce7;
    color: #166534;
    border: 1px solid #86efac;
}

.badge-clean {
    background: #dcfce7;
    color: #166534;
    border: 1px solid #86efac;
}

.badge-missed {
    background: #fee2e2;
    color: #991b1b;
    border: 1px solid #fca5a5;
}

.badge-false-alarm {
    background: #fef3c7;
    color: #b45309;
    border: 1px solid #fcd34d;
}

/* Details/Logs */
details {
    margin: 12px 0;
    padding: 12px;
    background: #ffffff;
    border: 1px solid #e1e8ed;
    border-radius: 8px;
}

summary {
    cursor: pointer;
    font-weight: 600;
    padding: 8px;
    user-select: none;
    color: #2c3e50;
    transition: color 0.2s ease;
    display: flex;
    align-items: center;
}

summary:hover {
    color: #3b82f6;
}

summary::marker {
    color: #3b82f6;
}

pre {
    background: #f5f7fa;
    padding: 16px;
    border-radius: 6px;
    font-size: 13px;
    overflow-x: auto;
    border: 1px solid #e1e8ed;
    line-height: 1.5;
    color: #2c3e50;
    margin: 12px 0 0 0;
}

/* Text Colors */
.info { color: #3b82f6; }
.warn { color: #f59e0b; }
.error { color: #ef4444; }
.success { color: #10b981; }

/* Log Summary */
.log-summary {
    font-size: 12px;
    color: #6e7681;
    font-weight: 500;
    margin-left: 8px;
}

.timestamp {
    color: #6e7681;
    font-size: 13px;
    font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, monospace;
}

/* Links */
a {
    color: #3b82f6;
    text-decoration: none;
    font-weight: 500;
    transition: color 0.2s ease;
}

a:hover {
    color: #1e40af;
    text-decoration: underline;
}

/* Footer */
.footer {
    border-top: 1px solid #e1e8ed;
    background: #ffffff;
    padding: 24px 40px;
    margin-top: 48px;
    text-align: center;
    font-size: 12px;
    color: #6e7681;
}

/* Responsive */
@media (max-width: 768px) {
    .header {
        padding: 20px 24px;
    }

    .container {
        padding: 0 24px;
    }

    .kpi-grid {
        grid-template-columns: 1fr;
    }

    .header-meta {
        flex-direction: column;
        gap: 8px;
    }

    h2 {
        font-size: 22px;
    }

    .kpi-value {
        font-size: 32px;
    }
}

/* Print */
@media print {
    body {
        background: #ffffff;
        margin: 0;
        padding: 0;
    }

    .header {
        box-shadow: none;
        border-bottom: 2px solid #2c3e50;
    }

    .footer {
        display: none;
    }

    table, .card, details {
        page-break-inside: avoid;
        box-shadow: none;
    }

    a {
        color: #2c3e50;
    }
}

/* Animations */
@keyframes fadeIn {
    from {
        opacity: 0;
        transform: translateY(10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.card, .kpi-box, table {
    animation: fadeIn 0.3s ease;
}

h1 {
    margin: 0;
    font-size: 28px;
    font-weight: 700;
    color: #1a202c;
    letter-spacing: -0.5px;
}

h2 {
    margin: 28px 0 16px;
    font-size: 20px;
    font-weight: 700;
    color: #1a202c;
    border-bottom: 1px solid #e1e8ed;
    padding-bottom: 12px;
}

section {
    margin-bottom: 48px;
}

section:last-of-type {
    margin-bottom: 32px;
}

.container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 40px;
}

.header-meta {
    display: flex;
    gap: 32px;
    margin-top: 16px;
    font-size: 14px;
    color: #6e7681;
}

.header-meta span {
    display: flex;
    align-items: center;
    gap: 8px;
}

.meta-label {
    font-weight: 600;
    color: #2c3e50;
}

.text-muted {
    color: #6e7681;
    font-style: italic;
    margin: 16px 0;
}

.timeline-cards {
    display: flex;
    flex-direction: column;
    gap: 24px;
}

.timeline-cards .card {
    padding: 20px;
    border: 1px solid #e1e8ed;
}

.timeline-cards .card h4 {
    margin: 0 0 12px;
    font-size: 16px;
    font-weight: 600;
    color: #1a202c;
}

.timeline-cards .card img {
    width: 100%;
    height: auto;
    border-radius: 4px;
    margin-bottom: 12px;
    display: block;
}

.diagnostic-box {
    background: #f5f7fa;
    padding: 12px 16px;
    border-radius: 4px;
    font-size: 13px;
    color: #2c3e50;
    border-left: 3px solid #0969da;
    margin-top: 12px;
}

.logs-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.logs-section details {
    padding: 12px 16px;
    background: #f5f7fa;
    border: 1px solid #e1e8ed;
    border-radius: 4px;
    cursor: pointer;
}

.logs-section details[open] {
    background: #ffffff;
    border-color: #d1d9e0;
}

.logs-section summary {
    font-weight: 600;
    color: #2c3e50;
    user-select: none;
    outline: none;
}

.logs-section summary:hover {
    color: #0969da;
}

.log-summary {
    font-size: 12px;
    color: #6e7681;
    font-weight: 400;
    margin-left: 8px;
}

.logs-section pre {
    margin: 12px 0 0;
    padding: 12px;
    background: #f9fafb;
    border-left: 3px solid #d1d9e0;
    border-radius: 0;
    font-size: 12px;
    overflow-x: auto;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
}

.logs-section .info {
    color: #0969da;
}

.logs-section .warning {
    color: #bf8700;
    font-weight: 500;
}

.logs-section .error {
    color: #cf222e;
    font-weight: 500;
}

.logs-section .debug {
    color: #6e7681;
}

.footer {
    background: #ffffff;
    border-top: 1px solid #e1e8ed;
    padding: 28px 40px;
    margin-top: 48px;
    text-align: center;
}

.footer-content {
    max-width: 1400px;
    margin: 0 auto;
}

.footer p {
    margin: 0;
    font-size: 14px;
    color: #2c3e50;
    font-weight: 500;
}

table thead {
    background: #f5f7fa;
}

table tbody tr {
    border-bottom: 1px solid #e1e8ed;
}

table tbody tr:hover {
    background: #fafbfc;
}

table td {
    vertical-align: middle;
    padding: 12px;
}

table th {
    vertical-align: middle;
    padding: 12px;
    font-weight: 600;
    color: #2c3e50;
    font-size: 13px;
    text-align: left;
}

.timestamp {
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    font-size: 12px;
    color: #6e7681;
}

.badge {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
}

.badge-detected, .badge-clean {
    background: #ddf4e8;
    color: #1a7f37;
}

.badge-missed {
    background: #ffebe6;
    color: #cf222e;
}

.badge-false_alarm {
    background: #fff3c6;
    color: #bf8700;
}

@media (max-width: 768px) {
    .header-meta {
        flex-direction: column;
        gap: 12px;
    }

    .container {
        padding: 0 20px;
    }

    h1 {
        font-size: 24px;
    }

    h2 {
        font-size: 18px;
    }

    table {
        font-size: 13px;
    }

    table td, table th {
        padding: 8px;
    }
}

@media print {
    body {
        background: white;
    }

    .header, .footer {
        page-break-after: avoid;
    }

    section {
        page-break-inside: avoid;
    }

    .timeline-cards .card {
        page-break-inside: avoid;
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
            f"<td><small>{html.escape(rules_display)}</small></td>"
            f"</tr>")

        # Asset timeline figure
        fig_b64, data_quality_fallback = asset_figure(s, meta)

        run_row = latest_runs.loc[meta["asset_key"]] if meta["asset_key"] in latest_runs.index else None
        data_quality = (format_data_quality_human(run_row.get("data_quality_json")) if run_row is not None else None) \
            or data_quality_fallback
        calibration = format_calibration_human(run_row.get("calibration_json")) if run_row is not None else None

        diag_boxes = f"<div class='diagnostic-box'><strong>Data Quality:</strong> {html.escape(data_quality)}</div>"
        if calibration:
            diag_boxes += f"<div class='diagnostic-box'><strong>Calibration:</strong> {html.escape(calibration)}</div>"

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

        data_quality_line = format_data_quality_human(getattr(r, "data_quality_json", None))
        calibration_line = format_calibration_human(getattr(r, "calibration_json", None))
        if data_quality_line:
            diag_html += f"<small><div>Data: {html.escape(data_quality_line)}</div></small>"
        if calibration_line:
            diag_html += f"<small><div>{html.escape(calibration_line)}</div></small>"

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
            {kpi_html if kpi_html else '<p class="text-muted">No summary metrics available</p>'}
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
            <p style='font-size: 13px; color: #6e7681; margin-top: 8px;'>
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
