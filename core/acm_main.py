# core/acm_main.py
from __future__ import annotations

import hashlib
import sys
import json
import time
import threading
from datetime import datetime
import os
from typing import Any, Dict, List, Tuple, Optional, Sequence

import numpy as np
import pandas as pd
from pathlib import Path
import joblib

# --- import guard to support both `python -m core.acm_main` and `python core\acm_main.py`
try:
    # import ONLY core modules relatively
    from . import regimes, drift, fuse
    from . import correlation, outliers, forecast, river_models # New modules
    from . import fast_features
    # DEPRECATED: from . import storage  # Use output_manager instead
except ImportError:
    import pathlib
    sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
    from core import regimes, drift, fuse
    from core import correlation, outliers, forecast
    from core import river_models
    # DEPRECATED: from core import storage  # Use output_manager instead
    try:
        from core import fast_features
    except Exception:
        fast_features = None

# Note: models/ directory deleted - all functionality consolidated into core/
# PCA, IForest, GMM → core/outliers.py and core/correlation.py
# OMR → core/omr.py (OMRDetector class)
from core.omr import OMRDetector  # OMR-02: Overall Model Residual

# Import the unified output system
from core.output_manager import OutputManager
from core import rul_estimator
from core import enhanced_forecasting
# Import run metadata writer
from core.run_metadata_writer import write_run_metadata, extract_run_metadata_from_scores, extract_data_quality_score
# Import episode culprits writer
from core.episode_culprits_writer import write_episode_culprits_enhanced
# Import config history writer
from core.config_history_writer import log_auto_tune_changes
# ---

import argparse

# Config
try:
    import yaml
except ImportError as e:
    raise SystemExit("pyyaml is required: pip install pyyaml") from e

# SQL client (optional; only used in SQL mode)
try:
    from core.sql_client import SQLClient  # type: ignore
except Exception:
    SQLClient = None  # type: ignore

# Timer + Logger (safe fallbacks)
try:
    from utils.timer import Timer  # type: ignore
except Exception:
    class Timer:
        def __init__(self, enable: bool = True): pass
        def section(self, *_a, **_k):
            class _C:
                def __enter__(self): return self
                def __exit__(self, *x): return False
            return _C()
        def log(self, *a, **k): pass

try:
    from utils.logger import Console  # type: ignore
except Exception:
    class Console:
        @staticmethod
        def info(msg: str): print(f"[INFO] {msg}")
        # portability shim for environments that expect `.warning`
        warning = staticmethod(lambda msg: print(f"[WARN] {msg}"))
        warn = staticmethod(lambda msg: print(f"[WARN] {msg}"))
        @staticmethod
        def error(msg: str): print(f"[ERROR] {msg}")


def _nearest_indexer(index: pd.Index, targets: Sequence[Any], label: str = "indexer") -> np.ndarray:
    """Map target timestamps to index positions using nearest matches.

    Returns an array of index locations where ``-1`` denotes missing targets.
    Handles non-monotonic indexes by operating on a sorted view and falls back
    to a NumPy search path when Pandas raises for complex target shapes.
    """
    if index.empty:
        return np.full(len(targets), -1, dtype=int) if hasattr(targets, "__len__") else np.array([], dtype=int)

    if not hasattr(targets, "__len__"):
        targets = list(targets)

    if len(targets) == 0:
        return np.empty(0, dtype=int)

    target_dt = pd.to_datetime(targets, errors="coerce")
    if isinstance(target_dt, pd.Series):
        target_dt = target_dt.to_numpy()
    target_idx = pd.DatetimeIndex(target_dt)
    result = np.full(target_idx.shape[0], -1, dtype=int)

    valid_mask = ~target_idx.isna()
    if not valid_mask.any():
        return result

    work_index = pd.DatetimeIndex(index)
    if not work_index.is_monotonic_increasing:
        work_index = work_index.sort_values()

    try:
        locs = work_index.get_indexer(target_idx, method="nearest")
    except (ValueError, TypeError) as err:
        Console.warn(f"[{label}] Falling back to manual nearest mapping: {err}")
        idx_values = work_index.asi8
        target_values = target_idx.asi8[valid_mask]
        if target_values.size and idx_values.size:
            pos = np.searchsorted(idx_values, target_values, side="left")
            right_idx = np.clip(pos, 0, len(idx_values) - 1)
            left_idx = np.clip(pos - 1, 0, len(idx_values) - 1)
            right_dist = np.abs(idx_values[right_idx] - target_values)
            left_dist = np.abs(idx_values[left_idx] - target_values)
            chosen = np.where(right_dist < left_dist, right_idx, left_idx)
            result[valid_mask] = chosen.astype(int)
        return result

    locs = np.asarray(locs, dtype=int)
    result[valid_mask] = locs[valid_mask]
    return result


def _write_run_meta_json(local_vars: Dict[str, Any]) -> None:
    """Persist run metadata to meta.json inside the current run directory."""
    run_dir = local_vars.get("run_dir")
    if not run_dir:
        return

    try:
        run_dir_path = Path(run_dir)
    except TypeError:
        Console.warn("[META] Skipped meta.json: invalid run_dir value")
        return

    run_id = local_vars.get("run_id")
    equip = local_vars.get("equip")
    equip_id = local_vars.get("equip_id")
    run_start_time = local_vars.get("run_start_time")
    run_completion_time = local_vars.get("run_completion_time")
    if run_completion_time is None and run_start_time is not None:
        run_completion_time = datetime.now()

    if (not equip_id or equip_id == 0) and equip:
        try:
            equip_id = _get_equipment_id(str(equip))
        except Exception:
            equip_id = 0

    config_signature = local_vars.get("config_signature")
    loaded_from_cache = local_vars.get("loaded_from_cache", False)
    cache_meta = local_vars.get("meta")
    cache_version = getattr(cache_meta, "version", None)
    if cache_version is None and isinstance(cache_meta, dict):
        cache_version = cache_meta.get("version")

    train_obj = local_vars.get("train")
    score_obj = local_vars.get("score")
    episodes_obj = local_vars.get("episodes")
    train_df = train_obj if isinstance(train_obj, pd.DataFrame) else None
    score_df = score_obj if isinstance(score_obj, pd.DataFrame) else None
    episodes_df = episodes_obj if isinstance(episodes_obj, pd.DataFrame) else None

    run_metadata = local_vars.get("run_metadata") or {}
    if not hasattr(run_metadata, "get"):
        run_metadata = {}

    regime_count_val = local_vars.get("regime_count")
    regime_count = regime_count_val if isinstance(regime_count_val, (int, np.integer)) else 0
    silhouette = local_vars.get("silhouette")
    per_regime_enabled = bool(local_vars.get("per_regime_enabled")) if "per_regime_enabled" in local_vars else False

    data_quality_score = local_vars.get("data_quality_score")
    refit_flag_path = local_vars.get("refit_flag_path")
    if isinstance(refit_flag_path, str):
        refit_flag_path = Path(refit_flag_path)

    try:
        tables_generated = sum(1 for _ in run_dir_path.glob("tables/*.csv"))
        charts_generated = sum(1 for _ in run_dir_path.glob("charts/*.png"))

        meta_payload = {
            "run_id": run_id,
            "equipment": equip,
            "equip_id": int(equip_id) if isinstance(equip_id, (int, np.integer)) else equip_id,
            "started_at": run_start_time.isoformat() if run_start_time else None,
            "completed_at": run_completion_time.isoformat() if run_completion_time else None,
            "duration_seconds": (run_completion_time - run_start_time).total_seconds() if run_start_time and run_completion_time else None,
            "config_signature": config_signature,
            "cache_status": {
                "models_loaded_from_cache": bool(loaded_from_cache),
                "cache_version": cache_version
            },
            "data_metrics": {
                "train_rows": len(train_df) if train_df is not None else 0,
                "score_rows": len(score_df) if score_df is not None else 0,
                "sensors_count": len(train_df.columns) if train_df is not None else 0,
                "kept_sensors": train_df.columns.tolist() if train_df is not None else []
            },
            "detection_results": {
                "episode_count": len(episodes_df) if episodes_df is not None else 0,
                "health_status": run_metadata.get("health_status", "UNKNOWN"),
                "avg_health_index": run_metadata.get("avg_health_index"),
                "min_health_index": run_metadata.get("min_health_index"),
                "max_fused_z": run_metadata.get("max_fused_z")
            },
            "regime_clustering": {
                "regime_count": regime_count,
                "quality_score": silhouette,
                "per_regime_thresholds_enabled": per_regime_enabled
            },
            "model_quality": {
                "data_quality_score": data_quality_score,
                "refit_requested": bool(refit_flag_path.exists()) if isinstance(refit_flag_path, Path) else False
            },
            "output_artifacts": {
                "tables_generated": tables_generated,
                "charts_generated": charts_generated
            }
        }

        meta_path = run_dir_path / "meta.json"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as handle:
            json.dump(meta_payload, handle, indent=2, default=str)
        Console.info(f"[META] Written run metadata to {meta_path}")
    except Exception as meta_err:
        Console.warn(f"[META] Failed to write meta.json: {meta_err}")


def _maybe_write_run_meta_json(local_vars: Dict[str, Any]) -> None:
    """Invoke run metadata writer if it is available in the module globals."""
    # Enforce SQL-only: do not write meta.json when running in SQL mode
    try:
        if bool(local_vars.get('SQL_MODE')):
            Console.info("[META] SQL-only mode: Skipping meta.json write")
            return
    except Exception:
        pass
    writer = globals().get("_write_run_meta_json")
    if callable(writer):
        writer(local_vars)
    else:
        Console.warn("[META] meta.json writer unavailable; skipping run metadata dump")

# ===== DRIFT-01: Multi-Feature Drift Detection Helpers =====
def _compute_drift_trend(drift_series: np.ndarray, window: int = 20) -> float:
    """
    Compute drift trend as the slope of linear regression over the last `window` points.
    Positive slope indicates upward drift, negative indicates downward drift.
    Returns normalized slope (slope per sample).
    """
    if len(drift_series) < 2:
        return 0.0
    
    # Use last `window` points
    recent = drift_series[-window:] if len(drift_series) >= window else drift_series
    if len(recent) < 2:
        return 0.0
    
    # Remove NaNs
    valid_mask = ~np.isnan(recent)
    if valid_mask.sum() < 2:
        return 0.0
    
    x = np.arange(len(recent))[valid_mask]
    y = recent[valid_mask]
    
    # Linear regression: y = slope * x + intercept
    try:
        slope, _ = np.polyfit(x, y, 1)
        return float(slope)
    except Exception:
        return 0.0


def _compute_regime_volatility(regime_labels: np.ndarray, window: int = 20) -> float:
    """
    Compute regime volatility as the fraction of regime transitions in the last `window` points.
    Returns value in [0, 1] where 0 = stable, 1 = highly volatile.
    """
    if len(regime_labels) < 2:
        return 0.0
    
    # Use last `window` points
    recent = regime_labels[-window:] if len(regime_labels) >= window else regime_labels
    if len(recent) < 2:
        return 0.0
    
    # Count transitions (label changes)
    transitions = np.sum(recent[1:] != recent[:-1])
    return float(transitions) / (len(recent) - 1)


# ===== Heartbeat =====
class Heartbeat:
    """Prints a line every `interval` seconds until stop() is called."""
    def __init__(self, label: str, interval: float = 2.0, next_hint: str | None = None, eta_hint: float | None = None, enabled: bool = True):
        self.label = label
        self.interval = interval
        self.next_hint = next_hint
        self.eta_hint = eta_hint
        self.enabled = enabled
        self._stop = threading.Event()
        self._t0 = time.perf_counter()
        self._thr = threading.Thread(target=self._run, daemon=True)
        self._started = False

    def start(self):
        if not self.enabled:
            return self
        print(f"[..] {self.label} ...")
        self._thr.start()
        self._started = True
        return self

    def stop(self):
        self._stop.set()
        if self._started and self._thr.is_alive():
            self._thr.join(timeout=0.1)
        if self._started:
            took = time.perf_counter() - self._t0
            print(f"[OK] {self.label} done in {took:.2f}s")

    def _run(self):
        spinner = ["-", "\\", "|", "/"]
        i = 0
        while not self._stop.wait(self.interval):
            spent = time.perf_counter() - self._t0
            eta = ""
            if self.eta_hint and spent < self.eta_hint * 5:
                rem = max(0.0, self.eta_hint - spent)
                eta = f" | ~{rem:0.0f}s left"
            nxt = f" | next: {self.next_hint}" if self.next_hint else ""
            print(f"[..] {spinner[i % len(spinner)]} {self.label}{eta}{nxt}")
            i = (i + 1) % len(spinner)


def _get_equipment_id(equipment_name: str) -> int:
    """
    Convert equipment name to numeric ID for asset-specific config.
    For SQL mode, map known equipment to their database IDs.
    
    Returns:
        0 for global defaults, >0 for specific equipment
    """
    if not equipment_name:
        return 0
    
    # SQL mode: use actual database IDs for known equipment
    sql_equipment_mapping = {
        'FD_FAN': 1,
        'GAS_TURBINE': 2621,
        # Add other equipment mappings as needed
    }
    
    if equipment_name in sql_equipment_mapping:
        return sql_equipment_mapping[equipment_name]
    
    # Fallback: Generate deterministic ID from equipment name (1-9999 range)
    import hashlib
    hash_val = int(hashlib.md5(equipment_name.encode()).hexdigest(), 16)
    equip_id = (hash_val % 9999) + 1  # Range: 1-9999
    return equip_id


def _load_config(path: Path = None, equipment_name: str = None) -> Dict[str, Any]:
    """
    Load config from SQL (preferred) or CSV table.
    Returns ConfigDict that acts like a dict but supports updates.
    
    Priority:
    1. SQL database (ACM_Config table) - if available
    2. CSV table (config_table.csv) - required fallback in configs/
    
    Args:
        path: Optional path to CSV config file (for explicit override)
        equipment_name: Name of equipment (e.g., "FD_FAN", "GAS_TURBINE")
                       If provided, loads asset-specific config overrides
    """
    from utils.config_dict import ConfigDict
    from utils.sql_config import get_equipment_config
    
    # Determine equipment ID
    equip_id = _get_equipment_id(equipment_name) if equipment_name else 0
    
    # Auto-discover config directory if no explicit path provided
    if path is None:
        config_dir = Path("configs")
        csv_path = config_dir / "config_table.csv"
    else:
        config_dir = path.parent
        csv_path = path if path.suffix == '.csv' else config_dir / "config_table.csv"
    
    # Try SQL first (new production mode)
    try:
        cfg_dict = get_equipment_config(
            equipment_code=equipment_name,
            use_sql=True,
            fallback_to_csv=False  # We'll handle fallback manually
        )
        if cfg_dict:
            equip_label = f"{equipment_name} (EquipID={equip_id})" if equip_id > 0 else "global defaults"
            Console.info(f"[CFG] Loaded config from SQL for {equip_label}")
            return ConfigDict(cfg_dict, mode="sql", equip_id=equip_id)
    except Exception as e:
        Console.warn(f"[CFG] Could not load config from SQL: {e}")
    
    # Fallback to CSV table (required)
    if csv_path.exists():
        if equip_id > 0:
            Console.info(f"[CFG] Loading config for {equipment_name} (EquipID={equip_id}) from {csv_path}")
        else:
            Console.info(f"[CFG] Loading global config from {csv_path}")
        return ConfigDict.from_csv(csv_path, equip_id=equip_id)
    
    # No config found - fail fast
    raise FileNotFoundError(
        f"Config file not found: {csv_path}\n"
        f"Please ensure config_table.csv exists in configs/ directory"
    )


