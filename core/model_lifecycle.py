# core/model_lifecycle.py
"""
Model Lifecycle Management for V11
===================================
Tracks model maturity states and promotion criteria.

MaturityState Lifecycle:
    COLDSTART -> LEARNING -> CONVERGED -> DEPRECATED

Promotion Criteria (LEARNING -> CONVERGED):
    - Minimum 7 days of training data
    - Regime clustering quality passes metric-specific threshold
    - Stability ratio >= 0.75 (no regime thrashing)
    - At least 5 consecutive successful runs
    - Optional: forecast MAPE and RMSE within acceptable bounds

Regime Quality Metrics and their promotion thresholds:
    - silhouette  [-1, 1]:  score >= min_silhouette_score (default 0.40)
    - dbcv        [-1, 1]:  score >= min_dbcv_score       (default 0.0)
    - calinski_harabasz [0, inf]: normalised; treat same as silhouette scale only when
                                < 100 (raw values can be large - use quality_ok flag)
    - bic         (-inf, 0]:  absolute value cannot be thresholded; rely on
                            regime_quality_ok boolean from regimes.py instead

v11.11.0 change: regime quality check is now metric-aware. Storing a raw BIC value
in silhouette_score and comparing it to 0.40 used to block LEARNING->CONVERGED forever
for GMM-based regime detection.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import math
from typing import Dict, Any, Optional, List
import json

from core.observability import Console


class MaturityState(str, Enum):
    """Model maturity states for lifecycle tracking."""
    COLDSTART = "COLDSTART"    # Initial state - insufficient data
    LEARNING = "LEARNING"      # Training in progress, not yet reliable
    CONVERGED = "CONVERGED"    # Quality criteria passed, production-ready
    DEPRECATED = "DEPRECATED"  # Superseded by newer version

    def __str__(self) -> str:
        return self.value


# Metrics whose raw scores are on a [-1, 1] or [0, 1] scale and can be compared
# against a numeric threshold directly.
_SILHOUETTE_SCALE_METRICS = frozenset({"silhouette", "silhouette_non_noise"})

# Metrics whose raw scores are on a [-1, 1] scale but have different semantics
# than silhouette (HDBSCAN validity index).
_DBCV_SCALE_METRICS = frozenset({"dbcv", "persistence"})

# Metrics whose raw values cannot be compared against a meaningful fixed threshold.
# For these we rely exclusively on the regime_quality_ok boolean flag.
# Public alias: also imported by acm_main.py for the retrain-trigger check.
BOOLEAN_ONLY_METRICS = frozenset({"bic", "calinski_harabasz", "aic", "inertia"})
_BOOLEAN_ONLY_METRICS = BOOLEAN_ONLY_METRICS  # backward-compat internal alias


@dataclass
class PromotionCriteria:
    """Criteria for promoting model from LEARNING to CONVERGED.

    P0-FIX (v11.2.2): ANALYTICAL AUDIT FLAW #10 - Tightened promotion criteria
    Previous thresholds were too permissive, allowing unreliable models to reach
    CONVERGED state. New thresholds ensure production-grade reliability.

    v11.11.0: Added metric-aware regime quality thresholds.
    - min_silhouette_score: applies only to silhouette/silhouette_non_noise metrics
    - min_dbcv_score: applies only to dbcv/persistence metrics (HDBSCAN)
    - BIC/calinski_harabasz: threshold is not meaningful; regime_quality_ok flag is
      the sole gate for these metrics

    These defaults can be overridden via config_table.csv under 'lifecycle' category:
    - lifecycle.promotion.min_training_days
    - lifecycle.promotion.min_silhouette_score
    - lifecycle.promotion.min_dbcv_score
    - lifecycle.promotion.min_stability_ratio
    - lifecycle.promotion.min_consecutive_runs
    - lifecycle.promotion.min_training_rows
    - lifecycle.promotion.max_forecast_mape
    - lifecycle.promotion.max_forecast_rmse

    Reference:
        MAPE < 35% is good for industrial forecasting (Hyndman 2018, adjusted)
        Silhouette > 0.4 indicates reasonable cluster separation (Rousseeuw 1987)
        DBCV > 0.0 indicates non-trivial cluster structure (Moulavi et al. 2014)
        RMSE < 12 on 0-100 health scale = good prediction accuracy
    """
    min_training_days: int = 7
    min_silhouette_score: float = 0.15   # For silhouette-scale metrics only. Matches config_table.csv.
    min_dbcv_score: float = 0.0          # For HDBSCAN DBCV/persistence metrics
    min_stability_ratio: float = 0.60   # Matches config_table.csv.
    min_consecutive_runs: int = 3        # Matches config_table.csv.
    min_training_rows: int = 200         # Matches config_table.csv.
    max_forecast_mape: float = 35.0
    max_forecast_rmse: float = 12.0

    @classmethod
    def from_config(cls, cfg: Dict[str, Any]) -> "PromotionCriteria":
        """
        Create PromotionCriteria from config dictionary.

        Looks for values in cfg['lifecycle']['promotion'] with fallback to defaults.
        """
        lifecycle = cfg.get("lifecycle", {}) or {}
        promotion = lifecycle.get("promotion", {}) or {}

        return cls(
            min_training_days=int(promotion.get("min_training_days", 7)),
            min_silhouette_score=float(promotion.get("min_silhouette_score", 0.40)),
            min_dbcv_score=float(promotion.get("min_dbcv_score", 0.0)),
            min_stability_ratio=float(promotion.get("min_stability_ratio", 0.75)),
            min_consecutive_runs=int(promotion.get("min_consecutive_runs", 5)),
            min_training_rows=int(promotion.get("min_training_rows", 400)),
            max_forecast_mape=float(promotion.get("max_forecast_mape", 35.0)),
            max_forecast_rmse=float(promotion.get("max_forecast_rmse", 12.0)),
        )


@dataclass
class ModelState:
    """Current state of a model version for an equipment."""
    equip_id: int
    version: int
    maturity: MaturityState
    created_at: datetime
    promoted_at: Optional[datetime] = None
    deprecated_at: Optional[datetime] = None

    # Regime quality metrics
    # regime_quality_score holds the raw score from whichever metric was used.
    # It maps to the SilhouetteScore SQL column for storage (column pre-dates metric
    # awareness). Interpretation depends on regime_quality_metric.
    regime_quality_score: Optional[float] = None
    regime_quality_metric: str = "silhouette"   # e.g. "silhouette", "dbcv", "bic"
    regime_quality_ok: Optional[bool] = None    # boolean gate from regimes.py

    stability_ratio: Optional[float] = None
    training_rows: int = 0
    training_days: float = 0.0
    consecutive_runs: int = 0

    # Forecast quality metrics
    forecast_mape: Optional[float] = None
    forecast_rmse: Optional[float] = None

    # Run tracking
    last_run_id: Optional[str] = None
    last_run_at: Optional[datetime] = None
    total_runs: int = 0

    # ------------------------------------------------------------------
    # Backward-compat property: old code used silhouette_score everywhere.
    # Reading it returns regime_quality_score; writing updates it too.
    # ------------------------------------------------------------------
    @property
    def silhouette_score(self) -> Optional[float]:
        return self.regime_quality_score

    @silhouette_score.setter
    def silhouette_score(self, value: Optional[float]) -> None:
        self.regime_quality_score = value

    @property
    def total_days(self) -> float:
        """Alias for training_days for backward compatibility."""
        return self.training_days

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for SQL persistence."""
        return {
            'EquipID': self.equip_id,
            'Version': self.version,
            'MaturityState': str(self.maturity),
            'CreatedAt': self.created_at,
            'PromotedAt': self.promoted_at,
            'DeprecatedAt': self.deprecated_at,
            'SilhouetteScore': self.regime_quality_score,
            'StabilityRatio': self.stability_ratio,
            'TrainingRows': self.training_rows,
            'TrainingDays': self.training_days,
            'ConsecutiveRuns': self.consecutive_runs,
            'LastRunID': self.last_run_id,
            'LastRunAt': self.last_run_at,
            'TotalRuns': self.total_runs,
        }


