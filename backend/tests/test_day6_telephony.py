import pytest

import db
import outbound_dialer
import tools


@pytest.fixture
def tmp_db(tmp_path):
    db_file = tmp_path / "test_krishi_day6.db"
    db.init_db(db_file)
    return db_file


def test_db_alert_subscriptions(tmp_db):
    """Test saving and cancelling alert subscriptions in SQLite database."""
    sub = db.save_alert_subscription(
        user_id="test_farmer_1",
        phone_number="+918509200280",
        district="Hooghly",
        alert_type="heavy_rain",
        language="bengali",
        db_path=tmp_db,
    )
    assert sub["id"] is not None
    assert sub["district"] == "Hooghly"
    assert sub["alert_type"] == "heavy_rain"
    assert sub["status"] == "active"
    assert sub["language"] == "bengali"

    active_alerts = db.get_active_alerts(user_id="test_farmer_1", db_path=tmp_db)
    assert len(active_alerts) == 1
    assert active_alerts[0]["alert_type"] == "heavy_rain"

    cancelled = db.cancel_alert_subscription(user_id="test_farmer_1", db_path=tmp_db)
    assert cancelled >= 1

    remaining_alerts = db.get_active_alerts(user_id="test_farmer_1", db_path=tmp_db)
    assert len(remaining_alerts) == 0


def test_db_scheduled_calls(tmp_db):
    """Test saving and retrieving scheduled calls in SQLite database."""
    call = db.save_scheduled_call(
        user_id="test_farmer_sched",
        phone_number="+918509200280",
        topic="Potato Market Prices",
        district="Burdwan",
        language="english",
        delay_seconds=0,
        db_path=tmp_db,
    )
    assert call["id"] is not None
    assert call["status"] == "pending"

    due = db.get_due_scheduled_calls(db_path=tmp_db)
    assert len(due) >= 1
    assert due[0]["id"] == call["id"]

    db.mark_scheduled_call_completed(call["id"], status="completed", db_path=tmp_db)
    due_after = db.get_due_scheduled_calls(db_path=tmp_db)
    assert len(due_after) == 0


def test_atomic_claim_and_cooldown(tmp_db):
    """Test atomic claiming and phone cooldown rate-limiting guardrail."""
    call = db.save_scheduled_call(
        user_id="test_farmer_atomic",
        phone_number="+918509200280",
        topic="Wheat Fertilizer Advice",
        district="Burdwan",
        language="english",
        delay_seconds=0,
        db_path=tmp_db,
    )
    call_id = call["id"]

    # First claim must succeed
    assert db.claim_due_scheduled_call(call_id, db_path=tmp_db) is True

    # Second claim must fail (already claimed/processing)
    assert db.claim_due_scheduled_call(call_id, db_path=tmp_db) is False

    # Check cooldown returns True while in processing
    assert (
        db.is_phone_in_cooldown("+918509200280", cooldown_seconds=60, db_path=tmp_db)
        is True
    )


def test_parse_delay_seconds():
    """Test delay string parsing into integer seconds."""
    assert tools.parse_delay_seconds("10 seconds") == 10
    assert tools.parse_delay_seconds("2 minutes") == 120
    assert tools.parse_delay_seconds("5 sec") == 5
    assert tools.parse_delay_seconds("1 minute") == 60
    assert tools.parse_delay_seconds("10") == 10


@pytest.mark.asyncio
async def test_schedule_outbound_call_confirmations(tmp_db, monkeypatch):
    """Test schedule_outbound_call tool output in English, Hindi, and Bengali."""
    monkeypatch.setattr(db, "DB_PATH", tmp_db)

    # English confirmation
    res_en = await tools.schedule_outbound_call(
        delay_or_time_str="10 seconds",
        topic="potato prices",
        phone_number="+918509200280",
        user_id="test_farmer",
        district="Burdwan",
        language="english",
    )
    assert "Got it! I have scheduled a call for you in 10 seconds" in res_en

    # Hindi confirmation
    res_hi = await tools.schedule_outbound_call(
        delay_or_time_str="10 seconds",
        topic="आलू का भाव",
        phone_number="+918509200280",
        user_id="test_farmer",
        district="Burdwan",
        language="hindi",
    )
    assert "10 सेकंड में Burdwan में आलू का भाव की जानकारी के लिए फोन कॉल करूँगा" in res_hi

    # Bengali confirmation
    res_bn = await tools.schedule_outbound_call(
        delay_or_time_str="10 seconds",
        topic="আলুর দাম",
        phone_number="+918509200280",
        user_id="test_farmer",
        district="Burdwan",
        language="bengali",
    )
    assert "10 সেকেন্ড-এর মধ্যে Burdwan-এ আলুর দাম-এর সংবাদের জন্য ফোন কল করব" in res_bn


@pytest.mark.asyncio
async def test_register_conditional_alert(tmp_db, monkeypatch):
    """Test register_conditional_alert tool output and database insertion."""
    monkeypatch.setattr(db, "DB_PATH", tmp_db)

    res_en = await tools.register_conditional_alert(
        district="Hooghly",
        alert_type="heavy rain",
        phone_number="+918509200280",
        user_id="farmer_h",
        language="english",
    )
    assert "Registered automated alert for heavy rain in Hooghly district." in res_en

    res_hi = await tools.register_conditional_alert(
        district="Burdwan",
        alert_type="भारी बारिश",
        phone_number="+918509200280",
        user_id="farmer_h",
        language="hindi",
    )
    assert "आपका Burdwan जिले के लिए भारी बारिश रजिस्टर्ड हो गया है।" in res_hi

    res_bn = await tools.register_conditional_alert(
        district="Hooghly",
        alert_type="ভারী বৃষ্টি",
        phone_number="+918509200280",
        user_id="farmer_h",
        language="bengali",
    )
    assert "আপনার Hooghly জেলার জন্য ভারী বৃষ্টি রেজিস্টার হয়ে গেছে।" in res_bn


def test_outbound_dialer_trigger(monkeypatch):
    """Test Twilio outbound dialer call trigger and simulated fallback mode."""
    # Test simulation mode when credentials not present
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "")
    res = outbound_dialer.trigger_twilio_call(
        to_number="+918509200280",
        topic_context="Potato Price Alert",
        district="Burdwan",
        language="english",
    )
    assert res["success"] is True
    assert res["simulated"] is True
    assert res["to"] == "+918509200280"


def test_universal_commodity_extraction():
    """Test universal commodity extractor for Apple, Banana, Potato, Paddy, etc."""
    assert tools.extract_commodity_from_topic("apple mandi prices") == "apple"
    assert (
        tools.extract_commodity_from_topic("current market price of Apple in Hoogly?")
        == "apple"
    )
    assert tools.extract_commodity_from_topic("banana rates in Burdwan") == "banana"
    assert tools.extract_commodity_from_topic("paddy market update") == "paddy"
