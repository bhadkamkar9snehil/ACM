# ACM V6 — Developer & AI Coding Agent Guide

_This document defines the runtime behavior, conventions, integration points, and modification boundaries for all contributors and AI coding assistants working on the ACM V6 repository._

---

## 🚀 Quick Run (File Mode)

Preferred PowerShell wrapper:
```powershell
.\scripts
un_file_mode.ps1 -Equip FD_FAN -Artifacts artifacts -Config configs\config.yaml -EnableReport
```

Equivalent direct Python invocation:
```powershell
python -m core.acm_main --equip FD_FAN --artifact-root artifacts --config configs\config.yaml --mode batch --enable-report
```

**Notes**
- `--equip` and `--artifact-root` are mandatory.
- Default config path: `configs/config.yaml`.
- Use PowerShell only; do **not** run through notebooks or IDE “Run Cell”.

---

## 🧩 Core Runtime Overview

| File | Role | Critical Notes |
|------|------|----------------|
| `core/acm_main.py` | Primary orchestrator | Never rename or split; handles lifecycle, SQL calls, finalization |
| `core/data_io.py` | CSV/SQL adapters | Normalize timestamps; enforce schema contract |
| `core/fast_features.py` | Polars-first feature computation | Must return **pandas.DataFrame**; ensure no NaNs |
| `core/analytics.py` | Scoring logic (PCA, AR1, IF, GMM) | Keep metric keys consistent (`pca_recon_rmse`, `xcorr_max`, etc.) |
| `core/train.py` | Training & artifact persistence | Output → `run/models/*.joblib` |
| `core/sql_client.py` | Thin pyodbc wrapper | Preserve stored-proc contract (`usp_ACM_StartRun`, `usp_ACM_FinalizeRun`) |
| `report/` | HTML + JSON reports | `index.html` under each run directory |
| `scripts/` | Execution wrappers | No logic duplication with `core` |
| `configs/` | YAML configs | Central runtime options |

---

## ⚙️ Feature Contracts

- **Input:** Clean numeric feature table with timestamp index  
- **Output:** Median-imputed, NaN-free `DataFrame`
- **Mandatory columns:** all sensor tags in training data
- **Imputation rule:** median; must preserve dtype
- **Contract enforcement:** `core/fast_features.compute_basic_features()`

---

## 🧱 Modes of Operation

| Mode | Description | Entry Flag |
|-------|--------------|------------|
| `batch` | File-based (CSV input) | `--mode batch` |
| `stream` | Continuous scoring on live data | `--mode stream` |
| `sql` | SQL-backed execution using stored procedures | `--mode sql` |

**SQL Mode Contract**
- Triggered when `cfg.runtime.storage_backend == "sql"`.
- Must call `dbo.usp_ACM_StartRun` and `dbo.usp_ACM_FinalizeRun`.
- Return dataset must include defined output columns (`Tag`, `Value`, `Timestamp`, etc.).
- Finalize block in `acm_main` must **always execute** (even on exception).

---

## 🧠 AI Coding Agent Rules

1. **Do not rename existing functions** (`run(ctx)`, `finalize_run(ctx)`, `compute_basic_features(df)`).  
2. **Do not add `_v6`, `_new`, or suffixes** to existing filenames or function names.  
3. Always search the repo before introducing a new helper.  
4. Maintain artifact layout: `artifacts/<ASSET>/run/{scores.csv, report/, models/, plots/}`.  
5. Preserve JSON schema of `report/report.json`.  
6. Use only approved dependencies: `numpy`, `pandas`, `polars`, `scikit-learn`, `scipy`, `matplotlib`.  
7. Avoid network calls, cloud APIs, or GPU-specific code.  
8. All new modules must expose a callable `run(ctx)` or `compute(ctx)` for uniform orchestration.  
9. When editing feature or analytics logic, update the **Changelog** section below.

---

## 🧩 Development Workflow

### Typical Edit Flow
1. Extend helper in `core/fast_features.py` (prefer polars expressions; return pandas DataFrame).  
2. Adjust analytics or model logic in `core/analytics.py` or `core/train.py`.  
3. Validate via `scripts/run_file_mode.ps1`.  
4. Generate artifacts and confirm report completeness.  
5. Update **Changelog**.

### Validation Checklist
1. `artifacts/<EQUIP>/run/report/index.html` exists.  
2. `report.json` contains all metrics (`pca_var90_n`, `xcorr_mean`, etc.).  
3. SQL finalization executed (if in SQL mode).  
4. No missing `scores.csv` or `models/*.joblib`.  
5. No NaN columns in final artifact.

---

## 🔒 Protected Core Files

```
core/acm_main.py
core/sql_client.py
core/fast_features.py
core/analytics.py
core/train.py
report/html.py
report/report.py
```

---

## 🧠 Memory & Performance

- Favor **Polars** for heavy joins and window ops.  
- Always convert to pandas before feeding models.  
- Avoid deep copying large DataFrames inside loops.  
- Use `ctx.timer()` or internal timing logs when profiling.  
- For streaming, maintain minimal rolling window state (≤ 1000 samples typical).  

---

## 🧮 Integrations

### SQL
- `pyodbc` with `fast_executemany: true`
- TVP chunk size: `100 000`
- Retry logic:  
  ```yaml
  deadlock_retry:
    attempts: 3
    backoff_seconds: 2
  ```

### File I/O
- CSVs: UTF-8, comma-delimited, timestamp column normalized to UTC.
- Artifacts: Overwrite only within `/run/` folder for each execution.
- Do not hard-delete previous runs — they act as historical references.

---

## 🧩 Project-Specific Conventions

- Report metrics must include:  
  `xcorr_max`, `xcorr_mean`, `pca_var90_n`, `pca_recon_rmse`, `iforest_score`, `fusion_z`, `alert_flag`
- Charts: PCA variance, Cross-correlation heatmap, Reconstruction error time-series, Fused anomaly score overlay
- Folder naming: `<ASSET>` must match equipment ID exactly (spaces replaced by `_`).

---

## 🧱 Release Policy

- No unit tests will be added.  
- No micro-benchmarks unless explicitly required.  
- All commits that affect runtime logic must include a **Changelog** entry.  
- CI/CD or release packaging is handled externally; do not modify `pyproject.toml` or packaging scripts.

---

## 🧾 Changelog

| Date | Author | Change Summary |
|------|---------|----------------|
| 2025-10-24 | Snehil Bhadkamkar | Initial consolidated ACM V6 gemini.md for AI agents and human developers |
| 2025-10-24 | — | Added mode semantics, protected files list, validation checklist, and SQL integration details |
| (Next) | — | — |

---

## ✅ Final Notes

- This document is the **single source of truth** for coding conventions and agent guidance.  
- All AI-assisted commits must conform to this spec.  
- **Do not** introduce new folders or rename existing ones.  
- **Do not** remove this file; it anchors all agent context.  
- Always update the **Changelog** when any operational or analytical logic changes.
