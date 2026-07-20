"""#138 ingestion adapters: manual rows, file/sqlite/http pull sources
(watermark-incremental, normalize()-clean), and the drop-folder scan."""

import sqlite3
from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl

from ingest.csv_source import ingest_rows
from ingest.sources import FileSource, SqliteTableSource, build_source
from runtime import Runtime
from store.raw import TIMESTAMP_COL, RawStore

UTC = timezone.utc


def _rows(n, start_min=0):
    base = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        {"ts": (base + timedelta(minutes=start_min + i)).isoformat(),
         "temp": float(i % 7), "vib": float((i * 3) % 5)}
        for i in range(n)
    ]


def test_manual_ingest_rows_normalizes_and_dedups(tmp_path):
    store = RawStore(tmp_path / "raw")
    rep = ingest_rows(store, "m/1", _rows(100))
    assert rep.rows_stored == 100 and rep.channels == 2
    # labels never enter the store; a non-numeric column is dropped
    rows = _rows(10, start_min=100)
    for r in rows:
        r["status"] = "RUNNING"  # label column
    rep2 = ingest_rows(store, "m/1", rows)
    assert "status" in rep2.dropped_columns
    assert "status" not in store.read("m/1").columns
    # idempotent replay: same rows again store 0 new
    assert ingest_rows(store, "m/1", _rows(100)).rows_stored == 0


def test_file_source_watermark_incremental(tmp_path):
    store = RawStore(tmp_path / "raw")
    csv = tmp_path / "feed.csv"
    pl.DataFrame(_rows(50)).write_csv(csv)
    src = FileSource("f/1", str(csv))
    assert src.drain(store) == 50
    assert src.drain(store) == 0  # nothing new -> watermark holds
    # append more rows to the file; only the new ones ingest
    pl.DataFrame(_rows(80)).write_csv(csv)
    assert src.drain(store) == 30


def test_sqlite_table_source(tmp_path):
    store = RawStore(tmp_path / "raw")
    db = tmp_path / "hist.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE readings (ts TEXT, temp REAL, vib REAL)")
    con.executemany(
        "INSERT INTO readings VALUES (?,?,?)",
        [(r["ts"], r["temp"], r["vib"]) for r in _rows(40)],
    )
    con.commit()
    con.close()
    src = SqliteTableSource("s/1", str(db), "readings", ts_col="ts")
    assert src.drain(store) == 40
    assert src.drain(store) == 0
    assert store.read("s/1").height == 40


def test_build_source_kinds(tmp_path):
    assert build_source("a", {"kind": "manual"}) is None
    assert build_source("a", {"kind": "folder"}) is None
    assert isinstance(
        build_source("a", {"kind": "file", "path": "x.csv"}), FileSource
    )
    assert isinstance(
        build_source("a", {"kind": "sqlite", "db_path": "d.db",
                           "table": "t"}), SqliteTableSource
    )


def test_drop_folder_auto_onboards(tmp_path):
    """A CSV dropped into incoming_dir becomes a monitored asset within
    one scan - the fast dataset-testing loop."""
    store = RawStore(tmp_path / "raw")
    incoming = tmp_path / "incoming"
    (incoming / "plant").mkdir(parents=True)

    # enough history for the guarantee to arm
    rng = np.random.default_rng(0)
    base = datetime(2025, 1, 1, tzinfo=UTC)
    n = 5000
    frame = pl.DataFrame({
        "ts": [(base + timedelta(minutes=10 * i)).isoformat() for i in range(n)],
        "temp": rng.normal(size=n),
        "vib": 0.8 * rng.normal(size=n) + 0.3 * rng.normal(size=n),
        "press": rng.normal(size=n),
    })
    frame.write_csv(incoming / "plant" / "pump-3.csv")

    rt = Runtime(store=store, data_root=tmp_path, incoming_dir=incoming)
    onboarded = rt.scan_incoming()
    assert onboarded == 1
    assert "plant/pump-3" in rt.monitors  # keyed by relative path
    assert store.row_count("plant/pump-3") == n
    # scanning again ingests nothing new (seen-set) and re-onboards nothing
    assert rt.scan_incoming() == 0