def _regime_quality_criterion_met(
    state: ModelState,
    criteria: PromotionCriteria,
) -> tuple[bool, Optional[str]]:
    """
    Evaluate whether the regime clustering quality criterion is met.

    Returns (met: bool, unmet_reason: str | None).

    Logic:
      - silhouette-scale metrics  : compare raw score against min_silhouette_score
      - DBCV-scale metrics        : compare raw score against min_dbcv_score
      - Boolean-only metrics (BIC): rely on regime_quality_ok flag exclusively
      - Unknown metric            : rely on regime_quality_ok flag if set,
                                    otherwise default to passing (don't block on
                                    metrics we don't understand)
    """
    metric = state.regime_quality_metric or "silhouette"
    score = state.regime_quality_score
    quality_ok = state.regime_quality_ok  # may be None if not set

    if metric in _SILHOUETTE_SCALE_METRICS:
        # Score in [-1, 1]; compare against threshold
        if score is None or score < criteria.min_silhouette_score:
            s = score if score is not None else 0.0
            return False, f"{metric}={s:.3f} < {criteria.min_silhouette_score}"
        return True, None

    if metric in _DBCV_SCALE_METRICS:
        # DBCV in [-1, 1]; > 0.0 means non-trivial cluster structure
        if score is None or score < criteria.min_dbcv_score:
            s = score if score is not None else 0.0
            return False, f"{metric}={s:.3f} < {criteria.min_dbcv_score}"
        return True, None

    if metric in _BOOLEAN_ONLY_METRICS:
        # Raw score is not on a fixed scale; rely on the quality_ok boolean.
        if quality_ok is False:
            s = score if score is not None else 0.0
            return False, f"regime_quality_ok=False ({metric}={s:.3f})"
        # quality_ok=True or quality_ok=None (unknown) -> pass
        return True, None

    # Unknown metric - trust quality_ok if available, otherwise pass.
    if quality_ok is False:
        s = score if score is not None else 0.0
        return False, f"regime_quality_ok=False ({metric}={s:.3f})"
    return True, None


