# ACM V8 Copilot Guide
- **Mission focus**: autonomous condition monitoring pipeline that ingests CSV/SQL data, self-tunes detectors, and emits charts/tables under `artifacts/{EQUIP}/run_*`.
- **Primary entrypoint**: `python -m core.acm_main --equip FD_FAN --enable-report` (see README §Development Workflow); most flows go through `run_pipeline()` in `core/acm_main.py`.
- **Modes**: file-mode reads `data/*.csv`; SQL-mode requires `configs/sql_connection.ini` and `core/sql_client.SQLClient`. Keep file-mode working before touching SQL paths.

- **Configuration**: `utils/config_dict.ConfigDict` loads cascading config from `configs/config_table.csv` (global `*` rows overridden by equipment-specific rows). Callers expect dot-path access (e.g., `cfg['fusion']['weights']['omr_z']`). Update docs/CHANGELOG + `# To Do.md` when changing schemas.
- **Adaptive tuning**: `core/analytics.py::AdaptiveTuning` logs changes through `core/config_history_writer.log_auto_tune_changes`. Respect this flow instead of writing directly to CSV/SQL.
- **Caching**: `core/model_persistence.py` persists models under `artifacts/{equip}/models`. Signatures must include config+schema; use existing helpers rather than new hash logic.
- **Output contract**: `core/output_manager.OutputManager` governs all CSV/PNG/SQL writes. Route new tables/charts through it; dual-write guardrails expect `ALLOWED_TABLES` and batched transactions.
- **Local time policy**: timestamps are timezone-naive local. Do not reintroduce UTC conversions; rely on `_to_naive*` helpers in `core/output_manager.py` and `core/acm_main.py`.

- **Detectors**: Mahalanobis, PCA, IForest, GMM, AR1, and OMR live under `core/` (`omr.py`, `correlation.py`, `outliers.py`). Fusion happens in `core/fuse.py`; per-regime logic in `core/regimes.py` with GMM clustering. When editing thresholds, ensure fused z-score contracts stay in sync with `docs/Analytics Backbone.md`.
- **Fast features**: `core/fast_features.py` supports pandas + optional Polars. Tests gate regressions in `tests/test_fast_features.py`; keep API surface backward compatible.
- **Drift & episodes**: `core/drift.py` provides multi-feature drift with hysteresis; episodes written via `core/episode_culprits_writer`. New alerting must update `docs/COLDSTART_MODE.md` and `docs/OMR_DETECTOR.md` if behavior changes.
- **Rust bridge**: optional acceleration in `rust_bridge/`. Python must remain primary path (no hard dependency on Rust).

- **Developer workflows**:
	- Rapid run: `python -m core.acm_main --equip GAS_TURBINE --enable-report --artifact-root artifacts`.
	- SQL smoke test: `python scripts/sql/verify_acm_connection.py` (requires local SQL Server, credentials via env vars or ini).
	- Batch harness: `python scripts/analyze_latest_run.py --equip FD_FAN`; docs/BATCH_PROCESSING.md outline batch+replay procedures.
	- PowerShell shortcut: `scripts/run_file_mode.ps1` wraps the baseline run (defaults to file mode).

- **Testing**: use `pytest tests/test_fast_features.py`, `pytest tests/test_dual_write.py`, and `pytest tests/test_progress_tracking.py`. Some tests skip when optional deps (Polars, SQL Server) absent; respect markers instead of disabling.
- **Data contracts**: sample CSVs under `data/` expose a datetime index plus sensor columns. Keep naming consistent with `configs/config_table.csv` sensor tags.
- **Artifacts/backups**: `artifacts/` and `backups/` are gitignored staging directories. Keep derived outputs there; do not add new tracked artifact folders.
- **Documentation cadence**: README is authoritative. When changing pipeline structure, sync guides in `docs/` (notably `Analytics Backbone.md`, `COLDSTART_MODE.md`, `PROJECT_STRUCTURE.md`).
- **Coding style**: Python 3.11, 100-char lines, vectorized pandas/NumPy where possible. `ruff`/`mypy` live in `[project.optional-dependencies]`—run them for linting/typing when touching shared modules.
- **Secrets & config**: never commit credentials. `configs/sql_connection.ini` stays local; reference env-variable fallbacks when documenting new settings.

Please flag unclear sections so we can refine these instructions.