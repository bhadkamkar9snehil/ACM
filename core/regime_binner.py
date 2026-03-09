"""
Online PCA Binner
=================

Asset-agnostic online regime proxy for zero-day context inference.

The binner consumes a tag-agnostic numeric monitoring surface, maintains an
online mean/covariance estimate, projects observations onto the dominant
principal component, and percentile-bins that one-dimensional latent context
into small integer regime IDs from the earliest viable batches.

This is intentionally a fallback regime proxy:
- before mature HDBSCAN regimes exist, it provides early context IDs
- after the first successful binner -> HDBSCAN remap, it stops acting as a
  runtime fallback to avoid mixing incompatible label spaces
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from core.observability import Console

ONLINE_PCA_BINNER_TYPE = "OnlinePCABinner"
ONLINE_PCA_BINNER_STATE_VERSION = 1

_DEFAULT_ALPHA = 0.05
_DEFAULT_HISTORY_LIMIT = 512
_DEFAULT_MIN_ROWS_FOR_ASSIGNMENT = 20
_COV_REGULARIZATION = 1e-6


def _ensure_covariance_matrix(cov: np.ndarray, n_features: int) -> np.ndarray:
    cov = np.asarray(cov, dtype=float)
    if cov.ndim == 0:
        cov = np.array([[float(cov)]], dtype=float)
    cov = np.nan_to_num(cov, nan=0.0, posinf=0.0, neginf=0.0)
    if cov.shape != (n_features, n_features):
        return np.eye(n_features, dtype=float) * _COV_REGULARIZATION
    cov = (cov + cov.T) * 0.5
    cov += np.eye(n_features, dtype=float) * _COV_REGULARIZATION
    return cov


def _power_iteration(
    cov: np.ndarray,
    warm_start: Optional[np.ndarray] = None,
    n_iter: int = 25,
) -> np.ndarray:
    n_features = cov.shape[0]
    if n_features == 1:
        return np.array([1.0], dtype=float)

    if warm_start is not None and warm_start.shape == (n_features,) and np.isfinite(warm_start).all():
        vec = warm_start.astype(float, copy=True)
    else:
        vec = np.ones(n_features, dtype=float)

    norm = float(np.linalg.norm(vec))
    if not np.isfinite(norm) or norm <= 1e-12:
        vec = np.ones(n_features, dtype=float) / np.sqrt(float(n_features))
    else:
        vec /= norm

    for _ in range(n_iter):
        candidate = cov @ vec
        cand_norm = float(np.linalg.norm(candidate))
        if not np.isfinite(cand_norm) or cand_norm <= 1e-12:
            break
        vec = candidate / cand_norm

    if vec[0] < 0:
        vec = -vec
    return vec


class OnlinePCABinner:
    """
    Asset-agnostic online latent regime proxy.

    Args:
        n_bins: Number of percentile bins along PC1.
        min_rows_for_assignment: Minimum observed rows before assignment becomes active.
        alpha: Exponential smoothing factor for online mean/covariance updates.
        history_limit: Maximum number of projected values kept for percentile edges.
    """

    def __init__(
        self,
        n_bins: int = 3,
        min_rows_for_assignment: int = _DEFAULT_MIN_ROWS_FOR_ASSIGNMENT,
        alpha: float = _DEFAULT_ALPHA,
        history_limit: int = _DEFAULT_HISTORY_LIMIT,
    ) -> None:
        if n_bins < 2:
            raise ValueError("n_bins must be >= 2")
        if min_rows_for_assignment < 1:
            raise ValueError("min_rows_for_assignment must be >= 1")
        if not (0.0 < alpha <= 1.0):
            raise ValueError("alpha must be in (0, 1]")
        if history_limit < min_rows_for_assignment:
            raise ValueError("history_limit must be >= min_rows_for_assignment")

        self.n_bins = int(n_bins)
        self.min_rows_for_assignment = int(min_rows_for_assignment)
        self.alpha = float(alpha)
        self.history_limit = int(history_limit)

        self.sensor_cols: List[str] = []
        self._mean: Optional[np.ndarray] = None
        self._cov: Optional[np.ndarray] = None
        self._dominant_vector: Optional[np.ndarray] = None
        self._pc1_history: List[float] = []
        self._n_rows_seen: int = 0
        self._n_batches_seen: int = 0
        self._binner_remapped: bool = False

    @property
    def n_regimes(self) -> int:
        return self.n_bins

    @property
    def is_ready(self) -> bool:
        return (
            self._dominant_vector is not None
            and self._mean is not None
            and self._n_rows_seen >= self.min_rows_for_assignment
            and len(self._pc1_history) >= self.min_rows_for_assignment
        )

    @property
    def can_assign_fallback(self) -> bool:
        return not self._binner_remapped

    def mark_remapped(self) -> None:
        self._binner_remapped = True

    def align_to_surface(self, sensor_cols: Sequence[str]) -> bool:
        """
        Ensure persisted latent state matches the active monitoring surface.

        Returns True when the current state is already compatible.
        Returns False when state had to be invalidated and rebuilt cold.
        """
        normalized = [str(col) for col in sensor_cols]
        if not normalized:
            self._reset_state()
            return False
        if not self.sensor_cols:
            self.sensor_cols = list(normalized)
            Console.info(
                f"OnlinePCABinner aligned to monitoring surface with {len(self.sensor_cols)} channels",
                component="REGIME_BINNER",
                selected_count=len(self.sensor_cols),
            )
            return True
        if self.sensor_cols == normalized:
            return True

        Console.warn(
            "OnlinePCABinner state invalidated because the active monitoring surface changed.",
            component="REGIME_BINNER",
            previous_cols=len(self.sensor_cols),
            current_cols=len(normalized),
        )
        self._reset_state(sensor_cols=normalized)
        return False

    def observe_batch(self, df: pd.DataFrame) -> None:
        values, row_valid = self._prepare_batch(df, allow_lock=True)
        if values.size == 0 or not row_valid.any():
            return

        observed = values[row_valid]
        n_rows, n_features = observed.shape
        batch_center = np.median(observed, axis=0)
        centered = observed - batch_center

        if n_rows > 1:
            batch_cov = np.cov(centered, rowvar=False)
        else:
            batch_cov = np.eye(n_features, dtype=float) * _COV_REGULARIZATION
        batch_cov = _ensure_covariance_matrix(batch_cov, n_features)

        if self._mean is None or self._cov is None or self._dominant_vector is None:
            self._mean = batch_center.astype(float, copy=True)
            self._cov = batch_cov
        else:
            self._mean = ((1.0 - self.alpha) * self._mean) + (self.alpha * batch_center)
            self._cov = ((1.0 - self.alpha) * self._cov) + (self.alpha * batch_cov)
            self._cov = _ensure_covariance_matrix(self._cov, n_features)

        self._dominant_vector = _power_iteration(self._cov, warm_start=self._dominant_vector)
        projections = (observed - self._mean) @ self._dominant_vector
        finite_proj = projections[np.isfinite(projections)]
        if finite_proj.size:
            self._pc1_history.extend(float(x) for x in finite_proj.tolist())
            if len(self._pc1_history) > self.history_limit:
                self._pc1_history = self._pc1_history[-self.history_limit :]

        self._n_rows_seen += int(row_valid.sum())
        self._n_batches_seen += 1

    def assign_batch(self, df: pd.DataFrame) -> np.ndarray:
        if not self.sensor_cols:
            return np.full(len(df), -1, dtype=int)

        values, row_valid = self._prepare_batch(df, allow_lock=False)
        if values.size == 0 or not self.is_ready:
            return np.full(len(df), -1, dtype=int)

        assert self._mean is not None
        assert self._dominant_vector is not None

        history = np.asarray(self._pc1_history, dtype=float)
        if history.size < self.min_rows_for_assignment:
            return np.full(len(df), -1, dtype=int)

        edges = np.percentile(history, np.linspace(0, 100, self.n_bins + 1)[1:-1])
        edges = np.unique(np.asarray(edges, dtype=float))
        projections = (values - self._mean) @ self._dominant_vector
        bins = np.searchsorted(edges, projections, side="right").astype(int)
        bins = np.clip(bins, 0, self.n_bins - 1)
        bins[~row_valid] = -1
        return bins

    def describe_regime(self, regime_id: int) -> str:
        if regime_id < 0:
            return "unassigned"
        return f"pc1_bin={int(regime_id)}"

    def save_to_sql(self, sql_client, equip_id: int) -> bool:
        if not self.sensor_cols or self._mean is None or self._cov is None or self._dominant_vector is None:
            return False

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        state_json = json.dumps(
            {
                "binner_type": ONLINE_PCA_BINNER_TYPE,
                "state_version": ONLINE_PCA_BINNER_STATE_VERSION,
                "n_bins": self.n_bins,
                "min_rows_for_assignment": self.min_rows_for_assignment,
                "alpha": self.alpha,
                "history_limit": self.history_limit,
                "n_rows_seen": self._n_rows_seen,
                "n_batches_seen": self._n_batches_seen,
                "sensor_cols": list(self.sensor_cols),
                "mean": self._mean.tolist(),
                "cov": self._cov.tolist(),
                "dominant_vector": self._dominant_vector.tolist(),
                "pc1_history": list(self._pc1_history),
                "binner_remapped": self._binner_remapped,
            }
        )

        merge_sql = """
