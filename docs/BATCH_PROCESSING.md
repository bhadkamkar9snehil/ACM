# Batch Processing Guide

**ACM V8 Batch Processing & Chunk Replay Best Practices**

---

## Overview

ACM V8 supports batch processing through the **chunk replay harness** (`scripts/chunk_replay.py`), which enables:

- Sequential or parallel processing of pre-sliced time-series batches
- Cold-start bootstrapping on first chunk per asset
- Model caching and reuse across chunks
- Progress tracking with resume capability
- Incremental model updates (where supported)

This guide covers optimal batch sizing, usage patterns, and troubleshooting.

---

## Quick Start

### 1. Prepare Chunked Data

Organize your time-series data into sequential chunks per equipment:

```
data/chunked/
├── FD_FAN/
│   ├── batch_001.csv
│   ├── batch_002.csv
│   └── batch_003.csv
└── GAS_TURBINE/
    ├── batch_001.csv
    ├── batch_002.csv
    └── batch_003.csv
```

**Naming Convention:** Files are sorted by numeric index (e.g., `batch_001`, `batch_002`). The first chunk is used for cold-start training.

### 2. Run Chunk Replay

**Basic Usage (Sequential):**
```bash
python scripts/chunk_replay.py --equip FD_FAN GAS_TURBINE
```

**Parallel Processing:**
```bash
python scripts/chunk_replay.py --max-workers 4
```

**Resume from Last Checkpoint:**
```bash
python scripts/chunk_replay.py --resume
```

**Dry Run (Preview Commands):**
```bash
python scripts/chunk_replay.py --dry-run
```

**Forward Arguments to ACM:**
```bash
python scripts/chunk_replay.py --acm-args -- --enable-report --config-override fusion.weights.ar1_z=0.3
```

---

## Optimal Batch Sizing

### Key Factors

1. **Sensor Count** - More sensors = more compute per sample
2. **Sampling Cadence** - Higher frequency = more samples per time window
3. **Time Window** - Longer windows provide more regime coverage
4. **Memory Constraints** - Large batches increase memory footprint
5. **Detection Latency** - Smaller batches reduce time-to-detection

### Recommended Batch Sizes

| Equipment Profile | Sensors | Cadence | Batch Duration | Expected Rows | Notes |
|-------------------|---------|---------|----------------|---------------|-------|
| **Small Asset** | 10-20 | 1 min | 7 days | 10,080 | Fast processing, minimal memory |
| **Medium Asset** | 20-50 | 1 min | 3-5 days | 4,320-7,200 | Balanced trade-off |
| **Large Asset** | 50-100+ | 1 min | 1-3 days | 1,440-4,320 | Heavy compute, frequent updates |
| **High-Frequency** | Any | 1-10 sec | 1-2 days | 8,640-17,280 | Streaming-like behavior |
| **Low-Frequency** | Any | 15-60 min | 14-30 days | 1,344-2,880 | Long-term trend analysis |

### General Guidelines

**Minimum Batch Size:**
- At least **500-1,000 rows** for stable detector training
- At least **2-3 regime states** for meaningful clustering
- At least **24 hours** of data for diurnal pattern capture

**Maximum Batch Size:**
- Keep below **50,000 rows** for memory efficiency (< 2 GB RAM per batch)
- Keep below **30 days** to avoid stale model drift

**Cold-Start Batch (First Chunk):**
- Should be **2-3x larger** than scoring batches for robust training
- Should cover **all major operating regimes** (startup, steady-state, shutdown)
- Recommended: **7-14 days** for initial training

### Calculation Formula

```python
# Estimate batch size
sensor_count = 50
cadence_seconds = 60  # 1 minute
days = 3

expected_rows = (days * 24 * 3600) / cadence_seconds
expected_memory_mb = (expected_rows * sensor_count * 8) / (1024 * 1024)  # 8 bytes per float64

print(f"Expected rows: {expected_rows:,.0f}")
print(f"Expected memory: {expected_memory_mb:.1f} MB")
```

**Example Output:**
```
Expected rows: 4,320
Expected memory: 1.6 MB
```

---

## Usage Patterns

### Pattern 1: Historical Backfill

**Scenario:** Process 6 months of historical data for initial model training and validation.

