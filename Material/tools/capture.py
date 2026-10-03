"""Capture the real UI against a disposable, offline SQLite API.

Requires the repository's backend venv, frontend npm dependencies, and Playwright
Chromium. Stops only the two processes created here and removes its temporary DB.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]


def free_port() -> int:
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        return connection.getsockname()[1]


def ready(url: str, process: subprocess.Popen) -> None:
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError("Capture server exited before it was ready")
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError):
            pass
        time.sleep(1)
    raise TimeoutError("Capture server did not become ready")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="matriva-material-") as directory:
        temporary = Path(directory)
        api_port, web_port = free_port(), free_port()
        api, web = f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{web_port}"
        environment = {
            **os.environ,
            "DATABASE_URL": f"sqlite:///{temporary / 'capture.db'}",
            "REDIS_URL": "",
            "VECTOR_DATABASE_URL": "",
            "ENVIRONMENT": "development",
            "DEMO_MODE": "true",
            "AUTO_CREATE_TABLES": "false",
            "JWT_SECRET": secrets.token_urlsafe(48),
            "JWT_EXPIRES_MINUTES": "120",
            "RAG_ENGINE": "local",
            "LLM_API_KEY": "",
            "GROQ_API_KEY": "",
            "EMBEDDING_API_KEY": "",
            "GEMINI_API_KEY": "",
            "TAVILY_API_KEY": "",
            "LANGSMITH_API_KEY": "",
            "LANGSMITH_TRACING": "false",
            "LANGCHAIN_TRACING_V2": "false",
            "LANGSMITH_TRACING_V2": "false",
            "LANGSMITH_ANONYMIZE": "true",
            "CORS_ORIGINS": web,
            "NEXT_PUBLIC_API_URL": api,
            "MATERIAL_API_URL": api,
            "MATERIAL_WEB_URL": web,
            "EVALUATION_REPORT_DIR": str(temporary / "reports"),
            "RATE_LIMIT_GENERAL_PER_MINUTE": "1000",
            "RATE_LIMIT_CHAT_PER_MINUTE": "1000",
            "RATE_LIMIT_AUTH_PER_MINUTE": "1000",
            "NEXT_TELEMETRY_DISABLED": "1",
        }
        python = ROOT / "backend/.venv/bin/python"
        subprocess.run(
            [str(python), "-m", "alembic", "upgrade", "head"],
            cwd=ROOT / "backend",
            env=environment,
            check=True,
        )
        processes = []
        try:
            with (
                (temporary / "api.log").open("w") as api_log,
                (temporary / "web.log").open("w") as web_log,
            ):
                backend = subprocess.Popen(
                    [
                        str(python),
                        "-m",
                        "uvicorn",
                        "app.main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(api_port),
                    ],
                    cwd=ROOT / "backend",
                    env=environment,
                    stdout=api_log,
                    stderr=subprocess.STDOUT,
                )
                processes.append(backend)
                frontend = subprocess.Popen(
                    [
                        "node",
                        "node_modules/next/dist/bin/next",
                        "dev",
                        "--webpack",
                        "--hostname",
                        "127.0.0.1",
                        "--port",
                        str(web_port),
                    ],
                    cwd=ROOT / "frontend",
                    env=environment,
                    stdout=web_log,
                    stderr=subprocess.STDOUT,
                )
                processes.append(frontend)
                ready(api + "/health", backend)
                ready(web, frontend)
                with urlopen(api + "/health", timeout=5) as response:
                    assert json.load(response)["status"] == "ok"
                subprocess.run(
                    ["node", str(ROOT / "Material/tools/capture.mjs")],
                    cwd=ROOT,
                    env=environment,
                    check=True,
                )
        finally:
            for process in reversed(processes):
                process.terminate()
            for process in reversed(processes):
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    main()
