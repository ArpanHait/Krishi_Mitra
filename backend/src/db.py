import datetime
import logging
import sqlite3
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger("krishi_db")

DB_PATH = Path(__file__).parent.parent / "krishi_memory.db"


def get_connection(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


_INITIALIZED_DBS: set[str] = set()


def init_db(db_path: Path | str = DB_PATH) -> None:
    """Initialize SQLite database tables for farmer profiles, alert subscriptions, and scheduled calls."""
    path_key = str(db_path)
    if path_key in _INITIALIZED_DBS:
        return

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS farmer_profiles (
                user_id TEXT PRIMARY KEY,
                name TEXT,
                language_preference TEXT DEFAULT 'hindi',
                crops_grown TEXT,
                land_size TEXT,
                district TEXT,
                irrigation_type TEXT,
                last_topic TEXT,
                consent_given INTEGER DEFAULT 0,
                last_interaction TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS alert_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                phone_number TEXT,
                district TEXT,
                alert_type TEXT,
                status TEXT DEFAULT 'active',
                language TEXT DEFAULT 'hindi',
                created_at TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS scheduled_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                phone_number TEXT,
                topic TEXT,
                district TEXT,
                language TEXT DEFAULT 'hindi',
                scheduled_at TIMESTAMP,
                due_at TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS escalations (
                ticket_id TEXT PRIMARY KEY,
                farmer_name TEXT,
                topic TEXT,
                summary TEXT,
                urgency TEXT CHECK(urgency IN ('Low', 'Medium', 'High', 'Emergency')),
                status TEXT DEFAULT 'OPEN',
                language TEXT,
                preferred_followup TEXT,
                officer_response TEXT DEFAULT NULL,
                has_unread_reply INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS call_logs (
                call_id TEXT PRIMARY KEY,
                caller_id TEXT DEFAULT 'Browser User',
                call_type TEXT CHECK(call_type IN ('BROWSER', 'SIP_OUTBOUND')),
                topic TEXT DEFAULT 'General Inquiry',
                duration_seconds INTEGER DEFAULT 0,
                outcome TEXT CHECK(outcome IN ('SUCCESS', 'FAILED')),
                failure_reason TEXT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute("PRAGMA table_info(escalations)")
        escalation_cols = [row[1] for row in cursor.fetchall()]
        if "officer_response" not in escalation_cols:
            cursor.execute(
                "ALTER TABLE escalations ADD COLUMN officer_response TEXT DEFAULT NULL"
            )
        if "has_unread_reply" not in escalation_cols:
            cursor.execute(
                "ALTER TABLE escalations ADD COLUMN has_unread_reply INTEGER DEFAULT 0"
            )

        # Migrate existing table if old CHECK(status IN...) constraint exists
        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='escalations'"
        )
        tbl_row = cursor.fetchone()
        if tbl_row and tbl_row[0] and "CHECK(status IN" in tbl_row[0]:
            cursor.execute(
                """
                CREATE TABLE escalations_new (
                    ticket_id TEXT PRIMARY KEY,
                    farmer_name TEXT,
                    topic TEXT,
                    summary TEXT,
                    urgency TEXT CHECK(urgency IN ('Low', 'Medium', 'High', 'Emergency')),
                    status TEXT,
                    language TEXT,
                    preferred_followup TEXT,
                    officer_response TEXT DEFAULT NULL,
                    has_unread_reply INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                INSERT INTO escalations_new (
                    ticket_id, farmer_name, topic, summary, urgency, status, language,
                    preferred_followup, officer_response, has_unread_reply, created_at, updated_at
                )
                SELECT ticket_id, farmer_name, topic, summary, urgency, status, language,
                       preferred_followup, officer_response, has_unread_reply, created_at, updated_at
                FROM escalations
                """
            )
            cursor.execute("DROP TABLE escalations")
            cursor.execute("ALTER TABLE escalations_new RENAME TO escalations")
            logger.info(
                "Migrated escalations table schema to allow OFFICER_REPLIED status."
            )

        conn.commit()
    _INITIALIZED_DBS.add(path_key)
    logger.info("Initialized krishi_memory.db tables successfully.")


def get_farmer_profile(
    user_id: str, db_path: Path | str = DB_PATH
) -> dict[str, Any] | None:
    """Retrieve existing farmer profile by user_id, with fallback to most recently updated consented profile."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        # 1. Try exact match on user_id
        cursor.execute(
            "SELECT * FROM farmer_profiles WHERE user_id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        if row:
            return dict(row)

        # 2. Fallback: Check 'default_farmer' key
        cursor.execute("SELECT * FROM farmer_profiles WHERE user_id = 'default_farmer'")
        row = cursor.fetchone()
        if row:
            return dict(row)

        # 3. Fallback: Most recent consented farmer profile
        cursor.execute(
            "SELECT * FROM farmer_profiles WHERE consent_given = 1 ORDER BY last_interaction DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if row:
            return dict(row)

    return None


def upsert_farmer_profile(
    user_id: str,
    name: str = "",
    facts: dict[str, Any] | None = None,
    consent: bool = True,
    db_path: Path | str = DB_PATH,
) -> dict[str, Any]:
    """Upsert farmer profile record into SQLite database."""
    init_db(db_path)
    facts = facts or {}
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    existing = get_farmer_profile(user_id, db_path=db_path) or {}

    updated_name = name or existing.get("name", "")
    lang_pref = facts.get("language_preference") or existing.get(
        "language_preference", "hindi"
    )
    crops = facts.get("crops_grown") or existing.get("crops_grown", "")
    land = facts.get("land_size") or existing.get("land_size", "")
    dist = facts.get("district") or existing.get("district", "")
    irrigation = facts.get("irrigation_type") or existing.get("irrigation_type", "")
    topic = facts.get("last_topic") or existing.get("last_topic", "")
    consent_val = 1 if consent else 0

    target_ids = {user_id, "default_farmer"}

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        for uid in target_ids:
            cursor.execute(
                """
                INSERT INTO farmer_profiles (
                    user_id, name, language_preference, crops_grown, land_size, district,
                    irrigation_type, last_topic, consent_given, last_interaction
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    name = excluded.name,
                    language_preference = excluded.language_preference,
                    crops_grown = excluded.crops_grown,
                    land_size = excluded.land_size,
                    district = excluded.district,
                    irrigation_type = excluded.irrigation_type,
                    last_topic = excluded.last_topic,
                    consent_given = excluded.consent_given,
                    last_interaction = excluded.last_interaction
                """,
                (
                    uid,
                    updated_name,
                    lang_pref,
                    crops,
                    land,
                    dist,
                    irrigation,
                    topic,
                    consent_val,
                    now,
                ),
            )
        conn.commit()

    return get_farmer_profile(user_id, db_path=db_path) or {}


def update_language_preference(
    user_id: str,
    language: str,
    db_path: Path | str = DB_PATH,
) -> None:
    """Update language_preference for user_id and default_farmer in SQLite database via UPSERT."""
    init_db(db_path)
    lang_clean = str(language).strip().lower()
    if not lang_clean:
        return

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    target_ids = {user_id, "default_farmer"}

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        for uid in target_ids:
            cursor.execute(
                """
                INSERT INTO farmer_profiles (user_id, language_preference, last_interaction)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    language_preference = excluded.language_preference,
                    last_interaction = excluded.last_interaction
                """,
                (uid, lang_clean, now),
            )
        conn.commit()


def delete_farmer_profile(
    user_id: str,
    db_path: Path | str = DB_PATH,
) -> None:
    """Delete farmer profile for user_id and default_farmer from SQLite database."""
    init_db(db_path)
    target_ids = {user_id, "default_farmer"}
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        for uid in target_ids:
            cursor.execute("DELETE FROM farmer_profiles WHERE user_id = ?", (uid,))
        conn.commit()
    logger.info(f"Deleted farmer profile for {user_id} and default_farmer.")


def save_alert_subscription(
    user_id: str,
    phone_number: str,
    district: str,
    alert_type: str,
    language: str = "hindi",
    db_path: Path | str = DB_PATH,
) -> dict[str, Any]:
    """Save an alert subscription into SQLite database."""
    init_db(db_path)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    phone_clean = phone_number.strip() if phone_number else ""
    dist_clean = district.strip() if district else "Burdwan"
    alert_clean = alert_type.strip() if alert_type else "weather_alert"
    lang_clean = language.strip().lower() if language else "hindi"

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO alert_subscriptions (
                user_id, phone_number, district, alert_type, status, language, created_at
            ) VALUES (?, ?, ?, ?, 'active', ?, ?)
            """,
            (user_id, phone_clean, dist_clean, alert_clean, lang_clean, now),
        )
        sub_id = cursor.lastrowid
        conn.commit()

    return {
        "id": sub_id,
        "user_id": user_id,
        "phone_number": phone_clean,
        "district": dist_clean,
        "alert_type": alert_clean,
        "status": "active",
        "language": lang_clean,
        "created_at": now,
    }


def cancel_alert_subscription(
    user_id: str,
    db_path: Path | str = DB_PATH,
) -> int:
    """Cancel all active alert subscriptions and pending scheduled calls for a user."""
    init_db(db_path)
    target_ids = {user_id, "default_farmer"}
    updated_count = 0
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        for uid in target_ids:
            cursor.execute(
                "UPDATE alert_subscriptions SET status = 'cancelled' WHERE user_id = ? AND status = 'active'",
                (uid,),
            )
            updated_count += cursor.rowcount
            cursor.execute(
                "UPDATE scheduled_calls SET status = 'cancelled' WHERE user_id = ? AND status = 'pending'",
                (uid,),
            )
            updated_count += cursor.rowcount
        conn.commit()
    logger.info(
        f"Cancelled {updated_count} active alert subscriptions and pending calls for {user_id}."
    )
    return updated_count


def get_active_alerts(
    user_id: str | None = None,
    db_path: Path | str = DB_PATH,
) -> list[dict[str, Any]]:
    """Retrieve active alert subscriptions from SQLite database."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if user_id:
            cursor.execute(
                "SELECT * FROM alert_subscriptions WHERE (user_id = ? OR user_id = 'default_farmer') AND status = 'active' ORDER BY created_at DESC",
                (user_id,),
            )
        else:
            cursor.execute(
                "SELECT * FROM alert_subscriptions WHERE status = 'active' ORDER BY created_at DESC"
            )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def save_scheduled_call(
    user_id: str,
    phone_number: str,
    topic: str,
    district: str = "Burdwan",
    language: str = "hindi",
    delay_seconds: int = 10,
    db_path: Path | str = DB_PATH,
) -> dict[str, Any]:
    """Save a scheduled call record into SQLite database with due_at timestamp and supersede older pending calls."""
    init_db(db_path)
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    due_dt = now_dt + datetime.timedelta(seconds=delay_seconds)
    now_iso = now_dt.isoformat()
    due_iso = due_dt.isoformat()

    phone_clean = phone_number.strip() if phone_number else ""
    topic_clean = topic.strip() if topic else "Agricultural Update"
    dist_clean = district.strip() if district else "Burdwan"
    lang_clean = language.strip().lower() if language else "hindi"

    target_ids = {user_id, "default_farmer"}

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        # Supersede older pending scheduled calls so duplicate calls never stack up
        for uid in target_ids:
            cursor.execute(
                "UPDATE scheduled_calls SET status = 'superseded' WHERE user_id = ? AND status = 'pending'",
                (uid,),
            )
        if phone_clean:
            cursor.execute(
                "UPDATE scheduled_calls SET status = 'superseded' WHERE phone_number = ? AND status = 'pending'",
                (phone_clean,),
            )

        cursor.execute(
            """
            INSERT INTO scheduled_calls (
                user_id, phone_number, topic, district, language, scheduled_at, due_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                user_id,
                phone_clean,
                topic_clean,
                dist_clean,
                lang_clean,
                now_iso,
                due_iso,
            ),
        )
        call_id = cursor.lastrowid
        conn.commit()

    return {
        "id": call_id,
        "user_id": user_id,
        "phone_number": phone_clean,
        "topic": topic_clean,
        "district": dist_clean,
        "language": lang_clean,
        "scheduled_at": now_iso,
        "due_at": due_iso,
        "status": "pending",
    }


def get_due_scheduled_calls(
    db_path: Path | str = DB_PATH,
) -> list[dict[str, Any]]:
    """Retrieve all pending scheduled calls where due_at <= NOW."""
    init_db(db_path)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM scheduled_calls WHERE status = 'pending' AND due_at <= ? ORDER BY due_at ASC",
            (now_iso,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def claim_due_scheduled_call(
    call_id: int,
    db_path: Path | str = DB_PATH,
) -> bool:
    """Atomically claim a pending scheduled call by setting status to 'processing'."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE scheduled_calls SET status = 'processing' WHERE id = ? AND status = 'pending'",
            (call_id,),
        )
        claimed = cursor.rowcount > 0
        conn.commit()
        return claimed


def is_phone_in_cooldown(
    phone_number: str,
    cooldown_seconds: int = 60,
    db_path: Path | str = DB_PATH,
) -> bool:
    """Check if an outbound call was placed or processed for phone_number within the last cooldown_seconds."""
    init_db(db_path)
    phone_clean = phone_number.strip() if phone_number else ""
    if not phone_clean:
        return False

    cutoff = (
        datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(seconds=cooldown_seconds)
    ).isoformat()

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM scheduled_calls
            WHERE phone_number = ? AND status IN ('processing', 'completed') AND (due_at >= ? OR scheduled_at >= ?)
            """,
            (phone_clean, cutoff, cutoff),
        )
        count = cursor.fetchone()[0]
        return count > 0


def mark_scheduled_call_completed(
    call_id: int,
    status: str = "completed",
    db_path: Path | str = DB_PATH,
) -> None:
    """Mark a scheduled call record as completed or failed."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE scheduled_calls SET status = ? WHERE id = ?",
            (status, call_id),
        )
        conn.commit()


def create_escalation_record(
    ticket_id: str,
    farmer_name: str,
    topic: str,
    summary: str,
    urgency: str,
    language: str,
    preferred_followup: str = "Phone Call",
    db_path: Path | str = DB_PATH,
) -> None:
    """Insert a new escalation ticket into SQLite escalations table."""
    init_db(db_path)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO escalations (ticket_id, farmer_name, topic, summary, urgency, status, language, preferred_followup, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?)
            """,
            (
                ticket_id,
                farmer_name,
                topic,
                summary,
                urgency,
                language,
                preferred_followup,
                now,
                now,
            ),
        )
        conn.commit()
    prune_old_resolved_tickets(limit=3, db_path=db_path)


def get_open_duplicate_escalation(
    farmer_name: str,
    topic: str,
    db_path: Path | str = DB_PATH,
) -> dict[str, Any] | None:
    """Check for an existing OPEN duplicate ticket for the same farmer and topic."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM escalations WHERE farmer_name = ? AND topic = ? AND status = 'OPEN'",
            (farmer_name, topic),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def update_escalation_summary_and_urgency(
    ticket_id: str,
    new_summary: str,
    urgency: str,
    db_path: Path | str = DB_PATH,
) -> None:
    """Update summary, urgency, and updated_at timestamp for an existing ticket."""
    init_db(db_path)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE escalations SET summary = ?, urgency = ?, updated_at = ? WHERE ticket_id = ?",
            (new_summary, urgency, now, ticket_id),
        )
        conn.commit()


def get_all_escalations(db_path: Path | str = DB_PATH) -> list[dict[str, Any]]:
    """Retrieve all escalation tickets sorted by created_at DESC."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM escalations ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def get_pending_escalations_count(db_path: Path | str = DB_PATH) -> int:
    """Retrieve count of tickets with status = 'OPEN'."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM escalations WHERE status = 'OPEN'")
        return cursor.fetchone()[0]


def update_escalation_status(
    ticket_id: str,
    status: str,
    db_path: Path | str = DB_PATH,
) -> bool:
    """Update ticket status (e.g. OPEN to RESOLVED). Returns True if updated."""
    init_db(db_path)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE escalations SET status = ?, updated_at = ? WHERE ticket_id = ?",
            (status, now, ticket_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def prune_old_resolved_tickets(limit: int = 3, db_path: Path | str = DB_PATH) -> int:
    """Retains at most limit resolved tickets by deleting the oldest ones based on updated_at timestamp."""
    init_db(db_path)
    query = """
    DELETE FROM escalations 
    WHERE status = 'RESOLVED' 
    AND ticket_id NOT IN (
        SELECT ticket_id FROM escalations 
        WHERE status = 'RESOLVED' 
        ORDER BY updated_at DESC 
        LIMIT ?
    )
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (limit,))
        conn.commit()
        return cursor.rowcount


