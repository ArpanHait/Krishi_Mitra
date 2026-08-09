import contextlib
import os
import tempfile

import pytest

from db import get_farmer_profile, init_db, upsert_farmer_profile


@pytest.fixture
def memory_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    if os.path.exists(path):
        with contextlib.suppress(Exception):
            os.remove(path)


def test_automatic_basic_memory_and_returning_caller(memory_db):
    """Verify automatic background saving of basic farming facts and returning caller greeting."""
    user_id = "+919876543210"

    # Call 1: Initially new caller (no profile in DB)
    profile_before = get_farmer_profile(user_id, db_path=memory_db)
    assert profile_before is None

    # Agent automatically saves basic facts (name, crop, district, topic) during conversation turn
    facts = {
        "crops_grown": "cotton",
        "district": "Burdwan, West Bengal",
        "last_topic": "cotton pest control",
        "language_preference": "english",
    }
    upsert_farmer_profile(
        user_id=user_id,
        name="Ramesh",
        facts=facts,
        consent=True,
        db_path=memory_db,
    )

    # Verify basic facts are saved in DB
    saved = get_farmer_profile(user_id, db_path=memory_db)
    assert saved is not None
    assert saved["name"] == "Ramesh"
    assert saved["crops_grown"] == "cotton"

    # Call 2: Returning caller connects -> automatically welcomed back by name and topic
    returning_profile = get_farmer_profile(user_id, db_path=memory_db)
    assert returning_profile is not None
    assert returning_profile["name"] == "Ramesh"

    lang_pref = str(returning_profile.get("language_preference", "")).lower()
    topic = returning_profile.get("last_topic") or returning_profile.get("crops_grown")
    if lang_pref == "english":
        greeting = f"Hello {returning_profile['name']}! Last time we spoke about your {topic}. Did that help? How is your field doing today?"
    else:
        greeting = f"नमस्ते {returning_profile['name']} जी! पिछली बार हमने {topic} के बारे में चर्चा की थी।"

    assert "Ramesh" in greeting
    assert "cotton" in greeting
