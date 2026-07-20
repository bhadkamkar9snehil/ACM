"""The world model (S7, gem C1 at Tier 2-S): learned nonlinear dynamics.

Two architectures share one scorer contract:

TorchWorldModel - per-channel quantile MLPs predict each channel from
the OTHER channels' CONTEMPORANEOUS and lagged values - the target's own
history is architecturally excluded (a self-conditioned model tracks its
own faults), and contemporaneous others are included (found by spike:
lagged-only inputs gave the model strictly less information than the
ridge's cross-sectional view - the innovations of coupled drivers were
invisible). Found by the spike itself: a self-conditioned model TRACKS
an additive fault on its own lags (separation 1.28 vs ridge 2.65 on the
nonlinear fixture) - the exact 'tracking model hides drift' failure C9
exists for. Detection models must never condition a channel on itself.
Surprise is the residual from the median head; the q10/q90 heads give
calibrated predictive intervals (pinball loss), so PIT comes from the
model itself rather than an empirical residual grid.

MaskedWorldModel (#100) - ONE shared trunk trained masked-reconstruction
style for very wide assets: each pass masks a fixed seeded group of
channels (ALL their lag entries plus a mask-indicator input) and the
pinball loss reads only the masked channels' predictions. Compute and
weight memory are O(d) in channel count instead of the per-channel
model's O(d^2) - the difference between tens of minutes and seconds at
Farm C width (957 channels). Own-history exclusion holds BY
CONSTRUCTION: channel j's prediction is only ever read from the pass
where j and all its lags were zeroed at the input (verified exactly in
tests: shifting a channel's values moves its residual by precisely
delta/resid_scale - the prediction cannot see the shift). Scoring uses
the SAME fixed partition training used, so the train and score input
distributions are identical and scores are deterministic tick to tick.
The mask indicator is required, not decoration: inputs are MAD-scaled,
so a plain zero means 'at the median' - the model must be told
'unknown', not shown a plausible value. Spike (2026-07-20, CPU):
PIT KS 0.055 vs per-channel 0.052, separation 2.15 vs 2.09 (ridge
1.06), d=48 fit 3.7s vs 7.9s. NOT selected by the governor - reachable
only via scorer_cls_override until CARE evidence-lane parity on the GPU
box lands (issue #100's landing criterion).

Tier placement (D6/D7 honest state): this is the COMPACT world model -
the from-scratch path that D7 guarantees the design never depends on
priors for. Foundation-prior initialization (Chronos-class) remains the
upgrade path when GPU hardware exists; the scorer interface is
identical, so the swap is a drop-in. CPU-trainable by construction
(small MLP, bounded epochs, early stopping): the Tier 2-S reference
envelope.

Import-guarded: torch lives in the optional 'tier2' dependency group; the
system is complete at Tier 0 without it, by design.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import polars as pl

from store.raw import TIMESTAMP_COL

LAG = 8
HIDDEN = 128
QUANTILES = (0.1, 0.5, 0.9)
MAX_EPOCHS = 300
PATIENCE = 20
BATCH = 256
PIT_GRID_K = 257

EVAL_CHUNK = 4096  # rows per held-out eval batch (bounds activations)

# masked model: score-time passes are capped at this many groups, so
# inference is O(d) with a constant of MASK_GROUPS_MAX forward passes.
# 8 groups = 12.5% of channels masked per pass: each prediction still
# sees 87.5% of its potential predictors (a 25% ratio was measurably
# fine on the fixture; 12.5% keeps the handicap negligible on wide
# assets where co-masked predictors actually matter).
MASK_GROUPS_MAX = 8

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


def _scale_channels(frame: pl.DataFrame):
    """Shared fit-side preprocessing: numeric columns, MAD center/scale,
    drop channels with <30 finite values or no spread. Returns
    (channels, centers, scales, z)."""
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
    channels = [cols[i] for i in keep]
    centers_a, scales_a = np.array(centers), np.array(scales)
    z = np.nan_to_num((x[:, keep] - centers_a) / scales_a)
    return channels, centers_a, scales_a, z


def _lag_features(z: np.ndarray) -> np.ndarray:
    """Feature blocks for rows LAG..n-1: contemporaneous + lags 1..LAG,
    all channels - shape [n-LAG, d*(LAG+1)]."""
    nz = z.shape[0]
    blocks = [z[LAG:]]
    for k in range(1, LAG + 1):
        blocks.append(z[LAG - k : nz - k])
    return np.concatenate(blocks, axis=1).astype(np.float32)


class _ResidualLenses:
    """Everything downstream of the residual z-matrix - shared verbatim
    by both world-model architectures so the scorer contract (score,
    score_topk, pit, attribution, channel_surprise, concentration,
    coverage) cannot drift between them. Subclasses provide fit() and
    _residual_z() plus the fitted attributes these methods read."""

    def score(self, frame: pl.DataFrame) -> np.ndarray:
        rz = self._residual_z(frame)
        if rz.shape[0] == 0:
            return np.array([])
        return np.mean(np.abs(rz), axis=1)

    def score_topk(self, frame: pl.DataFrame, k: int = 3) -> np.ndarray:
        """Channel-local lens: mean of the k largest per-channel |residual
        z| per row - cross-tier contract parity with the conditional
        scorer (#92 discipline; rationale in surprise.score_topk, #115)."""
        rz = np.abs(self._residual_z(frame))
        if rz.shape[0] == 0:
            return np.array([])
        kk = min(k, rz.shape[1])
        return np.partition(rz, -kk, axis=1)[:, -kk:].mean(axis=1)

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

    def channel_surprise(
        self, frame: pl.DataFrame, top_k: int = 12
    ) -> dict[str, float]:
        """attribution() with magnitudes kept - cross-tier contract parity
        with the conditional scorer (the #92 lesson: a Tier-2 asset must
        render the same UI, not a degraded one)."""
        rz = np.abs(self._residual_z(frame.tail(min(frame.height, 256 + LAG))))
        if rz.shape[0] == 0:
            return {}
        contrib = np.nanmean(rz, axis=0)
        order = np.argsort(contrib)[::-1][:top_k]
        return {self.channels[i]: round(float(contrib[i]), 3) for i in order}

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

    def _coverage_sample(self, z: np.ndarray, split: int) -> None:
        step = max(1, split // 512)
        self._fit_sample = z[LAG:][:split:step][:512]
        dd = np.sqrt(
            (
                (self._fit_sample[:, None, :] - self._fit_sample[None, :, :])
                ** 2
            ).sum(-1)
        )
        np.fill_diagonal(dd, np.inf)
        self._fit_nn_scale = float(np.median(dd.min(axis=1)))


@dataclass
class TorchWorldModel(_ResidualLenses):
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
        self.channels, self.centers, self.scales, z = _scale_channels(frame)
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
        feat_all = _lag_features(z)
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
            mask3_full = mask3

            def forward(xb, W, m):
                h = gelu(torch.einsum("nf,gfh->gnh", xb, W[0] * m) + W[1])
                return torch.einsum("gnh,ghq->gnq", h, W[2]) + W[3]

            def eval_chunked(W, m, targets):
                """Chunked held-out eval: bounds activation memory to
                EVAL_CHUNK rows regardless of validation size."""
                tot, seen = None, 0
                with torch.no_grad():
                    for a in range(0, len(xv), EVAL_CHUNK):
                        xb = xv[a : a + EVAL_CHUNK]
                        part = pinball_pc(
                            forward(xb, W, m), targets[a : a + EVAL_CHUNK]
                        ) * len(xb)
                        tot = part if tot is None else tot + part
                        seen += len(xb)
                return (tot / seen).cpu()

            # live[i] = original group row of the i-th row still training.
            # Early-stopped channels are COMPACTED out of the tensors so
            # a group where 90% converged stops paying 100% of the FLOPs
            # (their final weights are already frozen in best_w).
            live = list(range(g))
            yt_live, yv_live = yt_g, yv_g
            best = torch.full((g,), float("inf"))
            patience = np.full(g, PATIENCE)
            active = np.ones(g, dtype=bool)
            best_w = [t.detach().clone() for t in (w1, bb1, w2, bb2)]
            for epoch in range(MAX_EPOCHS):
                if on_progress is not None and epoch % 20 == 0:
                    on_progress(gi * MAX_EPOCHS + epoch,
                                n_groups * MAX_EPOCHS)
                W = (w1, bb1, w2, bb2)
                act = torch.tensor(active[live], device=dev,
                                   dtype=torch.float32)
                perm = torch.randperm(len(xt), device=dev)
                for a in range(0, len(xt), BATCH):
                    idx = perm[a : a + BATCH]
                    opt.zero_grad()
                    losses = pinball_pc(forward(xt[idx], W, mask3),
                                        yt_live[idx])
                    (losses * act).sum().backward()
                    opt.step()
                val_live = eval_chunked(W, mask3, yv_live)
                lv = np.asarray(live)
                improved_l = (val_live.numpy() < best.numpy()[lv] - 1e-5) \
                    & active[lv]
                if improved_l.any():
                    imp_l = torch.tensor(improved_l, device=dev)
                    imp_g = torch.tensor(lv[improved_l])
                    for bw, cur in zip(best_w, W):
                        bw[imp_g] = cur.detach()[imp_l]
                    best[imp_g] = val_live[torch.tensor(improved_l)]
                patience[lv[improved_l]] = PATIENCE
                stalled = lv[active[lv] & ~improved_l]
                patience[stalled] -= 1
                active[stalled] = patience[stalled] > 0
                if not active.any():
                    break
                # compact when enough channels have stopped to matter
                dead_l = [i for i, o in enumerate(live) if not active[o]]
                if len(dead_l) >= max(8, len(live) // 4):
                    keep_l = [i for i, o in enumerate(live)
                              if active[o]]
                    kt = torch.tensor(keep_l, device=dev)
                    new_params, states = [], []
                    for p in (w1, bb1, w2, bb2):
                        st = opt.state.get(p, {})
                        states.append({
                            k: (v[kt].clone()
                                if torch.is_tensor(v) and v.dim()
                                and v.shape[0] == p.shape[0] else v)
                            for k, v in st.items()
                        })
                        new_params.append(
                            p.detach()[kt].clone().requires_grad_(True)
                        )
                    w1, bb1, w2, bb2 = new_params
                    # Adam moments move WITH the surviving channels, so
                    # their trajectory is identical to the uncompacted run
                    opt = torch.optim.Adam((w1, bb1, w2, bb2), lr=2e-3)
                    for p, st in zip(new_params, states):
                        if st:
                            opt.state[p] = st
                    mask3 = mask3[kt]
                    ktc = torch.tensor(keep_l, device=dev)
                    yt_live = yt_live[:, ktc]
                    yv_live = yv_live[:, ktc]
                    live = [live[i] for i in keep_l]

            with torch.no_grad():
                for a in range(0, len(xv), EVAL_CHUNK):
                    xb = xv[a : a + EVAL_CHUNK]
                    val_preds[a : a + EVAL_CHUNK, js] = (
                        forward(xb, best_w, mask3_full)[:, :, 1]
                        .T.to("cpu", torch.float64).numpy()
                    )

            # unpack this group's weights into the same per-channel
            # Sequential nets as before: scoring, pickling, and
            # cross-machine loading are untouched (nets live on CPU - a
            # tick scores a few thousand rows, and a CPU net loads
            # anywhere, including a machine without a GPU)
            bw1 = (best_w[0] * mask3_full).cpu()
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
            del w1, bb1, w2, bb2, best_w, opt, mask, mask3, mask3_full
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
        self._coverage_sample(z, split)
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
        feat_all = _lag_features(z)
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


@dataclass
class MaskedWorldModel(_ResidualLenses):
    """O(d) shared-trunk world model for very wide assets (#100).

    One network reconstructs any masked channel group from the rest.
    Input = [d*(LAG+1) lag features with the masked group zeroed,
    d-dim mask indicator]; output = [d, Q] quantiles; loss reads only
    the masked channels. Channel j's prediction is only ever taken from
    the pass where j (contemporaneous AND all lags) was masked - the C9
    own-history exclusion, by construction instead of by per-net input
    pruning. The mask partition is FIXED and seeded: training and
    scoring see identical input distributions, and scores are
    reproducible tick to tick (the e-process must never see mask
    lottery noise). Hidden width scales gently with channel count
    (4 per channel, floor HIDDEN, cap 512) - total weights stay O(d).
    """

    channels: list[str] = field(default_factory=list)
    centers: np.ndarray | None = None
    scales: np.ndarray | None = None
    resid_scales: np.ndarray | None = None
    resid_grids: np.ndarray | None = None
    trunk: object | None = None
    groups: list = field(default_factory=list)
    _fit_sample: np.ndarray | None = None
    _fit_nn_scale: float = 1.0

    @staticmethod
    def _hidden(d: int) -> int:
        return max(HIDDEN, min(512, 4 * d))

    @staticmethod
    def _partition(d: int) -> list[np.ndarray]:
        """Fixed seeded partition into min(d, MASK_GROUPS_MAX) groups."""
        rng = np.random.default_rng(0)
        perm = rng.permutation(d)
        k = min(d, MASK_GROUPS_MAX)
        return [np.sort(perm[i::k]) for i in range(k)]

    @staticmethod
    def _group_cols(groups: list[np.ndarray], d: int) -> list[np.ndarray]:
        """Feature-column indices per group: channel j occupies columns
        j, j+d, ..., j+LAG*d (contemporaneous + every lag block)."""
        return [
            np.concatenate([g + b * d for b in range(LAG + 1)])
            for g in groups
        ]

    # ------------------------------------------------------------- fit
    def fit(self, frame: pl.DataFrame) -> "MaskedWorldModel":
        torch = _torch()
        self.channels, self.centers, self.scales, z = _scale_channels(frame)
        n, d = z.shape
        if n < 20 * LAG:
            raise ValueError(f"world model needs >= {20 * LAG} rows, got {n}")

        H, Q = self._hidden(d), len(QUANTILES)
        feat = _lag_features(z)
        ys = z[LAG:].astype(np.float32)
        split = int(len(ys) * 0.8)
        f_all = feat.shape[1]

        dev = _device(torch)
        torch.manual_seed(0)
        qs = torch.tensor(QUANTILES, dtype=torch.float32, device=dev)
        X = torch.tensor(feat, dtype=torch.float32, device=dev)
        Y = torch.tensor(ys, dtype=torch.float32, device=dev)
        xt, yt = X[:split], Y[:split]
        xv, yv = X[split:], Y[split:]

        trunk = torch.nn.Sequential(
            torch.nn.Linear(f_all + d, H),
            torch.nn.GELU(),
            torch.nn.Linear(H, H),
            torch.nn.GELU(),
            torch.nn.Linear(H, d * Q),
        ).to(dev)
        opt = torch.optim.Adam(trunk.parameters(), lr=2e-3)

        self.groups = self._partition(d)
        gcols = self._group_cols(self.groups, d)
        k = len(self.groups)
        gidx = [torch.tensor(g, device=dev) for g in self.groups]
        gcols_t = [torch.tensor(gc, device=dev) for gc in gcols]

        def masked_forward(xb, gi):
            xm = xb.clone()
            xm[:, gcols_t[gi]] = 0.0
            ind = torch.zeros(xb.shape[0], d, device=dev)
            ind[:, gidx[gi]] = 1.0
            out = trunk(torch.cat([xm, ind], dim=1))
            return out.view(-1, d, Q)

        def masked_pinball(pred, target, gi):
            err = target[:, gidx[gi]].unsqueeze(-1) - pred[:, gidx[gi], :]
            return torch.maximum(qs * err, (qs - 1) * err).mean()

        def val_loss():
            """Masked pinball over every group = every channel scored
            exactly once, chunked to bound activations."""
            tot, seen = 0.0, 0
            with torch.no_grad():
                for a in range(0, len(xv), EVAL_CHUNK):
                    xb, yb = xv[a : a + EVAL_CHUNK], yv[a : a + EVAL_CHUNK]
                    for gi in range(k):
                        tot += float(
                            masked_pinball(masked_forward(xb, gi), yb, gi)
                        ) * len(xb)
                    seen += len(xb)
            return tot / (seen * k)

        rng = np.random.default_rng(1)
        best, patience_left = float("inf"), PATIENCE
        best_state = {kk: vv.detach().clone()
                      for kk, vv in trunk.state_dict().items()}
        for epoch in range(MAX_EPOCHS):
            if on_progress is not None and epoch % 20 == 0:
                on_progress(epoch, MAX_EPOCHS)
            perm = torch.randperm(len(xt), device=dev)
            for a in range(0, len(xt), BATCH):
                idx = perm[a : a + BATCH]
                gi = int(rng.integers(k))
                opt.zero_grad()
                loss = masked_pinball(
                    masked_forward(xt[idx], gi), yt[idx], gi
                )
                loss.backward()
                opt.step()
            v = val_loss()
            if v < best - 1e-5:
                best = v
                best_state = {kk: vv.detach().clone()
                              for kk, vv in trunk.state_dict().items()}
                patience_left = PATIENCE
            else:
                patience_left -= 1
                if patience_left <= 0:
                    break
        trunk.load_state_dict(best_state)
        trunk.eval()
        # trunk lives on CPU after fit, like the per-channel nets: a tick
        # scores a few thousand rows, and a CPU net pickles/loads
        # anywhere, including a machine without a GPU
        self.trunk = trunk.to("cpu")

        # residual calibration on the held-out fold (in-sample-bias law):
        # k-pass predictions with the SAME fixed partition scoring uses
        pred = self._predict(torch, torch.device("cpu"), feat[split:])
        resid = ys[split:] - pred
        med = np.median(resid, axis=0)
        mad = 1.4826 * np.median(np.abs(resid - med), axis=0)
        self.resid_scales = np.maximum(mad, 1e-9)
        self.resid_grids = np.quantile(
            resid, np.linspace(0, 1, PIT_GRID_K), axis=0
        ).T
        self._coverage_sample(z, split)
        return self

    # ----------------------------------------------------------- score
    def _predict(self, torch, dev, feat: np.ndarray) -> np.ndarray:
        """Median-head predictions for every channel: one pass per mask
        group, each channel read from the pass where it was masked.
        Chunked to bound activations; O(d) compute per row."""
        d = len(self.channels)
        Q = len(QUANTILES)
        gcols = self._group_cols(self.groups, d)
        trunk = self.trunk.to(dev) if dev.type == "cuda" else self.trunk
        pred = np.empty((len(feat), d), dtype=np.float64)
        with torch.no_grad():
            for a in range(0, len(feat), EVAL_CHUNK):
                xb = torch.tensor(
                    feat[a : a + EVAL_CHUNK], dtype=torch.float32,
                    device=dev,
                )
                for gi, g in enumerate(self.groups):
                    xm = xb.clone()
                    xm[:, torch.tensor(gcols[gi], device=dev)] = 0.0
                    ind = torch.zeros(xb.shape[0], d, device=dev)
                    ind[:, torch.tensor(g, device=dev)] = 1.0
                    out = trunk(torch.cat([xm, ind], dim=1)).view(-1, d, Q)
                    pred[a : a + EVAL_CHUNK, g] = (
                        out[:, torch.tensor(g, device=dev), 1]
                        .to("cpu", torch.float64).numpy()
                    )
        if dev.type == "cuda":
            self.trunk.to("cpu")
        return pred

    def _residual_z(self, frame: pl.DataFrame) -> np.ndarray:
        torch = _torch()
        z = self._z(frame)
        if z.shape[0] <= LAG:
            return np.zeros((0, len(self.channels)))
        ys = z[LAG:]
        d = len(self.channels)
        dev = _device(torch)
        use_dev = dev if (dev.type == "cuda"
                          and len(ys) * d > 100_000) else torch.device("cpu")
        pred = self._predict(torch, use_dev, _lag_features(z))
        return (ys - pred) / self.resid_scales
