from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.core.rate_limit import RateLimitUnavailable, allow_request
from app.main import app


@pytest.mark.parametrize("path", ["/care/plan", "/profile", "/privacy/export", "/resources", "/evaluation/results"])
def test_general_routes_are_limited(client, monkeypatch, path):
    monkeypatch.setattr(get_settings(), "rate_limit_general_per_minute", 1)
    client.get(path)
    response = client.get(path, headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 429
    assert response.headers["Retry-After"]
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
    assert response.headers["Cache-Control"] == "no-store"


def test_changing_resource_ids_does_not_reset_quota(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_general_per_minute", 1)
    client.get("/sources/first")
    assert client.get("/sources/second").status_code == 429
    assert client.get("/health").status_code == 200


def test_preflight_does_not_consume_quota(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_general_per_minute", 1)
    response = client.options("/profile", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET",
    })
    assert response.status_code == 200
    assert client.get("/profile").status_code == 401


def test_redis_quota_is_shared_and_contains_no_client_identifiers():
    counts = {}

    def evaluate(script, keys, key, window):
        assert "EXPIRE" in script and keys == 1 and window == 60
        assert "192.0.2.1" not in key
        counts[key] = counts.get(key, 0) + 1
        return counts[key], 59

    worker_a = SimpleNamespace(eval=evaluate)
    worker_b = SimpleNamespace(eval=evaluate)
    assert allow_request("192.0.2.1:care", 1, redis_client=worker_a)[0]
    assert allow_request("192.0.2.1:care", 1, redis_client=worker_b) == (False, 0, 59)


def test_redis_outage_fails_closed_in_production(client, monkeypatch):
    def unavailable(*args):
        raise ConnectionError("offline")

    monkeypatch.setattr(get_settings(), "environment", "production")
    monkeypatch.setattr(app.state, "redis", SimpleNamespace(eval=unavailable))
    response = client.get("/profile", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 503
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
    with pytest.raises(RateLimitUnavailable):
        allow_request("client:care", 1, required=True)


def test_unhealthy_dependencies_fail_readiness(client, monkeypatch):
    def unavailable():
        raise ConnectionError("offline")

    monkeypatch.setattr(app.state, "redis", SimpleNamespace(ping=unavailable))
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_limited_requests_are_counted_once(client, monkeypatch):
    from app.core.observability import metrics

    monkeypatch.setattr(get_settings(), "rate_limit_general_per_minute", 1)
    client.get("/profile")
    before = sum(metrics.snapshot()["requests"].values())
    assert client.get("/profile").status_code == 429
    assert sum(metrics.snapshot()["requests"].values()) == before + 1
