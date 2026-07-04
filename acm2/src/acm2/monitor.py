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
from acm2.store.raw import TIMESTAMP_COL

FIT_FRACTION = 0.6
MODEL_EPOCH_FMT = "s1-robustz-{fit_rows}r-{calib_rows}c"


@dataclass
class AssetMonitor:
    asset_key: str
    scorer: RobustZScorer | None = None
    bank: EProcessBank | None = None
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
            self.scorer = RobustZScorer().fit(fit)
            calib_scores = self.scorer.score(held_out)
            # Rate dial -> per-anchor Ville probability (see
            # REANCHORS_PER_YEAR rationale in the constants registry).
            alpha = float(const("ALPHA_PER_ASSET_YEAR")) / float(
                const("REANCHORS_PER_YEAR")
            )
            self.bank = EProcessBank(calib_scores, alpha=alpha, seed=seed)
        except ValueError as exc:
            self.scorer, self.bank = None, None
            self.insufficient_reason = str(exc)
            return False
        self.calib_rows = n
        self.model_epoch = MODEL_EPOCH_FMT.format(
            fit_rows=split, calib_rows=n - split
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
            scorer = RobustZScorer()
            scorer.medians, scorer.scales = base.medians, base.scales
            sample = base.calibration_sample(store, ledger=ledger)
            calib_scores = scorer.score(sample)
            alpha = float(const("ALPHA_PER_ASSET_YEAR")) / float(
                const("REANCHORS_PER_YEAR")
            )
            self.bank = EProcessBank(calib_scores, alpha=alpha, seed=seed)
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

        return V.Verdict(
            asset_key=self.asset_key,
            at=self.last_ts,
            state=state,
            confidence=V.confidence_from(self.calib_rows, state_now.evidence),
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
