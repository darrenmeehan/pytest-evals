"""LLM-as-judge — rubric, pairwise, tone, groundedness graders."""

from __future__ import annotations

import dataclasses
import json

# ── Results ───────────────────────────────────────────────────────────────

@dataclasses.dataclass
class RubricResult:
    """Result of a rubric-based LLM eval."""

    passed: int
    total: int
    details: list[dict[str, str | bool]]


@dataclasses.dataclass
class ToneResult:
    """Result of a tone-evaluation eval."""

    passed: int
    total: int
    details: list[dict[str, str | bool | float]]


@dataclasses.dataclass
class PairwiseResult:
    """Result of a pairwise A/B comparison."""

    preferred: str  # "A" | "B" | "tie"
    reasoning: str = ""


@dataclasses.dataclass
class GroundednessResult:
    """Result of a groundedness check."""

    supported: int
    unsupported: int
    unsupported_claims: list[str]


# ── Config ────────────────────────────────────────────────────────────────


@dataclasses.dataclass
class LLMJudgeConfig:
    """How to reach the judge model.

    The ``model`` string follows the LiteLLM provider/model convention:
      - ``gpt-4o``  (OpenAI, default)
      - ``anthropic/claude-sonnet-4-20250514``
      - ``openrouter/anthropic/claude-sonnet``
      - ``groq/llama3-70b-8192``

    LiteLLM reads API keys from standard environment variables
    (``OPENAI_API_KEY``, ``ANTHROPIC_API_KEY``, etc.)
    """

    model: str = "gpt-4o"
    temperature: float = 0.0
    max_tokens: int = 4096


# ── LiteLLM client ────────────────────────────────────────────────────


