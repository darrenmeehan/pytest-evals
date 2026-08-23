"""Tests for edge cases and error handling.

Covers boundary conditions, invalid inputs, and unusual scenarios
that the plugin should handle gracefully.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

from conftest import run_pytest_on, count_tests_in


class TestEdgeCases:
    """Boundary conditions and unusual inputs."""

    def test_empty_eval_file_no_crash(self):
        """An eval file with no tests should not crash."""
        source = ""
        result = run_pytest_on(source)
        assert result.returncode in (0, 5), (
            f"Empty file should not crash, got {result.returncode}"
        )

    def test_runs_zero_clamps_to_one(self):
        """runs=0 is clamped to 1 trial (avoid empty parametrization)."""
        source = """
        import pytest

        @pytest.mark.eval(runs=0)
        def eval_zero_runs(run_id):
            assert True
        """
        collected = count_tests_in(source)
        assert collected == 1, f"Expected 1 test with runs=0 (clamped), got {collected}"

    def test_very_large_runs_collects_many(self):
        """A large runs value should collect many tests."""
        source = """
        import pytest

        @pytest.mark.eval(runs=100)
        def eval_many(run_id):
            assert True
        """
        collected = count_tests_in(source)
        assert collected == 100, f"Expected 100 tests, got {collected}"

    def test_eval_function_with_assertion_error(self):
        """An assertion error in an eval should be caught and reported."""
        source = """
        import pytest

        @pytest.mark.eval(tier="always_passes")
        def eval_fails():
            assert False, "this should fail"
        """
        result = run_pytest_on(source)
        assert result.returncode != 0, "Failing eval should exit non-zero"
        assert "assertion" in result.stdout.lower() or "AssertionError" in result.stdout, (
            "Assertion error should appear in output"
        )

    def test_eval_function_with_exception(self):
        """An exception in an eval should be caught and reported."""
        source = """
        import pytest

        @pytest.mark.eval(tier="always_passes")
        def eval_crashes():
            raise ValueError("unexpected error")
        """
        result = run_pytest_on(source)
        assert result.returncode != 0, "Crashing eval should exit non-zero"
        assert "ValueError" in result.stdout, "Exception should appear in output"

    def test_multiple_evals_with_same_name(self):
        """Evals with same function name in different files should not merge."""
        import tempfile
        import shutil

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            # File A: eval_same_name passes (runs=2)
            (tmp_dir / "eval_a.py").write_text(textwrap.dedent("""\
            import pytest
            @pytest.mark.eval(tier="always_passes", runs=2)
            def eval_same_name(run_id):
                assert True
            """))
            # File B: eval_same_name fails (runs=1)
            (tmp_dir / "eval_b.py").write_text(textwrap.dedent("""\
            import pytest
            @pytest.mark.eval(tier="always_passes")
            def eval_same_name():
                assert False
            """))
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(tmp_dir), "-v", "--evals",
                 "-o", "python_files=eval_*.py test_*.py",
                 "-o", "python_functions=eval_* test_*"],
                capture_output=True, text=True, timeout=15, cwd=tmp_dir,
            )
            # Keyed by nodeid (minus param suffix), so both files appear
            # as separate rows with aggregated pass@k:
            assert "eval_a.py::eval_same_name" in result.stdout, "File A row missing"
            assert "eval_b.py::eval_same_name" in result.stdout, "File B row missing"
            assert "2/2" in result.stdout, "File A should show 2/2"
            assert "0/1" in result.stdout, "File B should show 0/1"
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class TestEmptyAndMissing:
    """Empty files, missing dependencies, etc."""

    def test_file_with_only_comments(self):
        source = "# just a comment\n# no tests at all\n"
        result = run_pytest_on(source)
        assert result.returncode in (0, 5), (
            f"Comments-only file should not crash, got {result.returncode}"
        )

    def test_no_eval_marker_on_eval_function(self):
        """An eval_ function without @pytest.mark.eval runs as a regular test."""
        source = """
        def eval_no_marker():
            assert True
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, (
            f"Unmarked eval_ function should pass, got {result.returncode}"
        )


class TestParallelExecution:
    """Tests that should be safe in parallel runs."""

    def test_independent_temp_dirs(self):
        """Each temp_env call should create a unique directory."""
        source = """
        import pytest

        def test_temp_dir_a(temp_env):
            assert temp_env.exists()

        def test_temp_dir_b(temp_env):
            assert temp_env.exists()
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, (
            f"Multiple temp_env should work, got {result.returncode}"
        )


class TestInvalidInputs:
    """Invalid inputs and edge cases."""

    def test_invalid_tier_value_in_marker(self):
        """An invalid tier value should not crash (it's just a string)."""
        source = """
        import pytest

        @pytest.mark.eval(tier="invalid_tier")
        def eval_bad_tier():
            assert True
        """
        result = run_pytest_on(source)
        # The plugin doesn't validate tier values, so it should pass
        assert result.returncode == 0, (
            f"Invalid tier should not crash, got {result.returncode}"
        )

    def test_negative_runs_value_clamps_to_one(self):
        """runs=-1 is clamped to 1 trial (avoid empty parametrization)."""
        source = """
        import pytest

        @pytest.mark.eval(runs=-1)
        def eval_negative_runs(run_id):
            assert True
        """
        collected = count_tests_in(source)
        assert collected == 1, f"Expected 1 test with runs=-1 (clamped), got {collected}"