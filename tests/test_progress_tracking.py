"""Test script for batch processing features"""
import json
from pathlib import Path
import sys

# Test progress tracking functions
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.chunk_replay import _load_progress, _save_progress, _mark_chunk_completed, _get_progress_file

def test_progress_tracking():
    """Test progress tracking functionality"""
    artifact_root = Path("artifacts_test")
    artifact_root.mkdir(exist_ok=True)
    
    # Test 1: Load empty progress
    progress = _load_progress(artifact_root)
    assert progress == {}, f"Expected empty dict, got {progress}"
    print("✅ Test 1 passed: Load empty progress")
    
    # Test 2: Save progress
    test_progress = {"FD_FAN": {"batch_001.csv", "batch_002.csv"}}
    _save_progress(artifact_root, test_progress)
    assert _get_progress_file(artifact_root).exists(), "Progress file not created"
    print("✅ Test 2 passed: Save progress")
    
    # Test 3: Load saved progress
    loaded = _load_progress(artifact_root)
    assert loaded == {"FD_FAN": {"batch_001.csv", "batch_002.csv"}}, f"Progress mismatch: {loaded}"
    print("✅ Test 3 passed: Load saved progress")
    
    # Test 4: Mark chunk completed
    _mark_chunk_completed(artifact_root, "FD_FAN", "batch_003.csv")
    updated = _load_progress(artifact_root)
    assert "batch_003.csv" in updated["FD_FAN"], "Chunk not marked completed"
    print("✅ Test 4 passed: Mark chunk completed")
    
    # Test 5: Add new asset
    _mark_chunk_completed(artifact_root, "GAS_TURBINE", "batch_001.csv")
    updated = _load_progress(artifact_root)
    assert "GAS_TURBINE" in updated, "New asset not added"
    assert "batch_001.csv" in updated["GAS_TURBINE"], "Chunk not added to new asset"
    print("✅ Test 5 passed: Add new asset")
    
    # Cleanup
    progress_file = _get_progress_file(artifact_root)
    if progress_file.exists():
        progress_file.unlink()
    artifact_root.rmdir()
    
    print("\n🎉 All tests passed!")

if __name__ == "__main__":
    test_progress_tracking()
