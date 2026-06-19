#!/usr/bin/env python3
"""
ACM visual report - one module, any selection of assets, full timeline.

Reads the canonical SQL results store (scripts/acm_store.py; SQLite file or
SQL Server) and renders a standalone HTML report: per asset the fused
anomaly timeline start-to-end with the self-tuned threshold and alarm
shading, a per-detector z heat strip (with click-to-isolate per detector),
and the verdict; a fleet summary table on top. No server required - open
the file in a browser. Charts are interactive Plotly figures loaded from a
CDN script tag; no local asset files are required.

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
import html
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

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

# Per-detector trace colors for the interactive heatmap/timeline, drawn from
# the same warm industrial palette as the page CSS so charts and chrome read
# as one design system instead of two.
DETECTOR_COLORS = {
    "ar1_z": "#b3551e",
    "pca_spe_z": "#c2742a",
    "pca_t2_z": "#a8731f",
    "iforest_z": "#8a5a16",
    "gmm_z": "#c98a3a",
    "omr_z": "#7a4a12",
}

# Verdict vocabulary covers both pipelines seen in production data:
# DETECTED/CLEAN/MISSED/FALSE_ALARM (care-style scoring) and ALARM/OK
# (fleet-style scoring). DETECTED is a confirmed anomaly so it gets its own
# attention-orange rather than sharing green with CLEAN/OK (nothing wrong).
VERDICT_COLOR = {
    "DETECTED": "#b3551e",
    "CLEAN": "#3d7a3f",
    "MISSED": "#a8342b",
    "FALSE_ALARM": "#a8791f",
    "ALARM": "#a8342b",
    "OK": "#3d7a3f",
}

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;500;600;700;800&family=Share+Tech+Mono&display=swap');

:root {
    /* warm industrial paper base, light theme */
    --bg: #ece6dc;
    --paper: #f7f3ec;
    --panel: #e4dccd;
    --panel2: #d8cdb8;
    --card: #f7f3ec;

    /* ink and muted text */
    --ink: #2a2014;
    --text: #332819;
    --muted: #6b5c45;
    --soft: #998765;

    /* borders - thick, structural, no rounding */
    --line: #c2b596;
    --line2: #a89871;

    /* dark command surfaces (header band, footer, log pane) */
    --dark: #241b10;
    --dark2: #2e2210;
    --dark3: #1c150d;
    --darkLine: #4a3a22;

    /* semantic accents, warm forge family */
    --blue: #2f6f8f;
    --blue-light: #4a8ba8;
    --green: #3d7a3f;
    --orange: #b3551e;
    --amber: #a8791f;
    --red: #a8342b;
    --purple: #6e5490;

    /* geometry - boxy, no rounding on structural elements */
    --radius: 0px;
    --content-width: 1800px;

    /* typography - strict role split, large readable base */
    --font: 'Barlow Condensed', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    --mono: 'Share Tech Mono', ui-monospace, SFMono-Regular, Consolas, monospace;

    /* tactile 3D physics: raised casts a soft drop shadow with a light top
       highlight; inset has a heavy inner shadow and no outer shadow */
    --shadow: 0 1px 0 rgba(255,252,245,.6) inset, 0 2px 4px rgba(42,32,20,.18);
    --shadow-deep: 0 1px 0 rgba(255,252,245,.5) inset, 0 4px 12px rgba(42,32,20,.22);
    --shadow-inset: inset 0 3px 6px rgba(42,32,20,.28);
}

* {
    box-sizing: border-box;
}

html {
    scroll-behavior: smooth;
    font-size: 18px;
}

body {
    font-family: var(--font);
    font-size: 1.25rem;
    line-height: 1.6;
    color: var(--text);
    background: var(--bg);
    margin: 0;
    padding: 0;
    font-weight: 500;
    overflow-x: hidden;
}

/* ---- Header: dark command band, raised against the page ---- */
.header {
    background: linear-gradient(180deg, var(--dark2), var(--dark));
    border-bottom: 4px solid var(--orange);
    padding: 36px 44px;
    max-width: 100%;
    overflow-x: hidden;
}

.header-content {
    width: min(96vw, var(--content-width));
    margin: 0 auto;
    overflow-wrap: anywhere;
}

.header h1 {
    margin: 0 0 12px 0;
    font-size: 3.4rem;
    font-weight: 800;
    color: #faf3e6;
    letter-spacing: -0.01em;
    text-transform: uppercase;
}

.header-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 32px;
    margin-top: 16px;
    font-size: 1.4rem;
    font-weight: 600;
    color: #e6d9c0;
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
    font-size: 1.05rem;
    color: #b8a780;
}

.container {
    width: min(96vw, var(--content-width));
    margin: 0 auto;
    padding: 36px 44px 8px;
}

section {
    margin-bottom: 48px;
}

h2 {
    margin: 0 0 24px 0;
    font-size: 2rem;
    font-weight: 800;
    color: var(--ink);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding-bottom: 14px;
    border-bottom: 4px solid var(--dark);
}

h3 {
    margin: 30px 0 18px 0;
    font-size: 1.7rem;
    font-weight: 700;
    color: var(--ink);
}

h4 {
    margin: 0 0 6px 0;
    font-size: 1.55rem;
    font-weight: 700;
    color: var(--ink);
    letter-spacing: 0.01em;
    overflow-wrap: anywhere;
    word-break: break-word;
}

p {
    margin: 8px 0;
    color: var(--text);
}

.text-muted {
    color: var(--muted);
    font-style: italic;
    margin: 12px 0;
    font-size: 1.2rem;
}

/* ---- KPI strip: tactile raised cells on an inset rail, equal-height rows ---- */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    grid-auto-rows: 1fr;
    align-items: stretch;
    gap: 4px;
    margin: 0 0 8px 0;
    background: var(--panel2);
    padding: 4px;
    border: 4px solid var(--line2);
    box-shadow: var(--shadow-inset);
}

.kpi-box {
    display: flex;
    flex-direction: column;
    background: linear-gradient(180deg, #fffdf8, var(--card));
    border: 1px solid var(--line);
    border-top: 1px solid #fffdf8;
    box-shadow: var(--shadow);
    padding: 22px 24px;
}

.kpi-label {
    font-family: var(--mono);
    font-size: 1.05rem;
    color: var(--muted);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-bottom: 14px;
}

.kpi-value {
    font-size: 3.6rem;
    font-weight: 800;
    color: var(--ink);
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.01em;
    line-height: 1;
}

.kpi-value.success { color: var(--green); }
.kpi-value.error { color: var(--red); }
.kpi-value.warn { color: var(--amber); }
.kpi-value.alarm { color: var(--red); }
.kpi-value.ok { color: var(--green); }

.kpi-desc {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--muted);
    margin-top: 10px;
    min-height: 1.6em;
}

/* ---- Tables: paper surface, mono headers, large readable rows ---- */
table {
    border-collapse: collapse;
    width: 100%;
    margin: 0;
    font-size: 1.25rem;
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
    font-size: 1.05rem;
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
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--ink);
    line-height: 1.5;
}

.diag-line {
    display: block;
    font-family: var(--mono);
    font-size: 1.1rem;
    color: var(--muted);
    margin-top: 8px;
    line-height: 1.5;
}

/* ---- Card frame: raised panel, thick border, layered shadow ---- */
.card {
    background: var(--card);
    border: 4px solid var(--line2);
    box-shadow: var(--shadow-deep);
    padding: 0;
    margin: 0 0 24px 0;
    overflow-x: auto;
    overflow-y: visible;
}

.card > table {
    margin: 0;
}

/* ---- Diagnostic block: labelled inset panel ---- */
.diag-box {
    background: var(--panel);
    border: 1px solid var(--line);
    box-shadow: var(--shadow-inset);
    padding: 16px 20px;
    font-size: 1.2rem;
    font-weight: 600;
    color: var(--text);
    line-height: 1.5;
}

.diag-label {
    display: block;
    font-family: var(--mono);
    font-size: 1rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--orange);
    margin-bottom: 8px;
}

/* tidy key:value rows inside a diag-box (tuning diagnostics, armed heads) -
   replaces a single dense comma-joined paragraph with a scannable list */
.diag-kv-list {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 4px 16px;
    margin-top: 4px;
    font-family: var(--mono);
    font-size: 1.05rem;
}

.diag-kv-list dt {
    color: var(--soft);
    font-weight: 700;
}

.diag-kv-list dd {
    margin: 0;
    color: var(--text);
}

/* ---- Status pills: tactile, filled, semantic ---- */
.badge {
    display: inline-block;
    padding: 8px 16px;
    font-size: 1.05rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-family: var(--mono);
    border: 1px solid rgba(42,32,20,.25);
    box-shadow: 0 1px 0 rgba(255,255,255,.3) inset, 0 1px 2px rgba(42,32,20,.2);
}

.badge-detected {
    background: var(--orange);
    color: #fdf3e6;
}

.badge-clean, .badge-ok {
    background: var(--green);
    color: #eef8ee;
}

.badge-missed, .badge-alarm {
    background: var(--red);
    color: #fbeceb;
}

.badge-false_alarm, .badge-false-alarm {
    background: var(--amber);
    color: #fbf2dc;
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

.chart-container {
    width: 100%;
    margin: 12px 0 0;
    border: 1px solid var(--line);
    background: var(--paper);
}

.chart-note {
    margin: 4px 0 0;
    font-family: var(--mono);
    font-size: 0.98rem;
    color: var(--muted);
}

.asset-card-grid {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.asset-card-chart, .asset-card-diag {
    width: 100%;
    min-width: 0;
}

.asset-card-chart {
    overflow-x: auto;
}

.asset-card-diag {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
    gap: 16px;
    align-items: start;
}

.asset-card-diag > .diag-box:first-child,
.asset-card-diag > .mini-table:first-child {
    margin-top: 0;
}

/* ---- Compact in-card tables (alarm history, detector stats) ---- */
.mini-table {
    width: 100%;
    margin: 0;
    font-size: 1.05rem;
    background: var(--paper);
    border: 1px solid var(--line);
    overflow: hidden;
}

.mini-table td, .mini-table th {
    padding: 8px 12px;
}

.mini-table th {
    font-size: 0.95rem;
}

/* ---- Logs ---- */
.logs-section {
    display: flex;
    flex-direction: column;
    gap: 1px;
    border: 4px solid var(--line2);
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
    font-size: 1.25rem;
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
    font-size: 1.1rem;
    color: var(--muted);
    font-weight: 500;
    margin-left: 10px;
}

.logs-section pre {
    margin: 0;
    padding: 18px 20px 20px;
    background: var(--dark3);
    border-top: 1px solid var(--darkLine);
    font-size: 1.05rem;
    line-height: 1.6;
    overflow-x: auto;
    font-family: var(--mono);
    white-space: pre-wrap;
    color: #f0e6d2;
}

/* log levels - warm palette tones against the dark log pane */
.logs-section .info { color: #7fb8d8; }
.logs-section .warning { color: #e0b558; font-weight: 700; }
.logs-section .error { color: #e08a78; font-weight: 700; }
.logs-section .debug { color: #b8a780; }

.timestamp {
    font-family: var(--mono);
    font-size: 1.15rem;
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
    border-top: 4px solid var(--dark);
    background: var(--paper);
    padding: 24px 44px;
    margin-top: 16px;
    max-width: 100%;
    overflow-x: hidden;
}

.footer-content {
    width: min(96vw, var(--content-width));
    margin: 0 auto;
    overflow-wrap: anywhere;
}

.footer p {
    margin: 0;
    font-size: 1.1rem;
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
        font-size: 1.6rem;
    }

    .kpi-value {
        font-size: 2.6rem;
    }

    .asset-card-diag {
        grid-template-columns: minmax(0, 1fr);
    }

    .diag-box, .chart-note {
        overflow-wrap: anywhere;
    }

    .mini-table {
        display: block;
        overflow-x: auto;
    }

    table {
        font-size: 1.1rem;
    }

    td, th {
        padding: 11px 13px;
    }
}

@media (max-width: 480px) {
    .kpi-grid {
        grid-template-columns: 1fr;
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
    if dq.get("duplicate_ts") is not None:
        parts.append(f"{dq['duplicate_ts']} duplicate timestamps")
    if dq.get("cadence_s"):
        cadence = dq["cadence_s"]
        parts.append(f"{cadence / 60:.2f}-min cadence" if cadence >= 60 else f"{cadence:.2f}s cadence")
    return ", ".join(parts) if parts else None


def format_calibration_human(calib_json: Optional[str]) -> Optional[tuple[str, dict[str, str]]]:
    """Convert a run's calibration_json (fusion weights) into a short summary
    line plus a key/value dict of auto-tune diagnostics, so the caller can
    render the tuning internals as a scannable list instead of one dense
    comma-joined paragraph. Numeric values are rounded to readable precision
    (raw floats from the tuner can run 15+ decimal places)."""
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
    summary = f"Fusion weights ({tuned}): " + ", ".join(parts)

    tuning_kv: dict[str, str] = {}
    tuning = calib.get("tuning")
    if isinstance(tuning, dict):
        for k, v in tuning.items():
            if not isinstance(v, (int, float, str, bool)):
                continue
            label = k.replace("_", " ")
            if isinstance(v, float):
                tuning_kv[label] = f"{v:.3g}"
            else:
                tuning_kv[label] = str(v)
    return summary, tuning_kv


def format_culprits_human(notes: Optional[str]) -> Optional[str]:
    """Convert a run's notes field (e.g. "culprits: ch1, ch2, ch3") into one human-readable line."""
    if not notes or pd.isna(notes):
        return None
    notes = str(notes).strip()
    m = re.match(r"culprits:\s*(.+)", notes, re.IGNORECASE)
    if not m:
        return None
    culprits = [c.strip() for c in m.group(1).split(",") if c.strip()]
    if not culprits:
        return None
    labeled = [detector_label(c) for c in culprits]
    return "Culprit sensors: " + ", ".join(labeled)


