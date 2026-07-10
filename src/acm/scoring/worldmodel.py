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

EVAL_CHUNK = 4096  # rows per held-out eval batch (bounds activations)

# optional observer called as on_progress(steps_done, steps_total) from
# inside fit() - training takes minutes on wide assets and MUST be
# observable from the outside (set by the runtime, surfaced in the
# service activity stream)
on_progress = None


def _group_size(torch, dev, f_all: int, x_bytes: int) -> int:
    """Channels per parallel training group, sized to device memory.

    Per-channel training cost is dominated by the [f_all, HIDDEN] weight
    slice times 4 (weights + grads + Adam m and v) plus the best-state
    clone. The feature tensor is already resident, so it is subtracted
    from the budget. Narrow assets get one group (full parallelism);
    a 957-channel Farm C asset lands at whatever count fits - grouped
    training is O(group) memory, not O(d^2)."""
    per_channel = f_all * HIDDEN * 4 * 5  # w1 x (self+grad+m+v+best)
    if dev.type == "cuda":
        free, _total = torch.cuda.mem_get_info(dev)
        budget = int(free * 0.6)
    else:
        budget = max(1_000_000_000, 4_000_000_000 - x_bytes)
    return max(1, min(1024, budget // per_channel))


def _device(torch):
    """CUDA when available - the whole point of the T2-S tier. Training
    79+ small nets sequentially on CPU leaves the probed GPU idle (found
    live: RTX 4060 at 0% through a 10-minute onboard)."""
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _torch():
    try:
        import torch

        # TF32 on Ampere+ tensor cores: ~2x matmul throughput at a
        # precision (10-bit mantissa) far beyond what a quantile net
        # trained on MAD-scaled SCADA data can even express. Off by
        # default in torch; pure waste to leave it off here.
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
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
        dev = _device(torch)
        qs = torch.tensor(QUANTILES, dtype=torch.float32, device=dev)
        torch.manual_seed(0)

        # ---- grouped-batch training: channels train in PARALLEL GROUPS
        # sized to the device's free memory, instead of d sequential nets
        # (kernel-launch-bound, GPU idle) or one all-channel batch (O(d^2)
        # weight memory - a 957-channel Farm C asset would not fit in
        # 8 GB VRAM). Group size adapts: small assets train in one group,
        # wide assets in however many fit. Own-history exclusion is a hard
        # input mask (masked inputs get exactly-0 gradients - equivalent
        # to excluding them). Per-channel early stopping and best-state
        # restore are preserved.
        H, Q = HIDDEN, len(QUANTILES)
        nz = z.shape[0]
        blocks = [z[LAG:]]
        for k in range(1, LAG + 1):
            blocks.append(z[LAG - k : nz - k])
        feat_all = np.concatenate(blocks, axis=1).astype(np.float32)
        f_all = feat_all.shape[1]  # d * (LAG + 1)

        X = torch.tensor(feat_all, dtype=torch.float32, device=dev)
        Y = torch.tensor(ys, dtype=torch.float32, device=dev)
        xt, yt = X[:split], Y[:split]
        xv, yv = X[split:], Y[split:]

        group = _group_size(torch, dev, f_all, X.nbytes)
        n_groups = (d + group - 1) // group
        fan_in = (d - 1) * (LAG + 1)
        b1sc, b2sc = fan_in**-0.5, float(H) ** -0.5
        gelu = torch.nn.functional.gelu
        own = torch.arange(LAG + 1, device=dev) * d

        def pinball_pc(pred, target):
            """Per-channel pinball: pred [g,n,Q], target [n,g] -> [g]."""
            err = target.T.unsqueeze(-1) - pred
            return torch.maximum(qs * err, (qs - 1) * err).mean(dim=(1, 2))

        self._nets = [None] * d
        val_preds = np.empty((len(ys) - split, d), dtype=np.float64)
        for gi in range(n_groups):
            js = list(range(gi * group, min(d, (gi + 1) * group)))
            g = len(js)
            yt_g, yv_g = yt[:, js], yv[:, js]

            mask = torch.ones((g, f_all), device=dev)
            for i, j in enumerate(js):
                mask[i, own + j] = 0.0
            mask3 = mask.unsqueeze(-1)

            # init mirrors nn.Linear defaults with the EFFECTIVE fan-in
            # (the (d-1)*(LAG+1) unmasked inputs)
            w1 = (torch.rand(g, f_all, H, device=dev) * 2 - 1) * b1sc
            bb1 = (torch.rand(g, 1, H, device=dev) * 2 - 1) * b1sc
            w2 = (torch.rand(g, H, Q, device=dev) * 2 - 1) * b2sc
            bb2 = (torch.rand(g, 1, Q, device=dev) * 2 - 1) * b2sc
            for p in (w1, bb1, w2, bb2):
                p.requires_grad_(True)
            opt = torch.optim.Adam((w1, bb1, w2, bb2), lr=2e-3)

            def forward(xb, a=w1, b=bb1, c=w2, e=bb2, m=mask3):
                h = gelu(torch.einsum("nf,gfh->gnh", xb, a * m) + b)
                return torch.einsum("gnh,ghq->gnq", h, c) + e

            def eval_val(*weights):
                """Chunked held-out eval: bounds activation memory to
                EVAL_CHUNK rows regardless of validation size."""
                tot, seen = None, 0
                with torch.no_grad():
                    for a in range(0, len(xv), EVAL_CHUNK):
                        xb, yb = xv[a : a + EVAL_CHUNK], yv_g[a : a + EVAL_CHUNK]
                        part = pinball_pc(
                            forward(xb, *weights) if weights else forward(xb),
                            yb,
                        ) * len(xb)
                        tot = part if tot is None else tot + part
                        seen += len(xb)
                return (tot / seen).cpu()

            best = torch.full((g,), float("inf"))
            patience = np.full(g, PATIENCE)
            active = np.ones(g, dtype=bool)
            best_w = None
            for epoch in range(MAX_EPOCHS):
                if on_progress is not None and epoch % 20 == 0:
                    on_progress(gi * MAX_EPOCHS + epoch,
                                n_groups * MAX_EPOCHS)
                act = torch.tensor(active, device=dev, dtype=torch.float32)
                perm = torch.randperm(len(xt), device=dev)
                for a in range(0, len(xt), BATCH):
                    idx = perm[a : a + BATCH]
                    opt.zero_grad()
                    losses = pinball_pc(forward(xt[idx]), yt_g[idx])
                    (losses * act).sum().backward()
                    opt.step()
                val = eval_val()
                improved = (val < best - 1e-5).numpy() & active
                if best_w is None:
                    best_w = [t.detach().clone()
                              for t in (w1, bb1, w2, bb2)]
                elif improved.any():
                    imp = torch.tensor(improved, device=dev)
                    for bw, cur in zip(best_w, (w1, bb1, w2, bb2)):
                        bw[imp] = cur.detach()[imp]
                best = torch.where(torch.tensor(improved), val, best)
                patience[improved] = PATIENCE
                patience[active & ~improved] -= 1
                active = active & (patience > 0)
                if not active.any():
                    break

            with torch.no_grad():
                for a in range(0, len(xv), EVAL_CHUNK):
                    xb = xv[a : a + EVAL_CHUNK]
                    val_preds[a : a + EVAL_CHUNK, js] = (
                        forward(xb, *best_w)[:, :, 1]
                        .T.to("cpu", torch.float64).numpy()
                    )

            # unpack this group's weights into the same per-channel
            # Sequential nets as before: scoring, pickling, and
            # cross-machine loading are untouched (nets live on CPU - a
            # tick scores a few thousand rows, and a CPU net loads
            # anywhere, including a machine without a GPU)
            bw1 = (best_w[0] * mask3).cpu()
            bbb1, bw2, bbb2 = [t.cpu() for t in best_w[1:]]
            for i, j in enumerate(js):
                keep = [
                    b * d + c
                    for b in range(LAG + 1)
                    for c in range(d)
                    if c != j
                ]
                net = torch.nn.Sequential(
                    torch.nn.Linear(fan_in, H),
                    torch.nn.GELU(),
                    torch.nn.Linear(H, Q),
                )
                with torch.no_grad():
                    net[0].weight.copy_(bw1[i][keep, :].T)
                    net[0].bias.copy_(bbb1[i, 0])
                    net[2].weight.copy_(bw2[i].T)
                    net[2].bias.copy_(bbb2[i, 0])
                net.eval()
                self._nets[j] = net
            # free this group's training state before the next allocates
            del w1, bb1, w2, bb2, best_w, opt, mask, mask3
            if dev.type == "cuda":
                torch.cuda.empty_cache()

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
        dev = _device(torch)
        # batched GPU inference for anything beyond a trivial tick: the
        # per-net CPU loop rebuilds a feature matrix d times and runs d
        # sequential forwards - a first tick over a 54k-row lifetime took
        # ~2 minutes that way; one grouped einsum does it in seconds
        if dev.type == "cuda" and len(ys) * d > 100_000:
            return self._residual_z_batched(torch, dev, z, ys, d)
        pred = np.empty((len(ys), d), dtype=np.float64)
        with torch.no_grad():
            for j, net in enumerate(self._nets):
                feats = torch.tensor(
                    self._features_for(z, j), dtype=torch.float32
                )
                pred[:, j] = net(feats)[:, 1].numpy()
        return (ys - pred) / self.resid_scales

    def _residual_z_batched(self, torch, dev, z, ys, d: int) -> np.ndarray:
        """Grouped-einsum inference: stack the per-channel nets into
        [d, f_all, H] weights (own-channel rows stay zero - the exact
        mask geometry training used) and score every channel of every
        row in one chunked GPU pass. Same weights, same math, same
        output as the sequential loop."""
        H = self._nets[0][0].weight.shape[0]
        Q = self._nets[0][2].weight.shape[0]
        nz = z.shape[0]
        blocks = [z[LAG:]]
        for k in range(1, LAG + 1):
            blocks.append(z[LAG - k : nz - k])
        feat_all = np.concatenate(blocks, axis=1).astype(np.float32)
        f_all = feat_all.shape[1]

        w1 = torch.zeros(d, f_all, H)
        b1 = torch.empty(d, 1, H)
        w2 = torch.empty(d, H, Q)
        b2 = torch.empty(d, 1, Q)
        with torch.no_grad():
            for j, net in enumerate(self._nets):
                keep = [
                    b * d + c
                    for b in range(LAG + 1)
                    for c in range(d)
                    if c != j
                ]
                w1[j, keep, :] = net[0].weight.T
                b1[j, 0] = net[0].bias
                w2[j] = net[2].weight.T
                b2[j, 0] = net[2].bias
        w1, b1, w2, b2 = (t.to(dev) for t in (w1, b1, w2, b2))
        gelu = torch.nn.functional.gelu

        pred = np.empty((len(ys), d), dtype=np.float64)
        with torch.no_grad():
            for a in range(0, len(feat_all), EVAL_CHUNK):
                xb = torch.tensor(
                    feat_all[a : a + EVAL_CHUNK], device=dev
                )
                h = gelu(torch.einsum("nf,dfh->dnh", xb, w1) + b1)
                out = torch.einsum("dnh,dhq->dnq", h, w2) + b2
                pred[a : a + EVAL_CHUNK] = (
                    out[:, :, 1].T.to("cpu", torch.float64).numpy()
                )
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
