"""Unit tests for the LLMJudge — rubric, tone, pairwise, groundedness.

These tests use a fake ``JudgeClient`` to avoid real LLM API calls,
making them fast, deterministic, and isolated. They verify the judge's
logic for building prompts, parsing responses, and handling edge cases.
"""

from __future__ import annotations

from pytest_evals.judge import (
    GroundednessResult,
    LLMJudge,
    LLMJudgeConfig,
    PairwiseResult,
    RubricResult,
    ToneResult,
    _LiteLLMClient,
)


class FakeJudgeClient:
    """A fake JudgeClient that returns pre-programmed responses."""

    def __init__(self, responses: list[str] | None = None):
        self.responses = list(responses or [])
        self.system = ""
        self.user = ""

    @classmethod
    def one(cls, response: str) -> FakeJudgeClient:
        return cls([response])

    def generate(self, system: str, user: str) -> str:
        self.system = system
        self.user = user
        if not self.responses:
            return "[]"
        return self.responses.pop(0)


def make_judge(client: FakeJudgeClient) -> LLMJudge:
    """Create an LLMJudge whose _get_client returns the fake."""
    judge = LLMJudge(LLMJudgeConfig(model="fake-model"))
    judge._client = client  # type: ignore[assignment]
    return judge


# ── Rubric ───────────────────────────────────────────────────────────────


class TestRubric:
    def test_rubric_returns_result(self):
        client = FakeJudgeClient.one(
            '[{"criterion": "A", "passed": true, "reason": "ok"},'
            '{"criterion": "B", "passed": false, "reason": "no"}]'
        )
        judge = make_judge(client)
        result = judge.rubric(
            output="some output",
            criteria=["A", "B"],
        )
        assert isinstance(result, RubricResult)
        assert result.passed == 1
        assert result.total == 2
        assert len(result.details) == 2

    def test_rubric_all_pass(self):
        client = FakeJudgeClient.one(
            '[{"criterion": "A", "passed": true}, {"criterion": "B", "passed": true}]'
        )
        judge = make_judge(client)
        result = judge.rubric(output="x", criteria=["A", "B"])
        assert result.passed == 2
        assert result.total == 2

    def test_rubric_builds_prompt_with_output_and_criteria(self):
        client = FakeJudgeClient.one("[]")
        judge = make_judge(client)
        judge.rubric(
            output="hello",
            criteria=["Criterion One"],
        )
        assert "hello" in client.user
        assert "Criterion One" in client.user
        assert "Evaluate each criterion" in client.user

    def test_rubric_includes_context_when_provided(self):
        client = FakeJudgeClient.one("[]")
        judge = make_judge(client)
        judge.rubric(output="x", criteria=["A"], context="some context")
        assert "some context" in client.user

    def test_rubric_omits_context_when_absent(self):
        client = FakeJudgeClient.one("[]")
        judge = make_judge(client)
        judge.rubric(output="x", criteria=["A"])
        assert "Context" not in client.user

    def test_rubric_parse_failure_falls_back_to_all_fail(self):
        client = FakeJudgeClient.one("NOT JSON at all {{")
        judge = make_judge(client)
        result = judge.rubric(output="x", criteria=["A", "B", "C"])
        # Fallback: all fail on parse error to avoid silent passes
        assert result.passed == 0, f"Expected 0 passed on parse fail, got {result.passed}"
        assert result.total == 3
        assert "parse error" in result.details[0]["reason"]

    def test_rubric_valid_json_missing_passed_key_falls_back(self):
        """Regression: valid JSON missing the 'passed' key must not crash."""
        client = FakeJudgeClient.one('[{"criterion": "A", "reason": "ok"}]')
        judge = make_judge(client)
        result = judge.rubric(output="x", criteria=["A"])
        assert result.passed == 0, f"Expected all-fail on missing key, got {result.passed}"
        assert "parse error" in result.details[0]["reason"]


# ── Tone ─────────────────────────────────────────────────────────────────


