import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hallucination.run import run_evaluation

# Questions that share literally zero keyword overlap with the seed corpus --
# these are the reliable floor: no ambiguity, no incidental term collision.
_CLEARLY_UNRELATED_QUESTIONS = {
    "What are the tax filing deadlines this year?",
    "How do I train for a marathon?",
    "What is the capital of France?",
}


def test_at_least_10_questions_tested() -> None:
    report = run_evaluation()
    assert report["num_questions"] >= 10


def test_llm_is_never_called_when_a_case_is_scored_insufficient() -> None:
    """The core Section 43 guarantee always holds regardless of retrieval
    quality: whenever the response IS the insufficient-evidence text,
    the LLM was categorically never invoked to produce it."""
    report = run_evaluation()
    for case in report["cases"]:
        if case["produced_insufficient_evidence"]:
            assert not case["llm_was_called"]


def test_clearly_unrelated_questions_are_correctly_flagged() -> None:
    """Reliable floor: questions with zero keyword overlap with the corpus
    must trigger the insufficient-evidence response."""
    report = run_evaluation()
    for case in report["cases"]:
        if case["question"] in _CLEARLY_UNRELATED_QUESTIONS:
            assert case["passed"], case["question"]


def test_all_out_of_corpus_cases_abstain_before_generation() -> None:
    """Enforce the complete benchmark, including incidental keyword matches.

    Passing this small set does not prove semantic sufficiency for every query;
    backend tests separately ensure supported queries still reach generation.
    """
    report = run_evaluation()
    assert report["all_passed"], [case for case in report["cases"] if not case["passed"]]
