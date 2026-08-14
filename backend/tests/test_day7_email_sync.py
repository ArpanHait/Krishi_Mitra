import contextlib
import tempfile
import time
from pathlib import Path

import pytest

import db


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


def test_db_schema_columns(temp_db):
    """Test that officer_response and has_unread_reply columns are present in escalations table."""
    db.init_db(temp_db)
    with db.get_connection(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(escalations)")
        cols = [row[1] for row in cursor.fetchall()]
        assert "officer_response" in cols
        assert "has_unread_reply" in cols


def test_update_officer_reply_and_mark_read(temp_db):
    """Test updating officer response and clearing unread reply status."""
    db.create_escalation_record(
        ticket_id="KM-TST101",
        farmer_name="Ramesh Kumar",
        topic="Potato Blight",
        summary="Late blight on leaves",
        urgency="High",
        language="english",
        db_path=temp_db,
    )

    success = db.update_officer_reply(
        ticket_id="KM-TST101",
        reply_text="Please spray Mancozeb 75% WP @ 2g/liter of water immediately.",
        db_path=temp_db,
    )
    assert success is True

    tickets = db.get_all_escalations(db_path=temp_db)
    assert len(tickets) == 1
    t = tickets[0]
    assert t["status"] == "OFFICER_REPLIED"
    assert t["has_unread_reply"] == 1
    assert "Mancozeb" in t["officer_response"]

    # Mark as read
    read_success = db.mark_reply_read("KM-TST101", db_path=temp_db)
    assert read_success is True

    tickets_after = db.get_all_escalations(db_path=temp_db)
    assert tickets_after[0]["has_unread_reply"] == 0


def test_prune_old_resolved_tickets_limit_3(temp_db):
    """Test that resolving tickets auto-prunes older RESOLVED tickets keeping max 3."""
    # Create 5 tickets
    for i in range(1, 6):
        db.create_escalation_record(
            ticket_id=f"KM-00{i}",
            farmer_name=f"Farmer {i}",
            topic="Crop Issue",
            summary="Issue description",
            urgency="Medium",
            language="english",
            db_path=temp_db,
        )

    # Resolve all 5 tickets sequentially
    for i in range(1, 6):
        db.resolve_ticket(f"KM-00{i}", db_path=temp_db)
        time.sleep(0.01)

    resolved_tickets = [
        t for t in db.get_all_escalations(db_path=temp_db) if t["status"] == "RESOLVED"
    ]
    # Should retain at most 3 resolved tickets (KM-003, KM-004, KM-005)
    assert len(resolved_tickets) == 3
    retained_ids = {t["ticket_id"] for t in resolved_tickets}
    assert "KM-001" not in retained_ids
    assert "KM-002" not in retained_ids
    assert "KM-005" in retained_ids


def test_update_officer_reply_skip_resolved_and_duplicate(temp_db):
    """Test that update_officer_reply returns False when ticket is RESOLVED or reply is duplicate."""
    db.create_escalation_record(
        ticket_id="KM-SKP999",
        farmer_name="Suresh Kumar",
        topic="Wheat Rust",
        summary="Yellow rust on leaves",
        urgency="High",
        language="english",
        db_path=temp_db,
    )

    # First update succeeds
    first_res = db.update_officer_reply(
        ticket_id="KM-SKP999",
        reply_text="Use Propiconazole 25% EC.",
        db_path=temp_db,
    )
    assert first_res is True

    # Second duplicate update returns False (prevents re-flagging unread)
    dup_res = db.update_officer_reply(
        ticket_id="KM-SKP999",
        reply_text="Use Propiconazole 25% EC.",
        db_path=temp_db,
    )
    assert dup_res is False

    # Resolve ticket
    db.resolve_ticket("KM-SKP999", db_path=temp_db)

    # Update on RESOLVED ticket returns False (prevents re-opening)
    res_update = db.update_officer_reply(
        ticket_id="KM-SKP999",
        reply_text="New response after resolved",
        db_path=temp_db,
    )
    assert res_update is False

    # Check status is still RESOLVED
    t = db.get_all_escalations(db_path=temp_db)[0]
    assert t["status"] == "RESOLVED"
