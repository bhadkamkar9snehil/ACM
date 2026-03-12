"""
ACM Run Metadata Writer

Writes comprehensive run-level metadata to ACM_Runs table for:
- Run tracking and auditing
- Performance monitoring
- Quality assessment
- Refit scheduling

Called at the end of every ACM run (success or failure).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import json
import pandas as pd
import numpy as np
from core.observability import Console


@dataclass(frozen=True)
class ZeroDayRunStatus:
    """Operator-facing day-0 status persisted per run."""

    scoring_active: bool
    status: str
    surface_type: str = "none"
    channel_count: int = 0


@dataclass(frozen=True)
class RepresentationRunStatus:
    """Operator-facing representation summary persisted per run."""

    authoritative: bool
    score_allowed: Optional[bool]
    learn_allowed: Optional[bool]
    context_label: str = "UNKNOWN"
    runtime_mode: str = "UNASSESSED"
    schema_compatibility: str = "PENDING"
    basis_compatibility: str = "PENDING"
    baseline_compatibility: str = "PENDING"
    suppressed_reasons_json: str = "[]"
    degraded_reasons_json: str = "[]"


def _normalize_optional_float(value: Any) -> Optional[float]:
    """Convert NaN/Inf-like float inputs into SQL-safe nullable scalars."""
    if value is None:
        return None
    try:
        normalized = float(value)
    except Exception:
        return None
    if not np.isfinite(normalized):
        return None
    return normalized


def build_zero_day_run_status(
    *,
    scoring_active: bool,
    status: str,
    surface_type: str = "none",
    channel_count: int = 0,
) -> ZeroDayRunStatus:
    """Create a normalized day-0 status payload."""
    normalized_status = str(status or "inactive_unknown").strip().lower() or "inactive_unknown"
    normalized_surface = str(surface_type or "none").strip().lower() or "none"
    normalized_channel_count = max(0, int(channel_count or 0))
    return ZeroDayRunStatus(
        scoring_active=bool(scoring_active),
        status=normalized_status,
        surface_type=normalized_surface,
        channel_count=normalized_channel_count,
    )


def zero_day_status_from_noop_reason(reason: str) -> ZeroDayRunStatus:
    """Map load-stage NOOP reasons to persisted day-0 status."""
    normalized = str(reason or "UNKNOWN_NOOP").strip().upper() or "UNKNOWN_NOOP"
    mapping = {
        "SCORING_NO_DATA": "inactive_no_data",
        "COLDSTART_DEFERRED": "inactive_coldstart_deferred",
    }
    return build_zero_day_run_status(
        scoring_active=False,
        status=mapping.get(normalized, "inactive_unknown"),
        surface_type="none",
        channel_count=0,
    )


def build_representation_run_status(representation_result: Optional[Any]) -> Optional[RepresentationRunStatus]:
    """Create a normalized run-level representation summary from the pipeline result."""
    if representation_result is None:
        return None
    eligibility = getattr(representation_result, "eligibility", None)
    compatibility = getattr(representation_result, "compatibility", None)
    context = getattr(representation_result, "context", None)
    baseline_governance = getattr(representation_result, "baseline_governance", None)
    if eligibility is None or compatibility is None or context is None or baseline_governance is None:
        return None
    return RepresentationRunStatus(
        authoritative=bool(getattr(representation_result, "authoritative", False)),
        score_allowed=getattr(eligibility, "score_allowed", None),
        learn_allowed=getattr(eligibility, "learn_allowed", None),
        context_label=str(getattr(context, "context_label", "UNKNOWN") or "UNKNOWN"),
        runtime_mode=str(getattr(getattr(baseline_governance, "runtime_mode", None), "value", "UNASSESSED") or "UNASSESSED"),
        schema_compatibility=str(getattr(compatibility, "schema_compatibility", "PENDING") or "PENDING"),
        basis_compatibility=str(getattr(compatibility, "basis_compatibility", "PENDING") or "PENDING"),
        baseline_compatibility=str(getattr(compatibility, "baseline_compatibility", "PENDING") or "PENDING"),
        suppressed_reasons_json=json.dumps(
            list(getattr(eligibility, "suppressed_reason_codes", ()) or ()),
            ensure_ascii=True,
        ),
        degraded_reasons_json=json.dumps(
            list(getattr(eligibility, "degraded_reason_codes", ()) or ()),
            ensure_ascii=True,
        ),
    )


def _acm_runs_has_zero_day_columns(sql_client: Any) -> bool:
    """Check whether ACM_Runs has the explicit zero-day observability columns."""
    query = """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'dbo'
          AND TABLE_NAME = 'ACM_Runs'
          AND COLUMN_NAME IN (
              'ZeroDayScoringActive',
              'ZeroDayStatus',
              'ZeroDaySurfaceType',
              'ZeroDayChannelCount'
          )
    """
    try:
        with sql_client.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
    except Exception:
        return False

    required = {
        "ZeroDayScoringActive",
        "ZeroDayStatus",
        "ZeroDaySurfaceType",
        "ZeroDayChannelCount",
    }
    found = {str(row[0]) for row in rows}
    return required.issubset(found)


def _acm_runs_has_representation_columns(sql_client: Any) -> bool:
    """Check whether ACM_Runs has the explicit representation-summary columns."""
    query = """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'dbo'
          AND TABLE_NAME = 'ACM_Runs'
          AND COLUMN_NAME IN (
              'RepresentationAuthoritative',
              'RepresentationScoreAllowed',
              'RepresentationLearnAllowed',
              'RepresentationContextLabel',
              'RepresentationRuntimeMode',
              'RepresentationSchemaCompatibility',
              'RepresentationBasisCompatibility',
              'RepresentationBaselineCompatibility',
              'RepresentationSuppressedReasons',
              'RepresentationDegradedReasons'
          )
    """
    try:
        with sql_client.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
    except Exception:
        return False

    required = {
        "RepresentationAuthoritative",
        "RepresentationScoreAllowed",
        "RepresentationLearnAllowed",
        "RepresentationContextLabel",
        "RepresentationRuntimeMode",
        "RepresentationSchemaCompatibility",
        "RepresentationBasisCompatibility",
        "RepresentationBaselineCompatibility",
        "RepresentationSuppressedReasons",
        "RepresentationDegradedReasons",
    }
    found = {str(row[0]) for row in rows}
    return required.issubset(found)


def _warn_missing_zero_day_columns(logger: Any, run_id: Optional[str], equip_id: Optional[int]) -> None:
    """Warn when migration 017 has not been applied yet."""
    logger.warn(
        "Zero-day run observability skipped because ACM_Runs is missing explicit "
        "zero-day status columns. Apply SQL migration 017 before relying on "
        "persisted day-0 run visibility.",
        component="RUN_META",
        run_id=run_id,
        equip_id=equip_id,
    )


def _warn_missing_representation_columns(logger: Any, run_id: Optional[str], equip_id: Optional[int]) -> None:
    """Warn when ACM_Runs is missing explicit representation-summary columns."""
    logger.warn(
        "Representation run observability skipped because ACM_Runs is missing explicit "
        "representation summary columns. Apply SQL migration 022 before relying on "
        "persisted run-level representation visibility.",
        component="RUN_META",
        run_id=run_id,
        equip_id=equip_id,
    )


def write_zero_day_run_status(
    sql_client: Any,
    run_id: Optional[str],
    zero_day_status: Optional[ZeroDayRunStatus],
    *,
    equip_id: Optional[int] = None,
    logger: Any = Console,
) -> bool:
    """Persist explicit day-0 status onto the ACM_Runs row."""
    if sql_client is None or not run_id or zero_day_status is None:
        return False

    if not _acm_runs_has_zero_day_columns(sql_client):
        _warn_missing_zero_day_columns(logger, run_id, equip_id)
        return False

    status = build_zero_day_run_status(
        scoring_active=zero_day_status.scoring_active,
        status=zero_day_status.status,
        surface_type=zero_day_status.surface_type,
        channel_count=zero_day_status.channel_count,
    )

    update_sql = """
        UPDATE dbo.ACM_Runs
        SET ZeroDayScoringActive = ?,
            ZeroDayStatus = ?,
            ZeroDaySurfaceType = ?,
            ZeroDayChannelCount = ?
        WHERE RunID = ?
    """

    try:
        with sql_client.cursor() as cur:
            cur.execute(
                update_sql,
                (
                    bool(status.scoring_active),
                    status.status,
                    status.surface_type,
                    int(status.channel_count),
                    run_id,
                ),
            )
        sql_client.conn.commit()
        logger.info(
            f"Wrote zero-day status to ACM_Runs: {run_id}",
            component="RUN_META",
            run_id=run_id,
            equip_id=equip_id,
            zero_day_status=status.status,
            zero_day_scoring_active=bool(status.scoring_active),
            zero_day_surface_type=status.surface_type,
            zero_day_channel_count=int(status.channel_count),
        )
        return True
    except Exception as e:
        logger.error(
            f"Failed to write zero-day ACM_Runs status: {e}",
            component="RUN_META",
            run_id=run_id,
            equip_id=equip_id,
            error_type=type(e).__name__,
            error=str(e)[:200],
        )
        try:
            sql_client.conn.rollback()
        except Exception:
            pass
        return False


def write_run_metadata(
    sql_client,
    run_id: str,
    equip_id: int,
    equip_name: str,
    started_at: datetime,
    completed_at: datetime,
    config_signature: str,
    train_row_count: int,
    score_row_count: int,
    episode_count: int,
    health_status: str,
    avg_health_index: float,
    min_health_index: float,
    max_fused_z: float,
    data_quality_score: float,
    refit_requested: bool,
    kept_columns: str,
    error_message: Optional[str] = None,
    zero_day_status: Optional[ZeroDayRunStatus] = None,
    representation_status: Optional[RepresentationRunStatus] = None,
) -> bool:
    """
    Write run metadata to ACM_Runs table.
    
    Args:
        sql_client: SQL connection client
        run_id: Unique run identifier (UUID)
        equip_id: Equipment ID
        equip_name: Equipment name
        started_at: Run start timestamp (UTC)
        completed_at: Run completion timestamp (UTC)
        config_signature: MD5 hash of config for change detection
        train_row_count: Number of training rows processed
        score_row_count: Number of scoring rows processed
        episode_count: Number of anomaly episodes detected
        health_status: Overall health status (HEALTHY, CAUTION, ALERT)
        avg_health_index: Average health index (0-100)
        min_health_index: Minimum health index (0-100)
        max_fused_z: Maximum fused z-score
        data_quality_score: Data quality metric (0-100)
        refit_requested: Whether model refit was requested
        kept_columns: Comma-separated list of sensor columns used
        error_message: Error message if run failed (optional)
    
    Returns:
        bool: True if write succeeded, False otherwise
    """
    
    if sql_client is None:
        Console.warn("No SQL client provided, skipping ACM_Runs write", component="RUN_META", run_id=run_id, equip_id=equip_id)
        return False
    
    try:
        # Calculate duration
        duration_seconds = int((completed_at - started_at).total_seconds())
        
        # Ensure timestamps are UTC naive (SQL datetime2 requirement)
        if started_at.tzinfo is not None:
            started_at = started_at.replace(tzinfo=None)
        if completed_at.tzinfo is not None:
            completed_at = completed_at.replace(tzinfo=None)
        
        # Build UPDATE statement (row already exists from _sql_start_run)
        include_zero_day = zero_day_status is not None and _acm_runs_has_zero_day_columns(sql_client)
        include_representation = (
            representation_status is not None and _acm_runs_has_representation_columns(sql_client)
        )
        normalized_zero_day = None
        if zero_day_status is not None and not include_zero_day:
            _warn_missing_zero_day_columns(Console, run_id, equip_id)
        if representation_status is not None and not include_representation:
            _warn_missing_representation_columns(Console, run_id, equip_id)
        if include_zero_day and zero_day_status is not None:
            normalized_zero_day = build_zero_day_run_status(
                scoring_active=zero_day_status.scoring_active,
                status=zero_day_status.status,
                surface_type=zero_day_status.surface_type,
                channel_count=zero_day_status.channel_count,
            )

        update_sql = """
        UPDATE dbo.ACM_Runs
        SET EquipName = ?,
            CompletedAt = ?,
            DurationSeconds = ?,
            TrainRowCount = ?,
            ScoreRowCount = ?,
            EpisodeCount = ?,
            HealthStatus = ?,
            AvgHealthIndex = ?,
            MinHealthIndex = ?,
            MaxFusedZ = ?,
            DataQualityScore = ?,
            RefitRequested = ?,
            KeptColumns = ?,
            ErrorMessage = ?
        """
        if include_zero_day:
            update_sql += """
            , ZeroDayScoringActive = ?,
            ZeroDayStatus = ?,
            ZeroDaySurfaceType = ?,
            ZeroDayChannelCount = ?
            """
        if include_representation and representation_status is not None:
            update_sql += """
            , RepresentationAuthoritative = ?,
            RepresentationScoreAllowed = ?,
            RepresentationLearnAllowed = ?,
            RepresentationContextLabel = ?,
            RepresentationRuntimeMode = ?,
            RepresentationSchemaCompatibility = ?,
            RepresentationBasisCompatibility = ?,
            RepresentationBaselineCompatibility = ?,
            RepresentationSuppressedReasons = ?,
            RepresentationDegradedReasons = ?
            """
        update_sql += """
        WHERE RunID = ?
        """
        
        # Prepare record (note: RunID is last for WHERE clause)
        record_parts = [
            equip_name,
            completed_at,
            duration_seconds,
            train_row_count,
            score_row_count,
            episode_count,
            health_status,
            _normalize_optional_float(avg_health_index),
            _normalize_optional_float(min_health_index),
            _normalize_optional_float(max_fused_z),
            _normalize_optional_float(data_quality_score),
            refit_requested,
            kept_columns,
            error_message,
        ]
        if include_zero_day and normalized_zero_day is not None:
            record_parts.extend(
                [
                    bool(normalized_zero_day.scoring_active),
                    normalized_zero_day.status,
                    normalized_zero_day.surface_type,
                    int(normalized_zero_day.channel_count),
                ]
            )
        if include_representation and representation_status is not None:
            record_parts.extend(
                [
                    bool(representation_status.authoritative),
                    representation_status.score_allowed,
                    representation_status.learn_allowed,
                    representation_status.context_label,
                    representation_status.runtime_mode,
                    representation_status.schema_compatibility,
                    representation_status.basis_compatibility,
                    representation_status.baseline_compatibility,
                    representation_status.suppressed_reasons_json,
                    representation_status.degraded_reasons_json,
                ]
            )
        record_parts.append(run_id)
        record = tuple(record_parts)
        
        # Execute update
        with sql_client.cursor() as cur:
            cur.execute(update_sql, record)
        
        # Commit
        sql_client.conn.commit()
        
        Console.info(f"Wrote run metadata to ACM_Runs: {run_id}", component="RUN_META")
        return True
        
    except Exception as e:
        Console.error(f"Failed to write ACM_Runs: {e}", component="RUN_META", run_id=run_id, equip_id=equip_id, equip_name=equip_name, error_type=type(e).__name__, error=str(e)[:200])
        try:
            sql_client.conn.rollback()
        except:
            pass
        return False


def compute_run_health_status(avg_health: float, min_health: float) -> str:
    """
    Determine overall run health status based on health metrics.
    
    Args:
        avg_health: Average health index (0-100)
        min_health: Minimum health index (0-100)
    
    Returns:
        str: "HEALTHY", "CAUTION", or "ALERT"
    """
    # Alert if minimum health is critically low
    if min_health < 50:
        return "ALERT"
    
    # Alert if average health is low
    if avg_health < 70:
        return "ALERT"
    
    # Caution if minimum health is borderline
    if min_health < 70:
        return "CAUTION"
    
    # Caution if average health is moderate
    if avg_health < 90:
        return "CAUTION"
    
    # Healthy
    return "HEALTHY"


def resolve_run_outcome_from_degradations(degradations: Optional[List[str]]) -> tuple[str, Optional[str]]:
    """
    Compute final run outcome from degradation list.

    Returns:
        Tuple of (outcome, err_json). err_json is populated only for DEGRADED.
    """
    if degradations:
        return "DEGRADED", json.dumps({"degraded_steps": degradations[:20]}, ensure_ascii=False)
    return "OK", None


def serialize_run_exception(exc: Exception) -> str:
    """
    Build stable JSON payload for run failure serialization.
    """
    try:
        return json.dumps({"type": exc.__class__.__name__, "message": str(exc)}, ensure_ascii=False)
    except Exception:
        return '{"type":"Exception","message":"<serialization failed>"}'


def finalize_noop_run(
    sql_client: Any,
    run_id: Optional[str],
    logger: Any = Console,
    zero_day_status: Optional[ZeroDayRunStatus] = None,
    equip_id: Optional[int] = None,
) -> None:
    """
    Finalize a run as NOOP with zero row counts.
    """
    if not sql_client or not run_id:
        return
    write_zero_day_run_status(
        sql_client=sql_client,
        run_id=run_id,
        zero_day_status=zero_day_status,
        equip_id=equip_id,
        logger=logger,
    )
    sql_client.finalize_run(
        run_id=run_id,
        outcome="NOOP",
        rows_read=0,
        rows_written=0,
        err_json=None,
    )
    logger.info(f"Finalized NOOP RunID={run_id}", component="RUN")


def extract_run_metadata_from_scores(scores: pd.DataFrame, per_regime_enabled: bool = False, regime_count: int = 0) -> dict:
    """
    Extract health and quality metrics from scores dataframe.
    
    Args:
        scores: Scores dataframe with fused z-scores and precomputed health
        per_regime_enabled: Whether per-regime calibration was enabled (DET-07)
        regime_count: Number of regimes detected
    
    Returns:
        dict: Metadata including health metrics and calibration info
    """
    import numpy as np
    metadata = {}
    
    try:
        if "fused" not in scores.columns:
            raise ValueError("No fused score column available for run metadata")

        fused = pd.to_numeric(scores["fused"], errors="coerce")
        if fused.notna().sum() == 0:
            raise ValueError("No finite fused score values available for run metadata")

        # Use precomputed health if available
        if "__health" in scores.columns:
            health = pd.to_numeric(scores["__health"], errors="coerce")
        else:
            # v10.1.0: Fallback uses softer sigmoid formula
            # OLD: 100/(1+Z^2) was too aggressive
            z_threshold = 5.0
            steepness = 1.5
            abs_z = np.abs(fused)
            normalized = (abs_z - z_threshold / 2) / (z_threshold / 4)
            sigmoid = 1 / (1 + np.exp(-normalized * steepness))
            health = np.clip(100.0 * (1 - sigmoid), 0.0, 100.0)

        health = pd.to_numeric(pd.Series(health, index=scores.index), errors="coerce")
        health_finite = health.dropna()
        fused_finite = fused.abs().dropna()
        if health_finite.empty or fused_finite.empty:
            raise ValueError("No finite health metrics available for run metadata")
        
        metadata["avg_health_index"] = float(health_finite.mean())
        metadata["min_health_index"] = float(health_finite.min())
        metadata["max_fused_z"] = float(fused_finite.max())
        
        # Health status
        metadata["health_status"] = compute_run_health_status(
            metadata["avg_health_index"],
            metadata["min_health_index"]
        )
        
        # DET-07: Add per-regime calibration info
        metadata["per_regime_enabled"] = per_regime_enabled
        metadata["regime_count"] = regime_count
        
    except Exception as e:
        Console.warn(f"Failed to extract health metrics: {e}", component="RUN_META", error_type=type(e).__name__, error=str(e)[:200])
        metadata["avg_health_index"] = None
        metadata["min_health_index"] = None
        metadata["max_fused_z"] = None
        metadata["health_status"] = "UNKNOWN"
        metadata["per_regime_enabled"] = False
        metadata["regime_count"] = 0
    
    return metadata


def extract_data_quality_score(
    sql_client: Any,
    run_id: str,
    equip_id: int,
) -> float:
    """
    Extract overall data quality score from ACM_DataQuality (SQL-only runtime).

    Args:
        sql_client: SQL client for database query.
        run_id: RunID for the current batch.
        equip_id: EquipID for the current equipment.

    Returns:
        float: Quality score in [0, 100]. Defaults to 100.0 if no records exist
        or if quality rows are not yet written for this run.
    """
    if sql_client is None:
        Console.warn(
            "Data quality query skipped: sql_client is None; defaulting to 100.0",
            component="RUN_META",
            run_id=run_id,
            equip_id=equip_id,
        )
        return 100.0

    if not run_id or int(equip_id) <= 0:
        Console.warn(
            "Data quality query skipped: invalid run_id/equip_id; defaulting to 100.0",
            component="RUN_META",
            run_id=run_id,
            equip_id=equip_id,
        )
        return 100.0

    try:
        query = """
            SELECT train_null_pct, score_null_pct
            FROM dbo.ACM_DataQuality
            WHERE RunID = ? AND EquipID = ? AND CheckName = 'data_quality'
        """
        with sql_client.cursor() as cur:
            cur.execute(query, (run_id, int(equip_id)))
            rows = cur.fetchall()

        if not rows:
            Console.debug(
                "No data quality rows found in SQL; defaulting to 100.0",
                component="RUN_META",
                run_id=run_id,
                equip_id=equip_id,
            )
            return 100.0

        train_null_values: List[float] = []
        score_null_values: List[float] = []
        for row in rows:
            train_null = row[0] if len(row) > 0 else None
            score_null = row[1] if len(row) > 1 else None
            if train_null is not None:
                train_null_values.append(float(train_null))
            if score_null is not None:
                score_null_values.append(float(score_null))

        if not train_null_values and not score_null_values:
            Console.debug(
                "Data quality rows contain no null-rate values; defaulting to 100.0",
                component="RUN_META",
                run_id=run_id,
                equip_id=equip_id,
            )
            return 100.0

        train_mean = float(np.mean(train_null_values)) if train_null_values else 0.0
        score_mean = float(np.mean(score_null_values)) if score_null_values else 0.0
        avg_null_pct = (train_mean + score_mean) / 2.0

        # Guard against unexpected out-of-range values.
        avg_null_pct = float(np.clip(avg_null_pct, 0.0, 100.0))
        quality_score = float(np.clip(100.0 * (1.0 - avg_null_pct / 100.0), 0.0, 100.0))

        Console.debug(
            f"Data quality from SQL: avg_null={avg_null_pct:.2f}%, score={quality_score:.1f}",
            component="RUN_META",
            run_id=run_id,
            equip_id=equip_id,
        )
        return quality_score
    except Exception as e:
        Console.warn(
            f"Failed to query ACM_DataQuality: {e}; defaulting to 100.0",
            component="RUN_META",
            run_id=run_id,
            equip_id=equip_id,
            error_type=type(e).__name__,
            error=str(e)[:200],
        )
        return 100.0


def write_retrain_metadata(
    sql_client,
    run_id: str,
    equip_id: int,
    equip_name: str,
    retrain_decision: bool,
    retrain_reason: str,
    forecast_state_version: int,
    model_age_batches: Optional[int] = None,
    forecast_rmse: Optional[float] = None,
    forecast_mae: Optional[float] = None,
    forecast_mape: Optional[float] = None,
) -> bool:
    """
    Write forecasting retrain decision + model age + quality metrics to ACM_RunMetadata.

    Args:
        sql_client: Active SQL client (must expose cursor()/conn)
        run_id: Current run unique identifier (UUID string)
        equip_id: Equipment numeric ID
        equip_name: Equipment code/name
        retrain_decision: Whether retraining occurred/is requested this batch
        retrain_reason: Reason string from should_retrain()
        forecast_state_version: Incrementing state version after merge
        model_age_batches: Batches since last retrain (optional if not tracked yet)
        forecast_rmse: Backtest RMSE (optional placeholder)
        forecast_mae: Backtest MAE (optional placeholder)
        forecast_mape: Backtest MAPE (optional placeholder)

    Returns:
        bool: True if insert succeeded.
    """
    if sql_client is None:
        Console.warn("No SQL client; skipping ACM_RunMetadata write", component="RUN_META", run_id=run_id, equip_id=equip_id)
        return False

    try:
        insert_sql = """
        INSERT INTO dbo.ACM_RunMetadata (
            RunID, EquipID, EquipName, CreatedAt,
            RetrainDecision, RetrainReason, ForecastStateVersion,
            ModelAgeBatches, ForecastRMSE, ForecastMAE, ForecastMAPE
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        created_at = datetime.utcnow().replace(tzinfo=None)
        record = (
            run_id,
            int(equip_id),
            equip_name,
            created_at,
            bool(retrain_decision),
            retrain_reason[:250] if retrain_reason else None,
            int(forecast_state_version) if forecast_state_version is not None else None,
            int(model_age_batches) if model_age_batches is not None else None,
            float(forecast_rmse) if forecast_rmse is not None else None,
            float(forecast_mae) if forecast_mae is not None else None,
            float(forecast_mape) if forecast_mape is not None else None,
        )

        with sql_client.cursor() as cur:
            cur.execute(insert_sql, record)
        sql_client.conn.commit()
        Console.info(f"Wrote retrain metadata RunID={run_id} StateV={forecast_state_version}", component="RUN_META")
        return True
    except Exception as e:
        Console.error(
            f"Failed to write ACM_RunMetadata: {e}",
            component="RUN_META",
            run_id=run_id,
            equip_id=equip_id,
            equip_name=equip_name,
            error_type=type(e).__name__,
            error=str(e)[:200],
        )
        try:
            sql_client.conn.rollback()
        except Exception:
            pass
        return False


def emit_batch_summary(
    console: Any,
    equip: str,
    run_id: Optional[str],
    win_start: Optional[pd.Timestamp],
    win_end: Optional[pd.Timestamp],
    outcome: str,
    frame: Optional[pd.DataFrame] = None,
    episodes: Optional[pd.DataFrame] = None,
    score_out: Optional[Dict[str, Any]] = None,
    regime_quality_ok: bool = False,
    model_state: Optional[Any] = None,
    rows_read: int = 0,
    train: Optional[pd.DataFrame] = None,
    degradations: Optional[List[str]] = None,
    refit_requested: bool = False,
    timer: Optional[Any] = None,
    zero_day_status: Optional[ZeroDayRunStatus] = None,
    representation_status: Optional[RepresentationRunStatus] = None,
) -> None:
    """
    Emit consolidated batch summary and timing logs (best-effort).
    """
    try:
        from core.analytics_builder import health_index as _compute_health_index

        _eq = equip if equip else "?"
        _ws = win_start.strftime("%Y-%m-%d %H:%M") if win_start is not None else "?"
        _we = win_end.strftime("%H:%M") if win_end is not None else "?"
        _rid = str(run_id)[:8] if run_id else "?"
        _out = outcome if outcome else "?"

        # Health summary
        _health_str = ""
        _health_status = "?"
        _anomaly_str = ""
        if isinstance(frame, pd.DataFrame) and "fused" in frame.columns:
            _fused = frame["fused"].dropna().to_numpy()
            if len(_fused) > 0:
                _hi = _compute_health_index(_fused)
                _health_str = (
                    f"avg={np.mean(_hi):.1f}%  min={np.min(_hi):.1f}%  max={np.max(_hi):.1f}%  "
                    f"P10={np.percentile(_hi,10):.1f}%  P50={np.percentile(_hi,50):.1f}%"
                )
                _health_status = compute_run_health_status(float(np.mean(_hi)), float(np.min(_hi)))
                _n_anom = int((_fused > 3.0).sum())
                _anomaly_str = f"{_n_anom}/{len(_fused)} ({_n_anom/len(_fused)*100:.1f}%)"

        # RUL (forecasting disabled)
        _rul_str = "disabled"

        # Episodes
        _ep_str = ""
        if isinstance(episodes, pd.DataFrame):
            _ep_total = len(episodes)
            _active_col = next((c for c in ("Active", "active", "IsActive") if c in episodes.columns), None)
            _ep_active = int(episodes[_active_col].sum()) if _active_col else 0
            _sev_cols = [c for c in ("severity", "Severity") if c in episodes.columns]
            _ep_str = f"{_ep_total} total, {_ep_active} active"
            if _sev_cols and _ep_total > 0:
                _sevs = episodes[_sev_cols[0]].dropna()
                if len(_sevs) > 0:
                    _ep_str += f", avg_severity={_sevs.mean():.2f}"

        # Regime
        _regime_str = ""
        if isinstance(score_out, dict):
            _k = score_out.get("regime_k", 0)
            _qok = "OK" if regime_quality_ok else "FAIL"
            _regime_str = f"K={_k}  quality={_qok}"
            if isinstance(frame, pd.DataFrame) and "regime_label" in frame.columns:
                _dom = frame["regime_label"].mode()
                if len(_dom) > 0 and len(frame) > 0:
                    _dom_pct = (frame["regime_label"] == _dom.iloc[0]).sum() / len(frame) * 100
                    _regime_str += f"  dominant=R{int(_dom.iloc[0])}({_dom_pct:.0f}%)"

        # Drift
        _drift_str = ""
        if isinstance(frame, pd.DataFrame) and "drift_mode" in frame.columns and len(frame) > 0:
            _drift_str = str(frame["drift_mode"].iloc[-1])

        # Model
        _model_str = ""
        if model_state is not None:
            _ms = model_state
            _model_str = f"{_ms.maturity.value}  runs={_ms.consecutive_runs}  days={_ms.training_days:.1f}"

        # Data volume
        _scored = rows_read
        _trained = len(train) if isinstance(train, pd.DataFrame) else "?"

        # Timing
        _timing_str = ""
        if timer is not None and hasattr(timer, "totals") and timer.totals:
            _total_t = timer.total_elapsed() if hasattr(timer, "total_elapsed") else sum(timer.totals.values())
            _top = sorted(timer.totals.items(), key=lambda x: x[1], reverse=True)[:5]
            _timing_str = f"total={_total_t:.1f}s  " + "  ".join(f"{s}={t:.1f}s" for s, t in _top)

        _deg = ", ".join(degradations) if degradations else "none"
        _refit = "yes" if refit_requested else "no"
        _zero_day = "status=?"
        if zero_day_status is not None:
            _z = build_zero_day_run_status(
                scoring_active=zero_day_status.scoring_active,
                status=zero_day_status.status,
                surface_type=zero_day_status.surface_type,
                channel_count=zero_day_status.channel_count,
            )
            _zero_day = (
                f"status={_z.status}  active={'yes' if _z.scoring_active else 'no'}  "
                f"surface={_z.surface_type}  channels={_z.channel_count}"
            )
        _representation = "mode=?"
        if representation_status is not None:
            _representation = (
                f"mode={representation_status.runtime_mode}  "
                f"authoritative={'yes' if representation_status.authoritative else 'no'}  "
                f"score_allowed={representation_status.score_allowed}  "
                f"learn_allowed={representation_status.learn_allowed}  "
                f"context={representation_status.context_label}  "
                f"schema={representation_status.schema_compatibility}  "
                f"basis={representation_status.basis_compatibility}  "
                f"baseline={representation_status.baseline_compatibility}"
            )

        console.info(
            f"Batch summary | {_eq} | RunID={_rid} | [{_ws}-{_we}] | outcome={_out} | "
            f"health=[{_health_str}] status={_health_status} | "
            f"anomalies={_anomaly_str} | "
            f"episodes=[{_ep_str}] | "
            f"RUL=[{_rul_str}] | "
            f"regime=[{_regime_str}] | drift={_drift_str} | "
            f"zero_day=[{_zero_day}] | "
            f"representation=[{_representation}] | "
            f"model=[{_model_str}] | "
            f"data={_scored} scored, {_trained} trained | "
            f"refit={_refit} | degraded=[{_deg}]",
            component="SUMMARY",
            equip=_eq,
            run_id=_rid,
            outcome=_out,
            health_status=_health_status,
        )
        if _timing_str:
            console.info(f"Timing | {_timing_str}", component="SUMMARY")
    except Exception:
        pass


def finalize_run_with_metadata(
    sql_client: Any,
    output_manager: Optional[Any],
    run_id: Optional[str],
    equip_id: int,
    equip_name: str,
    started_at: datetime,
    outcome: str,
    rows_read: int,
    rows_written: int,
    err_json: Optional[str],
    frame: Optional[pd.DataFrame] = None,
    train: Optional[pd.DataFrame] = None,
    episodes: Optional[pd.DataFrame] = None,
    meta: Optional[Any] = None,
    refit_requested: bool = False,
    config_signature: str = "UNKNOWN",
    per_regime_enabled: bool = False,
    regime_count: int = 0,
    observability_enabled: bool = False,
    record_data_quality_fn: Optional[Any] = None,
    record_run_fn: Optional[Any] = None,
    record_batch_processed_fn: Optional[Any] = None,
    record_health_score_fn: Optional[Any] = None,
    record_error_fn: Optional[Any] = None,
    logger: Any = Console,
    zero_day_status: Optional[ZeroDayRunStatus] = None,
    representation_status: Optional[RepresentationRunStatus] = None,
) -> None:
    """
    Finalize ACM run metadata + status and close SQL/output resources (best-effort).
    """
    if not sql_client or not run_id:
        return

    record_data_quality = record_data_quality_fn or (lambda *a, **k: None)
    record_run = record_run_fn or (lambda *a, **k: None)
    record_batch_processed = record_batch_processed_fn or (lambda *a, **k: None)
    record_health_score = record_health_score_fn or (lambda *a, **k: None)
    record_error = record_error_fn or (lambda *a, **k: None)

    try:
        completed_at = datetime.now()

        if isinstance(frame, pd.DataFrame) and len(frame) > 0:
            run_metadata = extract_run_metadata_from_scores(
                frame,
                per_regime_enabled=per_regime_enabled,
                regime_count=regime_count,
            )
            data_quality_score = extract_data_quality_score(
                sql_client=sql_client,
                run_id=run_id,
                equip_id=equip_id,
            )
            record_data_quality(equip_name, float(data_quality_score) if data_quality_score else 0.0)
        else:
            run_metadata = {
                "health_status": "UNKNOWN",
                "avg_health_index": None,
                "min_health_index": None,
                "max_fused_z": None,
            }
            data_quality_score = 0.0

        write_run_metadata(
            sql_client=sql_client,
            run_id=run_id,
            equip_id=int(equip_id),
            equip_name=equip_name,
            started_at=started_at,
            completed_at=completed_at,
            config_signature=config_signature,
            train_row_count=len(train) if isinstance(train, pd.DataFrame) else 0,
            score_row_count=len(frame) if isinstance(frame, pd.DataFrame) else rows_read,
            episode_count=len(episodes) if isinstance(episodes, pd.DataFrame) else 0,
            health_status=run_metadata.get("health_status", "UNKNOWN"),
            avg_health_index=run_metadata.get("avg_health_index"),
            min_health_index=run_metadata.get("min_health_index"),
            max_fused_z=run_metadata.get("max_fused_z"),
            data_quality_score=data_quality_score,
            refit_requested=bool(refit_requested),
            kept_columns=",".join(getattr(meta, "kept_cols", [])) if meta is not None else "",
            error_message=err_json if outcome in ("FAIL", "DEGRADED") else None,
            zero_day_status=zero_day_status,
            representation_status=representation_status,
        )

        sql_client.finalize_run(
            run_id=run_id,
            outcome=outcome,
            rows_read=rows_read,
            rows_written=rows_written,
            err_json=err_json,
        )
        logger.info(
            f"Finalized RunID={run_id} outcome={outcome} rows_in={rows_read} rows_out={rows_written}",
            component="RUN",
        )

        if observability_enabled and started_at:
            duration_seconds = (completed_at - started_at).total_seconds()
            record_run(equip_name, outcome or "OK", duration_seconds)
            record_batch_processed(
                equip_name,
                rows=rows_read,
                duration_seconds=duration_seconds,
                outcome=(outcome or "ok").lower(),
            )
            if run_metadata.get("avg_health_index") is not None:
                record_health_score(equip_name, float(run_metadata["avg_health_index"]))
            if outcome == "FAIL":
                record_error(equip_name, str(err_json) if err_json else "Run failed", "RunFailure")

    except Exception as e:
        logger.error(
            f"Run finalization failed: {e}",
            component="RUN",
            equip=equip_name,
            run_id=run_id,
        )
    finally:
        try:
            if output_manager is not None:
                output_manager.close()
        except Exception:
            pass
        try:
            sql_client.close()
        except Exception:
            pass


@dataclass
class PipelineTeardownState:
    """Typed teardown payload passed from ACM orchestrator."""
    console: Any
    equip: str
    run_id: Optional[str]
    win_start: Optional[pd.Timestamp]
    win_end: Optional[pd.Timestamp]
    outcome: str
    frame: Optional[pd.DataFrame]
    episodes: Optional[pd.DataFrame]
    score_out: Optional[Dict[str, Any]]
    regime_quality_ok: bool
    model_state: Optional[Any]
    rows_read: int
    train: Optional[pd.DataFrame]
    degradations: Optional[List[str]]
    refit_requested: bool
    timer: Optional[Any]
    sql_client: Any
    output_manager: Optional[Any]
    equip_id: int
    equip_name: str
    started_at: datetime
    rows_written: int
    err_json: Optional[str]
    meta: Optional[Any]
    config_signature: str
    per_regime_enabled: bool
    regime_count: int
    observability_enabled: bool
    record_data_quality_fn: Optional[Any]
    record_run_fn: Optional[Any]
    record_batch_processed_fn: Optional[Any]
    record_health_score_fn: Optional[Any]
    record_error_fn: Optional[Any]
    zero_day_status: Optional[ZeroDayRunStatus]
    representation_status: Optional[RepresentationRunStatus]
    span_ctx: Optional[Any]
    root_span: Optional[Any]
    close_run_span_fn: Any
    shutdown_run_observability_fn: Any


def finalize_pipeline_teardown(state: PipelineTeardownState) -> None:
    """
    Consolidated teardown for summary, SQL finalization, and observability shutdown.
    """
    emit_batch_summary(
        console=state.console,
        equip=state.equip,
        run_id=state.run_id,
        win_start=state.win_start,
        win_end=state.win_end,
        outcome=state.outcome,
        frame=state.frame,
        episodes=state.episodes,
        score_out=state.score_out,
        regime_quality_ok=state.regime_quality_ok,
        model_state=state.model_state,
        rows_read=state.rows_read,
        train=state.train,
        degradations=state.degradations,
        refit_requested=state.refit_requested,
        timer=state.timer,
        zero_day_status=state.zero_day_status,
        representation_status=state.representation_status,
    )

    finalize_run_with_metadata(
        sql_client=state.sql_client,
        output_manager=state.output_manager,
        run_id=state.run_id,
        equip_id=int(state.equip_id),
        equip_name=state.equip_name,
        started_at=state.started_at,
        outcome=state.outcome,
        rows_read=state.rows_read,
        rows_written=state.rows_written,
        err_json=state.err_json,
        frame=state.frame,
        train=state.train,
        episodes=state.episodes,
        meta=state.meta,
        refit_requested=state.refit_requested,
        config_signature=state.config_signature,
        per_regime_enabled=state.per_regime_enabled,
        regime_count=state.regime_count,
        observability_enabled=state.observability_enabled,
        record_data_quality_fn=state.record_data_quality_fn,
        record_run_fn=state.record_run_fn,
        record_batch_processed_fn=state.record_batch_processed_fn,
        record_health_score_fn=state.record_health_score_fn,
        record_error_fn=state.record_error_fn,
        logger=state.console,
        zero_day_status=state.zero_day_status,
        representation_status=state.representation_status,
    )

    state.close_run_span_fn(
        span_ctx=state.span_ctx,
        root_span=state.root_span,
        outcome=state.outcome,
        rows_read=state.rows_read,
        rows_written=state.rows_written,
    )

    state.shutdown_run_observability_fn(state.observability_enabled)
