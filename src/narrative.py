"""The health narrative (gem C10): the system as an accountable witness.

Every asset gets a continuously maintainable story - what the system
believes, on what evidence, what changed since the last verdict, what it
expects, and what would change its mind. Every sentence is generated FROM
the evidence structure (never the other way around); nothing is prose
without provenance.

Returns a structured list of {kind, text} sections rather than one flat
string - the UI renders each kind with its own label/emphasis instead of
dumping the whole story into an unformatted text block.
"""

from __future__ import annotations

import verdict as V


def build_narrative_sections(
    current: V.Verdict,
    previous: V.Verdict | None = None,
    immune: dict | None = None,
) -> list[dict]:
    v = current
    sections: list[dict] = []

    def add(kind: str, text: str) -> None:
        sections.append({"kind": kind, "text": text})

    add(
        "judgment",
        f"{v.asset_key} is judged {v.state.upper()} as of {v.at} "
        f"(confidence {v.confidence}, model epoch {v.model_epoch}).",
    )

    if previous is not None and previous.state != v.state:
        add(
            "change",
            f"This changed from {previous.state.upper()} at {previous.at}; "
            f"evidence moved {previous.evidence} -> {v.evidence}.",
        )
    elif previous is not None:
        add(
            "change",
            f"Unchanged since {previous.at} "
            f"(evidence {previous.evidence} -> {v.evidence}).",
        )

    trail = v.evidence_trail or {}
    domain = trail.get("domain", "magnitude")
    if v.state in (V.STATE_ALARM, V.STATE_ESCALATING, V.STATE_CHANGE):
        add(
            "evidence",
            f"The evidence is in the {domain} domain at {v.evidence}x the "
            f"alarm threshold, carried by: {', '.join(v.attribution) or 'n/a'}.",
        )
        anat = trail.get("anatomy")
        if anat and anat.get("origin"):
            add(
                "anatomy",
                f"Anatomically it originates in the organ [{anat['origin']}] "
                f"(elevation onset order: {anat.get('onsets')}).",
            )
        if trail.get("shape"):
            add(
                "shape",
                f"The episode shape is '{trail['shape']}' with novelty "
                f"{trail.get('novelty')} against this asset's whole life"
                + (
                    f"; it resembles the past episode starting "
                    f"{trail['signature_match']['episode']} (confidence "
                    f"{trail['signature_match']['confidence']})."
                    if trail.get("signature_match")
                    else "; nothing like it exists in this asset's history."
                ),
            )
        hz = trail.get("horizon")
        if hz:
            if hz.get("gated"):
                add(
                    "horizon",
                    f"Expected crossing of the critical level: median "
                    f"{hz['median_steps']} steps (80% interval "
                    f"{hz['p10_steps']}..{hz['p90_steps']}"
                    + (
                        ", level PROVISIONAL until the first closed episode "
                        "calibrates it)."
                        if hz.get("provisional_level")
                        else ")."
                    ),
                )
            else:
                add(
                    "horizon",
                    f"No failure horizon is shown: {hz.get('reason')} - a "
                    "date is only ever displayed when it is calibrated.",
                )

    cov = v.coverage or {}
    fam = cov.get("operating_point_familiarity")
    if fam is not None:
        word = "well-known" if fam > 0.7 else (
            "moderately known" if fam > 0.3 else "barely seen"
        )
        add(
            "coverage",
            f"The current operating point is {word} territory "
            f"(familiarity {fam}); coverage: {cov.get('calib_rows')} "
            f"calibration rows, {cov.get('scored_rows')} scored.",
        )

    if immune is not None:
        if immune.get("sick"):
            add(
                "immune-sick",
                "SELF-TEST: the detector itself failed its last immune "
                f"pass (pit={immune.get('pit')}, "
                f"live_degenerate={immune.get('live_degenerate')}); a "
                "rebuild was triggered - treat verdicts around that window "
                "with reduced trust.",
            )
        else:
            floors = immune.get("floors", {})
            add(
                "immune-ok",
                "Self-test healthy; measured sensitivity floors (sigma): "
                + ", ".join(f"{k}={v}" for k, v in floors.items())
                + ".",
            )

    add("falsifiable", f"This verdict is falsifiable by: {v.falsifiable_by}")
    return sections
