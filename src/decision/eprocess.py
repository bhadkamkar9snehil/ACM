"""Anytime-valid change detection: conformal e-processes (gem Component 3).

THE VALIDITY KEYSTONE. This module converts any scorer's output stream into
alarms with a mathematically guaranteed false-alarm bound, with zero labels
and zero distributional assumptions beyond exchangeability of healthy scores
against their calibration reference.

Mechanism
---------
1. Each incoming score is converted to a smoothed conformal p-value against
   a healthy calibration sample: p = (#{calib > x} + U * (#{calib == x} + 1))
   / (n + 1), U ~ Uniform(0,1). Under exchangeability p is uniform.
2. A betting martingale accumulates evidence against "still healthy":
   the simple mixture over power martingales integrates the betting
   parameter out analytically-free via a discrete epsilon grid:
       e(p) = mean_i [ eps_i * p**(eps_i - 1) ]
   Each factor has expectation 1 under uniform p, so wealth
   W_t = prod e(p_t) is a nonnegative supermartingale under health.
3. Ville's inequality: P(sup_t W_t >= 1/alpha) <= alpha, for ALL t
   simultaneously. Watching the wealth every tick forever costs nothing:
   the guarantee is anytime-valid by construction. ALPHA_PER_ASSET_YEAR is
   therefore the alarm budget for the asset's whole monitored life-year,
   set once, never tuned.

Serial dependence (D12, the design's one real trap)
---------------------------------------------------
Raw SCADA scores are autocorrelated; conformal p-values on raw ticks are
not uniform under health. Two defenses, both used:
- Scores should already be residual-space (conditional model) outputs.
- BLOCK AGGREGATION: the e-process consumes per-block statistics (mean of
  block_size consecutive scores) instead of raw ticks. Blocks longer than
  the score autocorrelation length are approximately exchangeable. The
  empirical alpha-conformance test in tests/test_eprocess.py is the gate:
  it feeds AR(1)-correlated healthy data through and requires the false
  alarm rate to hold the Ville bound.

Multi-timescale bank
--------------------
Fault physics spans minutes to months, so a bank of e-processes runs at
staggered block sizes, each funded with alpha/n_members (union bound keeps
the total budget exact). The bank alarm is "any member crossed its own
1/alpha_member".

Reset policy: wealth is NOT reset on alarm; the alarm state latches until
the consumer (episode logic, S5) closes the episode and re-anchors the
calibration reference. A supermartingale restarted on the same reference
would silently spend the alpha budget twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

_EPS_GRID = np.array([0.05, 0.1, 0.2, 0.35, 0.5, 0.65, 0.8])
_LOG_WEALTH_CAP = 700.0  # exp overflow guard; far above any alarm threshold
_ACF_DECORR_THRESHOLD = 0.1  # |acf| below this = effectively decorrelated
# Refusal floor for the exchangeability audit (#114): a bank whose derived
# block still carries residual |acf| at/above this REFUSES to arm (the
# ValueError becomes insufficient-history at the monitor). Empirical basis
# (250-300 reps, healthy streams, promised alpha 0.05): residual 0.53/0.74
# realized 2.4x/4x the promised false-alarm rate; residual <= ~0.17 stayed
# within ~1.2x (decaying/AR dependence) and ~2.7x (adversarial non-decaying
# regime plateaus, disclosed via exchangeability_acf rather than refused).
_ACF_REFUSAL_FLOOR = 0.2
_MIN_CALIB_BLOCKS = 30


def _acf_at(x: np.ndarray, lag: int) -> float:
    """Lag-`lag` autocorrelation of a centered series (0.0 when the series
    is too short or degenerate - the callers treat that as 'no evidence of
    correlation', which errs conservative only where nothing can be
    estimated anyway)."""
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    n = x.size
    if lag < 1 or n <= lag + 2:
        return 0.0
    x = x - x.mean()
    denom = float(np.dot(x, x))
    if denom <= 0.0:
        return 0.0
    return float(np.dot(x[:-lag], x[lag:])) / denom


def decorrelation_length(x: np.ndarray, max_lag: int | None = None) -> int:
    """Smallest lag at which |autocorrelation| stays below threshold.

    This is how block sizes are DERIVED from the asset's own calibration
    scores instead of chosen: blocks shorter than the correlation length
    break exchangeability and inflate false alarms (the D12 trap, observed
    directly on the S1 pilots at 1s cadence). Never hardcode a block size.

    The search is capped at n // (2 * _MIN_CALIB_BLOCKS) so the derived
    block always leaves >= 30 calibration blocks. When the cap binds
    WITHOUT the series having decorrelated, the returned lag is a lie -
    callers that need the guarantee must check (EProcessBank does, and
    refuses; see #114: the silent version of this produced a measured 4x
    false-alarm-budget violation on short autocorrelated calibrations).
    """
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    n = x.size
    if n < 60:
        return 1
    max_lag = max_lag or n // (2 * _MIN_CALIB_BLOCKS)
    for lag in range(1, max(2, max_lag)):
        if abs(_acf_at(x, lag)) < _ACF_DECORR_THRESHOLD:
            return lag
    return max(1, max_lag)


@dataclass
class EProcess:
    """One conformal betting e-process over block-aggregated scores."""

    calibration: np.ndarray
    alpha: float
    block_size: int = 1
    seed: int = 0
    log_wealth: float = 0.0
    max_log_wealth: float = 0.0
    n_blocks: int = 0
    _buffer: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not 0.0 < self.alpha < 1.0:
            raise ValueError(
                f"alpha must be a probability in (0,1), got {self.alpha}; "
                "rate dials must be converted (see REANCHORS_PER_YEAR)"
            )
        calib = np.asarray(self.calibration, dtype=np.float64)
        calib = calib[np.isfinite(calib)]
        if calib.size < 30:
            raise ValueError(
                f"calibration needs >= 30 finite values, got {calib.size}"
            )
        if self.block_size > 1:
            n_cal = calib.size // self.block_size
            calib = calib[: n_cal * self.block_size].reshape(
                n_cal, self.block_size
            ).mean(axis=1)
            if calib.size < 30:
                raise ValueError(
                    "calibration too short for block_size "
                    f"{self.block_size}: {calib.size} blocks < 30"
                )
        self._calib_sorted = np.sort(calib)
        self._rng = np.random.default_rng(self.seed)

    @property
    def threshold_log(self) -> float:
        return float(np.log(1.0 / self.alpha))

    @property
    def alarmed(self) -> bool:
        """Latching: once wealth has EVER crossed 1/alpha, the alarm holds
        until the consumer re-anchors (see module docstring)."""
        return self.max_log_wealth >= self.threshold_log

    def update(self, scores: np.ndarray | list[float]) -> None:
        """Feed raw tick scores; blocks are formed internally."""
        for s in np.atleast_1d(np.asarray(scores, dtype=np.float64)):
            if not np.isfinite(s):
                continue
            self._buffer.append(float(s))
            if len(self._buffer) >= self.block_size:
                block_stat = float(np.mean(self._buffer[: self.block_size]))
                self._buffer = self._buffer[self.block_size:]
                self._ingest_block(block_stat)

    # ---- durable runtime state (exact restart continuity) -------------
    # The mutable state that evolves per tick: the accumulated wealth, the
    # partial-block buffer, and the RNG (the p-value's smoothing draw
    # advances it every block). Persisting all of it lets a restart resume
    # the e-process BIT-EXACTLY rather than reverting to the last monitor-
    # cache checkpoint. The calibration reference (_calib_sorted, block_size,
    # alpha) is NOT here - it is restored by rebuilding the identical bank.
    def runtime_state(self) -> dict:
        return {
            "log_wealth": self.log_wealth,
            "max_log_wealth": self.max_log_wealth,
            "n_blocks": self.n_blocks,
            "buffer": list(self._buffer),
            "rng": self._rng.bit_generator.state,
        }

    def load_runtime_state(self, d: dict) -> None:
        self.log_wealth = float(d["log_wealth"])
        self.max_log_wealth = float(d["max_log_wealth"])
        self.n_blocks = int(d["n_blocks"])
        self._buffer = [float(x) for x in d.get("buffer", [])]
        if d.get("rng") is not None:
            self._rng.bit_generator.state = d["rng"]

    def _ingest_block(self, x: float) -> None:
        n = self._calib_sorted.size
        greater = n - np.searchsorted(self._calib_sorted, x, side="right")
        equal = np.searchsorted(
            self._calib_sorted, x, side="right"
        ) - np.searchsorted(self._calib_sorted, x, side="left")
        u = self._rng.uniform()
        p = (greater + u * (equal + 1)) / (n + 1)
        p = min(max(p, 1e-12), 1.0)
        e_val = float(np.mean(_EPS_GRID * p ** (_EPS_GRID - 1.0)))
        self.log_wealth = min(
            self.log_wealth + float(np.log(e_val)), _LOG_WEALTH_CAP
        )
        self.max_log_wealth = max(self.max_log_wealth, self.log_wealth)
        self.n_blocks += 1


@dataclass
class BankState:
    alarmed: bool
    evidence: float  # max over members of log_wealth / threshold_log
    member_states: dict[int, tuple[float, bool]]


class EProcessBank:
    """Multi-timescale bank; total budget = alpha via union bound."""

    def __init__(
        self,
        calibration: np.ndarray,
        alpha: float,
        block_sizes: tuple[int, ...] | None = None,
        seed: int = 0,
        audit: bool = True,
    ) -> None:
        """audit=False skips the exchangeability REFUSAL (the residual acf
        is still recorded). Reserved for contamination-scan instruments -
        the bootstrap's detect->mask->re-detect passes, whose calibration
        EXPECTEDLY contains the very fault the pass exists to find (a
        contiguous contaminated block reads as massive autocorrelation,
        so the audit would refuse the instrument that cures the cause).
        Production monitors always audit: the final post-masking
        calibration is the one that arms the guarantee."""
        calib = np.asarray(calibration, dtype=np.float64)
        calib = calib[np.isfinite(calib)]
        # Residual |acf| at the derived base block (0.0 when block sizes
        # were passed explicitly - the caller owns validity in that case).
        # Values in [_ACF_DECORR_THRESHOLD, _ACF_REFUSAL_FLOOR) mean the
        # guarantee is armed but QUALIFIED - consumers surface this.
        self.exchangeability_acf = 0.0
        if block_sizes is None:
            # Derive from the asset's own calibration: base block = the
            # decorrelation length; longer members at geometric spacing for
            # slower fault timescales; keep only members the calibration
            # can actually support with >= 30 blocks.
            base = decorrelation_length(calib)
            # Exchangeability audit (#114): when the derivation's lag cap
            # bound BEFORE the series decorrelated, the base block does not
            # restore exchangeability and the Ville bound degrades.
            # Measured on healthy AR(1) score streams (250-300 reps,
            # promised alpha 0.05): residual |acf| at the capped block of
            # 0.53/0.74 (a 360-row calibration at phi 0.9/0.95) realized
            # 0.12/0.20 false-alarm rates - indefensible, REFUSED below;
            # everything measured at residual |acf| <= ~0.17 stayed within
            # ~1.2x for decaying (AR) dependence and within ~2.7x for the
            # adversarial worst case (non-decaying regime-level plateaus).
            # Policy: refuse the indefensible, DISCLOSE the marginal - the
            # residual acf is recorded on the bank and surfaced so a
            # merely-qualified guarantee is never a silent fiction. In
            # both refusal families, more history genuinely cures it: AR
            # dependence gets a longer lag search; regime plateaus become
            # blockable once life spans >= _MIN_CALIB_BLOCKS regimes. The
            # 2/sqrt(n) term is an estimation-noise allowance so short but
            # genuinely-white calibrations are not refused on ACF noise.
            residual_acf = abs(_acf_at(calib, base))
            cap = max(1, calib.size // (2 * _MIN_CALIB_BLOCKS))
            noise_allowance = 2.0 / np.sqrt(max(calib.size, 1))
            if (
                audit
                and base >= cap
                and residual_acf >= _ACF_REFUSAL_FLOOR + noise_allowance
            ):
                raise ValueError(
                    "calibration too autocorrelated for its length: "
                    f"|acf|={residual_acf:.2f} at the largest supportable "
                    f"block ({base}); a valid false-alarm guarantee needs "
                    "a longer healthy history"
                )
            self.exchangeability_acf = round(residual_acf, 3)
            candidates = [base, 4 * base, 16 * base]
            block_sizes = tuple(
                b for b in candidates if calib.size // b >= _MIN_CALIB_BLOCKS
            ) or (base,)
        # The raw (unsorted, unblocked) calibration stream, retained for
        # consumers that must build derived banks over the SAME reference
        # (immune rehearsal). Passing a member's _calib_sorted instead was
        # a latent bug the #114 exchangeability audit exposed: a SORTED
        # array reads as ~0.9 autocorrelated, so rehearsal had been
        # deriving its block structure over a monotone staircase.
        self.calibration_scores = calib
        member_alpha = alpha / len(block_sizes)
        self.members = [
            EProcess(
                calibration=calib,
                alpha=member_alpha,
                block_size=b,
                seed=seed + i,
            )
            for i, b in enumerate(block_sizes)
        ]
        self.block_sizes = tuple(block_sizes)

    def update(self, scores: np.ndarray | list[float]) -> BankState:
        for m in self.members:
            m.update(scores)
        return self.state()

    # ---- durable runtime state (exact restart continuity) -------------
    def _signature(self) -> str:
        """Stable identity of the calibration REFERENCE this bank's wealth
        was accumulated against. Wealth is only meaningful against the
        same reference, so restore is gated on this matching: a bank
        rebuilt from identical data (deterministic calibration) reproduces
        the same signature and resumes exactly; a rebuilt-from-different-
        data bank does not, and safely starts fresh instead of overlaying
        wealth onto a different block structure."""
        import hashlib

        cal = np.ascontiguousarray(
            np.asarray(self.calibration_scores, dtype=np.float64)
        )
        h = hashlib.sha1(cal.tobytes())
        h.update(repr(self.block_sizes).encode())
        return h.hexdigest()[:16]

    def runtime_state(self) -> dict:
        return {
            "signature": self._signature(),
            "members": {
                str(m.block_size): m.runtime_state() for m in self.members
            },
        }

    def load_runtime_state(self, d: dict) -> bool:
        """Overlay persisted wealth onto this bank. Returns True if applied
        (signature matched), False if skipped (reference differs - the
        conservative fresh start)."""
        if not d or d.get("signature") != self._signature():
            return False
        members = d.get("members", {})
        for m in self.members:
            ms = members.get(str(m.block_size))
            if ms is not None:
                m.load_runtime_state(ms)
        return True

    def state(self) -> BankState:
        member_states = {
            m.block_size: (m.log_wealth, m.alarmed) for m in self.members
        }
        # Evidence = PEAK wealth fraction (matches latching semantics: a
        # latched alarm keeps showing the evidence that caused it). Floor
        # at 0: under health log-wealth drifts negative (a supermartingale
        # earns nothing on uniform p-values); negative wealth is "no
        # evidence", not "negative evidence". The known cost - deep
        # negative wealth delays detection after long healthy runs - is
        # accepted for S1 and revisited with e-detector (ARL-style restart)
        # variants when episode logic lands in S5.
        evidence = max(
            max(0.0, m.max_log_wealth) / m.threshold_log for m in self.members
        )
        return BankState(
            alarmed=any(m.alarmed for m in self.members),
            evidence=float(evidence),
            member_states=member_states,
        )
