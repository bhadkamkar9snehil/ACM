# MEMORY.md - agent working memory (read FIRST, before CLAUDE.md)

> The distilled, CURRENT state of this repo for any agent starting a
> session. CLAUDE.md is the full historical knowledge base (200KB+,
> most of it about the pre-rewrite lab) - go there for deep history,
> come here for what is true NOW.
> Last updated: 2026-07-08 (restructure + rename + first real evidence).

---

## What this repo is

**ACM - Asset Condition Monitor, version 2.0.0a0.** Unsupervised,
self-validating asset condition monitoring with ONE dial
(ALPHA_PER_ASSET_YEAR) and an anytime-valid e-process false-alarm
guarantee. The repo root IS the product:

```
src/acm/         the package (import name: acm; python -m acm.service)
tests/           unit + statistical lanes (pytest markers)
install.sh|ps1   uv-based one-command install
pyproject.toml   name=acm, version carries the 2
docs/            acm-gem-plan.md (architecture), acm-rethink-plan.md,
                 acm-implementation-plan.md (build guide), acm-factory.md
paper/           research paper draft (lab-era, Markdown)
lab/             the ENTIRE pre-rewrite ACM1 system (six-detector
                 pipeline, simulator, CARE/public benchmark harnesses).
                 Reference + tooling, NOT the product. Runs FROM lab/.
CLAUDE.md        full historical KB (has a PATH TRANSLATION banner:
                 legacy paths read with a lab/ prefix; acm2 module
                 paths read as acm)
MEMORY.md        this file
```

Naming history (all 2026-07-08): #93 moved the legacy lab wholesale to
`lab/`; #94 promoted the acm2/ project to the repo root; #95 renamed
the package `acm2` -> `acm` (the 2 lives in the version field only).
"ACM2" in older docs/KB prose = this product.

## Git & workflow (current reality)

