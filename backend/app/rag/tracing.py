"""Optional LangSmith tracing for the RAG pipeline, off by default.

MATRIVA answers pregnancy and health questions. LangSmith tracing uploads the
run tree to a SaaS endpoint, and by default that includes the user's literal
question, the retrieved source passages and the generated answer -- personal
health information leaving the system.

So tracing is opt-in and fails closed:

- ``langsmith_tracing`` defaults to ``False``; nothing is sent unless enabled.
- ``langsmith_anonymize`` defaults to ``True``, which keeps the structure that
  makes a trace useful (stage names, timings, token counts, citation ids,
  evidence levels) while replacing question text, source content and the
  generated answer with length-only placeholders.
- A missing or invalid API key degrades to a no-op. Tracing must never be able
  to break the chat endpoint.

What you get in LangSmith is the run tree from the reference UI: the chain, its
child stages with per-stage durations, token counts and the citation ids that
survived validation.

Enable with::

    LANGCHAIN_TRACING_V2=true
    LANGSMITH_API_KEY=...        # never commit this
    LANGSMITH_PROJECT=matriva

See docs/observability.md for the full walkthrough.
"""

from __future__ import annotations

import os
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.core.config import Settings, get_settings

MAX_TRACED_CHARS = 120


def tracing_enabled(settings: Settings | None = None) -> bool:
    """True only when tracing is on AND a key is present.

    Uses ``getattr`` defaults so that partial settings objects (the
    ``SimpleNamespace`` fakes the test-suite passes around) are handled rather
    than raising ``AttributeError`` inside the chat path. Tracing must never be
    able to break a request.
    """

    resolved = settings or get_settings()
    if not getattr(resolved, "langsmith_tracing", False):
        return False
    return bool(getattr(resolved, "langsmith_api_key", "") or os.environ.get("LANGSMITH_API_KEY"))


def apply_tracing_env(settings: Settings | None = None) -> bool:
    """Push settings into the env vars LangChain reads. Returns whether tracing is on.

    Called once at process start. When ``langsmith_anonymize`` is set it also
    hides the verbose payload inputs, so the run tree still exists even though
    the verbatim question and answer do not leave the machine.
    """

    resolved = settings or get_settings()
    if not tracing_enabled(resolved):
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        return False

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = getattr(resolved, "langsmith_project", "matriva")
    key = getattr(resolved, "langsmith_api_key", "") or os.environ.get("LANGSMITH_API_KEY")
    if key:
        os.environ["LANGSMITH_API_KEY"] = key
    if getattr(resolved, "langsmith_anonymize", True):
        os.environ["LANGCHAIN_HIDE_INPUTS"] = "true"
        os.environ["LANGCHAIN_HIDE_OUTPUTS"] = "true"
    return True


def _redact(text: str | None) -> dict[str, Any]:
    """Replace content with a length-only summary."""

    if not text:
        return {"chars": 0}
    return {"chars": len(text), "preview": text[:MAX_TRACED_CHARS] + ("..." if len(text) > MAX_TRACED_CHARS else "")}


def run_config(settings: Settings | None = None, **tags: Any) -> RunnableConfig:
    """Config to pass to ``.invoke``/``.stream`` so runs land in the right project."""

    resolved = settings or get_settings()
    config: RunnableConfig = {"run_name": "matriva.rag.query"}
    if tracing_enabled(resolved):
        config["tags"] = ["matriva", *(f"{k}:{v}" for k, v in tags.items() if v is not None)]
        config["metadata"] = {k: v for k, v in tags.items() if isinstance(v, (str, int, float, bool))}
    return config


def summarize_citations(result: Any) -> dict[str, Any]:
    """Trace-safe summary of what the pipeline decided about evidence."""

    if result is None:
        return {}
    out: dict[str, Any] = {"short_circuited": getattr(result, "short_circuited", None)}
    packet = getattr(result, "context_packet", None)
    if packet is not None:
        out["sources_retrieved"] = len(getattr(packet, "retrieved_sources", []) or [])
        out["domains"] = [d.value for d in getattr(packet.evidence_summary, "domains", [])] if getattr(packet, "evidence_summary", None) else []
        out["context_tokens"] = getattr(packet, "total_tokens", None)
        out["web_sources"] = len(getattr(packet, "web_sources", []) or [])
    citation = getattr(result, "citation_result", None)
    if citation is not None:
        out["verified_citations"] = list(getattr(citation, "verified_citation_ids", []) or [])
        out["unverifiable_citations"] = list(getattr(citation, "unverifiable_citation_ids", []) or [])
    post = getattr(result, "post_check_report", None)
    if post is not None:
        out["post_check_passed"] = getattr(post, "passed", None)
    return out