def _compute_config_signature(cfg: Dict[str, Any]) -> str:
    """
    Compute a deterministic hash of config sections that affect model fitting.
    
    DEBT-05: Expanded to include all sections that affect model behavior:
    - models: Model hyperparameters (PCA, iForest, GMM, OMR, etc.)
    - features: Feature engineering (window, FFT, etc.)
    - preprocessing: Data preprocessing settings
    - detectors: Detector-specific parameters (AR1, HST, etc.)
    - thresholds: Calibration thresholds (q, self_tune, clip_z)
    - fusion: Fusion weights and auto-tuning settings
    - regimes: Regime clustering parameters (k, auto_k, etc.)
    - episodes: Episode detection thresholds (CPD k_sigma, h_sigma)
    - drift: Drift detection parameters (p95_threshold, multi_feature)
    
    Returns hex string for cache validation.
    """
    relevant_keys = ["models", "features", "preprocessing", "detectors", "thresholds", "fusion", "regimes", "episodes", "drift"]
    config_subset = {k: cfg.get(k) for k in relevant_keys if k in cfg}
    # Sort keys for determinism
    config_str = json.dumps(config_subset, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(config_str.encode("utf-8")).hexdigest()[:16]


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _ensure_local_index(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure the DataFrame index is a timezone-naive local DatetimeIndex.

    Simplified policy: treat all timestamps as local time and drop any tz info.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, errors="coerce")
    else:
        # If timezone-aware, strip tz information and keep local wall-clock times
        try:
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
        except Exception:
            # Fallback: coerce to naive datetimes
            df.index = pd.to_datetime(df.index, errors="coerce")
    return df

# =======================
# SQL helpers (local)
# =======================
def _sql_mode(cfg: Dict[str, Any]) -> bool:
    """Check if SQL mode is enabled. SQL mode is now the DEFAULT.

    Allows an environment override via ACM_FORCE_SQL_MODE so callers
    like the SQL batch runner can force SQL mode even if older configs
    still have runtime.storage_backend='file'.
    """
    force = os.getenv("ACM_FORCE_SQL_MODE", "").strip().lower()
    if force in ("1", "true", "yes", "sql"):
        return True
    backend = cfg.get("runtime", {}).get("storage_backend", "sql")  # Changed default from "file" to "sql"
    return backend == "sql"

def _sql_connect(cfg: Dict[str, Any]) -> Optional[Any]:
    if not SQLClient:
        raise RuntimeError("SQLClient not available. Ensure core/sql_client.py exists and pyodbc is installed.")
    # Prefer INI-based connection with Windows Authentication
    try:
        cli = SQLClient.from_ini('acm')
        cli.connect()
        return cli
    except Exception as ini_err:
        # Fallback to config dict (legacy behavior)
        Console.warn(f"[SQL] Failed to connect via INI, trying config dict: {ini_err}")
        sql_cfg = cfg.get("sql", {}) or {}
        cli = SQLClient(sql_cfg)
        cli.connect()
        return cli

def _sql_start_run(cli: Any, cfg: Dict[str, Any], equip_code: str) -> Tuple[str, pd.Timestamp, pd.Timestamp, int]:
    """
    Calls dbo.usp_ACM_StartRun and returns (run_id, window_start, window_end, equip_id).
    Uses a T-SQL block with OUTPUT parameters and a SELECT for capture.
    """
    # Get EquipID from equipment name (but let SP do the lookup)
    equip_id = _get_equipment_id(equip_code)  # Keep for return value
    
    stage = cfg.get("runtime", {}).get("stage", "score")
    version = cfg.get("runtime", {}).get("version", "v5.0.0")
    config_hash = cfg.get("hash", "")
    trigger = "timer"
    tick_minutes = cfg.get("runtime", {}).get("tick_minutes", 30)  # Default 30-minute intervals
    
    # For now, use NULL for the datetime parameters since the procedure will calculate them
    window_start = None
    window_end = None

    tsql = """
    DECLARE @RunID UNIQUEIDENTIFIER, @WS DATETIME2(3), @WE DATETIME2(3), @EID INT;
    EXEC dbo.usp_ACM_StartRun
        @EquipCode = ?, @EquipID = NULL, @Stage = ?, @TickMinutes = ?,
        @DefaultStartUtc = ?, @Version = ?, @ConfigHash = ?, @TriggerReason = ?,
        @RunID = @RunID OUTPUT,
        @WindowStartEntryDateTime = @WS OUTPUT,
        @WindowEndEntryDateTime = @WE OUTPUT,
        @EquipIDOut = @EID OUTPUT;
    SELECT CONVERT(varchar(36), @RunID) AS RunID, @WS AS WindowStartEntryDateTime, @WE AS WindowEndEntryDateTime, @EID AS EquipID;
    """
    """
    Calls the database stored procedure to start a new run.

    This procedure is expected to:
    1. Log the run start in a database table.
    2. Return a unique RunID for this execution.
    3. Determine and return the data processing window (start and end timestamps).
    """
    cur = cli.cursor()
    try:
        Console.info(f"[DEBUG] Calling usp_ACM_StartRun with params: EquipCode={equip_code}, Stage={stage}, TickMinutes={tick_minutes}")
        cur.execute(tsql, (equip_code, stage, tick_minutes, window_start, version, config_hash, trigger))
        row = cur.fetchone()
        if not row or row[0] is None:
            raise RuntimeError("usp_ACM_StartRun did not return a RunID.")
        run_id = str(row[0])
        ws = pd.to_datetime(row[1]) if row[1] else pd.Timestamp.now()
        we = pd.to_datetime(row[2]) if row[2] else pd.Timestamp.now()
        # Get EquipID from stored procedure output (4th column)
        equip_id = int(row[3]) if len(row) > 3 and row[3] is not None else equip_id
        cli.conn.commit()
        Console.info(f"[RUN] Started RunID={run_id} window=[{ws},{we}) equip='{equip_code}' EquipID={equip_id}")
        return run_id, ws, we, equip_id
    except Exception:
        cli.conn.rollback()
        raise
    finally:
        cur.close()

def _sql_finalize_run(cli: Any, run_id: str, outcome: str, rows_read: int, rows_written: int, err_json: Optional[str] = None) -> None:
    params = {
        "RunID": run_id,
        "Outcome": outcome,
        "RowsRead": rows_read,
        "RowsWritten": rows_written,
        "ErrorJSON": err_json
    }
    cli.call_proc("dbo.usp_ACM_FinalizeRun", params)

# =======================


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--equip", required=True)
    ap.add_argument("--artifact-root", default="artifacts", 
                    help="Base artifact path for charts/reports (equipment subdirectory always added: {base}/{EQUIP}/run_xxx/). Default: ./artifacts")
    ap.add_argument("--config", default=None, help="Config file path (auto-discovers configs/ directory if not specified)")
    ap.add_argument("--train-csv", help="Path to baseline CSV (historical normal data), overrides config.")
    ap.add_argument("--baseline-csv", dest="train_csv", help="Alias for --train-csv (baseline data)")
    ap.add_argument("--score-csv", help="Path to batch CSV (current data to analyze), overrides config.")
    ap.add_argument("--batch-csv", dest="score_csv", help="Alias for --score-csv (batch data)")
    ap.add_argument("--mode", choices=["batch"], default="batch")
    ap.add_argument("--clear-cache", action="store_true", help="Force re-training by deleting the cached model for this equipment.")
    args = ap.parse_args()

    T = Timer(enable=True)

    equip = args.equip
    art_root = Path(args.artifact_root)
    cfg_path = Path(args.config) if args.config else None
    cfg = _load_config(cfg_path, equipment_name=equip)
    
    # DEBT-10: Deep copy config to prevent accidental mutation
    import copy
    cfg = copy.deepcopy(cfg)
    Console.info("[CFG] Config deep-copied to prevent accidental mutations")
    
    # Store equipment ID in config for later use
    equip_id = _get_equipment_id(equip)
    if not hasattr(cfg, '_equip_id') or cfg._equip_id == 0:
        cfg._equip_id = equip_id
    
    # Compute config signature for cache validation
    config_signature = _compute_config_signature(cfg)
    Console.info(f"[CFG] Config signature: {config_signature}")
    
    # CRITICAL FIX: Store signature in config for cache validation
    cfg["_signature"] = config_signature

    # Inline Option A adapter (no extra file): derive SQL_MODE
    SQL_MODE = _sql_mode(cfg)

    Console.info(f"[ACM] Inside Main Now")
    Console.info(f"--- Starting ACM V5 for {equip} ---")
    Console.info(f"[CFG] storage_backend={'sql' if SQL_MODE else 'file'}  |  artifacts={art_root}")

    # CRITICAL FIX: ALWAYS enforce artifacts/{EQUIP}/run_{timestamp}/ structure
    # STRICT: Only allow "artifacts" as base - strip everything else
    equip_slug = equip.replace(" ", "_")
    run_id_ts = time.strftime("%Y%m%d_%H%M%S")

    # ENFORCE: ONLY artifacts/{EQUIP}/run_{timestamp}/ - NO INTERMEDIATE FOLDERS
    # User passes "artifacts" or "artifacts/anything" → ALWAYS becomes artifacts/{EQUIP}/
    base_artifacts = Path("artifacts")  # HARDCODED - ignore user's subdirectories
    equip_root = base_artifacts / equip_slug
    run_dir = equip_root / f"run_{run_id_ts}"
    Console.info(f"[RUN] Creating unique run directory: {run_dir}")
    models_dir = run_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    # Heartbeat gating
    heartbeat_on = bool(cfg.get("runtime", {}).get("heartbeat", True))

    reuse_models = bool(cfg.get("runtime", {}).get("reuse_model_fit", False))
    # CRITICAL FIX: Stable cache must match equipment root (artifacts/{EQUIP}/models/)
    stable_models_dir = equip_root / "models"
    try:
        stable_models_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    # Refit-request marker path (set by quality/drift policy)
    refit_flag_path = stable_models_dir / "refit_requested.flag"
    model_cache_path = (stable_models_dir / "detectors.joblib")
    detector_cache: Optional[Dict[str, Any]] = None
    train_feature_hash: Optional[str] = None  # DEBT-09: Changed to str for stable hash
    current_train_columns: Optional[List[str]] = None
    regime_model: Optional[regimes.RegimeModel] = None
    regime_basis_train: Optional[pd.DataFrame] = None
    regime_basis_score: Optional[pd.DataFrame] = None
    regime_basis_meta: Dict[str, Any] = {}
    regime_basis_hash: Optional[int] = None
    train_numeric: Optional[pd.DataFrame] = None
    score_numeric: Optional[pd.DataFrame] = None
    cache_payload: Optional[Dict[str, Any]] = None
    regime_quality_ok: bool = True
    _ensure_dir(run_dir)

    if args.clear_cache:
        if model_cache_path.exists():
            model_cache_path.unlink()
            Console.info(f"[CACHE] Cleared model cache at {model_cache_path}")
        else:
            Console.info(f"[CACHE] No model cache found at {model_cache_path} to clear.")

    # Heuristic ETAs (adjust via config if needed)
    eta_load = float((cfg.get("hints") or {}).get("eta_load_sec", 30))
    eta_fit  = float((cfg.get("hints") or {}).get("eta_fit_sec", 8))
    eta_score = float((cfg.get("hints") or {}).get("eta_score_sec", 6))

    # Check if dual-write mode is enabled
    dual_mode = cfg.get("output", {}).get("dual_mode", False)

    # ===== SQL: Start Run (window discovery) or Dual Mode Setup =====
    sql_client: Optional[Any] = None
    run_id: Optional[str] = None
    win_start: Optional[pd.Timestamp] = None
    win_end: Optional[pd.Timestamp] = None
    equip_id: int = 0

    if SQL_MODE:
        try:
            sql_client = _sql_connect(cfg)
            # Prefer EquipCode from config if set; else use CLI --equip
            equip_codes = cfg.get("runtime", {}).get("equip_codes") or [equip]
            Console.info(f"[DEBUG] equip_codes type={type(equip_codes)}, value={equip_codes}")
            equip_code = str(equip_codes[0] if isinstance(equip_codes, list) else equip)
            Console.info(f"[DEBUG] Final equip_code={equip_code}")
            run_id, win_start, win_end, equip_id = _sql_start_run(sql_client, cfg, equip_code)
        except Exception as e:
            Console.error(f"[RUN] Failed to start SQL run: {e}")
            # ensure finalize in finally still runs with whatever we have
            raise
    elif dual_mode:
        # Dual mode: Create SQL connection but don't start run (use file timestamps)
        try:
            sql_client = _sql_connect(cfg)
            # Generate run_id for dual mode (UUID format for SQL compatibility)
            import uuid
            run_id = str(uuid.uuid4())
            # Set equip_id for dual mode
            equip_id = _get_equipment_id(equip)
            Console.info(f"[DUAL] Created SQL connection for dual-write mode, run_id={run_id}")
        except Exception as e:
            Console.warn(f"[DUAL] Failed to connect to SQL for dual-write, will use file-only mode: {e}")
            sql_client = None
            run_id = None

    # Create OutputManager early - needed for data loading and all outputs
    output_manager = OutputManager(
        sql_client=sql_client,
        run_id=run_id,
        equip_id=equip_id,
        sql_only_mode=SQL_MODE
    )

    # ---------- Robust finalize context ----------
    outcome = "OK"
    err_json: Optional[str] = None
    rows_read = 0
    rows_written = 0
    errors = []
    
    # Track run timing for ACM_Runs metadata
    from datetime import datetime
    run_start_time = datetime.now()

    try:
        # ===== 1) Load data (legacy CSV path; historian SQL can be wired later) =====
        hb = Heartbeat("Loading data (read -> parse ts -> sort -> resample -> interpolate)", next_hint="build features", eta_hint=eta_load, enabled=heartbeat_on).start()
        with T.section("load_data"):
            # Ensure data section exists in config
            if "data" not in cfg:
                cfg["data"] = {}
            
            # Override data paths from CLI if provided
            if args.train_csv:
                cfg["data"]["train_csv"] = args.train_csv
            if args.score_csv:
                cfg["data"]["score_csv"] = args.score_csv
            
            # Cold-start mode: If no baseline provided, will bootstrap from batch data
            train_csv_provided = "train_csv" in cfg.get("data", {}) or args.train_csv
            if not train_csv_provided:
                Console.info("[DATA] Cold-start mode: No baseline provided, will bootstrap from batch data")
            else:
                Console.info(f"[DATA] Using baseline (train_csv): {cfg.get('data', {}).get('train_csv', 'N/A')}")
            Console.info(f"[DATA] Using batch (score_csv): {cfg.get('data', {}).get('score_csv', 'N/A')}")

            if SQL_MODE:
                # SQL mode: Use smart coldstart with retry logic
                from core.smart_coldstart import SmartColdstart
                
                coldstart_manager = SmartColdstart(
                    sql_client=sql_client,
                    equip_id=equip_id,
                    equip_name=equip,
                    stage='score'  # Always use 'score' stage for now
                )
                
                # Attempt data loading with intelligent retry
                train, score, meta, coldstart_complete = coldstart_manager.load_with_retry(
                    output_manager=output_manager,
                    cfg=cfg,
                    initial_start=win_start,
                    initial_end=win_end,
                    max_attempts=3
                )
                
                # If coldstart not complete, exit gracefully (will retry next job run)
                if not coldstart_complete:
                    Console.info("[COLDSTART] Deferred to next job run - insufficient data for training")
                    Console.info("[COLDSTART] Job will retry automatically when more data arrives")
                    
                    # Mark run as NOOP (no operation) - not a failure
                    outcome = "NOOP"
                    rows_read = 0
                    rows_written = 0
                    
                    # Finalize and exit
                    if sql_client and run_id:
                        _sql_finalize_run(sql_client, run_id=run_id, outcome=outcome, 
                                        rows_read=rows_read, rows_written=rows_written, err_json=None)
                    return  # Exit gracefully
                    
            else:
                # File mode: Load from CSV files
                train, score, meta = output_manager.load_data(cfg)
                
            train = _ensure_local_index(train)
            score = _ensure_local_index(score)
            
            # Deduplicate indices early to prevent O(n²) performance and silent data loss
            train_dups = train.index.duplicated(keep='last').sum()
            score_dups = score.index.duplicated(keep='last').sum()
            if train_dups > 0:
                Console.warn(f"[DATA] Removing {train_dups} duplicate timestamps from TRAIN data")
                train = train[~train.index.duplicated(keep='last')].sort_index()
            if score_dups > 0:
                Console.warn(f"[DATA] Removing {score_dups} duplicate timestamps from SCORE data")
                score = score[~score.index.duplicated(keep='last')].sort_index()
            
            # CRITICAL: Assert index uniqueness after deduplication to prevent downstream errors
            if not train.index.is_unique:
                raise RuntimeError(f"[DATA] TRAIN data still has duplicate timestamps after deduplication! "
                                 f"Total: {len(train)}, Unique: {train.index.nunique()}")
            if not score.index.is_unique:
                raise RuntimeError(f"[DATA] SCORE data still has duplicate timestamps after deduplication! "
                                 f"Total: {len(score)}, Unique: {score.index.nunique()}")
            meta.dup_timestamps_removed = int(train_dups + score_dups)
            Console.info(f"[DATA] Index integrity verified: BASELINE={len(train)} unique, BATCH={len(score)} unique")
        hb.stop()
        Console.info(
            f"[DATA] timestamp={meta.timestamp_col} cadence_ok={meta.cadence_ok} "
            f"kept={len(meta.kept_cols)} drop={len(meta.dropped_cols)} "
            f"tz_stripped={getattr(meta, 'tz_stripped', 0)} "
            f"future_drop={getattr(meta, 'future_rows_dropped', 0)} "
            f"dup_removed={getattr(meta, 'dup_timestamps_removed', 0)}"
        )
        T.log("shapes", train=train.shape, score=score.shape)
        train_numeric = train.copy()
        score_numeric = score.copy()

        # ===== Adaptive Rolling Baseline (cold-start helper) =====
        # If TRAIN is missing or too small, bootstrap it from a persisted rolling buffer
        # or, as a fallback, from the head of SCORE data.
        with T.section("baseline.seed"):
            try:
                baseline_cfg = (cfg.get("runtime", {}) or {}).get("baseline", {}) or {}
                min_points = int(baseline_cfg.get("min_points", 300))
                buffer_path = stable_models_dir / "baseline_buffer.csv"
                train_rows = len(train_numeric) if isinstance(train_numeric, pd.DataFrame) else 0
                if train_rows < min_points:
                    used: Optional[str] = None
                    if buffer_path.exists():
                        buf = pd.read_csv(buffer_path, index_col=0, parse_dates=True)
                        buf = _ensure_local_index(buf)
                        # Align TRAIN buffer to current SCORE columns to avoid drift
                        if isinstance(score_numeric, pd.DataFrame) and hasattr(buf, "columns"):
                            common_cols = [c for c in buf.columns if c in score_numeric.columns]
                            if len(common_cols) > 0:
                                buf = buf[common_cols]
                        train = buf.copy()
                        train_numeric = train.copy()
                        used = f"baseline_buffer.csv ({len(train)} rows)"
                    else:
                        # Seed TRAIN from the leading portion of SCORE
                        if isinstance(score_numeric, pd.DataFrame) and len(score_numeric):
                            seed_n = min(len(score_numeric), max(min_points, int(0.2 * len(score_numeric))))
                            train = score_numeric.iloc[:seed_n].copy()
                            train_numeric = train.copy()
                            used = f"score head ({seed_n} rows)"
                    if used:
                        Console.info(f"[BASELINE] Using adaptive baseline for TRAIN: {used}")
            except Exception as be:
                Console.warn(f"[BASELINE] Cold-start baseline setup failed: {be}")

        # ===== Data quality guardrails (High #4) =====
        with T.section("data.guardrails"):
            try:
                # 1) Baseline/Batch window ordering & overlap check
                tr_start = pd.to_datetime(train.index.min()) if len(train.index) else None
                tr_end   = pd.to_datetime(train.index.max()) if len(train.index) else None
                sc_start = pd.to_datetime(score.index.min()) if len(score.index) else None
                sc_end   = pd.to_datetime(score.index.max()) if len(score.index) else None
                if tr_end is not None and sc_start is not None and sc_start <= tr_end:
                    Console.warn(
                        f"[DATA] Batch window starts before or overlaps baseline end:"
                        f" batch_start={sc_start}, baseline_end={tr_end}"
                    )

                # 2) Low-variance sensor detection on BASELINE
                low_var_threshold = 1e-6
                low_var_features = []
                if isinstance(train_numeric, pd.DataFrame) and len(train_numeric.columns):
                    train_stds = train_numeric.std(numeric_only=True)
                    low_var = train_stds[train_stds < low_var_threshold]
                    if len(low_var) > 0:
                        low_var_features = list(low_var.index)
                        preview = ", ".join(low_var_features[:10])
                        Console.warn(
                            f"[DATA] {len(low_var)} low-variance sensor(s) in TRAIN (std<{low_var_threshold:g}): {preview}"
                        )

                # 3) Missing data report (per-tag null counts) → tables/data_quality.csv
                with T.section("data.guardrails.data_quality"):
                    try:
                        tables_dir = (run_dir / "tables")
                        tables_dir.mkdir(parents=True, exist_ok=True)
                        interp_method = str((cfg.get("data", {}) or {}).get("interp_method", "linear"))
                        sampling_secs = (cfg.get("data", {}) or {}).get("sampling_secs", None)
                        # Build summary for intersecting columns only
                        common_cols = []
                        if hasattr(train_numeric, "columns") and hasattr(score_numeric, "columns"):
                            common_cols = [c for c in train_numeric.columns if c in score_numeric.columns]
                        records = []
                        for col in common_cols:
                            tr_series = train_numeric[col]
                            sc_series = score_numeric[col]
                            tr_total = int(len(tr_series))
                            sc_total = int(len(sc_series))
                            tr_nulls = int(tr_series.isna().sum())
                            sc_nulls = int(sc_series.isna().sum())
                            tr_std = float(pd.to_numeric(tr_series, errors="coerce").std()) if tr_total else float("nan")
                            sc_std = float(pd.to_numeric(sc_series, errors="coerce").std()) if sc_total else float("nan")
                            
                            # Calculate longest gap (consecutive NaNs or missing timestamps)
                            def calc_longest_gap(series):
                                if len(series) == 0:
                                    return 0
                                is_null = series.isna()
                                if not is_null.any():
                                    return 0
                                # Find consecutive null runs
                                null_runs = is_null.astype(int).groupby((~is_null).cumsum()).sum()
                                return int(null_runs.max()) if len(null_runs) > 0 else 0
                            
                            tr_longest_gap = calc_longest_gap(tr_series)
                            sc_longest_gap = calc_longest_gap(sc_series)
                            
                            # Calculate flatline spans (consecutive identical values)
                            def calc_flatline_span(series):
                                if len(series) == 0:
                                    return 0
                                numeric = pd.to_numeric(series, errors='coerce').dropna()
                                if len(numeric) < 2:
                                    return 0
                                # Find consecutive identical values
                                is_same = (numeric == numeric.shift()).astype(int)
                                flat_runs = is_same.groupby((~is_same.astype(bool)).cumsum()).sum()
                                return int(flat_runs.max()) if len(flat_runs) > 0 else 0
                            
                            tr_flatline = calc_flatline_span(tr_series)
                            sc_flatline = calc_flatline_span(sc_series)
                            
                            # CHART-04: Min/Max timestamps - use standard format without 'T' separator
                            tr_min_ts = pd.Timestamp(tr_series.index.min()).strftime('%Y-%m-%d %H:%M:%S') if len(tr_series) > 0 else None
                            tr_max_ts = pd.Timestamp(tr_series.index.max()).strftime('%Y-%m-%d %H:%M:%S') if len(tr_series) > 0 else None
                            sc_min_ts = pd.Timestamp(sc_series.index.min()).strftime('%Y-%m-%d %H:%M:%S') if len(sc_series) > 0 else None
                            sc_max_ts = pd.Timestamp(sc_series.index.max()).strftime('%Y-%m-%d %H:%M:%S') if len(sc_series) > 0 else None
                            
                            note_bits = []
                            if tr_total > 0 and tr_std < low_var_threshold:
                                note_bits.append("low_variance_train")
                            if tr_total > 0 and tr_nulls == tr_total:
                                note_bits.append("all_nulls_train")
                            if sc_total > 0 and sc_nulls == sc_total:
                                note_bits.append("all_nulls_score")
                            if tr_flatline > 100:  # Arbitrary threshold for "concerning" flatline
                                note_bits.append(f"flatline_train_{tr_flatline}pts")
                            if sc_flatline > 100:
                                note_bits.append(f"flatline_score_{sc_flatline}pts")
                            
                            records.append({
                                "sensor": str(col),
                                "train_count": tr_total,
                                "train_nulls": tr_nulls,
                                "train_null_pct": (100.0 * tr_nulls / tr_total) if tr_total else 0.0,
                                "train_std": tr_std,
                                "train_longest_gap": tr_longest_gap,
                                "train_flatline_span": tr_flatline,
                                "train_min_ts": tr_min_ts,
                                "train_max_ts": tr_max_ts,
                                "score_count": sc_total,
                                "score_nulls": sc_nulls,
                                "score_null_pct": (100.0 * sc_nulls / sc_total) if sc_total else 0.0,
                                "score_std": sc_std,
                                "score_longest_gap": sc_longest_gap,
                                "score_flatline_span": sc_flatline,
                                "score_min_ts": sc_min_ts,
                                "score_max_ts": sc_max_ts,
                                "interp_method": interp_method,
                                "sampling_secs": sampling_secs,
                                "notes": ",".join(note_bits)
                            })
                        if records:
                            dq = pd.DataFrame(records)
                            # Use OutputManager for efficient writing
                            output_mgr = output_manager
                            output_mgr.write_dataframe(dq, tables_dir / "data_quality.csv")
                            try:
                                Console.info(f"[DATA] Wrote data quality summary -> {tables_dir / 'data_quality.csv'} ({len(records)} sensors)")
                            except UnicodeEncodeError:
                                Console.info(f"[DATA] Wrote data quality summary (path: {tables_dir / 'data_quality.csv'})")

                        counters_records = [
                            {"metric": "tz_stripped_total", "value": int(getattr(meta, "tz_stripped", 0))},
                            {"metric": "future_rows_dropped_total", "value": int(getattr(meta, "future_rows_dropped", 0))},
                            {"metric": "dup_timestamps_removed_total", "value": int(getattr(meta, "dup_timestamps_removed", 0))},
                        ]
                        counters_df = pd.DataFrame(counters_records)
                        output_manager.write_dataframe(counters_df, tables_dir / "data_quality_counters.csv")
                        Console.info(f"[DATA] Wrote data quality counters -> {tables_dir / 'data_quality_counters.csv'}")
                        
                        # 4) Generate dropped_sensors.csv - track sensors excluded from analysis
                        if hasattr(meta, 'dropped_cols') and len(meta.dropped_cols) > 0:
                            dropped_records = []
                            for dropped_col in meta.dropped_cols:
                                dropped_records.append({
                                    "sensor": str(dropped_col),
                                    "reason": "non_numeric_or_excluded_during_load",
                                    "train_present": dropped_col in (train.columns if hasattr(train, 'columns') else []),
                                    "score_present": dropped_col in (score.columns if hasattr(score, 'columns') else []),
                                })
                            if dropped_records:
                                dropped_df = pd.DataFrame(dropped_records)
                                output_mgr.write_dataframe(dropped_df, tables_dir / "dropped_sensors.csv")
                                Console.info(f"[DATA] Wrote dropped sensors summary -> {tables_dir / 'dropped_sensors.csv'} ({len(dropped_records)} dropped)")
                    except Exception as dq_e:
                        Console.warn(f"[DATA] Data quality summary skipped: {dq_e}")
            except Exception as g_e:
                Console.warn(f"[DATA] Guardrail checks skipped: {g_e}")

        # ===== Feature construction (migrate to fast_features POC) =====
        # We intentionally replace the raw sensor matrices with a compact, robust
        # feature space computed by `core.fast_features.compute_basic_features`.
        # This is a deliberate migration: no runtime toggle. Features are used
        # for downstream PCA/AR1 fitting and scoring.
        with T.section("features.build"):
            try:
                feat_win = int((cfg.get("features", {}) or {}).get("window", 3))
                if fast_features is not None and cfg.get("runtime", {}).get("phases", {}).get("features", True):
                    # Preserve original indices before they are lost in the feature building process
                    idx_train = train.index
                    idx_score = score.index

                    Console.info(f"[FEAT] Building features with window={feat_win} (fast_features)")
                    # --- OPTIMIZATION: Convert to Polars to use the fast path ---
                    # The compute_basic_features function is optimized for Polars input.
                    # By converting here, we ensure the high-performance `compute_basic_features_pl`
                    # is called internally, avoiding the slow pandas .apply() loops.
                    # Benchmark-gate Polars conversion to avoid overhead on small datasets
                    # Polars overhead break-even point is typically around 10k rows
                    total_rows = len(train) + len(score) 
                    polars_threshold = int((cfg.get("features", {}) or {}).get("polars_threshold", 10000))
                    use_polars = fast_features.HAS_POLARS and total_rows > polars_threshold
                    
                    # --- DATA-04: Compute fill values from TRAIN data to prevent leakage ---
                    # Score data should use training-derived statistics for imputation, not its own
                    with T.section("features.compute_fill_values"):
                        train_fill_values = train.select_dtypes(include=[np.number]).median().to_dict()
                        Console.info(f"[FEAT] Computed {len(train_fill_values)} fill values from training data (prevents leakage)")
                    
                    if use_polars:
                        with T.section("features.polars_convert"):
                            import polars as pl  # type: ignore
                            train_pl = pl.from_pandas(train)
                            score_pl = pl.from_pandas(score)
                        Console.info(f"[FEAT] Using Polars for feature computation ({total_rows:,} rows > {polars_threshold:,} threshold)")
                        with T.section("features.compute_train"):
                            Console.info("[FEAT] Building train features...")
                            train = fast_features.compute_basic_features(train_pl, window=feat_win)
                        with T.section("features.compute_score"):
                            Console.info("[FEAT] Building score features (using train fill values)...")
                            score = fast_features.compute_basic_features(score_pl, window=feat_win, fill_values=train_fill_values)
                    elif fast_features.HAS_POLARS:
                        Console.info(f"[FEAT] Using pandas for feature computation ({total_rows:,} rows <= {polars_threshold:,} threshold)")
                        with T.section("features.compute_train"):
                            train = fast_features.compute_basic_features(train, window=feat_win)
                        with T.section("features.compute_score"):
                            Console.info("[FEAT] Building score features (using train fill values)...")
                            score = fast_features.compute_basic_features(score, window=feat_win, fill_values=train_fill_values)
                    else: # Fallback if Polars is not installed
                        Console.warn("[FEAT] Polars not found, using pandas implementation.")
                        with T.section("features.compute_train"):
                            train = fast_features.compute_basic_features(train, window=feat_win)
                        with T.section("features.compute_score"):
                            Console.info("[FEAT] Building score features (using train fill values)...")
                            score = fast_features.compute_basic_features(score, window=feat_win, fill_values=train_fill_values)
                    
                    with T.section("features.normalize"):
                        # normalize back to pandas, restore index, enforce numeric
                        if not isinstance(train, pd.DataFrame):
                            train = train.to_pandas() if hasattr(train, "to_pandas") else pd.DataFrame(train)
                        if not isinstance(score, pd.DataFrame):
                            score = score.to_pandas() if hasattr(score, "to_pandas") else pd.DataFrame(score)
                        train.index = idx_train
                        score.index = idx_score
                        train = train.apply(pd.to_numeric, errors="coerce")
                        score = score.apply(pd.to_numeric, errors="coerce")

                    T.log("shapes_post_features", train=train.shape, score=score.shape)
                else:
                    Console.warn("[FEAT] fast_features not available; continuing with raw sensor inputs")
            except Exception as fe:
                Console.warn(f"[FEAT] Feature build failed, continuing with raw inputs: {fe}")

        # ===== Impute missing values in feature space =====
        with T.section("features.impute"):
            try:
                if isinstance(train, pd.DataFrame):
                    # Replace any infs with NaNs first, then fill NaNs with column medians.
                    # This ensures both inf and NaN are handled before modeling.
                    train.replace([np.inf, -np.inf], np.nan, inplace=True)
                    score.replace([np.inf, -np.inf], np.nan, inplace=True)

                    Console.info("[FEAT] Imputing non-finite values in features using train medians")
                    col_meds = train.median(numeric_only=True)
                    train.fillna(col_meds, inplace=True)
                    # Align SCORE to TRAIN columns to avoid mismatches and silent drops
                    score = score.reindex(columns=train.columns)
                    score.fillna(col_meds, inplace=True)
                    # Any remaining NaNs (rare) → fill with score column medians
                    nan_cols = score.columns[score.isna().any()].tolist()
                    if nan_cols:
                        for c in nan_cols:
                            if score[c].dtype.kind in "if":
                                score[c].fillna(score[c].median(), inplace=True)
                    
                    # Guard: drop all-NaN columns (train median is NaN)
                    # This prevents propagating NaNs into detectors
                    all_nan_cols = [c for c in train.columns if pd.isna(col_meds.get(c))]
                    
                    # FEAT-03: Also drop low-variance features from raw sensors
                    # Check variance in engineered features (not just raw sensors)
                    feat_stds = train.std(numeric_only=True)
                    low_var_feat = feat_stds[feat_stds < low_var_threshold]
                    low_var_feat_cols = list(low_var_feat.index) if len(low_var_feat) > 0 else []
                    
                    # Combine all columns to drop
                    cols_to_drop = list(set(all_nan_cols + low_var_feat_cols))
                    
                    if cols_to_drop:
                        Console.warn(f"[FEAT] Dropping {len(cols_to_drop)} unusable feature columns ({len(all_nan_cols)} NaN, {len(low_var_feat_cols)} low-variance)")
                        Console.warn(f"[FEAT] Dropped columns preview: {cols_to_drop[:10]}")
                        train = train.drop(columns=cols_to_drop)
                        score = score.drop(columns=cols_to_drop)
                        
                        # FEAT-03: Log feature drops to feature_drop_log.csv
                        with T.section("features.log_drops"):
                            try:
                                tables_dir = (run_dir / "tables")
                                tables_dir.mkdir(parents=True, exist_ok=True)
                                drop_records = []
                                for col in cols_to_drop:
                                    reason = "all_NaN" if col in all_nan_cols else "low_variance"
                                    med_val = col_meds.get(col)
                                    std_val = feat_stds.get(col)
                                    drop_records.append({
                                        "feature": str(col),
                                        "reason": reason,
                                        "train_median": str(med_val) if not pd.isna(med_val) else "NaN",
                                        "train_std": f"{std_val:.6f}" if not pd.isna(std_val) else "NaN",
                                        "timestamp": pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')  # CHART-04: Standard format
                                    })
                                if drop_records:
                                    drop_df = pd.DataFrame(drop_records)
                                    drop_log_path = tables_dir / "feature_drop_log.csv"
                                    # Append mode to preserve history across runs
                                    if not SQL_MODE:
                                        if drop_log_path.exists():
                                            drop_df.to_csv(drop_log_path, mode='a', header=False, index=False)
                                        else:
                                            drop_df.to_csv(drop_log_path, mode='w', header=True, index=False)
                                        Console.info(f"[FEAT] Logged {len(drop_records)} dropped features -> {drop_log_path}")
                            except Exception as drop_e:
                                Console.warn(f"[FEAT] Feature drop logging failed: {drop_e}")
                    
                    # Final guard: ensure we have at least one usable feature
                    if train.shape[1] == 0:
                        raise RuntimeError("[FEAT] No usable feature columns after imputation; aborting.")
            except Exception as ie:
                Console.warn(f"[FEAT] Imputation step failed or skipped: {ie}")

        current_train_columns = list(train.columns)
        with T.section("features.hash"):
            try:
                # DEBT-09: Stable hash across pandas versions and OS
                # Include shape + dtypes + data for cross-platform consistency
                shape_str = f"{train.shape[0]}x{train.shape[1]}"
                dtype_str = "|".join(f"{col}:{train[col].dtype}" for col in sorted(train.columns))
                
                # Sort columns for deterministic hashing
                train_sorted = train[sorted(train.columns)]
                data_bytes = train_sorted.to_numpy(dtype=np.float64, copy=False).tobytes()
                data_hash = hashlib.sha256(data_bytes).hexdigest()
                
                # Combine all fingerprints
                combined = f"{shape_str}|{dtype_str}|{data_hash}"
                train_feature_hash = hashlib.sha256(combined.encode('utf-8')).hexdigest()[:16]
                Console.info(f"[HASH] Stable hash computed: {train_feature_hash} (shape={shape_str})")
            except Exception as e:
                Console.warn(f"[HASH] Hash computation failed: {e}")
                train_feature_hash = None

        # Respect refit-request flag: bypass cache once and clear the flag
        refit_requested = False
        with T.section("models.refit_flag"):
            try:
                if refit_flag_path.exists():
                    refit_requested = True
                    Console.warn(f"[MODEL] Refit requested by quality policy; bypassing cache this run")
                    try:
                        refit_flag_path.unlink()
                    except Exception:
                        pass
            except Exception:
                pass

        if reuse_models and model_cache_path.exists() and not refit_requested:
            with T.section("models.cache_local"):
                try:
                    cached_bundle = joblib.load(model_cache_path)
                    cached_cols = cached_bundle.get("train_columns")
                    cached_hash = cached_bundle.get("train_hash")
                    cached_cfg_sig = cached_bundle.get("config_signature")
                    
                    # Validate cache: columns, train data hash, and config signature must match
                    with T.section("models.cache_local.validate"):
                        cols_match = (cached_cols == current_train_columns)
                        hash_match = (cached_hash is None or cached_hash == train_feature_hash)
                        cfg_match = (cached_cfg_sig is None or cached_cfg_sig == config_signature)
                    
                    if cols_match and hash_match and cfg_match:
                        detector_cache = cached_bundle
                        Console.info(f"[MODEL] Reusing cached detectors from {model_cache_path}")
                        Console.info(f"[MODEL] Cache validated: config_sig={config_signature[:8]}...") 
                    else:
                        reasons = []
                        if not cols_match: reasons.append("columns changed")
                        if not hash_match: reasons.append(f"train data changed ({cached_hash[:8] if cached_hash else 'none'} -> {train_feature_hash[:8]})")
                        if not cfg_match: reasons.append(f"config changed ({cached_cfg_sig[:8] if cached_cfg_sig else 'none'} -> {config_signature[:8]})")
                        Console.warn(f"[MODEL] Cache invalidated ({', '.join(reasons)}); re-fitting.")
                except Exception as e:
                    Console.warn(f"[MODEL] Failed to load cached detectors: {e}")

        # Attempt to infer EquipID from config or meta if available (0 if unknown)
        # CRITICAL: In SQL_MODE, equip_id is already set by _sql_start_run() from stored procedure
        # Do NOT override it! Only infer for file/dual modes.
        if not SQL_MODE:
            with T.section("data.equip_id_infer"):
                try:
                    equip_id = int(getattr(meta, "equip_id", 0) or 0)
                except Exception:
                    equip_id = 0
                
                # For dual mode, try config fallback if meta didn't provide it
                if dual_mode and equip_id == 0:
                    equip_id_cfg = cfg.get("runtime", {}).get("equip_id", equip_id)
                    try:
                        equip_id = int(equip_id_cfg)
                    except Exception:
                        equip_id = 0
        
        # Validate equip_id for SQL/dual modes
        if (SQL_MODE or dual_mode) and equip_id <= 0:
            raise RuntimeError(
                f"EquipID is required and must be a positive integer in SQL/dual mode. "
                f"Current value: {equip_id}. In SQL mode, this should come from _sql_start_run(). "
                f"In dual mode, set runtime.equip_id in config OR ensure load_data provides it."
            )

        # ===== 2) Fit heads on TRAIN =====
        
        # ===== Model Persistence: Try loading cached models =====
        cached_models = None
        cached_manifest = None
        # Skip persisted caches whenever a refit was requested to force fresh training
        use_cache = cfg.get("models", {}).get("use_cache", True) and not refit_requested
        
        if use_cache and detector_cache is None:
            with T.section("models.persistence.load"):
                try:
                    from core.model_persistence import ModelVersionManager
                    
                    model_manager = ModelVersionManager(
                        equip=equip, 
                        artifact_root=Path(art_root),
                        sql_client=sql_client if SQL_MODE or dual_mode else None,
                        equip_id=equip_id if SQL_MODE or dual_mode else None,
                        sql_only_mode=SQL_MODE
                    )
                    cached_models, cached_manifest = model_manager.load_models()
                    
                    if cached_models and cached_manifest:
                        # Validate cache
                        current_config_sig = cfg.get("_signature", "unknown")
                        current_sensors = list(train.columns) if hasattr(train, 'columns') else []
                        
                        with T.section("models.persistence.validate"):
                            is_valid, invalid_reasons = model_manager.check_model_validity(
                                manifest=cached_manifest,
                                current_config_signature=current_config_sig,
                                current_sensors=current_sensors
                            )
                        
                        if is_valid:
                            Console.info(f"[MODEL] Using cached models from v{cached_manifest['version']}")
                            Console.info(f"[MODEL] Cache created: {cached_manifest.get('created_at', 'unknown')}")
                        else:
                            Console.warn(f"[MODEL] Cached models invalid, retraining required:")
                            for reason in invalid_reasons:
                                Console.warn(f"[MODEL]   - {reason}")
                            cached_models = None
                            cached_manifest = None
                except Exception as e:
                    Console.warn(f"[MODEL] Failed to load cached models: {e}")
                    cached_models = None
                    cached_manifest = None
        
        # Initialize detector variables
        ar1_detector = pca_detector = mhal_detector = iforest_detector = gmm_detector = omr_detector = None  # type: ignore
        # CRITICAL FIX: Cache PCA train scores to avoid recomputation
        pca_train_spe = pca_train_t2 = None
        
        # PERF-03: Check fusion weights to skip disabled detectors (lazy evaluation)
        fusion_cfg = (cfg or {}).get("fusion", {})
        fusion_weights = fusion_cfg.get("weights", {})
        ar1_enabled = fusion_weights.get("ar1_z", 0.0) > 0
        pca_enabled = fusion_weights.get("pca_spe_z", 0.0) > 0 or fusion_weights.get("pca_t2_z", 0.0) > 0
        mhal_enabled = fusion_weights.get("mhal_z", 0.0) > 0
        iforest_enabled = fusion_weights.get("iforest_z", 0.0) > 0
        gmm_enabled = fusion_weights.get("gmm_z", 0.0) > 0
        omr_enabled = fusion_weights.get("omr_z", 0.0) > 0
        
        disabled_detectors = []
        if not ar1_enabled: disabled_detectors.append("ar1")
        if not pca_enabled: disabled_detectors.append("pca")
        if not mhal_enabled: disabled_detectors.append("mhal")
        if not iforest_enabled: disabled_detectors.append("iforest")
        if not gmm_enabled: disabled_detectors.append("gmm")
        if not omr_enabled: disabled_detectors.append("omr")
        
        if disabled_detectors:
            Console.info(f"[PERF] Lazy evaluation: skipping disabled detectors: {', '.join(disabled_detectors)}")
        
        # Try loading cached regime model from joblib persistence (new system)
        regime_model = None
        try:
            regime_model = regimes.load_regime_model(stable_models_dir)
            if regime_model is not None:
                Console.info(f"[REGIME] Loaded cached regime model: K={regime_model.kmeans.n_clusters}, hash={regime_model.train_hash}")
        except Exception as e:
            Console.warn(f"[REGIME] Failed to load cached regime model: {e}")
            regime_model = None
        
        # Try loading from cache (either old detector_cache or new persistence system)
        if cached_models:
            with T.section("models.persistence.rebuild"):
                # Load from new persistence system
                try:
                    # Reconstruct detector objects from cached models
                    # Note: We need to pass empty configs since we're loading pre-trained models
                    if "ar1_params" in cached_models and cached_models["ar1_params"]:
                        ar1_detector = forecast.AR1Detector(ar1_cfg={})
                        ar1_detector.phimap = cached_models["ar1_params"]["phimap"]
                        ar1_detector.sdmap = cached_models["ar1_params"]["sdmap"]
                        ar1_detector._is_fitted = True
                    
                    if "pca_model" in cached_models and cached_models["pca_model"]:
                        pca_detector = correlation.PCASubspaceDetector(pca_cfg={})
                        pca_detector.pca = cached_models["pca_model"]
                        pca_detector._is_fitted = True
                    
                    if "mhal_params" in cached_models and cached_models["mhal_params"] is not None:
                        mhal_detector = correlation.MahalanobisDetector(regularization=1e-3)
                        mhal_detector.mu = cached_models["mhal_params"]["mu"]
                        mhal_detector.S_inv = cached_models["mhal_params"]["S_inv"]
                    
                    if "iforest_model" in cached_models and cached_models["iforest_model"]:
                        iforest_detector = outliers.IsolationForestDetector(if_cfg={})
                        iforest_detector.model = cached_models["iforest_model"]
                        iforest_detector._is_fitted = True
                    
                    if "gmm_model" in cached_models and cached_models["gmm_model"]:
                        gmm_detector = outliers.GMMDetector(gmm_cfg={})
                        gmm_detector.model = cached_models["gmm_model"]
                        gmm_detector._is_fitted = True
                    
                    if "omr_model" in cached_models and cached_models["omr_model"]:
                        omr_cfg = (cfg.get("models", {}).get("omr", {}) or {})
                        omr_detector = OMRDetector.from_dict(cached_models["omr_model"], cfg=omr_cfg)
                    
                    if "regime_model" in cached_models and cached_models["regime_model"]:
                        from core.regimes import RegimeModel
                        regime_model = RegimeModel()
                        regime_model.model = cached_models["regime_model"]
                        regime_quality_ok = cached_manifest.get("models", {}).get("regimes", {}).get("quality", {}).get("quality_ok", True)
                        # CRITICAL FIX: Validate regime model compatibility
                        if regime_model.model is None:
                            Console.warn("[REGIME] Cached regime model is None; discarding.")
                            regime_model = None
                    
                    if "feature_medians" in cached_models and cached_models["feature_medians"] is not None:
                        col_meds = cached_models["feature_medians"]
                    
                    # Validate all critical models loaded
                    if all([ar1_detector, pca_detector, mhal_detector, iforest_detector]):
                        Console.info("[MODEL] Successfully loaded all models from cache")
                    else:
                        missing = []
                        if not ar1_detector: missing.append("ar1")
                        if not pca_detector: missing.append("pca")
                        if not mhal_detector: missing.append("mhal")
                        if not iforest_detector: missing.append("iforest")
                        Console.warn(f"[MODEL] Incomplete model cache, missing: {missing}, retraining required")
                        ar1_detector = pca_detector = mhal_detector = iforest_detector = gmm_detector = None
                        
                except Exception as e:
                    import traceback
                    Console.warn(f"[MODEL] Failed to reconstruct detectors from cache: {e}")
                    Console.warn(f"[MODEL] Traceback: {traceback.format_exc()}")
                    ar1_detector = pca_detector = mhal_detector = iforest_detector = gmm_detector = None
        
        elif detector_cache:
            with T.section("models.cache_local.apply"):
                ar1_detector = detector_cache.get("ar1")
                pca_detector = detector_cache.get("pca")
                mhal_detector = detector_cache.get("mhal")
                iforest_detector = detector_cache.get("iforest")
                gmm_detector = detector_cache.get("gmm")
                regime_model = detector_cache.get("regime_model")
                cached_regime_hash = detector_cache.get("regime_basis_hash")
                regime_quality_ok = bool(detector_cache.get("regime_quality_ok", True))
            if regime_model is not None:
                regime_model.meta["quality_ok"] = regime_quality_ok
            if not all([ar1_detector, pca_detector, mhal_detector, iforest_detector]):
                Console.warn("[MODEL] Cached detectors incomplete; re-fitting this run.")
                detector_cache = None
                regime_model = None
            else:
                Console.info("[MODEL] Using cached detectors from previous training run.")
                if regime_model is not None and cached_regime_hash is not None:
                    regime_model.train_hash = cached_regime_hash

        # Fit models if not loaded from cache
        if not all([ar1_detector or not ar1_enabled, 
                    pca_detector or not pca_enabled, 
                    mhal_detector or not mhal_enabled, 
                    iforest_detector or not iforest_enabled]):
            hb = Heartbeat("Fitting heads (AR1, Correlation, Outliers)", next_hint="score heads", eta_hint=eta_fit, enabled=heartbeat_on).start()
            
            if ar1_enabled and not ar1_detector:
                with T.section("fit.ar1"):
                    ar1_detector = forecast.AR1Detector(ar1_cfg=(cfg.get("models", {}).get("ar1", {}) or {})).fit(train)
            
            if pca_enabled and not pca_detector:
                with T.section("fit.pca_subspace"):
                    pca_cfg = (cfg.get("models", {}).get("pca", {}) or {})
                    pca_detector = correlation.PCASubspaceDetector(pca_cfg=pca_cfg).fit(train)
                    Console.info(f"[PCA] Subspace detector fitted with {pca_detector.pca.n_components_} components.")
                    # Cache TRAIN raw PCA scores to eliminate double computation in calibration
                    pca_train_spe, pca_train_t2 = pca_detector.score(train)
                    Console.info(f"[PCA] Cached train scores: SPE={len(pca_train_spe)} samples, T²={len(pca_train_t2)} samples")
            
            if mhal_enabled and not mhal_detector:
                with T.section("fit.mhal"):
                    # Stronger default regularization for stability (config-overridable)
                    mhal_reg = float((cfg.get("models", {}).get("mhal", {}) or {}).get("regularization", 1e-3))
                    Console.info(f"[MHAL] Using regularization: {mhal_reg}")
                    mhal_detector = correlation.MahalanobisDetector(regularization=mhal_reg).fit(train)
                    # ANA-07: Export condition number for calibration_summary
                    if hasattr(mhal_detector, 'cond_num'):
                        cfg.setdefault("_diagnostics", {})["mhal_cond_num"] = float(mhal_detector.cond_num)
            
            if iforest_enabled and not iforest_detector:
                with T.section("fit.iforest"):
                    if_cfg = (cfg.get("models", {}).get("iforest", {}) or {})
                    iforest_detector = outliers.IsolationForestDetector(if_cfg=if_cfg).fit(train)
            
            if gmm_enabled and not gmm_detector:
                with T.section("fit.gmm"):
                    # Harden GMM defaults
                    gmm_cfg = (cfg.get("models", {}).get("gmm", {}) or {})
                    gmm_cfg.setdefault("covariance_type", "full")
                    gmm_cfg.setdefault("reg_covar", 1e-3)
                    gmm_cfg.setdefault("n_init", 3)
                    gmm_cfg.setdefault("random_state", 42)
                    gmm_detector = outliers.GMMDetector(gmm_cfg=gmm_cfg).fit(train)
            
            if omr_enabled and not omr_detector:
                with T.section("fit.omr"):
                    omr_cfg = (cfg.get("models", {}).get("omr", {}) or {})
                    omr_detector = OMRDetector(cfg=omr_cfg).fit(train)
            hb.stop()

        # Validate required detectors are present (skip disabled ones)
        required_detectors = []
        if ar1_enabled and not ar1_detector: required_detectors.append("ar1")
        if pca_enabled and not pca_detector: required_detectors.append("pca")
        if mhal_enabled and not mhal_detector: required_detectors.append("mhal")
        if iforest_enabled and not iforest_detector: required_detectors.append("iforest")
        if gmm_enabled and not gmm_detector: required_detectors.append("gmm")
        if omr_enabled and not omr_detector: required_detectors.append("omr")
        
        if required_detectors:
            raise RuntimeError(f"[MODEL] Required detector initialization failed for enabled detectors: {required_detectors}")

        # ===== ADAPTIVE PARAMETER TUNING: Continuous Self-Monitoring =====
        # Check model health and auto-adjust parameters if needed
        Console.info("[ADAPTIVE] Checking model health...")
        param_adjustments = []
        
        # 1. Mahalanobis condition number check
        if mhal_enabled and mhal_detector and hasattr(mhal_detector, 'cond_num'):
            cond_num = mhal_detector.cond_num
            current_reg = mhal_detector.l2
            
            if cond_num > 1e28:
                # Critical: Increase regularization significantly
                suggested_reg = min(current_reg * 10.0, 10.0)
                param_adjustments.append({
                    'param': 'models.mahl.regularization',
                    'old': current_reg,
                    'new': suggested_reg,
                    'reason': f'Condition number {cond_num:.2e} exceeds 1e28 (critical instability)'
                })
                Console.warn(f"[ADAPTIVE] [TUNE] Mahalanobis needs tuning: {current_reg} -> {suggested_reg}")
            
            elif cond_num > 1e20 and current_reg < 0.1:
                # High: Moderate increase
                suggested_reg = min(current_reg * 5.0, 1.0)
                param_adjustments.append({
                    'param': 'models.mahl.regularization',
                    'old': current_reg,
                    'new': suggested_reg,
                    'reason': f'Condition number {cond_num:.2e} indicates high correlation (preventive tuning)'
                })
                Console.info(f"[ADAPTIVE] [TUNE] Mahalanobis preventive tuning: {current_reg} -> {suggested_reg}")
        
        # 2. NaN rate check (score a sample to detect NaN production)
        if mhal_enabled and mhal_detector:
            test_sample = train.head(min(100, len(train)))
            mhal_scores = mhal_detector.score(test_sample)
            nan_rate = np.isnan(mhal_scores).sum() / len(mhal_scores)
            
            if nan_rate > 0.01:  # > 1% NaN production
                Console.warn(f"[ADAPTIVE] Mahalanobis producing {nan_rate:.1%} NaNs - model instability detected")
                # Already flagged by condition number, just log
        
        # 3. Write parameter adjustments to config if needed
        if param_adjustments:
            Console.info(f"[ADAPTIVE] Writing {len(param_adjustments)} parameter adjustment(s) to config...")
            config_table_path = Path("configs/config_table.csv")
            
            if config_table_path.exists():
                try:
                    df_config = pd.read_csv(config_table_path)
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    for adj in param_adjustments:
                        param_parts = adj['param'].split('.')
                        category = param_parts[0]
                        param_path = '.'.join(param_parts[1:])
                        
                        # Try to parse EquipID from equip string
                        try:
                            equip_id = int(equip)
                        except ValueError:
                            equip_id = 0
                        
                        # Check if row exists
                        mask = (df_config["EquipID"] == equip_id) & \
                               (df_config["Category"] == category) & \
                               (df_config["ParamPath"] == param_path)
                        
                        if mask.any():
                            # Update existing
                            df_config.loc[mask, "ParamValue"] = adj['new']
                            df_config.loc[mask, "UpdatedDateTime"] = timestamp
                            df_config.loc[mask, "UpdatedBy"] = "ADAPTIVE_TUNING"
                            df_config.loc[mask, "ChangeReason"] = adj['reason']
                            Console.info(f" Updated {adj['param']}: {adj['old']} -> {adj['new']}")
                        else:
                            # Insert new
                            new_row = {
                                "EquipID": equip_id,
                                "Category": category,
                                "ParamPath": param_path,
                                "ParamValue": adj['new'],
                                "ValueType": "float",
                                "UpdatedDateTime": timestamp,
                                "UpdatedBy": "ADAPTIVE_TUNING",
                                "ChangeReason": adj['reason']
                            }
                            df_config = pd.concat([df_config, pd.DataFrame([new_row])], ignore_index=True)
                            Console.info(f"  Inserted {adj['param']}: {adj['new']}")
                    
                    # Save config (file-mode only)
                    if not SQL_MODE:
                        df_config.to_csv(config_table_path, index=False)
                        Console.info(f"[ADAPTIVE] Config updated: {config_table_path}")
                        Console.info(f"[ADAPTIVE] Rerun ACM to apply new parameters (current run continues with old params)")
                    
                except Exception as e:
                    Console.error(f"[ADAPTIVE] Failed to update config: {e}")
            else:
                Console.warn(f"[ADAPTIVE] Config table not found at {config_table_path}, skipping parameter updates")
        else:
            Console.info("[ADAPTIVE] All model parameters within healthy ranges")

        try:
            regime_basis_train, regime_basis_score, regime_basis_meta = regimes.build_feature_basis(
                train_features=train,
                score_features=score,
                raw_train=train_numeric,
                raw_score=score_numeric,
                pca_detector=pca_detector,
                cfg=cfg,
            )
            regime_basis_hash = int(pd.util.hash_pandas_object(regime_basis_train, index=True).sum())
        except Exception as e:
            Console.warn(f"[REGIME] Failed to build regime feature basis: {e}")
            regime_basis_train = None
            regime_basis_score = None
            regime_basis_meta = {}
            regime_basis_hash = None

        if regime_model is not None:
            if (
                regime_basis_train is None
                or regime_model.feature_columns != list(regime_basis_train.columns)
                or (regime_basis_hash is not None and regime_model.train_hash != regime_basis_hash)
            ):
                Console.warn("[REGIME] Cached regime model mismatch; will refit.")
                regime_model = None

        # ===== 3) Score on SCORE =====
        frame = pd.DataFrame(index=score.index)
        # Maintain the same ordering as `score` to prevent misalignment when
        # assigning Series by position. Episode mapping uses a nearest-indexer
        # that safely handles non-monotonic indexes, so no sort here.
        hb = Heartbeat("Scoring heads (AR1, Correlation, Outliers)", next_hint="calibration", eta_hint=eta_score, enabled=heartbeat_on).start()
        
        # PERF-03: Only score enabled detectors
        # CRITICAL FIX #6: Replace NaN with 0 after all detector .score() calls to prevent NaN propagation
        if ar1_enabled and ar1_detector:
            with T.section("score.ar1"):
                raw_score = ar1_detector.score(score)
                frame["ar1_raw"] = pd.Series(raw_score, index=frame.index).fillna(0)
        
        if pca_enabled and pca_detector:
            with T.section("score.pca_subspace"):
                pca_spe, pca_t2 = pca_detector.score(score)
                frame["pca_spe"] = pd.Series(pca_spe, index=frame.index).fillna(0)
                frame["pca_t2"] = pd.Series(pca_t2, index=frame.index).fillna(0)
        
        if mhal_enabled and mhal_detector:
            with T.section("score.mhal"):
                raw_score = mhal_detector.score(score)
                frame["mhal_raw"] = pd.Series(raw_score, index=frame.index).fillna(0)
        
        if iforest_enabled and iforest_detector:
            with T.section("score.iforest"):
                raw_score = iforest_detector.score(score)
                frame["iforest_raw"] = pd.Series(raw_score, index=frame.index).fillna(0)
        
        if gmm_enabled and gmm_detector:
            with T.section("score.gmm"):
                raw_score = gmm_detector.score(score)
                frame["gmm_raw"] = pd.Series(raw_score, index=frame.index).fillna(0)
        
        # Store OMR contributions outside frame (pandas doesn't support custom attributes)
        omr_contributions_data = None
        if omr_enabled and omr_detector:
            with T.section("score.omr"):
                # Score with contributions for attribution
                omr_z, omr_contributions = omr_detector.score(score, return_contributions=True)
                frame["omr_raw"] = pd.Series(omr_z, index=frame.index).fillna(0)
                # Store contributions for later export (stored as variable, not frame attribute)
                omr_contributions_data = omr_contributions
        
        hb.stop()

        # ===== Online Learning with River (Optional) =====
        if cfg.get("river", {}).get("enabled", False):
            with T.section("score.river_ar"):
                river_cfg = cfg.get("river", {}) or {}
                streaming_detector = river_models.RiverTAD(cfg=river_cfg)
                # Note: River models are stateful and process data row-by-row.
                frame["river_hst_raw"] = streaming_detector.score(score)

        # ===== 4) Regimes (Run before calibration to enable regime-aware thresholds) =====
        train_regime_labels = None
        score_regime_labels = None
        with T.section("regimes.label"):
            regime_ctx: Dict[str, Any] = {
                "regime_basis_train": regime_basis_train,
                "regime_basis_score": regime_basis_score,
                "basis_meta": regime_basis_meta,
                "regime_model": regime_model,
                "regime_basis_hash": regime_basis_hash,
                "X_train": train,
            }
            regime_out = regimes.label(score, regime_ctx, {"frame": frame}, cfg)
            frame = regime_out.get("frame", frame)
            regime_model = regime_out.get("regime_model", regime_model)
            score_regime_labels = regime_out.get("regime_labels")
            train_regime_labels = regime_out.get("regime_labels_train")
            regime_quality_ok = bool(regime_out.get("regime_quality_ok", True))
            if train_regime_labels is None and regime_model is not None and regime_basis_train is not None:
                train_regime_labels = regimes.predict_regime(regime_model, regime_basis_train)
            if score_regime_labels is None and regime_model is not None and regime_basis_score is not None:
                score_regime_labels = regimes.predict_regime(regime_model, regime_basis_score)
        score_out = regime_out
        regime_quality_ok = bool(regime_out.get("regime_quality_ok", True))

        # ===== Model Quality Assessment: Check if retraining needed =====
        # This happens AFTER first scoring so we can evaluate cached model performance
        force_retrain = False
        quality_report = None
        
        if cached_models and cfg.get("models", {}).get("auto_retrain", True):
            with T.section("models.quality_check"):
                try:
                    from core.model_evaluation import assess_model_quality
                    
                    # Build temporary episodes for quality check (before fusion/episodes)
                    temp_episodes = pd.DataFrame()  # Will be populated after fusion
                    
                    # Get regime quality metrics
                    regime_quality_metrics = {
                        "silhouette": score_out.get("silhouette", 0.0),
                        "quality_ok": regime_quality_ok
                    }
                    
                    # Assess quality (will do full assessment after fusion, but check config now)
                    config_changed = False
                    if cached_manifest:
                        cached_sig = cached_manifest.get("config_signature", "")
                        current_sig = cfg.get("_signature", "unknown")
                        config_changed = (cached_sig != current_sig)
                    
                    if config_changed:
                        Console.warn(f"[MODEL] Config changed - forcing retraining")
                        force_retrain = True
                        # Invalidate cached models
                        cached_models = None
                        ar1_detector = pca_detector = mhal_detector = iforest_detector = gmm_detector = None
                        
                except Exception as e:
                    Console.warn(f"[MODEL] Quality assessment failed: {e}")

        # ===== Model Persistence: Save trained models with versioning =====
        # Save if we trained new models (not loaded from cache)
        models_were_trained = (not cached_models and detector_cache is None) or force_retrain
        if models_were_trained:
            with T.section("models.persistence.save"):
                try:
                    from core.model_persistence import ModelVersionManager, create_model_metadata
                    
                    model_manager = ModelVersionManager(
                        equip=equip, 
                        artifact_root=Path(art_root),
                        sql_client=sql_client if SQL_MODE or dual_mode else None,
                        equip_id=equip_id if SQL_MODE or dual_mode else None,
                        sql_only_mode=SQL_MODE
                    )
                    
                    # Collect all models
                    models_to_save = {
                        "ar1_params": {"phimap": ar1_detector.phimap, "sdmap": ar1_detector.sdmap} if hasattr(ar1_detector, 'phimap') else None,
                        "pca_model": pca_detector.pca if hasattr(pca_detector, 'pca') else None,
                        "iforest_model": iforest_detector.model if hasattr(iforest_detector, 'model') else None,
                        "gmm_model": gmm_detector.model if hasattr(gmm_detector, 'model') else None,
                        "omr_model": omr_detector.to_dict() if omr_detector and omr_detector._is_fitted else None,
                        "mhal_params": {"mu": mhal_detector.mu, "S_inv": mhal_detector.S_inv} if hasattr(mhal_detector, 'S_inv') and mhal_detector.S_inv is not None else None,
                        "regime_model": regime_model.model if regime_model and hasattr(regime_model, 'model') else None,
                        "feature_medians": col_meds if 'col_meds' in locals() else None
                    }
                    
                    # Calculate training duration (approximate from timing sections)
                    # Use aggregate timing from T sections for model training
                    training_duration_s = None
                    try:
                        # Get timing data from the global timer
                        fit_sections = ["fit.ar1", "fit.pca_subspace", "fit.mhal", "fit.iforest", "fit.gmm", "fit.omr", "regimes.fit"]
                        total_fit_time = sum([T.timings.get(sec, {}).get("elapsed", 0.0) for sec in fit_sections])
                        if total_fit_time > 0:
                            training_duration_s = total_fit_time
                    except Exception:
                        pass
                    
                    # Create metadata
                    regime_quality_metrics = {
                        "quality_ok": regime_quality_ok,
                        "n_regimes": regime_model.model.n_clusters if regime_model and hasattr(regime_model, 'model') else 0
                    }
                    
                    with T.section("models.persistence.metadata"):
                        metadata = create_model_metadata(
                            config_signature=cfg.get("_signature", "unknown"),
                            train_data=train,
                            models_dict=models_to_save,
                            regime_quality=regime_quality_metrics,
                            training_duration_s=training_duration_s
                        )
                    
                    # Save models
                    model_version = model_manager.save_models(
                        models=models_to_save,
                        metadata=metadata
                    )
                    
                    Console.info(f"[MODEL] Saved all trained models to version v{model_version}")
                    
                except Exception as e:
                    import traceback
                    Console.warn(f"[MODEL] Failed to save models: {e}")
                    traceback.print_exc()

        # ===== 5) Calibrate -> pca_spe_z, pca_t2_z, ar1_z, mhal_z, iforest_z, gmm_z =====
        # CRITICAL FIX: Fit calibrators on TRAIN data, transform SCORE data
        with T.section("calibrate"):
            cal_q = float((cfg or {}).get("thresholds", {}).get("q", 0.98))
            self_tune_cfg = (cfg or {}).get("thresholds", {}).get("self_tune", {})
            use_per_regime = (cfg.get("fusion", {}) or {}).get("per_regime", False)
            quality_ok = bool(use_per_regime and regime_quality_ok and train_regime_labels is not None and score_regime_labels is not None)
            
            # Score TRAIN data with all fitted detectors (frame contains SCORE data)
            Console.info("[CAL] Scoring TRAIN data for calibration baseline...")
            train_frame = pd.DataFrame(index=train.index)
            train_frame["ar1_raw"] = ar1_detector.score(train)
            # CRITICAL FIX: Reuse cached PCA train scores to avoid recomputation
            if pca_train_spe is not None and pca_train_t2 is not None:
                Console.info("[CAL] Using cached PCA train scores (optimization)")
                train_frame["pca_spe"], train_frame["pca_t2"] = pca_train_spe, pca_train_t2
            else:
                Console.warn("[CAL] Cache miss - recomputing PCA train scores")
                train_frame["pca_spe"], train_frame["pca_t2"] = pca_detector.score(train)
            train_frame["mhal_raw"] = mhal_detector.score(train)
            train_frame["iforest_raw"] = iforest_detector.score(train)
            train_frame["gmm_raw"] = gmm_detector.score(train)
            if omr_enabled and omr_detector:
                train_frame["omr_raw"] = omr_detector.score(train, return_contributions=False)
            
            # Compute adaptive z-clip: Fit temp calibrators to get TRAIN P99, then set adaptive clip
            default_clip = float(self_tune_cfg.get("clip_z", 8.0))
            temp_cfg = dict(self_tune_cfg)  # Don't modify original yet
            train_z_p99 = {}
            
            det_list = [("ar1", "ar1_raw"), ("pca_spe", "pca_spe"), ("pca_t2", "pca_t2"),
                       ("mhal", "mhal_raw"), ("iforest", "iforest_raw"), ("gmm", "gmm_raw")]
            if omr_enabled:
                det_list.append(("omr", "omr_raw"))
            
            for det_name, raw_col in det_list:
                if raw_col in train_frame.columns:
                    # Fit temp calibrator with default clip
                    temp_cal = fuse.ScoreCalibrator(q=cal_q, self_tune_cfg=temp_cfg).fit(
                        train_frame[raw_col].to_numpy(copy=False), regime_labels=None
                    )
                    temp_z = temp_cal.transform(train_frame[raw_col].to_numpy(copy=False), regime_labels=None)
                    finite_z = temp_z[np.isfinite(temp_z)]
                    if len(finite_z) > 10:
                        p99 = float(np.percentile(finite_z, 99))
                        if 0 < p99 < 100:  # Sanity check
                            train_z_p99[det_name] = p99
            
            # Set adaptive clip: max(default, 1.5 * max_train_p99), capped at 50
            if train_z_p99:
                max_train_p99 = max(train_z_p99.values())
                adaptive_clip = max(default_clip, min(max_train_p99 * 1.5, 50.0))
                self_tune_cfg["clip_z"] = adaptive_clip
                Console.info(f"[CAL] Adaptive clip_z={adaptive_clip:.2f} (TRAIN P99 max={max_train_p99:.2f})")
            
            fit_regimes = train_regime_labels if quality_ok else None
            transform_regimes = score_regime_labels if quality_ok else None

            # Surface per-regime calibration activity
            frame["per_regime_active"] = 1 if quality_ok else 0
            
            # AR1: Fit on TRAIN, transform SCORE
            cal_ar = fuse.ScoreCalibrator(q=cal_q, self_tune_cfg=self_tune_cfg).fit(
                train_frame["ar1_raw"].to_numpy(copy=False), regime_labels=fit_regimes
            )
            frame["ar1_z"] = cal_ar.transform(frame["ar1_raw"].to_numpy(copy=False), regime_labels=transform_regimes)
            
            # PCA SPE: Fit on TRAIN, transform SCORE
            cal_pca_spe = fuse.ScoreCalibrator(q=cal_q, self_tune_cfg=self_tune_cfg).fit(
                train_frame["pca_spe"].to_numpy(copy=False), regime_labels=fit_regimes
            )
            frame["pca_spe_z"] = cal_pca_spe.transform(frame["pca_spe"].to_numpy(copy=False), regime_labels=transform_regimes)
            
            # PCA T²: Fit on TRAIN, transform SCORE
            cal_pca_t2 = fuse.ScoreCalibrator(q=cal_q, self_tune_cfg=self_tune_cfg).fit(
                train_frame["pca_t2"].to_numpy(copy=False), regime_labels=fit_regimes
            )
            frame["pca_t2_z"] = cal_pca_t2.transform(frame["pca_t2"].to_numpy(copy=False), regime_labels=transform_regimes)
            
            # Mahalanobis: Fit on TRAIN, transform SCORE
            cal_mhal = fuse.ScoreCalibrator(q=cal_q, self_tune_cfg=self_tune_cfg).fit(
                train_frame["mhal_raw"].to_numpy(copy=False), regime_labels=fit_regimes
            )
            frame["mhal_z"] = cal_mhal.transform(frame["mhal_raw"].to_numpy(copy=False), regime_labels=transform_regimes)
            
            # IsolationForest: Fit on TRAIN, transform SCORE
            cal_if = fuse.ScoreCalibrator(q=cal_q, self_tune_cfg=self_tune_cfg).fit(
                train_frame["iforest_raw"].to_numpy(copy=False), regime_labels=fit_regimes
            )
            frame["iforest_z"] = cal_if.transform(frame["iforest_raw"].to_numpy(copy=False), regime_labels=transform_regimes)
            
            # GMM: Fit on TRAIN, transform SCORE
            cal_gmm = fuse.ScoreCalibrator(q=cal_q, self_tune_cfg=self_tune_cfg).fit(
                train_frame["gmm_raw"].to_numpy(copy=False), regime_labels=fit_regimes
            )
            frame["gmm_z"] = cal_gmm.transform(frame["gmm_raw"].to_numpy(copy=False), regime_labels=transform_regimes)
            
            # OMR: Fit on TRAIN, transform SCORE
            if omr_enabled and "omr_raw" in train_frame.columns and "omr_raw" in frame.columns:
                cal_omr = fuse.ScoreCalibrator(q=cal_q, self_tune_cfg=self_tune_cfg).fit(
                    train_frame["omr_raw"].to_numpy(copy=False), regime_labels=fit_regimes
                )
                frame["omr_z"] = cal_omr.transform(frame["omr_raw"].to_numpy(copy=False), regime_labels=transform_regimes)
            
            # River Half-Space Trees (if enabled)
            if "river_hst_raw" in frame.columns:
                # River is online so doesn't have TRAIN scores; fit on SCORE data as fallback
                cal_river = fuse.ScoreCalibrator(q=cal_q, self_tune_cfg=self_tune_cfg).fit(
                    frame["river_hst_raw"].to_numpy(copy=False), regime_labels=transform_regimes
                )
                frame["river_hst_z"] = cal_river.transform(
                    frame["river_hst_raw"].to_numpy(copy=False), regime_labels=transform_regimes
                )

            # Compute TRAIN z-scores for PCA metrics (needed for SQL metadata)
            # Robust to cache reuse - uses train_frame which is always computed
            pca_train_spe_z = cal_pca_spe.transform(
                train_frame["pca_spe"].to_numpy(dtype=np.float32), regime_labels=fit_regimes
            )
            pca_train_t2_z = cal_pca_t2.transform(
                train_frame["pca_t2"].to_numpy(dtype=np.float32), regime_labels=fit_regimes
            )
            spe_p95_train = float(np.nanpercentile(pca_train_spe_z, 95))
            t2_p95_train = float(np.nanpercentile(pca_train_t2_z, 95))
            
            calibrators: List[Tuple[str, fuse.ScoreCalibrator]] = [
                ("ar1_z", cal_ar),
                ("pca_spe_z", cal_pca_spe),
                ("pca_t2_z", cal_pca_t2),
                ("mhal_z", cal_mhal),
                ("iforest_z", cal_if),
                ("gmm_z", cal_gmm),
            ]
            if omr_enabled and "omr_raw" in frame.columns:
                calibrators.append(("omr_z", cal_omr))
            if "river_hst_raw" in frame.columns:
                calibrators.append(("river_hst_z", cal_river))

            # DET-07: Generate per-regime threshold transparency table
            if quality_ok and use_per_regime:
                Console.info("[CAL] Generating per-regime threshold table...")
                per_regime_rows = []
                for detector_name, calibrator in calibrators:
                    for regime_id in sorted(calibrator.regime_thresh_.keys()):
                        med_r, scale_r = calibrator.regime_params_[regime_id]
                        thresh_z = calibrator.regime_thresh_[regime_id]
                        per_regime_rows.append({
                            "detector": detector_name,
                            "regime": int(regime_id),
                            "median": float(med_r),
                            "scale": float(scale_r),
                            "z_threshold": float(thresh_z),
                            "global_median": float(calibrator.med),
                            "global_scale": float(calibrator.scale),
                        })
                
                if per_regime_rows:
                    # Convert to pandas DataFrame (output_mgr expects pandas)
                    per_regime_df = pd.DataFrame(per_regime_rows)
                    tables_dir = run_dir / "tables"
                    tables_dir.mkdir(parents=True, exist_ok=True)
                    per_regime_path = tables_dir / "per_regime_thresholds.csv"
                    output_mgr.write_dataframe(per_regime_df, per_regime_path)
                    Console.info(f"[CAL] Wrote per-regime thresholds: {len(per_regime_rows)} regime-detector pairs")

            # ANA-09: Always write thresholds table with global fallback
            threshold_rows: List[Dict[str, Any]] = []
            for detector_name, calibrator in calibrators:
                threshold_rows.append({
                    "detector": detector_name,
                    "regime": "GLOBAL",
                    "median": float(calibrator.med),
                    "scale": float(calibrator.scale),
                    "z_threshold": float(calibrator.q_z),
                    "raw_threshold": float(calibrator.q_thresh),
                })
                for regime_id, regime_thresh in calibrator.regime_thresh_.items():
                    med_r, scale_r = calibrator.regime_params_.get(regime_id, (calibrator.med, calibrator.scale))
                    threshold_rows.append({
                        "detector": detector_name,
                        "regime": int(regime_id),
                        "median": float(med_r),
                        "scale": float(scale_r),
                        "z_threshold": float(regime_thresh),
                        "raw_threshold": float(med_r + regime_thresh * max(scale_r, 1e-9)),
                    })

            if threshold_rows:
                tables_dir = run_dir / "tables"
                tables_dir.mkdir(parents=True, exist_ok=True)
                thresholds_df = pd.DataFrame(threshold_rows)
                thresholds_path = tables_dir / "acm_thresholds.csv"
                output_mgr.write_dataframe(thresholds_df, thresholds_path)
                Console.info(f"[CAL] Wrote thresholds table with {len(threshold_rows)} rows -> {thresholds_path.name}")

        # ===== 6) Fusion + episodes =====
        with T.section("fusion"): # type: ignore
            # Remove pca_recon_z and rebalance weights
            default_w = {
                "pca_spe_z": 0.35,
                "ar1_z": 0.20,
                "mhal_z": 0.20,
                "iforest_z": 0.20,
                "gmm_z": 0.05,
                "omr_z": 0.0,  # OMR-02: Disabled by default (enable in config for testing)
                "river_hst_z": 0.10,  # only if present
            }
            weights = (cfg or {}).get("fusion", {}).get("weights", default_w)
            fusion_weights_used = dict(weights)
            avail = set(frame.columns)
            
            # CRITICAL FIX #10: Validate weights keys against available detectors BEFORE fusion
            # This prevents KeyError crashes from misconfigured weights
            invalid_keys = [k for k in weights.keys() if not k.endswith('_z')]
            if invalid_keys:
                raise ValueError(f"[FUSE] Invalid detector keys in fusion.weights: {invalid_keys}. "
                               f"All keys must end with '_z' (e.g., 'ar1_z', 'pca_spe_z')")
            
            missing = [k for k in weights.keys() if k not in avail]
            if missing:
                Console.warn(f"[FUSE] Ignoring missing streams: {missing}; available={sorted([c for c in avail if c.endswith('_z')])}")
            present = {k: frame[k].to_numpy(copy=False) for k in weights.keys() if k in avail}
            if not present:
                raise RuntimeError("[FUSE] No valid input streams for fusion. Check your fusion.weights keys or ensure detectors are enabled.")
            
            # FUSE-11: Dynamic weight normalization for present streams only
            # Remove weights for missing detectors and renormalize
            if missing:
                # Build new weights dict with only present detectors
                present_weights = {k: weights[k] for k in present.keys()}
                total_present = sum(present_weights.values())
                
                if total_present > 0:
                    # Renormalize to sum to 1.0
                    weights = {k: v / total_present for k, v in present_weights.items()}
                    Console.info(f"[FUSE] Dynamic normalization: {len(missing)} detector(s) absent, renormalized {len(weights)} weights")
                else:
                    # All weights were zero - use equal weighting
                    equal_weight = 1.0 / len(present)
                    weights = {k: equal_weight for k in present.keys()}
                    Console.warn(f"[FUSE] All configured weights were 0.0, using equal weighting ({equal_weight:.3f} each)")
                
                fusion_weights_used = dict(weights)
            
            # FUSE-10: Load previous weights for warm-start (persistent learning)
            previous_weights = None
            if run_dir:
                try:
                    # Look for previous weight_tuning.json in equipment's artifact folder
                    equipment_artifact_root = run_dir.parent
                    prev_runs = sorted([d for d in equipment_artifact_root.glob("run_*") if d.is_dir()], reverse=True)
                    
                    # Skip current run, look for most recent previous run
                    for prev_run_dir in prev_runs[1:] if len(prev_runs) > 1 else []:
                        prev_tune_path = prev_run_dir / "tables" / "weight_tuning.json"
                        if prev_tune_path.exists():
                            with open(prev_tune_path, 'r') as f:
                                prev_data = json.load(f)
                                previous_weights = prev_data.get("tuned_weights", {})
                                Console.info(f"[TUNE] Loaded previous weights from {prev_tune_path.name}")
                                break
                except Exception as load_e:
                    Console.warn(f"[TUNE] Failed to load previous weights: {load_e}")
            
            # Use previous weights as starting point if available
            if previous_weights:
                # Warm-start: blend config weights with learned weights (favor learned)
                warm_start_lr = float((cfg or {}).get("fusion", {}).get("auto_tune", {}).get("warm_start_lr", 0.7))
                weights = {k: (1 - warm_start_lr) * weights.get(k, 0.0) + warm_start_lr * previous_weights.get(k, weights.get(k, 0.0)) 
                          for k in weights.keys()}
                # Normalize
                total = sum(weights.values())
                if total > 0:
                    weights = {k: v / total for k, v in weights.items()}
                Console.info(f"[TUNE] Warm-start blending: warm_start_lr={warm_start_lr:.2f}")
            
            # DET-06: Auto-tune weights before fusion
            tuned_weights = None
            tuning_diagnostics = None
            with T.section("fusion.auto_tune"):
                try:
                    # First fusion pass with current weights to get baseline
                    fused_baseline, _ = fuse.combine(present, weights, cfg, original_features=score)
                    fused_baseline_np = np.asarray(fused_baseline, dtype=np.float32).reshape(-1)
                    
                    # Tune weights based on episode separability (not circular correlation)
                    tuned_weights, tuning_diagnostics = fuse.tune_detector_weights(
                        streams=present,
                        fused=fused_baseline_np,
                        current_weights=weights,
                        cfg=cfg
                    )
                    
                    # Use tuned weights if tuning was enabled
                    if tuning_diagnostics.get("enabled"):
                        weights = tuned_weights
                        fusion_weights_used = dict(tuned_weights)
                        Console.info("[TUNE] Using auto-tuned weights for final fusion")
                        
                        # Save tuning diagnostics to tables/weight_tuning.json
                        if tuning_diagnostics and run_dir:
                            try:
                                tables_dir = run_dir / "tables"
                                tables_dir.mkdir(parents=True, exist_ok=True)
                                tune_path = tables_dir / "weight_tuning.json"
                                
                                # Add timestamp and metadata
                                tuning_diagnostics["timestamp"] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')  # CHART-04: Standard format
                                # ANA-01: config_weights already captured in tune_detector_weights(), don't overwrite!
                                # tuning_diagnostics["config_weights"] is set in fuse.py and reflects the ORIGINAL config
                                tuning_diagnostics["warm_started"] = previous_weights is not None
                                if previous_weights:
                                    tuning_diagnostics["previous_weights"] = previous_weights
                                
                                if not SQL_MODE:
                                    with open(tune_path, 'w') as f:
                                        json.dump(tuning_diagnostics, f, indent=2)
                                    Console.info(f"[TUNE] Saved tuning diagnostics -> {tune_path}")
                                
                                # FUSE-12: Export fusion metrics to CSV for QA regression testing
                                metrics_rows = []
                                for detector_name, weight in fusion_weights_used.items():
                                    det_metrics = tuning_diagnostics.get("detector_metrics", {}).get(detector_name, {})
                                    metrics_rows.append({
                                        "detector_name": detector_name,
                                        "weight": weight,
                                        "n_samples": det_metrics.get("n_samples", 0),
                                        "quality_score": det_metrics.get("quality_score", 0.0),
                                        "tuning_method": tuning_diagnostics.get("method", "unknown"),
                                        "timestamp": tuning_diagnostics["timestamp"]
                                    })
                                
                                if metrics_rows:
                                    metrics_df = pd.DataFrame(metrics_rows)
                                    metrics_path = tables_dir / "fusion_metrics.csv"
                                    if not SQL_MODE:
                                        metrics_df.to_csv(metrics_path, index=False)
                                        Console.info(f"[TUNE] Saved fusion metrics -> {metrics_path}")
                            except Exception as save_e:
                                Console.warn(f"[TUNE] Failed to save diagnostics: {save_e}")
                except Exception as tune_e:
                    Console.warn(f"[TUNE] Weight auto-tuning failed: {tune_e}")
            
            fused, episodes = fuse.combine(present, weights, cfg, original_features=score)
            fused_np = np.asarray(fused, dtype=np.float32).reshape(-1)
            if fused_np.shape[0] != len(frame.index):
                raise RuntimeError(f"[FUSE] Fused length {fused_np.shape[0]} != frame length {len(frame.index)}")
            frame["fused"] = fused_np

        regime_stats: Dict[int, Dict[str, float]] = {}
        if not regime_quality_ok and "regime_label" in frame.columns:
            Console.warn("[REGIME] Per-regime thresholds disabled (quality low).")
            frame["regime_state"] = "unknown"
        if regime_model is not None and regime_quality_ok and "regime_label" in frame.columns and "fused" in frame.columns:
            try:
                regime_stats = regimes.update_health_labels(regime_model, frame["regime_label"].to_numpy(copy=False), frame["fused"], cfg)
                frame["regime_state"] = frame["regime_label"].map(lambda x: regime_model.health_labels.get(int(x), "unknown"))
                summary_df = regimes.build_summary_dataframe(regime_model)
                if not summary_df.empty and run_dir is not None:
                    tables_dir = run_dir / "tables"
                    tables_dir.mkdir(parents=True, exist_ok=True)
                    # Use OutputManager for efficient writing
                    output_mgr = output_manager
                    output_mgr.write_dataframe(summary_df, tables_dir / "regime_summary.csv")
            except Exception as e:
                Console.warn(f"[REGIME] Health labelling skipped: {e}")
        if "regime_label" in frame.columns and "regime_state" not in frame.columns:
            frame["regime_state"] = frame["regime_label"].map(lambda _: "unknown")
        
        # REG-06: Transient state detection
        if "regime_label" in frame.columns:
            with T.section("regimes.transient_detection"):
                try:
                    transient_states = regimes.detect_transient_states(
                        data=score,  # Use original score data for ROC calculation
                        regime_labels=frame["regime_label"].to_numpy(copy=False),
                        cfg=cfg
                    )
                    frame["transient_state"] = transient_states
                    
                    # Log distribution
                    transient_counts = frame["transient_state"].value_counts().to_dict() if "transient_state" in frame.columns else {}
                    Console.info(f"[TRANSIENT] Distribution: {transient_counts}")
                except Exception as trans_e:
                    Console.warn(f"[TRANSIENT] Detection failed: {trans_e}")
                    frame["transient_state"] = "unknown"
        
        if regime_stats:
            state_counts = frame["regime_state"].value_counts().to_dict() if "regime_state" in frame.columns else {}
            Console.info(f"[REGIME] state histogram {state_counts}")
        elif not regime_quality_ok:
            Console.warn("[REGIME] Clustering quality below threshold; per-regime thresholds disabled.")

        # ===== Autonomous Parameter Tuning: Update config based on quality =====
        if cfg.get("models", {}).get("auto_tune", True) and not SQL_MODE:
            try:
                from core.model_evaluation import assess_model_quality
                
                # Build regime quality metrics
                regime_quality_metrics = {
                    "silhouette": score_out.get("silhouette", 0.0),
                    "quality_ok": regime_quality_ok
                }
                
                # Perform full quality assessment now that we have scores and episodes
                should_retrain, reasons, quality_report = assess_model_quality(
                    scores=frame,
                    episodes=episodes,
                    regime_quality=regime_quality_metrics,
                    cfg=cfg,
                    cached_manifest=cached_manifest if 'cached_manifest' in locals() else None
                )
                
                if should_retrain:
                    Console.warn(f"[AUTO-TUNE] Quality degradation detected: {', '.join(reasons)}")
                    
                    # Auto-tune parameters based on specific issues
                    tuning_actions = []
                    
                    # Issue 1: High detector saturation → Increase clip_z
                    detector_quality = quality_report.get("metrics", {}).get("detector_quality", {})
                    if detector_quality.get("max_saturation_pct", 0) > 5.0:
                        self_tune_cfg = cfg.get("thresholds", {}).get("self_tune", {})
                        raw_clip_z = self_tune_cfg.get("clip_z", 12.0)
                        try:
                            current_clip_z = float(raw_clip_z)
                        except (TypeError, ValueError):
                            current_clip_z = 12.0

                        # Allow auto-tune to climb toward the same ceiling used during calibration (50 by default)
                        clip_caps = [
                            self_tune_cfg.get("max_clip_z"),
                            cfg.get("model_quality", {}).get("max_clip_z"),
                            50.0,
                        ]
                        clip_cap = 0.0
                        for candidate in clip_caps:
                            if candidate is None:
                                continue
                            try:
                                clip_cap = max(clip_cap, float(candidate))
                            except (TypeError, ValueError):
                                continue
                        clip_cap = max(clip_cap, current_clip_z, 20.0)

                        proposed_clip = round(current_clip_z * 1.2, 2)
                        if proposed_clip <= current_clip_z + 0.05:
                            # Guard against stagnation when current clip already large
                            proposed_clip = current_clip_z + 2.0

                        new_clip_z = min(proposed_clip, clip_cap)

                        if new_clip_z > current_clip_z + 0.05:
                            # Config immutability: record proposed change only; do not mutate cfg in-run
                            tuning_actions.append(f"thresholds.self_tune.clip_z: {current_clip_z:.2f}->{new_clip_z:.2f}")
                        else:
                            if current_clip_z >= clip_cap - 0.05:
                                Console.warn(
                                    f"[AUTO-TUNE] Clip_z already at ceiling {clip_cap:.2f} while saturation is {detector_quality.get('max_saturation_pct'):.1f}%"
                                )
                            else:
                                Console.info("[AUTO-TUNE] Clip limit already near target, no change applied")
                    
                    # Issue 2: High anomaly rate → Increase k_sigma/h_sigma
                    anomaly_metrics = quality_report.get("metrics", {}).get("anomaly_metrics", {})
                    if anomaly_metrics.get("anomaly_rate", 0) > 0.10:
                        raw_k_sigma = cfg.get("episodes", {}).get("cpd", {}).get("k_sigma", 2.0)
                        try:
                            current_k = float(raw_k_sigma)
                        except (TypeError, ValueError):
                            current_k = 2.0
                        new_k = min(round(current_k * 1.1, 3), 4.0)  # Increase by 10%, cap at 4.0
                        if new_k > current_k + 0.05:
                            # Config immutability: record proposed change only; do not mutate cfg in-run
                            tuning_actions.append(f"episodes.cpd.k_sigma: {current_k:.3f}->{new_k:.3f}")
                        else:
                            Console.info("[AUTO-TUNE] k_sigma already increased recently, skipping change")
                    
                    # Issue 3: Low regime quality → Increase k_max
                    regime_metrics = quality_report.get("metrics", {}).get("regime_metrics", {})
                    if regime_metrics.get("silhouette", 1.0) < 0.15:
                        auto_k_cfg = cfg.get("regimes", {}).get("auto_k", {})
                        raw_k_max = auto_k_cfg.get("k_max", cfg.get("regimes", {}).get("k_max", 8))
                        try:
                            current_k_max = int(raw_k_max)
                        except (TypeError, ValueError):
                            try:
                                current_k_max = int(float(raw_k_max))
                            except Exception:
                                current_k_max = 8
                        new_k_max = min(current_k_max + 2, 12)  # Increase by 2, cap at 12
                        if new_k_max > current_k_max:
                            # Config immutability: record proposed change only; do not mutate cfg in-run
                            tuning_actions.append(f"regimes.auto_k.k_max: {current_k_max}->{int(new_k_max)}")
                        else:
                            Console.info("[AUTO-TUNE] k_max already at configured ceiling, no change applied")
                    
                    if tuning_actions:
                        Console.info(f"[AUTO-TUNE] Applied {len(tuning_actions)} parameter adjustments: {', '.join(tuning_actions)}")
                        Console.info(f"[AUTO-TUNE] Retraining required on next run to apply changes")
                        
                        # Log config changes to ACM_ConfigHistory
                        try:
                            if sql_client and run_id:
                                log_auto_tune_changes(
                                    sql_client=sql_client,
                                    equip_id=int(equip_id),
                                    tuning_actions=tuning_actions,
                                    run_id=run_id
                                )
                        except Exception as log_err:
                            Console.warn(f"[CONFIG_HIST] Failed to log auto-tune changes: {log_err}")
                    else:
                        Console.info(f"[AUTO-TUNE] No automatic parameter adjustments available")

                    # Persist a refit marker so next run bypasses cache even if params unchanged
                    try:
                        # Atomic write: create temp then replace
                        if not SQL_MODE:
                            tmp_path = refit_flag_path.with_suffix(".pending")
                            with tmp_path.open("w", encoding="utf-8") as rf:
                                rf.write(f"requested_at={pd.Timestamp.now().isoformat()}\n")
                                rf.write(f"reasons={'; '.join(reasons)}\n")
                            try:
                                import os
                                os.replace(tmp_path, refit_flag_path)
                            except Exception:
                                # Fallback to rename on platforms without os.replace edge cases
                                tmp_path.rename(refit_flag_path)
                            Console.info(f"[MODEL] Refit flag written atomically -> {refit_flag_path}")
                    except Exception as re:
                        Console.warn(f"[MODEL] Failed to write refit flag: {re}")
                
                else:
                    Console.info(f"[AUTO-TUNE] Model quality acceptable, no tuning needed")
                    
            except Exception as e:
                Console.warn(f"[AUTO-TUNE] Autonomous tuning failed: {e}")

        if reuse_models:
                cache_payload = {
                    "ar1": ar1_detector,
                    "pca": pca_detector,
                    "mhal": mhal_detector,
                    "iforest": iforest_detector,
                    "gmm": gmm_detector,
                    "omr": omr_detector,
                    "train_columns": current_train_columns,
                    "train_hash": train_feature_hash,
                    "config_signature": config_signature,
                    "regime_model": regime_model,
                    "regime_basis_hash": regime_basis_hash,
                    "regime_quality_ok": regime_quality_ok,
                }

        # ===== 7) Drift =====
        with T.section("drift"):
            score_out["frame"] = frame # type: ignore
            score_out = drift.compute(score, score_out, cfg)
            frame = score_out["frame"]

        # DRIFT-01: Multi-Feature Drift Detection (replaces simple P95 threshold)
        # Combines drift trend, fused level, and regime volatility with hysteresis to distinguish
        # gradual drift (requires retraining) from transient faults (does not require retraining)
        drift_col = "cusum_z" if "cusum_z" in frame.columns else ("drift_z" if "drift_z" in frame.columns else None)
        
        # Retrieve multi-feature drift configuration
        drift_cfg = (cfg or {}).get("drift", {})
        multi_feat_cfg = drift_cfg.get("multi_feature", {})
        multi_feat_enabled = bool(multi_feat_cfg.get("enabled", False))
        
        if drift_col is not None:
            try:
                drift_array = frame[drift_col].to_numpy(dtype=np.float32)
                
                if multi_feat_enabled:
                    # DRIFT-01: Multi-feature logic with hysteresis
                    # Configuration parameters
                    trend_window = int(multi_feat_cfg.get("trend_window", 20))
                    trend_threshold = float(multi_feat_cfg.get("trend_threshold", 0.05))  # Slope per sample
                    fused_drift_min = float(multi_feat_cfg.get("fused_drift_min", 2.0))    # P95 min for drift
                    fused_drift_max = float(multi_feat_cfg.get("fused_drift_max", 5.0))    # P95 max for drift
                    regime_volatility_max = float(multi_feat_cfg.get("regime_volatility_max", 0.3))
                    hysteresis_on = float(multi_feat_cfg.get("hysteresis_on", 3.0))         # Turn ON drift alert
                    hysteresis_off = float(multi_feat_cfg.get("hysteresis_off", 1.5))       # Turn OFF drift alert
                    
                    # Compute features
                    drift_trend = _compute_drift_trend(drift_array, window=trend_window)
                    fused_p95 = float(np.nanpercentile(frame["fused"].to_numpy(dtype=np.float32), 95)) if "fused" in frame.columns else 0.0
                    
                    # Compute regime volatility if regime labels exist
                    regime_volatility = 0.0
                    if "regime_label" in frame.columns and regime_quality_ok:
                        regime_labels = frame["regime_label"].to_numpy()
                        regime_volatility = _compute_regime_volatility(regime_labels, window=trend_window)
                    
                    # Composite rule: DRIFT if all conditions met
                    # 1. Positive drift trend (sustained upward movement)
                    # 2. Fused level in drift range (not too high = fault, not too low = normal)
                    # 3. Low regime volatility (stable operating conditions)
                    drift_p95 = float(np.nanpercentile(drift_array, 95))
                    
                    # Get previous alert_mode (if exists) for hysteresis
                    # In first run or if unavailable, assume "FAULT"
                    prev_alert_mode = "FAULT"
                    # Note: In production, could load from prior run's final frame or maintain state
                    
                    # Apply hysteresis: different thresholds for turning ON vs OFF
                    is_drift_condition = (
                        abs(drift_trend) > trend_threshold and       # Sustained trend (up or down)
                        fused_drift_min <= fused_p95 <= fused_drift_max and  # In drift severity range
                        regime_volatility < regime_volatility_max     # Stable regime
                    )
                    
                    # Hysteresis logic
                    if prev_alert_mode == "DRIFT":
                        # Currently in DRIFT: turn OFF if drift_p95 drops below hysteresis_off
                        alert_mode = "DRIFT" if drift_p95 > hysteresis_off else "FAULT"
                    else:
                        # Currently in FAULT: turn ON if drift_p95 exceeds hysteresis_on AND conditions met
                        alert_mode = "DRIFT" if (drift_p95 > hysteresis_on and is_drift_condition) else "FAULT"
                    
                    frame["alert_mode"] = alert_mode
                    Console.info(
                        f"[DRIFT] Multi-feature: {drift_col} P95={drift_p95:.3f}, trend={drift_trend:.4f}, "
                        f"fused_P95={fused_p95:.3f}, regime_vol={regime_volatility:.3f} -> {alert_mode}"
                    )
                else:
                    # Fallback to legacy simple threshold (CFG-06)
                    drift_p95 = float(np.nanpercentile(drift_array, 95))
                    drift_threshold = float(drift_cfg.get("p95_threshold", 2.0))
                    frame["alert_mode"] = "DRIFT" if drift_p95 > drift_threshold else "FAULT"
                    Console.info(f"[DRIFT] {drift_col} P95={drift_p95:.3f} (threshold={drift_threshold:.1f}) -> alert_mode={frame['alert_mode'].iloc[-1]}")
            except Exception as e:
                Console.warn(f"[DRIFT] Detection failed: {e}")
                frame["alert_mode"] = "FAULT"
        else:
            frame["alert_mode"] = "FAULT"

        # --- Normalize episodes schema for report/export ------------
        # Defensive copy: ensure episodes is a DataFrame before .copy()
        episodes = (episodes if isinstance(episodes, pd.DataFrame) else pd.DataFrame()).copy()
        if "episode_id" not in episodes.columns:
            episodes.insert(0, "episode_id", np.arange(1, len(episodes) + 1, dtype=int))
        if "severity" not in episodes.columns:
            episodes["severity"] = "info"
        if "regime" not in episodes.columns:
            episodes["regime"] = ""
        if "start_ts" not in episodes.columns:
            episodes["start_ts"] = pd.NaT
        if "end_ts" not in episodes.columns:
            episodes["end_ts"] = pd.NaT
        start_idx_series = episodes.get("start")
        end_idx_series = episodes.get("end")
        # Ensure frame is sorted before any indexing operations
        if not frame.index.is_monotonic_increasing:
            Console.warn("[EPISODE] Sorting frame index for timestamp mapping")
            frame = frame.sort_index()
        idx_array = frame.index.to_numpy()

        # Prefer nearest mapping; preserve NaT (avoid clip-to-zero artefacts)
        if start_idx_series is None:
            # CRITICAL FIX: Deduplicate frame index before episode mapping to prevent aggregation errors
            if not frame.index.is_unique:
                Console.warning(f"[EPISODES] Deduplicating {len(frame)} - {frame.index.nunique()} = {len(frame) - frame.index.nunique()} duplicate timestamps")
                frame = frame.groupby(frame.index).first()
                idx_array = frame.index.to_numpy()  # Update after deduplication

            start_positions = _nearest_indexer(frame.index, episodes["start_ts"], label="EPISODE.start")
            start_idx_series = pd.Series(start_positions, index=episodes.index, dtype="int64")
        if end_idx_series is None:
            end_positions = _nearest_indexer(frame.index, episodes["end_ts"], label="EPISODE.end")
            end_idx_series = pd.Series(end_positions, index=episodes.index, dtype="int64")
        start_idx_series = start_idx_series.fillna(-1).astype(int)
        end_idx_series = end_idx_series.fillna(-1).astype(int)
        if len(idx_array):
            start_idx = start_idx_series.clip(-1, len(idx_array) - 1).to_numpy()
            end_idx = end_idx_series.clip(-1, len(idx_array) - 1).to_numpy()
            s_idx_safe = np.where(start_idx >= 0, start_idx, 0)
            e_idx_safe = np.where(end_idx >= 0, end_idx, 0)
            # Create datetime arrays, use pd.NaT for invalid indices
            start_times = idx_array[s_idx_safe]
            end_times = idx_array[e_idx_safe]
            episodes["start_ts"] = pd.Series(start_times, index=episodes.index, dtype='datetime64[ns]')
            episodes["end_ts"] = pd.Series(end_times, index=episodes.index, dtype='datetime64[ns]')
            # Set NaT for invalid indices
            episodes.loc[start_idx < 0, "start_ts"] = pd.NaT
            episodes.loc[end_idx < 0, "end_ts"] = pd.NaT
        else:
            start_idx = np.zeros(len(episodes), dtype=int)
            end_idx = np.zeros(len(episodes), dtype=int)
            episodes["start_ts"] = pd.NaT
            episodes["end_ts"] = pd.NaT

        label_series = frame.get("regime_label")
        state_series = frame.get("regime_state")
        if label_series is not None:
            label_array = label_series.to_numpy()
            state_array = state_series.to_numpy() if state_series is not None else None
            regime_vals: List[Any] = []
            regime_states: List[str] = []
            for s_idx, e_idx in zip(start_idx, end_idx):
                if len(label_array) == 0:
                    regime_vals.append(-1)
                    regime_states.append("unknown")
                    continue
                s_clamped = int(np.clip(s_idx, 0, len(label_array) - 1))
                e_clamped = int(np.clip(e_idx, 0, len(label_array) - 1))
                if e_clamped < s_clamped:
                    e_clamped = s_clamped
                slice_labels = label_array[s_clamped:e_clamped + 1]
                if slice_labels.size:
                    counts = np.bincount(slice_labels.astype(int))
                    majority_label = int(np.argmax(counts))
                else:
                    majority_label = -1
                regime_vals.append(majority_label)
                if state_array is not None and slice_labels.size:
                    slice_states = state_array[s_clamped:e_clamped + 1]
                    values, counts = np.unique(slice_states, return_counts=True)
                    majority_state = str(values[np.argmax(counts)])
                else:
                    majority_state = "unknown"
                regime_states.append(majority_state)
            episodes["regime"] = regime_vals
            episodes["regime_state"] = regime_states
        else:
            episodes["regime_state"] = "unknown"

        severity_map = {"critical": "critical", "suspect": "warning", "warning": "warning"}
        severity_override = episodes["regime_state"].map(lambda s: severity_map.get(str(s)))
        episodes["severity"] = severity_override.fillna(episodes["severity"])

        # Ensure both timestamps are parsed before subtraction
        start_ts = pd.to_datetime(episodes["start_ts"], errors="coerce")
        end_ts = pd.to_datetime(episodes["end_ts"], errors="coerce")
        episodes["duration_s"] = (end_ts - start_ts).dt.total_seconds()
        # Convenience: duration in hours for operator tables
        try:
            episodes["duration_hours"] = episodes["duration_s"].astype(float) / 3600.0
        except Exception:
            episodes["duration_hours"] = np.where(pd.notna(episodes.get("duration_s")), episodes.get("duration_s").astype(float) / 3600.0, 0.0)
        episodes = episodes.sort_values(["start_ts", "end_ts", "episode_id"]).reset_index(drop=True)
        episodes["regime"] = episodes["regime"].astype(str)

        # ===== Rolling Baseline Buffer: Update with latest raw SCORE =====
        try:
            baseline_cfg = (cfg.get("runtime", {}) or {}).get("baseline", {}) or {}
            buffer_path = stable_models_dir / "baseline_buffer.csv"
            if isinstance(score_numeric, pd.DataFrame) and len(score_numeric):
                to_append = score_numeric.copy()
                # Normalize index to local naive timestamps for stable CSV format
                try:
                    idx_local = pd.DatetimeIndex(to_append.index).tz_localize(None)
                except Exception:
                    idx_local = pd.DatetimeIndex(to_append.index)
                to_append.index = idx_local

                if buffer_path.exists():
                    try:
                        prev = pd.read_csv(buffer_path, index_col=0, parse_dates=True)
                    except Exception:
                        prev = pd.DataFrame()
                    # Keep only common columns to avoid drift issues
                    common = [c for c in prev.columns if c in to_append.columns]
                    if common:
                        prev = prev[common]
                        to_append = to_append[common]
                    combined = pd.concat([prev, to_append], axis=0)
                else:
                    combined = to_append

                # Normalize index to local-naive consistently, drop dups, sort
                try:
                    norm_idx = pd.to_datetime(combined.index, errors="coerce")
                except Exception:
                    norm_idx = pd.DatetimeIndex(combined.index)
                combined.index = norm_idx
                combined = combined[~combined.index.duplicated(keep="last")].sort_index()

                # Retention: window_hours and/or max_points
                window_hours = float(baseline_cfg.get("window_hours", 72))
                max_points = int(baseline_cfg.get("max_points", 100000))
                if len(combined):
                    last_ts = pd.to_datetime(combined.index.max())
                    if window_hours and window_hours > 0:
                        cutoff = last_ts - pd.Timedelta(hours=window_hours)
                        combined = combined[combined.index >= cutoff]
                    if max_points and max_points > 0 and len(combined) > max_points:
                        combined = combined.iloc[-max_points:]

                # CHART-04: Use uniform timestamp format without 'T' or 'Z' suffixes (file-mode only)
                if not SQL_MODE:
                    combined.to_csv(buffer_path, index=True, date_format="%Y-%m-%d %H:%M:%S")
                    Console.info(f"[BASELINE] Updated rolling baseline buffer -> {buffer_path} rows={len(combined)} cols={len(combined.columns)}")
                
                # Write to SQL ACM_BaselineBuffer table if in SQL mode
                if sql_client and SQL_MODE:
                    try:
                        # Transform wide format (timestamp × sensors) to long format (rows per sensor-timestamp)
                        baseline_records = []
                        for ts_idx, row in combined.iterrows():
                            for sensor_name, sensor_value in row.items():
                                if pd.notna(sensor_value):
                                    baseline_records.append((
                                        int(equip_id),
                                        pd.Timestamp(ts_idx).to_pydatetime().replace(tzinfo=None),
                                        str(sensor_name),
                                        float(sensor_value),
                                        None  # DataQuality (future enhancement)
                                    ))
                    
                        if baseline_records:
                            # Bulk insert with fast_executemany
                            insert_sql = """
                            INSERT INTO dbo.ACM_BaselineBuffer (EquipID, Timestamp, SensorName, SensorValue, DataQuality)
                            VALUES (?, ?, ?, ?, ?)
                            """
                            with sql_client.cursor() as cur:
                                cur.fast_executemany = True
                                cur.executemany(insert_sql, baseline_records)
                            sql_client.conn.commit()
                            Console.info(f"[BASELINE] Wrote {len(baseline_records)} records to ACM_BaselineBuffer")
                        
                            # Run cleanup procedure to maintain retention policy
                            try:
                                with sql_client.cursor() as cur:
                                    cur.execute("EXEC dbo.usp_CleanupBaselineBuffer @EquipID=?, @RetentionHours=?, @MaxRowsPerEquip=?",
                                              (int(equip_id), int(window_hours), max_points))
                                sql_client.conn.commit()
                            except Exception as cleanup_err:
                                Console.warn(f"[BASELINE] Cleanup procedure failed: {cleanup_err}")
                    except Exception as sql_err:
                        Console.warn(f"[BASELINE] SQL write to ACM_BaselineBuffer failed: {sql_err}")
                        try:
                            sql_client.conn.rollback()
                        except:
                            pass
        except Exception as be:
            Console.warn(f"[BASELINE] Update failed: {be}")

        sensor_context: Optional[Dict[str, Any]] = None
        with T.section("sensor.context"):
            try:
                if (
                    isinstance(train_numeric, pd.DataFrame)
                    and isinstance(score_numeric, pd.DataFrame)
                    and len(train_numeric)
                    and len(score_numeric)
                ):
                    common_cols = [col for col in score_numeric.columns if col in train_numeric.columns]
                    if common_cols:
                        train_baseline = train_numeric[common_cols].copy()
                        score_baseline = score_numeric[common_cols].copy()
                        train_mean = train_baseline.mean()
                        # CRITICAL FIX #5: Prevent division by zero with safe epsilon fallback
                        train_std = train_baseline.std()
                        train_std = train_std.replace(0.0, np.nan).fillna(1e-10)  # Safe fallback
                        valid_cols = train_std[train_std > 1e-10].index.tolist()  # Only truly valid columns
                        if valid_cols:
                            train_mean = train_mean[valid_cols]
                            train_std = train_std[valid_cols]
                            score_baseline = score_baseline[valid_cols]
                            score_aligned = score_baseline.reindex(frame.index)
                            score_aligned = score_aligned.apply(pd.to_numeric, errors="coerce")
                            sensor_z = (score_aligned - train_mean) / train_std
                            sensor_z = sensor_z.replace([np.inf, -np.inf], np.nan)
                            # Ensure alignment with scoring frame for downstream joins
                            sensor_context = {
                                "values": score_aligned,
                                "z_scores": sensor_z,
                                "train_mean": train_mean,
                                "train_std": train_std,
                                "train_p95": train_baseline[valid_cols].quantile(0.95),
                                "train_p05": train_baseline[valid_cols].quantile(0.05),
                                "omr_contributions": omr_contributions_data,  # Add OMR contributions for visualization
                                "regime_meta": regime_model.meta if regime_model else {}  # Add regime model metadata for chart subtitles
                            }
            except Exception as sensor_ctx_err:
                Console.warn(f"[SENSOR] Failed to build sensor analytics context: {sensor_ctx_err}")
                sensor_context = None

        # ===== 8) Persist artifacts / Finalize (per-mode) =====
        rows_read = int(score.shape[0])
        anomaly_count = int(len(episodes))
        
        # Check if dual-write mode is enabled (write to both file and SQL)
        dual_mode = cfg.get("output", {}).get("dual_mode", False)
        
        # FILE_MODE: Now explicitly enabled via config flag (default is SQL-only)
        file_mode_enabled = cfg.get("output", {}).get("enable_file_mode", False)
        
        if not SQL_MODE and file_mode_enabled:
            # ---------- FILE MODE (or DUAL MODE) ----------
            with T.section("persist"):
                out_log = run_dir / "run.jsonl"
                
                # Use unified OutputManager for all file operations
                # Note: output_manager is already created at the start of main()
                
                with T.section("persist.write_scores"):
                    try:
                        # Write scores using OutputManager
                        output_manager.write_scores(frame, run_dir, enable_sql=dual_mode)
                        
                        # Generate schema.json descriptor for scores.csv
                        try:
                            schema_path = run_dir / "schema.json"
                            schema_dict = {
                                "file": "scores.csv",
                                "description": "ACM anomaly scores with detector outputs and fusion results",
                                "timestamp_column": "index" if frame.index.name is None else frame.index.name,
                                "columns": []
                            }
                            
                            # Document each column with name, dtype, and description
                            for col in frame.columns:
                                col_info = {
                                    "name": str(col),
                                    "dtype": str(frame[col].dtype),
                                    "nullable": bool(frame[col].isnull().any())
                                }
                                
                                # Add semantic descriptions based on column name patterns
                                if col.endswith("_raw"):
                                    col_info["description"] = f"Raw anomaly score from {col.replace('_raw', '')} detector"
                                elif col.endswith("_z"):
                                    col_info["description"] = f"Calibrated z-score from {col.replace('_z', '')} detector"
                                elif col == "fused":
                                    col_info["description"] = "Weighted fusion of all detector z-scores"
                                elif col == "alert_level":
                                    col_info["description"] = "Alert severity: NORMAL, CAUTION, or FAULT"
                                elif col == "alert_mode":
                                    col_info["description"] = "Alert mode based on threshold exceedance"
                                elif col == "regime_label":
                                    col_info["description"] = "Operating regime cluster label (0-based)"
                                elif col == "regime_state":
                                    col_info["description"] = "Regime health state: healthy, suspect, or critical"
                                elif col == "episode_id":
                                    col_info["description"] = "Episode identifier for anomaly periods (NaN outside episodes)"
                                else:
                                    col_info["description"] = f"Column {col}"
                                
                                schema_dict["columns"].append(col_info)
                            
                            # Write schema.json with pretty formatting
                            if not SQL_MODE:
                                with schema_path.open("w", encoding="utf-8") as sf:
                                    json.dump(schema_dict, sf, indent=2, ensure_ascii=False)
                                Console.info(f"[ART] {schema_path}")
                        except Exception as se:
                            Console.warn(f"[IO] Failed to write schema.json: {se}")
                            
                    except Exception as we:
                        Console.warn(f"[IO] Failed to write scores via OutputManager: {we}")

                with T.section("persist.write_score_stream"):
                    try:
                        # Write score stream using OutputManager  
                        stream = frame.copy().reset_index().rename(columns={"index": "ts"})
                        output_manager.write_dataframe(
                            stream, 
                            models_dir / "score_stream.csv",
                            index=False
                        )
                    except Exception as se:
                        Console.warn(f"[IO] Failed to write score_stream via OutputManager: {se}")

                if regime_model is not None:
                    with T.section("persist.regime_model"):
                        try:
                            # Save regime model with joblib persistence (KMeans + Scaler)
                            regimes.save_regime_model(regime_model, models_dir)
                        except Exception as e:
                            Console.warn(f"[REGIME] Failed to persist regime model: {e}")
                        promote_dir: Optional[Path] = None
                        if stable_models_dir and stable_models_dir != models_dir:
                            promote_dir = stable_models_dir

                        if promote_dir and regime_quality_ok:
                            try:
                                regimes.save_regime_model(regime_model, promote_dir)
                                Console.info(f"[REGIME] Promoted regime model to {promote_dir}")
                            except Exception as promote_exc:
                                Console.warn(f"[REGIME] Failed to promote regime model to stable cache: {promote_exc}")
                        elif promote_dir and not regime_quality_ok:
                            Console.info("[REGIME] Skipping stable regime cache update because quality_ok=False")

                with T.section("persist.write_episodes"):
                    try:
                        # Write episodes using OutputManager
                        output_manager.write_episodes(episodes, run_dir, enable_sql=dual_mode)
                    except Exception as ee:
                        Console.warn(f"[IO] Failed to write episodes via OutputManager: {ee}")
                # Emit a lightweight culprits.jsonl for episode-level attribution
                with T.section("persist.write_culprits"):
                    try:
                        if not SQL_MODE:
                            culprits_path = run_dir / "culprits.jsonl"
                            with culprits_path.open("w", encoding="utf-8") as cj:
                                for _, row in episodes.iterrows():
                                    # CHART-04: Use uniform timestamp format without 'T' or 'Z' suffixes
                                    start_ts_val = row.get("start_ts")
                                    end_ts_val = row.get("end_ts")
                                    start_ts_str = None
                                    end_ts_str = None
                                    if pd.notna(start_ts_val):
                                        start_dt = pd.to_datetime(start_ts_val, errors="coerce")
                                        if pd.notna(start_dt):
                                            start_ts_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
                                    if pd.notna(end_ts_val):
                                        end_dt = pd.to_datetime(end_ts_val, errors="coerce")
                                        if pd.notna(end_dt):
                                            end_ts_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")
                                    
                                    rec = {
                                    "start_ts": start_ts_str,
                                    "end_ts": end_ts_str,
                                    "duration_hours": float(row.get("duration_hours", np.nan)) if pd.notna(row.get("duration_hours", np.nan)) else None,
                                    "culprits": row.get("culprits", ""),
                                    "method": "episode_primary_detector"
                                }
                                cj.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        if not SQL_MODE:
                            Console.info(f"[ART] {culprits_path}")
                    except Exception as ce:
                        Console.warn(f"[IO] Failed to write culprits.jsonl: {ce}")
                with T.section("persist.write_runlog"):
                    if not SQL_MODE:
                        with out_log.open("w", encoding="utf-8") as f:
                            f.write(json.dumps({
                                "equip": equip,
                                "rows": int(len(frame)),
                                "kept_cols": meta.kept_cols
                            }, ensure_ascii=False) + "\n")

                if cache_payload:
                    with T.section("persist.cache_detectors"):
                        try:
                            joblib.dump(cache_payload, model_cache_path)
                            Console.info(f"[MODEL] Cached detectors to {model_cache_path}")
                        except Exception as e:
                            Console.warn(f"[MODEL] Failed to cache detectors: {e}")

            Console.info(f"[OK] rows={len(frame)} heads={','.join([c for c in frame.columns if c.endswith('_z')])} episodes={len(episodes)}")
            Console.info(f"[ART] {run_dir / 'scores.csv'}") # type: ignore
            Console.info(f"[ART] {run_dir / 'episodes.csv'}")

            # === COMPREHENSIVE ANALYTICS GENERATION ===
            try:
                # Use OutputManager directly for all output operations
                tables_dir = run_dir / "tables"
                tables_dir.mkdir(exist_ok=True)

                with T.section("outputs.comprehensive_analytics"):
                    # Generate comprehensive analytics tables using OutputManager
                    Console.info("[ANALYTICS] Generating comprehensive analytics tables...")
                    
                    try:
                        # Generate all 23+ analytical tables
                        output_manager.generate_all_analytics_tables(
                            scores_df=frame,
                            episodes_df=episodes,
                            cfg=cfg,
                            tables_dir=tables_dir,
                            sensor_context=sensor_context
                        )
                        Console.info("[ANALYTICS] Successfully generated all comprehensive analytics tables")
                        table_count = 23  # Comprehensive table count
                    except Exception as e:
                        Console.error(f"[ANALYTICS] Error generating comprehensive analytics: {str(e)}")
                        # Fallback to basic tables
                        Console.info("[ANALYTICS] Falling back to basic table generation...")
                        table_count = 0
                        
                        # Health timeline (if we have fused scores)
                        if 'fused' in frame.columns:
                            health_df = pd.DataFrame({
                                'timestamp': frame.index.strftime('%Y-%m-%d %H:%M:%S'),
                                'fused_z': frame['fused'],
                                'health_index': 100.0 / (1.0 + frame['fused'] ** 2)
                            })
                            output_manager.write_dataframe(health_df, tables_dir / "health_timeline.csv")
                            table_count += 1
                        
                        # Regime timeline (if available)
                        if 'regime_label' in frame.columns:
                            regime_df = pd.DataFrame({
                                'timestamp': frame.index.strftime('%Y-%m-%d %H:%M:%S'),
                                'regime_label': frame['regime_label']
                            })
                            output_manager.write_dataframe(regime_df, tables_dir / "regime_timeline.csv")
                            table_count += 1

                Console.info(f"[OUTPUTS] Generated {table_count} analytics tables via OutputManager")
                Console.info(f"[OUTPUTS] Tables: {tables_dir}")
                
                # === FORECAST GENERATION (enabled by default; opt-out via output.enable_forecast=False) ===
                output_cfg = (cfg.get("output", {}) or {})
                forecast_enabled = bool(output_cfg.get("enable_forecast", True))
                if forecast_enabled:
                    Console.info("[FORECAST] Generating forecast with uncertainty bands...")
                    try:
                        with T.section("outputs.forecast"):
                            charts_dir = run_dir / "charts"
                            charts_dir.mkdir(exist_ok=True)
                            
                            forecast_ctx = {
                                "run_dir": run_dir,
                                "plots_dir": charts_dir,
                                "tables_dir": tables_dir,
                                "config": cfg,
                                "run_id": run_id,
                                "equip_id": int(equip_id) if 'equip_id' in locals() else None
                            }
                            forecast_result = forecast.run(forecast_ctx)
                            if "error" not in forecast_result:
                                Console.info(f"[FORECAST] Generated {len(forecast_result.get('tables', []))} forecast tables and {len(forecast_result.get('plots', []))} plots")
                                if forecast_result.get("metrics"):
                                    metrics = forecast_result["metrics"]
                                    Console.info(f"[FORECAST] Series: {metrics.get('series_used', 'N/A')}, phi={metrics.get('ar1_phi', 0):.3f}, Horizon: {metrics.get('horizon', 0)} ({metrics.get('horizon_hours', 24)}h)")

                                # === RUL + SQL surfacing of forecast ===
                                try:
                                    health_threshold = float(
                                        (cfg.get("analytics", {}) or {}).get(
                                            "health_alert_threshold", 70.0
                                        )
                                    )
                                except Exception:
                                    health_threshold = 70.0
                                try:
                                    rul_tables = rul_estimator.estimate_rul_and_failure(
                                        tables_dir=tables_dir,
                                        equip_id=int(equip_id) if 'equip_id' in locals() else None,
                                        run_id=str(run_id) if run_id is not None else None,
                                        health_threshold=health_threshold,
                                    )
                                    if rul_tables:
                                        Console.info(f"[RUL] Generated {len(rul_tables)} RUL/forecast tables")
                                        enable_sql_rul = getattr(output_manager, "sql_client", None) is not None
                                        for sql_name, df in rul_tables.items():
                                            if df is None or df.empty:
                                                continue
                                            csv_name = {
                                                "ACM_HealthForecast_TS": "health_forecast_ts.csv",
                                                "ACM_FailureForecast_TS": "failure_forecast_ts.csv",
                                                "ACM_RUL_TS": "rul_timeseries.csv",
                                                "ACM_RUL_Summary": "rul_summary.csv",
                                                "ACM_RUL_Attribution": "rul_attribution.csv",
                                                "ACM_MaintenanceRecommendation": "maintenance_recommendation.csv",
                                            }.get(sql_name, f"{sql_name}.csv")
                                            out_path = tables_dir / csv_name
                                            output_manager.write_dataframe(
                                                df,
                                                out_path,
                                                sql_table=sql_name if enable_sql_rul else None,
                                                add_created_at="CreatedAt" not in df.columns,
                                            )
                                except Exception as e:
                                    Console.warn(f"[RUL] RUL estimation failed: {e}")
                                
                                # === ENHANCED FORECASTING (if enabled) ===
                                try:
                                    enhanced_enabled = cfg.get("forecasting", {}).get("enhanced_enabled", True)
                                    if enhanced_enabled:
                                        Console.info("[ENHANCED_FORECAST] Running enhanced forecasting analysis")
                                        enhanced_ctx = {
                                            'run_dir': run_dir,
                                            'tables_dir': tables_dir,
                                            'plots_dir': plots_dir,
                                            'config': cfg,
                                            'run_id': str(run_id) if run_id is not None else None,
                                            'equip_id': int(equip_id) if 'equip_id' in locals() else None
                                        }
                                        enhanced_result = enhanced_forecasting.EnhancedForecastingEngine(cfg).run(enhanced_ctx)
                                        if enhanced_result and enhanced_result.get('tables'):
                                            Console.info(f"[ENHANCED_FORECAST] Generated {len(enhanced_result['tables'])} enhanced tables")
                                            # Tables already written by enhanced_forecasting module
                                        if enhanced_result and enhanced_result.get('metrics'):
                                            metrics = enhanced_result['metrics']
                                            Console.info(f"[ENHANCED_FORECAST] RUL: {metrics.get('rul_hours', 0):.1f}h, "
                                                       f"Max Failure Prob: {metrics.get('max_failure_probability', 0)*100:.1f}%, "
                                                       f"Maintenance Required: {metrics.get('maintenance_required', False)}, "
                                                       f"Urgency: {metrics.get('urgency_score', 0):.0f}/100")
                                except Exception as e:
                                    Console.warn(f"[ENHANCED_FORECAST] Enhanced forecasting failed: {e}")
                            else:
                                Console.warn(f"[FORECAST] {forecast_result['error']['message']}")
                    except Exception as e:
                        Console.warn(f"[FORECAST] Forecast generation failed: {str(e)}")

            except Exception as e:
                Console.warn(f"[OUTPUTS] Output generation failed: {e}")

            # File mode path exits here (finally still runs, no SQL finalize executed).
            run_completion_time = datetime.now()
            _maybe_write_run_meta_json(locals())
            return

        # ---------- SQL MODE: WRITE ARTIFACTS ----------
        
        # === COMPREHENSIVE ANALYTICS GENERATION (SQL MODE) ===
        try:
            # Use OutputManager directly for all output operations
            tables_dir = run_dir / "tables"
            tables_dir.mkdir(exist_ok=True)

            with T.section("outputs.comprehensive_analytics"):
                # Generate comprehensive analytics tables using OutputManager
                Console.info("[ANALYTICS] Generating comprehensive analytics tables...")
                
                try:
                    # Generate all 26 analytical tables with FORCED SQL WRITES
                    result = output_manager.generate_all_analytics_tables(
                        scores_df=frame,
                        episodes_df=episodes,
                        cfg=cfg,
                        tables_dir=tables_dir,
                        enable_sql=True,  # FORCE SQL WRITES
                        sensor_context=sensor_context
                    )
                    Console.info(f"[ANALYTICS] Successfully generated all comprehensive analytics tables")
                    Console.info(f"[ANALYTICS] Written {result.get('sql_tables', 0)} tables to SQL database")
                except Exception as e:
                    Console.error(f"[ANALYTICS] Error generating comprehensive analytics: {str(e)}")

        except Exception as e:
            Console.warn(f"[OUTPUTS] Comprehensive analytics generation failed: {e}")

        # === SQL-SPECIFIC ARTIFACT WRITING (BATCHED TRANSACTION) ===
        # Batch all SQL writes in a single transaction to prevent connection pool exhaustion
        if sql_client:
            with T.section("sql.batch_writes"):
                try:
                    Console.info("[SQL] Starting batched artifact writes...")
                    
                    # 1) ScoresTS: write fused + calibrated z streams (as sensors)
                    rows_scores = 0
                    out_scores_wide = pd.DataFrame(index=frame.index)
                    # Name them explicitly to keep clarity in Grafana
                    if "fused" in frame.columns:       out_scores_wide["ACM_fused"] = frame["fused"]
                    if "pca_spe_z" in frame.columns:   out_scores_wide["ACM_pca_spe_z"] = frame["pca_spe_z"]
                    if "pca_t2_z" in frame.columns:    out_scores_wide["ACM_pca_t2_z"] = frame["pca_t2_z"]
                    if "mhal_z" in frame.columns:      out_scores_wide["ACM_mhal_z"] = frame["mhal_z"]
                    if "iforest_z" in frame.columns:   out_scores_wide["ACM_iforest_z"] = frame["iforest_z"]
                    if "gmm_z" in frame.columns:       out_scores_wide["ACM_gmm_z"] = frame["gmm_z"]
                    if "river_hst_z" in frame.columns: out_scores_wide["ACM_river_hst_z"] = frame["river_hst_z"]

                    if len(out_scores_wide.columns):
                        with T.section("sql.scores.melt"):
                            long_scores = output_manager.melt_scores_long(out_scores_wide, equip_id=equip_id, run_id=run_id or "", source="ACM")
                        with T.section("sql.scores.write"):
                            rows_scores = output_manager.write_scores_ts(long_scores, run_id or "")
                        
                except Exception as e:
                    Console.warn(f"[SQL] Batched SQL writes failed, continuing with individual writes: {e}")
                    rows_scores = 0
        else:
            Console.info("[SQL] No SQL client available, skipping SQL writes")
            rows_scores = 0
            
        # Fallback to individual writes if batching not available
        if sql_client and rows_scores == 0:
            # 1) ScoresTS: write fused + calibrated z streams (as sensors)
            with T.section("sql.scores.individual"):
                rows_scores = 0
                try:
                    out_scores_wide = pd.DataFrame(index=frame.index)
                    # Name them explicitly to keep clarity in Grafana
                    if "fused" in frame.columns:       out_scores_wide["ACM_fused"] = frame["fused"]
                    if "pca_spe_z" in frame.columns:   out_scores_wide["ACM_pca_spe_z"] = frame["pca_spe_z"]
                    if "pca_t2_z" in frame.columns:    out_scores_wide["ACM_pca_t2_z"] = frame["pca_t2_z"]
                    if "mhal_z" in frame.columns:      out_scores_wide["ACM_mhal_z"] = frame["mhal_z"]
                    if "iforest_z" in frame.columns:   out_scores_wide["ACM_iforest_z"] = frame["iforest_z"]
                    if "gmm_z" in frame.columns:       out_scores_wide["ACM_gmm_z"] = frame["gmm_z"]
                    if "river_hst_z" in frame.columns: out_scores_wide["ACM_river_hst_z"] = frame["river_hst_z"]

                    if len(out_scores_wide.columns):
                        with T.section("sql.scores.melt"):
                            long_scores = output_manager.melt_scores_long(out_scores_wide, equip_id=equip_id, run_id=run_id or "", source="ACM")
                        with T.section("sql.scores.write"):
                            rows_scores = output_manager.write_scores_ts(long_scores, run_id or "")
                except Exception as e:
                    Console.warn(f"[SQL] ScoresTS write skipped: {e}")

        # 2) DriftTS (if drift_z exists) — method from config
        rows_drift = 0
        with T.section("sql.drift"):
            try:
                if "drift_z" in frame.columns:
                    drift_method = (cfg.get("drift", {}) or {}).get("method", "CUSUM") # type: ignore
                    df_drift = pd.DataFrame({
                        "EntryDateTime": pd.to_datetime(frame.index),
                        "EquipID": int(equip_id),
                        "DriftZ": frame["drift_z"].astype(np.float32),
                        "Method": drift_method,
                        "RunID": run_id or ""
                    })
                    rows_drift = output_manager.write_drift_ts(df_drift, run_id or "")
            except Exception as e:
                Console.warn(f"[SQL] DriftTS write skipped: {e}")

        # 3) AnomalyEvents (from episodes)
        rows_events = 0
        with T.section("sql.events"):
            try:
                if len(episodes):
                    df_events = pd.DataFrame({
                        "EquipID": int(equip_id),
                        "StartEntryDateTime": episodes["start_ts"],
                        "EndEntryDateTime": episodes["end_ts"],
                        "Severity": episodes.get("severity", pd.Series(["info"]*len(episodes))),
                        "Detector": "FUSION",
                        "Score": episodes.get("score", np.nan),
                        "ContributorsJSON": episodes.get("culprits", "{}"),
                        "RunID": run_id or ""
                    })
                    rows_events = output_manager.write_anomaly_events(df_events, run_id or "")
            except Exception as e:
                Console.warn(f"[SQL] AnomalyEvents write skipped: {e}")

        # 4) RegimeEpisodes
        rows_regimes = 0
        with T.section("sql.regimes"):
            try:
                if len(episodes):
                    df_reg = pd.DataFrame({
                        "EquipID": int(equip_id),
                        "StartEntryDateTime": episodes["start_ts"],
                        "EndEntryDateTime": episodes["end_ts"],
                        "RegimeLabel": episodes.get("regime", pd.Series([""]*len(episodes))),
                        "Confidence": np.nan,
                        "RunID": run_id or ""
                    })
                    rows_regimes = output_manager.write_regime_episodes(df_reg, run_id or "")
            except Exception as e:
                Console.warn(f"[SQL] RegimeEpisodes write skipped: {e}")

        # 5) PCA Model / Loadings / Metrics
        rows_pca_model = rows_pca_load = rows_pca_metrics = 0
        with T.section("sql.pca"):
            try:
                now_utc = pd.Timestamp.now()
                pca_model = getattr(pca_detector, "pca", None) # type: ignore

                # PCA Model row (TRAIN window used)
                var_ratio = getattr(pca_model, "explained_variance_ratio_", None)
                var_json = json.dumps(var_ratio.tolist()) if var_ratio is not None else "[]"
                
                # Use TRAIN-based thresholds computed earlier in calibration section
                # (spe_p95_train, t2_p95_train are already available from TRAIN data)

                # Capture actual scaler type from PCA detector
                scaler_name = pca_detector.scaler.__class__.__name__ if hasattr(pca_detector, 'scaler') else "StandardScaler"
                scaler_params = {}
                if hasattr(pca_detector, 'scaler'):
                    scaler_params["with_mean"] = getattr(pca_detector.scaler, 'with_mean', True)
                    scaler_params["with_std"] = getattr(pca_detector.scaler, 'with_std', True)
                else:
                    scaler_params = {"with_mean": True, "with_std": True}
                
                scaling_spec = json.dumps({"scaler": scaler_name, **scaler_params})
                model_row = {
                    "RunID": run_id or "",
                    "EquipID": int(equip_id),
                    "EntryDateTime": now_utc,
                    "NComponents": int(getattr(pca_model, "n_components_", getattr(pca_model, "n_components", 0))),
                    "TargetVar": json.dumps({"SPE_P95_train": spe_p95_train, "T2_P95_train": t2_p95_train}),
                    "VarExplainedJSON": var_json,
                    "ScalingSpecJSON": scaling_spec,
                    "ModelVersion": cfg.get("runtime", {}).get("version", "v5.0.0"),
                    "TrainStartEntryDateTime": train.index.min() if len(train.index) else None,
                    "TrainEndEntryDateTime": train.index.max() if len(train.index) else None
                }
                rows_pca_model = output_manager.write_pca_model(model_row)

                # PCA Loadings
                comps = getattr(pca_model, "components_", None)
                if comps is not None and hasattr(train, "columns"):
                    load_rows = []
                    for k in range(comps.shape[0]):
                        for j, sensor in enumerate(train.columns):
                            load_rows.append({
                                "RunID": run_id or "",
                                "EntryDateTime": now_utc,
                                "ComponentNo": int(k + 1),
                                "Sensor": str(sensor),
                                "Loading": float(comps[k, j])
                            })
                    df_load = pd.DataFrame(load_rows)
                    rows_pca_load = output_manager.write_pca_loadings(df_load, run_id or "")

                # PCA Metrics
                spe_p95 = float(np.nanpercentile(frame["pca_spe"].to_numpy(dtype=np.float32), 95)) if "pca_spe" in frame.columns else None
                t2_p95  = float(np.nanpercentile(frame["pca_t2"].to_numpy(dtype=np.float32),  95)) if "pca_t2"  in frame.columns else None

                var90_n = None
                if var_ratio is not None:
                    csum = np.cumsum(var_ratio)
                    var90_n = int(np.searchsorted(csum, 0.90) + 1)
                df_metrics = pd.DataFrame([{
                    "RunID": run_id or "",
                    "EntryDateTime": now_utc,
                    "Var90_N": var90_n,
                    "ReconRMSE": None,
                    "P95_ReconRMSE": spe_p95, # This is the score-based P95 SPE
                    "Notes": json.dumps({"SPE_P95_score": spe_p95, "T2_P95_score": t2_p95})
                }])
                rows_pca_metrics = output_manager.write_pca_metrics(df_metrics, run_id or "")
            except Exception as e:
                Console.warn(f"[SQL] PCA artifacts write skipped: {e}")

        # Aggregate row counts for finalize
        rows_written = int(rows_scores + rows_drift + rows_events + rows_regimes + rows_pca_model + rows_pca_load + rows_pca_metrics)

        # Optional compact RunStats (best-effort)
        with T.section("sql.run_stats"):
            try:
                if sql_client and run_id and win_start is not None and win_end is not None:
                    drift_p95 = None
                    if "drift_z" in frame.columns:
                        drift_p95 = float(np.nanpercentile(frame["drift_z"].to_numpy(dtype=np.float32), 95))
                    # No recon stream in current pipeline
                    recon_rmse = None
                    sensors_kept = len(getattr(meta, "kept_cols", []))
                    cadence_ok_pct = float(getattr(meta, "cadence_ok", 1.0)) * 100.0 if hasattr(meta, "cadence_ok") else None

                    output_manager.write_run_stats({
                        "RunID": run_id,
                        "EquipID": int(equip_id),
                        "WindowStartEntryDateTime": win_start,
                        "WindowEndEntryDateTime": win_end,
                        "SamplesIn": rows_read,
                        "SamplesKept": rows_read,      # after cleaning; equal for now
                        "SensorsKept": sensors_kept,
                        "CadenceOKPct": cadence_ok_pct,
                        "DriftP95": drift_p95,
                        "ReconRMSE": recon_rmse,
                        "AnomalyCount": anomaly_count
                    })
            except Exception as e: # type: ignore
                Console.warn(f"[RUN] RunStats not recorded: {e}")

        # === WRITE RUN METADATA TO ACM_RUNS ===
        with T.section("sql.run_metadata"):
            try:
                if sql_client and run_id:
                    # Track completion time
                    from datetime import datetime
                    run_completion_time = datetime.now()
                    
                    # Extract health metrics from scores
                    # DET-07: Pass per-regime calibration info
                    per_regime_enabled = bool(quality_ok and use_per_regime) if 'quality_ok' in locals() and 'use_per_regime' in locals() else False
                    regime_count = len(set(score_regime_labels)) if score_regime_labels is not None else 0
                    run_metadata = extract_run_metadata_from_scores(frame, per_regime_enabled=per_regime_enabled, regime_count=regime_count)
                    
                    # Extract data quality score
                    data_quality_path = tables_dir / "data_quality.csv" if 'tables_dir' in locals() else None
                    data_quality_score = extract_data_quality_score(data_quality_path) if data_quality_path else 100.0
                    
                    # Get kept columns list
                    kept_cols_str = ",".join(getattr(meta, "kept_cols", []))
                    
                    # Write run metadata
                    write_run_metadata(
                        sql_client=sql_client,
                        run_id=run_id,
                        equip_id=int(equip_id),
                        equip_name=equip,
                        started_at=run_start_time,
                        completed_at=run_completion_time,
                        config_signature=config_signature,
                        train_row_count=len(train) if 'train' in locals() and isinstance(train, pd.DataFrame) else 0,
                        score_row_count=len(frame) if isinstance(frame, pd.DataFrame) else 0,
                        episode_count=len(episodes) if isinstance(episodes, pd.DataFrame) else 0,
                        health_status=run_metadata.get("health_status", "UNKNOWN"),
                        avg_health_index=run_metadata.get("avg_health_index"),
                        min_health_index=run_metadata.get("min_health_index"),
                        max_fused_z=run_metadata.get("max_fused_z"),
                        data_quality_score=data_quality_score,
                        refit_requested=refit_flag_path.exists() if 'refit_flag_path' in locals() else False,
                        kept_columns=kept_cols_str,
                        error_message=None
                    )
                    Console.info(f"[RUN_META] Successfully wrote run metadata to ACM_Runs for RunID={run_id}")

            except Exception as e:
                Console.warn(f"[RUN_META] Failed to write ACM_Runs metadata: {e}")

        # === WRITE EPISODE CULPRITS TO ACM_EpisodeCulprits ===
        with T.section("sql.culprits"):
            try:
                if sql_client and run_id and isinstance(episodes, pd.DataFrame) and len(episodes) > 0:
                    # Use enhanced writer that computes detector contributions from scores
                    write_episode_culprits_enhanced(
                        sql_client=sql_client,
                        run_id=run_id,
                        episodes=episodes,
                        scores_df=frame
                    )
                    Console.info(f"[CULPRITS] Successfully wrote episode culprits to ACM_EpisodeCulprits for RunID={run_id}")
            except Exception as e:
                Console.warn(f"[CULPRITS] Failed to write ACM_EpisodeCulprits: {e}")

        if reuse_models and cache_payload:
            with T.section("sql.cache_detectors"):
                try:
                    joblib.dump(cache_payload, model_cache_path)
                    Console.info(f"[MODEL] Cached detectors to {model_cache_path}")
                except Exception as e:
                    Console.warn(f"[MODEL] Failed to cache detectors: {e}")

        # success path outcome
        outcome = "OK"

    except Exception as e:
        # capture error for finalize (must be 'FAIL' not 'ERROR' to match Runs table constraint)
        outcome = "FAIL"
        try:
            err_json = json.dumps({"type": e.__class__.__name__, "message": str(e)}, ensure_ascii=False)
        except Exception:
            err_json = '{"type":"Exception","message":"<serialization failed>"}'
        
        # Write failed run metadata to ACM_Runs
        try:
            if sql_client and run_id:
                from datetime import datetime
                run_completion_time = datetime.now()
                
                # Write run metadata with error message
                write_run_metadata(
                    sql_client=sql_client,
                    run_id=run_id,
                    equip_id=int(equip_id) if 'equip_id' in locals() else 0,
                    equip_name=equip if 'equip' in locals() else "UNKNOWN",
                    started_at=run_start_time,
                    completed_at=run_completion_time,
                    config_signature=config_signature if 'config_signature' in locals() else "UNKNOWN",
                    train_row_count=len(train) if 'train' in locals() and isinstance(train, pd.DataFrame) else 0,
                    score_row_count=rows_read,
                    episode_count=0,
                    health_status="ERROR",
                    avg_health_index=None,
                    min_health_index=None,
                    max_fused_z=None,
                    data_quality_score=0.0,
                    refit_requested=False,
                    kept_columns="",
                    error_message=str(e)[:4000]  # Truncate to fit nvarchar field
                )
                Console.info(f"[RUN_META] Wrote failed run metadata to ACM_Runs for RunID={run_id}")
        except Exception as meta_err:
            Console.warn(f"[RUN_META] Failed to write error run metadata: {meta_err}")
        
        Console.error(f"[RUN] Exception: {e}")
        # re-raise to keep stderr useful for orchestrators
        raise

    finally:
        # Always finalize and close SQL in SQL mode
        if SQL_MODE and sql_client and run_id: # type: ignore
            try:
                _sql_finalize_run(
                    sql_client,
                    run_id=run_id,
                    outcome=outcome,
                    rows_read=rows_read,
                    rows_written=rows_written,
                    err_json=err_json
                )
                Console.info(f"[RUN] Finalized RunID={run_id} outcome={outcome} rows_in={rows_read} rows_out={rows_written}")
            except Exception as fe:
                Console.error(f"[RUN] Finalize failed (finally): {fe}")
            finally:
                # CRITICAL FIX: Close OutputManager to prevent connection leaks
                try:
                    if 'output_manager' in locals():
                        output_manager.close()
                except Exception:
                    pass
                try:
                    getattr(sql_client, "close", lambda: None)()
                except Exception:
                    pass

    # Outputs are always generated to the local run_dir (even in SQL mode).
    _maybe_write_run_meta_json(locals())
    return


if __name__ == "__main__":
    main()
