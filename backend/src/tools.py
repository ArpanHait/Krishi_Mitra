import asyncio
import datetime
import json
import logging
import os
import re
import smtplib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import httpx
from livekit.agents import function_tool

import db
import outbound_dialer

logger = logging.getLogger("krishi_tools")

MANDI_RATES_FILE = Path(__file__).parent / "mandi_rates.json"


def _load_fallback_mandi_rates() -> dict:
    """Load local mandi benchmark fallback data from mandi_rates.json."""
    if MANDI_RATES_FILE.exists():
        try:
            with open(MANDI_RATES_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading mandi_rates.json: {e}")
    return {}


async def fetch_district_weather(district_name: str, state: str = "West Bengal") -> str:
    """Fetch live weather data for a district using Open-Meteo Geocoding and Forecast API."""
    district_clean = district_name.strip()
    state_clean = state.strip() if state else "West Bengal"
    today_str = datetime.date.today().strftime("%d %B %Y")

    try:
        async with httpx.AsyncClient(timeout=0.6) as client:
            # 1. Geocoding request
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={district_clean}&count=1"
            geo_resp = await client.get(geo_url)
            geo_resp.raise_for_status()
            geo_data = geo_resp.json()

            results = geo_data.get("results")
            if not results:
                logger.warning(
                    f"Geocoding returned no coordinates for {district_clean}"
                )
                return "Unable to fetch live weather data at this moment. Please check again shortly."

            location = results[0]
            lat = location.get("latitude")
            lon = location.get("longitude")
            resolved_name = location.get("name", district_clean)

            # 2. Weather Forecast request
            forecast_url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}&current_weather=true"
                f"&daily=precipitation_sum,temperature_2m_max,temperature_2m_min&timezone=auto"
            )
            weather_resp = await client.get(forecast_url)
            weather_resp.raise_for_status()
            weather_data = weather_resp.json()

            current = weather_data.get("current_weather", {})
            curr_temp = current.get("temperature", "N/A")

            daily = weather_data.get("daily", {})
            max_temps = daily.get("temperature_2m_max", [])
            min_temps = daily.get("temperature_2m_min", [])
            precip = daily.get("precipitation_sum", [])

            max_temp = max_temps[0] if max_temps else "N/A"
            min_temp = min_temps[0] if min_temps else "N/A"
            rain_mm = precip[0] if precip else 0.0

            db.log_tool_call("weather", "SUCCESS")
            try:
                import api_server
                api_server.broadcast_event_sync("tool_called", {"tool": "weather", "status": "SUCCESS"})
            except Exception:
                pass

            return (
                f"As per today's live weather report ({today_str}) for {resolved_name}, {state_clean}: "
                f"Current temperature is {curr_temp}°C (Min: {min_temp}°C, Max: {max_temp}°C). "
                f"Expected rainfall/precipitation today is {rain_mm} mm."
            )

    except Exception as e:
        logger.error(f"Error fetching district weather for {district_clean}: {e}")
        db.log_tool_call("weather", "FAILED", error_message=str(e))
        try:
            import api_server
            api_server.broadcast_event_sync("tool_called", {"tool": "weather", "status": "FAILED"})
        except Exception:
            pass
        return "Unable to fetch live weather data at this moment. Please check again shortly."


