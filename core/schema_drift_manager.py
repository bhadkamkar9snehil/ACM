"""
Schema-drift ownership for shadow representation governance.

This module makes feature-schema and regime-basis compatibility explicit while
preserving the current runtime alignment and refit behavior until cutover.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

import pandas as pd

from core.feature_schema import compare_feature_schema, schema_from_manifest
from core.representation_contracts import CompatibilityStatus


@dataclass(frozen=True)
class SchemaDriftDecision:
    schema_compatibility: str = "PENDING"
    basis_compatibility: str = "PENDING"
    cache_compatible: bool = True
    should_refit: bool = False
    use_intersection: bool = False
    aligned_columns: Tuple[str, ...] = ()
    missing_signals: Tuple[str, ...] = ()
    new_signals: Tuple[str, ...] = ()
    invalidated_features: Tuple[str, ...] = ()
    reason_codes: Tuple[str, ...] = ()
    operator_summary: str = ""


def classify_feature_schema_drift(
    current_columns: Sequence[str],
    cached_manifest: Optional[Dict[str, Any]],
    *,
    persistent_missing_signals: Optional[Sequence[str]] = None,
) -> SchemaDriftDecision:
    current = tuple(str(col) for col in current_columns)
    schema = schema_from_manifest(cached_manifest)

    if cached_manifest is None or schema is None:
        return SchemaDriftDecision(
            schema_compatibility="UNASSESSED",
            cache_compatible=True,
            aligned_columns=current,
            reason_codes=("no_cached_manifest",),
            operator_summary="No cached manifest available for schema comparison.",
        )

    comparison = compare_feature_schema(current, schema.feature_columns, order_sensitive=False)
    missing = comparison.missing_in_current
    extra = comparison.extra_in_current
    common = comparison.common_columns
    persistent_missing = {str(sig) for sig in persistent_missing_signals or ()}

    if comparison.set_matches:
        return SchemaDriftDecision(
            schema_compatibility="COMPATIBLE",
            cache_compatible=True,
            aligned_columns=schema.feature_columns,
            reason_codes=("schema_match",),
            operator_summary="Cached manifest matches current feature schema.",
        )

    if missing and extra:
        return SchemaDriftDecision(
            schema_compatibility="REPRESENTATION_BREAK",
            cache_compatible=False,
            should_refit=True,
            aligned_columns=current,
            missing_signals=missing,
            new_signals=extra,
            invalidated_features=missing,
            reason_codes=("missing_cached_features", "new_features_detected", "representation_break"),
            operator_summary=(
                f"Current schema has {len(missing)} missing cached features and "
                f"{len(extra)} new features."
            ),
        )

    if extra:
        return SchemaDriftDecision(
            schema_compatibility="ADDITIVE_GROWTH",
            cache_compatible=False,
            should_refit=True,
            aligned_columns=current,
            new_signals=extra,
            reason_codes=("new_features_detected",),
            operator_summary=f"Current schema has {len(extra)} new feature(s) outside the cached manifest.",
        )

    if missing and not common:
        return SchemaDriftDecision(
            schema_compatibility="SCHEMA_BREAK",
            cache_compatible=False,
            should_refit=True,
            aligned_columns=current,
            missing_signals=missing,
            invalidated_features=missing,
            reason_codes=("all_cached_features_missing", "schema_break"),
            operator_summary="No overlap remains between cached and current features.",
        )

    if missing:
        loss_is_persistent = bool(missing) and set(missing).issubset(persistent_missing) and persistent_missing
        compatibility = "PERMANENT_TAG_LOSS" if loss_is_persistent else "TEMPORARY_TAG_LOSS"
        cache_compatible = not loss_is_persistent
        return SchemaDriftDecision(
            schema_compatibility=compatibility,
            cache_compatible=cache_compatible,
            should_refit=not cache_compatible,
            use_intersection=cache_compatible,
            aligned_columns=tuple(common) if cache_compatible else current,
            missing_signals=missing,
            invalidated_features=missing,
            reason_codes=("missing_cached_features", compatibility.lower()),
            operator_summary=f"Cached schema is missing {len(missing)} feature(s) in current data.",
        )

    return SchemaDriftDecision(
        schema_compatibility="UNASSESSED",
        cache_compatible=True,
        aligned_columns=current,
        reason_codes=("schema_unassessed",),
        operator_summary="Schema drift could not be classified.",
    )


def apply_feature_schema_alignment(
    train: pd.DataFrame,
    score: pd.DataFrame,
    decision: SchemaDriftDecision,
) -> Tuple[pd.DataFrame, pd.DataFrame, list[str], bool]:
    current_sensors = list(train.columns) if hasattr(train, "columns") else []

    if decision.schema_compatibility == "COMPATIBLE" and decision.aligned_columns:
        aligned_columns = [str(col) for col in decision.aligned_columns]
        return train[aligned_columns], score[aligned_columns], aligned_columns, True

    if decision.use_intersection and decision.aligned_columns:
        aligned_columns = [str(col) for col in decision.aligned_columns]
        train_subset = train[[col for col in aligned_columns if col in train.columns]]
        score_subset = score[[col for col in aligned_columns if col in score.columns]]
        return train_subset, score_subset, aligned_columns, bool(decision.cache_compatible)

    return train, score, current_sensors, bool(decision.cache_compatible)


def validate_cached_model_schema_drift(
    model: Any,
    model_name: str,
    current_columns: Sequence[str],
    cached_manifest: Optional[Dict[str, Any]],
) -> Tuple[bool, Optional[str], SchemaDriftDecision]:
    current = tuple(str(col) for col in current_columns)
    schema = schema_from_manifest(cached_manifest)

    if model is None:
        return False, "Model is None", SchemaDriftDecision(
            schema_compatibility="UNASSESSED",
            cache_compatible=False,
            should_refit=True,
            aligned_columns=current,
            reason_codes=("model_missing",),
            operator_summary="Cached model is missing.",
        )

    if cached_manifest is None or schema is None:
        return True, None, SchemaDriftDecision(
            schema_compatibility="UNASSESSED",
            cache_compatible=True,
            aligned_columns=current,
            reason_codes=("no_cached_manifest",),
            operator_summary="No cached manifest available for model schema validation.",
        )

    order_sensitive = model_name in {"pca", "iforest", "gmm", "omr", "regime"}
    comparison = compare_feature_schema(current, schema.feature_columns, order_sensitive=order_sensitive)
    decision = classify_feature_schema_drift(current, cached_manifest)

    if not comparison.count_matches:
        reason = (
            f"Column count mismatch: cached={len(schema.feature_columns)}, "
            f"current={len(current)}"
        )
        return False, reason, SchemaDriftDecision(
            schema_compatibility="SCHEMA_BREAK",
            cache_compatible=False,
            should_refit=True,
            aligned_columns=current,
            missing_signals=decision.missing_signals,
            new_signals=decision.new_signals,
            invalidated_features=decision.invalidated_features,
            reason_codes=("column_count_mismatch",),
            operator_summary=reason,
        )

    if not comparison.set_matches:
        reasons = []
        if comparison.missing_in_current:
            reasons.append(f"missing: {list(comparison.missing_in_current)[:3]}...")
        if comparison.extra_in_current:
            reasons.append(f"new: {list(comparison.extra_in_current)[:3]}...")
        return False, f"Column mismatch - {'; '.join(reasons)}", decision

    if order_sensitive and not comparison.order_matches:
        for i, (cached_col, current_col) in enumerate(zip(schema.feature_columns, current)):
            if cached_col != current_col:
                reason = (
                    f"Column order mismatch at position {i}: "
                    f"cached='{cached_col}', current='{current_col}'"
                )
                return False, reason, SchemaDriftDecision(
                    schema_compatibility="ORDER_MISMATCH",
                    cache_compatible=False,
                    should_refit=True,
                    aligned_columns=current,
                    reason_codes=("column_order_mismatch",),
                    operator_summary=reason,
                )

    return True, None, decision


def classify_regime_basis_drift(
    *,
    regime_model: Any,
    regime_basis_train: Optional[pd.DataFrame],
    cached_model_version: Optional[Any],
    current_model_version: Any,
    cached_basis_signature: Optional[str] = None,
    current_basis_signature: Optional[str] = None,
) -> SchemaDriftDecision:
    if regime_basis_train is None:
        return SchemaDriftDecision(
            basis_compatibility="BASIS_UNAVAILABLE",
            cache_compatible=False,
            should_refit=True,
            reason_codes=("basis_unavailable",),
            operator_summary="Regime basis could not be built for this batch.",
        )

    if regime_model is None:
        return SchemaDriftDecision(
            basis_compatibility="UNASSESSED",
            cache_compatible=True,
            reason_codes=("no_cached_regime_model",),
            operator_summary="No cached regime model available for basis comparison.",
        )

    reason_codes = []
    incompatible = False
    if getattr(regime_model, "feature_columns", []) != list(regime_basis_train.columns):
        incompatible = True
        reason_codes.append("basis_column_mismatch")
    if cached_model_version is not None and cached_model_version != current_model_version:
        incompatible = True
        reason_codes.append("basis_version_mismatch")
    if (
        cached_basis_signature
        and current_basis_signature
        and str(cached_basis_signature) != str(current_basis_signature)
    ):
        incompatible = True
        reason_codes.append("basis_signature_mismatch")

    if incompatible:
        return SchemaDriftDecision(
            basis_compatibility="INCOMPATIBLE",
            cache_compatible=False,
            should_refit=True,
            aligned_columns=tuple(str(col) for col in regime_basis_train.columns),
            reason_codes=tuple(reason_codes),
            operator_summary="Cached regime model is incompatible with the active basis contract.",
        )

    return SchemaDriftDecision(
        basis_compatibility="COMPATIBLE",
        cache_compatible=True,
        aligned_columns=tuple(str(col) for col in regime_basis_train.columns),
        reason_codes=("basis_match",),
        operator_summary="Cached regime basis matches the active basis contract.",
    )


def compatibility_status_from_drift(
    *,
    feature_schema_drift: Optional[SchemaDriftDecision] = None,
    basis_drift: Optional[SchemaDriftDecision] = None,
    baseline_compatibility: str = "PENDING",
) -> CompatibilityStatus:
    missing_signals = tuple(feature_schema_drift.missing_signals if feature_schema_drift else ())
    new_signals = tuple(feature_schema_drift.new_signals if feature_schema_drift else ())
    invalidated_features = tuple(feature_schema_drift.invalidated_features if feature_schema_drift else ())

    return CompatibilityStatus(
        schema_compatibility=(
            feature_schema_drift.schema_compatibility if feature_schema_drift else "PENDING"
        ),
        basis_compatibility=(
            basis_drift.basis_compatibility if basis_drift else "PENDING"
        ),
        baseline_compatibility=str(baseline_compatibility or "PENDING").strip().upper(),
        missing_signals=missing_signals,
        new_signals=new_signals,
        invalidated_features=invalidated_features,
    )


__all__ = [
    "SchemaDriftDecision",
    "apply_feature_schema_alignment",
    "classify_feature_schema_drift",
    "classify_regime_basis_drift",
    "compatibility_status_from_drift",
    "validate_cached_model_schema_drift",
]
