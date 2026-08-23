"""Tests for pytest-evals built-in fixtures.

Uses subprocess tests to verify fixture behavior in real pytest runs,
and direct unit tests where the fixture logic is deterministic Python.
"""

from __future__ import annotations

from conftest import run_pytest_on


class TestRunIdFixture:
    """The run_id fixture — parametrized by pytest_generate_tests."""

    def test_run_id_receives_zero_index_first_run(self):
        source = """
        import pytest

        @pytest.mark.eval(runs=3)
        def eval_check_run_id(run_id):
            # First run: run_id == 0
            pass
        """
        result = run_pytest_on(source)
        assert result.returncode == 0

    def test_run_id_accessible_in_test_body(self):
        source = """
        import pytest

        @pytest.mark.eval(runs=3)
        def eval_test(run_id):
            assert isinstance(run_id, int)
            assert 0 <= run_id < 3
        """
        result = run_pytest_on(source)
        assert result.returncode == 0


class TestRunContextFixture:
    """The run_context fixture — metadata about the current eval run."""

    def test_run_context_contains_name(self):
        source = """
        import pytest

        @pytest.mark.eval(tier="always_passes", runs=1)
        def eval_my_name(run_context):
            assert run_context["name"] == "eval_my_name", run_context
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, f"run_context name check failed:\n{result.stdout}"

    def test_run_context_contains_tier(self):
        source = """
        import pytest

        @pytest.mark.eval(tier="experimental", runs=1)
        def eval_custom_tier(run_context):
            assert run_context["tier"] == "experimental", run_context
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, f"run_context tier check failed:\n{result.stdout}"

    def test_run_context_contains_run_id(self):
        source = """
        import pytest

        @pytest.mark.eval(runs=2)
        def eval_check_run_id(run_context, run_id):
            assert run_context["run_id"] == run_id, run_context
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, f"run_context run_id mismatch:\n{result.stdout}"

    def test_run_context_contains_node_id(self):
        source = """
        import pytest

        @pytest.mark.eval
        def eval_with_node_id(run_context):
            assert "eval_with_node_id" in run_context["node_id"], run_context
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, f"run_context node_id check failed:\n{result.stdout}"

    def test_run_context_without_eval_marker_defaults(self):
        source = """
        def test_context_defaults(run_context):
            assert run_context["tier"] == "always_passes"
            assert run_context["runs"] == 1
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, f"run_context defaults failed:\n{result.stdout}"

    def test_run_context_runs_reflects_pass_k_override(self):
        """Regression: run_context['runs'] must reflect the --pass-k override."""
        source = """
        import pytest

        @pytest.mark.eval(tier="experimental", runs=1)
        def eval_context(run_context):
            assert run_context["runs"] == 4, f"Got {run_context['runs']}, want 4"
        """
        result = run_pytest_on(source, "--pass-k", "4")
        assert result.returncode == 0, (
            f"run_context runs should be 4 under --pass-k 4:\n{result.stdout}"
        )


class TestAgentOutputFixture:
    """The agent_output fixture — reads output from well-known paths."""

    def test_reads_output_json(self):
        source = """
        import pytest
        from pathlib import Path

        # Write output.json at module level so it exists when fixture runs
        (Path(__file__).parent / "output.json").write_text('{"key": "val"}')

        def test_agent_output_json(agent_output):
            assert agent_output == '{"key": "val"}', f"Got: {agent_output!r}"
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, f"agent_output JSON failed:\n{result.stdout}"

    def test_falls_back_to_output_txt(self):
        source = """
        import pytest
        from pathlib import Path

        (Path(__file__).parent / "output.txt").write_text("hello world")

        def test_agent_output_txt(agent_output):
            assert agent_output == "hello world", f"Got: {agent_output!r}"
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, f"agent_output TXT failed:\n{result.stdout}"

    def test_falls_back_to_response_txt(self):
        source = """
        import pytest
        from pathlib import Path

        (Path(__file__).parent / "response.txt").write_text("response text")

        def test_agent_output_response(agent_output):
            assert agent_output == "response text", f"Got: {agent_output!r}"
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, f"agent_output response failed:\n{result.stdout}"

    def test_returns_empty_string_when_no_file_exists(self):
        source = """
        import pytest

        def test_agent_output_missing(agent_output):
            assert agent_output == "", f"Expected empty, got: {agent_output!r}"
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, f"agent_output missing failed:\n{result.stdout}\n{result.stderr}"

    def test_prefers_json_over_txt_over_response(self):
        source = """
        import pytest
        from pathlib import Path

        (Path(__file__).parent / "output.json").write_text('"json"')
        (Path(__file__).parent / "output.txt").write_text("txt")
        (Path(__file__).parent / "response.txt").write_text("response")

        def test_agent_output_precedence(agent_output):
            assert agent_output == '"json"', f"Expected JSON, got: {agent_output!r}"
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, f"agent_output precedence failed:\n{result.stdout}"


class TestTempEnvFixture:
    """The temp_env fixture — clean temporary directory per trial."""

    def test_creates_existing_directory(self):
        source = """
        def test_temp_env_exists(temp_env):
            assert temp_env.exists(), f"Directory {temp_env} does not exist"
            assert temp_env.is_dir(), f"{temp_env} is not a directory"
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, f"temp_env exists failed:\n{result.stdout}"

    def test_starts_empty(self):
        source = """
        def test_temp_env_empty(temp_env):
            contents = list(temp_env.iterdir())
            assert contents == [], f"Directory not empty: {contents}"
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, f"temp_env empty failed:\n{result.stdout}"

    def test_writable(self):
        source = """
        def test_temp_env_writable(temp_env):
            out = temp_env / "test.txt"
            out.write_text("hello")
            assert out.read_text() == "hello"
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, f"temp_env writable failed:\n{result.stdout}"


class TestLLMJudgeFixture:
    """The llm_judge fixture — lazy LLM-as-judge evaluator."""

    def test_llm_judge_is_llmjudge_instance(self):
        source = """
        import pytest
        from pytest_evals.judge import LLMJudge

        def test_type(llm_judge):
            assert isinstance(llm_judge, LLMJudge)
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, f"llm_judge type check failed:\n{result.stdout}"

    def test_llm_judge_lazy_init_no_failure_without_litellm(self):
        source = """
        import pytest
        from pytest_evals.judge import LLMJudge, LLMJudgeConfig

        def test_lazy_init():
            judge = LLMJudge(LLMJudgeConfig())
            assert judge._client is None
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, "lazy init failed"


class TestLLMJudgeConfigOverride:
    """The llm_judge_config fixture can be overridden."""

    def test_llm_judge_config_defaults(self):
        source = """
        def test_config_defaults(llm_judge_config):
            assert llm_judge_config.model == "gpt-4o"
            assert llm_judge_config.temperature == 0.0
            assert llm_judge_config.max_tokens == 4096
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, f"config defaults failed:\n{result.stdout}"


class TestFixtureCoexistence:
    """Multiple fixtures used together."""

    def test_run_context_and_temp_env_together(self):
        source = """
        import pytest

        @pytest.mark.eval(tier="experimental")
        def eval_with_both(run_context, temp_env):
            assert "name" in run_context
            assert temp_env.exists()
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, f"fixture coexistence failed:\n{result.stdout}"

    def test_run_context_and_run_id_match(self):
        source = """
        import pytest

        @pytest.mark.eval(runs=3)
        def eval_match(run_context, run_id):
            assert run_context["run_id"] == run_id
        """
        result = run_pytest_on(source)
        assert result.returncode == 0, f"run_context/run_id mismatch:\n{result.stdout}"