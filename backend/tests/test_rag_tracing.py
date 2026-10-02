"""Tests for LangSmith tracing (issue: observability).

The critical property is negative: tracing must not send anything unless it is
explicitly switched on, and when it is on the verbatim health text must still
stay local unless anonymisation is deliberately disabled.

A regression here would silently exfiltrate patient questions, so these assert
the defaults rather than the happy path.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from app.rag import tracing


def _settings(**overrides):
    base = {
        "langsmith_tracing": False,
        "langsmith_project": "matriva",
        "langsmith_api_key": "",
        "langsmith_anonymize": True,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_tracing_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """The shipped default must not phone home."""

    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    assert tracing.tracing_enabled(_settings()) is False
    assert tracing.apply_tracing_env(_settings()) is False
    assert os.environ["LANGCHAIN_TRACING_V2"] == "false"


def test_tracing_requires_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enabled but keyless must degrade to no-op, never crash the chat endpoint."""

    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    assert tracing.tracing_enabled(_settings(langsmith_tracing=True)) is False


def test_anonymisation_hides_inputs_and_outputs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Health text must not leave the machine by default."""

    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    assert tracing.apply_tracing_env(_settings(langsmith_tracing=True)) is True
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGCHAIN_PROJECT"] == "matriva"
    assert os.environ["LANGCHAIN_HIDE_INPUTS"] == "true"
    assert os.environ["LANGCHAIN_HIDE_OUTPUTS"] == "true"


def test_anonymisation_can_be_turned_off_explicitly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")
    monkeypatch.delenv("LANGCHAIN_HIDE_INPUTS", raising=False)
    monkeypatch.delenv("LANGCHAIN_HIDE_OUTPUTS", raising=False)
    tracing.apply_tracing_env(_settings(langsmith_tracing=True, langsmith_anonymize=False))
    assert "LANGCHAIN_HIDE_INPUTS" not in os.environ
    assert "LANGCHAIN_HIDE_OUTPUTS" not in os.environ


def test_run_config_stays_minimal_when_disabled() -> None:
    """No tags/metadata leak into runs when nothing is being traced."""

    config = tracing.run_config(_settings())
    assert config["run_name"] == "matriva.rag.query"
    assert "tags" not in config
    assert "metadata" not in config


def test_run_config_carries_tags_when_enabled() -> None:
    config = tracing.run_config(
        _settings(langsmith_tracing=True, langsmith_api_key="k"),
        orchestrator="langchain",
        engine="external",
    )
    assert "matriva" in config["tags"]
    assert "orchestrator:langchain" in config["tags"]
    assert config["metadata"]["orchestrator"] == "langchain"


def test_run_config_survives_partial_settings_objects() -> None:
    """The pipeline is called with fakes in tests; tracing must not raise there."""

    config = tracing.run_config(SimpleNamespace())  # no langsmith_* attributes at all
    assert config["run_name"] == "matriva.rag.query"
    assert "tags" not in config
    assert tracing.tracing_enabled(SimpleNamespace()) is False


def test_citation_summary_exposes_decisions_without_prose() -> None:
    """The summary must be safe to send: decisions and ids, never answer text."""

    result = SimpleNamespace(
        short_circuited=False,
        answer="I have heavy bleeding, go to hospital now",
        context_packet=SimpleNamespace(
            retrieved_sources=[1, 2],
            evidence_summary=SimpleNamespace(domains=[]),
            total_tokens=42,
            web_sources=[],
        ),
        citation_result=SimpleNamespace(
            verified_citation_ids=["src-a"],
            unverifiable_citation_ids=["src-fake"],
        ),
        post_check_report=SimpleNamespace(passed=True),
    )
    summary = tracing.summarize_citations(result)
    assert summary["verified_citations"] == ["src-a"]
    assert summary["unverifiable_citations"] == ["src-fake"]
    assert summary["post_check_passed"] is True
    assert summary["sources_retrieved"] == 2
    # The user's own words must not appear anywhere in the trace payload.
    assert "bleeding" not in repr(summary)
    assert "hospital" not in repr(summary)


def test_citation_summary_handles_none() -> None:
    assert tracing.summarize_citations(None) == {}