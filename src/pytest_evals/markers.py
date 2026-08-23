"""Eval tiers — graduated strictness for evals."""

from __future__ import annotations
from enum import Enum


class EvalTier(str, Enum):
    """Strictness tier for an eval (in increasing order)."""

    EXPERIMENTAL = "experimental"  # Log only — does not block
    USUALLY_PASSES = "usually_passes"  # Warn on failure; blocks only when paired with ALWAYS_PASSES
    ALWAYS_PASSES = "always_passes"  # Hard block on any failure

    def __str__(self) -> str:
        return self.value


