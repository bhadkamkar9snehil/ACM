---
type: reference
generated_at: 2026-02-21T14:23:15+00:00
---

# Outputs and Status

Outcome semantics:
1. OK
2. DEGRADED
3. NOOP
4. FAIL

Primary output owner:
- [[modules/core.output_manager]]

Primary run metadata owner:
- [[modules/core.run_metadata_writer]]

Primary lifecycle table:
- ACM_Runs

High-value tables to inspect first:
1. ACM_Runs
2. ACM_Scores_Wide
3. ACM_Episodes
4. ACM_HealthTimeline
5. ACM_DriftController
6. ACM_DataQuality