def check_promotion_eligibility(
    state: ModelState,
    criteria: Optional[PromotionCriteria] = None
) -> tuple[bool, List[str]]:
    """
    Check if a model in LEARNING state can be promoted to CONVERGED.

    Regime quality check is metric-aware (v11.11.0):
    - silhouette / silhouette_non_noise : compare raw score against threshold
    - dbcv / persistence (HDBSCAN)      : compare raw score against dbcv threshold
    - bic / calinski_harabasz / aic     : rely on regime_quality_ok boolean only

    Args:
        state: Current model state
        criteria: Promotion criteria (uses defaults if not provided)

    Returns:
        Tuple of (eligible: bool, reasons: list of unmet criteria)
    """
    if criteria is None:
        criteria = PromotionCriteria()

    unmet: List[str] = []

    if state.maturity != MaturityState.LEARNING:
        return False, [f"Not in LEARNING state (current: {state.maturity})"]

    if state.training_days < criteria.min_training_days:
        unmet.append(f"training_days={state.training_days:.1f} < {criteria.min_training_days}")

    # Metric-aware regime quality check
    quality_met, quality_reason = _regime_quality_criterion_met(state, criteria)
    if not quality_met:
        unmet.append(quality_reason)

    if state.stability_ratio is None or state.stability_ratio < criteria.min_stability_ratio:
        ratio = state.stability_ratio or 0.0
        unmet.append(f"stability={ratio:.2f} < {criteria.min_stability_ratio}")

    if state.consecutive_runs < criteria.min_consecutive_runs:
        unmet.append(f"consecutive_runs={state.consecutive_runs} < {criteria.min_consecutive_runs}")

    if state.training_rows < criteria.min_training_rows:
        unmet.append(f"training_rows={state.training_rows} < {criteria.min_training_rows}")

    if state.forecast_mape is not None and state.forecast_mape > criteria.max_forecast_mape:
        unmet.append(f"forecast_mape={state.forecast_mape:.1f}% > {criteria.max_forecast_mape}%")

    if state.forecast_rmse is not None and state.forecast_rmse > criteria.max_forecast_rmse:
        unmet.append(f"forecast_rmse={state.forecast_rmse:.2f} > {criteria.max_forecast_rmse}")

    eligible = len(unmet) == 0
    return eligible, unmet


