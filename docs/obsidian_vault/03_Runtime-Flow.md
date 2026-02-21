---
type: reference
generated_at: 2026-02-21T06:46:02+00:00
---

# Runtime Flow

Primary runtime entrypoint is `python -m core.acm`.

Main high-level sequence:
1. parse args
2. initialize observability
3. connect SQL
4. load config and equipment context
5. start run and resolve window
6. load data and coldstart handling
7. data contract validation
8. feature build and imputation
9. load or fit models
10. score detectors
11. regime label and quality checks
12. calibrate and fuse
13. episode extraction
14. drift computation
15. persist outputs
16. write run metadata and finalize run

Read next:
- [[01_Modules]]
- [[04_Outputs-and-Status]]
