"""The immune system: label-free self-validation (gem cross-cutting layer)."""

from acm2.immune.harness import (
    ImmuneReport,
    degeneracy_check,
    run_immune_check,
    sensitivity_profile,
)
from acm2.immune.inject import FAULT_CLASSES, inject

__all__ = [
    "FAULT_CLASSES",
    "ImmuneReport",
    "degeneracy_check",
    "inject",
    "run_immune_check",
    "sensitivity_profile",
]