MERGE ACM_RegimeBinnerState AS target
USING (VALUES (?, ?, ?)) AS source (EquipID, StateJson, UpdatedAt)
ON target.EquipID = source.EquipID
WHEN MATCHED THEN UPDATE SET StateJson = source.StateJson, UpdatedAt = source.UpdatedAt
WHEN NOT MATCHED THEN INSERT (EquipID, StateJson, UpdatedAt)
    VALUES (source.EquipID, source.StateJson, source.UpdatedAt);
"""
        try:
            with sql_client.conn.cursor() as cur:
                cur.execute(merge_sql, (equip_id, state_json, now))
            sql_client.conn.commit()
            Console.debug(
                f"OnlinePCABinner state saved: equip={equip_id} rows={self._n_rows_seen} "
                f"batches={self._n_batches_seen} cols={len(self.sensor_cols)}",
                component="REGIME_BINNER",
            )
            return True
        except Exception as exc:
            Console.warn(
                f"OnlinePCABinner save failed: {exc}",
                component="REGIME_BINNER",
            )
            return False

    def load_from_sql(self, sql_client, equip_id: int) -> bool:
        try:
            query = "SELECT StateJson FROM ACM_RegimeBinnerState WHERE EquipID = ?"
            with sql_client.conn.cursor() as cur:
                cur.execute(query, (equip_id,))
                row = cur.fetchone()
        except Exception as exc:
            Console.warn(
                f"OnlinePCABinner load skipped (table may not exist yet): {exc}",
                component="REGIME_BINNER",
            )
            return False

        if row is None:
            return False

        try:
            data = json.loads(row[0])
        except Exception as exc:
            Console.warn(
                f"OnlinePCABinner state parse failed: {exc}",
                component="REGIME_BINNER",
            )
            return False

        if data.get("binner_type") != ONLINE_PCA_BINNER_TYPE:
            Console.info(
                "Discarding legacy regime binner state; current runtime expects OnlinePCABinner state.",
                component="REGIME_BINNER",
            )
            return False

        sensor_cols = data.get("sensor_cols") or []
        mean = np.asarray(data.get("mean") or [], dtype=float)
        cov = np.asarray(data.get("cov") or [], dtype=float)
        dominant_vector = np.asarray(data.get("dominant_vector") or [], dtype=float)
        if not sensor_cols:
            return False
        n_features = len(sensor_cols)
        if mean.shape != (n_features,) or dominant_vector.shape != (n_features,):
            return False

        self.sensor_cols = [str(col) for col in sensor_cols]
        self.n_bins = int(data.get("n_bins", self.n_bins))
        self.min_rows_for_assignment = int(
            data.get("min_rows_for_assignment", self.min_rows_for_assignment)
        )
        self.alpha = float(data.get("alpha", self.alpha))
        self.history_limit = int(data.get("history_limit", self.history_limit))
        self._n_rows_seen = int(data.get("n_rows_seen", 0))
        self._n_batches_seen = int(data.get("n_batches_seen", 0))
        self._mean = mean
        self._cov = _ensure_covariance_matrix(cov, n_features)
        self._dominant_vector = _power_iteration(self._cov, warm_start=dominant_vector)
        self._pc1_history = [
            float(x)
            for x in list(data.get("pc1_history") or [])
            if np.isfinite(float(x))
        ][-self.history_limit :]
        self._binner_remapped = bool(data.get("binner_remapped", False))

        Console.info(
            f"OnlinePCABinner state loaded: equip={equip_id} rows={self._n_rows_seen} "
            f"batches={self._n_batches_seen} cols={len(self.sensor_cols)} remapped={self._binner_remapped}",
            component="REGIME_BINNER",
        )
        return True

    def _reset_state(self, sensor_cols: Optional[Sequence[str]] = None) -> None:
        self.sensor_cols = [str(col) for col in sensor_cols] if sensor_cols is not None else []
        self._mean = None
        self._cov = None
        self._dominant_vector = None
        self._pc1_history = []
        self._n_rows_seen = 0
        self._n_batches_seen = 0
        self._binner_remapped = False

    def _prepare_batch(
        self,
        df: pd.DataFrame,
        *,
        allow_lock: bool,
    ) -> Tuple[np.ndarray, np.ndarray]:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return np.empty((len(df), 0), dtype=float), np.zeros(len(df), dtype=bool)

        if not self.sensor_cols and allow_lock:
            numeric_cols = [
                col for col in df.columns
                if pd.api.types.is_numeric_dtype(df[col])
            ]
            self.sensor_cols = sorted(str(col) for col in numeric_cols)
            if self.sensor_cols:
                Console.info(
                    f"OnlinePCABinner locked {len(self.sensor_cols)} monitoring channels",
                    component="REGIME_BINNER",
                    selected_count=len(self.sensor_cols),
                )

        if not self.sensor_cols:
            return np.empty((len(df), 0), dtype=float), np.zeros(len(df), dtype=bool)

        working = (
            df.reindex(columns=self.sensor_cols)
            .apply(pd.to_numeric, errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
        )
        raw_values = working.to_numpy(dtype=float)
        row_valid = np.any(np.isfinite(raw_values), axis=1)

        medians = working.median(axis=0, numeric_only=True).reindex(self.sensor_cols)
        fill_values = medians.to_numpy(dtype=float).copy()

        if self._mean is not None and self._mean.shape == (len(self.sensor_cols),):
            fallback = self._mean
        else:
            fallback = np.zeros(len(self.sensor_cols), dtype=float)

        bad_fill = ~np.isfinite(fill_values)
        fill_values[bad_fill] = fallback[bad_fill]

        values = np.where(np.isfinite(raw_values), raw_values, fill_values[np.newaxis, :])
        values = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)
        return values.astype(float, copy=False), row_valid
