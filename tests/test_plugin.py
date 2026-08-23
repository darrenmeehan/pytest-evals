"""Tests for plugin presence, marker registration, and CLI flags.

Uses subprocess to verify the plugin is discoverable and correctly
registers markers and CLI options.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

from conftest import run_pytest_on


class TestPluginPresence:
    """Plugin discovery and registration."""

    def test_plugin_is_registered_in_pytest(self):
        """Given: pytest-evals is installed.
        When:  pytest --co lists plugins.
        Then:  The output contains 'evals-' indicating the plugin loaded.
        """
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--co"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert "evals-" in result.stdout, (
            f"pytest-evals plugin not registered\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_eval_marker_is_registered(self):
        """Given: pytest-evals is installed.
        When:  pytest --markers lists markers.
        Then:  The 'eval(tier=' marker description is shown.
        """
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--markers", "-q"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert "eval(tier=" in result.stdout, "eval marker not found in --markers output"


class TestCLIOptions:
    """CLI flags declared by the plugin."""

    def test_evals_flag_enables_reporter(self):
        """Given: An inline eval file with a passing eval.
        When:  pytest --evals is passed.
        Then:  The eval runs and the reporter table is printed.
        """
        source = textwrap.dedent("""\
        import pytest

        @pytest.mark.eval
        def eval_always_passes():
            assert True
        """)
        result = run_pytest_on(source)
        assert result.returncode == 0, (
            f"--evals should run evals, got exit {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert "Eval pass@k" in result.stdout, (
            "Reporter should print 'Eval pass@k' table with --evals"
        )

    def test_evals_flag_missing_no_reporter(self):
        """Given: An inline eval file.
        When:  pytest is run WITHOUT --evals.
        Then:  The reporter table is absent from stdout.
        """
        source = """
        import pytest
        @pytest.mark.eval
        def eval_always_passes():
            assert True
        """
        import tempfile
        from pathlib import Path
        import shutil

        tmp_dir = Path(tempfile.mkdtemp())
        tmp_file = tmp_dir / "eval_test.py"
        tmp_file.write_text(textwrap.dedent(source))
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(tmp_file), "-v",
                 "-o", "python_files=eval_*.py test_*.py",
                 "-o", "python_functions=eval_* test_*"],
                capture_output=True,
                text=True,
                timeout=15,
                cwd=tmp_dir,
            )
            assert "Eval pass@k" not in result.stdout, (
                "Eval pass@k table should not appear without --evals"
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_pass_k_flag_is_accepted(self):
        """Given: An inline eval file.
        When:  pytest --evals --pass-k 5 is passed.
        Then:  The flag is accepted and the command exits 0.
        """
        source = textwrap.dedent("""\
        import pytest

        @pytest.mark.eval(tier="always_passes", runs=1)
        def eval_always_passes():
            assert True
        """)
        result = run_pytest_on(source, "--pass-k", "5")
        assert result.returncode == 0, (
            f"--pass-k should be accepted, got exit {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_eval_tier_flag_is_accepted(self):
        """Given: An inline eval file.
        When:  pytest --evals --eval-tier always_passes is passed.
        Then:  The flag is accepted and the command exits 0.
        """
        source = textwrap.dedent("""\
        import pytest

        @pytest.mark.eval(tier="always_passes")
        def eval_always_passes():
            assert True
        """)
        result = run_pytest_on(source, "--eval-tier", "always_passes")
        assert result.returncode == 0, (
            f"--eval-tier should be accepted, got exit {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )