# ACM Refactor Analysis (Superseded)

This document is superseded by:

- `docs/ACM_SINGLE_ENTRYPOINT_REFACTOR_MASTER_PLAN.md`

Use the master plan for all active execution and source-control gating.

Current policy:
1. Single supported runtime entrypoint is `python -m core.acm`.
2. `core/acm_main.py` is decommissioned from active runtime path.
3. Refactor phases and promotion gates are defined only in the master plan.
