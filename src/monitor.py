"""Per-asset monitor: scorer + e-process bank -> verdicts.

Calibration split discipline: the scorer is fit on the first part of the
calibration frame and the e-process calibration distribution comes from
scoring the held-out second part. In-sample residuals understate healthy
spread; the split is not optional.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

import verdict as V
from constants import get as const
from decision.eprocess import EProcessBank
from scoring.surprise import ConditionalSurpriseScorer
from store.raw import TIMESTAMP_COL

FIT_FRACTION = 0.6
MODEL_EPOCH_FMT = "{tag}-{fit_rows}r-{calib_rows}c"
# The union bound keeps the total alpha budget exactly ALPHA_PER_ASSET_YEAR.
MAGNITUDE_ALPHA_SHARE = 0.4
CHANNEL_LOCAL_ALPHA_SHARE = 0.1
AVAILABILITY_ALPHA_SHARE = 0.15
HORIZON_GAP_ALPHA_SHARE = 0.1
BAND_ALPHA_SHARE = 0.05
TRANSIENT_ALPHA_SHARE = 0.1
DYNAMICS_ALPHA_SHARE = 0.1
# Below this channel count the mean's dilution factor is small enough that
# funding a separate channel-local stream would mostly duplicate evidence.
CHANNEL_LOCAL_MIN_CHANNELS = 8


def _scorer_tag(scorer_cls) -> str:
    if scorer_cls is ConditionalSurpriseScorer:
        return "s4-condsurprise"
    return scorer_cls.__name__.lower()


@dataclass
class AssetMonitor:
    asset_key: str
    scorer_cls: type = ConditionalSurpriseScorer
    scorer: object | None = None
    bank: EProcessBank | None = None
    chan_bank: EProcessBank | None = None
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
        """Calibrate from a cold-start frame; thin data returns False."""
        n = calib_frame.height
        split = int(n * FIT_FRACTION)
        fit, held_out = calib_frame.head(split), calib_frame.slice(split)
        try:
            self.scorer = self.scorer_cls().fit(fit)
            calib_scores = self.scorer.score(held_out)
            alpha = float(const("ALPHA_PER_ASSET_YEAR")) / float(
                const("REANCHORS_PER_YEAR")
            )
            self.bank = EProcessBank(
                calib_scores, alpha=alpha * MAGNITUDE_ALPHA_SHARE, seed=seed
            )
            self.chan_bank = self._build_channel_bank(held_out, alpha, seed)
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
        self.insufficient_reason = ""
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
        include_recent: bool = False,
        audit: bool = True,
    ) -> bool:
        """Calibrate against ledger-masked lifetime memory.

        Recent periods are excluded from e-process calibration so developing
        faults cannot calibrate themselves away. include_recent=True is the
        governed exception after a change-not-fault episode is absorbed.
        """
        from memory.baseline import LifetimeBaseline

        try:
            base = LifetimeBaseline.build(
                store, self.asset_key, ledger=ledger, cache_root=cache_root
            )
            sample = base.calibration_sample(
                store,
                ledger=ledger,
                exclude_recent=0 if include_recent else None,
            )
            split = int(sample.height * FIT_FRACTION)
            scorer = self.scorer_cls().fit(sample.head(split))
            held_out = sample.slice(split)
            calib_scores = scorer.score(held_out)
            alpha = float(const("ALPHA_PER_ASSET_YEAR")) / float(
                const("REANCHORS_PER_YEAR")
            )
            self.bank = EProcessBank(
                calib_scores,
                alpha=alpha * MAGNITUDE_ALPHA_SHARE,
                seed=seed,
                audit=audit,
            )
            self.chan_bank = self._build_channel_bank(
                held_out, alpha, seed, scorer=scorer
            )
            self.avail_bank = self._build_avail_bank(sample, alpha, seed)
            self._build_horizon_banks(
                sample.head(split), sample.slice(split), alpha, seed
            )
            self._build_transient_bank(sample, alpha, seed)
            self._build_dynamics_bank(
                sample.head(split), sample.slice(split), alpha, seed
            )
            self._learn_anatomy(sample, seed)
            self.scorer = scorer
        except ValueError as exc:
            self.scorer, self.bank = None, None
            self.insufficient_reason = str(exc)
            return False
        self.calib_rows = base.rows_total
        self.insufficient_reason = ""
        self.model_epoch = (
            f"s3-lifetime-{len(base.periods_used)}p-{base.rows_total}r"
        )
        return True

    def _build_channel_bank(
        self, held_out: pl.DataFrame, alpha: float, seed: int, scorer=None
    ):
        """Build the channel-local top-k evidence stream when it is distinct."""
        scorer = scorer if scorer is not None else self.scorer
        if (
            scorer is None
            or not hasattr(scorer, "score_topk")
            or len(getattr(scorer, "channels", ())) < CHANNEL_LOCAL_MIN_CHANNELS
        ):
            return None
        try:
            return EProcessBank(
                scorer.score_topk(held_out),
                alpha=alpha * CHANNEL_LOCAL_ALPHA_SHARE,
                seed=seed + 500,
            )
        except ValueError:
            return None

    def _build_avail_bank(
        self, calib_frame: pl.DataFrame, alpha: float, seed: int
    ):
        """Build the calibrated availability evidence stream."""
        from scoring.availability import AvailabilityScorer

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
        """Build horizon-gap and two-sided predictability evidence streams."""
        from scoring.horizons import MultiHorizonScorer

        try:
            self.mh_scorer = MultiHorizonScorer().fit(fit_frame)
            gap_calib = self.mh_scorer.gap_stream(held_out)
            band_calib = self.mh_scorer.bilateral_stream(held_out)
            self.gap_bank = EProcessBank(
                gap_calib,
                alpha=alpha * HORIZON_GAP_ALPHA_SHARE,
                seed=seed + 2000,
            )
            self.band_bank = EProcessBank(
                band_calib,
                alpha=alpha * BAND_ALPHA_SHARE,
                seed=seed + 3000,
            )
        except ValueError:
            self.mh_scorer = None
            self.gap_bank = None
            self.band_bank = None

    def _build_transient_bank(self, calib_frame, alpha, seed):
        """Build the transient-response catalogue evidence stream."""
        from scoring.transients import TransientCatalogue

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
        """Build the dynamics-drift evidence stream."""
        from scoring.dynamics import DynamicsDrift

        try:
            self.dyn_drift = DynamicsDrift().fit(fit_frame)
            calib = self.dyn_drift.calibration_stream(held_out)
            self.dyn_bank = EProcessBank(
                calib,
                alpha=alpha * DYNAMICS_ALPHA_SHARE,
                seed=seed + 5000,
            )
        except ValueError:
            self.dyn_drift = None
            self.dyn_bank = None

    def _learn_anatomy(self, calib_frame, seed):
        """Learn machine anatomy when calibration supports a stable graph."""
        from anatomy import Anatomy

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

        # Every bank ingests every frame. Domain priority is applied only
        # after updating them, so one domain cannot starve another of data.
        aux_states: list[tuple[str, object]] = []
        # Caches written before the channel-local bank existed lack the field.
        chan_bank = getattr(self, "chan_bank", None)
        if chan_bank is not None and not frame.is_empty():
            aux_states.append(
                (
                    "channel-local",
                    chan_bank.update(self.scorer.score_topk(frame)),
                )
            )
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
            aux_trail: dict = {"domain": aux_domain}
            aux_attr: tuple = (aux_domain,)
            if aux_domain == "channel-local" and not frame.is_empty():
                if hasattr(self.scorer, "attribution"):
                    aux_attr = tuple(self.scorer.attribution(frame))
                if hasattr(self.scorer, "channel_surprise"):
                    aux_trail["channel_surprise"] = (
                        self.scorer.channel_surprise(frame)
                    )
            return V.Verdict(
                asset_key=self.asset_key,
                at=self.last_ts,
                state=V.STATE_ALARM,
                confidence=V.confidence_from(self.calib_rows, aux_evidence),
                evidence=round(aux_evidence, 4),
                evidence_trail=aux_trail,
                attribution=aux_attr,
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
        channel_surprise = (
            self.scorer.channel_surprise(frame)
            if hasattr(self.scorer, "channel_surprise")
            and not frame.is_empty()
            else {}
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
                **(
                    {"channel_surprise": channel_surprise}
                    if channel_surprise
                    else {}
                ),
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

    _WEALTH_BANKS = (
        "bank",
        "chan_bank",
        "avail_bank",
        "gap_bank",
        "band_bank",
        "trans_bank",
        "dyn_bank",
    )

    def runtime_state(self) -> dict:
        out = {}
        for name in self._WEALTH_BANKS:
            bank = getattr(self, name, None)
            if bank is not None:
                out[name] = bank.runtime_state()
        return out

    def load_runtime_state(self, state: dict) -> list[str]:
        """Overlay persisted bank wealth when calibration signatures match."""
        restored = []
        for name in self._WEALTH_BANKS:
            bank = getattr(self, name, None)
            bank_state = (state or {}).get(name)
            if (
                bank is not None
                and bank_state is not None
                and bank.load_runtime_state(bank_state)
            ):
                restored.append(name)
        return restored


def render_report(verdicts: list[V.Verdict]) -> str:
    """Render a compact markdown fleet report."""
    lines = [
        "# ACM Fleet Report",
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
