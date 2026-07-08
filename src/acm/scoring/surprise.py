"""Conditional surprise scorer (S4, gem C1/C2 at Tier 0).

Each channel is predicted FROM THE OTHER CHANNELS (ridge regression on
standardized values, pure numpy); surprise is the reconstruction residual.
This is what the placeholder marginal scorer structurally could not do:
a correlation break leaves every marginal intact but destroys the
cross-channel relationships - here it produces large residuals immediately.

Probabilistic layer: each channel's fit-residual distribution is kept as an
equi-depth grid; PIT (probability integral transform) values of new
residuals against that grid are uniform under health BY CONSTRUCTION.
PIT distortion is therefore a free, continuous self-test (gem C2):
- distortion on many/most channels at once  -> the MODEL is sick
  (miscalibration, bad fit, regime the model never saw);
- distortion local to a few channels        -> the MACHINE is sick there.
That classification is the immune/detection boundary and has its own tests.

Tier 0 by design: linear conditioning is the floor, not the ceiling - the
world model (S7) replaces the regression, not the architecture around it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import polars as pl

from acm.store.raw import TIMESTAMP_COL

RIDGE_LAMBDA = 1e-2  # on standardized channels; structural, not tuned
PIT_GRID_K = 257
KS_DISTORTION_THRESHOLD = 0.1  # KS distance above this = distorted channel
MODEL_SICK_FRACTION = 0.5  # distorted-channel fraction that indicts the model


@dataclass
class ConditionalSurpriseScorer:
    channels: list[str] = field(default_factory=list)
    centers: np.ndarray | None = None
    scales: np.ndarray | None = None
    betas: np.ndarray | None = None  # (d, d) row j: weights over channels, diag 0
    resid_scales: np.ndarray | None = None
    resid_grids: np.ndarray | None = None  # (d, PIT_GRID_K) sorted fit residuals
    _fit_sample: np.ndarray | None = None
    _fit_nn_scale: float = 1.0

    # ------------------------------------------------------------- fit
    def fit(self, frame: pl.DataFrame) -> "ConditionalSurpriseScorer":
        cols, x = self._numeric_matrix(frame)
        keep, centers, scales = [], [], []
        for i, col in enumerate(cols):
            xi = x[:, i]
            xi = xi[np.isfinite(xi)]
            if xi.size < 30:
                continue
            med = float(np.median(xi))
            mad = 1.4826 * float(np.median(np.abs(xi - med)))
            scale = mad if mad > 1e-12 else float(np.std(xi))
            if scale > 1e-12:
                keep.append(i)
                centers.append(med)
                scales.append(scale)
        if len(keep) < 2:
            raise ValueError("conditional scorer needs >= 2 usable channels")
        self.channels = [cols[i] for i in keep]
        self.centers = np.array(centers)
        self.scales = np.array(scales)

        z = self._standardize(x[:, keep])
        # impute at the standardized median, exactly as score() does: a
        # single NaN row otherwise poisons the whole gram matrix -> NaN
        # betas -> every score non-finite -> a permanently dead monitor
        # (found on real CARE data: 3 null rows in 52k killed event 10)
        z = np.nan_to_num(z, nan=0.0)
        n, d = z.shape
        gram = z.T @ z + RIDGE_LAMBDA * n * np.eye(d)
        betas = np.zeros((d, d))
        resid_scales = np.empty(d)
        resid_grids = np.empty((d, PIT_GRID_K))
        for j in range(d):
            idx = [k for k in range(d) if k != j]
            g = gram[np.ix_(idx, idx)]
            b = np.linalg.solve(g, z[:, idx].T @ z[:, j])
            betas[j, idx] = b
            resid = z[:, j] - z[:, idx] @ b
            med = float(np.median(resid))
            mad = 1.4826 * float(np.median(np.abs(resid - med)))
            resid_scales[j] = mad if mad > 1e-12 else max(float(np.std(resid)), 1e-9)
            resid_grids[j] = np.quantile(resid, np.linspace(0, 1, PIT_GRID_K))
        self.betas = betas
        self.resid_scales = resid_scales
        self.resid_grids = resid_grids
        # coverage reference: a subsample of fit rows + their own
        # nearest-neighbor spacing (the yardstick for 'familiar')
        step = max(1, n // 512)
        self._fit_sample = z[::step][:512]
        m = self._fit_sample.shape[0]
        dd = np.sqrt(
            ((self._fit_sample[:, None, :] - self._fit_sample[None, :, :]) ** 2).sum(-1)
        )
        np.fill_diagonal(dd, np.inf)
        self._fit_nn_scale = float(np.median(dd.min(axis=1)))
        return self

    # ----------------------------------------------------------- score
    def _residual_z(self, frame: pl.DataFrame) -> np.ndarray:
        """(n, d) standardized reconstruction residuals."""
        assert self.betas is not None
        z = self._standardize(self._aligned_matrix(frame))
        z = np.nan_to_num(z, nan=0.0)  # imputation at the standardized median
        pred = z @ self.betas.T
        return (z - pred) / self.resid_scales

    def score(self, frame: pl.DataFrame) -> np.ndarray:
        """Per-row surprise: mean |residual z| across channels."""
        return np.mean(np.abs(self._residual_z(frame)), axis=1)

    def pit(self, frame: pl.DataFrame) -> np.ndarray:
        """(n, d) PIT values: uniform under health by construction."""
        assert self.resid_grids is not None
        z = self._standardize(self._aligned_matrix(frame))
        z = np.nan_to_num(z, nan=0.0)
        pred = z @ self.betas.T
        resid = z - pred
        grid_pos = np.linspace(0, 1, PIT_GRID_K)
        pits = np.empty_like(resid)
        for j in range(resid.shape[1]):
            pits[:, j] = np.interp(
                resid[:, j],
                self.resid_grids[j],
                grid_pos,
                left=0.0,
                right=1.0,
            )
        return pits

    def coverage(self, frame: pl.DataFrame) -> float:
        """Operating-point familiarity in [0,1]: how close the frame's
        recent operating points sit to the FIT sample, in units of the fit
        sample's own nearest-neighbor spacing (Layer 8: 'I know high-load
        well; I have seen cold starts twice'). 1 = deeply familiar
        territory; near 0 = a regime the model has barely seen - verdicts
        there carry less confidence REGARDLESS of what the scores say."""
        assert self._fit_sample is not None
        tail = self._standardize(self._aligned_matrix(frame.tail(128)))
        tail = np.nan_to_num(tail)
        # distance of each recent row to its nearest fit-sample row
        d = np.sqrt(
            ((tail[:, None, :] - self._fit_sample[None, :, :]) ** 2).sum(-1)
        ).min(axis=1)
        med_d = float(np.median(d))
        return float(np.exp(-max(0.0, med_d - self._fit_nn_scale)
                            / max(self._fit_nn_scale, 1e-9)))

    def concentration(self, frame: pl.DataFrame, top_k: int = 2) -> float:
        """Share of total surprise carried by the top_k channels (recent
        tail). Near 1 = channel-local (fault-like); low = coordinated
        (operating-change-like). The corroborating axis for step-shaped
        episodes - shape alone cannot separate a constant-severity fault
        from a setpoint change (both plateau; found on the real pilots)."""
        tail_h = min(frame.height, 256)
        rz = np.abs(self._residual_z(frame.tail(tail_h)))
        contrib = np.nanmean(rz, axis=0)
        total = float(contrib.sum())
        d = contrib.size
        if total <= 0 or d <= top_k:
            return 0.0
        raw = float(np.sort(contrib)[::-1][:top_k].sum()) / total
        uniform = top_k / d
        # normalized: 0 = spread evenly over all channels, 1 = all surprise
        # in the top_k. Without this, few-channel assets read concentrated
        # at baseline (top-2 of 3 uniform channels is already 0.67).
        return max(0.0, (raw - uniform) / (1.0 - uniform))

    def attribution(self, frame: pl.DataFrame, top_k: int = 5) -> list[str]:
        tail_h = min(frame.height, 256)
        rz = np.abs(self._residual_z(frame.tail(tail_h)))
        contrib = np.nanmean(rz, axis=0)
        order = np.argsort(contrib)[::-1]
        return [self.channels[i] for i in order[:top_k]]

    # --------------------------------------------------------- helpers
    def _numeric_matrix(self, frame: pl.DataFrame) -> tuple[list[str], np.ndarray]:
        cols = [
            c
            for c, dt in frame.schema.items()
            if c != TIMESTAMP_COL and dt.is_numeric()
        ]
        x = frame.select(cols).to_numpy().astype(np.float64)
        return cols, x

    def _aligned_matrix(self, frame: pl.DataFrame) -> np.ndarray:
        out = np.full((frame.height, len(self.channels)), np.nan)
        for i, col in enumerate(self.channels):
            if col in frame.columns:
                out[:, i] = frame.get_column(col).to_numpy().astype(np.float64)
        return out

    def _standardize(self, x: np.ndarray) -> np.ndarray:
        return (x - self.centers) / self.scales


# ------------------------------------------------------- PIT monitoring
def ks_uniform(pits_1d: np.ndarray) -> float:
    """Kolmogorov-Smirnov distance of a PIT sample from Uniform(0,1)."""
    p = np.sort(pits_1d[np.isfinite(pits_1d)])
    n = p.size
    if n == 0:
        return 1.0
    grid = np.arange(1, n + 1) / n
    return float(np.max(np.abs(p - grid)))


def classify_pit_distortion(
    pits: np.ndarray, channels: list[str]
) -> tuple[str, dict[str, float]]:
    """('ok' | 'channels' | 'model', per-channel KS distances).

    Many channels distorted at once -> the model is sick (miscalibration or
    an unseen regime): an IMMUNE event - drop confidence, trigger rebuild.
    Few channels distorted -> the machine is sick there: a DETECTION event.

    SCOPE (measured on the real pilots): during a genuine severe fault the
    distortion spreads through physically coupled channels and this reads
    'model' too. The classification is therefore an immune signal ONLY
    while the decision layer is NOT alarmed; once the e-process has
    alarmed, distortion is expected and consumers must not treat it as
    model sickness. Enforced at the consumer (immune path), not here.
    """
    ks = {ch: ks_uniform(pits[:, j]) for j, ch in enumerate(channels)}
    distorted = [ch for ch, d in ks.items() if d > KS_DISTORTION_THRESHOLD]
    if not distorted:
        return "ok", ks
    if len(distorted) / len(channels) >= MODEL_SICK_FRACTION:
        return "model", ks
    return "channels", ks
