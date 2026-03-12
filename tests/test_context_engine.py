from __future__ import annotations

import numpy as np
import pandas as pd

from core.context_engine import (
    apply_transient_state_labels,
    build_context_assignment,
    detect_transient_states,
)


def test_build_context_assignment_defaults_to_unknown_without_frame() -> None:
    context = build_context_assignment(None)

    assert context.context_label == "UNKNOWN"
    assert context.context_confidence == 0.0
    assert context.is_ambiguous is True


def test_build_context_assignment_uses_latest_frame_row() -> None:
    frame = pd.DataFrame(
        {
            "regime_label": [0, 2],
            "regime_confidence": [0.9, 0.4],
            "regime_is_novel": [False, True],
            "transient_state": ["steady", "transient"],
        }
    )

    context = build_context_assignment(frame)

    assert context.context_id == "regime:2"
    assert context.context_label == "REGIME_2"
    assert context.context_confidence == 0.4
    assert context.transition_status == "TRANSIENT"
    assert context.context_stability == "TRANSIENT"
    assert context.is_novel is True
    assert context.is_ambiguous is True


def test_detect_transient_states_handles_generic_numeric_columns_directly() -> None:
    idx = pd.date_range("2026-01-01", periods=5, freq="h")
    data = pd.DataFrame(
        {
            "sensor_1_avg": [1.0, 1.2, 1.8, 2.6, 2.7],
            "sensor_2_avg": [5.0, 5.1, 5.0, 5.4, 5.5],
        },
        index=idx,
    )
    regime_labels = np.array([0, 0, 0, 1, 1])

    states = detect_transient_states(data=data, regime_labels=regime_labels, cfg={})

    assert len(states) == len(data)
    assert set(states.tolist()) <= {"steady", "transient", "trip"}


def test_apply_transient_state_labels_noops_without_regime_label() -> None:
    frame = pd.DataFrame({"fused": [0.1, 0.2, 0.3]})
    score_data = pd.DataFrame({"sensor": [1.0, 2.0, 3.0]})

    out_frame, counts = apply_transient_state_labels(frame=frame, score_data=score_data, cfg={})

    assert out_frame.equals(frame)
    assert counts == {}
