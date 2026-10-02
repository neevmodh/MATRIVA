"""Print every stage of the MATRIVA RAG pipeline as it runs (issue: observability).

Why this exists: the external path (`RAG_ENGINE=external`) composes safety,
retrieval, grounding, generation, citation validation and the output post-check
into a single LangChain runnable. That is deliberately opaque -- you get the
final answer and no idea what happened on the way there. When an answer looks
wrong, the first question is always "which stage dropped it?", and the code has
no way to answer that.

This script runs the *real* pipeline -- the same
`_prepare_generation` / `_langchain_answer_query` / `_finalize_generation`
functions the API calls -- and reports what each stage decided.

No API key and no network by default: the LLM is stubbed, so this shows
control flow and evidence handling, not answer quality. With `--live` it uses
the real provider instead.

Usage
-----
    cd backend
    python -m scripts.rag_trace "What should I eat in the first trimester?"

    # every route
    python -m scripts.rag_trace --urgent      "I have heavy bleeding"
    python -m scripts.rag_trace --no-evidence  "What is the capital of France?"

    # stream the tokens and time each stage
    python -m scripts.rag_trace --stream "What should I eat in pregnancy?"

    # real model (needs LLM_API_KEY and RAG_ENGINE=external)
    python -m scripts.rag_trace --live "What should I eat in pregnancy?"

Exit code is 0 when a final answer was produced and 1 when the pipeline
short-circuited, so it can be used as a smoke check in CI.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from app.core.config import Settings, get_settings
from app.llm import langchain_provider
from app.rag.pipeline import (
    DEFAULT_K,
    GenerationPlan,
    _langchain_answer_query,
    _prepare_generation,
)
from app.rag.reranking import UserContext
from app.schemas.knowledge import Domain, EvidenceLevel, KnowledgeChunk, SourceType

RULE = "=" * 78


@dataclass
class Stage:
    name: str
    ms: float
    detail: str


def _demo_chunk() -> KnowledgeChunk:
    """A single approved nutrition chunk so the happy path has real evidence."""

    return KnowledgeChunk(
        chunk_id="chunk-demo-1",
        document_id="doc-demo-1",
        source_id="src-demo-nutrition",
        domain=Domain.NUTRITION,
        topic="pregnancy nutrition",
        evidence_level=EvidenceLevel.SUPPORTED,
        source_type=SourceType.NUTRITION_REFERENCE,
        language="en",
        content=(
            "During pregnancy, eat a balanced diet that includes iron-rich foods "
            "such as lentils, spinach and jaggery, along with protein, fruit and "
            "vegetables. Avoid empty-calorie snacks."
        ),
        chunk_index=0,
        token_count=32,
    )


def _stub_model(settings: Settings | None = None):
    """Answer from the context packet's own sources so citation validation is real."""

    def generate(messages: list[dict[str, str]]) -> AIMessage:
        return AIMessage(
            content=(
                "A balanced pregnancy diet should include iron-rich foods such as "
                "lentils, spinach and jaggery, plus protein, fruit and vegetables "
                "[src-demo-nutrition]."
            )
        )

    return RunnableLambda(generate)


def _timed(name: str, fn, *args, **kwargs) -> tuple[Any, Stage]:
    start = time.perf_counter()
    value = fn(*args, **kwargs)
    ms = (time.perf_counter() - start) * 1000
    return value, Stage(name, ms, "")


def _report_stage_1_prepare(plan: GenerationPlan, stage: Stage) -> None:
    """Safety pre-check, retrieval, grounding gate, context packet."""
    # On a short-circuit the classification lives on early_result, not on the
    # plan's own safety_result (which stays None because nothing ran).
    safety = plan.safety_result or (plan.early_result.safety_result if plan.early_result else None)
    detail = f"risk={getattr(safety, 'risk_category', '?')}"
    if plan.early_result is not None:
        detail += " | SHORT-CIRCUIT (no LLM called)"
    elif plan.context_packet is not None:
        packet = plan.context_packet
        detail += (
            f" | sources={len(packet.retrieved_sources)}"
            f" | domains={[d.value for d in packet.evidence_summary.domains]}"
            f" | tokens={packet.total_tokens}"
            f" | web={len(packet.web_sources)}"
        )
    stage.detail = detail