def promote_model(state: ModelState) -> ModelState:
    """
    Promote a model from LEARNING to CONVERGED.
    """
    if state.maturity != MaturityState.LEARNING:
        raise ValueError(f"Cannot promote model in {state.maturity} state")

    state.maturity = MaturityState.CONVERGED
    state.promoted_at = datetime.now()

    Console.info(
        f"Model v{state.version} promoted LEARNING → CONVERGED. "
        f"Regime metric={state.regime_quality_metric} score={state.regime_quality_score}, "
        f"stability={state.stability_ratio}, consecutive_runs={state.consecutive_runs}.",
        component="LIFECYCLE",
        equip_id=state.equip_id,
        version=state.version,
        regime_metric=state.regime_quality_metric,
        regime_score=state.regime_quality_score,
        stability=state.stability_ratio,
    )

    return state


def deprecate_model(state: ModelState, reason: str = "") -> ModelState:
    """
    Deprecate a model (superseded by newer version).
    """
    old_maturity = state.maturity
    state.maturity = MaturityState.DEPRECATED
    state.deprecated_at = datetime.now()

    Console.info(
        f"Model v{state.version} deprecated ({old_maturity} -> DEPRECATED)",
        component="LIFECYCLE",
        equip_id=state.equip_id,
        version=state.version,
        reason=reason,
    )

    return state


def create_new_model_state(
    equip_id: int,
    version: int,
    training_rows: int,
    training_start: datetime,
    training_end: datetime,
    silhouette_score: Optional[float] = None,
    regime_quality_metric: str = "silhouette",
    regime_quality_ok: Optional[bool] = None,
    run_id: Optional[str] = None,
) -> ModelState:
    """
    Create a new model state in LEARNING maturity.

    Args:
        equip_id: Equipment ID
        version: Model version number
        training_rows: Number of rows in training data
        training_start: Start of training window
        training_end: End of training window
        silhouette_score: Raw regime quality score (value meaning depends on
                          regime_quality_metric)
        regime_quality_metric: The metric used for regime quality assessment
                               ("silhouette", "dbcv", "bic", etc.)
        regime_quality_ok: Boolean quality flag from regimes.py (used for
                           metrics that can't be compared via threshold)
        run_id: Run ID that created this model
    """
    training_days = (training_end - training_start).total_seconds() / 86400.0

    state = ModelState(
        equip_id=equip_id,
        version=version,
        maturity=MaturityState.LEARNING,
        created_at=datetime.now(),
        regime_quality_score=silhouette_score,
        regime_quality_metric=regime_quality_metric,
        regime_quality_ok=regime_quality_ok,
        training_rows=training_rows,
        training_days=training_days,
        consecutive_runs=1,
        last_run_id=run_id,
        last_run_at=datetime.now(),
        total_runs=1,
    )

    Console.info(
        f"New model v{version} created in LEARNING state "
        f"({training_rows} training rows, {training_days:.1f} training days). "
        "Model will accumulate consecutive scoring runs before promotion to CONVERGED.",
        component="LIFECYCLE",
        equip_id=equip_id,
        version=version,
        training_rows=training_rows,
        training_days=f"{training_days:.1f}",
    )

    return state


def update_model_state_from_run(
    state: ModelState,
    run_id: str,
    run_success: bool,
    silhouette_score: Optional[float] = None,
    regime_quality_metric: Optional[str] = None,
    regime_quality_ok: Optional[bool] = None,
    stability_ratio: Optional[float] = None,
    additional_rows: int = 0,
    additional_days: float = 0.0,
    forecast_mape: Optional[float] = None,
    forecast_rmse: Optional[float] = None,
) -> ModelState:
    """
    Update model state after a run completes.

    Args:
        state: Current model state
        run_id: Run ID
        run_success: Whether run completed successfully
        silhouette_score: Raw regime quality score for this run
        regime_quality_metric: Metric used ("silhouette", "dbcv", "bic", ...)
        regime_quality_ok: Boolean quality flag from regimes.py
        stability_ratio: Regime stability ratio
        additional_rows: Rows processed in this run
        additional_days: Days of data processed in this run
        forecast_mape: Forecast MAPE from this run
        forecast_rmse: Forecast RMSE from this run
    """
    state.last_run_id = run_id
    state.last_run_at = datetime.now()
    state.total_runs += 1

    if run_success:
        state.consecutive_runs += 1
    else:
        state.consecutive_runs = 0  # Reset on failure

    if silhouette_score is not None:
        state.regime_quality_score = silhouette_score

    if regime_quality_metric is not None:
        state.regime_quality_metric = regime_quality_metric

    if regime_quality_ok is not None:
        state.regime_quality_ok = regime_quality_ok

    if stability_ratio is not None:
        state.stability_ratio = stability_ratio

    if forecast_mape is not None:
        state.forecast_mape = forecast_mape

    if forecast_rmse is not None:
        state.forecast_rmse = forecast_rmse

    state.training_rows += additional_rows
    state.training_days += additional_days

    return state


