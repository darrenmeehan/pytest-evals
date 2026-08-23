"""Shared test helpers for pytest-evals tests."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


def _eval_pytest_args() -> list[str]:
    """Extra pytest args to ensure eval_* discovery works in the subprocess.

    We use ``-o`` CLI overrides because ``config.inicfg`` (the only other
    way to add patterns from a plugin hook) is deprecated and unreliable.
    """
    return [
        "-o", "python_files=eval_*.py test_*.py",
        "-o", "python_functions=eval_* test_*",
    ]


def run_pytest_on(
    source: str,
    *args: str,
    filename: str = "eval_test.py",
) -> subprocess.CompletedProcess:
    """Run pytest with --evals on inline Python source.

    Args:
        source: Python source code (dedented automatically).
        *args: Additional pytest CLI arguments.
        filename: Name of the temporary file (default: eval_test.py).

    Returns:
        CompletedProcess with stdout, stderr, returncode.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="pytest_evals_test_"))
    tmp_file = tmp_dir / filename
    tmp_file.write_text(textwrap.dedent(source))
    try:
        cmd = [
            sys.executable, "-m", "pytest", str(tmp_file), "-v", "--evals",
            *_eval_pytest_args(),
            *args,
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=tmp_dir,
        )
        return result
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def count_tests_in(source: str, *args: str, filename: str = "eval_test.py") -> int:
    """Return the number of tests collected for the given source.

    Uses ``--collect-only`` to avoid running any tests.
    Counts lines containing ``::`` (test nodes) in the output rather than
    relying on the pre-filter collection header which may overcount.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="pytest_evals_count_"))
    tmp_file = tmp_dir / filename
    tmp_file.write_text(textwrap.dedent(source))
    try:
        cmd = [
            sys.executable, "-m", "pytest", str(tmp_file), "--collect-only", "-q", "--evals",
            *_eval_pytest_args(),
            *args,
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=tmp_dir,
        )
        # Count lines with :: (test function nodes) — these are the
        # post-filter collection, not the pre-filter header count.
        return sum(1 for line in result.stdout.splitlines() if "::" in line)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)