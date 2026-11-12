"""ACM - unsupervised, self-validating asset condition monitoring.

The spine of the gem architecture (docs/archive/plans-2026-07/acm-gem-plan.md), built per
docs/archive/plans-2026-07/acm-implementation-plan.md by the agent factory (docs/archive/plans-2026-07/acm-factory.md).

Import boundary rule (D9): nothing in this package may import the legacy
pipeline modules (core, scripts, sim, static). Salvage means copying code in,
never importing it live. Enforced by tests/test_import_boundary.py.
"""

__version__ = "2.0.0a0"
