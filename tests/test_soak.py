from evidence.soak import ASSET_KEY, _episodes
from store.state import SqliteStateStore


def test_soak_reads_relational_episode_ledger(tmp_path):
    state = SqliteStateStore(tmp_path / "state.db")
    state.add_episode(
        {
            "asset_key": ASSET_KEY,
            "start": "2026-01-01T00:00:00+00:00",
            "end": "2026-01-02T00:00:00+00:00",
            "state": "change-not-fault",
            "note": "absorbed",
        }
    )
    state.add_episode(
        {
            "asset_key": "other/asset",
            "start": "2026-01-01T00:00:00+00:00",
            "end": "2026-01-02T00:00:00+00:00",
            "state": "alarm",
            "note": "unrelated",
        }
    )
    state.close()

    episodes = _episodes(tmp_path)
    assert len(episodes) == 1
    assert episodes[0]["asset_key"] == ASSET_KEY
    assert episodes[0]["state"] == "change-not-fault"
