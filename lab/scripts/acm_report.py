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

ROOT = Path(__file__).resolve().parents[1]
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

# Detector line palettes for the interactive detail panel. The default uses
# strong hue separation so selected detector lines do not collapse into one
# orange/brown bundle.
DETECTOR_PALETTES = {
    "contrast": {
        "ar1_z": "#1f77b4",
        "pca_spe_z": "#ff7f0e",
        "pca_t2_z": "#9467bd",
        "iforest_z": "#2ca02c",
        "gmm_z": "#d62728",
        "omr_z": "#17becf",
    },
    "industrial": {
        "ar1_z": "#b3551e",
        "pca_spe_z": "#2f6f8f",
        "pca_t2_z": "#6e5490",
        "iforest_z": "#3d7a3f",
        "gmm_z": "#a8342b",
        "omr_z": "#a8791f",
    },
    "cool": {
        "ar1_z": "#2563eb",
        "pca_spe_z": "#0891b2",
        "pca_t2_z": "#7c3aed",
        "iforest_z": "#059669",
        "gmm_z": "#db2777",
        "omr_z": "#475569",
    },
    "signal": {
        "ar1_z": "#005f73",
        "pca_spe_z": "#ee9b00",
        "pca_t2_z": "#9b2226",
        "iforest_z": "#0a9396",
        "gmm_z": "#ca6702",
        "omr_z": "#6a4c93",
    },
}

DETECTOR_COLORS = DETECTOR_PALETTES["contrast"]

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
    padding: 20px 44px;
    max-width: 100%;
    overflow-x: hidden;
}

.header-content {
    width: min(96vw, var(--content-width));
    margin: 0 auto;
    overflow-wrap: anywhere;
}

.header h1 {
    margin: 0 0 6px 0;
    font-size: 2.7rem;
    font-weight: 800;
    color: #faf3e6;
    letter-spacing: -0.01em;
    text-transform: uppercase;
}

.header-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 22px;
    margin-top: 8px;
    font-size: 1.18rem;
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
    font-size: 0.95rem;
    color: #b8a780;
}

.container {
    width: min(96vw, var(--content-width));
    margin: 0 auto;
    padding: 26px 44px 8px;
}

section {
    margin-bottom: 34px;
}

h2 {
    margin: 0 0 16px 0;
    font-size: 1.85rem;
    font-weight: 800;
    color: var(--ink);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding-bottom: 10px;
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
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
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
    padding: 14px 18px;
}

.kpi-label {
    font-family: var(--mono);
    font-size: 0.98rem;
    color: var(--muted);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-bottom: 8px;
}

.kpi-value {
    font-size: 2.8rem;
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
    font-size: 1rem;
    font-weight: 600;
    color: var(--muted);
    margin-top: 6px;
    min-height: 0;
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
    padding: 14px 18px;
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
    font-size: 1.22rem;
    letter-spacing: 0.04em;
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
    overflow: hidden;
}

.card > table {
    margin: 0;
}

.table-card {
    overflow-x: auto;
    overflow-y: visible;
}

.ops-table {
    table-layout: fixed;
}

.ops-table th:nth-child(1),
.ops-table td:nth-child(1) { width: 26%; }
.ops-table th:nth-child(2),
.ops-table td:nth-child(2) { width: 20%; }
.ops-table th:nth-child(3),
.ops-table td:nth-child(3) { width: 11%; }
.ops-table th:nth-child(4),
.ops-table td:nth-child(4) { width: 9%; }
.ops-table th:nth-child(5),
.ops-table td:nth-child(5) { width: 8%; }
.ops-table th:nth-child(6),
.ops-table td:nth-child(6) { width: 26%; }

.ops-diag-row > td {
    padding: 0 18px 16px;
    background: var(--paper);
}

.ops-table .timestamp {
    white-space: normal;
    font-size: 1.08rem;
    line-height: 1.45;
}

.ops-table td {
    overflow-wrap: anywhere;
}

.timestamp .time-part {
    color: var(--muted);
}

