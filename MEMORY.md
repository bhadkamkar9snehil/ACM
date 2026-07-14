# MEMORY.md - agent working memory (read FIRST, before CLAUDE.md)

> The distilled, CURRENT state of this repo for any agent starting a
> session. CLAUDE.md is the full historical knowledge base (200KB+,
> most of it about the pre-rewrite lab) - go there for deep history,
> come here for what is true NOW.
> Last updated: 2026-07-09 (UI overhaul + local-environment handoff).

---

## READ THIS FIRST IF YOU ARE A NEW SESSION ON THE LOCAL GPU BOX

The user is moving development from the cloud sandbox to a local
Windows machine with an RTX 4060 (the GPU box - see "Hardware tiers"
below). If you are starting fresh there:

1. You have NO sandbox proxy remote - `origin` should already point at
   `https://github.com/bhadkamkar9snehil/ACM.git` from a normal
   `git clone`. Verify with `git remote -v` before assuming anything.
2. **Push straight to `main`, always** - explicit standing instruction,
   repeated multiple times. Do not create feature branches or PRs
   unless the user asks. `git checkout main && git pull --ff-only
   origin main` before starting; full local suite green before every
   push; commit and push as you go, not in one giant batch at the end.
3. `uv sync` drops torch (tier2 dependency group) - reinstall CUDA
   torch after every sync: `uv pip install torch --index-url
   https://download.pytorch.org/whl/cu126` (see Hardware tiers).
4. The GitHub MCP connector may need re-authorization on a fresh
   machine/session (claude.ai connector settings, or `claude mcp` /
   `/mcp` interactively) - without it, issue-first cannot be followed
   and must be noted as a deviation in commit messages instead, same
   as happened for the two UI commits below.
5. Two commits (`ddc6cd5` UI feature-complete, `9786805` UI
   ECharts+WebSocket) shipped WITHOUT filed issues because the
   connector was down mid-session - DONE (2026-07-09): retroactively
   filed as #97 and #98 same-session once the connector reconnected,
   both closed against their commits. If you ever find a commit
   referencing an unfiled issue again, follow this same pattern.

---

## What this repo is

**ACM - Asset Condition Monitor, version 2.0.0a0.** Unsupervised,
self-validating asset condition monitoring with ONE dial
(ALPHA_PER_ASSET_YEAR) and an anytime-valid e-process false-alarm
guarantee. The repo root IS the product:

```
src/             flat src-layout (no wrapping package dir); python -m service
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

`src/vendor/echarts.min.js` (Apache-2.0, ~1MB) is vendored and
served at `/vendor/echarts.min.js` by the service itself - the UI is
zero-build and must work air-gapped, so this is never a CDN reference.
Re-vendor by re-downloading the same file if it's ever missing; do not
add a build step to fetch it.

## Git & workflow (current reality)

- **main IS the working branch** (not in production) and the ONLY
  push target - explicit, repeated user instruction: "keep pushing to
  main only." No feature branches, no PRs, unless asked. Remote-session
  branches (claude/*) fast-forward into it when they exist at all.
  Never force-push.
- 167 legacy branches are parked under `archive/*`; the stale original
  refs could not be deleted from the sandbox (git proxy blocks ref
  deletion + tag pushes) - one-time `gh api` cleanup command is in
  CLAUDE.md's Git Workflow section. Still pending as of 2026-07-09.
- **Issue-first**: every non-trivial change gets a GitHub issue;
  commits say `Fix #N - ...`. Docs-only changes are exempt. When the
  GitHub connector is down, note the deviation explicitly in the
  commit message (do not silently skip it, do not block on it either).
- **The full LOCAL suite is the merge gate** - GitHub Actions is
  billing-locked at the account level and never runs. `uv run pytest
  tests` must be green before push, no exceptions; the statistical
  lane blocks like a unit test.
- KB rule: update CLAUDE.md (and this file) after every session's
  durable findings. README-sync rule: user-facing flag/command changes
  update README in the same change.
- ASCII-only in everything touched (CI-pinned for src/ and tests/).
- Development is transitioning from this cloud sandbox to the user's
  local GPU box (Windows, RTX 4060) as of 2026-07-09. Same repo, same
  main-only workflow, same rules - only the machine changes. See the
  "READ THIS FIRST" section at the top of this file.

## Hard invariants (do not violate; most are test-pinned)

- One dial: ALPHA_PER_ASSET_YEAR. Everything else = derived from the
  asset's own data OR a rationale-carrying constant in
  `src/constants.py`. No config files, no per-site tuning surface.
- Verdict contract v1 fields are FROZEN (`src/verdict.py`).
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
- torch is NOT in default `uv sync` (tier2 group): reinstall torch
  after every sync or test_worldmodel silently skips. CPU:
  `uv pip install torch --index-url https://download.pytorch.org/whl/cpu`.
  On the GPU box use the CUDA index instead (cu126 or whatever matches
  the installed driver) - the governor probes for CUDA and switches to
  TorchWorldModel automatically when it's available, no code change.
- uvicorn ships with NO WebSocket protocol library by default, and
  Starlette's TestClient MASKS this (its websocket_connect works even
  without one) - a real browser gets "Unsupported upgrade request" and
  the UI's live stream silently falls back to polling. `websockets` is
  now a hard pyproject dependency; if a WS-dependent test passes but
  the browser shows a gray/dead status dot, check this first.
- The service's async action endpoints (tick/reanchor/bootstrap) run
  the actual work via `asyncio.to_thread` and then broadcast a fresh
  fleet snapshot over `/api/ws` - any NEW action endpoint must follow
  the same pattern (thread the blocking call, then push) or it will
  silently block the event loop / leave the UI stale until next tick.
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
  `uv run python -m evidence.soak --root results/soak1 --minutes 90`
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

## UI (2026-07-09 overhaul - current state)

`src/ui.html` is a single-file, zero-build UI using vendored
Apache ECharts (see above) plus a real-time WebSocket stream:

- Fleet dashboard strip: state donut, worst-first evidence bars (alarm
  line at 1.0 drawn explicitly), confidence-vs-evidence scatter
  (log-scale y, click a dot to open that asset).
- Per-asset detail: health-index trajectory (zoomable area line),
  evidence-domain bars against the alarm threshold, coverage
  familiarity gauge, anatomy organ-surprise bars (origin highlighted),
  failure-time distribution (p10/median/p90 band), episode timeline
  over REAL wall-clock time (faults red, absorbed changes orange, open
  episode extends live), immune floors per fault class + rehearsal
  gauge. Every frozen verdict-contract field is visible SOMEWHERE
  (including `at`, previously missing entirely).
- Real-time: `/api/ws` pushes a fleet snapshot after every tick (loop
  or manual) and every action; client auto-reconnects with backoff and
  falls back to 6s polling if the socket won't hold. Renders are
  hash-debounced (skip repaint if nothing changed) and chart instances
  are reused via `setOption`, never torn down and rebuilt.
- New endpoints backing it: `GET /api/episodes/{key}` (ledger history,
  absorbed changes included - previously invisible), `GET /api/report`
  (the S6 fleet report, existed since S1 as `render_report()` but was
  never wired to an endpoint).
- Verified in real chromium (not just TestClient): page interactive
  ~465ms, asset detail with 6 charts ~429ms, zero JS console errors.
- Screenshots from that verification exist only in the conversation
  history, not committed to the repo (would bloat it) - re-run the
  playwright check in the commit message if you need to reproduce.

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
   run it where it belongs (now imminent - user is setting up the GPU
   box locally), plus C8 rehearsed-manifold sensitivity floors on real
   data with actual CUDA acceleration instead of the CPU lower bound.
4. **Broader evidence**: full Farm A replay, Farms B/C, longer soaks,
   simulator fleets - all cheaper and faster once running locally on
   the GPU box instead of this cloud sandbox.
5. One-time branch-ref cleanup from a machine with gh (command in
   CLAUDE.md Git Workflow) - still pending.

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