def update_and_persist_model_lifecycle(
    *,
    sql_client: Any,
    output_manager: Any,
    equip_id: int,
    regime_state_version: int,
    cfg: Dict[str, Any],
    train_data: Any,
    run_id: Optional[str],
    regime_model: Optional[Any],
    score_out: Optional[Dict[str, Any]],
    regime_quality_ok: Optional[bool],
    logger: Any = Console,
) -> Optional[ModelState]:
    """
    Update lifecycle state after model training and persist active-model pointers.

    This keeps lifecycle policy in one owner module and lets the pipeline call a
    single function instead of inlining the same logic.
    """
    if sql_client is None or output_manager is None:
        return None

    # Resolve training window from the current training dataframe.
    if hasattr(train_data, "index") and len(train_data.index) > 0:
        train_start_raw = train_data.index.min()
        train_end_raw = train_data.index.max()
    else:
        train_start_raw = datetime.now()
        train_end_raw = datetime.now()

    if isinstance(train_start_raw, datetime):
        train_start = train_start_raw
    elif hasattr(train_start_raw, "to_pydatetime"):
        train_start = train_start_raw.to_pydatetime()
    else:
        train_start = datetime.now()

    if isinstance(train_end_raw, datetime):
        train_end = train_end_raw
    elif hasattr(train_end_raw, "to_pydatetime"):
        train_end = train_end_raw.to_pydatetime()
    else:
        train_end = datetime.now()

    # Metric name: prefer score_out (most current), then model fit metadata.
    if score_out and score_out.get("regime_metric"):
        regime_fit_metric = score_out["regime_metric"]
    elif regime_model is not None and hasattr(regime_model, "meta"):
        regime_fit_metric = regime_model.meta.get("fit_metric", "silhouette")
    else:
        regime_fit_metric = "silhouette"

    # Score: prefer model fit score, then label-time score.
    if regime_model is not None and hasattr(regime_model, "meta"):
        regime_fit_score = regime_model.meta.get("fit_score")
        if regime_fit_score is None and score_out:
            regime_fit_score = score_out.get("regime_score")
    elif score_out:
        regime_fit_score = score_out.get("regime_score")
    else:
        regime_fit_score = None

    # Compute weighted stability across regimes when available.
    actual_stability = 1.0 if regime_quality_ok else 0.75
    if regime_model is not None and hasattr(regime_model, "stats") and regime_model.stats:
        total_samples = 0
        weighted_stability = 0.0
        for _regime_id, stat in regime_model.stats.items():
            count = stat.get("count", 0)
            stab = stat.get("stability_score", 1.0)
            try:
                stab_f = float(stab)
            except Exception:
                continue
            if count > 0 and math.isfinite(stab_f):
                weighted_stability += stab_f * count
                total_samples += count
        if total_samples > 0:
            actual_stability = weighted_stability / total_samples

    model_state = load_model_state_from_sql(sql_client, equip_id)
    if model_state is None:
        model_state = create_new_model_state(
            equip_id=int(equip_id),
            version=regime_state_version,
            training_rows=len(train_data),
            training_start=train_start,
            training_end=train_end,
            silhouette_score=regime_fit_score,
            regime_quality_metric=regime_fit_metric,
            regime_quality_ok=regime_quality_ok if regime_quality_ok is not None else True,
            run_id=run_id,
        )
    else:
        training_days = (train_end - train_start).total_seconds() / 86400.0
        model_state = update_model_state_from_run(
            state=model_state,
            run_id=run_id,  # type: ignore[arg-type]
            run_success=True,
            silhouette_score=regime_fit_score,
            regime_quality_metric=regime_fit_metric,
            regime_quality_ok=regime_quality_ok if regime_quality_ok is not None else True,
            stability_ratio=actual_stability,
            additional_rows=len(train_data),
            additional_days=training_days,
        )

        if model_state.maturity == MaturityState.LEARNING:
            promotion_criteria = PromotionCriteria.from_config(cfg or {})
            eligible, unmet = check_promotion_eligibility(model_state, promotion_criteria)
            if eligible:
                old_maturity = model_state.maturity.value
                model_state = promote_model(model_state)
                try:
                    promotion_record = [{
                        "RegimeLabel": "ALL",
                        "FromState": old_maturity,
                        "ToState": model_state.maturity.value,
                        "Reason": "met_promotion_criteria",
                        "PromotedAt": datetime.now(),
                        "Version": model_state.version,
                        "ConsecutiveRuns": model_state.consecutive_runs,
                        "TotalDays": model_state.total_days,
                    }]
                    output_manager.write_regime_promotion_log(promotion_record)
                except Exception:
                    pass
                logger.ok(
                    f"Model promoted: LEARNING->CONVERGED (runs={model_state.consecutive_runs}, days={model_state.total_days:.1f})",
                    component="LIFECYCLE",
                )
            else:
                logger.info(f"Promotion not eligible: {', '.join(unmet)}", component="LIFECYCLE")

    output_manager.write_active_models(
        get_active_model_dict(model_state, regime_version=regime_state_version)
    )
    output_manager.set_maturity_state(str(model_state.maturity.value))
    logger.info(
        f"Model state: {model_state.maturity.value}",
        component="LIFECYCLE",
        version=model_state.version,
        consecutive_runs=model_state.consecutive_runs,
    )
    return model_state


