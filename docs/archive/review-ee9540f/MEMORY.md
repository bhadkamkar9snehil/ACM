# MEMORY.md - current project state

Standing rules are in `AGENTS.md`. This file holds what is true now:
evidence, open items, and how the user works. Replace facts here when
they change; do not append history.

Last updated: 2026-11-12.

## Evidence so far

All of this is small-sample, and all of it is under re-evaluation (see
"Status of prior analysis" in `AGENTS.md`). Results live in the
gitignored `results/` directory.

- **Operational soak (#90).** The real service ran against a live-fed
  buffer for 37.5 compressed asset-days and passed all 8 criteria. The
  healthy phase stayed healthy. The setpoint change was declared and
  absorbed after one anchor period. The injected fault alarmed on the
  absorbed baseline. Memory stayed flat near 178 MB. Rerun with
  `uv run python -m acm.evidence.soak --root results/soak1 --minutes 90`.
- **CARE Farm A pilot (8 events, Tier 0 scorer).** None of the 5 normal
  events alarmed. Of the 3 anomaly events, event 0 (generator bearing)
  was detected 240 hours after event start. Event 22 (hydraulic group)
  alarmed but was classified as a change, not a fault. Event 10
  (gearbox) was missed on an 8-day prediction window. CARE prediction
  windows are 8 to 20 days, which is a short runway for the e-process.
- **World model (Tier 2, #91 and #92), CPU torch only.** Event 0 was
  detected 48 hours after event start, against 240 hours at Tier 0.
  Event 25 (normal) stayed clean. Cost on CPU was about 19 minutes per
  calibration and 90 minutes per event at 82 channels.

CARE files are semicolon-delimited. The adapter declares their naive
timestamps as UTC. The columns `status_type_id`, `train_test`, `id` and
`asset_id` are for splitting and evaluation only. The evidence runner
counts a detection when any alarm occurs at or after event start.

## Open items

1. **Build to the design.** `docs/acm-design.md` is the decided
   design. Its section 11 gives the build order and gates, and section
   12 the status of each part. Step 1 is the evaluation harness. The
   only code so far is the operating-map prototype in
   `src/acm/opmap.py` (issue #143), which has three known failures and
   written-in constants that still need the halve-and-double test.
   `test_change_not_fault_auto_absorbs_after_anchor_period` fails on
   commit ff7ed51 as well as on the working tree.
2. **Event 22.** A real hydraulic fault was read as a coordinated
   change. The concentration check that separates a fault from a change
   failed here. It has not been tuned.
3. **Tier 2 on the GPU.** The world model has only run on CPU torch.
   Run it with CUDA, and measure sensitivity floors on real data.
4. **Broader evidence.** Full Farm A replay, Farms B and C, longer
   soaks, and simulator fleets.
5. **Intervention ingestion.** A fault episode waits for maintenance,
   but only the UI Re-anchor button tells ACM that maintenance
   happened. The user deferred work-order ingestion.
6. **Branch cleanup.** 167 legacy branches are copied under `archive/*`
   but the original refs still exist on the remote. Deleting them is a
   "confirm first" step.
7. **Untracked files at the repo root.** `scratch_refactor*.py`,
   `test_poly.py`, `acm_care_bench/`, `tests/create_parity_baseline.py`
   and `tests/parity_baseline_pandas.pkl` are of unknown origin. Ask
   before deleting or committing them.

## How the user works

- Expects results that work end to end. Is direct when something is
  wrong, and wants the course corrected without a defence of the old
  one.
- Does not want benchmark numbers chased. ACM is judged as an
  unattended monitor with a guarantee.
- Will change established structure when the outcome is demonstrably
  better, and wants to be told first when a suggestion crosses an
  invariant.
