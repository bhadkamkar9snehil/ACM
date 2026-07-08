"""ACM2 - unsupervised, self-validating asset condition monitoring.

The spine of the gem architecture (docs/acm-gem-plan.md), built per
docs/acm2-implementation-plan.md by the agent factory (docs/acm2-factory.md).

Import boundary rule (D9): nothing in this package may import the legacy
pipeline modules (core, scripts, sim, static). Salvage means copying code in,
never importing it live. Enforced by tests/test_import_boundary.py.
"""

__version__ = "2.0.0a0"
