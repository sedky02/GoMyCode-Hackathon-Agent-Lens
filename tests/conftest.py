import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agentlens import store  # noqa: E402
from agentlens.demo import load_source_events  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "agentlens-test.db")
    for name in ("AGENTLENS_LLM_BASE_URL", "AGENTLENS_LLM_MODEL", "AGENTLENS_MODE"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(scope="session")
def dataset_events():
    return load_source_events()


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from agentlens.api import app
    return TestClient(app)


@pytest.fixture()
def live_server():
    """A real uvicorn server: the threadpool behaviour differs from TestClient's."""
    import socket
    import threading
    import time

    import uvicorn

    from agentlens.api import app
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started:
        assert time.time() < deadline, "uvicorn did not start"
        time.sleep(0.02)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)
