"""Terminal reporter for pytest-evals: pass@k table output."""

from __future__ import annotations

from collections import defaultdict

import pytest
from _pytest.config import Config
from _pytest.config.argparsing import Parser
from _pytest.runner import CallInfo
from _pytest.terminal import TerminalReporter


def normalize_tier(tier: str | None) -> str:
    """Normalize a tier value to lowercase for consistent comparison."""
    return str(tier or "always_passes").lower()


class EvalReportPlugin:
    """Aggregates pass@k stats and prints a summary table.

    Results are keyed by nodeid (file::function) so evals with the same
    function name in different files don't merge.

    Exit-code semantics (matching the tier docs):
      - always_passes failure   -> block (non-zero exit)
      - usually_passes failure  -> warn only, does not block
      - experimental failure    -> log only, does not block
    When ONLY non-blocking evals fail, the session exits 0.
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.results: dict[str, dict[str, object]] = defaultdict(lambda: defaultdict(list))
        self._nonblocking_failed = False
        self._blocking_failed = False
        self._non_eval_failed = False

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_makereport(self, item, call: CallInfo[None]):
        passed = call.excinfo is None
        marker = item.get_closest_marker("eval")

        if marker is None:
            # Non-eval test: any phase failure (setup/teardown/call) blocks.
            if not passed:
                self._non_eval_failed = True
            return

        # Only aggregate pass@k from the call phase; setup/teardown errors
        # in an eval are recorded as failures too.
        if call.when == "call":
            tier = normalize_tier(marker.kwargs.get("tier", "always_passes"))
            # Key by nodeid minus the parametrization suffix, so pass@k runs
            # of the same eval aggregate, but same-named evals in different
            # files stay separate (e.g. eval_a.py::eval_foo vs eval_b.py::eval_foo).
            key = item.nodeid.split("[")[0]
            self.results[key]["tier"] = tier
            self.results[key].setdefault("passes", [])
            self.results[key]["passes"].append(passed)  # type: ignore[attr-defined]
            if not passed:
                if tier == "always_passes":
                    self._blocking_failed = True
                else:
                    self._nonblocking_failed = True
        elif not passed:
            # Setup/teardown failure in an eval — treat as blocking.
            self._blocking_failed = True

    @pytest.hookimpl(trylast=True)
    def pytest_terminal_summary(
        self,
        terminalreporter: TerminalReporter,
        exitstatus: int,
        config: Config,
    ):
        if not self.results:
            return
        terminalreporter.section("Eval pass@k", sep="=", bold=True)

        lines: list[str] = []
        for key in sorted(self.results):
            data = self.results[key]
            passes = data.get("passes", [])
            tier = data.get("tier", "?")
            total = len(passes)
            passed = sum(passes)  # type: ignore[arg-type]
            pct = f"{passed}/{total}"
            symbol = "✅" if passed == total else ("⚠️" if total > 0 else "❌")
            fail_str = ""
            if 0 < passed < total:
                fail_str = f"  ({total - passed} flake{'s' if total - passed != 1 else ''})"
            elif passed == 0 and total > 0:
                fail_str = "  ALL FAILED"
            lines.append(f"  {symbol} {key}  [{tier}]  {pct}{fail_str}")

        for line in lines:
            terminalreporter.write_line(line)

        if self._blocking_failed:
            terminalreporter.write_line("")
            terminalreporter.write_line("❌ ALWAYS_PASSES evals failed — blocking.", bold=True)

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session):
        """Enforce tier-based exit codes.

        pytest sets exitstatus=1 when any test fails. We downgrade it to 0
        ONLY when the failures all came from non-blocking evals. If any
        always_passes eval (or any non-eval test) failed, exit stays non-zero.
        """
        if self._blocking_failed or self._non_eval_failed:
            session.exitstatus = 1
            return
        if self._nonblocking_failed:
            # Only non-blocking evals failed -> don't block.
            session.exitstatus = 0


def pytest_addoption(parser: Parser):
    """Register eval-specific CLI flags."""
    group = parser.getgroup("evals", "Eval-Driven Development")
    group.addoption(
        "--pass-k",
        dest="pass_k",
        default=None,
        type=int,
        help="Default pass@k runs per eval (overrides marker's runs value)",
    )
    group.addoption(
        "--eval-tier",
        dest="eval_tier_filter",
        default=None,
        type=str,
        help="Only run evals of this tier (experimental, usually_passes, always_passes)",
    )
    group.addoption(
        "--evals",
        action="store_true",
        default=False,
        help="Enable eval-specific conventions (discovery, reporting)",
    )