.ops-table .rules-cell {
    overflow-wrap: anywhere;
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
    min-width: 0;
    overflow-wrap: anywhere;
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

.diag-details {
    margin-top: 10px;
    border-top: 1px solid var(--line);
    padding-top: 8px;
}

.diag-details summary {
    cursor: pointer;
    font-family: var(--mono);
    font-size: 0.98rem;
    color: var(--muted);
    font-weight: 700;
    text-transform: uppercase;
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

.chart-controls {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    margin: 10px 0 0;
    font-family: var(--mono);
}

.chart-control-label {
    color: var(--muted);
    font-size: 0.98rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}

.palette-btn {
    border: 1px solid var(--line2);
    background: var(--panel);
    color: var(--text);
    padding: 5px 10px;
    font-family: var(--mono);
    font-size: 0.95rem;
    font-weight: 700;
    text-transform: uppercase;
    cursor: pointer;
    box-shadow: var(--shadow);
}

.palette-btn.active {
    background: var(--dark);
    color: #faf3e6;
    border-color: var(--orange);
}

.palette-swatches {
    display: inline-flex;
    gap: 2px;
    margin-left: 6px;
    vertical-align: middle;
}

.palette-swatch {
    display: inline-block;
    width: 10px;
    height: 10px;
    border: 1px solid rgba(42,32,20,.22);
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

.asset-card-diag {
    display: grid;
    grid-template-columns: repeat(12, minmax(0, 1fr));
    gap: 16px;
    align-items: start;
}

.asset-card-diag > .diag-box {
    grid-column: 1 / -1;
}

.diag-summary,
.diag-calibration,
.diag-culprits {
    grid-column: 1 / -1;
}

.diag-detectors {
    grid-column: 1 / -1;
}

.diag-history {
    grid-column: 1 / -1;
}

.diag-score,
.diag-validation {
    grid-column: 1 / -1;
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
    table-layout: auto;
}

.mini-table td, .mini-table th {
    padding: 8px 12px;
    white-space: nowrap;
}

.mini-table th {
    font-size: 0.95rem;
}

.mini-table-scroll {
    width: 100%;
    max-width: 100%;
    overflow-x: auto;
    overflow-y: visible;
}

.diag-detectors .mini-table {
    min-width: 620px;
}

.diag-history .mini-table {
    min-width: 860px;
}

.diag-validation .mini-table {
    min-width: 980px;
}

.event-hit {
    color: var(--green);
    font-weight: 800;
}

.event-missed {
    color: var(--red);
    font-weight: 800;
}

.event-outside {
    color: var(--muted);
    font-weight: 700;
}

.diag-history .timestamp {
    font-size: 0.95rem;
}

.diag-history .ack-cell {
    min-width: 160px;
    white-space: normal;
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

.op-details {
    margin-top: 10px;
    border-top: 1px solid var(--line);
    padding-top: 8px;
}

.op-details summary {
    cursor: pointer;
    font-family: var(--mono);
    font-size: 1.08rem;
    color: var(--muted);
    font-weight: 700;
    text-transform: uppercase;
}

.op-diag-stack {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px 14px;
    margin-top: 10px;
}

.op-diag-section {
    border: 1px solid var(--line);
    background: var(--paper);
}

.op-diag-section.wide {
    grid-column: 1 / -1;
}

.op-diag-title {
    padding: 7px 10px;
    background: var(--panel);
    border-bottom: 1px solid var(--line);
    font-family: var(--mono);
    font-size: 0.98rem;
    font-weight: 700;
    color: var(--orange);
    text-transform: uppercase;
    letter-spacing: 0.06em;
}

.op-diag-table {
    width: 100%;
    margin: 0;
    border: 0;
    font-size: 1.02rem;
}

.op-diag-table td,
.op-diag-table th {
    padding: 6px 10px;
    border-bottom: 1px solid rgba(194,181,150,.55);
}

.op-diag-table th {
    font-size: 0.98rem;
}

.op-diag-table tr:last-child td {
    border-bottom: none;
}

.op-diag-key {
    width: 36%;
    color: var(--muted);
    font-family: var(--mono);
    font-weight: 700;
    text-transform: uppercase;
}

.op-diag-value {
    color: var(--text);
    overflow-wrap: anywhere;
}

.op-diag-status {
    font-weight: 800;
    text-transform: uppercase;
}

.op-diag-status.armed {
    color: var(--red);
}

.op-diag-status.disarmed {
    color: var(--muted);
}

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

    .diag-summary,
    .diag-calibration,
    .diag-culprits,
    .diag-detectors,
    .diag-history {
        grid-column: auto;
    }

    .diag-box, .chart-note {
        overflow-wrap: anywhere;
    }

    .mini-table-scroll {
        overflow-x: auto;
    }

    .op-diag-stack {
        grid-template-columns: minmax(0, 1fr);
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


def format_override_human(override_json: Optional[str]) -> Optional[str]:
    """Convert a run's override_json (the raw ablation --override CLI JSON, see
    scripts/acm_run.py) into one human-readable "dotted.path=value" summary line."""
    if not override_json or pd.isna(override_json):
        return None
    try:
        override = json.loads(override_json)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(override, dict) or not override:
        return None

    def _flatten(d: dict, prefix: str = "") -> list[str]:
        pairs = []
        for k, v in d.items():
            path = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                pairs.extend(_flatten(v, path))
            else:
                pairs.append(f"{path}={json.dumps(v)}")
        return pairs

    pairs = _flatten(override)
    return "Ablation override active: " + ", ".join(pairs) if pairs else None


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


def format_report_datetime(value: Any) -> str:
    """Render stored timestamps as readable report labels without changing source values."""
    if value is None or pd.isna(value):
        return "-"
    text = str(value).strip()
    if not text:
        return "-"
    try:
        ts = pd.to_datetime(text, errors="coerce")
    except (TypeError, ValueError):
        return text
    if pd.isna(ts):
        return text
    suffix = ""
    if getattr(ts, "tzinfo", None) is not None:
        try:
            ts = ts.tz_convert("UTC")
            suffix = " UTC"
        except (TypeError, ValueError):
            suffix = ""
    date_part = f"{ts.strftime('%b')} {ts.day}, {ts.year}"
    time_part = ts.strftime("%I:%M %p").lstrip("0")
    return f"{date_part} {time_part}{suffix}"


def format_report_datetime_cell(value: Any) -> str:
    """Render a human datetime as two lines for narrow table cells."""
    text = format_report_datetime(value)
    parts = text.split(" ")
    if len(parts) >= 5 and parts[1].endswith(","):
        date_part = " ".join(parts[:3])
        time_part = " ".join(parts[3:])
        return f"{html.escape(date_part)}<br><span class='time-part'>{html.escape(time_part)}</span>"
    return html.escape(text)


def format_diag_number(value: Any, digits: int = 3) -> str:
    """Display diagnostic floats compactly without changing stored values."""
    if isinstance(value, (int, float)) and np.isfinite(float(value)):
        if digits == 0:
            return f"{float(value):.0f}"
        return f"{float(value):.{digits}g}"
    if value is None or pd.isna(value):
        return "-"
    return str(value)


def render_key_value_section(title: str, rows: list[tuple[str, str]], wide: bool = False) -> str:
    """Render compact diagnostic key/value rows."""
    if not rows:
        return ""
    cls = "op-diag-section wide" if wide else "op-diag-section"
    body = "".join(
        "<tr>"
        f"<td class='op-diag-key'>{html.escape(str(k))}</td>"
        f"<td class='op-diag-value'>{html.escape(str(v))}</td>"
        "</tr>"
        for k, v in rows
    )
    return (
        f"<div class='{cls}'>"
        f"<div class='op-diag-title'>{html.escape(title)}</div>"
        f"<table class='op-diag-table'><tbody>{body}</tbody></table>"
        "</div>"
    )


def render_rule_diagnostics(rules_json: Any) -> str:
    """Render rule diagnostics as a compact status table."""
    if rules_json is None or pd.isna(rules_json):
        return ""
    try:
        diag = json.loads(rules_json)
    except (json.JSONDecodeError, TypeError):
        return ""
    if not isinstance(diag, dict):
        return ""

    rows = []
    for rule_name, rule_info in diag.items():
        if rule_name == "per_head" and isinstance(rule_info, dict):
            for det_name, det_info in rule_info.items():
                if not isinstance(det_info, dict):
                    continue
                status = "armed" if det_info.get("active") else "disarmed"
                rows.append((
                    detector_label(det_name),
                    status,
                    format_diag_number(det_info.get("train_n"), 0),
                    format_diag_number(det_info.get("thr")),
                ))
        elif isinstance(rule_info, dict):
            status = "armed" if rule_info.get("active") else "disarmed"
            rows.append((
                str(rule_name).replace("_", " ").title(),
                status,
                format_diag_number(rule_info.get("train_n"), 0),
                format_diag_number(rule_info.get("thr")),
            ))
    if not rows:
        return ""

    body = "".join(
        "<tr>"
        f"<td>{html.escape(name)}</td>"
        f"<td><span class='op-diag-status {html.escape(status)}'>{html.escape(status)}</span></td>"
        f"<td>{html.escape(train_n)}</td>"
        f"<td>{html.escape(thr)}</td>"
        "</tr>"
        for name, status, train_n, thr in rows
    )
    return (
        "<div class='op-diag-section wide'>"
        "<div class='op-diag-title'>Rule Arming</div>"
        "<table class='op-diag-table'>"
        "<thead><tr><th>Rule</th><th>Status</th><th>Train N</th><th>Threshold</th></tr></thead>"
        f"<tbody>{body}</tbody>"
        "</table></div>"
    )


def render_run_diagnostics(r: Any) -> str:
    """Render run diagnostics as structured report sections."""
    sections = []
    rule_section = render_rule_diagnostics(getattr(r, "rules_diagnostic_json", None))
    if rule_section:
        sections.append(rule_section)

    data_quality_line = format_data_quality_human(getattr(r, "data_quality_json", None))
    if data_quality_line:
        sections.append(render_key_value_section("Data Quality", [("Summary", data_quality_line)], wide=True))

    calibration = format_calibration_human(getattr(r, "calibration_json", None))
    if calibration:
        calib_summary, tuning_kv = calibration
        rows = [("Summary", calib_summary)]
        rows.extend((k.title(), v) for k, v in tuning_kv.items())
        sections.append(render_key_value_section("Calibration", rows, wide=True))

    override_line = format_override_human(getattr(r, "override_json", None))
    if override_line:
        sections.append(render_key_value_section("Ablation Override", [("Override", override_line)], wide=True))

    culprits_line = format_culprits_human(getattr(r, "notes", None))
    if culprits_line:
        sections.append(render_key_value_section("Culprits", [("Sensors", culprits_line)], wide=True))

    if not sections:
        return ""
    return (
        "<details class='op-details'>"
        "<summary>Run diagnostics</summary>"
        "<div class='op-diag-stack'>"
        + "".join(sections) +
        "</div></details>"
    )


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
                     "len": 0.34, "y": 0.42, "thickness": 14},
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
            "line": {"color": DETECTOR_COLORS.get(z, "#8a5a16"), "width": 1.6},
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
             "y": 0.52, "xanchor": "left", "showarrow": False,
             "font": {"size": 14, "color": "#6b5c45"}},
            {"text": "Detector line detail", "xref": "paper", "yref": "paper", "x": 0,
             "y": 0.34, "xanchor": "left", "showarrow": False,
             "font": {"size": 14, "color": "#6b5c45"}},
        ],
        # Row 1: fused timeline; Row 2: heatmap; Row 3: per-detector
        # lines, hidden until a head is selected. The detector detail panel
        # deliberately gets a larger share so selected detector lines remain
        # readable instead of huddled at the bottom of the chart.
        "xaxis": {"domain": [0, 1], "anchor": "y", "showticklabels": False,
                  "gridcolor": "#e0d6c0"},
        "yaxis": {"domain": [0.57, 1], "title": {"text": "Fused Z", "font": {"size": 15}},
                  "tickfont": {"size": 13}, "gridcolor": "#e0d6c0"},
        "xaxis2": {"domain": [0, 1], "anchor": "y2", "showticklabels": False, "matches": "x"},
        "yaxis2": {"domain": [0.38, 0.51], "title": {"text": "", "font": {"size": 12}},
                   "tickfont": {"size": 13}},
        "xaxis3": {"domain": [0, 1], "anchor": "y3", "matches": "x", "title": {"text": "Time", "font": {"size": 15}},
                   "tickfont": {"size": 13}, "gridcolor": "#e0d6c0"},
        "yaxis3": {"domain": [0, 0.32], "title": {"text": "Detector Z", "font": {"size": 14}},
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
            ack_time = format_report_datetime(getattr(a, "ack_at", None))
            ack = f"Acknowledged by {html.escape(str(a.ack_by))} at {html.escape(ack_time)}"
            if pd.notna(getattr(a, "ack_note", None)) and a.ack_note:
                ack += f" - {html.escape(str(a.ack_note))}"
        else:
            ack = "Unacknowledged"
        start_ts = format_report_datetime(getattr(a, "start_ts", None))
        end_ts = format_report_datetime(getattr(a, "end_ts", None))
        rows.append(
            f"<tr><td class='timestamp'>{html.escape(start_ts)}</td>"
            f"<td class='timestamp'>{html.escape(end_ts)}</td>"
            f"<td>{dur}</td><td>{peak}</td><td class='ack-cell'>{ack}</td></tr>")
    return (
        "<div class='diag-box diag-history'><span class='diag-label'>Alarm History</span>"
        "<div class='mini-table-scroll'><table class='mini-table'><thead><tr>"
        "<th>Start</th><th>End</th><th>Duration</th><th>Peak Score</th><th>Acknowledgment</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div></div>")


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
        "<div class='diag-box diag-detectors'><span class='diag-label'>Detector Z-Scores</span>"
        "<div class='mini-table-scroll'><table class='mini-table'><thead><tr>"
        + header + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div></div>")


def parse_mixed_datetime_series(values: pd.Series) -> pd.Series:
    """Parse mixed report/event timestamp strings without assuming one format."""
    try:
        return pd.to_datetime(values, format="mixed", errors="coerce")
    except TypeError:
        return pd.to_datetime(values, errors="coerce")


def intervals_overlap(a_start: Any, a_end: Any, b_start: Any, b_end: Any) -> bool:
    """True when two closed timestamp intervals overlap."""
    if pd.isna(a_start) or pd.isna(a_end) or pd.isna(b_start) or pd.isna(b_end):
        return False
    return max(a_start, b_start) <= min(a_end, b_end)


def infer_validation_dataset(asset_key: str) -> Optional[str]:
    """Map ACM asset keys/stems from public adapters back to validation dataset names."""
    key = str(asset_key).lower()
    for name in ("metropt3", "batadal", "cmapss", "milling", "secom", "ai4i", "bearing", "skab"):
        if name in key:
            return name
    if "smd_" in key or "smd-machine" in key or "smd_machine" in key:
        return "smd"
    if "machine-" in key and "smd" in key:
        return "smd"
    return None


def load_validation_events(root: Path = ROOT / "data" / "public_datasets" / "adapted") -> dict[str, pd.DataFrame]:
    """Load known event windows from adapted public datasets, if present."""
    events: dict[str, pd.DataFrame] = {}
    if not root.exists():
        return events
    for path in sorted(root.glob("*/known_events.csv")):
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        required = {"event_start", "event_end", "description"}
        if not required.issubset(df.columns):
            continue
        df = df.copy()
        df["event_start"] = parse_mixed_datetime_series(df["event_start"])
        df["event_end"] = parse_mixed_datetime_series(df["event_end"])
        df = df.dropna(subset=["event_start", "event_end"])
        df["dataset"] = path.parent.name
        df["source_file"] = str(path)
        events[path.parent.name] = df
    return events


def filter_events_for_asset(dataset: str, asset_key: str, events: pd.DataFrame) -> pd.DataFrame:
    """Restrict dataset event windows to the current asset when the adapter encodes asset identity."""
    if events.empty:
        return events
    key = str(asset_key)
    if dataset == "smd":
        machine_match = re.search(r"(machine-\d+-\d+)", key)
        if machine_match:
            machine = machine_match.group(1)
            return events[events["description"].astype(str).str.contains(machine, regex=False, na=False)].copy()
    if dataset == "cmapss":
        unit_match = re.search(r"unit0*(\d+)", key, flags=re.IGNORECASE)
        fd_match = re.search(r"(FD\d+)", key, flags=re.IGNORECASE)
        filtered = events
        if fd_match:
            filtered = filtered[filtered["description"].astype(str).str.contains(fd_match.group(1).upper(), regex=False, na=False)]
        if unit_match:
            token = f"unit {int(unit_match.group(1))}"
            filtered = filtered[filtered["description"].astype(str).str.contains(token, regex=False, na=False)]
        return filtered.copy()
    if dataset == "batadal" and "train1" in key.lower():
        return events[events["description"].astype(str).str.contains("train1", regex=False, na=False)].copy()
    return events.copy()


def score_coverage_box(s: pd.DataFrame, alarms_for_asset: Optional[pd.DataFrame]) -> str:
    """Render score/alarm counts and score distribution for one asset."""
    score_rows = len(s)
    alarm_rows = int(s["alarm"].fillna(0).astype(bool).sum()) if "alarm" in s.columns else 0
    alarm_rate = (alarm_rows / score_rows * 100.0) if score_rows else 0.0
    fused = pd.to_numeric(s["fused"], errors="coerce") if "fused" in s.columns else pd.Series(dtype=float)
    peak = f"{fused.max():.2f}" if fused.notna().any() else "-"
    mean = f"{fused.mean():.2f}" if fused.notna().any() else "-"
    p95 = f"{fused.quantile(0.95):.2f}" if fused.notna().any() else "-"
    ts = parse_mixed_datetime_series(s["ts"]) if "ts" in s.columns else pd.Series(dtype="datetime64[ns]")
    span = "-"
    if ts.notna().any():
        span = f"{format_report_datetime(ts.min())} to {format_report_datetime(ts.max())}"
    episode_count = 0
    alarm_hours = 0.0
    if alarms_for_asset is not None and not alarms_for_asset.empty:
        episode_count = int(len(alarms_for_asset))
        if "duration_h" in alarms_for_asset.columns:
            alarm_hours = float(pd.to_numeric(alarms_for_asset["duration_h"], errors="coerce").fillna(0).sum())
    rows = [
        ("Scored Rows", f"{score_rows:,}"),
        ("Alarm Rows", f"{alarm_rows:,} ({alarm_rate:.2f}%)"),
        ("Alarm Episodes", str(episode_count)),
        ("Alarm Episode Hours", f"{alarm_hours:.2f}"),
        ("Fused Peak / Mean / P95", f"{peak} / {mean} / {p95}"),
        ("Scored Span", span),
    ]
    body = "".join(
        f"<tr><td>{html.escape(k)}</td><td>{html.escape(v)}</td></tr>"
        for k, v in rows
    )
    return (
        "<div class='diag-box diag-score'><span class='diag-label'>Score Coverage</span>"
        "<div class='mini-table-scroll'><table class='mini-table'><tbody>"
        + body + "</tbody></table></div></div>"
    )


def validation_for_asset(
    asset_key: str,
    s: pd.DataFrame,
    alarms_for_asset: Optional[pd.DataFrame],
    validation_events: dict[str, pd.DataFrame],
) -> tuple[dict[str, Any], str]:
    """Compute known-event overlap evidence and render one asset validation box."""
    dataset = infer_validation_dataset(asset_key)
    base_summary: dict[str, Any] = {
        "asset_key": asset_key,
        "dataset": dataset,
        "known_total": 0,
        "events_in_span": 0,
        "events_hit": 0,
        "events_missed": 0,
        "alarm_episodes": 0,
        "alarm_episodes_without_event": 0,
        "alarm_hours": 0.0,
        "has_source": False,
    }
    if not dataset or dataset not in validation_events or s.empty or "ts" not in s.columns:
        return base_summary, ""

    events = filter_events_for_asset(dataset, asset_key, validation_events[dataset])
    base_summary["known_total"] = int(len(events))
    base_summary["has_source"] = True
    if events.empty:
        return base_summary, (
            "<div class='diag-box diag-validation'><span class='diag-label'>Known Event Match</span>"
            f"No known event rows matched asset {html.escape(asset_key)} in dataset {html.escape(dataset)}.</div>"
        )

    score_ts = parse_mixed_datetime_series(s["ts"])
    if not score_ts.notna().any():
        return base_summary, ""
    score_start, score_end = score_ts.min(), score_ts.max()

    alarm_ranges: list[tuple[Any, Any, float]] = []
    if alarms_for_asset is not None and not alarms_for_asset.empty:
        base_summary["alarm_episodes"] = int(len(alarms_for_asset))
        if "duration_h" in alarms_for_asset.columns:
            base_summary["alarm_hours"] = float(pd.to_numeric(alarms_for_asset["duration_h"], errors="coerce").fillna(0).sum())
        for a in alarms_for_asset.itertuples():
            alarm_ranges.append((pd.to_datetime(a.start_ts, errors="coerce"),
                                 pd.to_datetime(a.end_ts, errors="coerce"),
                                 float(a.peak_fused) if pd.notna(getattr(a, "peak_fused", None)) else float("nan")))

    event_rows = []
    event_hits: list[bool] = []
    for e in events.itertuples():
        in_span = intervals_overlap(score_start, score_end, e.event_start, e.event_end)
        if not in_span:
            event_rows.append((e, "outside", None, None))
            continue
        hit_alarm = None
        for a_start, a_end, a_peak in alarm_ranges:
            if intervals_overlap(a_start, a_end, e.event_start, e.event_end):
                hit_alarm = (a_start, a_end, a_peak)
                break
        event_hits.append(hit_alarm is not None)
        event_rows.append((e, "hit" if hit_alarm else "missed", hit_alarm, None))

    base_summary["events_in_span"] = int(len(event_hits))
    base_summary["events_hit"] = int(sum(event_hits))
    base_summary["events_missed"] = int(len(event_hits) - sum(event_hits))

    false_alarm_episodes = 0
    for a_start, a_end, _peak in alarm_ranges:
        any_event = any(intervals_overlap(a_start, a_end, e.event_start, e.event_end) for e in events.itertuples())
        if not any_event:
            false_alarm_episodes += 1
    base_summary["alarm_episodes_without_event"] = false_alarm_episodes

    summary = (
        f"Dataset {dataset}: {base_summary['events_hit']} hit, "
        f"{base_summary['events_missed']} missed, {base_summary['events_in_span']} known events in scored span, "
        f"{base_summary['known_total']} known events total for this asset."
    )
    rows = []
    for e, status, hit_alarm, _unused in event_rows:
        if status == "outside":
            status_label = "<span class='event-outside'>OUTSIDE SCORE WINDOW</span>"
            alarm_text = "-"
            lag_text = "-"
            peak_text = "-"
        elif status == "hit" and hit_alarm is not None:
            a_start, _a_end, peak = hit_alarm
            lag_h = (a_start - e.event_start).total_seconds() / 3600.0 if pd.notna(a_start) else float("nan")
            status_label = "<span class='event-hit'>HIT</span>"
            alarm_text = format_report_datetime(a_start)
            lag_text = f"{lag_h:+.2f}h" if np.isfinite(lag_h) else "-"
            peak_text = f"{peak:.2f}" if np.isfinite(peak) else "-"
        else:
            status_label = "<span class='event-missed'>MISSED</span>"
            alarm_text = "-"
            lag_text = "-"
            peak_text = "-"
        rows.append(
            "<tr>"
            f"<td>{status_label}</td>"
            f"<td class='timestamp'>{html.escape(format_report_datetime(e.event_start))}</td>"
            f"<td class='timestamp'>{html.escape(format_report_datetime(e.event_end))}</td>"
            f"<td>{html.escape(str(e.description))}</td>"
            f"<td class='timestamp'>{html.escape(alarm_text)}</td>"
            f"<td>{html.escape(lag_text)}</td>"
            f"<td>{html.escape(peak_text)}</td>"
            "</tr>"
        )
    return base_summary, (
        "<div class='diag-box diag-validation'><span class='diag-label'>Known Event Match</span>"
        f"{html.escape(summary)}"
        "<div class='mini-table-scroll'><table class='mini-table'><thead><tr>"
        "<th>Status</th><th>Event Start</th><th>Event End</th><th>Description</th>"
        "<th>First Alarm Start</th><th>Alarm Lag</th><th>Alarm Peak</th>"
        "</tr></thead><tbody>"
        + "".join(rows) +
        "</tbody></table></div></div>"
    )


def validation_summary_section(validation_summaries: list[dict[str, Any]]) -> str:
    """Render cross-asset validation evidence for known-event datasets."""
    rows = [r for r in validation_summaries if r.get("has_source")]
    if not rows:
        return ""
    events_in_span = sum(int(r["events_in_span"]) for r in rows)
    hits = sum(int(r["events_hit"]) for r in rows)
    missed = sum(int(r["events_missed"]) for r in rows)
    known_total = sum(int(r["known_total"]) for r in rows)
    alarm_episodes = sum(int(r["alarm_episodes"]) for r in rows)
    false_alarm_episodes = sum(int(r["alarm_episodes_without_event"]) for r in rows)
    alarm_hours = sum(float(r["alarm_hours"]) for r in rows)
    recall = (hits / events_in_span * 100.0) if events_in_span else 0.0

    kpis = [
        ("Known Events In Scored Window", f"{events_in_span:,}"),
        ("Known Events Hit", f"{hits:,}"),
        ("Known Events Missed", f"{missed:,}"),
        ("Event Recall", f"{recall:.1f}%"),
        ("Known Events Total", f"{known_total:,}"),
        ("Alarm Episodes", f"{alarm_episodes:,}"),
        ("Alarm Episodes Without Known Event", f"{false_alarm_episodes:,}"),
        ("Alarm Episode Hours", f"{alarm_hours:.2f}"),
    ]
    kpi_html = "".join(
        "<div class='kpi-box'>"
        f"<div class='kpi-label'>{html.escape(label)}</div>"
        f"<div class='kpi-value'>{html.escape(value)}</div>"
        "</div>"
        for label, value in kpis
    )
    table_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(r['asset_key']))}</td>"
        f"<td>{html.escape(str(r['dataset']))}</td>"
        f"<td>{int(r['events_hit'])}</td>"
        f"<td>{int(r['events_missed'])}</td>"
        f"<td>{int(r['events_in_span'])}</td>"
        f"<td>{int(r['known_total'])}</td>"
        f"<td>{int(r['alarm_episodes'])}</td>"
        f"<td>{int(r['alarm_episodes_without_event'])}</td>"
        f"<td>{float(r['alarm_hours']):.2f}</td>"
        "</tr>"
        for r in rows
    )
    return (
        "<section>"
        "<h2>Validation Evidence</h2>"
        "<p class='text-muted'>Known event windows are loaded from adapted dataset known_events.csv files when asset names match a public validation dataset. Labels are not fed into ACM scoring.</p>"
        f"<div class='kpi-grid'>{kpi_html}</div>"
        "<div class='card table-card'><table>"
        "<thead><tr><th>Asset</th><th>Dataset</th><th>Hit</th><th>Missed</th><th>Events In Score Span</th>"
        "<th>Known Events Total</th><th>Alarm Episodes</th><th>Alarm Episodes Without Event</th><th>Alarm Hours</th></tr></thead>"
        f"<tbody>{table_rows}</tbody></table></div>"
        "</section>"
    )


