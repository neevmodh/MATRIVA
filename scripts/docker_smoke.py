"""Exercise production images with disposable synthetic data and no developer secrets.

Run from any directory: python scripts/docker_smoke.py. Docker Compose v2 is required.
Only the uniquely named test project's containers and volumes are removed afterward.
"""

from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import tempfile
import time
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def request(base, path, *, method="GET", payload=None, token=None, expected=200, raw=None, content_type=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        raw = json.dumps(payload).encode()
        content_type = "application/json"
    if content_type:
        headers["Content-Type"] = content_type
    req = Request(base + path, data=raw, headers=headers, method=method)
    try:
        response = urlopen(req, timeout=30)
    except HTTPError as error:
        response = error
    with response:
        body = response.read()
        assert response.status == expected, f"{method} {path}: {response.status}, {body[:500]!r}"
        return json.loads(body) if "application/json" in response.headers.get("Content-Type", "") else body


def main():
    project = "matriva-smoke-" + secrets.token_hex(4)
    with tempfile.TemporaryDirectory(prefix="matriva-smoke-") as directory:
        temporary = Path(directory)
        env_file = temporary / "smoke.env"
        # Override every Compose interpolation; never load the checkout's .env.
        values = {
            "POSTGRES_USER": "smoke", "POSTGRES_PASSWORD": secrets.token_hex(16), "POSTGRES_DB": "smoke",
            "REDIS_PASSWORD": secrets.token_hex(16), "JWT_SECRET": secrets.token_hex(32),
            "CORS_ORIGINS": "http://localhost:3000", "NEXT_PUBLIC_API_URL": "http://localhost:8000",
            "INSTALL_OPTIONAL": "true", "RAG_ENGINE": "local", "RAG_ORCHESTRATOR": "langchain",
            "LLM_API_KEY": "", "GROQ_API_KEY": "", "EMBEDDING_API_KEY": "", "GEMINI_API_KEY": "", "TAVILY_API_KEY": "",
            "MATRIVA_ENV_FILE": str(env_file),
        }
        with socket.socket() as api_socket, socket.socket() as web_socket:
            api_socket.bind(("127.0.0.1", 0))
            web_socket.bind(("127.0.0.1", 0))
            api_port = api_socket.getsockname()[1]
            web_port = web_socket.getsockname()[1]
        values["NEXT_PUBLIC_API_URL"] = f"http://127.0.0.1:{api_port}"
        values["CORS_ORIGINS"] = f"http://127.0.0.1:{web_port}"
        values["DATABASE_URL"] = f"postgresql+psycopg://smoke:{values['POSTGRES_PASSWORD']}@db:5432/smoke"
        values["REDIS_URL"] = f"redis://:{values['REDIS_PASSWORD']}@redis:6379/0"
        values["VECTOR_DATABASE_URL"] = values["DATABASE_URL"]
        env_file.write_text("\n".join(f"{key}={value}" for key, value in values.items()) + "\n")
        env_file.chmod(0o600)
        override = temporary / "ports.yml"
        override.write_text(f'''services:
  backend:
    ports: ["127.0.0.1:{api_port}:8000"]
    environment:
      FORWARDED_ALLOW_IPS: "127.0.0.1"
  frontend:
    ports: ["127.0.0.1:{web_port}:3000"]
''')
        command = ["docker", "compose", "--project-name", project, "--env-file", str(env_file),
                   "-f", str(ROOT / "docker-compose.prod.yml"), "-f", str(override)]
        environment = {**os.environ, **values}

        def compose(*args, capture=False):
            return subprocess.run(command + list(args), cwd=ROOT, env=environment, check=True,
                                  text=True, stdout=subprocess.PIPE if capture else None).stdout

        try:
            compose("up", "--build", "--detach", "--wait", "--wait-timeout", "180")
            api = "http://" + compose("port", "backend", "8000", capture=True).strip()
            web = "http://" + compose("port", "frontend", "3000", capture=True).strip()
            for attempt in range(30):
                try:
                    request(web, "/")
                    break
                except (URLError, TimeoutError):
                    if attempt == 29:
                        raise
                    time.sleep(1)
            health = request(api, "/health")
            assert health["status"] == "ok" and health["database"] == health["redis"] == "ok"
            compose("exec", "-T", "backend", "python", "-m", "pip", "check")
            compose("exec", "-T", "backend", "tesseract", "--version", capture=True)
            compose("exec", "-T", "frontend", "node", "-e",
                    "for (const key of ['JWT_SECRET', 'DATABASE_URL', 'REDIS_PASSWORD', 'LLM_API_KEY']) "
                    "{ if (key in process.env) throw new Error('Backend secret reached frontend: ' + key); }")
            compose("exec", "-T", "backend", "alembic", "upgrade", "head")  # rerun migrations too
            for name in ("mother", "nutrition", "gestation"):
                assert request(web, f"/plates/{name}.jpg").startswith(b"\xff\xd8")
            request(api, "/profile", expected=401)
            credentials = {"email": "smoke@example.com", "password": "StrongPass123"}
            token = request(api, "/auth/register", method="POST", payload=credentials, expected=201)["access_token"]
            request(api, "/auth/login", method="POST", payload=credentials)
            request(api, "/admin/documents", token=token, expected=403)
            request(api, "/profile", method="PUT", token=token, payload={"consent": True, "region": "Gujarat"})
            request(api, "/care/dating", method="PUT", token=token, payload={"current_week": 20})
            request(api, "/care/plan", token=token)
            request(api, "/care/summary", token=token)
            answer = request(api, "/chat", method="POST", token=token, payload={"message": "I have heavy bleeding"})
            assert answer["safety_status"] == "urgent_escalation" and answer["sources"] == []
            # Promote only our synthetic account in this fresh disposable database.
            compose("exec", "-T", "backend", "python", "-c", '''from app.core.db import SessionLocal
from app.models import User
with SessionLocal() as db:
    user = db.query(User).filter_by(email="smoke@example.com").one()
    user.role = "admin"
    db.commit()
''')
            boundary = "matriva-smoke-upload"
            metadata = json.dumps({"title": "Synthetic test source", "domain": "nutrition", "source_name": "smoke-source",
                                   "source_type": "government", "evidence_level": "supported"})
            upload = (f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n{metadata}\r\n'
                      f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="source.txt"\r\n'
                      'Content-Type: text/plain\r\n\r\nSynthetic source text about balanced meals.\r\n'
                      f'--{boundary}--\r\n').encode()
            document = request(api, "/admin/documents", method="POST", token=token, raw=upload,
                               content_type=f"multipart/form-data; boundary={boundary}", expected=201)
            prefix = "/admin/documents/" + document["id"]
            request(api, prefix + "/approve", method="POST", token=token, expected=409)
            request(api, prefix + "/reindex", method="POST", token=token)
            request(api, prefix + "/approve", method="POST", token=token)
            assert request(api, "/knowledge/search?query=balanced%20meals")["count"] > 0
            evaluation = request(api, "/evaluation/run", method="POST", token=token, payload={"suite": "safety"})
            assert evaluation["status"] == "completed", evaluation
            assert evaluation["metrics"]["safety"]["score"] == 1
            compose("exec", "-T", "backend", "python", "-c", '''from app.core.redis import connect_redis
from app.core.rate_limit import allow_request
a, b = connect_redis(), connect_redis()
assert allow_request("smoke:quota", 1, redis_client=a, required=True)[0]
assert not allow_request("smoke:quota", 1, redis_client=b, required=True)[0]
''')
            assert request(api, "/privacy/export", token=token)["profile"]["consent"]
            request(api, "/privacy/account", method="DELETE", token=token)
            request(api, "/profile", token=token, expected=401)
            if "--browser" in sys.argv:
                subprocess.run(
                    ["npx", "--no-install", "playwright", "test", "--config", "playwright.production.config.ts"],
                    cwd=ROOT / "frontend", check=True,
                    env={**environment, "SMOKE_WEB_URL": web, "SMOKE_API_URL": api},
                )
            print("Production smoke passed: migrations, readiness, assets, auth, consent, care, safety, document review, reports, shared quotas, export and deletion.")
        except Exception:
            compose("logs", "--no-color", "--tail", "80")
            raise
        finally:
            compose("down", "--volumes", "--remove-orphans")


if __name__ == "__main__":
    main()
