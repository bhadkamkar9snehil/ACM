"""Verdict contract v1 (gem C10, frozen at S1).

FIELDS ARE FROZEN: later phases enrich values, never change the contract.
Every verdict is a falsifiable, evidence-pointed, model-stamped statement.
States escalating and change-not-fault exist in the vocabulary now but are
only produced from S5/S7 onward (trend layer, novelty shape).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

STATE_HEALTHY = "healthy"
STATE_INSUFFICIENT = "insufficient-history"
STATE_WATCH = "watch"
STATE_ALARM = "alarm"
STATE_ESCALATING = "escalating"
STATE_CHANGE = "change-not-fault"

ALL_STATES = (
    STATE_HEALTHY,
    STATE_INSUFFICIENT,
    STATE_WATCH,
    STATE_ALARM,
    STATE_ESCALATING,
    STATE_CHANGE,
)

WATCH_EVIDENCE = 0.5  # fraction of the alarm threshold that opens a watch


@dataclass(frozen=True)
class Verdict:
    asset_key: str
    at: str  # ISO8601 UTC of last scored row
    state: str
    confidence: float  # 0..1
    evidence: float  # max member log-wealth / threshold (0 = none, 1 = alarm)
    evidence_trail: dict = field(default_factory=dict)
    attribution: tuple[str, ...] = ()
    model_epoch: str = ""
    coverage: dict = field(default_factory=dict)
    falsifiable_by: str = ""

    def __post_init__(self) -> None:
        if self.state not in ALL_STATES:
            raise ValueError(f"unknown verdict state {self.state!r}")

    def to_dict(self) -> dict:
        return asdict(self)


def confidence_from(calib_rows: int, evidence: float) -> float:
    """Placeholder confidence (S1): grows with calibration coverage, firms
    with evidence margin distance from the watch boundary. Replaced by
    per-condition coverage at S5+ (Layer 8). Documented, not tuned."""
    coverage_part = min(1.0, calib_rows / 5000.0)
    margin = abs(evidence - WATCH_EVIDENCE) / max(WATCH_EVIDENCE, 1e-9)
    margin_part = min(1.0, margin)
    return round(0.5 * coverage_part + 0.5 * margin_part, 3)
