"""Hallucination / grounding guard (issue #19, Master Prompt Section 43).

Gap this closes: #66's Sprint 0 script (seed_qa.py) already returned a fixed
insufficient-evidence response when retrieval found nothing, but the real
pipeline (#6 hybrid_retrieve -> #7 rerank -> #8 context_packet -> #9 generate)
never got an equivalent check -- it would happily build a context packet with
zero (or only weakly-relevant) sources and hand it to the LLM anyway, which
is exactly the failure mode Section 43 warns about: the model filling the
gap from general knowledge when it should say "I don't know."

The only way to actually guarantee the model can't do that is to never give
it the chance -- so `generate_or_insufficient_evidence` checks evidence
sufficiency BEFORE calling Groq at all, and returns the fixed response
directly (no LLM call) when there's nothing to ground an answer in.
"""

from __future__ import annotations

from app.llm.groq_client import Groq, generate_from_packet
from app.rag.context_packet import ContextPacket
from app.rag.keyword_search import MIN_KEYWORD_RELEVANCE, keyword_query_coverage
from app.schemas.knowledge import KnowledgeChunk

INSUFFICIENT_EVIDENCE_RESPONSE = (
    "I don't have enough evidence in the available knowledge base to answer that reliably."
)

# Keyword mode requires a positive score AND query coverage when a question
# is supplied. Vector mode uses a cosine floor against unboosted evidence
# scores; ranking bonuses do not count as semantic relevance.
DEFAULT_MIN_SCORE = 0.0
_VECTOR_MIN_SCORE = 0.75  # cosine similarity floor; revisit once real embeddings are live and this can be tuned against actual data
DEFAULT_MIN_SCORE_BY_MODE = {"keyword": DEFAULT_MIN_SCORE, "vector": _VECTOR_MIN_SCORE}


def has_sufficient_evidence(
    scored_chunks: list[tuple[KnowledgeChunk, float]],
    min_score: float | None = None,
    scoring_mode: str = "keyword",
    query: str | None = None,
) -> bool:
    """True if at least one retrieved chunk clears the relevance bar.

    `scoring_mode` picks the right default threshold ("keyword" vs "vector",
    see DEFAULT_MIN_SCORE_BY_MODE) -- pass #6's RetrievalResult.scoring_mode
    here rather than relying on the keyword-only default. `min_score`
    overrides the mode-based default explicitly when given.
    Generation callers always supply the question; the query-less form is
    retained for score-only integrations and does not assess topical coverage.
    """
    if min_score is None:
        min_score = DEFAULT_MIN_SCORE_BY_MODE.get(scoring_mode, DEFAULT_MIN_SCORE)
    return any(
        score > min_score
        and (
            scoring_mode != "keyword" or query is None
            or keyword_query_coverage(query, chunk.content) >= MIN_KEYWORD_RELEVANCE
        )
        for chunk, score in scored_chunks
    )


def generate_or_insufficient_evidence(
    context_packet: ContextPacket,
    scored_chunks: list[tuple[KnowledgeChunk, float]],
    *,
    min_score: float | None = None,
    scoring_mode: str = "keyword",
    client: Groq | None = None,
    **generate_kwargs,
) -> str:
    """Section 43's guarantee: if evidence is insufficient, return the fixed
    response WITHOUT calling the LLM at all -- the model never gets a chance
    to fill the gap from general knowledge."""
    if not has_sufficient_evidence(
        scored_chunks, min_score=min_score, scoring_mode=scoring_mode, query=context_packet.user_question,
    ):
        return INSUFFICIENT_EVIDENCE_RESPONSE
    return generate_from_packet(context_packet, client=client, **generate_kwargs)
