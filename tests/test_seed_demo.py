"""evidence.seed_demo (#131): seeding a CARE-shaped farm into a LIVE
data root as one continuous asset per event - the demo/UI path, distinct
from care_replay's isolated per-event scoring runs."""

from pathlib import Path

from evidence.seed_demo import seed_farm
from store.raw import RawStore
from tests.test_care_replay import _make_farm  # reuse the synthetic farm fixture


def test_seed_farm_appends_one_asset_per_event_no_meta_columns(tmp_path):
    farm = _make_farm(tmp_path)
    root = tmp_path / "acm_data"
    keys = seed_farm(farm, root)

    assert sorted(keys) == ["wind-farm-t/1", "wind-farm-t/2"]

    store = RawStore(root / "raw")
    for key, expected_rows in (("wind-farm-t/1", 6000), ("wind-farm-t/2", 6000)):
        frame = store.read(key)
        assert frame.height == expected_rows
        # the whole life, no train/prediction split (unlike care_replay)
        assert "train_test" not in frame.columns
        # labels never enter the raw store, full stop
        for meta in ("status_type_id", "asset_id", "id"):
            assert meta not in frame.columns
        assert frame.schema["timestamp"].time_zone == "UTC"


def test_seed_farm_custom_prefix(tmp_path):
    farm = _make_farm(tmp_path)
    root = tmp_path / "acm_data"
    keys = seed_farm(farm, root, prefix="demo")
    assert sorted(keys) == ["demo/1", "demo/2"]


def test_seed_farm_skips_missing_csvs(tmp_path):
    """Partial downloads (--count on the downloader) are the norm, not
    an error - mirrors care_replay's replay_farm behavior."""
    farm = _make_farm(tmp_path)
    (farm / "datasets" / "2.csv").unlink()
    root = tmp_path / "acm_data"
    keys = seed_farm(farm, root)
    assert keys == ["wind-farm-t/1"]
