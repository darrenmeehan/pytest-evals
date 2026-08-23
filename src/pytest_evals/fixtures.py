"""Built-in fixtures for pytest-evals."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

from pytest_evals.judge import LLMJudge, LLMJudgeConfig

# ── run_id (parametrized by pytest_generate_tests) ────────────────────────


@pytest.fixture
def run_id(request: pytest.FixtureRequest) -> int:
    """The pass@k run index (0-based). Parametrized by ``pytest_generate_tests``."""
    return request.param  # type: ignore[attr-defined]


# ── llm_judge ─────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def llm_judge_config() -> LLMJudgeConfig:
    """Override this fixture to configure the LLM judge."""
    return LLMJudgeConfig(
        model=os.environ.get("EVAL_JUDGE_MODEL", "gpt-4o"),
        provider=os.environ.get("EVAL_JUDGE_PROVIDER", "openai"),
        temperature=float(os.environ.get("EVAL_JUDGE_TEMPERATURE", "0.0")),
    )


@pytest.fixture
def llm_judge(llm_judge_config: LLMJudgeConfig) -> LLMJudge:
    """An LLM-as-judge evaluator for rubric, tone, pairwise, and groundedness checks.

    The client is created lazily; the fixture itself won't fail if deps are missing.
    Install extras: ``pip install pytest-evals[llm]``

    Usage::

        def eval_tone(llm_judge):
            with open("response.txt") as f:
                output = f.read()
            result = llm_judge.rubric(
                output=output,
                criteria=["Criterion A", "Criterion B"],
            )
            assert result.passed >= 1
    """
    return LLMJudge(config=llm_judge_config)


# ── run_context ────────────────────────────────────────────────────────────


@pytest.fixture
def run_context(request: pytest.FixtureRequest, run_id: int) -> dict[str, Any]:
    """Metadata about the current eval run.

    Returns a dict with keys:
      - name: the eval function name
      - tier: the tier string (experimental / usually_passes / always_passes)
      - run_id: the pass@k run index (0-based)
      - runs: total pass@k runs configured
      - node_id: the pytest nodeid
    """
    marker = request.node.get_closest_marker("eval")
    tier = marker.kwargs.get("tier", "always_passes") if marker else "always_passes"
    # Effective runs: prefer the value stored by pytest_generate_tests
    # (which reflects --pass-k overrides and clamping), else the marker.
    effective = getattr(request.node, "_evals_effective_runs", None)
    if effective is None:
        effective = marker.kwargs.get("runs", 1) if marker else 1
    return {
        "name": request.node.originalname or request.node.name,
        "tier": str(tier),
        "run_id": run_id,
        "runs": int(effective),
        "node_id": request.node.nodeid,
    }


# ── agent_output ───────────────────────────────────────────────────────────


@pytest.fixture
def agent_output(request: pytest.FixtureRequest) -> str:
    """Read the output being evaluated from a well-known path.

    Looks for ``output.json``, then ``output.txt``, then ``response.txt``
    relative to the test directory. Override this fixture for custom logic.
    """
    for name in ("output.json", "output.txt", "response.txt"):
        path = Path(request.path).parent / name
        if path.exists():
            return path.read_text(encoding="utf-8")
    return ""


# ── temp_env ───────────────────────────────────────────────────────────────


@pytest.fixture
def temp_env():
    """A clean temporary directory per trial for sandboxed eval execution.

    Yields the Path. The directory is destroyed after the test.
    """
    tmp = Path(tempfile.mkdtemp(prefix="pytest_evals_"))
    try:
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)