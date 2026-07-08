"""The world model (S7, gem C1 at Tier 2-S): learned nonlinear dynamics.

Per-channel quantile MLPs predict each channel from the OTHER channels'
CONTEMPORANEOUS and lagged values - the target's own history is
architecturally excluded (a self-conditioned model tracks its own faults),
and contemporaneous others are included (found by spike: lagged-only
inputs gave the model strictly less information than the ridge's
cross-sectional view - the innovations of coupled drivers were invisible). Found by the spike itself: a self-conditioned model TRACKS an
additive fault on its own lags (separation 1.28 vs ridge 2.65 on the
nonlinear fixture) - the exact 'tracking model hides drift' failure C9
exists for. Detection models must never condition a channel on itself. Surprise is the residual from the median head; the q10/q90
heads give calibrated predictive intervals (pinball loss), so PIT comes
from the model itself rather than an empirical residual grid.

Tier placement (D6/D7 honest state): this is the COMPACT world model - the
from-scratch path that D7 guarantees the design never depends on priors
for. Foundation-prior initialization (Chronos-class) remains the upgrade
path when GPU hardware exists; the scorer interface is identical, so the
swap is a drop-in. CPU-trainable by construction (small MLP, bounded
epochs, early stopping): the Tier 2-S reference envelope.

Import-guarded: torch lives in the optional 'tier2' dependency group; the
system is complete at Tier 0 without it, by design.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import polars as pl

from acm.store.raw import TIMESTAMP_COL

LAG = 8
HIDDEN = 128
QUANTILES = (0.1, 0.5, 0.9)
MAX_EPOCHS = 300
PATIENCE = 20
BATCH = 256
PIT_GRID_K = 257


def _torch():
    try:
        import torch

        return torch
    except ImportError as exc:  # pragma: no cover
        raise ValueError(
            "torch is not installed (tier2 group); the world model is a "
            "Tier 2-S capability - Tier 0 uses the conditional scorer"
        ) from exc


@dataclass
class TorchWorldModel:
    channels: list[str] = field(default_factory=list)
    centers: np.ndarray | None = None
    scales: np.ndarray | None = None
    resid_scales: np.ndarray | None = None
    resid_grids: np.ndarray | None = None
    _nets: list = field(default_factory=list)
    _fit_sample: np.ndarray | None = None
    _fit_nn_scale: float = 1.0

    # ------------------------------------------------------------- fit
    def fit(self, frame: pl.DataFrame) -> "TorchWorldModel":
        torch = _torch()
        cols = [
            c
            for c, dt in frame.schema.items()
            if c != TIMESTAMP_COL and dt.is_numeric()
        ]
        x = frame.select(cols).to_numpy().astype(np.float64)
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
            raise ValueError("world model needs >= 2 usable channels")
        self.channels = [cols[i] for i in keep]
        self.centers, self.scales = np.array(centers), np.array(scales)
        z = np.nan_to_num((x[:, keep] - self.centers) / self.scales)
        n, d = z.shape
        if n < 20 * LAG:
            raise ValueError(f"world model needs >= {20 * LAG} rows, got {n}")

        ys = z[LAG:].astype(np.float32)
        split = int(len(ys) * 0.8)
        qs = torch.tensor(QUANTILES, dtype=torch.float32)
        torch.manual_seed(0)

        def pinball(pred, target):
            err = target.unsqueeze(-1) - pred
            return torch.maximum(qs * err, (qs - 1) * err).mean()

        self._nets = []
        val_preds = np.empty((len(ys) - split, d), dtype=np.float64)
        for j in range(d):
            feats = self._features_for(z, j)
            xt = torch.tensor(feats[:split], dtype=torch.float32)
            yt = torch.tensor(ys[:split, j], dtype=torch.float32)
            xv = torch.tensor(feats[split:], dtype=torch.float32)
            yv = torch.tensor(ys[split:, j], dtype=torch.float32)
            net = torch.nn.Sequential(
                torch.nn.Linear(feats.shape[1], HIDDEN),
                torch.nn.GELU(),
                torch.nn.Linear(HIDDEN, len(QUANTILES)),
            )
            opt = torch.optim.Adam(net.parameters(), lr=2e-3)
            best, best_state, patience = float("inf"), None, PATIENCE
            for _epoch in range(MAX_EPOCHS):
                net.train()
                perm = torch.randperm(len(xt))
                for a in range(0, len(xt), BATCH):
                    idx = perm[a : a + BATCH]
                    opt.zero_grad()
                    loss = pinball(net(xt[idx]), yt[idx])
                    loss.backward()
                    opt.step()
                net.eval()
                with torch.no_grad():
                    val = float(pinball(net(xv), yv))
                if val < best - 1e-5:
                    best, patience = val, PATIENCE
                    best_state = {
                        k: v.clone() for k, v in net.state_dict().items()
                    }
                else:
                    patience -= 1
                    if patience <= 0:
                        break
            if best_state is not None:
                net.load_state_dict(best_state)
            net.eval()
            self._nets.append(net)
            with torch.no_grad():
                val_preds[:, j] = net(xv)[:, 1].numpy()

        # residual calibration on the held-out fold (in-sample-bias law)
        resid = ys[split:] - val_preds
        med = np.median(resid, axis=0)
        mad = 1.4826 * np.median(np.abs(resid - med), axis=0)
        self.resid_scales = np.maximum(mad, 1e-9)
        self.resid_grids = np.quantile(
            resid, np.linspace(0, 1, PIT_GRID_K), axis=0
        ).T
        step = max(1, split // 512)
        self._fit_sample = z[LAG:][:split:step][:512]
        dd = np.sqrt(
            ((self._fit_sample[:, None, :] - self._fit_sample[None, :, :]) ** 2).sum(-1)
        )
        np.fill_diagonal(dd, np.inf)
        self._fit_nn_scale = float(np.median(dd.min(axis=1)))
        return self

    @staticmethod
    def _features_for(z: np.ndarray, j: int) -> np.ndarray:
        """Features for target channel j at rows LAG..n-1: OTHER channels
        contemporaneous + at lags 1..LAG. Own history never included."""
        n, d = z.shape
        others = [c for c in range(d) if c != j]
        blocks = [z[LAG:, others]]  # contemporaneous others
        for k in range(1, LAG + 1):
            blocks.append(z[LAG - k : n - k][:, others])
        return np.concatenate(blocks, axis=1).astype(np.float32)

    # ----------------------------------------------------------- score
    def _residual_z(self, frame: pl.DataFrame) -> np.ndarray:
        torch = _torch()
        z = self._z(frame)
        if z.shape[0] <= LAG:
            return np.zeros((0, len(self.channels)))
        ys = z[LAG:]
        d = len(self.channels)
        pred = np.empty((len(ys), d), dtype=np.float64)
        with torch.no_grad():
            for j, net in enumerate(self._nets):
                feats = torch.tensor(
                    self._features_for(z, j), dtype=torch.float32
                )
                pred[:, j] = net(feats)[:, 1].numpy()
        return (ys - pred) / self.resid_scales

    def score(self, frame: pl.DataFrame) -> np.ndarray:
        rz = self._residual_z(frame)
        if rz.shape[0] == 0:
            return np.array([])
        return np.mean(np.abs(rz), axis=1)

    def pit(self, frame: pl.DataFrame) -> np.ndarray:
        rz = self._residual_z(frame) * self.resid_scales  # raw residuals
        grid_pos = np.linspace(0, 1, PIT_GRID_K)
        pits = np.empty_like(rz)
        for j in range(rz.shape[1]):
            pits[:, j] = np.interp(
                rz[:, j], self.resid_grids[j], grid_pos, left=0.0, right=1.0
            )
        return pits

    def attribution(self, frame: pl.DataFrame, top_k: int = 5) -> list[str]:
        rz = np.abs(self._residual_z(frame.tail(min(frame.height, 256 + LAG))))
        if rz.shape[0] == 0:
            return []
        contrib = np.nanmean(rz, axis=0)
        order = np.argsort(contrib)[::-1]
        return [self.channels[i] for i in order[:top_k]]

    def concentration(self, frame: pl.DataFrame, top_k: int = 2) -> float:
        """Share of total surprise carried by the top_k channels -
        IDENTICAL semantics to the conditional scorer's (cross-tier
        contract: verdict words must not depend on the tier). Without
        this, _enrich_alarm's hasattr fallback made change-not-fault
        structurally unreachable at Tier 2 (#92): a coordinated
        setpoint step read as a channel-local fault."""
        rz = np.abs(self._residual_z(frame.tail(min(frame.height, 256 + LAG))))
        if rz.shape[0] == 0:
            return 0.0
        contrib = np.nanmean(rz, axis=0)
        total = float(contrib.sum())
        d = contrib.size
        if total <= 0 or d <= top_k:
            return 0.0
        raw = float(np.sort(contrib)[::-1][:top_k].sum()) / total
        uniform = top_k / d
        return max(0.0, (raw - uniform) / (1.0 - uniform))

    def coverage(self, frame: pl.DataFrame) -> float:
        tail = self._z(frame.tail(128))
        d = np.sqrt(
            ((tail[:, None, :] - self._fit_sample[None, :, :]) ** 2).sum(-1)
        ).min(axis=1)
        med_d = float(np.median(d))
        return float(
            np.exp(
                -max(0.0, med_d - self._fit_nn_scale)
                / max(self._fit_nn_scale, 1e-9)
            )
        )

    def _z(self, frame: pl.DataFrame) -> np.ndarray:
        out = np.full((frame.height, len(self.channels)), np.nan)
        for i, col in enumerate(self.channels):
            if col in frame.columns:
                out[:, i] = frame.get_column(col).to_numpy().astype(np.float64)
        return np.nan_to_num((out - self.centers) / self.scales)
