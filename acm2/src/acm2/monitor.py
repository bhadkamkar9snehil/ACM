"""Per-asset monitor: scorer + e-process bank -> verdicts (S1 spine).

Calibration split discipline (the OMR in-sample-bias lesson, made law):
the scorer is FIT on the first part of the calibration frame and the
e-process calibration distribution comes from scoring the HELD-OUT second
part. In-sample residuals understate healthy spread; the split is not
optional.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from acm2 import verdict as V
from acm2.constants import get as const
from acm2.decision.eprocess import EProcessBank
from acm2.scoring import RobustZScorer
from acm2.scoring.surprise import ConditionalSurpriseScorer
from acm2.store.raw import TIMESTAMP_COL

FIT_FRACTION = 0.6
MODEL_EPOCH_FMT = "{tag}-{fit_rows}r-{calib_rows}c"
# alpha split across the two evidence domains (union bound keeps the total
# budget exact): magnitude carries most faults; availability events are
# rarer and structurally distinct.
# union bound keeps the total budget exact across the four domains
MAGNITUDE_ALPHA_SHARE = 0.5
AVAILABILITY_ALPHA_SHARE = 0.15
HORIZON_GAP_ALPHA_SHARE = 0.1
BAND_ALPHA_SHARE = 0.05
TRANSIENT_ALPHA_SHARE = 0.1
DYNAMICS_ALPHA_SHARE = 0.1


def _scorer_tag(scorer_cls) -> str:
    return {
        RobustZScorer: "s1-robustz",
        ConditionalSurpriseScorer: "s4-condsurprise",
    }.get(scorer_cls, scorer_cls.__name__.lower())


@dataclass
class AssetMonitor:
    asset_key: str
    scorer_cls: type = ConditionalSurpriseScorer  # S4 primary; robust-z auxiliary
    scorer: object | None = None
    bank: EProcessBank | None = None
    avail_bank: EProcessBank | None = None
    avail_scorer: object | None = None
    mh_scorer: object | None = None
    gap_bank: EProcessBank | None = None
    band_bank: EProcessBank | None = None
    trans_catalogue: object | None = None
    trans_bank: EProcessBank | None = None
    dyn_drift: object | None = None
    dyn_bank: EProcessBank | None = None
    anatomy: object | None = None
    model_epoch: str = ""
    calib_rows: int = 0
    scored_rows: int = 0
    last_ts: str = ""
    insufficient_reason: str = ""

    def calibrate(self, calib_frame: pl.DataFrame, seed: int = 0) -> bool:
        """Returns False (-> insufficient-history verdicts) when the asset
        cannot support a valid calibration yet; never raises for thin data."""
        n = calib_frame.height
        split = int(n * FIT_FRACTION)
        fit, held_out = calib_frame.head(split), calib_frame.slice(split)
        try:
            self.scorer = self.scorer_cls().fit(fit)
            calib_scores = self.scorer.score(held_out)
            # Rate dial -> per-anchor Ville probability (see
            # REANCHORS_PER_YEAR rationale in the constants registry).
            alpha = float(const("ALPHA_PER_ASSET_YEAR")) / float(
                const("REANCHORS_PER_YEAR")
            )
            self.bank = EProcessBank(
                calib_scores, alpha=alpha * MAGNITUDE_ALPHA_SHARE, seed=seed
            )
            self.avail_bank = self._build_avail_bank(held_out, alpha, seed)
            self._build_horizon_banks(fit, held_out, alpha, seed)
            self._build_transient_bank(calib_frame, alpha, seed)
            self._build_dynamics_bank(fit, held_out, alpha, seed)
            self._learn_anatomy(calib_frame, seed)
        except ValueError as exc:
            self.scorer, self.bank = None, None
            self.insufficient_reason = str(exc)
            return False
        self.calib_rows = n
        self.model_epoch = MODEL_EPOCH_FMT.format(
            tag=_scorer_tag(self.scorer_cls), fit_rows=split, calib_rows=n - split
        )
        return True

    def calibrate_from_lifetime(
        self,
        store,
        ledger=None,
        cache_root=None,
        seed: int = 0,
    ) -> bool:
        """S3 calibration path: the scorer's reference comes from the
        recency-capped, ledger-masked LIFETIME baseline; the e-process
        calibration scores come from a healthy sample of the OLDER life
        (recent periods excluded - a developing fault can never sit inside
        its own calibration reference)."""
        from acm2.memory.baseline import LifetimeBaseline

        try:
            base = LifetimeBaseline.build(
                store, self.asset_key, ledger=ledger, cache_root=cache_root
            )
            sample = base.calibration_sample(store, ledger=ledger)
            if self.scorer_cls is RobustZScorer:
                scorer = RobustZScorer()
                scorer.medians, scorer.scales = base.medians, base.scales
                calib_scores = scorer.score(sample)
            else:
                # conditional scorer: FIT on the older 60% of the lifetime
                # sample, calibrate on the held-out rest (in-sample-bias law)
                split = int(sample.height * FIT_FRACTION)
                scorer = self.scorer_cls().fit(sample.head(split))
                calib_scores = scorer.score(sample.slice(split))
            alpha = float(const("ALPHA_PER_ASSET_YEAR")) / float(
                const("REANCHORS_PER_YEAR")
            )
            self.bank = EProcessBank(
                calib_scores, alpha=alpha * MAGNITUDE_ALPHA_SHARE, seed=seed
            )
            self.avail_bank = self._build_avail_bank(sample, alpha, seed)
            split_mh = int(sample.height * FIT_FRACTION)
            self._build_horizon_banks(
                sample.head(split_mh), sample.slice(split_mh), alpha, seed
            )
            self._build_transient_bank(sample, alpha, seed)
            split_dd = int(sample.height * FIT_FRACTION)
            self._build_dynamics_bank(
                sample.head(split_dd), sample.slice(split_dd), alpha, seed
            )
            self._learn_anatomy(sample, seed)
            self.scorer = scorer
        except ValueError as exc:
            self.scorer, self.bank = None, None
            self.insufficient_reason = str(exc)
            return False
        self.calib_rows = base.rows_total
        self.model_epoch = (
            f"s3-lifetime-{len(base.periods_used)}p-{base.rows_total}r"
        )
        return True

    def _build_avail_bank(
        self, calib_frame: pl.DataFrame, alpha: float, seed: int
    ):
        """Availability stream gets its own fitted scorer (live scales come
        from calibration, NEVER from the frame being scored), its own bank
        and budget share; a thin calibration disables it rather than
        guessing."""
        from acm2.scoring.availability import AvailabilityScorer

        try:
            self.avail_scorer = AvailabilityScorer().fit(calib_frame)
            avail_calib = self.avail_scorer.score(calib_frame)
            return EProcessBank(
                avail_calib,
                alpha=alpha * AVAILABILITY_ALPHA_SHARE,
                seed=seed + 1000,
            )
        except ValueError:
            self.avail_scorer = None
            return None

    def _build_horizon_banks(self, fit_frame, held_out, alpha, seed):
        """C9: multi-horizon gap + two-sided predictability band, each with
        its own bank and budget share. Thin data disables (None), never
        guesses. Fit/calibration split preserved (in-sample-bias law)."""
        from acm2.scoring.horizons import MultiHorizonScorer

        try:
            self.mh_scorer = MultiHorizonScorer().fit(fit_frame)
            gap_calib = self.mh_scorer.gap_stream(held_out)
            band_calib = self.mh_scorer.bilateral_stream(held_out)
            self.gap_bank = EProcessBank(
                gap_calib, alpha=alpha * HORIZON_GAP_ALPHA_SHARE,
                seed=seed + 2000,
            )
            self.band_bank = EProcessBank(
                band_calib, alpha=alpha * BAND_ALPHA_SHARE, seed=seed + 3000,
            )
        except ValueError:
            self.mh_scorer = None
            self.gap_bank = None
            self.band_bank = None

    def _build_transient_bank(self, calib_frame, alpha, seed):
        """C7: the lifetime transient catalogue; leave-one-out distances of
        healthy transients from their nearest sibling ARE the calibration.
        Too few healthy transients disables the stream, never guesses."""
        from acm2.scoring.transients import TransientCatalogue

        try:
            self.trans_catalogue = TransientCatalogue().fit(calib_frame)
            self.trans_bank = EProcessBank(
                self.trans_catalogue.calibration_scores(),
                alpha=alpha * TRANSIENT_ALPHA_SHARE,
                seed=seed + 4000,
            )
        except ValueError:
            self.trans_catalogue = None
            self.trans_bank = None

    def _build_dynamics_bank(self, fit_frame, held_out, alpha, seed):
        """Koopman-flavored dynamics drift (spike passed GO): the operator
        the machine forces us to learn, re-identified per window; drift
        from the healthy reference is its own evidence stream. Thin data
        disables, never guesses."""
        from acm2.scoring.dynamics import DynamicsDrift

        try:
            self.dyn_drift = DynamicsDrift().fit(fit_frame)
            calib = self.dyn_drift.calibration_stream(held_out)
            self.dyn_bank = EProcessBank(
                calib, alpha=alpha * DYNAMICS_ALPHA_SHARE, seed=seed + 5000
            )
        except ValueError:
            self.dyn_drift = None
            self.dyn_bank = None

    def _learn_anatomy(self, calib_frame, seed):
        """C6: the machine's functional anatomy, stability-selected; a thin
        or unstable calibration leaves it None (no anatomical claims)."""
        from acm2.anatomy import Anatomy

        try:
            self.anatomy = Anatomy.learn(calib_frame, seed=seed)
        except (ValueError, AssertionError):
            self.anatomy = None

    def process(self, frame: pl.DataFrame) -> V.Verdict:
        if not frame.is_empty():
            self.last_ts = str(frame.get_column(TIMESTAMP_COL).max())
        if self.bank is None or self.scorer is None:
            return V.Verdict(
                asset_key=self.asset_key,
                at=self.last_ts,
                state=V.STATE_INSUFFICIENT,
                confidence=0.0,
                evidence=0.0,
                evidence_trail={"reason": self.insufficient_reason},
                model_epoch="none",
                coverage={"calib_rows": self.calib_rows},
                falsifiable_by="calibrating on sufficient healthy history",
            )
        scores = self.scorer.score(frame)
        self.scored_rows += frame.height
        state_now = self.bank.update(scores)

        avail_alarmed = False
        avail_evidence = 0.0
        if (
            self.avail_bank is not None
            and self.avail_scorer is not None
            and not frame.is_empty()
        ):
            avail_state = self.avail_bank.update(
                self.avail_scorer.score(frame)
            )
            avail_alarmed = avail_state.alarmed
            avail_evidence = avail_state.evidence

        # EVERY bank ingests EVERY frame - evidence must never be lost to
        # attribution ordering (found by test: a dynamics alarm was
        # starving the band bank of the very data that proved the fault).
        # Only the DOMAIN LABEL is chosen by priority afterwards.
        aux_states: list[tuple[str, object]] = []
        if self.dyn_drift is not None and not frame.is_empty():
            d_stream = self.dyn_drift.drift_stream(frame)
            if d_stream.size:
                aux_states.append(
                    ("dynamics-drift", self.dyn_bank.update(d_stream))
                )
        if self.trans_catalogue is not None and not frame.is_empty():
            t_scores = self.trans_catalogue.score_new(frame)
            if t_scores.size:
                aux_states.append(
                    ("transient-response", self.trans_bank.update(t_scores))
                )
        if self.mh_scorer is not None and not frame.is_empty():
            aux_states.append(
                (
                    "horizon-gap",
                    self.gap_bank.update(self.mh_scorer.gap_stream(frame)),
                )
            )
            aux_states.append(
                (
                    "predictability-band",
                    self.band_bank.update(
                        self.mh_scorer.bilateral_stream(frame)
                    ),
                )
            )
        aux_domain = None
        aux_evidence = 0.0
        for name, st in aux_states:
            if st.alarmed and st.evidence > aux_evidence:
                aux_domain, aux_evidence = name, st.evidence

        if aux_domain is not None and not state_now.alarmed and not avail_alarmed:
            return V.Verdict(
                asset_key=self.asset_key,
                at=self.last_ts,
                state=V.STATE_ALARM,
                confidence=V.confidence_from(self.calib_rows, aux_evidence),
                evidence=round(aux_evidence, 4),
                evidence_trail={"domain": aux_domain},
                attribution=(aux_domain,),
                model_epoch=self.model_epoch,
                coverage={
                    "calib_rows": self.calib_rows,
                    "scored_rows": self.scored_rows,
                },
                falsifiable_by=(
                    "the stream returning inside its healthy band; episode "
                    "close + re-anchor"
                ),
            )
        if avail_alarmed and not state_now.alarmed:
            return V.Verdict(
                asset_key=self.asset_key,
                at=self.last_ts,
                state=V.STATE_ALARM,
                confidence=V.confidence_from(self.calib_rows, avail_evidence),
                evidence=round(avail_evidence, 4),
                evidence_trail={"domain": "availability"},
                attribution=("availability",),
                model_epoch=self.model_epoch,
                coverage={
                    "calib_rows": self.calib_rows,
                    "scored_rows": self.scored_rows,
                },
                falsifiable_by=(
                    "telemetry variance returning to the asset's live "
                    "envelope; episode close + re-anchor"
                ),
            )
        if state_now.alarmed:
            state = V.STATE_ALARM
            falsifiable = (
                "episode close + re-anchor on post-repair healthy data; "
                "the latched wealth is the evidence record"
            )
        elif state_now.evidence >= V.WATCH_EVIDENCE:
            state = V.STATE_WATCH
            falsifiable = (
                "wealth decaying back below the watch line as new blocks "
                "score healthy"
            )
        else:
            state = V.STATE_HEALTHY
            falsifiable = "evidence accumulating across any bank timescale"

        familiarity = (
            self.scorer.coverage(frame)
            if hasattr(self.scorer, "coverage") and not frame.is_empty()
            else 1.0
        )
        return V.Verdict(
            asset_key=self.asset_key,
            at=self.last_ts,
            state=state,
            confidence=round(
                V.confidence_from(self.calib_rows, state_now.evidence)
                * (0.5 + 0.5 * familiarity),
                3,
            ),
            evidence=round(state_now.evidence, 4),
            evidence_trail={
                "members": {
                    str(b): {"log_wealth": round(lw, 3), "alarmed": al}
                    for b, (lw, al) in state_now.member_states.items()
                },
            },
            attribution=tuple(self.scorer.attribution(frame)),
            model_epoch=self.model_epoch,
            coverage={
                "calib_rows": self.calib_rows,
                "scored_rows": self.scored_rows,
                "operating_point_familiarity": round(familiarity, 3),
            },
            falsifiable_by=falsifiable,
        )


def render_report(verdicts: list[V.Verdict]) -> str:
    """Minimal S1 fleet report (markdown). The UI shell arrives at S6."""
    lines = [
        "# ACM2 Fleet Report (S1 minimal)",
        "",
        "| asset | state | evidence | confidence | top attribution | model epoch |",
        "|---|---|---|---|---|---|",
    ]
    for v in verdicts:
        lines.append(
            f"| {v.asset_key} | {v.state} | {v.evidence} | {v.confidence} "
            f"| {', '.join(v.attribution[:3]) or '-'} | {v.model_epoch} |"
        )
    return "\n".join(lines) + "\n"
