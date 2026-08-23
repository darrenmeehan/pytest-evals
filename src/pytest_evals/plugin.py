"""pytest-evals: entry point for the pytest plugin."""

from __future__ import annotations

import pytest
from _pytest.config import Config
from _pytest.config.argparsing import Parser

from pytest_evals.reporter import EvalReportPlugin, normalize_tier, pytest_addoption as _reporter_addoption

# imported so fixtures are discovered
from pytest_evals.fixtures import (
    agent_output,
    llm_judge,
    llm_judge_config,
    run_context,
    run_id,
    temp_env,
)


def pytest_addoption(parser: Parser):
    _reporter_addoption(parser)


@pytest.hookimpl(trylast=True)
def pytest_configure(config: Config):
    """Register the eval marker and reporter plugin."""
    config.addinivalue_line(
        "markers",
        "eval(tier='always_passes', runs=1, kind='code'): "
        "Mark a function as an eval with tier and pass@k runs.",
    )
    if config.getoption("evals", False):
        config.pluginmanager.register(EvalReportPlugin(config), "_evals_reporter")


@pytest.hookimpl(tryfirst=True)
def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrize ``run_id`` for eval functions to implement pass@k.

    If the function has an ``@pytest.mark.eval(runs=N)`` marker and
    accepts a ``run_id`` parameter, parametrize it over ``range(N)``.
    The CLI flag ``--pass-k`` overrides the marker's ``runs`` value.
    """
    if "run_id" not in metafunc.fixturenames:
        return
    marker = metafunc.definition.get_closest_marker("eval")
    if marker is None:
        metafunc.parametrize("run_id", [0], scope="function")
        return
    runs = marker.kwargs.get("runs", 1)
    cli_runs = metafunc.config.getoption("pass_k", None)
    if cli_runs is not None:
        runs = cli_runs
    # Clamp to at least 1 so runs=0/-1 still produce one trial.
    runs = max(1, int(runs))
    # Store the effective runs on the definition so run_context can
    # report the real count even when --pass-k overrides the marker.
    metafunc.definition._evals_effective_runs = runs
    metafunc.parametrize("run_id", range(runs), scope="function")


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: Config, items: list[pytest.Item]):
    """Filter by --eval-tier if specified."""
    tier_filter = config.getoption("eval_tier_filter", None)
    if tier_filter is None:
        return

    filtered: list[pytest.Item] = []
    for item in items:
        marker = item.get_closest_marker("eval")
        if marker is None:
            filtered.append(item)
            continue
        item_tier = normalize_tier(marker.kwargs.get("tier", "always_passes"))
        if item_tier == normalize_tier(tier_filter):
            filtered.append(item)
    items[:] = filtered