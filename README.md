# ACM - Asset Condition Monitor

> Version 2.0 - the ground-up rewrite. The product is ACM; the 2 lives in the version field, not the name.

ACM watches industrial assets and tells you when something is wrong -
**unattended, with no labels, no training-data preparation, no
thresholds to tune, and a mathematically guaranteed false-alarm
budget**. Point it at an asset's raw sensor history and forget it: it
cleans its own first contact with the data, learns what normal looks
like from the asset's entire life, accumulates statistical evidence
before it speaks, explains every verdict, absorbs legitimate operating
changes on its own, checks its own health weekly, and estimates
time-to-failure while a fault develops.

**One dial.** The only configuration in the entire system is
`ALPHA_PER_ASSET_YEAR` (default 1.0): the promised number of false
alarms per asset per year. Everything else is derived from the asset's
own data or is a structural constant with its rationale written next to
it in the code (`src/acm/constants.py`). There is no config file, no
per-site table, no threshold sheet.

```bash
./install.sh          # or: .\install.ps1 on Windows (installs uv, syncs, self-tests)
uv run python -m acm.service --root acm_data --port 8899 --tick-seconds 300
# self-ticking fleet service + zero-build UI: open http://127.0.0.1:8899
```

Design docs: `docs/acm-gem-plan.md` (the architecture),
`docs/acm-rethink-plan.md` (why the rewrite), and
`docs/acm-implementation-plan.md` (the build guide). The pre-rewrite
system lives under [`lab/`](lab/README.md) as reference and tooling.

---

## Why the guarantee is real (and not a threshold)

Classical anomaly detection alerts when a score crosses a line, so its
false-alarm rate is whatever the data decides it is. ACM instead runs
**anytime-valid e-processes** over its surprise scores: a bank of
betting processes wagers against the hypothesis "this asset is still
healthy", and an alarm fires only when accumulated evidence crosses the
Ville bound for the declared alpha. The math gives a hard ceiling on
false alarms per anchor period regardless of when you look, how long
the asset runs, or what the data distribution is - the guarantee is the
contract, detection power is what improves with tiers and models.

- Alarms **latch**: once evidence crosses, the episode stays open until
  it is resolved (repair, re-anchor, or governed absorption) - evidence
  is never quietly forgotten.
- `REANCHORS_PER_YEAR = 52` converts the yearly rate dial into a
  per-anchor probability, so weekly re-anchoring keeps the yearly
  budget exact.
- Block sizes for the e-process are **derived from calibration
  autocorrelation** - fixed sizes false-alarmed on real 1 Hz pilots.

## What a verdict looks like

Every asset always has exactly one current verdict, and the contract is
frozen (v1, `src/acm/verdict.py`):

| Field | Meaning |
|---|---|
| `state` | `healthy`, `insufficient-history`, `watch`, `alarm`, `escalating`, `change-not-fault` |
| `confidence` | how sure the system is of the state word |
| `evidence` | accumulated e-process evidence (alarm at >= 1.0) |
| `evidence_trail` | everything behind the number: shape, novelty, episode start, signature match, anatomy, horizon |
| `attribution` | which channels carry the surprise |
| `coverage` | is the current operating point inside familiar territory? |
| `model_epoch` | which learned model produced this |
| `falsifiable_by` | what observation would overturn this verdict |

`escalating` carries a **failure-time distribution** (information-gain
horizon plus a case-based trajectory match against the asset's own past
episodes). `change-not-fault` carries a re-baseline proposal - and the
runtime executes it (below).

## The six evidence domains

Six independent domains accumulate evidence in parallel, each with its
own e-process bank and a share of the alpha budget (union bound keeps
the total exact):

| Domain | Catches |
|---|---|
| **magnitude** | conditional surprise: each channel reconstructed from the others; residual z against lifetime calibration |
| **availability** | the parked/silent machine - absence of data is evidence too |
| **horizon-gap** | multi-horizon predictions diverging from actuals |
| **predictability-band** | the asset becoming easier/harder to predict than its history says |
| **transient-response** | startup/shutdown fingerprints drifting from the learned catalogue |
| **dynamics-drift** | Koopman-style linear-dynamics drift - the machine's physics changing |

## Episodes: faults vs changes, decided with corroboration

Evidence crossing the bound opens an **episode** at the surprise onset
(never at the frame boundary). The episode is then adjudicated:

