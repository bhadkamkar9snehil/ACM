---
type: agent-memory
---

# ACM SQL Output Map

Primary persistence owner:
- [[../modules/core.output_manager|core.output_manager]]

Primary run-finalization owner:
- [[../modules/core.run_metadata_writer|core.run_metadata_writer]]

Run lifecycle table:
1. ACM_Runs

Primary interpretation tables:
1. ACM_Scores_Wide
2. ACM_Episodes
3. ACM_HealthTimeline
4. ACM_DriftController
5. ACM_DataQuality
