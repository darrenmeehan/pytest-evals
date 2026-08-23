# pytest-evals

Eval-Driven Development for pytest: pass@k, tiers, and LLM-as-judge.

## What is this?

A pytest plugin with built-in support for evals — tests for LLM and agent
output. Same pytest you know, adapted for probabilistic, non-deterministic
systems.

## Install

```bash
pip install pytest-evals
```

For LLM-as-judge graders:

```bash
pip install "pytest-evals[llm]"
```

## Quick start

Write an eval file using the `eval_*.py` naming convention:

```python
# eval_transformer.py
import json
import pytest

@pytest.mark.eval(tier="always_passes", runs=5)
def eval_output_is_valid_json():
    """Output must parse as valid JSON"""
    with open("output.json") as f:
        data = json.load(f)
    assert isinstance(data, dict)

@pytest.mark.eval(tier="usually_passes", runs=3)
def eval_tone_is_professional(llm_judge):
    """Response must sound professional"""
    with open("response.txt") as f:
        response = f.read()
    result = llm_judge.tone(
        output=response,
        dimensions={
            "respectful": "Does not blame the customer",
            "professional": "Uses appropriate language",
        },
    )
    assert result.passed >= 1
```

Run:

```bash
pytest --evals
```

## pass@k

The `runs=N` marker runs each eval N times automatically. The reporter
prints a summary table:

```
============================= Eval pass@k ==============================
  ✅ eval_output_is_valid_json  [always_passes]  5/5
  ⚠️ eval_tone_is_professional   [usually_passes]  2/3  (1 flake)
```

Override with CLI:

```bash
pytest --evals --pass-k 10   # run all evals 10 times
```

## Tiers

| Tier | Behavior |
|------|----------|
| `experimental` | Log only (does not block) |
| `usually_passes` | Warns on failure; blocks only when paired with `always_passes` |
| `always_passes` | Any failure -> non-zero exit |

Filter by tier:

```bash
pytest --evals --eval-tier always_passes
```

## Graders

| Kind | Marker `kind=` | How it works |
|------|----------------|--------------|
| Code | `kind="code"` (default) | Python `assert` — deterministic |
| LLM rubric | `kind="llm"` | LLM judges output against criteria checklist |
| Tone | `kind="llm"` | LLM evaluates communication style dimensions |
| Pairwise | `kind="llm"` | LLM compares A vs B |
| Groundedness | `kind="llm"` | LLM checks claims against source text |

## Fixtures

| Fixture | What it gives you |
|---------|-------------------|
| `llm_judge` | LLM-as-judge: `.rubric()`, `.tone()`, `.pairwise()`, `.groundedness()` |
| `run_context` | Eval metadata: name, tier, run_id, runs |
| `run_id` | The pass@k run index (0-based) |
| `agent_output` | Output from `output.json` / `output.txt` / `response.txt` |
| `temp_env` | Clean temp directory per trial |
| `benchmark` | Baseline comparison (needs pytest-regressions) |

## LLM judge config

Set via environment variables or override the `llm_judge_config` fixture:

```bash
export EVAL_JUDGE_MODEL="gpt-4o"
export EVAL_JUDGE_PROVIDER="openai"
export EVAL_JUDGE_TEMPERATURE="0.0"
```

## Conventions

- Files: `eval_*.py` (alongside `test_*.py`)
- Functions: `def eval_*()` (alongside `def test_*()`)
- Markers: `@pytest.mark.eval(tier=..., runs=...)`

## License

MIT