def palette_controls(chart_id: str) -> str:
    """Render detector palette buttons for one chart."""
    buttons = []
    for i, (name, palette) in enumerate(DETECTOR_PALETTES.items()):
        swatches = "".join(
            f"<span class='palette-swatch' style='background:{html.escape(color)}'></span>"
            for color in palette.values()
        )
        active = " active" if i == 0 else ""
        label = name.replace("_", " ").title()
        buttons.append(
            f"<button type='button' class='palette-btn{active}' "
            f"data-chart='{html.escape(chart_id)}' data-palette='{html.escape(name)}'>"
            f"{html.escape(label)}<span class='palette-swatches'>{swatches}</span></button>"
        )
    return (
        "<div class='chart-controls'>"
        "<span class='chart-control-label'>Detector colors</span>"
        + "".join(buttons) +
        "</div>"
    )


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
    validation_events = load_validation_events()

    # Build asset rows and figures
    rows_html = []
    figs_html = []
    chart_specs: dict[str, dict] = {}
    validation_summaries: list[dict[str, Any]] = []

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
        override = format_override_human(run_row.get("override_json")) if run_row is not None else None
        culprits = format_culprits_human(run_row.get("notes")) if run_row is not None else None

        diag_boxes = f"<div class='diag-box diag-summary'><span class='diag-label'>Data Quality</span>{html.escape(data_quality)}</div>"
        if calibration:
            calib_summary, tuning_kv = calibration
            calib_html = html.escape(calib_summary)
            if tuning_kv:
                kv_items = "".join(
                    f"<dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>"
                    for k, v in tuning_kv.items())
                calib_html += (
                    "<details class='diag-details'>"
                    "<summary>Tuning details</summary>"
                    f"<dl class='diag-kv-list'>{kv_items}</dl>"
                    "</details>")
            diag_boxes += f"<div class='diag-box diag-calibration'><span class='diag-label'>Calibration</span>{calib_html}</div>"
        if override:
            diag_boxes += (
                "<div class='diag-box diag-override'>"
                "<span class='diag-label'>Ablation Override</span>"
                f"{html.escape(override)}</div>")
        if culprits:
            diag_boxes += f"<div class='diag-box diag-culprits'><span class='diag-label'>Culprits</span>{html.escape(culprits)}</div>"
        asset_alarms = alarms_by_asset.get(meta["asset_key"])
        diag_boxes += score_coverage_box(s, asset_alarms)
        diag_boxes += detector_stats_table(s)
        diag_boxes += alarm_history_table(asset_alarms)
        validation_summary, validation_box = validation_for_asset(
            str(meta["asset_key"]), s, asset_alarms, validation_events)
        validation_summaries.append(validation_summary)
        diag_boxes += validation_box

        figs_html.append(
            f"<div class='card' id='{html.escape(meta['asset_key'])}'>"
            f"<h4>{html.escape(meta['asset_key'])}</h4>"
            f"<div class='asset-card-grid'>"
            f"<div class='asset-card-chart'>"
            f"{palette_controls(chart_id)}"
            f"<div class='chart-container' id='{chart_id}' style='height:980px;'></div>"
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
        diag_block = render_run_diagnostics(r)

        main_row = (
            f"<tr>"
            f"<td>{html.escape(r.asset_key)}</td>"
            f"<td class='timestamp'>{format_report_datetime_cell(getattr(r, 'started_at', None))}</td>"
            f"<td>{duration_str}</td>"
            f"<td>{html.escape(r.status or '')}</td>"
            f"<td>{alert_z_str}</td>"
            f"<td class='rules-cell'><span class='rules-text'>{html.escape(rules_exp)}</span></td>"
            f"</tr>")
        if diag_block:
            main_row += f"<tr class='ops-diag-row'><td colspan='6'>{diag_block}</td></tr>"
        ops_rows.append(main_row)

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
    validation_html = validation_summary_section(validation_summaries)

    scope = f"farm {farm}" if farm else (f"{len(assets)} selected assets" if picks else "fleet")
    timestamp = format_report_datetime(datetime.now().astimezone().isoformat())
    chart_specs_json = json.dumps(chart_specs)
    detector_palettes_json = json.dumps(DETECTOR_PALETTES)
    detector_names_json = json.dumps({detector_label(k): k for k in Z_COLS})

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

        {validation_html}

        <section>
            <h2>Assets Overview</h2>
            <div class='card table-card'>
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
            <div class='card table-card'>
                <table class='ops-table'>
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
        var detectorPalettes = {detector_palettes_json};
        var detectorNameToKey = {detector_names_json};
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

        function applyPalette(chartId, paletteName) {{
            var el = document.getElementById(chartId);
            var palette = detectorPalettes[paletteName];
            if (!el || !palette || !el.data) return;
            var colors = [];
            var traceIndexes = [];
            el.data.forEach(function(trace, i) {{
                var key = detectorNameToKey[trace.name];
                if (!key || !palette[key]) return;
                colors.push(palette[key]);
                traceIndexes.push(i);
            }});
            if (traceIndexes.length) {{
                Plotly.restyle(el, {{'line.color': colors, 'marker.color': colors}}, traceIndexes);
            }}
            document.querySelectorAll('.palette-btn[data-chart="' + chartId + '"]').forEach(function(btn) {{
                btn.classList.toggle('active', btn.getAttribute('data-palette') === paletteName);
            }});
        }}

        document.querySelectorAll('.palette-btn').forEach(function(btn) {{
            btn.addEventListener('click', function() {{
                applyPalette(btn.getAttribute('data-chart'), btn.getAttribute('data-palette'));
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
