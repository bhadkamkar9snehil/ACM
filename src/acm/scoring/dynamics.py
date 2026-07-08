"""Dynamics-drift channel (gem C5 slow channel, Koopman-flavored, Tier 0).

Watch the MODEL, not just the residuals: periodically re-identify the
asset's one-step linear dynamics operator (DMD-style least squares,
z_{t+1} ~ A z_t on standardized channels) and measure how far the freshly
identified operator has moved from the healthy reference operator. A
degrading machine's governing equations change slowly; operator drift is
degradation made directly visible, often before residual magnitude
accumulates anything.

Drift metric: relative Frobenius distance ||A_w - A_ref||_F / ||A_ref||_F
per identification window - deliberately NOT eigenvalue matching (pairing
eigenvalues across refits is fragile; the operator distance bounds the
spectral movement and needs no pairing). Calibration: the drift of healthy
windows against the same reference - the e-process consumes it like any
other stream. Research-grade honesty: this is the spike implementation
(go/no-go evidence in tests); never a dependency of the other channels.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import polars as pl

from acm.store.raw import TIMESTAMP_COL

DMD_RIDGE = 1e-3
IDENT_WINDOW = 512  # rows per operator identification
MIN_WINDOWS = 6  # calibration windows needed to arm the stream


def _ident(z: np.ndarray) -> np.ndarray:
    """One-step operator A minimizing ||z_{t+1} - A z_t||, ridge-stabilized."""
    past, future = z[:-1], z[1:]
    d = z.shape[1]
    gram = past.T @ past + DMD_RIDGE * len(past) * np.eye(d)
    return np.linalg.solve(gram, past.T @ future).T  # (d, d)


@dataclass
class DynamicsDrift:
    channels: list[str] = field(default_factory=list)
    centers: np.ndarray | None = None
    scales: np.ndarray | None = None
    a_ref: np.ndarray | None = None
    _ref_norm: float = 1.0

    def fit(self, calib_frame: pl.DataFrame) -> "DynamicsDrift":
        cols = [
            c
            for c, dt in calib_frame.schema.items()
            if c != TIMESTAMP_COL and dt.is_numeric()
        ]
        x = calib_frame.select(cols).to_numpy().astype(np.float64)
        keep, centers, scales = [], [], []
        for i in range(x.shape[1]):
            xi = x[:, i][np.isfinite(x[:, i])]
            if xi.size < 30:
                continue
            med = float(np.median(xi))
            mad = 1.4826 * float(np.median(np.abs(xi - med)))
            s = mad if mad > 1e-12 else float(np.std(xi))
            if s > 1e-12:
                keep.append(i)
                centers.append(med)
                scales.append(s)
        if len(keep) < 2:
            raise ValueError("dynamics drift needs >= 2 usable channels")
        self.channels = [cols[i] for i in keep]
        self.centers, self.scales = np.array(centers), np.array(scales)
        z = np.nan_to_num((x[:, keep] - self.centers) / self.scales)
        if z.shape[0] < (MIN_WINDOWS + 1) * IDENT_WINDOW:
            raise ValueError(
                f"dynamics drift needs >= {(MIN_WINDOWS + 1) * IDENT_WINDOW} "
                f"calibration rows, got {z.shape[0]}"
            )
        self.a_ref = _ident(z)
        self._ref_norm = max(float(np.linalg.norm(self.a_ref)), 1e-9)
        return self

    def _z(self, frame: pl.DataFrame) -> np.ndarray:
        out = np.full((frame.height, len(self.channels)), np.nan)
        for i, col in enumerate(self.channels):
            if col in frame.columns:
                out[:, i] = frame.get_column(col).to_numpy().astype(np.float64)
        return np.nan_to_num((out - self.centers) / self.scales)

    def drift_stream(self, frame: pl.DataFrame) -> np.ndarray:
        """Drift values over OVERLAPPING identification windows (stride =
        window/8). Overlap induces serial dependence in the stream - which
        is exactly what the e-process's derived block sizes exist to absorb
        (D12 machinery); it buys enough calibration values from realistic
        holdout sizes without weakening the identification window."""
        z = self._z(frame)
        stride = IDENT_WINDOW // 8
        out = []
        for a in range(0, z.shape[0] - IDENT_WINDOW + 1, stride):
            a_w = _ident(z[a : a + IDENT_WINDOW])
            out.append(
                float(np.linalg.norm(a_w - self.a_ref)) / self._ref_norm
            )
        return np.array(out)

    def calibration_stream(self, calib_frame: pl.DataFrame) -> np.ndarray:
        """Healthy windows' drift against the same reference - the
        e-process calibration for this stream."""
        return self.drift_stream(calib_frame)
