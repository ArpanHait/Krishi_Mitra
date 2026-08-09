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