def format_verdict_badge(verdict: Optional[str]) -> str:
    """Return HTML badge for verdict."""
    if pd.isna(verdict):
        verdict = "UNKNOWN"
    verdict_clean = str(verdict).upper().strip()
    # Always create a semantic badge class (badge-{verdict}), whether or not it's in VERDICT_COLOR.
    # This ensures unknown verdicts still get a styled badge, and the CSS fallback applies only
    # to verdicts that have no semantic class at all (shouldn't happen in normal usage).
    badge_class = f"badge-{verdict_clean.lower()}"
    return f"<span class='badge {badge_class}'>{html.escape(verdict_clean)}</span>"


def finite_number_list(values: pd.Series) -> list[Optional[float]]:
    """Return JSON-safe numeric values without changing finite data."""
    out: list[Optional[float]] = []
    for v in pd.to_numeric(values, errors="coerce").to_numpy(dtype=float):
        out.append(float(v) if np.isfinite(v) else None)
    return out


def asset_figure_spec(s: pd.DataFrame, meta: pd.Series) -> tuple[dict, str]:
    """
    Build a Plotly figure spec (as a plain dict, JSON-embedded into the page)
    for one asset: fused-score timeline with threshold and alarm shading on
    top, a per-detector z heatmap below. Each detector is also drawn as its
    own toggleable line trace (hidden by default) so the legend can be used
    to isolate individual heads on top of the heatmap - addressing the need
    to inspect specific detectors interactively rather than only as a static
    stacked image.
    Returns: (figure_spec_dict, data_quality_text)
    """
    ts = pd.to_datetime(s["ts"])
    ts_list = ts.dt.strftime("%Y-%m-%dT%H:%M:%S").tolist()

    data_rows = len(s)
    data_nans = s[Z_COLS].isna().sum().sum() / (len(s) * len(Z_COLS)) * 100 if len(s) > 0 else 0

    fused = pd.to_numeric(s["fused"], errors="coerce")
    traces = []

    # Fused score line (row 1)
    traces.append({
        "type": "scattergl", "mode": "lines", "name": "Fused",
        "x": ts_list, "y": finite_number_list(fused),
        "line": {"color": "#b3551e", "width": 1.6},
        "xaxis": "x", "yaxis": "y", "legendgroup": "fused",
        "hovertemplate": "Time: %{x}<br>Fused Z: %{y:.2f}<extra>Fused</extra>",
    })

    # Alert threshold (row 1)
    thr = meta.get("alert_z")
    if pd.notna(thr):
        traces.append({
            "type": "scattergl", "mode": "lines", "name": f"Alert Z {thr:.2f}",
            "x": [ts_list[0], ts_list[-1]], "y": [float(thr), float(thr)],
            "line": {"color": "#2f6f8f", "width": 1.6, "dash": "dash"},
            "xaxis": "x", "yaxis": "y",
            "hovertemplate": "Time: %{x}<br>Alert Z: %{y:.2f}<extra>Threshold</extra>",
        })

    # Alarm shading (row 1) - bottom follows the data's own minimum instead
    # of a hardcoded 0, so shading never clips below negative fused values.
    alarm = s["alarm"].fillna(0).to_numpy().astype(bool) if "alarm" in s.columns else np.zeros(len(s), dtype=bool)
    if alarm.any():
        fused_min = float(min(0.0, fused.min())) if fused.notna().any() else 0.0
        fused_max = float(fused.max()) * 1.1 if fused.notna().any() else 1.0
        # Build contiguous alarm-region shapes instead of per-point markers,
        # so the shading reads as bands rather than noise.
        regions = []
        start_idx = None
        for i, a in enumerate(alarm):
            if a and start_idx is None:
                start_idx = i
            elif not a and start_idx is not None:
                regions.append((start_idx, i - 1))
                start_idx = None
        if start_idx is not None:
            regions.append((start_idx, len(alarm) - 1))
        for k, (i0, i1) in enumerate(regions):
            traces.append({
                "type": "scatter", "mode": "lines", "fill": "toself",
                "name": "Alarm window", "showlegend": (k == 0),
                "legendgroup": "alarm",
                "x": [ts_list[i0], ts_list[i1], ts_list[i1], ts_list[i0]],
                "y": [fused_min, fused_min, fused_max, fused_max],
                "fillcolor": "rgba(168,52,43,0.16)",
                "line": {"width": 0},
                "hoverinfo": "skip",
                "xaxis": "x", "yaxis": "y",
            })

    # Per-detector heatmap (row 2) - the primary "see all heads at once" view
    zmat = [finite_number_list(s[z]) for z in Z_COLS]
    detector_labels = [detector_label(z) for z in Z_COLS]
    traces.append({
        "type": "heatmap", "name": "Detector heatmap",
        "x": ts_list, "y": detector_labels, "z": zmat,
        "zmin": 0, "zmax": 8,
        "colorscale": [[0, "#2a2118"], [0.5, "#c8762a"], [1, "#ffb347"]],
        "colorbar": {"title": {"text": "Detector Z", "font": {"size": 13}},
                     "tickfont": {"size": 12},
                     "len": 0.42, "y": 0.18, "thickness": 14},
        "xaxis": "x2", "yaxis": "y2",
        "hovertemplate": "Time: %{x}<br>Detector: %{y}<br>Z: %{z:.2f}<extra></extra>",
    })

    # Per-detector line traces (row 2 area, hidden by default) - clicking a
    # detector name in the legend shows/isolates that head's raw z-score
    # line over time, on its own y-axis range, answering the "select to see
    # the various heads" requirement without replacing the heatmap overview.
    for z in Z_COLS:
        det_name = detector_label(z)
        traces.append({
            "type": "scattergl", "mode": "lines", "name": det_name,
            "x": ts_list, "y": finite_number_list(s[z]),
            "line": {"color": DETECTOR_COLORS.get(z, "#8a5a16"), "width": 1.2},
            "xaxis": "x3", "yaxis": "y3",
            "visible": "legendonly",
            "legendgroup": "heads",
            "hovertemplate": f"Time: %{{x}}<br>{html.escape(det_name)} Z: %{{y:.2f}}<extra>{html.escape(det_name)}</extra>",
        })

    desc = meta.get("description") or meta.get("label") or ""
    title = f"{meta['asset_key']} (ID: {meta['asset_id']}) - {desc}" if desc else f"{meta['asset_key']} (ID: {meta['asset_id']})"

    layout = {
        "font": {"family": "Barlow Condensed, sans-serif", "size": 15, "color": "#332819"},
        "paper_bgcolor": "#f7f3ec",
        "plot_bgcolor": "#f7f3ec",
        "margin": {"l": 72, "r": 168, "t": 86, "b": 58},
        "showlegend": True,
        "legend": {
            "orientation": "v",
            "x": 1.02,
            "xanchor": "left",
            "y": 1.0,
            "yanchor": "top",
            "bgcolor": "rgba(247,243,236,0.96)",
            "bordercolor": "#c2b596",
            "borderwidth": 1,
            "font": {"size": 13},
            "title": {"text": "Series", "font": {"size": 13}},
            "tracegroupgap": 10,
        },
        "hovermode": "x unified",
        "hoverlabel": {"font": {"size": 12}},
        "uirevision": str(meta["asset_key"]),
        "annotations": [
            {"text": "Fused score", "xref": "paper", "yref": "paper", "x": 0,
             "y": 1.04, "xanchor": "left", "showarrow": False,
             "font": {"size": 15, "color": "#6b5c45"}},
            {"text": "Detector heatmap", "xref": "paper", "yref": "paper", "x": 0,
             "y": 0.43, "xanchor": "left", "showarrow": False,
             "font": {"size": 14, "color": "#6b5c45"}},
            {"text": "Detector line detail", "xref": "paper", "yref": "paper", "x": 0,
             "y": 0.22, "xanchor": "left", "showarrow": False,
             "font": {"size": 14, "color": "#6b5c45"}},
        ],
        # Row 1: fused timeline (55% height); Row 2: heatmap (20%);
        # Row 3: per-detector lines, hidden until a head is selected (25%).
        "xaxis": {"domain": [0, 1], "anchor": "y", "showticklabels": False,
                  "gridcolor": "#e0d6c0"},
        "yaxis": {"domain": [0.45, 1], "title": {"text": "Fused Z", "font": {"size": 15}},
                  "tickfont": {"size": 13}, "gridcolor": "#e0d6c0"},
        "xaxis2": {"domain": [0, 1], "anchor": "y2", "showticklabels": False, "matches": "x"},
        "yaxis2": {"domain": [0.25, 0.42], "title": {"text": "", "font": {"size": 12}},
                   "tickfont": {"size": 13}},
        "xaxis3": {"domain": [0, 1], "anchor": "y3", "matches": "x", "title": {"text": "Time", "font": {"size": 15}},
                   "tickfont": {"size": 13}, "gridcolor": "#e0d6c0"},
        "yaxis3": {"domain": [0, 0.2], "title": {"text": "Detector Z", "font": {"size": 14}},
                   "tickfont": {"size": 13}, "gridcolor": "#e0d6c0"},
    }

    spec = {"data": traces, "layout": layout}
    data_quality = f"Data: {data_rows} rows, {len(Z_COLS)} detectors, {data_nans:.2f}% missing"
    return spec, data_quality


