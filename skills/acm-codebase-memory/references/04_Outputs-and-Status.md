---
type: reference
auto-updated: true
generated_at: 2026-03-12T13:16:23+00:00
---

# Outputs and Status

Outcome semantics: OK | DEGRADED | NOOP | FAIL

Primary output owner: [[modules/core.output_manager]]
Primary run metadata owner: [[modules/core.run_metadata_writer]]

High-value tables to inspect first:
1. ACM_Runs
2. ACM_Scores_Wide
3. ACM_Episodes
4. ACM_HealthTimeline
5. ACM_DriftController
6. ACM_DataQuality

See [[knowledge/SQL-Schema]] for full table reference including column names and critical gotchas.