class TestTone:
    def test_tone_returns_result(self):
        client = FakeJudgeClient.one(
            '[{"dimension": "respectful", "passed": true, "score": 1.0, "reason": "ok"},'
            '{"dimension": "professional", "passed": false, "score": 0.5, "reason": "slang"}]'
        )
        judge = make_judge(client)
        result = judge.tone(
            output="foo",
            dimensions={"respectful": "desc", "professional": "desc2"},
        )
        assert isinstance(result, ToneResult)
        assert result.passed == 1
        assert result.total == 2
        assert result.details[0]["dimension"] == "respectful"

    def test_tone_all_pass(self):
        client = FakeJudgeClient.one(
            '[{"dimension": "A", "passed": true}, {"dimension": "B", "passed": true}]'
        )
        judge = make_judge(client)
        result = judge.tone(output="x", dimensions={"A": "a", "B": "b"})
        assert result.passed == 2
        assert result.total == 2

    def test_tone_builds_prompt_with_dimensions(self):
        client = FakeJudgeClient.one("[]")
        judge = make_judge(client)
        judge.tone(
            output="output",
            dimensions={"respectful": "Does not blame the customer"},
        )
        assert "respectful" in client.user
        assert "Does not blame the customer" in client.user
        assert "Tone Dimensions" in client.user

    def test_tone_parse_failure_falls_back(self):
        client = FakeJudgeClient.one("garbage")
        judge = make_judge(client)
        result = judge.tone(output="x", dimensions={"A": "a", "B": "b"})
        assert result.passed == 0, f"Expected 0 passed on parse fail, got {result.passed}"
        assert result.total == 2

    def test_tone_valid_json_missing_passed_key_falls_back(self):
        """Regression: tone dict missing 'passed' must not crash."""
        client = FakeJudgeClient.one('[{"dimension": "A", "score": 0.5}]')
        judge = make_judge(client)
        result = judge.tone(output="x", dimensions={"A": "a"})
        assert result.passed == 0, f"Expected all-fail on missing key, got {result.passed}"


# ── Pairwise ─────────────────────────────────────────────────────────────


class TestPairwise:
    def test_pairwise_returns_preferred_a(self):
        client = FakeJudgeClient.one('{"preferred": "A", "reasoning": "A is better"}')
        judge = make_judge(client)
        result = judge.pairwise(output_a="x", output_b="y", criterion="better quality")
        assert isinstance(result, PairwiseResult)
        assert result.preferred == "A"
        assert result.reasoning == "A is better"

    def test_pairwise_returns_tie_on_parse_failure(self):
        client = FakeJudgeClient.one("NOT JSON")
        judge = make_judge(client)
        result = judge.pairwise(output_a="x", output_b="y", criterion="c")
        assert result.preferred == "tie"

    def test_pairwise_builds_prompt_with_both_outputs(self):
        client = FakeJudgeClient.one('{"preferred": "B", "reasoning": "x"}')
        judge = make_judge(client)
        judge.pairwise(output_a="AAAA", output_b="BBBB", criterion="better quality")
        assert "AAAA" in client.user
        assert "BBBB" in client.user


# ── Groundedness ─────────────────────────────────────────────────────────


class TestGroundedness:
    def test_groundedness_returns_supported(self):
        client = FakeJudgeClient.one(
            '{"supported": 3, "unsupported": 0, "unsupported_claims": []}'
        )
        judge = make_judge(client)
        result = judge.groundedness(output="x", source="y")
        assert isinstance(result, GroundednessResult)
        assert result.supported == 3
        assert result.unsupported == 0
        assert result.unsupported_claims == []

    def test_groundedness_returns_unsupported(self):
        client = FakeJudgeClient.one(
            '{"supported": 1, "unsupported": 2, "unsupported_claims": ["Claim 1", "Claim 2"]}'
        )
        judge = make_judge(client)
        result = judge.groundedness(output="x", source="y")
        assert result.supported == 1
        assert result.unsupported == 2
        assert result.unsupported_claims == ["Claim 1", "Claim 2"]

    def test_groundedness_parse_failure_marks_unsupported(self):
        client = FakeJudgeClient.one("NOT JSON")
        judge = make_judge(client)
        result = judge.groundedness(output="x", source="y")
        assert result.unsupported == 1
        assert result.unsupported_claims == ["parse error"]

    def test_groundedness_builds_prompt_with_source_and_output(self):
        client = FakeJudgeClient.one('{"supported": 1, "unsupported": 0, "unsupported_claims": []}')
        judge = make_judge(client)
        judge.groundedness(output="my output", source="my source")
        assert "my output" in client.user
        assert "my source" in client.user
        assert "SOURCE" in client.user


# ── Config ───────────────────────────────────────────────────────────────


class TestLLMJudgeConfig:
    def test_default_model(self):
        config = LLMJudgeConfig()
        assert config.model == "gpt-4o"

    def test_default_temperature(self):
        config = LLMJudgeConfig()
        assert config.temperature == 0.0

    def test_default_max_tokens(self):
        config = LLMJudgeConfig()
        assert config.max_tokens == 4096

    def test_custom_model(self):
        config = LLMJudgeConfig(model="openrouter/anthropic/claude-sonnet")
        assert config.model == "openrouter/anthropic/claude-sonnet"


# ── Judge init ──────────────────────────────────────────────────────────


class TestLLMJudgeInit:
    def test_init_lazy_does_not_require_litellm(self):
        """Creating an LLMJudge should not fail — client is lazy."""
        judge = LLMJudge(LLMJudgeConfig())
        assert judge._client is None

    def test_get_client_returns_litellm_client(self):
        """_get_client should create a _LiteLLMClient on first call."""
        judge = LLMJudge(LLMJudgeConfig(model="gpt-4o"))
        client = judge._get_client()
        assert isinstance(client, _LiteLLMClient)
        # Second call returns the same instance
        assert judge._get_client() is client