def alarm_history_table(alarms_for_asset: Optional[pd.DataFrame]) -> str:
    """Render a compact alarm-episode history table for one asset, or '' if it has none."""
    if alarms_for_asset is None or alarms_for_asset.empty:
        return ""
    rows = []
    for a in alarms_for_asset.itertuples():
        dur = f"{a.duration_h:.2f}h" if pd.notna(a.duration_h) else "-"
        peak = f"{a.peak_fused:.2f}" if pd.notna(a.peak_fused) else "-"
        if pd.notna(getattr(a, "ack_by", None)):
            ack = f"Acknowledged by {html.escape(str(a.ack_by))} at {html.escape(str(a.ack_at or ''))}"
            if pd.notna(getattr(a, "ack_note", None)) and a.ack_note:
                ack += f" - {html.escape(str(a.ack_note))}"
        else:
            ack = "Unacknowledged"
        rows.append(
            f"<tr><td class='timestamp'>{html.escape(str(a.start_ts or ''))}</td>"
            f"<td class='timestamp'>{html.escape(str(a.end_ts or ''))}</td>"
            f"<td>{dur}</td><td>{peak}</td><td>{ack}</td></tr>")
    return (
        "<div class='diag-box'><span class='diag-label'>Alarm History</span>"
        "<table class='mini-table'><thead><tr>"
        "<th>Start</th><th>End</th><th>Duration</th><th>Peak Score</th><th>Acknowledgment</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")


