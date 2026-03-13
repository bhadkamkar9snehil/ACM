from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple


REPRESENTATION_VERSION = "2026.2.0-draft"
SIGNAL_PROFILE_VERSION = "shadow-v0"


class RuntimeMode(str, Enum):
    BOOTSTRAP_NOT_READY = "BOOTSTRAP_NOT_READY"
    BASELINE_FORMATION = "BASELINE_FORMATION"
    ONLINE_SCORING = "ONLINE_SCORING"
    CONTROLLED_ADAPTATION = "CONTROLLED_ADAPTATION"
    SCHEMA_BREAK_REQUALIFICATION = "SCHEMA_BREAK_REQUALIFICATION"


@dataclass(frozen=True)
class ObservationIntegrity:
    coverage_ratio: float
    stale_ratio: float
    missingness_grade: str
    effective_signal_count: int
    expected_rows: int
    observed_rows: int
    duplicate_rows_removed: int = 0
    future_rows_dropped: int = 0


@dataclass(frozen=True)
class SignalProfile:
    signal_name: str
    missing_ratio: float
    flatline_ratio: float
    effective_cadence_seconds: Optional[float]
    monitorability_class: str
    reason_codes: Tuple[str, ...] = ()


@dataclass(frozen=True)
class SignalProfileSummary:
    monitorable_signal_count: int
    weak_signal_count: int = 0
    untrusted_signal_count: int = 0
    reason_codes: Tuple[str, ...] = ()


@dataclass(frozen=True)
class StateSnapshot:
    asset_id: int
    batch_end_time: Optional[datetime]
    run_id: str
    source_window_start: Optional[datetime]
    source_window_end: Optional[datetime]
    window_label: str
    integrity: ObservationIntegrity


@dataclass(frozen=True)
class ContextAssignment:
    context_id: str = "unknown"
    context_label: str = "UNKNOWN"
    context_confidence: float = 0.0
    context_stability: str = "UNASSESSED"
    transition_status: str = "UNASSESSED"
    is_novel: bool = False
    is_ambiguous: bool = True


@dataclass(frozen=True)
class CompatibilityStatus:
    schema_compatibility: str = "PENDING"
    basis_compatibility: str = "PENDING"
    baseline_compatibility: str = "PENDING"
    missing_signals: Tuple[str, ...] = ()
    new_signals: Tuple[str, ...] = ()
    invalidated_features: Tuple[str, ...] = ()


@dataclass(frozen=True)
class EligibilityDecision:
    authoritative: bool = False
    score_allowed: Optional[bool] = None
    learn_allowed: Optional[bool] = None
    degraded_reason_codes: Tuple[str, ...] = ()
    suppressed_reason_codes: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RepresentationAuthorityPolicy:
    mode: str = "shadow"
    active: bool = False
    reason: str = "shadow_default"
    historical_replay: bool = False


@dataclass(frozen=True)
class BaselineGovernanceDecision:
    runtime_mode: RuntimeMode
    enough_history_to_proceed: bool
    baseline_ready: bool
    readiness_state: str
    baseline_candidate_state: str
    contamination_verdict: str
    freeze_state: str
    shadow_refresh_state: str
    promoted_package_version: Optional[str] = None
    reason_codes: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RepresentationRefs:
    representation_version: str = REPRESENTATION_VERSION
    schema_version: str = "unbound"
    basis_signature: str = "pending"
    baseline_package_version: str = "pending"
    signal_profile_version: str = SIGNAL_PROFILE_VERSION


@dataclass(frozen=True)
class OperationalGrades:
    representation_confidence: float = 0.0
    input_integrity_grade: str = "UNASSESSED"
    context_stability_grade: str = "UNASSESSED"


@dataclass(frozen=True)
class RepresentationPipelineResult:
    enabled: bool
    authoritative: bool
    run_id: str
    equip_id: int
    train_state: Optional[StateSnapshot]
    score_state: Optional[StateSnapshot]
    signal_profiles: Tuple[SignalProfile, ...]
    signal_summary: SignalProfileSummary
    context: ContextAssignment
    compatibility: CompatibilityStatus
    eligibility: EligibilityDecision
    baseline_governance: BaselineGovernanceDecision
    refs: RepresentationRefs
    grades: OperationalGrades
    notes: Tuple[str, ...] = field(default_factory=tuple)

    def score_state_rows(self) -> int:
        if self.score_state is None:
            return 0
        return int(self.score_state.integrity.observed_rows)
