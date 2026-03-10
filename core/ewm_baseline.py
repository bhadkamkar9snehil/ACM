"""
EWM Baseline Manager
====================

Per-regime, per-channel Exponentially Weighted Moving statistics that provide
anomaly scores from the second observation — no training window required.

This is the core mechanism for zero-day learning (Paradigm-Zero-Day-Learning.md).

Design
------
- Dual-rate baselines: α_fast (~20 batch memory) and α_slow (~200 batch memory)
- Score = |x - μ| / σ, where σ is derived from EWM variance
- Cross-rate logic:
    anomalous vs both fast AND slow = genuine fault
    anomalous vs fast only           = regime shift (legitimate adaptation, NOT a fault)
- Baseline integrity: per-(regime, sensor) P50/P95 tracking; auto-freeze when score
  distribution collapses (baseline chasing a fault)
- State persisted to SQL table ACM_EWMBaseline per (EquipID, RegimeID, SensorName)
- StateVersion = 2 identifies the explicit tag-agnostic raw numeric monitoring
  surface. Older state is ignored rather than silently reinterpreted.

Vectorisation
-------------
All batch operations (score_batch, update_batch) use numpy entirely. No iterrows.
State is held as numpy arrays keyed by (regime_id, sensor_name) for O(1) access.

Usage
-----
    manager = EWMBaselineManager(equip_id=5010)
    manager.load_from_sql(sql_client)

    # Each batch (vectorised):
    ewm_z = manager.score_batch(regime_ids, df)         # pd.Series of fused z_slow
    manager.update_batch(regime_ids, df)                # update EWM state
    freeze_report = manager.check_and_apply_freeze()    # per-sensor freeze check
    manager.save_to_sql(sql_client)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from core.observability import Console

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

GLOBAL_REGIME_ID = -1           # used before regime assignment (early batches)
_MIN_N_TO_SCORE = 3             # need at least 3 obs for a meaningful score
_MIN_N_FOR_REGIME = 10          # use per-regime stats only after 10 obs in regime

_FREEZE_P50_THRESHOLD = 0.35    # P50 below this AND P95 also low → freeze
_FREEZE_P95_THRESHOLD = 1.5     # P95 below this together with P50 → freeze
_RESUME_P50_THRESHOLD = 0.4     # both must recover for resume
_RESUME_P95_THRESHOLD = 2.0
_SCORE_HISTORY_WINDOW = 50      # rolling window kept per (regime, sensor)
_SD_FLOOR = 1e-4                # minimum σ to avoid division by zero
EWM_STATE_VERSION = 2           # explicit raw numeric day-0 monitoring surface


# --------------------------------------------------------------------------- #
# Per-sensor EWM state (value object, no methods)
# --------------------------------------------------------------------------- #

@dataclass
class _SensorState:
    """EWM state for one (regime_id, sensor_name) pair."""
    mean_fast: float = 0.0
    var_fast: float = 1.0       # initialised to 1.0 so σ is non-zero on first score
    mean_slow: float = 0.0
    var_slow: float = 1.0
    n_samples: int = 0
    baseline_integrity: str = "ok"   # 'ok' | 'frozen'
    _score_history: List[float] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Cross-rate result (per sensor)
# --------------------------------------------------------------------------- #

@dataclass
class CrossRateResult:
    """Dual-rate anomaly interpretation for one sensor."""
    sensor: str
    z_fast: float
    z_slow: float
    is_fault: bool           # anomalous vs BOTH fast and slow
    is_regime_shift: bool    # anomalous vs fast only (legitimate adaptation)
    baseline_frozen: bool


# --------------------------------------------------------------------------- #
# EWMBaselineManager
# --------------------------------------------------------------------------- #

class EWMBaselineManager:
    """
    Per-regime, per-sensor dual-rate EWM baselines for zero-day anomaly scoring.

    All batch operations are vectorised. State keyed by (regime_id, sensor_name).
    RegimeID = GLOBAL_REGIME_ID (-1) is always maintained as fallback.

    Args:
        equip_id:   Equipment identifier (used for SQL persistence).
        alpha_fast: EWM decay for fast baseline (~20 batch memory). Default 0.05.
        alpha_slow: EWM decay for slow baseline (~200 batch memory). Default 0.005.
        anomaly_z:  Z-score threshold for cross-rate fault flag. Default 3.0.
    """

    def __init__(
        self,
        equip_id: int,
        alpha_fast: float = 0.05,
        alpha_slow: float = 0.005,
        anomaly_z: float = 3.0,
    ) -> None:
        self.equip_id = equip_id
        self.alpha_fast = alpha_fast
        self.alpha_slow = alpha_slow
        self.anomaly_z = anomaly_z

        # State: {(regime_id, sensor_name): _SensorState}
        self._state: Dict[Tuple[int, str], _SensorState] = {}

        # Set to True after the first successful binner→HDBSCAN remap so that
        # has_binner_regime_ids() is a reliable idempotency guard even when
        # HDBSCAN cluster IDs overlap numerically with binner regime IDs.
        self._binner_remapped: bool = False
        self._state_version_column_available: Optional[bool] = None
        self._warned_missing_state_version_column: bool = False

    # ---------------------------------------------------------------------- #
    # Vectorised batch API (primary interface)
    # ---------------------------------------------------------------------- #

    def score_batch(
        self,
        regime_ids: np.ndarray,
        df: pd.DataFrame,
    ) -> pd.Series:
        """
        Score all rows of df against EWM baselines. Vectorised per-sensor.

        Uses z_slow (long-term character baseline) as the primary anomaly signal.
        Falls back to global regime (-1) for any (regime, sensor) pair with
        fewer than _MIN_N_FOR_REGIME observations.

        Vectorisation strategy:
          For each sensor, build a {regime_id: effective_regime_id} lookup over unique
          regime IDs only (O(n_unique_regimes)), then apply via np.vectorize to assign
          effective_rids for all rows in one pass. Then group by effective_regime and
          compute z_slow in one numpy operation per group: abs(col - μ) / σ.
          Total cost: O(n_sensors × n_unique_regimes), no Python loop over rows.

        Args:
            regime_ids: Integer array of regime IDs, shape (len(df),).
                        -1 entries use the global baseline.
            df:         DataFrame of numeric sensor values with DatetimeIndex.

        Returns:
            pd.Series of mean z_slow per row, same index as df.
            Returns 0.0 for rows where no sensor has sufficient history.
        """
        sensors = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if not sensors:
            return pd.Series(np.zeros(len(df)), index=df.index, name="ewm_z")

        n = len(df)
        # Accumulate z_slow contributions per row; track how many sensors contributed
        z_sum = np.zeros(n, dtype=float)
        z_cnt = np.zeros(n, dtype=int)

        for sensor in sensors:
            col = df[sensor].values.astype(float)
            finite_mask = np.isfinite(col)

            # Map each unique regime_id → effective_regime_id (per-regime if mature, else global).
            # Build the lookup over unique IDs only (O(n_unique_regimes)), then apply with
            # np.vectorize to assign effective_rids for all rows in one pass (no Python for-loop).
            unique_rids = np.unique(regime_ids)
            rid_to_eff: dict = {}
            for rid in unique_rids:
                per = self._state.get((int(rid), sensor))
                rid_to_eff[int(rid)] = int(rid) if (per is not None and per.n_samples >= _MIN_N_FOR_REGIME) else GLOBAL_REGIME_ID
            effective_rids = np.vectorize(rid_to_eff.__getitem__)(regime_ids.astype(int))

            for eff_rid in np.unique(effective_rids):
                state = self._state.get((eff_rid, sensor))
                if state is None or state.n_samples < _MIN_N_TO_SCORE:
                    continue
                mu = state.mean_slow
                sd = max(math.sqrt(max(state.var_slow, 0.0)), _SD_FLOOR)
                group_mask = (effective_rids == eff_rid) & finite_mask
                if not group_mask.any():
                    continue
                z_group = np.abs(col[group_mask] - mu) / sd
                z_sum[group_mask] += z_group
                z_cnt[group_mask] += 1

        # Mean z_slow per row (0.0 where no sensor had state)
        fused = np.where(z_cnt > 0, z_sum / z_cnt, 0.0)
        return pd.Series(fused, index=df.index, name="ewm_z")

    def update_batch(
        self,
        regime_ids: np.ndarray,
        df: pd.DataFrame,
    ) -> None:
        """
        Update EWM state from all rows of df. Vectorised per-sensor per-regime group.

        Always updates the global regime (-1) in addition to per-regime state.
        Skips (regime, sensor) pairs where baseline_integrity == 'frozen'.

        Args:
            regime_ids: Integer array of regime IDs, shape (len(df),).
            df:         DataFrame of numeric sensor values.
        """
        sensors = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if not sensors:
            return

        # Process each sensor independently, grouped by regime for efficiency
        for sensor in sensors:
            col = df[sensor].values.astype(float)
            finite_mask = np.isfinite(col)

            # Always update global regime from all finite values
            self._update_sensor_from_array(GLOBAL_REGIME_ID, sensor, col, finite_mask)

            # Update per-regime: group indices by regime_id
            unique_regimes = np.unique(regime_ids)
            for rid in unique_regimes:
                if rid == GLOBAL_REGIME_ID:
                    continue
                mask = (regime_ids == rid) & finite_mask
                if not mask.any():
                    continue
                self._update_sensor_from_array(rid, sensor, col, mask)

    def check_and_apply_freeze(self) -> Dict[Tuple[int, str], str]:
        """
        Per-(regime, sensor) freeze/resume evaluation.

        For each (regime_id, sensor) pair independently:
        - If its score history P50 < _FREEZE_P50_THRESHOLD AND P95 < _FREEZE_P95_THRESHOLD
          → freeze (stop learning; fault is being absorbed)
        - If frozen AND P50 >= _RESUME_P50_THRESHOLD AND P95 >= _RESUME_P95_THRESHOLD
          → resume

        Returns:
            Dict of {(regime_id, sensor): 'frozen'|'resumed'|'ok'} for changed pairs only.
        """
        changes: Dict[Tuple[int, str], str] = {}

        for key, state in self._state.items():
            regime_id, sensor = key
            hist = state._score_history[-_SCORE_HISTORY_WINDOW:]
            if len(hist) < _SCORE_HISTORY_WINDOW // 2:
                continue

            arr = np.array(hist, dtype=float)
            p50 = float(np.percentile(arr, 50))
            p95 = float(np.percentile(arr, 95))

            was_frozen = (state.baseline_integrity == "frozen")

            if not was_frozen and p50 < _FREEZE_P50_THRESHOLD and p95 < _FREEZE_P95_THRESHOLD:
                state.baseline_integrity = "frozen"
                changes[key] = "frozen"
                Console.warn(
                    f"EWM baseline frozen: equip={self.equip_id} regime={regime_id} "
                    f"sensor={sensor} P50={p50:.2f} P95={p95:.2f} — "
                    f"baseline is chasing a fault; scoring against frozen baseline",
                    component="EWM_BASELINE",
                )
            elif was_frozen and p50 >= _RESUME_P50_THRESHOLD and p95 >= _RESUME_P95_THRESHOLD:
                state.baseline_integrity = "ok"
                changes[key] = "resumed"
                Console.info(
                    f"EWM baseline resumed: equip={self.equip_id} regime={regime_id} "
                    f"sensor={sensor} P50={p50:.2f} P95={p95:.2f}",
                    component="EWM_BASELINE",
                )

        return changes

    # ---------------------------------------------------------------------- #
    # Single-row score for callers that need per-sensor cross-rate results
    # ---------------------------------------------------------------------- #

    def score_row(
        self,
        regime_id: int,
        sensor_values: Dict[str, float],
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        Score a single observation. Returns (z_fast, z_slow) dicts.
        Returns 0.0 for sensors without sufficient history.
        """
        z_fast: Dict[str, float] = {}
        z_slow: Dict[str, float] = {}
        for sensor, x in sensor_values.items():
            if not math.isfinite(x):
                z_fast[sensor] = 0.0
                z_slow[sensor] = 0.0
                continue
            state = self._get_state_for_scoring(regime_id, sensor)
            if state is None or state.n_samples < _MIN_N_TO_SCORE:
                z_fast[sensor] = 0.0
                z_slow[sensor] = 0.0
                continue
            sd_f = max(math.sqrt(max(state.var_fast, 0.0)), _SD_FLOOR)
            sd_s = max(math.sqrt(max(state.var_slow, 0.0)), _SD_FLOOR)
            z_fast[sensor] = abs(x - state.mean_fast) / sd_f
            z_slow[sensor] = abs(x - state.mean_slow) / sd_s
        return z_fast, z_slow

    def cross_rate_results(
        self,
        regime_id: int,
        sensor_values: Dict[str, float],
    ) -> List[CrossRateResult]:
        """
        Cross-rate anomaly interpretation for each sensor.
        Genuine fault = anomalous vs BOTH fast and slow.
        Regime shift  = anomalous vs fast only.
        """
        z_fast, z_slow = self.score_row(regime_id, sensor_values)
        results = []
        for sensor in sensor_values:
            state = self._get_state_for_scoring(regime_id, sensor)
            frozen = state.baseline_integrity == "frozen" if state else False
            zf = z_fast.get(sensor, 0.0)
            zs = z_slow.get(sensor, 0.0)
            results.append(CrossRateResult(
                sensor=sensor,
                z_fast=zf,
                z_slow=zs,
                is_fault=(zf >= self.anomaly_z) and (zs >= self.anomaly_z),
                is_regime_shift=(zf >= self.anomaly_z) and (zs < self.anomaly_z),
                baseline_frozen=frozen,
            ))
        return results

    # ---------------------------------------------------------------------- #
    # Regime remapping (Phase 3: binner → HDBSCAN state transfer)
    # ---------------------------------------------------------------------- #

    def has_binner_regime_ids(self, binner_regime_ids: np.ndarray) -> bool:
        """
        Return True if binner→HDBSCAN remap has NOT yet occurred.

        HDBSCAN cluster IDs overlap numerically with binner regime IDs (both are small
        non-negative integers), so set-intersection alone cannot distinguish them after
        the first remap. Instead, track the remap with _binner_remapped flag which is
        set to True in remap_regime_ids() and never reset. This is a reliable one-shot guard.

        Args:
            binner_regime_ids: Array of binner-assigned regime IDs for the current batch.
                               Passed here for forward-compatibility (unused currently).
        """
        return not self._binner_remapped

    def remap_regime_ids(self, mapping: Dict[int, int]) -> Dict[int, int]:
        """
        Transfer EWM state from binner regime IDs to HDBSCAN cluster IDs.

        Called once when HDBSCAN first produces a stable model. Rows keyed by
        binner_regime_id are merged into rows keyed by hdbscan_cluster_id.

        Merge strategy for each (old_regime, sensor) → (new_regime, sensor):
        - If new_regime key doesn't exist: rename in place (O(1))
        - If new_regime key exists: blend old into existing using n_samples-weighted
          mean (HDBSCAN key keeps its history, binner state contributes weight)

        Args:
            mapping: {binner_regime_id: hdbscan_cluster_id}

        Returns:
            {old_regime_id: new_regime_id} for pairs that were actually remapped
            (may differ from input if some binner IDs had no EWM state).
        """
        if not mapping:
            return {}

        remapped: Dict[int, int] = {}
        new_state: Dict[Tuple[int, str], _SensorState] = {}

        for (regime_id, sensor), state in self._state.items():
            if regime_id in mapping:
                new_regime_id = mapping[regime_id]
                new_key = (new_regime_id, sensor)
                existing = new_state.get(new_key)

                if existing is None:
                    # No collision — rename
                    new_state[new_key] = state
                else:
                    # Weighted blend: n_samples-weighted EWM means/vars
                    n_old = state.n_samples
                    n_new = existing.n_samples
                    n_total = n_old + n_new
                    if n_total > 0:
                        w_old = n_old / n_total
                        w_new = n_new / n_total
                        existing.mean_fast = w_old * state.mean_fast + w_new * existing.mean_fast
                        existing.mean_slow = w_old * state.mean_slow + w_new * existing.mean_slow
                        existing.var_fast = w_old * state.var_fast + w_new * existing.var_fast
                        existing.var_slow = w_old * state.var_slow + w_new * existing.var_slow
                        existing.n_samples = n_total
                        # Preserve frozen state: if either was frozen, merged is frozen
                        if state.baseline_integrity == "frozen":
                            existing.baseline_integrity = "frozen"
                        # Merge score histories
                        existing._score_history = (
                            (state._score_history + existing._score_history)[-_SCORE_HISTORY_WINDOW:]
                        )
                    new_state[new_key] = existing

                remapped[regime_id] = new_regime_id
            elif regime_id == GLOBAL_REGIME_ID:
                # Global fallback always carries over unchanged
                new_state[(regime_id, sensor)] = state
            else:
                # Binner regime with no mapping: keep temporarily, will be shadowed by HDBSCAN
                new_state[(regime_id, sensor)] = state

        self._state = new_state
        self._binner_remapped = True
        n = len(remapped)
        Console.info(
            f"EWM regime remap: equip={self.equip_id} remapped {n} binner regimes "
            f"→ HDBSCAN clusters. mapping={mapping}",
            component="EWM_BASELINE",
        )
        return remapped

    # ---------------------------------------------------------------------- #
    # SQL persistence
    # ---------------------------------------------------------------------- #

    def save_to_sql(self, sql_client) -> int:
        """Upsert current EWM state to ACM_EWMBaseline. Returns rows written."""
        if not self._state:
            return 0
        if not self._has_state_version_column(sql_client):
            self._warn_missing_state_version_column()
            return 0

        def _sql_float(v: float) -> Optional[float]:
            """Return None (SQL NULL) for nan/inf — SQL Server rejects non-finite floats."""
            return None if (v is None or not math.isfinite(v)) else v

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = []
        for (regime_id, sensor), state in self._state.items():
            hist = state._score_history[-_SCORE_HISTORY_WINDOW:]
            if len(hist) >= 2:
                arr = np.array(hist, dtype=float)
                p50 = _sql_float(float(np.percentile(arr, 50)))
                p95 = _sql_float(float(np.percentile(arr, 95)))
            else:
                p50 = None
                p95 = None

            rows.append({
                "EquipID": self.equip_id,
                "RegimeID": regime_id,
                "SensorName": sensor,
                "StateVersion": EWM_STATE_VERSION,
                "EWMMean_Fast": _sql_float(state.mean_fast),
                "EWMVar_Fast": _sql_float(state.var_fast),
                "EWMMean_Slow": _sql_float(state.mean_slow),
                "EWMVar_Slow": _sql_float(state.var_slow),
                "NSamples": state.n_samples,
                "BaselineIntegrity": state.baseline_integrity,
                "ScoreP50": p50,
                "ScoreP95": p95,
                "UpdatedAt": now,
            })

        if not rows:
            return 0

        written = self._upsert_rows(sql_client, pd.DataFrame(rows))
        Console.debug(
            f"EWM state saved: equip={self.equip_id} rows={written}",
            component="EWM_BASELINE",
        )
        return written

    def load_from_sql(self, sql_client) -> int:
        """Load EWM state from ACM_EWMBaseline. Returns rows loaded (0 if table absent)."""
        if not self._has_state_version_column(sql_client):
            self._warn_missing_state_version_column()
            return 0
        try:
            query = """
                SELECT RegimeID, SensorName, StateVersion,
                       EWMMean_Fast, EWMVar_Fast, EWMMean_Slow, EWMVar_Slow,
                       NSamples, BaselineIntegrity, ScoreP50, ScoreP95
                FROM ACM_EWMBaseline
                WHERE EquipID = ? AND StateVersion = ?
            """
            with sql_client.conn.cursor() as cur:
                cur.execute(query, (self.equip_id, EWM_STATE_VERSION))
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description]
        except Exception as exc:
            Console.warn(
                f"EWM load skipped (table may not exist yet): {exc}",
                component="EWM_BASELINE",
            )
            return 0

        self._state = {}
        for row in rows:
            r = dict(zip(cols, row))
            regime_id = int(r["RegimeID"])
            sensor = str(r["SensorName"])
            state = _SensorState(
                mean_fast=float(r["EWMMean_Fast"] or 0.0),
                var_fast=float(r["EWMVar_Fast"] or 1.0),
                mean_slow=float(r["EWMMean_Slow"] or 0.0),
                var_slow=float(r["EWMVar_Slow"] or 1.0),
                n_samples=int(r["NSamples"] or 0),
                baseline_integrity=str(r["BaselineIntegrity"] or "ok"),
            )
            # Seed score history from persisted P50/P95 so freeze logic has context
            p50 = r.get("ScoreP50")
            p95 = r.get("ScoreP95")
            if p50 is not None and p95 is not None:
                state._score_history = [float(p50)] * 10 + [float(p95)]
            self._state[(regime_id, sensor)] = state

        Console.debug(
            f"EWM state loaded: equip={self.equip_id} rows={len(rows)}",
            component="EWM_BASELINE",
        )
        return len(rows)

    # ---------------------------------------------------------------------- #
    # Internal helpers
    # ---------------------------------------------------------------------- #

    def _get_or_create(self, regime_id: int, sensor: str) -> _SensorState:
        key = (regime_id, sensor)
        if key not in self._state:
            self._state[key] = _SensorState()
        return self._state[key]

    def _has_state_version_column(self, sql_client) -> bool:
        if self._state_version_column_available is not None:
            return self._state_version_column_available
        try:
            query = """
                SELECT 1
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = 'dbo'
                  AND TABLE_NAME = 'ACM_EWMBaseline'
                  AND COLUMN_NAME = 'StateVersion'
            """
            with sql_client.conn.cursor() as cur:
                cur.execute(query)
                self._state_version_column_available = cur.fetchone() is not None
        except Exception:
            self._state_version_column_available = False
        return bool(self._state_version_column_available)

    def _warn_missing_state_version_column(self) -> None:
        if self._warned_missing_state_version_column:
            return
        self._warned_missing_state_version_column = True
        Console.warn(
            "EWM persistence skipped because ACM_EWMBaseline.StateVersion is missing. "
            "Apply SQL migration 016 before relying on persisted zero-day EWM state.",
            component="EWM_BASELINE",
            expected_state_version=EWM_STATE_VERSION,
        )

    def _get_state_for_scoring(
        self, regime_id: int, sensor: str
    ) -> Optional[_SensorState]:
        """Return per-regime state if mature, else fall back to global (-1)."""
        per_regime = self._state.get((regime_id, sensor))
        if per_regime is not None and per_regime.n_samples >= _MIN_N_FOR_REGIME:
            return per_regime
        return self._state.get((GLOBAL_REGIME_ID, sensor))

    def _update_sensor_from_array(
        self,
        regime_id: int,
        sensor: str,
        col: np.ndarray,
        mask: np.ndarray,
    ) -> None:
        """
        Apply EWM update for one (regime, sensor) from masked numpy slice.
        Uses iterative online update — cannot be fully vectorised because
        each step depends on the previous state.
        """
        state = self._get_or_create(regime_id, sensor)
        if state.baseline_integrity == "frozen":
            return

        af = self.alpha_fast
        as_ = self.alpha_slow
        indices = np.where(mask)[0]

        for i in indices:
            x = float(col[i])
            if state.n_samples == 0:
                state.mean_fast = x
                state.mean_slow = x
                state.var_fast = 1.0
                state.var_slow = 1.0
            else:
                d_fast = x - state.mean_fast
                d_slow = x - state.mean_slow
                state.mean_fast += af * d_fast
                state.mean_slow += as_ * d_slow
                state.var_fast = (1 - af) * (state.var_fast + af * d_fast ** 2)
                state.var_slow = (1 - as_) * (state.var_slow + as_ * d_slow ** 2)
            state.n_samples += 1

            # Track z_slow for score distribution monitoring
            if state.n_samples >= _MIN_N_TO_SCORE:
                sd = max(math.sqrt(max(state.var_slow, 0.0)), _SD_FLOOR)
                z = abs(x - state.mean_slow) / sd
                state._score_history.append(z)

        # Trim history to prevent unbounded growth
        if len(state._score_history) > _SCORE_HISTORY_WINDOW * 2:
            state._score_history = state._score_history[-_SCORE_HISTORY_WINDOW:]

    # Maximum rows per VALUES clause. 500 rows × 13 cols = 6,500 params —
    # well within pyodbc's 32,767-parameter limit and SQL Server's VALUES limit.
    _UPSERT_CHUNK_SIZE = 500

    _UPSERT_COLS = [
        "EquipID", "RegimeID", "SensorName", "StateVersion",
        "EWMMean_Fast", "EWMVar_Fast", "EWMMean_Slow", "EWMVar_Slow",
        "NSamples", "BaselineIntegrity", "ScoreP50", "ScoreP95", "UpdatedAt",
    ]

    _MERGE_TEMPLATE = """\
MERGE ACM_EWMBaseline AS target
USING (VALUES {placeholders}) AS source
    (EquipID, RegimeID, SensorName, StateVersion,
     EWMMean_Fast, EWMVar_Fast, EWMMean_Slow, EWMVar_Slow,
     NSamples, BaselineIntegrity, ScoreP50, ScoreP95, UpdatedAt)
ON  target.EquipID    = source.EquipID
AND target.RegimeID   = source.RegimeID
AND target.SensorName = source.SensorName
WHEN MATCHED THEN UPDATE SET
    StateVersion      = source.StateVersion,
    EWMMean_Fast      = source.EWMMean_Fast,
    EWMVar_Fast       = source.EWMVar_Fast,
    EWMMean_Slow      = source.EWMMean_Slow,
    EWMVar_Slow       = source.EWMVar_Slow,
    NSamples          = source.NSamples,
    BaselineIntegrity = source.BaselineIntegrity,
    ScoreP50          = source.ScoreP50,
    ScoreP95          = source.ScoreP95,
    UpdatedAt         = source.UpdatedAt
WHEN NOT MATCHED THEN INSERT
    (EquipID, RegimeID, SensorName, StateVersion,
     EWMMean_Fast, EWMVar_Fast, EWMMean_Slow, EWMVar_Slow,
     NSamples, BaselineIntegrity, ScoreP50, ScoreP95, UpdatedAt)
VALUES
    (source.EquipID, source.RegimeID, source.SensorName, source.StateVersion,
     source.EWMMean_Fast, source.EWMVar_Fast, source.EWMMean_Slow, source.EWMVar_Slow,
     source.NSamples, source.BaselineIntegrity, source.ScoreP50, source.ScoreP95,
     source.UpdatedAt);"""

    def _upsert_rows(self, sql_client, df: pd.DataFrame) -> int:
        """Bulk-MERGE rows into ACM_EWMBaseline in chunks.

        Replaces the previous row-by-row execute loop (2,132 round-trips → 5).
        Each chunk issues one MERGE with a multi-row VALUES clause. Semantics
        are identical to the original single-row MERGE.
        """
        if df.empty:
            return 0

        n_cols = len(self._UPSERT_COLS)
        row_placeholder = f"({', '.join(['?'] * n_cols)})"

        # itertuples is ~10–100× faster than iterrows for record extraction
        records = list(df[self._UPSERT_COLS].itertuples(index=False, name=None))

        written = 0
        try:
            with sql_client.conn.cursor() as cur:
                for start in range(0, len(records), self._UPSERT_CHUNK_SIZE):
                    chunk = records[start : start + self._UPSERT_CHUNK_SIZE]
                    placeholders = ", ".join(row_placeholder for _ in chunk)
                    merge_sql = self._MERGE_TEMPLATE.format(placeholders=placeholders)
                    params = [v for row in chunk for v in row]
                    cur.execute(merge_sql, params)
                    written += len(chunk)
            sql_client.conn.commit()
            return written
        except Exception as exc:
            Console.warn(f"EWM save failed: {exc}", component="EWM_BASELINE")
            return 0