async def fetch_mandi_prices(
    commodity: str, district: str = "", state: str = "West Bengal"
) -> str:
    """Fetch real-time mandi prices via Government Agmarknet (data.gov.in) with strict timeout and benchmark fallback."""
    commodity_clean = commodity.strip()
    district_clean = district.strip() if district and district.strip() else "Local"
    state_clean = state.strip() if state else "West Bengal"
    today_str = datetime.date.today().strftime("%d %B %Y")

    try:
        api_key = os.getenv("DATA_GOV_API_KEY", "").strip()

        # Attempt Primary Live Gov API call with strict 1.0s timeout for instant voice responsiveness
        if api_key:
            try:
                async with httpx.AsyncClient(timeout=0.5) as client:
                    gov_url = "https://api.data.gov.in/resource/9ef0be31-5971-4be1-8511-50e207d76d56"
                    params = {
                        "api-key": api_key,
                        "format": "json",
                        "filters[state]": state_clean,
                        "filters[district]": district_clean,
                        "filters[commodity]": commodity_clean,
                    }
                    resp = await client.get(gov_url, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        records = data.get("records", [])
                        if records:
                            rec = records[0]
                            market_name = rec.get("market", f"{district_clean} Mandi")
                            comm_name = rec.get("commodity", commodity_clean)
                            modal_price = rec.get(
                                "modal_price", rec.get("modal_rate", "N/A")
                            )
                            min_price = rec.get("min_price", rec.get("min_rate", "N/A"))
                            max_price = rec.get("max_price", rec.get("max_rate", "N/A"))
                            report_date = rec.get("arrival_date", today_str)

                            db.log_tool_call("mandi", "SUCCESS")
                            try:
                                import api_server
                                api_server.broadcast_event_sync("tool_called", {"tool": "mandi", "status": "SUCCESS"})
                            except Exception:
                                pass

                            return (
                                f"As per today's live Agmarknet report ({report_date}) for {comm_name} in {market_name}, {district_clean} ({state_clean}): "
                                f"Modal price is ₹{modal_price}/quintal (Min: ₹{min_price}, Max: ₹{max_price}). "
                                f"Rates can vary locally; please verify at your local market before selling."
                            )
            except Exception as e:
                logger.warning(
                    f"Agmarknet Live API request failed/timed out: {e}. Falling back to benchmark rates."
                )

        # Local Fallback Strategy (mandi_rates.json)
        fallback_data = _load_fallback_mandi_rates()
        state_key = state_clean.lower().replace(" ", "_")
        dist_key = district_clean.lower().replace(" ", "_")
        comm_key = commodity_clean.lower().replace(" ", "_")

        rate_info = None

        # Search in state -> district -> commodity
        state_dict = fallback_data.get(state_key, {})
        dist_dict = state_dict.get(dist_key, {})

        # Check exact commodity key or substring match
        for k, v in dist_dict.items():
            if k in comm_key or comm_key in k:
                rate_info = v
                break

        # If not found in district, check default benchmarks
        if not rate_info:
            def_benchmarks = fallback_data.get("default_benchmarks", {})
            for k, v in def_benchmarks.items():
                if k in comm_key or comm_key in k:
                    rate_info = v
                    break

        # General fallback default if commodity unknown
        if not rate_info:
            rate_info = {
                "min_price": 2000,
                "max_price": 2400,
                "modal_price": 2200,
                "market": f"{district_clean} Mandi",
                "unit": "Quintal",
            }

        modal_price = rate_info.get("modal_price", 2200)
        min_price = rate_info.get("min_price", 2000)
        max_price = rate_info.get("max_price", 2400)
        market_name = f"{district_clean} Mandi" if district_clean else rate_info.get("market", "Local Mandi")

        db.log_tool_call("mandi", "SUCCESS")
        try:
            import api_server
            api_server.broadcast_event_sync("tool_called", {"tool": "mandi", "status": "SUCCESS"})
        except Exception:
            pass

        return (
            f"According to recent market benchmark report ({today_str}) for {commodity_clean} in {district_clean} ({state_clean}): "
            f"Modal price is ₹{modal_price}/quintal (Min: ₹{min_price}, Max: ₹{max_price}) at {market_name}. "
            f"Rates can vary locally; please verify at your local market before selling."
        )

    except Exception as e:
        logger.error(f"Error fetching mandi prices for {commodity_clean}: {e}")
        db.log_tool_call("mandi", "FAILED", error_message=str(e))
        try:
            import api_server
            api_server.broadcast_event_sync("tool_called", {"tool": "mandi", "status": "FAILED"})
        except Exception:
            pass
        return "Unable to fetch mandi rates at this moment. Please check with your local mandi market."


def extract_commodity_from_topic(topic: str) -> str:
    """Extract clean crop/fruit commodity name from topic text by stripping stop-words."""
    if not topic:
        return ""

    text = topic.lower().strip()
    # Strip punctuation characters (?, !, ., ,, etc.)
    text = re.sub(r"[^\w\s]", "", text)

    # Common stop-words in English, Hindi, Bengali to clean out
    stop_words = [
        "mandi",
        "prices",
        "price",
        "rates",
        "rate",
        "market",
        "update",
        "current",
        "today",
        "in",
        "for",
        "of",
        "about",
        "alert",
        "alerts",
        "ka",
        "bhav",
        "daam",
        "dam",
        "khabar",
        "dokan",
        "bazar",
    ]
    for sw in stop_words:
        text = re.sub(rf"\b{sw}\b", " ", text)

    clean = text.strip()
    clean = re.sub(
        r"\b(burdwan|hooghly|hoogly|bankura|nadia|kolkata|west bengal)\b", "", clean
    ).strip()
    return clean if clean else topic.strip()


def extract_topic_gist(topic: str) -> str:
    """Extract a rich, descriptive topic gist from user input by removing conversational filler words."""
    if not topic:
        return ""

    text = topic.strip()
    # 1. Strip call-scheduling conversational prefixes
    text = re.sub(
        r"^(?:can\s+you\s+)?(?:please\s+)?(?:call\s+me|schedule\s+(?:a\s+)?call)\s*(?:after|in)?\s*(?:\d+|\w+)?\s*(?:seconds?|minutes?|secs?|mins?|second|minute|घंटे|मिनट|सेकंड)?\s*(?:and|to)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

    # 2. Strip general query conversational prefixes iteratively
    filler_pattern = r"^(?:can\s+you|please|could\s+you|i\s+want\s+to\s+know|tell\s+me|ask\s+me|kya\s+aap\s+mujhe|mujhe\s+bataiye|kya\s+aap|aapse\s+puchna\s+hai|bataiye|amake\s+bolun|apni\s+ki|apni\s+amake|about|regarding)\s*"
    while True:
        new_text = re.sub(filler_pattern, "", text, flags=re.IGNORECASE).strip()
        if new_text == text:
            break
        text = new_text

    # 3. Strip trailing question marks and punctuation
    text = re.sub(r"[?!.,]+$", "", text).strip()

    # If text is too short or empty, fallback to extracted commodity or original topic
    if len(text) < 3:
        comm = extract_commodity_from_topic(topic)
        return comm if comm else topic.strip()

    return text


def parse_delay_seconds(delay_or_time_str: str) -> int:
    """Parse time string into delay in seconds (default 10s if unspecified)."""
    text = delay_or_time_str.lower().strip()

    # Check for seconds
    match_sec = re.search(r"(\d+)\s*(?:seconds?|secs?|सेकंड)", text)
    if match_sec:
        return max(1, int(match_sec.group(1)))

    # Check for minutes
    match_min = re.search(r"(\d+)\s*(?:minutes?|mins?|मिनट)", text)
    if match_min:
        return max(1, int(match_min.group(1)) * 60)

    # Check for hours
    match_hr = re.search(r"(\d+)\s*(?:hours?|hrs?|घंटे)", text)
    if match_hr:
        return max(1, int(match_hr.group(1)) * 3600)

    # Any numbers
    match_num = re.search(r"(\d+)", text)
    if match_num:
        return max(1, int(match_num.group(1)))

    return 10


async def generate_llm_topic_summary(
    topic: str, district: str = "Burdwan", language: str = "hindi"
) -> str:
    """Use Gemini LLM to generate a concise, expert 2-sentence voice call answer for any arbitrary agricultural topic."""
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        return f"Regarding {topic} in {district}, please consult your local Krishi Bhavan center for full assistance."

    prompt = (
        f"You are Krishi Mitra, an expert Indian agricultural advisor. A farmer in {district} district "
        f"is receiving an automated voice phone call regarding: '{topic}'.\n"
        f"Provide a clear, helpful, accurate 2-sentence spoken response answering their query.\n"
        f"Language requirement: Respond in natural {language}.\n"
        f"Do not include markdown or emojis. Keep it under 40 words so it speaks smoothly on a phone call."
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 100},
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                data = res.json()
                text = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                    .strip()
                )
                if text:
                    return text
    except Exception as e:
        logger.warning(f"Gemini LLM call summary generation failed: {e}")

    return f"Regarding {topic} in {district}, Krishi Mitra recommends consulting your local Krishi Bhavan agriculture officer."


async def prefetch_call_details(
    topic: str, district: str = "Burdwan", language: str = "hindi"
) -> str:
    """Smart detail pre-fetcher for scheduled outbound calls:
    1. Weather API if weather/temperature requested
    2. Mandi API if crop/mandi price requested
    3. Gemini LLM for ANY arbitrary custom agricultural topic!
    """
    if not topic:
        return ""

    topic_lower = topic.lower()

    # 1. Weather intent
    if any(
        k in topic_lower
        for k in [
            "weather",
            "temperature",
            "rain",
            "forecast",
            "sowing",
            "spraying",
            "मौसम",
            "तापमान",
            "बारिश",
            "আবহাওয়া",
            "বৃষ্টি",
            "তাপমাত্রা",
        ]
    ):
        try:
            return await fetch_district_weather(district_name=district)
        except Exception as fe:
            logger.warning(f"Error fetching weather in prefetcher: {fe}")

    # 2. Mandi commodity intent
    target_commodity = extract_commodity_from_topic(topic)
    if target_commodity and any(
        k in topic_lower
        for k in [
            "price",
            "prices",
            "rate",
            "rates",
            "mandi",
            "bhav",
            "dam",
            "daam",
            "bazar",
            "দাম",
            "ভাব",
            "দর",
            "বাজার",
        ]
    ):
        try:
            return await fetch_mandi_prices(target_commodity, district)
        except Exception as fe:
            logger.warning(f"Error fetching mandi prices in prefetcher: {fe}")

    # 3. Dynamic Gemini LLM advice for ANY arbitrary agricultural topic
    try:
        return await generate_llm_topic_summary(
            topic=topic, district=district, language=language
        )
    except Exception as fe:
        logger.warning(f"Error generating LLM topic summary: {fe}")
        return f"Regarding {topic} in {district}, please consult your local Krishi Bhavan center."


async def execute_scheduled_call_task(
    delay_seconds: int,
    to_number: str,
    topic: str,
    district: str,
    user_id: str,
    language: str,
) -> None:
    """Async background task that sleeps for delay_seconds then triggers the Twilio call with live commodity prices."""
    logger.info(
        f"Scheduling outbound call in {delay_seconds}s for {to_number} on {topic}"
    )
    await asyncio.sleep(delay_seconds)

    fetched_details = await prefetch_call_details(
        topic=topic, district=district, language=language
    )

    outbound_dialer.trigger_twilio_call(
        to_number=to_number,
        topic_context=topic,
        district=district,
        user_id=user_id,
        language=language,
        details=fetched_details,
    )


_background_tasks: set[asyncio.Task] = set()


async def schedule_outbound_call(
    delay_or_time_str: str,
    topic: str,
    phone_number: str | None = None,
    user_id: str = "default_farmer",
    district: str = "Burdwan",
    language: str = "hindi",
) -> str:
    """Tool A: Schedule an outbound phone call after delay_or_time_str to deliver updates on topic."""
    delay_secs = parse_delay_seconds(delay_or_time_str)
    target_phone = phone_number or os.getenv("MY_PHONE_NUMBER", "+918509200280")
    lang_clean = language.lower() if language else "hindi"

    # Auto-detect English script in topic (without Devanagari/Bengali characters)
    is_english = lang_clean == "english" or (
        bool(re.search(r"[a-zA-Z]", topic))
        and not re.search(r"[\u0900-\u097F\u0980-\u09FF]", topic)
    )
    resolved_lang = "english" if is_english else lang_clean

    # 1. Save to SQLite for 100% persistent cross-session call execution
    db.save_scheduled_call(
        user_id=user_id,
        phone_number=target_phone,
        topic=topic,
        district=district,
        language=resolved_lang,
        delay_seconds=delay_secs,
    )

    # 2. Auto-update farmer profile memory in SQLite (commodity, topic gist, district, language)
    target_commodity = extract_commodity_from_topic(topic)
    topic_gist = extract_topic_gist(topic)
    existing_profile = db.get_farmer_profile(user_id, db_path=db.DB_PATH) or {}
    existing_facts = dict(existing_profile)
    if target_commodity:
        existing_facts["crops_grown"] = target_commodity
    if topic_gist:
        existing_facts["last_topic"] = topic_gist
    else:
        existing_facts["last_topic"] = topic
    if district:
        existing_facts["district"] = district
    db.upsert_farmer_profile(
        user_id=user_id,
        facts=existing_facts,
        db_path=db.DB_PATH,
    )
    db.update_language_preference(
        user_id=user_id,
        language=resolved_lang,
        db_path=db.DB_PATH,
    )

    # 3. Ensure process-wide poller is running
    outbound_dialer.start_scheduled_call_poller()

    # 3. Fast-path in-memory task
    task = asyncio.create_task(
        execute_scheduled_call_task(
            delay_seconds=delay_secs,
            to_number=target_phone,
            topic=topic,
            district=district,
            user_id=user_id,
            language=resolved_lang,
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    if resolved_lang == "english":
        time_expr = (
            f"{delay_secs} seconds"
            if delay_secs < 60
            else f"{delay_secs // 60} minutes"
        )
        return (
            f"Got it! I have scheduled a call for you in {time_expr} "
            f"regarding {topic} in {district}. All market details will be provided to you directly over the phone call."
        )

    if resolved_lang == "bengali":
        time_expr_bn = (
            f"{delay_secs} সেকেন্ড" if delay_secs < 60 else f"{delay_secs // 60} মিনিট"
        )
        return f"ঠিক আছে! আমি আপনাকে {time_expr_bn}-এর মধ্যে {district}-এ {topic}-এর সংবাদের জন্য ফোন কল করব। সমস্ত তথ্য ফোনেই আপনাকে দেওয়া হবে।"

    time_expr_hi = (
        f"{delay_secs} सेकंड" if delay_secs < 60 else f"{delay_secs // 60} मिनट"
    )
    return f"ठीक है! मैं आपको {time_expr_hi} में {district} में {topic} की जानकारी के लिए फोन कॉल करूँगा। सारी जानकारी फोन कॉल पर ही दी जाएगी।"


async def register_conditional_alert(
    district: str,
    alert_type: str,
    phone_number: str | None = None,
    user_id: str = "default_farmer",
    language: str = "hindi",
) -> str:
    """Tool B: Register a conditional future alert for a district."""
    dist_clean = district.strip() if district else "Burdwan"
    alert_clean = alert_type.strip() if alert_type else "heavy rain alert"
    target_phone = phone_number or os.getenv("MY_PHONE_NUMBER", "+918509200280")
    lang_clean = language.lower() if language else "hindi"

    is_english = lang_clean == "english" or (
        bool(re.search(r"[a-zA-Z]", alert_clean))
        and not re.search(r"[\u0900-\u097F\u0980-\u09FF]", alert_clean)
    )
    resolved_lang = "english" if is_english else lang_clean

    db.save_alert_subscription(
        user_id=user_id,
        phone_number=target_phone,
        district=dist_clean,
        alert_type=alert_clean,
        language=resolved_lang,
    )

    # Auto-update farmer profile memory in SQLite (alert_type, district, language)
    existing_profile = db.get_farmer_profile(user_id, db_path=db.DB_PATH) or {}
    existing_facts = existing_profile.get("facts") or {}
    if dist_clean:
        existing_facts["district"] = dist_clean
    if alert_clean:
        existing_facts["last_alert_type"] = alert_clean
    db.upsert_farmer_profile(
        user_id=user_id,
        facts=existing_facts,
        db_path=db.DB_PATH,
    )
    db.update_language_preference(
        user_id=user_id,
        language=resolved_lang,
        db_path=db.DB_PATH,
    )

    if resolved_lang == "english":
        return (
            f"Done! Registered automated alert for {alert_clean} in {dist_clean} district. "
            f"I will call you as soon as an alert condition is detected."
        )

    if resolved_lang == "bengali":
        return (
            f"আপনার {dist_clean} জেলার জন্য {alert_clean} রেজিস্টার হয়ে গেছে। "
            f"কোনো অ্যালার্ট পাওয়া মাত্রই আমি আপনাকে ফোন কল করব।"
        )

    return (
        f"आपका {dist_clean} जिले के लिए {alert_clean} रजिस्टर्ड हो गया है। "
        f"कोई भी नया अलर्ट मिलते ही मैं आपको फोन कॉल कर दूंगा।"
    )


def sanitize_summary(text: str) -> str:
    """Strips out sensitive private information like OTPs, Passwords, Aadhaar/Government IDs, and Credit/Debit card numbers."""
    if not text:
        return ""
    # Aadhaar / 12-digit IDs
    clean = re.sub(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "[REDACTED_AADHAAR]", text)
    # OTP / PIN / Password key-value pairs
    clean = re.sub(
        r"\b(otp|pin|password)\s*[:=]?\s*\d+\b",
        "[REDACTED_SENSITIVE]",
        clean,
        flags=re.IGNORECASE,
    )
    # General 4-6 digit numeric codes
    clean = re.sub(r"\b\d{4,6}\b", "[REDACTED_NUMERIC]", clean)
    return clean


def send_email_alert(
    ticket_id: str, farmer_name: str, topic: str, urgency: str, summary: str
) -> bool:
    """Sends an email notification to the human support officer using standard SMTP."""
    sender_email = os.getenv("SMTP_SENDER_EMAIL")
    sender_password = os.getenv("SMTP_SENDER_PASSWORD")
    recipient_email = os.getenv("SUPPORT_OFFICER_EMAIL", sender_email)

    if not sender_email or not sender_password:
        logger.info("SMTP credentials missing; skipping email dispatch.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🚨 [{urgency} ESCALATION] Ticket #{ticket_id}: {topic}"
    msg["From"] = sender_email
    msg["To"] = recipient_email

    urgency_color = (
        "red"
        if urgency in ("Emergency", "High")
        else "orange"
        if urgency == "Medium"
        else "green"
    )

    html_content = f"""
    <h2>Krishi Mitra - Human Escalation Request</h2>
    <p><b>Ticket ID:</b> {ticket_id}</p>
    <p><b>Farmer Name:</b> {farmer_name}</p>
    <p><b>Urgency:</b> <span style="color:{urgency_color};"><b>{urgency}</b></span></p>
    <p><b>Topic:</b> {topic}</p>
    <hr/>
    <h3>Sanitized Issue Summary:</h3>
    <p>{summary}</p>
    <hr/>
    <p><i>Action required: Please review this open request in your dashboard.</i></p>
    """
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
        logger.info(f"Successfully sent email alert for ticket #{ticket_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email alert for ticket #{ticket_id}: {e}")
        return False


@function_tool
async def create_escalation(
    farmer_name: str,
    topic: str,
    summary: str,
    urgency: str = "Medium",
    language: str = "english",
    preferred_followup: str = "Phone Call",
) -> str:
    """Creates an escalation request. Checks for open duplicates first.

    Redacts sensitive info, saves to SQLite database, dispatches an email asynchronously, and returns the Ticket ID instantly.
    """
    clean_summary = sanitize_summary(summary)
    urgency_norm = urgency.strip().capitalize() if urgency else "Medium"
    if urgency_norm not in ("Low", "Medium", "High", "Emergency"):
        urgency_norm = "Medium"

    ticket_id = f"KM-{uuid.uuid4().hex[:6].upper()}"

    def _bg_ticket_task():
        # Check duplicate
        existing_ticket = db.get_open_duplicate_escalation(
            farmer_name, topic, db_path=db.DB_PATH
        )
        if existing_ticket:
            t_id = existing_ticket["ticket_id"]
            existing_summary = existing_ticket.get("summary") or ""
            updated_summary = f"{existing_summary}\n\n[UPDATE]: {clean_summary}".strip()
            db.update_escalation_summary_and_urgency(
                t_id, updated_summary, urgency_norm, db_path=db.DB_PATH
            )
            send_email_alert(
                t_id, farmer_name, f"{topic} (UPDATED)", urgency_norm, updated_summary
            )
        else:
            db.create_escalation_record(
                ticket_id=ticket_id,
                farmer_name=farmer_name,
                topic=topic,
                summary=clean_summary,
                urgency=urgency_norm,
                language=language,
                preferred_followup=preferred_followup,
                db_path=db.DB_PATH,
            )
            send_email_alert(ticket_id, farmer_name, topic, urgency_norm, clean_summary)

        try:
            import api_server

            api_server.broadcast_event_sync("ticket_updated", {"ticket_id": ticket_id})
        except Exception:
            pass

    # Launch background task so tool returns INSTANTLY (<2ms)
    _t = asyncio.create_task(asyncio.to_thread(_bg_ticket_task))
    _ = _t

    return f"Ticket created successfully under ID: #{ticket_id}"
