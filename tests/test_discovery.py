"""Tests for eval_* file naming and function naming conventions.

The plugin registers ``python_files`` and ``python_functions`` patterns
so that ``eval_*.py`` files and ``def eval_*()`` functions are discovered
automatically, alongside the standard ``test_*`` patterns.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

from conftest import count_tests_in


class TestEvalFileNaming:
    """eval_*.py files are discovered."""

    def test_eval_prefix_file_is_discovered(self):
        """Given: A file named eval_*.py.
        When:  pytest collects tests.
        Then:  The eval functions inside are discovered.
        """
        source = """
        import pytest

        @pytest.mark.eval
        def eval_works():
            assert True
        """
        collected = count_tests_in(source, filename="eval_myfile.py")
        assert collected >= 1, f"eval_*.py file not discovered, got {collected}"

    def test_test_prefix_file_still_works(self):
        """Given: A file named test_*.py.
        When:  pytest collects tests.
        Then:  Both test_* and eval_* functions are discovered.
        """
        source = """
        import pytest

        def test_regular():
            assert True

        @pytest.mark.eval
        def eval_also():
            assert True
        """
        collected = count_tests_in(source, filename="test_myfile.py")
        assert collected >= 2, f"test_*.py should collect both, got {collected}"

    def test_neither_prefix_file_is_not_discovered(self):
        """Given: A file with neither eval_ nor test_ prefix.
        When:  pytest collects from a directory.
        Then:  No tests are collected (python_files filters it out).
        """
        import shutil
        import tempfile

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            (tmp_dir / "other_file.py").write_text(textwrap.dedent("""\
            import pytest
            @pytest.mark.eval
            def eval_works():
                assert True
            """))
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(tmp_dir), "--collect-only", "-q", "--evals",
                 "-o", "python_files=eval_*.py",
                 "-o", "python_functions=eval_* test_*"],
                capture_output=True, text=True, timeout=15, cwd=tmp_dir,
            )
            assert "no tests collected" in result.stdout, (
                f"Expected no tests, got:\n{result.stdout}"
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class TestEvalFunctionNaming:
    """eval_* functions are discovered inside test/eval files."""

    def test_eval_prefix_function_is_discovered(self):
        source = """
        import pytest

        @pytest.mark.eval
        def eval_my_function():
            assert True
        """
        collected = count_tests_in(source)
        assert collected >= 1, f"eval_ function not discovered, got {collected}"

    def test_test_prefix_function_is_discovered(self):
        source = """
        def test_my_function():
            assert True
        """
        collected = count_tests_in(source)
        assert collected >= 1, f"test_ function not discovered, got {collected}"

    def test_eval_functions_work_without_marker(self):
        """An eval_ function without @pytest.mark.eval is still discovered
        and runs as a regular test.
        """
        source = """
        def eval_unmarked():
            assert True
        """
        collected = count_tests_in(source)
        assert collected >= 1, f"Unmarked eval_ function not discovered, got {collected}"


class TestMixedFileAndFunction:
    """Combinations of file and function naming patterns."""

    def test_eval_file_with_mixed_functions(self):
        """eval_*.py can contain both eval_* and test_* functions."""
        source = """
        import pytest

        @pytest.mark.eval
        def eval_my():
            assert True

        def test_my():
            assert True
        """
        collected = count_tests_in(source, filename="eval_combined.py")
        assert collected >= 2, f"Mixed functions in eval file, got {collected}"

    def test_test_file_with_eval_functions(self):
        """test_*.py can contain eval_* functions."""
        source = """
        import pytest

        @pytest.mark.eval
        def eval_inside_test():
            assert True

        def test_regular():
            assert True
        """
        collected = count_tests_in(source, filename="test_myfile.py")
        assert collected >= 2, f"eval_ inside test file, got {collected}"

    def test_multiple_eval_files_discovered(self):
        """Multiple eval_*.py files in the same directory are all discovered."""
        # We can't test this easily with count_tests_in since it only writes
        # one file. So we test with a directory-based approach.
        import shutil
        import tempfile

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            (tmp_dir / "eval_a.py").write_text(textwrap.dedent("""\
            import pytest
            @pytest.mark.eval
            def eval_a(): assert True
            """))
            (tmp_dir / "eval_b.py").write_text(textwrap.dedent("""\
            import pytest
            @pytest.mark.eval
            def eval_b(): assert True
            """))
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(tmp_dir), "--collect-only", "-q", "--evals",
                 "-o", "python_files=eval_*.py test_*.py",
                 "-o", "python_functions=eval_* test_*"],
                capture_output=True, text=True, timeout=15, cwd=tmp_dir,
            )
            assert "eval_a" in result.stdout, "eval_a not discovered"
            assert "eval_b" in result.stdout, "eval_b not discovered"
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)