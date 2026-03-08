# OutputManager Modularization Plan (2026-02-22)

## Goal
Reduce `core/output_manager.py` complexity while preserving existing runtime behavior and callsites.

Current size: ~4000 lines, mixed responsibilities.

## Current Responsibilities in `OutputManager`
1. SQL write core:
- dataframe preparation
- metadata population
- insert/upsert policies
- batching and transaction handling
- schema/introspection helpers

2. Domain writers:
- scores/episodes
- PCA artifacts
- drift/correlation/seasonality
- regime/model lifecycle tables
- data quality + contract validation

3. Pipeline orchestration:
- `prepare_persistence_inputs`
- `run_persistence_stage`
- `persist_pipeline_outputs`
- analytics generation + artifact fanout

4. Runtime utility:
- SQL data loading delegation
- audit/integrity helpers
- cache and flush lifecycle

## Target Module Split
Phase order is designed to avoid broad callsite churn.

### Phase A (safe extraction, low dependency)
1. `core/output_sql_core.py`
- move: `_prepare_dataframe_for_sql`, `_bulk_insert_sql` decomposition helpers,
  policy builders, metadata population, table contract/audit helpers.
- keep: thin pass-through methods on `OutputManager` for compatibility.

2. `core/output_writers_domain.py`
- move domain table writers:
  `write_scores`, `write_episodes`, `write_run_stats`, `write_pca_*`,
  `write_*correlation*`, `write_drift_*`, `write_*seasonal*`,
  `write_feature_drop_log`, `write_data_contract_validation`, etc.
- expose pure functions/classes receiving `OutputManager` context.

### Phase B (orchestration extraction)
3. `core/output_pipeline_orchestrator.py`
- move: `prepare_persistence_inputs`, `run_persistence_stage`,
  `persist_pipeline_outputs`, `persist_additional_artifacts`,
  `persist_core_outputs`.
- keep `OutputManager` as façade and dependency container.

### Phase C (final façade slimdown)
4. `core/output_manager.py`
- retain only:
  - constructor/state
  - lifecycle (`flush`, `close`, `get_stats`)
  - delegated public API surface used by external modules.

## Compatibility Strategy
1. Do not rename public methods during extraction.
2. Preserve method signatures and return shapes.
3. Keep existing callsites unchanged in:
- `core/acm.py`
- `core/forecast_engine.py`
- `core/detector_orchestrator.py`
- `core/pipeline_types.py`
- `core/model_lifecycle.py`
- `core/adaptive_thresholds.py`
- `core/drift.py`
- `core/fast_features.py`
- `core/regimes.py`

## Guardrails
1. All `write_dataframe(sql_table=...)` paths must pass explicit `write_policy`.
2. Metadata (`RunID`, `EquipID`, `CreatedAt`) must be generated before write.
3. Schema datetime handling must be schema-driven first, dynamic-name fallback second.
4. No reintroduction of static per-table maintenance maps for behavior.

## Immediate Next Refactor (recommended)
Extract SQL core first:
1. Create `core/output_sql_core.py` with:
- `WritePolicy`
- metadata population
- dataframe prep
- insert/upsert core
- table contract helpers
2. In `OutputManager`, replace method bodies with delegated calls.
3. Add focused unit tests for SQL core methods independent of full `OutputManager`.
