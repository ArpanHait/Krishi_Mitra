import asyncio
import contextlib
import tempfile
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

import api_server
import db


@pytest.fixture
def temp_db(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    monkeypatch.setattr(db, "DB_PATH", db_path)
    monkeypatch.setattr(api_server.db, "DB_PATH", db_path)
    db._INITIALIZED_DBS.clear()
    db.init_db(db_path)

    yield db_path

    if db_path.exists():
        with contextlib.suppress(Exception):
            db_path.unlink()


def test_tool_logging_and_analytics(temp_db):
    """Test log_tool_call and get_tool_analytics for Mandi and Weather."""
    # Check that initially counts are 0 with no mock data
    initial_stats = db.get_tool_analytics(db_path=temp_db)
    assert "mandi" in initial_stats
    assert "weather" in initial_stats
    assert initial_stats["mandi"]["total"] == 0
    assert initial_stats["mandi"]["successful"] == 0
    assert initial_stats["mandi"]["failed"] == 0
    assert initial_stats["weather"]["total"] == 0
    assert initial_stats["weather"]["successful"] == 0
    assert initial_stats["weather"]["failed"] == 0

    # Log 1 successful weather call
    db.log_tool_call("weather", "SUCCESS", db_path=temp_db)
    # Log 1 failed mandi call
    db.log_tool_call("mandi", "FAILED", error_message="Timeout", db_path=temp_db)

    updated_stats = db.get_tool_analytics(db_path=temp_db)
    assert updated_stats["weather"]["total"] == 1
    assert updated_stats["weather"]["successful"] == 1
    assert updated_stats["mandi"]["total"] == 1
    assert updated_stats["mandi"]["failed"] == 1


def test_agent_response_logging_and_analytics(temp_db):
    """Test log_agent_response and get_agent_response_analytics for Krishi Mitra and Fasal Doctor."""
    initial_agents = db.get_agent_response_analytics(db_path=temp_db)
    assert len(initial_agents) == 2
    km = next(a for a in initial_agents if a["name"] == "Krishi Mitra")
    fd = next(a for a in initial_agents if a["name"] == "Fasal Doctor")

    assert km["total"] == 0
    assert km["successful"] == 0
    assert km["failed"] == 0
    assert fd["total"] == 0
    assert fd["successful"] == 0
    assert fd["failed"] == 0

    # Log new response for Krishi Mitra
    db.log_agent_response("Krishi Mitra", "SUCCESS", db_path=temp_db)
    # Log new response for Fasal Doctor
    db.log_agent_response("Fasal Doctor", "SUCCESS", db_path=temp_db)

    updated_agents = db.get_agent_response_analytics(db_path=temp_db)
    km_up = next(a for a in updated_agents if a["name"] == "Krishi Mitra")
    fd_up = next(a for a in updated_agents if a["name"] == "Fasal Doctor")

    assert km_up["total"] == 1
    assert km_up["successful"] == 1
    assert fd_up["total"] == 1
    assert fd_up["successful"] == 1


@pytest.mark.asyncio
async def test_api_analytics_includes_tool_and_agent_stats(temp_db):
    """Test GET /api/analytics returns unified response with tool_stats and agent_stats."""
    app = api_server.create_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.get("/api/analytics")
        assert resp.status == 200
        data = await resp.json()

        assert "total_calls" in data
        assert "tool_stats" in data
        assert "agent_stats" in data
        assert "mandi" in data["tool_stats"]
        assert "weather" in data["tool_stats"]
        assert len(data["agent_stats"]) == 2
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_sse_event_broadcast():
    """Test that broadcast_event dispatches events to connected SSE client queues."""
    test_queue = asyncio.Queue()
    api_server._sse_clients.add(test_queue)

    try:
        await api_server.broadcast_event("new_call_logged", {"call_id": "CALL-123"})
        event = await asyncio.wait_for(test_queue.get(), timeout=2.0)
        assert event["event"] == "new_call_logged"
        assert event["data"]["call_id"] == "CALL-123"
    finally:
        api_server._sse_clients.discard(test_queue)
