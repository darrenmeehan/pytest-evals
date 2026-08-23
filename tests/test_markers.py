"""Unit tests for markers — EvalTier enum and eval_tier() helper.

These are pure Python, no subprocess needed.
"""

from __future__ import annotations

import pytest

from pytest_evals.markers import EvalTier


class TestEvalTierEnum:
    """EvalTier string enum with three levels."""

    def test_experimental_value(self):
        assert EvalTier.EXPERIMENTAL.value == "experimental"

    def test_usually_passes_value(self):
        assert EvalTier.USUALLY_PASSES.value == "usually_passes"

    def test_always_passes_value(self):
        assert EvalTier.ALWAYS_PASSES.value == "always_passes"

    def test_str_representation(self):
        assert str(EvalTier.ALWAYS_PASSES) == "always_passes"

    def test_membership(self):
        valid = set(EvalTier)
        assert "experimental" in valid
        assert "usually_passes" in valid
        assert "always_passes" in valid


class TestEvalTierEnum:
    """EvalTier string enum with three levels."""

    def test_experimental_value(self):
        assert EvalTier.EXPERIMENTAL.value == "experimental"

    def test_usually_passes_value(self):
        assert EvalTier.USUALLY_PASSES.value == "usually_passes"

    def test_always_passes_value(self):
        assert EvalTier.ALWAYS_PASSES.value == "always_passes"

    def test_str_representation(self):
        assert str(EvalTier.ALWAYS_PASSES) == "always_passes"

    def test_membership(self):
        valid = set(EvalTier)
        assert "experimental" in valid
        assert "usually_passes" in valid
        assert "always_passes" in valid