def update_officer_reply(
    ticket_id: str,
    reply_text: str,
    db_path: Path | str = DB_PATH,
) -> bool:
    """Update ticket with officer's response text and mark status as OFFICER_REPLIED and has_unread_reply = 1."""
    init_db(db_path)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        # Check current status & officer response first to prevent duplicate re-triggers
        cursor.execute(
            "SELECT status, officer_response FROM escalations WHERE ticket_id = ?",
            (ticket_id,),
        )
        row = cursor.fetchone()
        if not row:
            return False

        current_status = row[0]
        current_response = row[1]

        # 1. Do NOT re-open or modify tickets that the user has already marked as RESOLVED
        if current_status == "RESOLVED":
            return False

        # 2. Do NOT re-trigger unread status if officer_response is already identical and status is OFFICER_REPLIED
        if current_response == reply_text and current_status == "OFFICER_REPLIED":
            return False

        cursor.execute(
            """
            UPDATE escalations 
            SET officer_response = ?, status = 'OFFICER_REPLIED', has_unread_reply = 1, updated_at = ?
            WHERE ticket_id = ?
            """,
            (reply_text, now, ticket_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def mark_reply_read(ticket_id: str, db_path: Path | str = DB_PATH) -> bool:
    """Clear unread reply flag for a given ticket_id."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE escalations SET has_unread_reply = 0 WHERE ticket_id = ?",
            (ticket_id,),
        )
        conn.commit()
        return cursor.rowcount > 0


def resolve_ticket(ticket_id: str, db_path: Path | str = DB_PATH) -> bool:
    """Mark ticket status as RESOLVED and run auto-pruning for old resolved tickets beyond limit 3."""
    updated = update_escalation_status(ticket_id, "RESOLVED", db_path=db_path)
    if updated:
        prune_old_resolved_tickets(limit=3, db_path=db_path)
    return updated


def get_latest_escalation(
    farmer_name: str | None = None, db_path: Path | str = DB_PATH
) -> dict[str, Any] | None:
    """Retrieve the most recent escalation ticket for a farmer or overall."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if farmer_name:
            cursor.execute(
                "SELECT * FROM escalations WHERE LOWER(farmer_name) LIKE ? ORDER BY created_at DESC LIMIT 1",
                (f"%{farmer_name.lower()}%",),
            )
        else:
            cursor.execute("SELECT * FROM escalations ORDER BY created_at DESC LIMIT 1")
        row = cursor.fetchone()
        return dict(row) if row else None


def log_call_outcome(
    call_type: str = "BROWSER",
    topic: str = "General Inquiry",
    duration_seconds: int = 0,
    outcome: str = "SUCCESS",
    caller_id: str = "Browser User",
    failure_reason: str | None = None,
    db_path: Path | str | None = None,
) -> str:
    """Log a completed call session outcome and metrics to SQLite database."""
    target_db = db_path or DB_PATH
    init_db(target_db)
    call_id = f"CALL-{uuid.uuid4().hex[:6].upper()}"
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    clean_type = "SIP_OUTBOUND" if "SIP" in str(call_type).upper() else "BROWSER"
    clean_outcome = "SUCCESS" if str(outcome).upper() == "SUCCESS" else "FAILED"
    clean_topic = topic or "General Inquiry"

    with get_connection(target_db) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO call_logs (call_id, caller_id, call_type, topic, duration_seconds, outcome, failure_reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                call_id,
                caller_id,
                clean_type,
                clean_topic,
                int(duration_seconds),
                clean_outcome,
                failure_reason,
                now,
            ),
        )
        conn.commit()
    logger.info(
        f"[Call Analytics]: Logged {clean_type} call #{call_id} - Outcome: {clean_outcome} ({duration_seconds}s)"
    )
    return call_id


def get_call_analytics(db_path: Path | str | None = None) -> dict[str, Any]:
    """Retrieve summary call metrics and recent call logs from SQLite database."""
    target_db = db_path or DB_PATH
    init_db(target_db)
    with get_connection(target_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM call_logs")
        total_calls = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM call_logs WHERE outcome = 'SUCCESS'")
        successful_calls = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*) FROM call_logs
            WHERE outcome = 'FAILED'
            AND (
                failure_reason LIKE '%unanswered%'
                OR failure_reason LIKE '%declined%'
                OR failure_reason LIKE '%busy%'
                OR failure_reason LIKE '%canceled%'
                OR failure_reason LIKE '%pick%'
            )
            """
        )
        declined_calls = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*) FROM call_logs
            WHERE outcome = 'FAILED'
            AND (
                failure_reason IS NULL
                OR (
                    failure_reason NOT LIKE '%unanswered%'
                    AND failure_reason NOT LIKE '%declined%'
                    AND failure_reason NOT LIKE '%busy%'
                    AND failure_reason NOT LIKE '%canceled%'
                    AND failure_reason NOT LIKE '%pick%'
                )
            )
            """
        )
        system_failed_calls = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM call_logs WHERE outcome = 'FAILED'")
        failed_calls = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT call_id, caller_id, call_type, topic, duration_seconds, outcome, failure_reason, created_at
            FROM call_logs
            ORDER BY created_at DESC
            LIMIT 10
            """
        )
        rows = cursor.fetchall()
        recent_logs = [dict(row) for row in rows]

        success_rate = (
            round((successful_calls / total_calls) * 100, 1) if total_calls > 0 else 0.0
        )

        return {
            "total_calls": total_calls,
            "successful_calls": successful_calls,
            "declined_calls": declined_calls,
            "system_failed_calls": system_failed_calls,
            "failed_calls": failed_calls,
            "success_rate": success_rate,
            "recent_logs": recent_logs,
        }


def clear_all_call_logs(db_path: Path | str | None = None) -> int:
    """Delete all records from the call_logs table in SQLite. Returns count of deleted rows."""
    target_db = db_path or DB_PATH
    init_db(target_db)
    with get_connection(target_db) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM call_logs")
        deleted_count = cursor.rowcount
        conn.commit()
    logger.info(f"[Call Analytics]: Cleared all {deleted_count} call log records.")
    return deleted_count
