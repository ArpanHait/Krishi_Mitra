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


def test_log_call_outcome_and_metrics(temp_db):
    """Test log_call_outcome inserts records and get_call_analytics calculates metrics correctly."""
    # 1. Initially 0 calls
    analytics = db.get_call_analytics(db_path=temp_db)
    assert analytics["total_calls"] == 0
    assert analytics["successful_calls"] == 0
    assert analytics["failed_calls"] == 0
    assert analytics["success_rate"] == 0.0
    assert analytics["recent_logs"] == []

    # 2. Log a SUCCESS call
    call_id_1 = db.log_call_outcome(
        call_type="BROWSER",
        topic="Mandi prices: Potato in Burdwan",
        duration_seconds=25,
        outcome="SUCCESS",
        caller_id="Browser User",
        db_path=temp_db,
    )
    assert call_id_1.startswith("CALL-")

    # 3. Log a FAILED call
    call_id_2 = db.log_call_outcome(
        call_type="SIP_OUTBOUND",
        topic="General Inquiry",
        duration_seconds=3,
        outcome="FAILED",
        caller_id="Phone User",
        failure_reason="User disconnected early or enquiry incomplete",
        db_path=temp_db,
    )
    assert call_id_2.startswith("CALL-")

    # 4. Check analytics metrics
    analytics_updated = db.get_call_analytics(db_path=temp_db)
    assert analytics_updated["total_calls"] == 2
    assert analytics_updated["successful_calls"] == 1
    assert analytics_updated["failed_calls"] == 1
    assert analytics_updated["success_rate"] == 50.0
    assert len(analytics_updated["recent_logs"]) == 2
    assert analytics_updated["recent_logs"][0]["call_id"] == call_id_2
    assert analytics_updated["recent_logs"][1]["call_id"] == call_id_1


@pytest.mark.asyncio
async def test_analytics_api_endpoints(temp_db, monkeypatch):
    """Test GET /api/analytics and POST /api/analytics/log-call REST endpoints."""
    # Patch DB_PATH in api_server and db
    monkeypatch.setattr(db, "DB_PATH", temp_db)
    monkeypatch.setattr(api_server.db, "DB_PATH", temp_db)
    db._INITIALIZED_DBS.clear()
    db.init_db(temp_db)

    app = api_server.create_app()
    client = TestClient(TestServer(app))
    await client.start_server()

    # 1. GET /api/analytics initial state
    res = await client.get("/api/analytics")
    assert res.status == 200
    data = await res.json()
    assert data["total_calls"] == 0

    # 2. POST /api/analytics/log-call
    post_res = await client.post(
        "/api/analytics/log-call",
        json={
            "call_type": "BROWSER",
            "topic": "Weather in Hooghly",
            "duration_seconds": 15,
            "outcome": "SUCCESS",
        },
    )
    assert post_res.status == 200
    post_data = await post_res.json()
    assert post_data["success"] is True
    assert post_data["call_id"].startswith("CALL-")

    # 3. GET /api/analytics updated state
    res_updated = await client.get("/api/analytics")
    assert res_updated.status == 200
    data_updated = await res_updated.json()
    assert data_updated["total_calls"] == 1
    assert data_updated["successful_calls"] == 1
    assert data_updated["success_rate"] == 100.0

    await client.close()


def test_clear_all_call_logs(temp_db):
    """Test clearing all call logs resets analytics while keeping farmer profile intact."""
    # 1. Save profile
    db.upsert_farmer_profile(
        "default_farmer", name="Arpan", facts={"crops_grown": "Paddy"}, db_path=temp_db
    )

    # 2. Log call
    db.log_call_outcome(
        call_type="BROWSER",
        topic="Test Call",
        duration_seconds=10,
        outcome="SUCCESS",
        db_path=temp_db,
    )

    # 3. Clear call logs
    deleted = db.clear_all_call_logs(db_path=temp_db)
    assert deleted == 1

    # 4. Verify call analytics are 0
    analytics = db.get_call_analytics(db_path=temp_db)
    assert analytics["total_calls"] == 0
    assert len(analytics["recent_logs"]) == 0

    # 5. Verify farmer profile remains intact!
    profile = db.get_farmer_profile("default_farmer", db_path=temp_db)
    assert profile["name"] == "Arpan"