def detector_stats_table(s: pd.DataFrame) -> str:
    """Render peak/mean z-score per detector, overall and restricted to alarm-window rows
    (when the asset has any alarm rows)."""
    has_alarm = "alarm" in s.columns and s["alarm"].fillna(0).astype(bool).any()
    alarm_mask = s["alarm"].fillna(0).astype(bool) if has_alarm else None
    rows = []
    for z in Z_COLS:
        vals = pd.to_numeric(s[z], errors="coerce")
        peak_str = f"{vals.max():.2f}" if vals.notna().any() else "-"
        mean_str = f"{vals.mean():.2f}" if vals.notna().any() else "-"
        if has_alarm:
            a_vals = vals[alarm_mask]
            a_peak_str = f"{a_vals.max():.2f}" if a_vals.notna().any() else "-"
            a_mean_str = f"{a_vals.mean():.2f}" if a_vals.notna().any() else "-"
            rows.append(f"<tr><td>{detector_label(z)}</td><td>{peak_str}</td><td>{mean_str}</td>"
                       f"<td>{a_peak_str}</td><td>{a_mean_str}</td></tr>")
        else:
            rows.append(f"<tr><td>{detector_label(z)}</td><td>{peak_str}</td><td>{mean_str}</td></tr>")
    header = ("<th>Detector</th><th>Peak</th><th>Mean</th><th>Alarm-window Peak</th><th>Alarm-window Mean</th>"
              if has_alarm else "<th>Detector</th><th>Peak</th><th>Mean</th>")
    return (
        "<div class='diag-box'><span class='diag-label'>Detector Z-Scores</span>"
        "<table class='mini-table'><thead><tr>" + header + "</tr></thead><tbody>"
        + "".join(rows) + "</tbody></table></div>")


