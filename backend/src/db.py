import datetime
import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger("krishi_db")

DB_PATH = Path(__file__).parent.parent / "krishi_memory.db"


def get_connection(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | str = DB_PATH) -> None:
    """Initialize SQLite database tables farmer_profiles, alert_subscriptions, and scheduled_calls if they do not exist."""
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
        conn.commit()
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
