"""Tests for pass@k parametrization, run_id, --pass-k, and --eval-tier.

The plugin's ``pytest_generate_tests`` hook parametrizes the ``run_id``
fixture over ``range(runs)`` for any ``@pytest.mark.eval(runs=N)`` function.
The ``--pass-k`` CLI flag overrides the marker's runs value.
The ``--eval-tier`` CLI flag filters evals by tier.
"""

from __future__ import annotations

from conftest import run_pytest_on, count_tests_in


class TestPassKParametrization:
    """pass@k parametrization via @pytest.mark.eval(runs=N)."""

    def test_runs_3_produces_3_tests(self):
        """Given: An eval with @pytest.mark.eval(runs=3) and a run_id parameter.
        When:  Tests are collected.
        Then:  3 test variants are collected.
        """
        source = """
        import pytest

        @pytest.mark.eval(runs=3)
        def eval_three_times(run_id):
            assert True
        """
        collected = count_tests_in(source)
        assert collected == 3, f"Expected 3 tests, got {collected}"

    def test_runs_1_produces_1_test(self):
        """Given: An eval with @pytest.mark.eval(runs=1).
        When:  Tests are collected.
        Then:  1 test variant is collected.
        """
        source = """
        import pytest

        @pytest.mark.eval(runs=1)
        def eval_one_time(run_id):
            assert True
        """
        collected = count_tests_in(source)
        assert collected == 1, f"Expected 1 test, got {collected}"

    def test_default_runs_produces_1_test(self):
        """Given: An eval with @pytest.mark.eval (no runs argument).
        When:  Tests are collected.
        Then:  1 test variant is collected.
        """
        source = """
        import pytest

        @pytest.mark.eval
        def eval_default(run_id):
            assert True
        """
        collected = count_tests_in(source)
        assert collected == 1, f"Expected 1 test, got {collected}"

    def test_run_id_values_are_zero_based(self):
        """Given: An eval with runs=3.
        When:  The eval runs and checks run_id.
        Then:  run_id values are 0, 1, 2 (all pass).
        """
        source = """
        import pytest

        @pytest.mark.eval(runs=3)
        def eval_check_run_id(run_id):
            assert run_id in (0, 1, 2), f"run_id={run_id} out of range"
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, f"run_id check failed:\n{result.stdout}\n{result.stderr}"

    def test_run_id_without_eval_marker_returns_single_0(self):
        """Given: A non-eval test function that requests run_id.
        When:  Tests are collected.
        Then:  Only 1 test variant is collected with run_id=0.
        """
        source = """
        def test_plain_run_id(run_id):
            assert run_id == 0
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, f"Plain run_id test failed:\n{result.stdout}\n{result.stderr}"

    def test_non_eval_function_without_run_id_still_works(self):
        """Given: A regular test function with no run_id parameter.
        When:  Tests are collected.
        Then:  It still works (no parametrization applied).
        """
        source = """
        def test_regular():
            assert True
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, f"Regular test failed:\n{result.stdout}\n{result.stderr}"


class TestPassKCLIOverride:
    """--pass-k CLI flag overrides marker's runs value."""

    def test_pass_k_overrides_marker_runs(self):
        """Given: An eval with runs=1.
        When:  pytest --pass-k 5 is passed.
        Then:  5 tests are collected (override takes effect).
        """
        source = """
        import pytest

        @pytest.mark.eval(runs=1)
        def eval_override(run_id):
            assert True
        """
        collected = count_tests_in(source, "--pass-k", "5")
        assert collected == 5, f"Expected 5 tests with --pass-k 5, got {collected}"

    def test_pass_k_only_applies_to_eval_marker(self):
        """Given: A non-eval test with run_id.
        When:  pytest --pass-k 5 is passed.
        Then:  Only 1 test is collected (non-eval always gets 1).
        """
        source = """
        def test_not_an_eval(run_id):
            assert run_id == 0
        """
        collected = count_tests_in(source, "--pass-k", "5")
        assert collected == 1, f"Expected 1 test (non-eval), got {collected}"

    def test_pass_k_without_run_id_param_ignored(self):
        """Given: An eval WITHOUT run_id parameter.
        When:  pytest --pass-k 5 is passed.
        Then:  Only 1 test is collected (no run_id means no parametrization).
        """
        source = """
        import pytest

        @pytest.mark.eval(runs=1)
        def eval_no_run_id():
            assert True
        """
        collected = count_tests_in(source, "--pass-k", "5")
        assert collected == 1, f"Expected 1 test (no run_id param), got {collected}"


class TestEvalTierFilter:
    """--eval-tier CLI flag filters evals by tier."""

    def test_filter_keeps_matching_tier(self):
        """Given: Evals with different tiers.
        When:  pytest --eval-tier always_passes.
        Then:  Only always_passes evals are collected.
        """
        source = """
        import pytest

        @pytest.mark.eval(tier="always_passes")
        def eval_always():
            assert True

        @pytest.mark.eval(tier="experimental")
        def eval_experimental():
            assert True
        """
        collected = count_tests_in(source, "--eval-tier", "always_passes")
        assert collected == 1, f"Expected 1 always_passes eval, got {collected}"

    def test_filter_keeps_multiple_matching_tiers(self):
        """Given: 3 evals of the same tier.
        When:  pytest --eval-tier usually_passes.
        Then:  All 3 are collected.
        """
        source = """
        import pytest

        @pytest.mark.eval(tier="usually_passes")
        def eval_a():
            assert True

        @pytest.mark.eval(tier="usually_passes")
        def eval_b():
            assert True

        @pytest.mark.eval(tier="usually_passes")
        def eval_c():
            assert True
        """
        collected = count_tests_in(source, "--eval-tier", "usually_passes")
        assert collected == 3, f"Expected 3 usually_passes evals, got {collected}"

    def test_filter_excludes_non_matching_tier(self):
        """Given: always_passes eval.
        When:  pytest --eval-tier experimental.
        Then:  0 tests collected.
        """
        source = """
        import pytest

        @pytest.mark.eval(tier="always_passes")
        def eval_always():
            assert True
        """
        collected = count_tests_in(source, "--eval-tier", "experimental")
        assert collected == 0, f"Expected 0 tests, got {collected}"

    def test_filter_does_not_affect_non_eval_tests(self):
        """Given: A mix of evals and regular tests.
        When:  pytest --eval-tier always_passes.
        Then:  Regular tests are still collected.
        """
        source = """
        import pytest

        @pytest.mark.eval(tier="always_passes")
        def eval_always():
            assert True

        def test_regular():
            assert True
        """
        collected = count_tests_in(source, "--eval-tier", "always_passes")
        # Regular tests always pass through the filter
        assert collected == 2, f"Expected 2 (1 eval + 1 regular), got {collected}"

    def test_no_filter_collects_all(self):
        """Given: Evals of different tiers.
        When:  pytest without --eval-tier.
        Then:  All evals are collected.
        """
        source = """
        import pytest

        @pytest.mark.eval(tier="always_passes")
        def eval_always():
            assert True

        @pytest.mark.eval(tier="experimental")
        def eval_experimental():
            assert True
        """
        collected = count_tests_in(source)
        assert collected == 2, f"Expected 2 evals without filter, got {collected}"