- **main IS the working branch** (not in production). Remote-session
  branches (claude/*) fast-forward into it. Never force-push.
- 167 legacy branches are parked under `archive/*`; the stale original
  refs could not be deleted from the sandbox (git proxy blocks ref
  deletion + tag pushes) - one-time `gh api` cleanup command is in
  CLAUDE.md's Git Workflow section.
- **Issue-first**: every non-trivial change gets a GitHub issue;
  commits say `Fix #N - ...`. Docs-only changes are exempt.
- **The full LOCAL suite is the merge gate** - GitHub Actions is
  billing-locked at the account level and never runs. `uv run pytest
  tests` must be green before push, no exceptions; the statistical
  lane blocks like a unit test.
- KB rule: update CLAUDE.md (and this file) after every session's
  durable findings. README-sync rule: user-facing flag/command changes
  update README in the same change.
- ASCII-only in everything touched (CI-pinned for src/ and tests/).

## Hard invariants (do not violate; most are test-pinned)

- One dial: ALPHA_PER_ASSET_YEAR. Everything else = derived from the
  asset's own data OR a rationale-carrying constant in
  `src/acm/constants.py`. No config files, no per-site tuning surface.
- Verdict contract v1 fields are FROZEN (`src/acm/verdict.py`).
- `acm` never imports the legacy lab (test_import_boundary).
- Never-built list (lab lessons, they are the filter): no trailing/trim
  retention windows, no threshold rules, no distrust gate, no fusion
  auto-tune, no kurt/skew features.
- Timestamps timezone-aware UTC only; the CALLER declares the zone
  (adapters), ingest never guesses. Labels never enter the raw store.
- Alpha is a probability per anchor (REANCHORS_PER_YEAR=52 converts
  the yearly rate); EProcess rejects alpha outside (0,1).
- Cross-tier contract: verdict semantics identical at every tier, only
  power differs (concentration parity is pinned in test_worldmodel).

## Hard-won lessons (2026-07-07/08 sessions - each cost real debugging)

- Column order is NOT part of the store's contract: every concat over
  store frames must be `diagonal_relaxed` (three order-sensitive
  concats each broke production paths; grep before adding a new one).
- Any unsupervised asyncio task in the service is a silent-death
  hazard - the tick loop is guarded (log + retry), keep it that way.
- Fit-side NaN handling must match score-side (3 null rows in 52k once
  killed a monitor via a NaN gram matrix).
- "Virgin" = never bootstrapped (durable data_root/bootstrapped.json
  marker), NOT "no ledger windows" - clean assets never gain windows.
- Episode ledger semantics: FAULT windows mask the baseline;
  change-not-fault windows are ABSORBED into it. A mask that leaves no
  baseline is self-refuting - bootstrap repairs it (drops widest fault
  window, recalibrates).
- Change-not-fault plateaus auto-absorb after ONE anchor period
  (CHANGE_ABSORB_ANCHOR_PERIODS); an absorb IS an anchor so the alpha
  budget holds; drift-shaped episodes never absorb. Absorption is only
  real via calibrate_from_lifetime(include_recent=True) - the governed
  exception for change-closures only.
- torch is NOT in default `uv sync` (tier2 group): reinstall CPU torch
  after every sync (`uv pip install torch --index-url
  https://download.pytorch.org/whl/cpu`) or test_worldmodel silently
  skips.
- CARE data files are SEMICOLON-delimited; naive timestamps declared
  UTC by the adapter; meta cols (status_type_id, train_test, id,
  asset_id) are split/eval-only.
- Evidence-runner detection = ANY alarming tick at/after event_start
  (an early alarm absorbed as change that re-alarms in-window is a
  HIT, not a miss).
- In this sandbox: `pkill -f <pattern>` can match your own shell's
  eval string and self-kill - use bracket patterns like
  `pgrep -f "acm[.]evidence"`. Long jobs: nohup + disown + a Monitor
  with an until-loop; the Bash tool timeout caps at 10 min.

## Current evidence (honest, small-sample)

- **Operational soak (#90): PASSED all 8 criteria.** Real service +
  live-fed buffer, 37.5 compressed asset-days: healthy stayed healthy,
  change declared + auto-absorbed at exactly one anchor period,
  post-absorb plateau healthy, fault alarmed on the absorbed baseline,
  zero tick failures, RSS flat ~178MB. Rerun:
  `uv run python -m acm.evidence.soak --root results/soak1 --minutes 90`
- **CARE Farm A pilot (8 events, Tier 0)**: 0/5 normals false-alarmed;
  event 0 (generator bearing) hit at 240h lag; event 22 (hydraulic)
  alarmed but classified change-not-fault (OPEN observation - do not
  tune, the concentration corroboration failed on this real fault);
  event 10 missed on an 8-day runway (power result). CARE prediction
  windows are 8-20 days - short e-process runway by construction.
- **S7 world model (#91, first execution ever)**: 4/4 tests pass on
  CPU torch. Event 0 HIT at **48h lag vs Tier 0's 240h** through the
  full loop (early alarm -> change via concentration -> absorb ->
  re-alarm). Event 25 clean. CPU cost ~19 min/calibration, ~90
  min/event at 82 channels = Tier 2-S lower bound; the GPU box is the
  intended home.
- Results live in gitignored `results/`; the durable record is the KB.

## Open items (the real next work)

1. **Intervention ingestion (D16)**: fault episodes correctly wait for
   maintenance, but nothing tells ACM maintenance happened except the
   UI Re-anchor button. Work-order/annotation ingestion is the last
   missing piece of the episode loop's real-world contract. (User:
   "wire intervention stuff later" - deferred, not forgotten.)
2. **Event 22 concentration observation**: a real hydraulic fault read
   as a coordinated move. Auto-absorption now guarantees a second look,
   but the corroboration needs more real-fault exposure before it is
   trusted. Documented, deliberately not tuned.
3. **Tier 2 on the GPU box**: the world-model path is proven on CPU;
   run it where it belongs, plus C8 rehearsed-manifold sensitivity
   floors on real data.
4. **Broader evidence**: full Farm A replay, Farms B/C, longer soaks,
   simulator fleets.
5. One-time branch-ref cleanup from a machine with gh (command in
   CLAUDE.md Git Workflow).

## User working style

- Expects end-to-end working results, not "technically correct but
  incomplete". Direct and blunt; correct course immediately.
- Do NOT chase benchmark numbers - remember what ACM is supposed to be
  (unattended lifetime monitoring with a guarantee). Benchmarks are
  evidence, never tuning targets.
- Willing to break established structure when the outcome demonstrably
  improves (made main the ACM2 line, quarantined the lab, renamed the
  package) - but flag architecture-violating suggestions inline before
  acting (standing rule in CLAUDE.md).
- Wants the KB/memory maintained proactively after every work session.