```bash
# Split historical data into 7-day chunks
python scripts/split_data.py --equip FD_FAN --input data/FD_FAN_HISTORICAL.csv --chunk-days 7 --output data/chunked/FD_FAN

# Run batch processing with parallel execution
python scripts/chunk_replay.py --equip FD_FAN --max-workers 1 --clear-cache
```

**Tips:**
- Use `--clear-cache` to ensure fresh training on first chunk
- Set `max-workers=1` for single asset to avoid resource contention
- Monitor first chunk runtime to estimate total processing time

### Pattern 2: Continuous Learning

**Scenario:** Process new data daily while reusing and updating existing models.

```bash
# Day 1: Bootstrap with 14-day training chunk
python scripts/chunk_replay.py --equip FD_FAN --clear-cache

# Day 2+: Append new daily chunks and resume
python scripts/chunk_replay.py --equip FD_FAN --resume
```

**Tips:**
- First chunk should be 2-3x larger for robust training
- Use `--resume` to skip previously completed chunks
- Models will evolve incrementally with scalers updating via `partial_fit`

### Pattern 3: Multi-Asset Parallel Processing

**Scenario:** Process 20 assets simultaneously for monthly batch jobs.

```bash
# Process all assets with 8 parallel workers
python scripts/chunk_replay.py --max-workers 8 --resume --acm-args -- --enable-report
```

**Tips:**
- Set `max-workers` based on CPU cores (typically `cores - 2`)
- Use `--resume` for fault tolerance (rerun failed jobs)
- Monitor system resources (CPU, memory) during first run

### Pattern 4: Interrupted Recovery

**Scenario:** Long-running batch job failed midway, need to resume without reprocessing.

```bash
# Resume from last successful chunk (progress tracked in .chunk_replay_progress.json)
python scripts/chunk_replay.py --resume
```

**Progress Tracking:**
- Progress saved to `artifacts/.chunk_replay_progress.json`
- Tracks completed chunks per asset
- Safe to delete to force full reprocessing

---

## Model Behavior Across Chunks

### First Chunk (Bootstrap)
1. **Train** detectors on full chunk data
2. **Score** same chunk using trained models
3. **Cache** models in `artifacts/<EQUIP>/models/v1/`
4. **Generate** baseline statistics, thresholds, regimes

### Subsequent Chunks (Incremental Scoring)
1. **Load** cached models from previous chunk
2. **Score** new chunk data (no retraining)
3. **Update** scalers incrementally via `partial_fit` (if enabled)
4. **Append** results to cumulative outputs

### Model Retraining Triggers
Models will retrain if:
- Config signature changes (detector parameters modified)
- Sensor list changes (features added/removed)
- Quality degradation detected (silhouette score drops, NaN spike)
- Manual cache clear requested (`--clear-cache`)

---

## Performance Optimization

### Speedup Techniques

1. **Polars Feature Engineering** (82% faster than pandas)
   - Enabled by default in `core/fast_features.py`
   - Handles differencing, rolling stats, lag features

2. **Model Caching** (5-8s speedup per chunk)
   - Saves trained detectors to `artifacts/<EQUIP>/models/`
   - Skips redundant training on subsequent chunks

3. **Parallel Asset Processing**
   - Use `--max-workers` to process multiple assets simultaneously
   - Recommendation: `max_workers = min(cpu_count - 2, num_assets)`

4. **Batch Size Tuning**
   - Larger batches = fewer chunks = less overhead
   - Trade-off: Larger batches increase memory and detection latency

### Bottleneck Identification

**Slow Training (First Chunk):**
- Reduce PCA components: `models.pca.n_components = 3`
- Reduce IForest estimators: `models.iforest.n_estimators = 50`
- Reduce GMM components: `models.gmm.n_components = 3`

**Slow Scoring (Subsequent Chunks):**
- Check feature engineering time (enable profiling)
- Reduce rolling window sizes: `features.ma_window = 3`
- Disable expensive features if not needed

**Memory Spikes:**
- Reduce batch size (split into smaller chunks)
- Disable report generation: remove `--enable-report`
- Clear old artifacts: `python scripts/clean_artifacts.py`

---

## Troubleshooting

### Issue: "No chunks found for <EQUIP>"

**Cause:** Chunk directory missing or empty.

**Solution:**
```bash
# Verify chunk directory structure
ls data/chunked/<EQUIP>/

# Ensure CSVs are named correctly (batch_001.csv, batch_002.csv, etc.)
```

