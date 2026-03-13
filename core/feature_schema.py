"""
Feature-schema ownership for cached-model compatibility and alignment.

This module captures the current manifest/schema comparison rules in one place
without changing runtime authority. It is the precursor owner for later schema
drift governance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from core.observability import Console


FEATURE_SCHEMA_VERSION = "2026.2.shadow-v0"
_ORDER_SENSITIVE_MODELS = {"pca", "iforest", "gmm", "omr", "regime"}
_BASIC_FEATURE_FAMILIES = (
    "_med",
    "_mad",
    "_mean",
    "_std",
    "_slope",
    "_skew",
    "_kurt",
    "_energy_0",
    "_energy_1",
    "_energy_2",
    "_rz",
)


@dataclass(frozen=True)
class FeatureSchema:
    schema_version: str
    feature_columns: Tuple[str, ...]
    source: str = "explicit"
    required_columns: Tuple[str, ...] = field(default_factory=tuple)
    optional_columns: Tuple[str, ...] = field(default_factory=tuple)
    invalidated_columns: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class FeatureSchemaComparison:
    expected_columns: Tuple[str, ...]
    current_columns: Tuple[str, ...]
    common_columns: Tuple[str, ...]
    missing_in_current: Tuple[str, ...]
    extra_in_current: Tuple[str, ...]
    order_matches: bool
    overlap_ratio: float

    @property
    def set_matches(self) -> bool:
        return not self.missing_in_current and not self.extra_in_current

    @property
    def count_matches(self) -> bool:
        return len(self.expected_columns) == len(self.current_columns)


def schema_from_feature_list(
    feature_columns: Sequence[str],
    *,
    schema_version: str = FEATURE_SCHEMA_VERSION,
    source: str = "explicit",
) -> FeatureSchema:
    return FeatureSchema(
        schema_version=schema_version,
        feature_columns=tuple(str(col) for col in feature_columns),
        source=source,
    )


def derive_basic_feature_columns_from_raw_columns(
    raw_columns: Sequence[str],
) -> Tuple[str, ...]:
    """Derive the deterministic ACM basic-feature column order from raw signal columns."""
    normalized = tuple(str(col) for col in raw_columns)
    if not normalized:
        return ()

    derived: list[str] = []
    for family in _BASIC_FEATURE_FAMILIES:
        derived.extend(f"{col}{family}" for col in normalized)
    return tuple(derived)


def schema_from_basic_raw_columns(
    raw_columns: Sequence[str],
    *,
    schema_version: str = FEATURE_SCHEMA_VERSION,
    source: str = "basic_raw_preview",
) -> FeatureSchema:
    return schema_from_feature_list(
        derive_basic_feature_columns_from_raw_columns(raw_columns),
        schema_version=schema_version,
        source=source,
    )


def schema_from_manifest(cached_manifest: Optional[Dict[str, Any]]) -> Optional[FeatureSchema]:
    cached_columns = tuple((cached_manifest or {}).get("train_sensors", []) or ())
    if not cached_columns:
        return None
    return schema_from_feature_list(cached_columns, source="cached_manifest")


def compare_feature_schema(
    current_columns: Sequence[str],
    expected_columns: Sequence[str],
    *,
    order_sensitive: bool = False,
) -> FeatureSchemaComparison:
    current = tuple(str(col) for col in current_columns)
    expected = tuple(str(col) for col in expected_columns)
    current_set = set(current)
    expected_set = set(expected)
    common = tuple(sorted(current_set & expected_set))
    missing = tuple(sorted(expected_set - current_set))
    extra = tuple(sorted(current_set - expected_set))
    overlap_ratio = len(common) / len(current) if current else 0.0
    order_matches = expected == current if order_sensitive else True
    return FeatureSchemaComparison(
        expected_columns=expected,
        current_columns=current,
        common_columns=common,
        missing_in_current=missing,
        extra_in_current=extra,
        order_matches=order_matches,
        overlap_ratio=overlap_ratio,
    )


def align_frames_to_schema(
    train: pd.DataFrame,
    score: pd.DataFrame,
    schema_columns: Sequence[str],
) -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
    aligned_columns = [str(col) for col in schema_columns]
    return train[aligned_columns], score[aligned_columns], aligned_columns


def align_current_features_to_schema(
    train: pd.DataFrame,
    score: pd.DataFrame,
    cached_manifest: Optional[Dict[str, Any]],
    *,
    equip: str = "",
    logger: Any = Console,
) -> Tuple[pd.DataFrame, pd.DataFrame, List[str], bool]:
    """
    Apply the current cached-manifest alignment policy with explicit schema comparison.
    """
    current_sensors = list(train.columns) if hasattr(train, "columns") else []
    schema = schema_from_manifest(cached_manifest)

    if schema is None:
        return train, score, current_sensors, True

    comparison = compare_feature_schema(
        current_sensors,
        schema.feature_columns,
        order_sensitive=False,
    )

    if comparison.set_matches:
        train_aligned, score_aligned, aligned = align_frames_to_schema(
            train,
            score,
            schema.feature_columns,
        )
        return train_aligned, score_aligned, aligned, True

    logger.info(
        f"Aligning features: cached={len(schema.feature_columns)}, current={len(current_sensors)}, "
        f"common={len(comparison.common_columns)}, missing_in_current={len(comparison.missing_in_current)}, "
        f"extra_in_current={len(comparison.extra_in_current)}, overlap={comparison.overlap_ratio:.1%}",
        component="MODEL",
    )

    # Preserve current behavior: any new current feature outside cached schema
    # makes cached models unusable for this batch.
    if comparison.extra_in_current:
        logger.warn(
            f"Current data has {len(comparison.extra_in_current)} features not in cache - cannot use cached models",
            component="MODEL",
            equip=equip,
            extra_features=list(comparison.extra_in_current)[:5],
        )
        return train, score, current_sensors, False

    if comparison.missing_in_current:
        logger.warn(
            f"Using feature subset: {len(comparison.missing_in_current)} cached features missing in current data",
            component="MODEL",
            equip=equip,
            missing_features=list(comparison.missing_in_current)[:5],
        )
        aligned_columns = list(comparison.common_columns)
        train_subset = train[[c for c in aligned_columns if c in train.columns]]
        score_subset = score[[c for c in aligned_columns if c in score.columns]]
        logger.info(
            f"Features aligned to intersection: train={train_subset.shape}, score={score_subset.shape}",
            component="MODEL",
        )
        return train_subset, score_subset, aligned_columns, True

    aligned_columns = list(comparison.common_columns)
    train_subset = train[aligned_columns]
    score_subset = score[aligned_columns]
    return train_subset, score_subset, aligned_columns, True


def validate_cached_model_schema(
    model: Any,
    model_name: str,
    current_columns: Sequence[str],
    cached_manifest: Optional[Dict[str, Any]],
    *,
    equip: str = "",
    logger: Any = Console,
) -> Tuple[bool, Optional[str]]:
    """Validate cached-model compatibility against the extracted feature schema owner."""
    if model is None:
        return False, "Model is None"

    schema = schema_from_manifest(cached_manifest)
    if cached_manifest is None or schema is None:
        if cached_manifest is None:
            logger.warn(
                f"No manifest for {model_name} validation - assuming compatible",
                component="MODEL",
                equip=equip,
                model_name=model_name,
            )
        else:
            logger.warn(
                f"No train_sensors in manifest for {model_name} - assuming compatible",
                component="MODEL",
                equip=equip,
                model_name=model_name,
            )
        return True, None

    comparison = compare_feature_schema(
        current_columns,
        schema.feature_columns,
        order_sensitive=model_name in _ORDER_SENSITIVE_MODELS,
    )

    if not comparison.count_matches:
        return (
            False,
            f"Column count mismatch: cached={len(schema.feature_columns)}, current={len(tuple(current_columns))}",
        )

    if not comparison.set_matches:
        reasons = []
        if comparison.missing_in_current:
            reasons.append(f"missing: {list(comparison.missing_in_current)[:3]}...")
        if comparison.extra_in_current:
            reasons.append(f"new: {list(comparison.extra_in_current)[:3]}...")
        return False, f"Column mismatch - {'; '.join(reasons)}"

    if model_name in _ORDER_SENSITIVE_MODELS and not comparison.order_matches:
        for i, (cached_col, current_col) in enumerate(zip(schema.feature_columns, tuple(current_columns))):
            if cached_col != current_col:
                return False, (
                    f"Column order mismatch at position {i}: "
                    f"cached='{cached_col}', current='{current_col}'"
                )

    return True, None


__all__ = [
    "FEATURE_SCHEMA_VERSION",
    "FeatureSchema",
    "FeatureSchemaComparison",
    "derive_basic_feature_columns_from_raw_columns",
    "align_current_features_to_schema",
    "align_frames_to_schema",
    "compare_feature_schema",
    "schema_from_feature_list",
    "schema_from_basic_raw_columns",
    "schema_from_manifest",
    "validate_cached_model_schema",
]
