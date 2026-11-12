"""#135 relational state store: schema/migration, episode round-trip
matching the old EpisodeLedger semantics, durable runtime journal
(the #120 core), and the registry."""

import json
from datetime import datetime, timezone

from memory.ledger import Episode, EpisodeLedger
from store.state import AssetRow, SqliteStateStore, migrate_json_files

UTC = timezone.utc


def test_open_is_idempotent_and_versioned(tmp_path):
    p = tmp_path / "state.db"
    s1 = SqliteStateStore(p)
    s1.close()
    s2 = SqliteStateStore(p)  # re-open must not fail or double-migrate
    assert s2.table_counts()["assets"] == 0
    s2.close()


def test_episode_backend_matches_file_ledger(tmp_path):
    """The store-backed ledger must behave identically to the file one:
    add/remove/windows/mask and the direct .episodes list reads."""
    store = SqliteStateStore(tmp_path / "state.db")
    led = EpisodeLedger(store=store)
    a = Episode("m/1", "2025-01-01T00:00:00+00:00", "2025-01-02T00:00:00+00:00", "alarm")
    b = Episode("m/1", "2025-03-01T00:00:00+00:00", "", "change-not-fault")
    led.add(a)
    led.add(b)
    assert led.episodes == [a, b]
    assert set(led.windows("m/1", states=("alarm",))) == {
        ("2025-01-01T00:00:00+00:00", "2025-01-02T00:00:00+00:00")
    }
    # open episode ("" end) reports the sentinel far-future end
    assert ("2025-03-01T00:00:00+00:00", "9999-12-31T00:00:00+00:00") in led.windows("m/1")
    led.remove(a)
    assert led.episodes == [b]

    # a fresh ledger over the same store reloads exactly (durable)
    led2 = EpisodeLedger(store=store)
    assert led2.episodes == [b]
    store.close()


def test_runtime_journal_survives_reopen(tmp_path):
    """#120 core: last_seen/tick_count persist across a store re-open
    (i.e. a service restart), so the next tick resumes instead of
    re-reading the whole life."""
    p = tmp_path / "state.db"
    s = SqliteStateStore(p)
    s.ensure_asset("m/1", datetime.now(UTC).isoformat())
    s.set_last_seen("m/1", "2025-06-01T00:00:00+00:00")
    s.set_tick_count("m/1", 42)
    s.close()

    s2 = SqliteStateStore(p)
    assert s2.get_last_seen("m/1") == "2025-06-01T00:00:00+00:00"
    assert s2.get_tick_count("m/1") == 42
    s2.close()


def test_registry_upsert_list_retire(tmp_path):
    s = SqliteStateStore(tmp_path / "state.db")
    s.upsert_asset(AssetRow(
        asset_key="plant/pump-3", display_name="Pump 3", grp="plant",
        added_at="2025-01-01T00:00:00+00:00", source_kind="sqlite",
        source_config={"db": "hist.db", "table": "readings"},
    ))
    got = s.get_asset("plant/pump-3")
    assert got.display_name == "Pump 3"
    assert got.source_config["table"] == "readings"
    assert [a.asset_key for a in s.list_assets()] == ["plant/pump-3"]
    s.retire_asset("plant/pump-3", "2025-02-01T00:00:00+00:00")
    assert s.list_assets() == []  # retired hidden by default
    assert len(s.list_assets(include_retired=True)) == 1
    s.close()


def test_bootstrapped_marker_roundtrip(tmp_path):
    s = SqliteStateStore(tmp_path / "state.db")
    s.set_bootstrapped("m/1", "2025-01-01T00:00:00+00:00")
    assert s.get_bootstrapped() == {"m/1": "2025-01-01T00:00:00+00:00"}
    s.close()


def test_migrates_legacy_json_files(tmp_path):
    """A pre-#135 data root with ledger.json + bootstrapped.json is
    imported once, and the files are renamed aside."""
    (tmp_path / "ledger.json").write_text(json.dumps([
        {"asset_key": "m/1", "start": "2025-01-01T00:00:00+00:00",
         "end": "", "state": "alarm", "note": ""}
    ]), encoding="utf-8")
    (tmp_path / "bootstrapped.json").write_text(json.dumps(
        {"m/1": "2025-01-02T00:00:00+00:00"}
    ), encoding="utf-8")

    s = SqliteStateStore(tmp_path / "state.db")
    report = migrate_json_files(s, tmp_path)
    assert report == {"episodes": 1, "bootstrapped": 1}
    assert len(s.list_episodes()) == 1
    assert s.get_bootstrapped() == {"m/1": "2025-01-02T00:00:00+00:00"}
    assert not (tmp_path / "ledger.json").exists()
    assert (tmp_path / "ledger.json.migrated").exists()
    # idempotent: a second call imports nothing
    assert migrate_json_files(s, tmp_path) == {"episodes": 0, "bootstrapped": 0}
    s.close()
