import os

# Unit evaluation is always offline, including when a developer has exported keys.
for key in ("LLM_API_KEY", "GROQ_API_KEY", "EMBEDDING_API_KEY", "GEMINI_API_KEY", "TAVILY_API_KEY"):
    os.environ[key] = ""
