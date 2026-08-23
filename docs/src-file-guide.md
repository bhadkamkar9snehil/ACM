# src/ file guide

This is the current code map. Start with `constants.py`, then
`decision/eprocess.py`, `scoring/surprise.py`, `monitor.py`, `episodes.py`,
and `runtime.py`. For the conceptual walkthrough, read
`docs/how-acm-works.md`.

## Runtime spine

- **`constants.py`** - rationale-carrying structural constants plus the one
  operator dial, `ALPHA_PER_ASSET_YEAR`.
- **`verdict.py`** - frozen verdict contract and state vocabulary.
- **`monitor.py`** - per-asset scorer and evidence banks. Owns cold-start and
  lifetime calibration, alpha-share accounting, per-tick evidence updates,
  attribution, and restartable bank wealth.
- **`episodes.py`** - episode lifecycle around a monitor: onset, shape,
  novelty, fault vs change classification, matching, re-anchoring,
  absorption, and health trajectory.
- **`runtime.py`** - fleet orchestration: asset registry, onboarding,
  bootstrap, ingestion, ticks, rebuilds, immune passes, persistence, and
  fleet summaries.
- **`fleet_workers.py`** - process-worker entry points for expensive
  onboarding/bootstrap. Workers use private per-asset bootstrap ledgers and
  return diffs; the parent is the only writer of shared SQLite state. Uses
  spawn plus BLAS thread caps to avoid inherited numerical-library locks.
- **`service.py`** - FastAPI service, guarded self-tick loop, API/WebSocket
  surface, UI/vendor serving, and `python -m service` entrypoint.
- **`hardware.py`** - hardware probe, capability tier and resource governor.
- **`ui.html`** - zero-build operator UI using vendored browser assets.
- **`_version.py`** - source version used by runtime/cache compatibility.

## Decision and scoring

- **`decision/eprocess.py`** - validity keystone: conformal p-values,
  betting e-processes, block sizing for serial dependence, exchangeability
  audit, multi-timescale banks, union-bound budgeting, and latched alarms.
- **`scoring/surprise.py`** - default conditional surprise scorer. Reconstructs
  each channel from the others, then exposes aggregate surprise,
  channel-local surprise, PIT diagnostics, attribution, familiarity, and
  concentration.
- **`scoring/worldmodel.py`** - optional Tier-2 learned nonlinear dynamics
  scorers behind the same scoring contract. The masked model remains
  evidence-lane/override-only until its promotion gate is satisfied.
- **`scoring/availability.py`** - standstill and telemetry-gap evidence.
- **`scoring/horizons.py`** - horizon-gap and bilateral predictability streams.
- **`scoring/transients.py`** - recurring transient-response catalogue.
- **`scoring/dynamics.py`** - operator/dynamics drift evidence.

The old S1 marginal robust-z scorer is not a production capability. Its only
remaining implementation is `tests/marginal_scorer.py`, where it acts as the
negative control proving why the conditional scorer is required.

## Memory

- **`memory/baseline.py`** - lifetime definition of normal from the full
  ledger-masked history with bounded recency influence; cached period
  summaries and consecutive-chunk calibration sampling.
- **`memory/ledger.py`** - episode ledger abstraction. Production uses the
  relational state store; process workers may use a private throwaway file
  ledger while computing a bootstrap diff.
- **`memory/summaries.py`** - mergeable per-period statistics and quantile
  sketches.

## Store and ingestion

- **`store/raw.py`** - append-only Parquet history partitioned by asset and
  calendar month. UTC, idempotence, atomic writes and column-order
  independence are enforced here.
- **`store/state.py`** - durable SQLite state: asset registry, runtime journal,
  episodes, verdict history, activity, immune results and e-process wealth.
  Also contains the one-time migration from the pre-SQLite JSON files.
- **`ingest/csv_source.py`** - canonical normalization for tabular input.
- **`ingest/buffer_source.py`** - live `(timestamp, payload_json)` SQLite
  bridge source.
- **`ingest/sources.py`** - pull sources for files, SQLite historian tables
  and JSON HTTP endpoints. All expose `drain(store)` and use the same
  normalization/store path.

## Interpretation and prognosis

- **`novelty.py`** - shape/amplitude novelty and trend-shape classification.
- **`anatomy.py`** - stability-selected functional channel graph, organ
  grouping and origin attribution.
- **`prognosis.py`** - self-gated failure-time distribution from health-index
  drift; refuses to show a horizon when evidence is insufficient.
- **`narrative.py`** - plain-language rendering of verdict, change and immune
  context.

## Immune system

- **`immune/harness.py`** - canonical synthetic fault sensitivity,
  conformance and degeneracy checks.
- **`immune/inject.py`** - drift, step, variance and correlation-break
  injectors.
- **`immune/rehearsal.py`** - counterfactual rehearsal through learned asset
  relationships.

## Evidence

- **`evidence/download_care.py`** - partial CARE-to-Compare archive downloader.
- **`evidence/care_replay.py`** - labelled CARE regression/evidence replay
  through the production runtime. Labels are evaluation-only.
- **`evidence/seed_demo.py`** - seed CARE-shaped data into a live data root for
  operator/demo use.
- **`evidence/soak.py`** - real-service compressed-time operational soak.

## Tests

The tests are part of the product's validity envelope, not disposable scaffolding.
Important lanes include e-process alpha conformance, serial-dependence tests,
lifetime/frog tests, immune sensitivity, restart wealth continuity,
parallel-vs-sequential equivalence, service/API behavior, and optional Tier-2
contract tests. See `docs/testing-and-datasets.md`.
