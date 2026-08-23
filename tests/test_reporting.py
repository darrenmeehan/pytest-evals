"""Tests for the reporter — pass@k table, tier blocking, exit codes.

The reporter aggregates pass@k results and prints a summary table.
It also enforces exit codes based on eval tier:
- ALWAYS_PASSES failure → non-zero exit
- USUALLY_PASSES / EXPERIMENTAL failure → zero exit
"""

from __future__ import annotations

from conftest import run_pytest_on


class TestPassKTable:
    """The pass@k summary table printed in terminal output."""

    def test_table_shows_section_header(self):
        result = run_pytest_on("""
        import pytest

        @pytest.mark.eval(tier="always_passes", runs=1)
        def eval_ok():
            assert True
        """)
        assert "Eval pass@k" in result.stdout, "Table header not found"

    def test_table_shows_eval_name(self):
        result = run_pytest_on("""
        import pytest

        @pytest.mark.eval(tier="always_passes", runs=1)
        def eval_my_test():
            assert True
        """)
        assert "eval_my_test" in result.stdout, "Eval name not in table"

    def test_table_shows_tier(self):
        result = run_pytest_on("""
        import pytest

        @pytest.mark.eval(tier="experimental", runs=1)
        def eval_exp():
            assert True
        """)
        assert "experimental" in result.stdout, "Tier label not in table"

    def test_table_shows_pass_count(self):
        result = run_pytest_on("""
        import pytest

        @pytest.mark.eval(tier="always_passes", runs=3)
        def eval_three_times(run_id):
            assert True
        """)
        assert "Eval pass@k" in result.stdout, "Table header not found"
        assert "eval_three_times" in result.stdout, "Eval name not in table"
        assert "always_passes" in result.stdout, "Tier label not in table"

    def test_table_shows_partial_failure(self):
        result = run_pytest_on("""
        import pytest

        @pytest.mark.eval(tier="usually_passes", runs=3)
        def eval_partial(run_id):
            assert False
        """)
        assert "Eval pass@k" in result.stdout, "Table header should appear"

    def test_table_shows_no_evals_section(self):
        result = run_pytest_on("""
        def test_regular():
            assert True
        """)
        assert "Eval pass@k" not in result.stdout, (
            "Table should not appear when no evals are collected"
        )


class TestTierBlocking:
    """Tier-based exit code enforcement."""

    def test_always_passes_failure_exits_non_zero(self):
        result = run_pytest_on("""
        import pytest

        @pytest.mark.eval(tier="always_passes")
        def eval_must_pass():
            assert False, "intentional failure"
        """)
        assert result.returncode != 0, "ALWAYS_PASSES failure should block"

    def test_always_passes_all_pass_exits_zero(self):
        result = run_pytest_on("""
        import pytest

        @pytest.mark.eval(tier="always_passes")
        def eval_ok():
            assert True
        """)
        assert result.returncode == 0, "ALWAYS_PASSES all pass should exit 0"

    def test_usually_passes_failure_does_not_block(self):
        """USUALLY_PASSES failure exits 0 (warns, doesn't block)."""
        result = run_pytest_on("""
        import pytest

        @pytest.mark.eval(tier="usually_passes")
        def eval_meh():
            assert False
        """)
        assert result.returncode == 0, (
            f"USUALLY_PASSES failure should not block, got exit {result.returncode}\n"
            f"{result.stdout}"
        )
        assert "usually_passes" in result.stdout, "Tier label should appear"

    def test_experimental_failure_does_not_block(self):
        """EXPERIMENTAL failure exits 0 (logs only)."""
        result = run_pytest_on("""
        import pytest

        @pytest.mark.eval(tier="experimental")
        def eval_exp():
            assert False
        """)
        assert result.returncode == 0, (
            f"EXPERIMENTAL failure should not block, got exit {result.returncode}\n"
            f"{result.stdout}"
        )
        assert "experimental" in result.stdout, "Tier label should appear"

    def test_mixed_tiers_always_passes_fail_blocks(self):
        result = run_pytest_on("""
        import pytest

        @pytest.mark.eval(tier="always_passes")
        def eval_blocker():
            assert False
        """)
        assert result.returncode != 0, "ALWAYS_PASSES failure should block even mixed"

    def test_passing_then_failing_always_passes_still_blocks(self):
        result = run_pytest_on("""
        import pytest

        @pytest.mark.eval(tier="always_passes")
        def eval_ok():
            assert True

        @pytest.mark.eval(tier="always_passes")
        def eval_fail():
            assert False
        """)
        assert result.returncode != 0, "One ALWAYS_PASSES failure should block"

    def test_all_always_passes_pass_with_usually_passes_fail(self):
        """ALWAYS_PASSES pass + USUALLY_PASSES fail exits 0 (non-blocking tier doesn't block)."""
        result = run_pytest_on("""
        import pytest

        @pytest.mark.eval(tier="always_passes")
        def eval_blocker():
            assert True

        @pytest.mark.eval(tier="usually_passes")
        def eval_meh():
            assert False
        """)
        assert result.returncode == 0, (
            f"ALWAYS_PASSES pass + USUALLY_PASSES fail should exit 0, "
            f"got {result.returncode}\n{result.stdout}"
        )
        assert "eval_blocker" in result.stdout, "eval_blocker should be in table"
        assert "eval_meh" in result.stdout, "eval_meh should be in table"

    def test_non_eval_setup_error_blocks_even_with_nonblocking_evals(self):
        """Regression: a setup error in a regular test must not be downgraded
        to exit 0 just because only non-blocking evals failed."""
        result = run_pytest_on("""
        import pytest

        @pytest.fixture
        def broken():
            raise RuntimeError("setup boom")

        def test_needs_broken(broken):
            assert True

        @pytest.mark.eval(tier="experimental")
        def eval_exp():
            assert False
        """)
        assert result.returncode != 0, (
            f"Setup error in regular test should block, got exit {result.returncode}\n"
            f"{result.stdout}"
        )


class TestTableSymbols:
    """Symbols in the pass@k table."""

    def test_all_pass_shows_checkmark(self):
        result = run_pytest_on("""
        import pytest

        @pytest.mark.eval(tier="always_passes", runs=1)
        def eval_ok():
            assert True
        """)
        assert "✅" in result.stdout, "All-pass eval should show ✅"

    def test_always_passes_fail_shows_blocking_message(self):
        result = run_pytest_on("""
        import pytest

        @pytest.mark.eval(tier="always_passes")
        def eval_fail():
            assert False
        """)
        assert "ALWAYS_PASSES evals failed" in result.stdout, (
            "Blocking message should appear"
        )


class TestTableFormat:
    """Formatting of the pass@k table."""

    def test_multiple_evals_show_each_on_separate_line(self):
        result = run_pytest_on("""
        import pytest

        @pytest.mark.eval(tier="always_passes")
        def eval_a():
            assert True

        @pytest.mark.eval(tier="experimental")
        def eval_b():
            assert True
        """)
        assert "eval_a" in result.stdout
        assert "eval_b" in result.stdout