def update_and_persist_model_lifecycle_safe(
    *,
    sql_client: Any,
    output_manager: Any,
    equip_id: int,
    regime_state_version: int,
    cfg: Dict[str, Any],
    train_data: Any,
    run_id: Optional[str],
    regime_model: Optional[Any],
    score_out: Optional[Dict[str, Any]],
    regime_quality_ok: Optional[bool],
    logger: Any = Console,
) -> Optional[ModelState]:
    """
    Safe wrapper around update_and_persist_model_lifecycle.

    Returns None on failure and logs a warning instead of raising.
    """
    try:
        return update_and_persist_model_lifecycle(
            sql_client=sql_client,
            output_manager=output_manager,
            equip_id=equip_id,
            regime_state_version=regime_state_version,
            cfg=cfg,
            train_data=train_data,
            run_id=run_id,
            regime_model=regime_model,
            score_out=score_out,
            regime_quality_ok=regime_quality_ok,
            logger=logger,
        )
    except Exception as e:
        logger.warn(
            f"Failed to update model lifecycle: {e}",
            component="LIFECYCLE",
            error=str(e)[:200],
        )
        return None


def load_model_state_safe(
    sql_client: Any,
    equip_id: int,
    logger: Any = Console,
) -> Optional[ModelState]:
    """
    Safely load model state from SQL.

    Returns None when SQL is unavailable or on load errors.
    """
    if sql_client is None or not equip_id:
        return None
    try:
        return load_model_state_from_sql(sql_client, equip_id)
    except Exception as e:
        logger.warn(
            f"Failed to load model state: {e}",
            component="LIFECYCLE",
            error=str(e)[:200],
        )
        return None


def resolve_maturity_for_regime_stage(
    *,
    sql_client: Any,
    equip_id: int,
    refit_requested: bool,
    logger: Any = Console,
) -> Optional[str]:
    """
    Resolve maturity string used by regime discovery/labeling stage.

    Behavior:
    1. Load current model maturity from SQL.
    2. If refit is requested and maturity is CONVERGED, return LEARNING so
       regime rediscovery can proceed in the same run.
    """
    model_state = load_model_state_safe(sql_client, equip_id, logger=logger)
    if model_state is None:
        return None

    maturity = model_state.maturity.value
    logger.info(f"Model maturity: {maturity}", component="LIFECYCLE")

    if refit_requested and maturity == "CONVERGED":
        logger.info(
            "Refit requested with CONVERGED state - overriding to LEARNING to allow regime rediscovery",
            component="LIFECYCLE",
        )
        return "LEARNING"

    return maturity


