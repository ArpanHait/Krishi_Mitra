import asyncio
import email
import imaplib
import logging
import multiprocessing
import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

import db

logger = logging.getLogger("email_listener")

# Ensure environment variables are loaded
load_dotenv(".env.local")
load_dotenv(".env")


async def check_support_replies(db_path: Path | str = db.DB_PATH) -> None:
    """Checks IMAP inbox for replies from support officer containing Ticket IDs."""
    sender_email = os.getenv("SMTP_SENDER_EMAIL")
    sender_password = os.getenv("SMTP_SENDER_PASSWORD")

    if not sender_email or not sender_password:
        msg = "[IMAP Poller]: Missing SMTP_SENDER_EMAIL or SMTP_SENDER_PASSWORD in environment."
        logger.warning(msg)
        print(msg, flush=True)
        return

    def fetch_emails():
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(
                f"[{timestamp}] 📧 [IMAP Poller]: Quick-scanning inbox ({sender_email})...",
                flush=True,
            )

            # Set 5-second socket timeout to prevent blocking
            mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=5)
            mail.login(sender_email, sender_password)
            mail.select("inbox")

            # Check UNSEEN emails first for instant performance
            status, messages = mail.search(None, "UNSEEN")
            if status != "OK" or not messages or not messages[0]:
                # Fallback to last 5 messages if UNSEEN returns empty
                status, messages = mail.search(None, "ALL")

            if status != "OK" or not messages or not messages[0]:
                print(
                    f"[{timestamp}] 📧 [IMAP Poller]: Scan complete. Inbox is empty.",
                    flush=True,
                )
                mail.logout()
                return

            email_ids = messages[0].split()
            # Fast scan: last 5 emails only
            recent_ids = email_ids[-5:]
            matched_count = 0

            for num in recent_ids:
                _, data = mail.fetch(num, "(RFC822)")
                if not data or not data[0]:
                    continue

                raw_email = data[0][1]
                msg_obj = email.message_from_bytes(raw_email)

                sender_header = msg_obj["From"] or ""
                subject = msg_obj["Subject"] or ""
                body = ""

                if msg_obj.is_multipart():
                    for part in msg_obj.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode(errors="ignore")
                            break
                else:
                    body = msg_obj.get_payload(decode=True).decode(errors="ignore")

                # Match Ticket ID format (e.g., KM-8A2F91) in subject or body
                match = re.search(
                    r"KM-[A-F0-9]{6}", subject + " " + body, re.IGNORECASE
                )
                if match:
                    ticket_id = match.group(0).upper()

                    # Clean thread replies (strip previous quoted text)
                    clean_reply = re.split(
                        r"\r?\nOn .* written?:|\r?\nOn .* wrote:|\r?\n---------- Forwarded message ---------",
                        body,
                    )[0].strip()

                    if clean_reply:
                        # Update SQLite database record safely
                        updated = db.update_officer_reply(
                            ticket_id, clean_reply, db_path=db_path
                        )
                        if updated:
                            matched_count += 1
                            success_msg = f"[{timestamp}] ✅ [IMAP Poller SUCCESS]: Found officer reply for Ticket #{ticket_id} from {sender_header}! SQLite updated."
                            logger.info(success_msg)
                            print(success_msg, flush=True)

            mail.logout()
            print(
                f"[{timestamp}] 📧 [IMAP Poller]: Scan finished. Synced {matched_count} ticket replies.",
                flush=True,
            )
        except Exception as e:
            err_msg = f"[IMAP Poller Error]: {e}"
            logger.error(err_msg)
            print(err_msg, flush=True)

    # Run blocking IMAP calls in thread pool
    await asyncio.to_thread(fetch_emails)


async def start_periodic_email_polling(
    interval_seconds: int = 30, db_path: Path | str = db.DB_PATH
) -> None:
    """Periodic background task running every interval_seconds."""
    init_msg = f"🚀 [IMAP Poller]: Service initialized. Polling inbox every {interval_seconds}s..."
    logger.info(init_msg)
    print(init_msg, flush=True)
    while True:
        try:
            await check_support_replies(db_path=db_path)
        except Exception as e:
            err_msg = f"[IMAP Poller Loop Error]: {e}"
            logger.error(err_msg)
            print(err_msg, flush=True)
        await asyncio.sleep(interval_seconds)


def start_poller_process(
    interval_seconds: int = 30, db_path: Path | str = db.DB_PATH
) -> multiprocessing.Process:
    """Starts periodic IMAP email poller in an isolated background Process."""

    def _worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            start_periodic_email_polling(
                interval_seconds=interval_seconds, db_path=db_path
            )
        )

    p = multiprocessing.Process(
        target=_worker, daemon=True, name="email_poller_process"
    )
    p.start()
    return p
