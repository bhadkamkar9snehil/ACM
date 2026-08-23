"""Configured ingestion adapters and the shared normalization boundary."""

import sqlite3
import urllib.parse
from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl

from ingest.csv_source import ingest_rows
from ingest.sources import (
    FileSource,
    HttpSource,
    SqliteTableSource,
    _with_query_param,
    build_source,
)
from runtime import Runtime
from store.raw import RawStore

UTC = timezone.utc


def _rows(n, start_min=0):
    base = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        {
            "ts": (base + timedelta(minutes=start_min + i)).isoformat(),
            "temp": float(i % 7),
            "vib": float((i * 3) % 5),
        }
        for i in range(n)
    ]


def test_manual_ingest_rows_normalizes_and_dedups(tmp_path):
    store = RawStore(tmp_path / "raw")
    rep = ingest_rows(store, "m/1", _rows(100))
    assert rep.rows_stored == 100 and rep.channels == 2
    rows = _rows(10, start_min=100)
    for row in rows:
        row["status"] = "RUNNING"
    rep2 = ingest_rows(store, "m/1", rows)
    assert "status" in rep2.dropped_columns
    assert "status" not in store.read("m/1").columns
    assert ingest_rows(store, "m/1", _rows(100)).rows_stored == 0


def test_file_source_watermark_incremental(tmp_path):
    store = RawStore(tmp_path / "raw")
    csv = tmp_path / "feed.csv"
    pl.DataFrame(_rows(50)).write_csv(csv)
    source = FileSource("f/1", str(csv))
    assert source.drain(store) == 50
    assert source.drain(store) == 0
    pl.DataFrame(_rows(80)).write_csv(csv)
    assert source.drain(store) == 30


def test_sqlite_table_source(tmp_path):
    store = RawStore(tmp_path / "raw")
    db = tmp_path / "hist.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE readings (ts TEXT, temp REAL, vib REAL)")
    con.executemany(
        "INSERT INTO readings VALUES (?,?,?)",
        [(row["ts"], row["temp"], row["vib"]) for row in _rows(40)],
    )
    con.commit()
    con.close()
    source = SqliteTableSource("s/1", str(db), "readings", ts_col="ts")
    assert source.drain(store) == 40
    assert source.drain(store) == 0
    assert store.read("s/1").height == 40


def test_sqlite_identifiers_are_quoted(tmp_path):
    """Configured table/column names are identifiers, never SQL fragments."""
    store = RawStore(tmp_path / "raw")
    db = tmp_path / "hist-spaces.db"
    con = sqlite3.connect(db)
    con.execute(
        'CREATE TABLE "sensor readings" '
        '("sample time" TEXT, temp REAL, vib REAL)'
    )
    con.executemany(
        'INSERT INTO "sensor readings" VALUES (?,?,?)',
        [(row["ts"], row["temp"], row["vib"]) for row in _rows(12)],
    )
    con.commit()
    con.close()

    source = SqliteTableSource(
        "s/quoted", str(db), "sensor readings", ts_col="sample time"
    )
    assert source.drain(store) == 12
    assert source.last_error == ""


def test_http_watermark_query_is_encoded_and_replaced():
    timestamp = "2026-08-23T05:45:00+00:00"
    url = _with_query_param(
        "https://example.invalid/data?plant=A%26B&since=old#frag",
        "since",
        timestamp,
    )
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qs(parts.query)
    assert query == {"plant": ["A&B"], "since": [timestamp]}
    assert parts.fragment == "frag"
    assert "%2B00%3A00" in parts.query


def test_build_source_kinds():
    assert build_source("a", {"kind": "manual"}) is None
    assert build_source("a", {"kind": "folder"}) is None
    assert isinstance(
        build_source("a", {"kind": "file", "path": "x.csv"}), FileSource
    )
    assert isinstance(
        build_source(
            "a", {"kind": "sqlite", "db_path": "d.db", "table": "t"}
        ),
        SqliteTableSource,
    )
    assert isinstance(
        build_source("a", {"kind": "http", "url": "https://example.invalid"}),
        HttpSource,
    )


def test_drop_folder_auto_onboards(tmp_path):
    store = RawStore(tmp_path / "raw")
    incoming = tmp_path / "incoming"
    (incoming / "plant").mkdir(parents=True)

    rng = np.random.default_rng(0)
    base = datetime(2025, 1, 1, tzinfo=UTC)
    n = 5000
    frame = pl.DataFrame(
        {
            "ts": [
                (base + timedelta(minutes=10 * i)).isoformat() for i in range(n)
            ],
            "temp": rng.normal(size=n),
            "vib": 0.8 * rng.normal(size=n) + 0.3 * rng.normal(size=n),
            "press": rng.normal(size=n),
        }
    )
    frame.write_csv(incoming / "plant" / "pump-3.csv")

    runtime = Runtime(store=store, data_root=tmp_path, incoming_dir=incoming)
    onboarded = runtime.scan_incoming()
    assert onboarded == 1
    assert "plant/pump-3" in runtime.monitors
    assert store.row_count("plant/pump-3") == n
    assert runtime.scan_incoming() == 0