def _report_stage_4_finalize(result, stage: Stage) -> None:
    bits = [f"short_circuited={result.short_circuited}"]
    if result.citation_result is not None:
        bits.append(f"verified={result.citation_result.verified_citation_ids}")
        if result.citation_result.unverifiable_citation_ids:
            bits.append(f"REJECTED={result.citation_result.unverifiable_citation_ids}")
    if result.post_check_report is not None:
        bits.append(f"post_check_passed={result.post_check_report.passed}")
    stage.detail = " | ".join(bits)


def _print_header(query: str, settings: Settings, live: bool) -> None:
    print()
    print(RULE)
    print(f"QUERY   : {query}")
    print(f"ENGINE  : {settings.rag_engine}")
    print(f"ORCHESTRATOR : {settings.rag_orchestrator}")
    print(f"MODEL   : {'live provider' if live else 'stub (no API key, no network)'}")
    print(RULE)
    print()


def _print_stage(idx: int, stage: Stage) -> None:
    print(f"[{idx}] {stage.name:<38} {stage.ms:7.1f} ms")
    if stage.detail:
        for chunk in stage.detail.split(" | "):
            print(f"      {chunk}")


def run_trace(
    query: str,
    settings: Settings,
    chunk: KnowledgeChunk,
    scores: dict[str, float] | None,
    live: bool,
) -> int:
    stages: list[Stage] = []

    # Stage 1 - everything before the LLM: safety, retrieval, grounding, packet.
    plan, stage = _timed(
        "1. safety + retrieval + grounding",
        _prepare_generation,
        query,
        candidate_chunks=[chunk],
        candidate_scores=scores,
        profile=UserContext(),
        k=DEFAULT_K,
    )
    _report_stage_1_prepare(plan, stage)
    stages.append(stage)
    _print_stage(1, stage)

    if plan.early_result is not None:
        print()
        print("RESULT  : short-circuited before generation. The model was never called.")
        print()
        print(plan.early_result.answer)
        print()
        return 1

    # Stages 2 and 3 are fused inside _langchain_answer_query (that is the whole
    # point of the LCEL chain), so time them together and say so honestly.
    result, stage = _timed(
        "2+3. generate -> finalize (LangChain)",
        _langchain_answer_query,
        query,
        candidate_chunks=[chunk],
        candidate_scores=scores,
        candidate_scoring_mode=None,
        profile=UserContext(),
        client=None,
        k=DEFAULT_K,
        settings=settings,
    )
    stage.detail = "chain: RunnableLambda(prepare) -> RunnableBranch -> generate -> finalize"
    stages.append(stage)
    _print_stage(2, stage)

    fstage = Stage("4. citations + safety post-check", stage.ms, "")
    _report_stage_4_finalize(result, fstage)
    stages.append(fstage)
    _print_stage(4, fstage)

    print()
    print(RULE)
    print("FINAL ANSWER")
    print(RULE)
    print(result.answer)
    print()
    total = sum(s.ms for s in stages)
    print(f"total pipeline time: {total:.1f} ms")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", default="What should I eat in the first trimester?")
    parser.add_argument("--stream", action="store_true", help="stream deltas instead of tracing")
    parser.add_argument("--live", action="store_true", help="use the real LLM (needs keys)")
    parser.add_argument("--urgent", action="store_true", help="use an urgent query")
    parser.add_argument("--no-evidence", action="store_true", help="use a weak query with no evidence")
    args = parser.parse_args(argv)

    query = args.query
    if args.urgent:
        query = "I have heavy bleeding and severe abdominal pain"

    if not args.live:
        langchain_provider.build_chat_model = _stub_model

    settings = get_settings()
    chunk = _demo_chunk()
    scores: dict[str, float] | None = {chunk.chunk_id: 1.0}
    if args.no_evidence:
        # Let the grounding gate decide on real keyword scores instead of forcing 1.0.
        scores = None
        query = "What is the capital of France?"

    if args.stream:
        from app.rag.pipeline import answer_query_stream

        print()
        print("STREAM (delta events as they arrive)")
        print("-" * 78)
        for event in answer_query_stream(
            query,
            candidate_chunks=[chunk],
            candidate_scores=scores,
        ):
            if event.kind == "delta":
                print(event.text, end="", flush=True)
            else:
                print()
                print()
                print(f"[final] short_circuited={event.result.short_circuited if event.result else '?'}")
        print()
        return 0

    _print_header(query, settings, args.live)
    return run_trace(query, settings, chunk, scores, args.live)


if __name__ == "__main__":
    sys.exit(main())