import contextlib
import tempfile
from pathlib import Path

import pytest

import db
import tools


@pytest.fixture
def temp_db(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    db.init_db(db_path)
    monkeypatch.setattr("tools.send_email_alert", lambda *args, **kwargs: True)
    yield db_path
    if db_path.exists():
        with contextlib.suppress(Exception):
            db_path.unlink()


def test_sanitize_summary():
    """Test privacy redaction of Aadhaar, OTP/PIN/Password, and 4-6 digit numeric codes."""
    raw_text = (
        "Farmer Aadhaar is 1234-5678-9012. "
        "Sent OTP: 654321 and password= secret99. "
        "Pest issue in plot 9876."
    )
    clean = tools.sanitize_summary(raw_text)

    assert "[REDACTED_AADHAAR]" in clean
    assert "1234-5678-9012" not in clean
    assert "[REDACTED_SENSITIVE]" in clean or "[REDACTED_NUMERIC]" in clean
    assert "654321" not in clean


@pytest.mark.asyncio
async def test_create_escalation_new(temp_db, monkeypatch):
    """Test creating a new escalation ticket in SQLite."""
    monkeypatch.setattr("db.DB_PATH", temp_db)

    res = await tools.create_escalation(
        farmer_name="Ramesh Kumar",
        topic="Potato Late Blight",
        summary="Leaves turning black with white fungal growth.",
        urgency="High",
        language="english",
        preferred_followup="Phone Call",
    )

    assert "Ticket created successfully under ID: #KM-" in res

    tickets = db.get_all_escalations(db_path=temp_db)
    assert len(tickets) == 1
    t = tickets[0]
    assert t["farmer_name"] == "Ramesh Kumar"
    assert t["topic"] == "Potato Late Blight"
    assert t["urgency"] == "High"
    assert t["status"] == "OPEN"

    count = db.get_pending_escalations_count(db_path=temp_db)
    assert count == 1


@pytest.mark.asyncio
async def test_create_escalation_deduplication(temp_db, monkeypatch):
    """Test that creating a second OPEN ticket for same farmer & topic updates the existing ticket."""
    monkeypatch.setattr("db.DB_PATH", temp_db)

    res1 = await tools.create_escalation(
        farmer_name="Suresh Das",
        topic="Paddy Yellow Stem Borer",
        summary="Initial stem borer attack observed.",
        urgency="Medium",
        language="bengali",
    )
    assert "Ticket created successfully under ID: #KM-" in res1

    # Second call for same farmer and topic while status is OPEN
    res2 = await tools.create_escalation(
        farmer_name="Suresh Das",
        topic="Paddy Yellow Stem Borer",
        summary="Borer damage spread to 20% of the field.",
        urgency="Emergency",
        language="bengali",
    )
    assert "Existing open ticket #KM-" in res2
    assert "updated with new details." in res2

    tickets = db.get_all_escalations(db_path=temp_db)
    assert len(tickets) == 1  # No duplicate ticket row
    t = tickets[0]
    assert t["urgency"] == "Emergency"
    assert "[UPDATE]: Borer damage spread" in t["summary"]


@pytest.mark.asyncio
async def test_escalation_status_update(temp_db, monkeypatch):
    """Test updating escalation ticket status from OPEN to RESOLVED."""
    monkeypatch.setattr("db.DB_PATH", temp_db)

    await tools.create_escalation(
        farmer_name="Anita Roy",
        topic="Wheat Mandi Price Missing",
        summary="Agmarknet prices unavailable for Burdwan.",
        urgency="Low",
    )

    tickets = db.get_all_escalations(db_path=temp_db)
    ticket_id = tickets[0]["ticket_id"]

    # Mark RESOLVED
    ok = db.update_escalation_status(ticket_id, "RESOLVED", db_path=temp_db)
    assert ok is True

    pending_count = db.get_pending_escalations_count(db_path=temp_db)
    assert pending_count == 0

    updated_tickets = db.get_all_escalations(db_path=temp_db)
    assert updated_tickets[0]["status"] == "RESOLVED"
