import contextlib
import os
import tempfile

import pytest

from db import get_farmer_profile, init_db, upsert_farmer_profile


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    if os.path.exists(path):
        with contextlib.suppress(Exception):
            os.remove(path)


def test_init_db(temp_db):
    profile = get_farmer_profile("test_user_1", db_path=temp_db)
    assert profile is None


def test_upsert_and_get_farmer_profile(temp_db):
    upsert_farmer_profile(
        user_id="+919876543210",
        name="Ramesh Kumar",
        facts={
            "crops_grown": "Paddy, Mustard",
            "land_size": "2 acres",
            "district": "Burdwan, West Bengal",
            "last_topic": "Sub-1 paddy selection",
        },
        consent=True,
        db_path=temp_db,
    )

    profile = get_farmer_profile("+919876543210", db_path=temp_db)
    assert profile is not None
    assert profile["name"] == "Ramesh Kumar"
    assert profile["crops_grown"] == "Paddy, Mustard"
    assert profile["land_size"] == "2 acres"
    assert profile["district"] == "Burdwan, West Bengal"
    assert profile["last_topic"] == "Sub-1 paddy selection"
    assert profile["consent_given"] == 1


def test_update_existing_profile(temp_db):
    upsert_farmer_profile(
        user_id="user_123",
        name="Suresh",
        facts={"district": "Patna"},
        consent=True,
        db_path=temp_db,
    )
    upsert_farmer_profile(
        user_id="user_123",
        name="Suresh",
        facts={"crops_grown": "Wheat"},
        consent=True,
        db_path=temp_db,
    )

    profile = get_farmer_profile("user_123", db_path=temp_db)
    assert profile["district"] == "Patna"
    assert profile["crops_grown"] == "Wheat"


def test_auto_language_turn_overwrites(temp_db):
    """Test Turn 1: English -> Turn 2: Hindi -> Turn 3: Bengali language overwrite rule."""
    from db import update_language_preference

    # Turn 1: User speaks in English
    update_language_preference("farmer_dynamic", "english", db_path=temp_db)
    prof1 = get_farmer_profile("farmer_dynamic", db_path=temp_db)
    assert prof1["language_preference"] == "english"

    # Turn 2: User switches to Hindi
    update_language_preference("farmer_dynamic", "hindi", db_path=temp_db)
    prof2 = get_farmer_profile("farmer_dynamic", db_path=temp_db)
    assert prof2["language_preference"] == "hindi"

    # Turn 3: User switches to Bengali
    update_language_preference("farmer_dynamic", "bengali", db_path=temp_db)
    prof3 = get_farmer_profile("farmer_dynamic", db_path=temp_db)
    assert prof3["language_preference"] == "bengali"


@pytest.mark.asyncio
async def test_auto_commodity_and_location_persistence(temp_db, monkeypatch):
    """Test that scheduling call or alert automatically persists commodity, chemical, fertilizer, and location in SQLite."""
    import tools

    monkeypatch.setattr("db.DB_PATH", temp_db)

    # Schedule call for Urea fertilizer in Hooghly
    await tools.schedule_outbound_call(
        delay_or_time_str="10 seconds",
        topic="Urea fertilizer prices",
        district="Hooghly",
        user_id="farmer_auto_test",
        language="english",
    )

    prof = get_farmer_profile("farmer_auto_test", db_path=temp_db)
    assert prof is not None
    assert prof["district"] == "Hooghly"
    assert prof["crops_grown"] == "urea fertilizer"
    assert prof["last_topic"] == "Urea fertilizer prices"


def test_turn_level_topic_overwrite(temp_db):
    """Test that talking about Apple then Potato Fertilizer correctly updates last_topic in SQLite."""
    upsert_farmer_profile(
        user_id="farmer_turn_test",
        facts={"last_topic": "Apple mandi prices", "crops_grown": "apple"},
        db_path=temp_db,
    )
    prof1 = get_farmer_profile("farmer_turn_test", db_path=temp_db)
    assert prof1["last_topic"] == "Apple mandi prices"

    upsert_farmer_profile(
        user_id="farmer_turn_test",
        facts={
            "last_topic": "potato fertilizer",
            "crops_grown": "potato fertilizer",
        },
        db_path=temp_db,
    )
    prof2 = get_farmer_profile("farmer_turn_test", db_path=temp_db)
    assert prof2["last_topic"] == "potato fertilizer"
    assert prof2["crops_grown"] == "potato fertilizer"


def test_topic_gist_extraction():
    """Test extract_topic_gist cleans conversational fillers while keeping the rich topic gist."""
    import tools

    assert (
        tools.extract_topic_gist(
            "Can you call me after thirty second and tell me the current market price of Apple in Hooghly?"
        )
        == "the current market price of Apple in Hooghly"
    )
    assert (
        tools.extract_topic_gist(
            "Can you tell me about the best fertilizer for potato crops?"
        )
        == "the best fertilizer for potato crops"
    )
