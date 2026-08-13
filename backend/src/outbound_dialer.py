import asyncio
import logging
import os
import urllib.parse

from twilio.rest import Client

import db

logger = logging.getLogger("outbound_dialer")


def trigger_twilio_call(
    to_number: str = "",
    topic_context: str = "Agricultural Alert",
    district: str = "Burdwan",
    user_id: str = "default_farmer",
    language: str = "hindi",
    bypass_cooldown: bool = False,
    details: str = "",
) -> dict:
    """Initiate an automated outbound phone call using Twilio API with topic context and 60s cooldown protection."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    twilio_phone = os.getenv("TWILIO_PHONE_NUMBER", "").strip()
    default_my_phone = os.getenv("MY_PHONE_NUMBER", "+918509200280").strip()

    target_number = to_number.strip() if to_number else default_my_phone

    # Anti-spam guardrail: check 60s cooldown if not bypass_cooldown
    if not bypass_cooldown and db.is_phone_in_cooldown(
        target_number, cooldown_seconds=60
    ):
        logger.warning(
            f"Phone number {target_number} is in 60s cooldown window. Suppressing duplicate call."
        )
        return {
            "success": True,
            "suppressed": True,
            "to": target_number,
            "message": "Call suppressed due to 60s rate-limiting cooldown.",
        }

    if not account_sid or not auth_token or not twilio_phone:
        logger.warning(
            "Twilio environment credentials missing. Simulating outbound call dispatch."
        )
        return {
            "success": True,
            "simulated": True,
            "to": target_number,
            "topic": topic_context,
            "district": district,
            "message": f"Simulated outbound call to {target_number} regarding {topic_context} in {district}.",
        }

    try:
        client = Client(account_sid, auth_token)

        price_summary = details.strip()

        # Default outbound phone calls to Pure Clear English for crisp audio quality
        if price_summary:
            spoken_text = (
                f"Hello! This is Krishi Mitra calling with your requested update. {price_summary} "
                f"If you wish to stop automated call alerts at any time, simply say Stop alert to Krishi Mitra."
            )
        else:
            spoken_text = (
                f"Hello! This is Krishi Mitra calling. You have an update regarding {topic_context} in {district} district. "
                f"If you wish to stop automated call alerts at any time, simply say Stop alert to Krishi Mitra."
            )

        encoded_msg = urllib.parse.quote(spoken_text)
        twimlet_url = f"https://twimlets.com/message?Message%5B0%5D={encoded_msg}"

        backend_url = os.getenv("BACKEND_API_URL", "").strip().rstrip("/")
        kwargs = {
            "url": twimlet_url,
            "to": target_number,
            "from_": twilio_phone,
        }
        if backend_url:
            kwargs["status_callback"] = f"{backend_url}/api/twilio/status"
            kwargs["status_callback_event"] = [
                "completed",
                "answered",
                "no-answer",
                "busy",
                "failed",
                "canceled",
            ]
            kwargs["status_callback_method"] = "POST"

        call = client.calls.create(**kwargs)

        logger.info(f"Triggered Twilio call SID: {call.sid} to {target_number}")
        return {
            "success": True,
            "call_sid": call.sid,
            "to": target_number,
            "status": call.status,
            "topic": topic_context,
            "district": district,
        }

    except Exception as e:
        logger.error(f"Failed to place Twilio call to {target_number}: {e}")
        # Fallback simulation response so call flow never crashes
        return {
            "success": False,
            "error": str(e),
            "to": target_number,
            "topic": topic_context,
        }


def _get_twilio_client():
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    twilio_phone = os.getenv("TWILIO_PHONE_NUMBER", "").strip()
    if account_sid and auth_token and twilio_phone:
        return Client(account_sid, auth_token), twilio_phone
    return None, ""


async def _verify_call_status_task(
    call_sid: str, topic: str, to_num: str, call_id: int
) -> None:
    """Wait 12s after dialing then check Twilio API to see if call was answered or declined."""
    await asyncio.sleep(12)
    client, twilio_phone = _get_twilio_client()
    if not client or not call_sid or call_sid.startswith("SIM_"):
        return

    try:
        call_obj = client.calls(call_sid).fetch()
        status = str(call_obj.status).lower()
        duration = int(call_obj.duration or 0)
        logger.info(
            f"Verified Twilio call {call_sid}: status={status}, duration={duration}s"
        )

        if status in ("no-answer", "busy", "canceled", "failed"):
            db.log_call_outcome(
                call_type="SIP_OUTBOUND",
                topic=topic,
                duration_seconds=0,
                outcome="FAILED",
                caller_id=f"Phone {to_num or 'User'}",
                failure_reason="Call unanswered or declined by recipient",
            )
            db.mark_scheduled_call_completed(call_id, status="failed")
        else:
            # Answered / Completed / In-progress call
            db.log_call_outcome(
                call_type="SIP_OUTBOUND",
                topic=topic,
                duration_seconds=max(duration, 12),
                outcome="SUCCESS",
                caller_id=f"Phone {to_num or 'User'}",
            )
            db.mark_scheduled_call_completed(call_id, status="completed")
    except Exception as ve:
        logger.warning(f"Failed to verify Twilio call status for {call_sid}: {ve}")


_poller_started = False


async def _poll_due_calls_loop():
    """Background polling loop checking SQLite every 2 seconds for due outbound calls."""
    logger.info("Started SQLite scheduled call poller loop.")
    while True:
        try:
            due_calls = db.get_due_scheduled_calls()
            for call_item in due_calls:
                call_id = call_item["id"]
                to_num = call_item.get("phone_number")
                topic = call_item.get("topic", "")
                district = call_item.get("district", "Burdwan")
                user_id = call_item.get("user_id", "default_farmer")
                lang = call_item.get("language", "hindi")

                # Atomically claim call record first so it is NEVER executed twice
                if not db.claim_due_scheduled_call(call_id):
                    logger.info(
                        f"Scheduled call #{call_id} already claimed by another worker. Skipping."
                    )
                    continue

                # Smart pre-fetcher: Weather API, Mandi API, or Gemini LLM advice
                fetched_details = ""
                try:
                    import tools

                    fetched_details = await tools.prefetch_call_details(
                        topic=topic, district=district, language=lang
                    )
                except Exception as fe:
                    logger.warning(f"Error pre-fetching call details in poller: {fe}")

                logger.info(
                    f"Poller executing claimed call #{call_id} to {to_num} for '{topic}'"
                )
                res = trigger_twilio_call(
                    to_number=to_num,
                    topic_context=topic,
                    district=district,
                    user_id=user_id,
                    language=lang,
                    bypass_cooldown=True,  # Explicitly scheduled by poller
                    details=fetched_details,
                )
                call_sid = res.get("call_sid")
                if call_sid and not call_sid.startswith("SIM_"):
                    # Launch non-blocking status verifier to check if answered vs declined
                    asyncio.create_task(
                        _verify_call_status_task(
                            call_sid=call_sid,
                            topic=topic,
                            to_num=to_num,
                            call_id=call_id,
                        )
                    )
                else:
                    is_success = res.get("success", False) and not res.get(
                        "suppressed", False
                    )
                    db.mark_scheduled_call_completed(
                        call_id, status="completed" if is_success else "failed"
                    )
                    if is_success:
                        db.log_call_outcome(
                            call_type="SIP_OUTBOUND",
                            topic=topic,
                            duration_seconds=15,
                            outcome="SUCCESS",
                            caller_id=f"Phone {to_num or 'User'}",
                        )
                    else:
                        db.log_call_outcome(
                            call_type="SIP_OUTBOUND",
                            topic=topic,
                            duration_seconds=0,
                            outcome="FAILED",
                            caller_id=f"Phone {to_num or 'User'}",
                            failure_reason=res.get("error")
                            or "Call unanswered or declined by recipient",
                        )
        except Exception as e:
            logger.error(f"Error in scheduled call poller: {e}")

        await asyncio.sleep(2)


_poller_tasks: set[asyncio.Task] = set()


def start_scheduled_call_poller():
    """Ensure the background poller is running on the process event loop."""
    global _poller_started
    if _poller_started:
        return
    _poller_started = True
    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(_poll_due_calls_loop())
        _poller_tasks.add(task)
    except RuntimeError:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                task = loop.create_task(_poll_due_calls_loop())
                _poller_tasks.add(task)
        except Exception as e:
            logger.warning(f"Could not attach call poller loop: {e}")
