"""Shared keyword-overlap scoring, used by Sprint 0's seed_qa.py and #6's
hybrid retrieval as the keyword component of "semantic vector search +
metadata filtering + keyword search where useful" (Section 12 Step 6).
"""

from __future__ import annotations

import re

_STOPWORDS = {
    "the", "a", "an", "is", "are", "what", "should", "for", "of", "in", "on",
    "to", "and", "or", "my", "me", "i", "do", "does", "can", "any", "with",
}

# The SQL keyword adapter uses the same coverage floor. Raw overlap counts
# alone cannot distinguish a topical match from one incidental shared word.
MIN_KEYWORD_RELEVANCE = 0.3


def tokenize(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if w not in _STOPWORDS}


def keyword_overlap_score(query: str, text: str) -> int:
    return len(tokenize(query) & tokenize(text))


def keyword_query_coverage(query: str, text: str) -> float:
    terms = tokenize(query)
    return len(terms & tokenize(text)) / len(terms) if terms else 0.0


def contains_phrase(text: str, phrase: str) -> bool:
    """Word-boundary substring match: `phrase` must appear as whole words in
    `text`, not as a raw substring. Prevents false positives like "eat"
    matching inside "weather" (plain `phrase in text` would wrongly match).
    Works for both single words and multi-word phrases.
    """
    pattern = r"\b" + re.escape(phrase.lower()) + r"\b"
    return re.search(pattern, text.lower()) is not None
