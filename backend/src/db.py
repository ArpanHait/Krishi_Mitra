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
    """Initialize SQLite database table farmer_profiles if it does not exist."""
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
        conn.commit()
    logger.info("Initialized krishi_memory.db successfully.")


def get_farmer_profile(
    user_id: str, db_path: Path | str = DB_PATH
) -> dict[str, Any] | None:
    """Retrieve existing farmer profile by user_id, with fallback to most recently updated consented profile."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        # 1. Try exact match on user_id
        cursor.execute(
            "SELECT * FROM farmer_profiles WHERE user_id = ? AND name IS NOT NULL AND name != ''",
            (user_id,),
        )
        row = cursor.fetchone()
        if row:
            return dict(row)

        # 2. Fallback: Check 'default_farmer' key
        cursor.execute(
            "SELECT * FROM farmer_profiles WHERE user_id = 'default_farmer' AND name IS NOT NULL AND name != ''"
        )
        row = cursor.fetchone()
        if row:
            return dict(row)

        # 3. Fallback: Most recent consented farmer profile
        cursor.execute(
            "SELECT * FROM farmer_profiles WHERE consent_given = 1 AND name IS NOT NULL AND name != '' ORDER BY last_interaction DESC LIMIT 1"
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
    """Update language_preference for user_id and default_farmer in SQLite database."""
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
                UPDATE farmer_profiles
                SET language_preference = ?, last_interaction = ?
                WHERE user_id = ?
                """,
                (lang_clean, now, uid),
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
