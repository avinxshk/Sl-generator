import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """TestClient against a fresh seeded DB, forced into demo mode."""
    monkeypatch.setenv("SL_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # DB_PATH is read at import time; patch the module attribute too.
    from app import db
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c
