from pathlib import Path
import runpy

import pytest

from app.core.config import get_settings


def load_seed():
    return runpy.run_path(str(Path(__file__).resolve().parents[2] / "database" / "seed" / "seed.py"))


def test_seed_requires_an_explicit_password(monkeypatch):
    monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="Set DEMO_PASSWORD"):
        load_seed()["seed_demo_data"]()


@pytest.mark.parametrize("setting,value", [("environment", "production"), ("demo_mode", False)])
def test_seed_refuses_non_demo_environments(monkeypatch, setting, value):
    monkeypatch.setenv("DEMO_PASSWORD", "SyntheticSeed123!")
    monkeypatch.setattr(get_settings(), setting, value)
    with pytest.raises(RuntimeError, match="disabled"):
        load_seed()["seed_demo_data"]()


def test_seed_is_idempotent_and_does_not_log_password(monkeypatch, capsys):
    monkeypatch.setenv("DEMO_PASSWORD", "SyntheticSeed123!")
    seed = load_seed()["seed_demo_data"]
    seed()
    seed()
    from app.core.db import SessionLocal
    from app.core.security import verify_password
    from app.models import User

    with SessionLocal() as db:
        user = db.query(User).filter_by(email="admin@demo.example.com").one()
        assert verify_password("SyntheticSeed123!", user.password_hash)
    assert "SyntheticSeed123!" not in capsys.readouterr().out