- **drift shape** -> `escalating` (fault-like, horizon attached).
- **step shape + LOW attribution concentration** (a coordinated move
  across channels, not a channel-local defect) -> `change-not-fault`.
  Shape alone cannot separate a constant-severity fault from a setpoint
  change - the concentration corroboration is what can, and it works
  identically at every tier.
- **signature match**: the episode is compared against the asset's own
  ledgered past (channels + shape) and any recurrence is reported with
  confidence.

**Change-not-fault episodes absorb automatically**: when the new
plateau has held for one full anchor period (about a week - the
system's own cadence), the runtime re-anchors, the plateau becomes part
of normal, and the alpha accounting still holds because an absorb IS an
anchor. If surprise resumes on the absorbed baseline, a fresh episode
opens and escalates - the falsifiability text on the verdict is
mechanism, not prose. Fault episodes never self-absorb; they wait for
resolution.

## Lifetime memory (the frog-proof baseline)

The definition of "normal" comes from the asset's **entire life**,
never a trailing window:

- **Immortal raw store**: monthly parquet partitions, append-only,
  atomic writes, timezone-strict UTC, column-order-insensitive, labels
  rejected at the door.
- **Mergeable summaries** make lifetime statistics cheap: count / mean
  / variance merge exactly, quantiles within grid error.
- **Recency cap** (`RECENCY_CAP = 0.20`): recent data can never hold
  more than 20% of the baseline's weight, so a slow drift cannot boil
  the frog - the drift the trailing-window design absorbed is exactly
  the drift ACM alarms on (pinned by test).
- **Episode ledger**: fault windows are masked out of the healthy
  baseline; change-not-fault windows are absorbed into it (each state
  means what it says). A mask that would leave no baseline is
  self-refuting and gets repaired, never obeyed.
- Everything derived (baselines, calibrations) is a cache; replaying
  raw history regenerates it.

## First contact: the bootstrap

Real histories arrive contaminated. On first contact (once per asset
lifetime, tracked durably), ACM runs **detect -> mask -> re-detect to
convergence**: calibrate on the raw life, find episodes (a contiguous
contamination scan plus a full e-process replay), ledger them, then
recalibrate on the masked life and look again - each pass sees a
cleaner definition of normal until nothing new is found. The service
runs this in the tick loop, so the UI is never blocked by a deep
history.

## The immune system

A monitor that silently dies is worse than no monitor. Weekly (per
asset, staggered), ACM validates itself:

- **sensitivity profile**: canonical fault injections against the
  pipeline recipe - can this asset's data even carry a detection?
- **live degeneracy check**: is the deployed scorer's actual output
  alive (a zeroed scorer passes the recipe check - found by test)?
- **PIT conformance**: are the model's probabilities still calibrated?
  (An immune signal only while NOT alarmed - a fault in the tail is not
  model sickness.)

A sick model triggers a governed rebuild, and the finding is a
first-class event in the fleet summary.

## Hardware tiers - same guarantee, more power

The verdict semantics are identical at every tier; only detection power
differs.

| Tier | Scorer | When |
|---|---|---|
| **T0** | conditional ridge reconstruction (`ConditionalSurpriseScorer`) | any CPU box |
| **T2 / T2-S** | per-channel quantile world model (`TorchWorldModel`) | torch importable + GPU-class hardware (probed, never assumed) |

First cross-tier datapoint on real SCADA (CARE Farm A, generator
bearing failure): the world model detected at **48h lag vs Tier 0's
240h** on the same event - after alarming early, classifying the early
signal change-not-fault, absorbing it, and re-alarming when surprise
resumed. (CPU cost of that power: ~19 min per calibration at 82
channels - the GPU box is the intended home.)

## Service, UI, API

`python -m acm.service` is the whole deployment: FastAPI + a
self-ticking loop (guarded - a failing tick is logged and retried, the
loop never dies silently) + a zero-build vanilla-JS UI (one HTML file,
no bundler - deliberate, for air-gapped plants). Live sources attach
with `--live "asset/key=buffer.db"` (repeatable): any bridge that
writes the SQLite buffer shape `(ts, payload_json)` feeds the store on
every tick.

| Endpoint | Purpose |
|---|---|
| `GET /api/assets` | fleet summary, worst-first, immune counts |
| `GET /api/asset/{key}` | the full frozen verdict |
| `GET /api/narrative/{key}` | the verdict as an operator-readable story |
| `GET /api/domains/{key}` | per-domain evidence bars |
| `GET /api/health/{key}` | health-index series (prognosis trajectory) |
| `GET /api/immune/{key}` / `POST /api/immune-pass/{key}` | immune status / run a pass now |
| `POST /api/tick` / `POST /api/tick/{key}` | tick the fleet / one asset |
| `POST /api/reanchor/{key}` | governed episode close + recalibration |
| `POST /api/bootstrap/{key}` | first-contact cleaning on demand |

## Evidence lane (regression evidence, never tuning)

Real-data replays run through the PRODUCTION path and land in
gitignored `results/`; summaries go to the knowledge base.

```bash
# CARE-to-Compare farm replays (adapter declares UTC, labels never enter the store)
uv run python -m acm.evidence.care_replay \
    --farm-dir "care_data/Wind Farm A" --events 40 68 --out results/acm_care_A
# --scorer worldmodel|tier0|auto forces a cross-tier comparison

# The implement-and-forget gate: real service + continuously-fed live buffer
# through healthy -> setpoint change -> fault; exits non-zero on any failure
uv run python -m acm.evidence.soak --root results/soak1 --minutes 90
```

Current evidence (small samples, honestly labeled as such):

- **Operational soak: PASSED all 8 criteria** - 37.5 compressed
  asset-days: healthy stayed healthy, change declared and
  auto-absorbed at exactly one anchor period, post-absorb plateau
  healthy, fault alarmed on the absorbed baseline, zero tick failures,
  RSS flat.
- **CARE Farm A pilot (8 events)**: 0/5 normals false-alarmed (the
  alpha guarantee held on real SCADA); generator-bearing anomaly hit
  (Tier 0 lag 240h, world model 48h); one anomaly alarmed but
  classified change-not-fault (open observation); one missed on an
  8-day evidence runway (power, not a bug). CARE prediction windows
  are 8-20 days - short runway for an e-process by construction.

## Development

```bash
uv sync                                   # env from the committed lockfile
uv run pytest tests                       # full suite (unit + statistical lanes)
uv run pytest tests -m "not statistical"  # fast lane
uv run pytest tests -m statistical        # acceptance lane (immune, conformance)
```

- **Issue-first**: every change has a GitHub issue; commits reference it.
- **The statistical lane blocks like a unit test** - a change that
  greens its target but reds the lane is rejected, not negotiated.
- **The never-built list is the filter**: no trailing/trim windows, no
  threshold rules, no distrust gates, no fusion auto-tuning, no
  kurt/skew features. These are lessons, not omissions - the lab
  earned each one.
- `acm` never imports the legacy lab (CI-enforced import boundary);
  ASCII-only in `src/` and `tests/` (CI-enforced).
- `CLAUDE.md` is the knowledge base - the durable memory of every
  lesson, kept current by rule.

## Repository layout

```
src/acm/        the product (src-layout; import name acm)
tests/           unit + statistical + evidence-machinery tests
install.sh|ps1   one-command install (uv-based)
pyproject.toml   uv-locked project; the ONLY tunable is the alpha dial
docs/            design plans, build guide, ml-book, legacy docs
paper/           research paper draft (Markdown)
lab/             the pre-rewrite ACM1 system: six-detector pipeline,
                 simulator, CARE/public-dataset benchmark harnesses -
                 reference + tooling, not the product (lab/README.md)
CLAUDE.md        the knowledge base
```

## The legacy lab

The pre-rewrite system (stateless six-detector pipeline, correlation-
discounted fusion, self-tuned alarm rules, the full simulator, CARE and
public-dataset benchmark harnesses) is fully documented in
[`lab/README.md`](lab/README.md) and runs from `lab/`:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/bhadkamkar9snehil/ACM/main/lab/setup.sh)   # Linux/macOS
irm https://raw.githubusercontent.com/bhadkamkar9snehil/ACM/main/lab/setup_acm.ps1 | iex       # Windows
cd ~/ACM/lab && python scripts/acm_service.py   # -> http://localhost:8765
```

Its datasets and harnesses remain ACM's evidence fuel; its hard-won
failures (the OMR in-sample bias, the GMM dimensionality collapse, the
contamination-filter rejection, the empty-rule_fired diagnosis) are why
ACM's never-built list exists.
