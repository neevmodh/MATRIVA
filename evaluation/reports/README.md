# Generated evaluation reports

JSON files in this directory are local outputs and are ignored by Git. The runners create the directory when they write a report. Dataset YAML files and scoring code remain versioned in `evaluation/`.

From the repository root, with the backend dependencies installed and its virtual environment activated:

```bash
python evaluation/retrieval/run.py
python evaluation/generation/run.py
python evaluation/safety/run.py
python evaluation/hallucination/run.py
python evaluation/local_rag/run.py
python evaluation/local_rag/ablation.py
```

Without provider keys, generation runs labelled self-test examples and hallucination evaluation uses its keyword fallback. Setting `LLM_API_KEY` or `GROQ_API_KEY` enables live generation; `EMBEDDING_API_KEY` or `GEMINI_API_KEY` enables vector-backed hallucination evaluation. Check each report's mode before comparing scores: offline results do not reproduce a previous provider-backed run.

The admin evaluation API writes run-specific reports here in a checkout, or to `EVALUATION_REPORT_DIR` when configured (Docker uses its persistent runtime volume). The legacy keyword abstention benchmark now passes 11/11 using query coverage, and CI enforces that result; a small benchmark remains a heuristic check. Scores alone are not clinical review; generated responses still need the [human review checklist](../generation/human_review_checklist.md).