def build_report(con, prefix: str, out: Path, farm: Optional[str], picks: Optional[list[str]]) -> None:
    """Build HTML report from database."""
    assets = read_sql(con, f"SELECT * FROM {prefix}assets ORDER BY farm, label DESC, asset_id")
    assets = select_assets(assets, picks, farm)
    if assets.empty:
        print("No matching assets in store.")
        return

    # KPI metrics are derived strictly from the assets selected for THIS report
    # (never from the fleet-wide summary table) so a scoped report - one asset,
    # a handful of assets, a single farm - never bleeds in fleet-wide numbers.
    verdicts = assets["verdict"].fillna("UNKNOWN").astype(str).str.upper()
    kpi_metrics = {
        "total_assets": int(len(assets)),
        "alarm": int((verdicts == "ALARM").sum()),
        "ok": int((verdicts == "OK").sum()),
        "detected": int((verdicts == "DETECTED").sum()),
        "clean": int((verdicts == "CLEAN").sum()),
        "missed": int((verdicts == "MISSED").sum()),
        "false_alarms": int((verdicts == "FALSE_ALARM").sum()),
        "unknown": int((~verdicts.isin(["ALARM", "OK", "DETECTED", "CLEAN", "MISSED", "FALSE_ALARM"])).sum()),
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

    # Get alarm episode history
    alarms = read_sql(con, f"SELECT * FROM {prefix}alarms ORDER BY asset_key, start_ts")
    alarms = alarms[alarms["asset_key"].isin(assets["asset_key"])]
    alarms_by_asset = {k: g for k, g in alarms.groupby("asset_key")}

    # Build asset rows and figures
    rows_html = []
    figs_html = []
    chart_specs: dict[str, dict] = {}

    for _, meta in assets.iterrows():
        s = read_sql(con, f"SELECT * FROM {prefix}scores WHERE asset_key = ? ORDER BY ts",
                     (meta["asset_key"],))
        if s.empty:
            continue

        # Asset table row
        # Use .get() for safe access in case lead_h column doesn't exist (e.g., in CARE data)
        lead_h = meta.get("lead_h")
        lead = f"{lead_h:+.2f}h" if pd.notna(lead_h) else "-"
        rules_display = format_rules_human(meta.get("rules_fired"),
                                          meta.get("alert_z"),
                                          s["fused"].max() if len(s) > 0 else None)

        asset_id_val = meta.get("asset_id")
        if pd.notna(asset_id_val):
            # A nullable int column becomes float64 in pandas once it has
            # any nulls, so a clean integer id can arrive here as 1.0 -
            # display it as "1", not "1.0".
            asset_id_str = str(int(asset_id_val)) if float(asset_id_val).is_integer() else str(asset_id_val)
        else:
            asset_id_str = "-"
        rows_html.append(
            f"<tr>"
            f"<td><a href='#{html.escape(meta['asset_key'])}'><strong>{html.escape(meta['asset_key'])}</strong></a></td>"
            f"<td>{html.escape(asset_id_str)}</td>"
            f"<td>{html.escape(meta.get('label') or '')}</td>"
            f"<td>{html.escape(meta.get('description') or '')}</td>"
            f"<td>{format_verdict_badge(meta.get('verdict'))}</td>"
            f"<td>{lead}</td>"
            f"<td><span class='rules-text'>{html.escape(rules_display)}</span></td>"
            f"</tr>")

        # Asset timeline figure (interactive Plotly spec, rendered client-side)
        fig_spec, data_quality_fallback = asset_figure_spec(s, meta)
        chart_id = f"chart-{re.sub(r'[^a-zA-Z0-9_-]', '_', meta['asset_key'])}"
        chart_specs[chart_id] = fig_spec

        run_row = latest_runs.loc[meta["asset_key"]] if meta["asset_key"] in latest_runs.index else None
        data_quality = (format_data_quality_human(run_row.get("data_quality_json")) if run_row is not None else None) \
            or data_quality_fallback
        calibration = format_calibration_human(run_row.get("calibration_json")) if run_row is not None else None
        culprits = format_culprits_human(run_row.get("notes")) if run_row is not None else None

        diag_boxes = f"<div class='diag-box'><span class='diag-label'>Data Quality</span>{html.escape(data_quality)}</div>"
        if calibration:
            calib_summary, tuning_kv = calibration
            calib_html = html.escape(calib_summary)
            if tuning_kv:
                kv_items = "".join(
                    f"<dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>"
                    for k, v in tuning_kv.items())
                calib_html += f"<dl class='diag-kv-list'>{kv_items}</dl>"
            diag_boxes += f"<div class='diag-box'><span class='diag-label'>Calibration</span>{calib_html}</div>"
        if culprits:
            diag_boxes += f"<div class='diag-box'><span class='diag-label'>Culprits</span>{html.escape(culprits)}</div>"
        diag_boxes += detector_stats_table(s)
        diag_boxes += alarm_history_table(alarms_by_asset.get(meta["asset_key"]))

        figs_html.append(
            f"<div class='card' id='{html.escape(meta['asset_key'])}'>"
            f"<h4>{html.escape(meta['asset_key'])}</h4>"
            f"<div class='asset-card-grid'>"
            f"<div class='asset-card-chart'>"
            f"<div class='chart-container' id='{chart_id}' style='height:760px;'></div>"
            f"<p class='chart-note'>Chart values use raw ACM score rows; visible labels round to 2 decimals.</p>"
            f"</div>"
            f"<div class='asset-card-diag'>{diag_boxes}</div>"
            f"</div>"
            f"</div>")

    # Build operations table
    ops_rows = []
    for r in runs.itertuples():
        alert_z_str = f"{r.alert_z:.2f}" if pd.notna(r.alert_z) else "-"
        duration_str = f"{r.duration_s:.2f}s" if pd.notna(r.duration_s) else "-"
        rules_exp = format_rules_human(r.rules_fired, r.alert_z, None)

        # Parse diagnostics if available. Per-detector thresholds are rounded
        # to 3 significant figures - the raw tuner output runs 15+ decimal
        # places, which reads as noise rather than information.
        diag_html = ""
        if pd.notna(r.rules_diagnostic_json):
            try:
                diag = json.loads(r.rules_diagnostic_json)
            except (json.JSONDecodeError, TypeError):
                diag = None
            if isinstance(diag, dict):
                for rule_name, rule_info in diag.items():
                    if rule_name == "per_head" and isinstance(rule_info, dict):
                        # per_head is a nested dict of detector_name -> {active, train_n, thr},
                        # not a single rule_info dict - render one line per detector.
                        for det_name, det_info in rule_info.items():
                            if not isinstance(det_info, dict):
                                continue
                            train_n = det_info.get("train_n", "?")
                            if det_info.get("active"):
                                thr = det_info.get("thr")
                                thr_str = f"{thr:.3g}" if isinstance(thr, (int, float)) else "?"
                                diag_html += f"<div class='diag-line'>{html.escape(detector_label(det_name))}: armed (n={train_n}, thr={thr_str})</div>"
                            else:
                                diag_html += f"<div class='diag-line'>{html.escape(detector_label(det_name))}: disarmed (n={train_n})</div>"
                    elif isinstance(rule_info, dict):
                        if rule_info.get("active"):
                            train_n = rule_info.get("train_n", "?")
                            thr = rule_info.get("thr")
                            thr_str = f"{thr:.3g}" if isinstance(thr, (int, float)) else "?"
                            diag_html += f"<div class='diag-line'>{html.escape(rule_name)}: armed (n={train_n}, thr={thr_str})</div>"
                        else:
                            train_n = rule_info.get("train_n", "?")
                            diag_html += f"<div class='diag-line'>{html.escape(rule_name)}: disarmed (n={train_n})</div>"

        data_quality_line = format_data_quality_human(getattr(r, "data_quality_json", None))
        calibration = format_calibration_human(getattr(r, "calibration_json", None))
        culprits_line = format_culprits_human(getattr(r, "notes", None))
        if data_quality_line:
            diag_html += f"<div class='diag-line'>Data: {html.escape(data_quality_line)}</div>"
        if calibration:
            calib_summary, tuning_kv = calibration
            diag_html += f"<div class='diag-line'>{html.escape(calib_summary)}</div>"
            if tuning_kv:
                kv_items = "".join(
                    f"<dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>"
                    for k, v in tuning_kv.items())
                diag_html += f"<dl class='diag-kv-list'>{kv_items}</dl>"
        if culprits_line:
            diag_html += f"<div class='diag-line'>{html.escape(culprits_line)}</div>"

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

        lines_html = ""
        for stage, stage_grp in grp.groupby("stage", sort=False):
            lines_html += "".join(
                f"<div class='{escape_and_format_log(str(l.level).lower())}'>"
                f"<strong>[{escape_and_format_log(l.stage)}]</strong> {escape_and_format_log(l.message)}"
                f"</div>"
                for l in stage_grp.itertuples())

        log_html += (
            f"<details>"
            f"<summary>{html.escape(key)} - <span class='log-summary'>{level_str}</span></summary>"
            f"<pre>{lines_html}</pre>"
            f"</details>")

    # KPI section - always derived from `assets` above, so this is exact for
    # whatever scope (single asset / a handful / a farm / the whole fleet) was requested.
    total = kpi_metrics["total_assets"]
    def kpi_box(label: str, value: int, klass: str = "", desc: str = "") -> str:
        klass_attr = f" {klass}" if klass else ""
        desc_html = f"<div class='kpi-desc'>{html.escape(desc)}</div>" if desc else ""
        return (
            "<div class='kpi-box'>"
            f"<div class='kpi-label'>{html.escape(label)}</div>"
            f"<div class='kpi-value{klass_attr}'>{value}</div>"
            f"{desc_html}"
            "</div>"
        )

    care_total = (
        kpi_metrics["detected"] + kpi_metrics["clean"] +
        kpi_metrics["missed"] + kpi_metrics["false_alarms"]
    )
    acm_total = kpi_metrics["alarm"] + kpi_metrics["ok"]
    if acm_total and not care_total:
        kpi_cards = [
            kpi_box("Assets in Scope", total),
            kpi_box("Assets in Alarm", kpi_metrics["alarm"], "alarm", "ACM verdict = ALARM"),
            kpi_box("Assets OK", kpi_metrics["ok"], "ok", "ACM verdict = OK"),
        ]
    else:
        kpi_cards = [
            kpi_box("Assets in Scope", total),
            kpi_box("Detected", kpi_metrics["detected"], "success", "Confirmed anomaly, flagged"),
            kpi_box("Clean", kpi_metrics["clean"], "success", "No anomaly, no flag"),
            kpi_box("Missed", kpi_metrics["missed"], "error", "Confirmed anomaly, not flagged"),
            kpi_box("False Alarms", kpi_metrics["false_alarms"], "warn", "Flagged, no confirmed anomaly"),
        ]
    if kpi_metrics["unknown"]:
        kpi_cards.append(kpi_box("Unknown", kpi_metrics["unknown"], "warn", "Unmapped verdict"))

    kpi_html = "<div class='kpi-grid'>" + "".join(kpi_cards) + "</div>"

    scope = f"farm {farm}" if farm else (f"{len(assets)} selected assets" if picks else "fleet")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    chart_specs_json = json.dumps(chart_specs)

    html_content = f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ACM Condition Monitor Report - {html.escape(scope)}</title>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
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
            <p class='text-muted'>Legend controls show or hide visual layers. Numeric chart values come from stored ACM score rows and are only rounded in visible labels.</p>
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
                Data from canonical SQL results store - {html.escape(timestamp)}
            </p>
        </div>
    </div>

    <script>
    (function() {{
        var specs = {chart_specs_json};
        var config = {{responsive: true, displaylogo: false,
                       modeBarButtonsToRemove: ['lasso2d', 'select2d']}};
        function layoutForWidth(baseLayout, width) {{
            var layout = JSON.parse(JSON.stringify(baseLayout));
            if (width < 760) {{
                layout.margin = {{l: 54, r: 18, t: 82, b: 140}};
                layout.legend = Object.assign({{}}, layout.legend, {{
                    orientation: 'h',
                    x: 0,
                    xanchor: 'left',
                    y: -0.24,
                    yanchor: 'top',
                    title: {{text: ''}},
                    tracegroupgap: 4,
                    itemwidth: 76
                }});
                layout.font = Object.assign({{}}, layout.font, {{size: 11}});
                if (layout.colorbar) layout.colorbar = Object.assign({{}}, layout.colorbar, {{thickness: 10}});
            }}
            return layout;
        }}

        Object.keys(specs).forEach(function(chartId) {{
            var el = document.getElementById(chartId);
            if (!el) return;
            var spec = specs[chartId];
            Plotly.newPlot(el, spec.data, layoutForWidth(spec.layout, el.clientWidth), config);
            window.addEventListener('resize', function() {{
                Plotly.relayout(el, layoutForWidth(spec.layout, el.clientWidth));
            }});
        }});
    }})();
    </script>
</body>
</html>"""

    out.write_text(html_content, encoding="utf-8")
    print(f"Report written: {out} ({len(figs_html)} assets, {out.stat().st_size/1e6:.2f} MB)")


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
