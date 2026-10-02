# Observability: seeing what the RAG pipeline actually did

The external path answers a question by running several stages:

```
user question
  -> 1. safety pre-check      (classify, short-circuit if urgent)
  ->    hybrid retrieval      (keyword or vector + pgvector)
  ->    grounding gate        (enough evidence? else fixed refusal)
  ->    rerank + context packet
  -> 2. prompt from packet    (source-grounded system prompt)
  -> 3. ChatGroq              (the model call)
  -> 4. citations + post-check(validate, then fail-closed output guard)
  -> answer
```

Two ways to watch it: a terminal trace, and a LangSmith run tree.

---

## 1. Terminal trace (no key, no network)

```bash
cd backend
python -m scripts.rag_trace "What should I eat in the first trimester?"
```

Prints each stage, what it decided, and how long it took:

```
QUERY   : What should I eat in the first trimester?
ENGINE  : local
ORCHESTRATOR : langchain
MODEL   : stub (no API key, no network)

[1] 1. safety + retrieval + grounding          1.5 ms
      risk=SAFE_GENERAL
      sources=1
      domains=['NUTRITION']
      tokens=33
      web=0
[2] 2+3. generate -> finalize (LangChain)     11.8 ms
[4] 4. citations + safety post-check          11.8 ms
      short_circuited=False
      verified=['src-demo-nutrition']
      post_check_passed=True

FINAL ANSWER
A balanced pregnancy diet should include iron-rich foods such as lentils,
spinach and jaggery, plus protein, fruit and vegetables [src-demo-nutrition].

total pipeline time: 25.1 ms
```

Useful flags:

| flag | shows |
|---|---|
| `--urgent` | the safety short-circuit; the model is never called |
| `--no-evidence` | the grounding gate refusing; retrieval found nothing usable |
| `--stream` | token deltas as they arrive, then the validated final answer |
| `--live` | the real model (needs `LLM_API_KEY` and `RAG_ENGINE=external`) |

Exit code is `0` when an answer was produced and `1` on a short-circuit, so it
can be used as a smoke check.

---

## 2. LangSmith run tree (the UI in your screenshot)

LangSmith renders the chain as a tree: parent `RunnableSequence`, one child node
per stage, each with its own duration, and input/output on every node.

### Enable

In `backend/.env`:

```bash
LANGCHAIN_TRACING_V2=true
LANGSMITH_API_KEY=...        # never commit this
LANGSMITH_PROJECT=matriva
```

Or set `langsmith_tracing` / `langsmith_api_key` in `app/core/config.py`.
Then start the app or run the trace script and open
[smith.langchain.com](https://smith.langchain.com).

Stages are named explicitly, so the tree reads:

```
matriva.rag.query
├─ 1.safety+retrieval+grounding
├─ 2.context_packet
├─ 3.generate
│    └─ ChatGroq                (the actual model call)
└─ 4.citations+post_check
```

### Read this before you enable it

**MATRIVA handles pregnancy and health questions. Tracing uploads the run tree to
a SaaS endpoint, and by default that tree contains the user's literal question,
the retrieved source passages and the generated answer.** That is personal health
information leaving the system.

So:

- `langsmith_tracing` is **off by default**. Nothing is sent unless you turn it on.
- `langsmith_anonymize` is **on by default**. It sets `LANGCHAIN_HIDE_INPUTS` and
  `LANGCHAIN_HIDE_OUTPUTS`, so you get the run tree (stage names, durations,
  token counts, citation ids, evidence levels, pass/fail) but **not** the
  verbatim question or answer.
- Use it for development and demos **with synthetic data only**.
- A missing or invalid key degrades to a no-op. Tracing can never break the chat
  endpoint (`app/rag/tracing.py`, covered by `tests/test_rag_tracing.py`).

If tracing is ever needed in production, that needs a data-processing agreement,
a self-hosted LangSmith, or a redaction layer first. **Not a config flag.**

### What anonymised traces still tell you

Enough to debug the pipeline, which is the whole point:

- which stage dropped the answer, and why (`short_circuited`,
  `risk`, `unverifiable_citations`, `post_check_passed`)
- how long each stage took
- how many sources were retrieved and in which domains
- which citations survived validation
- whether web search was used

`tracing.summarize_citations()` builds exactly this summary, and there is a test
asserting the user's own words never appear in it.

---

## 3. Which orchestrator am I looking at?

| `RAG_ORCHESTRATOR` | what runs |
|---|---|
| `langchain` (default) | stages composed as one LCEL runnable chain |
| `native` | the original explicit Python sequence (rollback seam) |

Both call the same safety, grounding, citation and post-check functions. Only
the control flow differs, so the safety policy is identical.

---

## Troubleshooting an answer that looks wrong

Work down the list; the first stage that reports a problem is the culprit.

| symptom | likely stage | check |
|---|---|---|
| generic escalation message | 1. safety pre-check | `risk=` should not be `URGENT_ESCALATION` |
| "not enough evidence" | 1. grounding gate | `sources=` is 0, or scores below threshold |
| answer ignores the sources | 3. ChatGroq | look at the prompt; check `tokens=` |
| citations missing | 4. citations | `verified=` vs `unverifiable=` |
| safe answer replaced by a refusal | 4. post-check | `post_check_passed=False` |

With LangSmith off (the default), reproduce locally and run
`python -m scripts.rag_trace "<the same question>"` to get the same stage
breakdown.