class _LiteLLMClient:
    """Thin wrapper around litellm.completion for LLM-as-judge.

    The import is lazy — ``litellm`` is only imported on the first
    call to ``generate()``, so creating the client won't fail if the
    dependency is missing.
    """

    def __init__(self, model: str, temperature: float = 0.0, max_tokens: int = 4096):
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    def generate(self, system: str, user: str) -> str:
        import litellm

        resp = litellm.completion(
            model=self._model,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""


# ── Judge ─────────────────────────────────────────────────────────────────


class LLMJudge:
    """A reusable LLM-as-judge evaluator.

    Usage inside an eval function::

        def eval_tone(llm_judge):
            result = llm_judge.rubric(
                output="...",
                criteria=["Criterion A", "Criterion B"],
            )
            assert result.passed >= 1
    """

    def __init__(self, config: LLMJudgeConfig | None = None):
        self._config = config or LLMJudgeConfig()
        self._client: _LiteLLMClient | None = None

    def _get_client(self) -> _LiteLLMClient:
        if self._client is not None:
            return self._client
        config = self._config
        self._client = _LiteLLMClient(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        return self._client

    # ── Core rubric grader ─────────────────────────────────────────────

    def rubric(
        self,
        *,
        output: str,
        criteria: list[str],
        context: str | None = None,
    ) -> RubricResult:
        """Score an output against a checklist of criteria.

        Returns pass/fail per criterion as judged by the LLM.
        """
        criteria_text = "\n".join(f"- {c}" for c in criteria)
        system = (
            "You are a strict but fair evaluator. "
            "You will be given an output and a set of criteria.\n\n"
            "For EACH criterion, respond with a JSON object with keys:\n"
            '- "criterion": the criterion text\n'
            '- "passed": true or false\n'
            '- "reason": a short justification\n\n'
            "Output ONLY valid JSON as a list of these objects. No preamble."
        )
        ctx = f"\n\nContext:\n{context}" if context else ""
        user = f"Output:\n{output}\n\nCriteria:\n{criteria_text}{ctx}\n\nEvaluate each criterion."
        raw = self._get_client().generate(system, user)
        details = self._parse_rubric(raw, criteria)
        passed = sum(1 for d in details if d["passed"])
        return RubricResult(passed=passed, total=len(details), details=details)

    # ── Tone grader ────────────────────────────────────────────────────

    def tone(
        self,
        *,
        output: str,
        dimensions: dict[str, str],
    ) -> ToneResult:
        """Evaluate the tone of an output across named dimensions.

        Each dimension key is the dimension name (e.g. "respectful"),
        each value is a description of what passing looks like.
        """
        dims_text = "\n".join(f"- {name}: {desc}" for name, desc in dimensions.items())
        system = (
            "You are a communication-style evaluator. "
            "Analyze the tone of the given output across each dimension.\n\n"
            "For EACH dimension, respond with a JSON object with keys:\n"
            '- "dimension": the dimension name\n'
            '- "passed": true or false\n'
            '- "score": a float from 0.0 to 1.0\n'
            '- "reason": a short justification\n\n'
            "Output ONLY valid JSON as a list of these objects. No preamble."
        )
        user = f"Output:\n{output}\n\nTone Dimensions:\n{dims_text}\n\nEvaluate each dimension."
        raw = self._get_client().generate(system, user)
        details = self._parse_tone(raw, dimensions)
        passed = sum(1 for d in details if d["passed"])
        return ToneResult(passed=passed, total=len(details), details=details)

    # ── Pairwise comparator ────────────────────────────────────────────

    def pairwise(
        self,
        *,
        output_a: str,
        output_b: str,
        criterion: str,
    ) -> PairwiseResult:
        """Compare two outputs and decide which is better by a criterion."""
        system = (
            f"You are a comparison evaluator.\n\n"
            f"Given two outputs (A and B), decide which one better satisfies:\n"
            f"{criterion}\n\n"
            f"Respond with a JSON object with keys:\n"
            f'- "preferred": "A" or "B" or "tie"\n'
            f'- "reasoning": one sentence why\n\n'
            f"Output ONLY valid JSON. No preamble."
        )
        user = f"Output A:\n{output_a}\n\nOutput B:\n{output_b}\n\nWhich is better?"
        raw = self._get_client().generate(system, user)
        try:
            data = json.loads(raw)
            return PairwiseResult(preferred=data.get("preferred", "tie"), reasoning=data.get("reasoning", ""))
        except json.JSONDecodeError:  # .get() used below, KeyError cannot fire
            return PairwiseResult(preferred="tie", reasoning="parse error")

    # ── Groundedness checker ───────────────────────────────────────────

    def groundedness(
        self,
        *,
        output: str,
        source: str,
    ) -> GroundednessResult:
        """Check whether claims in output are supported by the source text."""
        system = (
            "You are a fact-checking evaluator.\n\n"
            "Compare the OUTPUT against the SOURCE. "
            "List any claims in the OUTPUT that are NOT supported by the SOURCE.\n\n"
            "Respond with a JSON object with keys:\n"
            '- "supported": number of supported claims\n'
            '- "unsupported": number of unsupported claims\n'
            '- "unsupported_claims": list of claim strings\n\n'
            "If all claims are supported, unsupported_claims is an empty list.\n"
            "Output ONLY valid JSON. No preamble."
        )
        user = f"SOURCE:\n{source}\n\nOUTPUT:\n{output}\n\nList unsupported claims."
        raw = self._get_client().generate(system, user)
        try:
            data = json.loads(raw)
            return GroundednessResult(
                supported=data.get("supported", 0),
                unsupported=data.get("unsupported", 0),
                unsupported_claims=data.get("unsupported_claims", []),
            )
        except json.JSONDecodeError:  # .get() used below, KeyError cannot fire
            return GroundednessResult(supported=0, unsupported=1, unsupported_claims=["parse error"])

    # ── Parsers ────────────────────────────────────────────────────────

    def _parse_rubric(self, raw: str, criteria: list[str]) -> list[dict]:
        """Parse rubric JSON; return list of dicts with 'passed' key, else all-fail."""
        parsed = self._parse_passed_list(raw)
        if parsed is not None:
            return parsed
        return [{"criterion": c, "passed": False, "reason": "parse error"} for c in criteria]

    def _parse_tone(self, raw: str, dimensions: dict[str, str]) -> list[dict]:
        """Parse tone JSON; return list of dicts with 'passed' key, else all-fail."""
        parsed = self._parse_passed_list(raw)
        if parsed is not None:
            return parsed
        return [
            {"dimension": name, "passed": False, "score": 0.0, "reason": "parse error"}
            for name in dimensions
        ]

    def _parse_passed_list(self, raw: str) -> list[dict] | None:
        """Parse JSON as a non-empty list of dicts each having a 'passed' key.

        Returns None when the raw text is not that shape, so callers can
        fall back to all-fail. Guards against valid JSON with missing keys
        (which would otherwise crash with KeyError in the caller).
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if (
            isinstance(data, list)
            and data
            and all(isinstance(d, dict) and "passed" in d for d in data)
        ):
            return data
        return None