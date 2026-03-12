"""
SQL persistence owner for representation-governance control-plane artifacts.

This module builds representation status payloads from the shadow governance
contracts and writes them through OutputManager's contract-driven SQL path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any, Iterable, Optional

import pandas as pd

from core.observability import Console
from core.representation_contracts import RepresentationPipelineResult, StateSnapshot
from core.signal_profiler import profile_signal_frame


@dataclass(frozen=True)
class RepresentationStoreWriteResult:
    representation_status_rows: int = 0
    signal_profile_rows: int = 0
    representation_schema_rows: int = 0
    baseline_governance_rows: int = 0

    @property
    def total_rows(self) -> int:
        return (
            int(self.representation_status_rows)
            + int(self.signal_profile_rows)
            + int(self.representation_schema_rows)
            + int(self.baseline_governance_rows)
        )


def _json_list(values: Iterable[Any]) -> str:
    return json.dumps([str(v) for v in values], ensure_ascii=True)


def _state_ref(result: RepresentationPipelineResult) -> Optional[StateSnapshot]:
    return result.score_state or result.train_state


def build_representation_status_df(result: RepresentationPipelineResult) -> pd.DataFrame:
    state = _state_ref(result)
    if state is None:
        return pd.DataFrame()

    integrity = state.integrity
    payload = {
        "RunID": result.run_id,
        "EquipID": int(result.equip_id),
        "Timestamp": state.batch_end_time,
        "SourceWindowStart": state.source_window_start,
        "SourceWindowEnd": state.source_window_end,
        "WindowLabel": state.window_label,
        "Enabled": bool(result.enabled),
        "Authoritative": bool(result.authoritative),
        "RepresentationVersion": result.refs.representation_version,
        "SchemaVersion": result.refs.schema_version,
        "BasisSignature": result.refs.basis_signature,
        "BaselinePackageVersion": result.refs.baseline_package_version,
        "SignalProfileVersion": result.refs.signal_profile_version,
        "CoverageRatio": float(integrity.coverage_ratio),
        "StaleRatio": float(integrity.stale_ratio),
        "MissingnessGrade": str(integrity.missingness_grade),
        "EffectiveSignalCount": int(integrity.effective_signal_count),
        "ExpectedRows": int(integrity.expected_rows),
        "ObservedRows": int(integrity.observed_rows),
        "DuplicateRowsRemoved": int(integrity.duplicate_rows_removed),
        "FutureRowsDropped": int(integrity.future_rows_dropped),
        "MonitorableSignalCount": int(result.signal_summary.monitorable_signal_count),
        "WeakSignalCount": int(result.signal_summary.weak_signal_count),
        "UntrustedSignalCount": int(result.signal_summary.untrusted_signal_count),
        "SignalSummaryReasonsJson": _json_list(result.signal_summary.reason_codes),
        "ContextID": result.context.context_id,
        "ContextLabel": result.context.context_label,
        "ContextConfidence": float(result.context.context_confidence),
        "ContextStability": result.context.context_stability,
        "TransitionStatus": result.context.transition_status,
        "ContextIsNovel": bool(result.context.is_novel),
        "ContextIsAmbiguous": bool(result.context.is_ambiguous),
        "SchemaCompatibility": result.compatibility.schema_compatibility,
        "BasisCompatibility": result.compatibility.basis_compatibility,
        "BaselineCompatibility": result.compatibility.baseline_compatibility,
        "ScoreAllowed": bool(result.eligibility.score_allowed),
        "LearnAllowed": bool(result.eligibility.learn_allowed),
        "RepresentationConfidence": float(result.grades.representation_confidence),
        "InputIntegrityGrade": result.grades.input_integrity_grade,
        "ContextStabilityGrade": result.grades.context_stability_grade,
        "DegradedReasonsJson": _json_list(result.eligibility.degraded_reason_codes),
        "SuppressedReasonsJson": _json_list(result.eligibility.suppressed_reason_codes),
        "MissingSignalsJson": _json_list(result.compatibility.missing_signals),
        "NewSignalsJson": _json_list(result.compatibility.new_signals),
        "InvalidatedFeaturesJson": _json_list(result.compatibility.invalidated_features),
        "NotesJson": _json_list(result.notes),
    }
    return pd.DataFrame([payload])


def build_signal_profiles_df(
    result: RepresentationPipelineResult,
    signal_source_df: Optional[pd.DataFrame],
) -> pd.DataFrame:
    state = _state_ref(result)
    if state is None or signal_source_df is None or signal_source_df.empty:
        return pd.DataFrame()

    rows = []
    for profile in profile_signal_frame(signal_source_df):
        rows.append(
            {
                "RunID": result.run_id,
                "EquipID": int(result.equip_id),
                "Timestamp": state.batch_end_time,
                "SignalName": profile.signal_name,
                "MissingRatio": float(profile.missing_ratio),
                "FlatlineRatio": float(profile.flatline_ratio),
                "EffectiveCadenceSeconds": profile.effective_cadence_seconds,
                "MonitorabilityClass": profile.monitorability_class,
                "ReasonCodesJson": _json_list(profile.reason_codes),
                "SignalProfileVersion": result.refs.signal_profile_version,
            }
        )
    return pd.DataFrame(rows)


def build_representation_schemas_df(result: RepresentationPipelineResult) -> pd.DataFrame:
    state = _state_ref(result)
    if state is None:
        return pd.DataFrame()

    payload = {
        "RunID": result.run_id,
        "EquipID": int(result.equip_id),
        "Timestamp": state.batch_end_time,
        "RepresentationVersion": result.refs.representation_version,
        "SchemaVersion": result.refs.schema_version,
        "BasisSignature": result.refs.basis_signature,
        "BaselinePackageVersion": result.refs.baseline_package_version,
        "SignalProfileVersion": result.refs.signal_profile_version,
        "SchemaCompatibility": result.compatibility.schema_compatibility,
        "BasisCompatibility": result.compatibility.basis_compatibility,
        "MissingSignalsJson": _json_list(result.compatibility.missing_signals),
        "NewSignalsJson": _json_list(result.compatibility.new_signals),
        "InvalidatedFeaturesJson": _json_list(result.compatibility.invalidated_features),
    }
    return pd.DataFrame([payload])


def build_baseline_governance_df(result: RepresentationPipelineResult) -> pd.DataFrame:
    state = _state_ref(result)
    if state is None:
        return pd.DataFrame()

    payload = {
        "RunID": result.run_id,
        "EquipID": int(result.equip_id),
        "Timestamp": state.batch_end_time,
        "RuntimeMode": result.baseline_governance.runtime_mode.value,
        "ReadinessState": result.baseline_governance.readiness_state,
        "BaselineCandidateState": result.baseline_governance.baseline_candidate_state,
        "ContaminationVerdict": result.baseline_governance.contamination_verdict,
        "FreezeState": result.baseline_governance.freeze_state,
        "ShadowRefreshState": result.baseline_governance.shadow_refresh_state,
        "PromotedPackageVersion": result.baseline_governance.promoted_package_version,
        "ReasonCodesJson": _json_list(result.baseline_governance.reason_codes),
    }
    return pd.DataFrame([payload])


def _write_optional_table(
    output_manager: Any,
    table_name: str,
    artifact_name: str,
    df: pd.DataFrame,
) -> int:
    if df is None or df.empty:
        return 0
    if hasattr(output_manager, "_can_write_dataframe") and not output_manager._can_write_dataframe(df):
        return 0
    result = output_manager.write_sql_table(
        table_name=table_name,
        df=df,
        artifact_name=artifact_name,
        required=False,
    )
    return int(result.get("inserted", 0))


def persist_representation_artifacts(
    output_manager: Any,
    representation_result: RepresentationPipelineResult,
    *,
    signal_source_df: Optional[pd.DataFrame] = None,
    logger: Any = Console,
) -> RepresentationStoreWriteResult:
    if output_manager is None or representation_result is None or not representation_result.enabled:
        return RepresentationStoreWriteResult()

    status_df = build_representation_status_df(representation_result)
    signal_df = build_signal_profiles_df(representation_result, signal_source_df)
    schema_df = build_representation_schemas_df(representation_result)
    baseline_df = build_baseline_governance_df(representation_result)

    result = RepresentationStoreWriteResult(
        representation_status_rows=_write_optional_table(
            output_manager, "ACM_RepresentationStatus", "representation_status", status_df
        ),
        signal_profile_rows=_write_optional_table(
            output_manager, "ACM_SignalProfiles", "signal_profiles", signal_df
        ),
        representation_schema_rows=_write_optional_table(
            output_manager, "ACM_RepresentationSchemas", "representation_schemas", schema_df
        ),
        baseline_governance_rows=_write_optional_table(
            output_manager, "ACM_BaselineGovernance", "baseline_governance", baseline_df
        ),
    )

    log_fn = logger.info if int(result.total_rows) > 0 else logger.warn
    message = (
        "Representation shadow control plane persisted"
        if int(result.total_rows) > 0
        else "Representation shadow control plane produced no SQL rows"
    )
    log_fn(
        message,
        component="REPRESENTATION",
        equip_id=representation_result.equip_id,
        run_id=representation_result.run_id,
        rows_written=int(result.total_rows),
    )
    return result


__all__ = [
    "RepresentationStoreWriteResult",
    "build_baseline_governance_df",
    "build_representation_schemas_df",
    "build_representation_status_df",
    "build_signal_profiles_df",
    "persist_representation_artifacts",
]
