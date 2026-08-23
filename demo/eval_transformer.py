"""Demo evals for a JSON transformer."""

import json
import subprocess
import pytest


# ── Code grader — deterministic check ──────────────────────────────────


@pytest.mark.eval(tier="always_passes", runs=5)
def eval_output_is_valid_json():
    """Transformed output must parse as JSON (runs 5 times for pass@k)"""
    with open("input.json") as f_in, open("output.json", "w") as f_out:
        subprocess.run(
            ["python3", "transform.py"],
            stdin=f_in,
            stdout=f_out,
            check=True,
        )
    with open("output.json") as f:
        data = json.load(f)
    assert isinstance(data, dict), "Output must be a JSON object"


@pytest.mark.eval(tier="always_passes")
def eval_output_has_required_fields():
    """Output must contain name, age, email fields"""
    with open("output.json") as f:
        data = json.load(f)
    for field in ("name", "age", "email"):
        assert field in data, f"Missing field: {field}"


# ── LLM-as-judge — subjective quality checks ───────────────────────────


@pytest.mark.eval(tier="usually_passes", runs=3)
def eval_tone_is_professional(llm_judge):
    """Customer-facing response must not sound rude or dismissive"""
    with open("output.txt") as f:
        output = f.read()
    result = llm_judge.tone(
        output=output,
        dimensions={
            "respectful": "Does not blame the customer",
            "professional": "Uses appropriate language, no slang",
            "helpful": "Offers a solution or next step",
            "patient": "Does not sound frustrated or rushed",
        },
    )
    assert result.passed >= 3, f"Only {result.passed}/{result.total} tone dimensions passed"


@pytest.mark.eval(tier="usually_passes")
def eval_explanation_is_clear(llm_judge):
    """The explanation should be understandable by a non-technical user"""
    with open("output.txt") as f:
        output = f.read()
    result = llm_judge.rubric(
        output=output,
        criteria=[
            "Avoids jargon without explanation",
            "Uses short sentences",
            "Step-by-step if describing a process",
            "States the outcome clearly",
        ],
    )
    assert result.passed >= 3, f"Clarity: {result.passed}/{result.total}"


@pytest.mark.eval(tier="experimental")
def eval_draft_vs_final_is_better(llm_judge):
    """Final draft should be preferred over the initial draft"""
    with open("draft_v1.txt") as f_a, open("draft_v2.txt") as f_b:
        draft_a = f_a.read()
        draft_b = f_b.read()
    result = llm_judge.pairwise(
        output_a=draft_a,
        output_b=draft_b,
        criterion="Which version is more complete and accurate?",
    )
    assert result.preferred == "B", f"Expected B, got {result.preferred}"


@pytest.mark.eval(tier="always_passes")
def eval_no_hallucinations(llm_judge):
    """Claims in the output must be grounded in the source document"""
    with open("output.txt") as f_o, open("source.txt") as f_s:
        output = f_o.read()
        source = f_s.read()
    result = llm_judge.groundedness(
        output=output,
        source=source,
    )
    assert len(result.unsupported_claims) == 0, f"Unsupported claims: {result.unsupported_claims}"


# ── Using fixtures ─────────────────────────────────────────────────────


@pytest.mark.eval(tier="experimental")
def eval_runs_in_clean_env(temp_env, run_context):
    """Eval should produce output in a clean temp directory"""
    output_file = temp_env / "output.json"
    output_file.write_text('{"status": "ok"}')
    data = json.loads(output_file.read_text())
    assert data["status"] == "ok"
    print(f"  run_context: {run_context}")  # visible in verbose mode