### Issue: "ACM run failed for <EQUIP> chunk <NAME> (exit code 1)"

**Cause:** ACM pipeline error (NaN data, config error, model failure).

**Solution:**
```bash
# Check logs for specific error
python -m core.acm_main --equip <EQUIP> --score-csv data/chunked/<EQUIP>/<NAME>.csv --artifact-root artifacts

# Common fixes:
# 1. Ensure CSV has valid timestamps and sensor columns
# 2. Check config_table.csv for correct equipment settings
# 3. Verify no NaN-only columns in data
```

### Issue: Progress file corruption

**Cause:** Interrupted write or JSON parsing error.

**Solution:**
```bash
# Delete progress file and restart
rm artifacts/.chunk_replay_progress.json

# Rerun with --resume (will reprocess all chunks)
python scripts/chunk_replay.py --resume
```

### Issue: Models not reusing across chunks

**Cause:** Config signature mismatch or cache invalidation.

**Solution:**
```bash
# Check model cache
ls artifacts/<EQUIP>/models/v*/

# Verify config consistency
python -c "from utils.config_dict import load_config; cfg = load_config('<EQUIP>'); print(cfg)"

# Force fresh training
python scripts/chunk_replay.py --clear-cache
```

---

## Advanced: Incremental Model Updates

ACM V8 supports incremental updates for compatible models (currently: StandardScaler only).

### Enabling Incremental Updates

Incremental updates are **automatic** when using chunk replay. Models that support `partial_fit` will update with each new chunk.

### Supported Models
- [SUPPORTED] **StandardScaler** - Updates mean/variance incrementally
- [NOT SUPPORTED] **PCA** - Requires full retraining (use IncrementalPCA for streaming)
- [NOT SUPPORTED] **IsolationForest** - Batch-only (no incremental equivalent)
- [NOT SUPPORTED] **GaussianMixture** - Batch-only (no incremental equivalent)
- [NOT SUPPORTED] **KMeans** - Batch-only (use MiniBatchKMeans for streaming)

### Future Streaming Support

To enable true streaming/incremental learning:
1. Replace `PCA` → `IncrementalPCA`
2. Replace `KMeans` → `MiniBatchKMeans`
3. Implement River streaming detectors (see `core/river_models.py`)

---

## Configuration Reference

### Chunk Replay Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--equip` | List | All assets | Specific equipment codes to process |
| `--chunk-root` | Path | `data/chunked` | Root directory for chunked data |
| `--artifact-root` | Path | `artifacts` | ACM artifacts output directory |
| `--max-workers` | Int | 1 | Number of assets to process in parallel |
| `--clear-cache` | Flag | False | Clear model cache on bootstrap chunk |
| `--resume` | Flag | False | Skip already-completed chunks |
| `--dry-run` | Flag | False | Print commands without execution |
| `--acm-args` | List | [] | Additional arguments forwarded to ACM |

### Example: Custom ACM Configuration

```bash
python scripts/chunk_replay.py \
  --equip FD_FAN \
  --max-workers 2 \
  --resume \
  --acm-args -- \
    --enable-report \
    --config configs/config_table.csv \
    --mode batch
```

---

## Best Practices Summary

**DO:**
- Start with 3-7 day batches for medium-sized assets
- Use 2-3x larger first chunk for robust training
- Enable `--resume` for long-running batch jobs
- Monitor first chunk runtime to estimate total time
- Use parallel processing for multi-asset scenarios
- Keep batch sizes under 50K rows for memory efficiency

**DON'T:**
- Use batches smaller than 500-1,000 rows (unstable training)
- Use batches larger than 50K rows (memory bloat)
- Change config mid-batch (invalidates model cache)
- Run parallel workers exceeding CPU cores
- Forget to verify first chunk covers all regimes

---

## Related Documentation

- **[Chunk Replay Script](../scripts/chunk_replay.py)** - Full implementation
- **[Model Persistence](../core/model_persistence.py)** - Caching and versioning
- **[Cold-Start Mode](COLDSTART_MODE.md)** - Bootstrap training details
- **[SQL Integration](SQL_INTEGRATION_PLAN.md)** - Database batch processing

---

**Last Updated:** 2025-11-05  
**Status:** Production-Ready
