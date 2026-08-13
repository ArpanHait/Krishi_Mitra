import asyncio
import email
from email.header import decode_header
import imaplib
import logging
import multiprocessing
import os
import re
from pathlib import Path

from dotenv import load_dotenv

import db

logger = logging.getLogger("email_listener")

# Ensure environment variables are loaded
load_dotenv(".env.local")
load_dotenv(".env")


def decode_mime_header(header_value: str) -> str:
    """Decodes MIME encoded-word headers (e.g. Base64 or Quoted-Printable) into plain UTF-8 text."""
    if not header_value:
        return ""
    try:
        parts = []
        for text, encoding in decode_header(header_value):
            if isinstance(text, bytes):
                parts.append(text.decode(encoding or "utf-8", errors="ignore"))
            else:
                parts.append(str(text))
        return " ".join(parts)
    except Exception:
        return str(header_value)


async def check_support_replies(db_path: Path | str = db.DB_PATH) -> None:
    """Checks IMAP inbox silently for replies from support officer containing Ticket IDs."""
    sender_email = os.getenv("SMTP_SENDER_EMAIL")
    sender_password = os.getenv("SMTP_SENDER_PASSWORD")

    if not sender_email or not sender_password:
        msg = "[IMAP Poller]: Missing SMTP_SENDER_EMAIL or SMTP_SENDER_PASSWORD in environment."
        logger.warning(msg)
        return

    def fetch_emails():
        try:
            # Set 5-second socket timeout to prevent blocking
            mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=5)
            mail.login(sender_email, sender_password)
            mail.select("inbox")

            # Search ALL inbox emails
            status, messages = mail.search(None, "ALL")
            if status != "OK" or not messages or not messages[0]:
                mail.logout()
                return

            email_ids = messages[0].split()
            # Fast, lightweight scan: strictly last 5 emails only
            recent_ids = email_ids[-5:]

            for num in recent_ids:
                _, data = mail.fetch(num, "(RFC822)")
                if not data or not data[0]:
                    continue

                raw_email = data[0][1]
                msg_obj = email.message_from_bytes(raw_email)

                sender_header = decode_mime_header(msg_obj["From"] or "")
                raw_subject = msg_obj["Subject"] or ""
                subject = decode_mime_header(raw_subject)
                body = ""

                if msg_obj.is_multipart():
                    for part in msg_obj.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode(errors="ignore")
                            break
                else:
                    body = msg_obj.get_payload(decode=True).decode(errors="ignore")

                # Search Ticket ID format (e.g., KM-EFD53D) in decoded subject or body
                search_text = f"{subject} {raw_subject} {body}"
                match = re.search(r"KM-[A-F0-9]{6}", search_text, re.IGNORECASE)
                if match:
                    ticket_id = match.group(0).upper()

                    # Clean thread replies (strip previous quoted text)
                    clean_reply = re.split(
                        r"\r?\nOn .* written?:|\r?\nOn .* wrote:|\r?\n---------- Forwarded message ---------",
                        body,
                    )[0].strip()

                    # Fallback if clean_reply is empty or starts with original Ticket ID header
                    if not clean_reply or clean_reply.startswith("Ticket ID:"):
                        clean_reply = body.strip()

                    if clean_reply:
                        # Update SQLite database record silently
                        updated = db.update_officer_reply(
                            ticket_id, clean_reply, db_path=db_path
                        )
                        if updated:
                            logger.info(
                                f"[IMAP Poller SUCCESS]: Found officer reply for Ticket #{ticket_id} from {sender_header}!"
                            )

            mail.logout()
        except Exception as e:
            logger.error(f"[IMAP Poller Error]: {e}")

    # Run blocking IMAP calls in thread pool
    await asyncio.to_thread(fetch_emails)


async def start_periodic_email_polling(
    interval_seconds: int = 45, db_path: Path | str = db.DB_PATH
) -> None:
    """Periodic background task running every interval_seconds silently."""
    logger.info(
        f"[IMAP Poller]: Service initialized. Polling inbox every {interval_seconds}s..."
    )
    while True:
        try:
            await check_support_replies(db_path=db_path)
        except Exception as e:
            logger.error(f"[IMAP Poller Loop Error]: {e}")
        await asyncio.sleep(interval_seconds)


def _run_email_poller_worker(interval_seconds: int, db_path: Path | str) -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(
        start_periodic_email_polling(interval_seconds=interval_seconds, db_path=db_path)
    )


def start_poller_process(
    interval_seconds: int = 45, db_path: Path | str = db.DB_PATH
) -> multiprocessing.Process:
    """Starts periodic IMAP email poller in an isolated background Process."""
    p = multiprocessing.Process(
        target=_run_email_poller_worker,
        args=(interval_seconds, db_path),
        daemon=True,
        name="email_poller_process",
    )
    p.start()
    return p