def get_active_model_dict(
    state: ModelState,
    regime_version: Optional[int] = None,
    threshold_version: Optional[int] = None,
    forecast_version: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Get dict suitable for write_active_models in output_manager.
    """
    _regime_score_str = (
        f"{state.regime_quality_score:.3f}" if state.regime_quality_score is not None else "N/A"
    )
    Console.info(
        f"Active model v{state.version}: state={state.maturity.value} | "
        f"runs={state.consecutive_runs} | "
        f"regime_metric={state.regime_quality_metric} score={_regime_score_str} "
        f"quality_ok={state.regime_quality_ok} | "
        f"stability={state.stability_ratio} | "
        f"training={state.training_rows} rows / {state.training_days:.1f} days",
        component="LIFECYCLE",
        regime_metric=state.regime_quality_metric,
        regime_score=(
            f"{state.regime_quality_score:.3f}"
            if state.regime_quality_score is not None else "None"
        ),
        regime_quality_ok=state.regime_quality_ok,
        stability=state.stability_ratio,
        training_rows=state.training_rows,
        training_days=f"{state.training_days:.1f}",
        consecutive_runs=state.consecutive_runs,
    )

    effective_regime_version = regime_version or state.version

    return {
        'ActiveRegimeVersion': effective_regime_version,
        'RegimeMaturityState': str(state.maturity),
        'RegimePromotedAt': state.promoted_at,
        'ActiveThresholdVersion': threshold_version or effective_regime_version,
        'ActiveForecastVersion': forecast_version or effective_regime_version,
        'RegimeQualityMetric': state.regime_quality_metric,
        'SilhouetteScore': state.regime_quality_score,
        'StabilityRatio': state.stability_ratio,
        'TrainingRows': state.training_rows,
        'TrainingDays': state.training_days,
        'ConsecutiveRuns': state.consecutive_runs,
        'TotalRuns': state.total_runs,
        'ForecastMAPE': state.forecast_mape,
        'ForecastRMSE': state.forecast_rmse,
        'CreatedAt': state.created_at,
    }


def load_model_state_from_sql(
    sql_client,
    equip_id: int,
) -> Optional[ModelState]:
    """
    Load current model state from ACM_ActiveModels.

    SilhouetteScore stores the raw regime quality score regardless of which
    metric was used (BIC, DBCV, silhouette). RegimeQualityMetric records
    which metric it is so the promotion check can evaluate it correctly.
    """
    try:
        with sql_client.cursor() as cur:
            cur.execute("""
                SELECT
                    ActiveRegimeVersion,
                    RegimeMaturityState,
                    RegimePromotedAt,
                    LastUpdatedAt,
                    LastUpdatedBy,
                    SilhouetteScore,
                    StabilityRatio,
                    TrainingRows,
                    TrainingDays,
                    ConsecutiveRuns,
                    TotalRuns,
                    ForecastMAPE,
                    ForecastRMSE,
                    CreatedAt,
                    ISNULL(RegimeQualityMetric, 'silhouette') AS RegimeQualityMetric
                FROM dbo.[ACM_ActiveModels]
                WHERE EquipID = ?
            """, (equip_id,))
            row = cur.fetchone()

            if row is None:
                return None

            version = row[0] or 1
            maturity_str = row[1] or "LEARNING"

            try:
                maturity = MaturityState(maturity_str)
            except ValueError:
                maturity = MaturityState.LEARNING

            return ModelState(
                equip_id=equip_id,
                version=version,
                maturity=maturity,
                created_at=row[13] or row[3] or datetime.now(),
                promoted_at=row[2],
                regime_quality_score=row[5],
                regime_quality_metric=row[14] or "silhouette",
                stability_ratio=row[6],
                training_rows=row[7] or 0,
                training_days=row[8] or 0.0,
                consecutive_runs=row[9] or 0,
                total_runs=row[10] or 0,
                forecast_mape=row[11],
                forecast_rmse=row[12],
                last_run_id=row[4],
                last_run_at=row[3],
            )
    except Exception as e:
        Console.warn(
            f"Failed to load model state from ACM_ActiveModels: {e}. "
            "Lifecycle will be treated as a fresh start (no prior state).",
            component="LIFECYCLE",
            equip_id=equip_id,
            error=str(e)[:200],
        )
        return None
