import asyncio
import contextlib
import datetime
import json
import logging
import multiprocessing
import threading

from aiohttp import web

import db

logger = logging.getLogger("api_server")

_sse_clients: set[asyncio.Queue] = set()
_server_loop: asyncio.AbstractEventLoop | None = None


async def broadcast_event(event_type: str, data: dict | None = None) -> None:
    """Broadcast an SSE event to all connected frontend clients."""
    payload = {
        "event": event_type,
        "data": data or {},
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    dead_clients = set()
    for queue in list(_sse_clients):
        try:
            queue.put_nowait(payload)
        except Exception:
            dead_clients.add(queue)
    for q in dead_clients:
        _sse_clients.discard(q)


def broadcast_event_sync(event_type: str, data: dict | None = None) -> None:
    """Thread-safe synchronous helper to broadcast SSE event from background threads/processes."""
    global _server_loop
    payload = {
        "event": event_type,
        "data": data or {},
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    # Always push directly to active client queues if available
    dead_clients = set()
    for queue in list(_sse_clients):
        try:
            queue.put_nowait(payload)
        except Exception:
            dead_clients.add(queue)
    for q in dead_clients:
        _sse_clients.discard(q)

    if _server_loop and _server_loop.is_running():
        with contextlib.suppress(Exception):
            _server_loop.call_soon_threadsafe(
                lambda: asyncio.create_task(broadcast_event(event_type, data))
            )


async def handle_sse(request):
    """SSE endpoint (GET /api/events) for real-time live events pushing to frontend dashboard."""
    global _server_loop
    with contextlib.suppress(Exception):
        _server_loop = asyncio.get_running_loop()

    response = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Bypass-Tunnel-Reminder, localtunnel-bypass-warning",
        },
    )
    await response.prepare(request)
    queue = asyncio.Queue()
    _sse_clients.add(queue)
    try:
        # Send initial connected handshake
        await response.write(b"event: connected\ndata: {}\n\n")
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                event_name = payload.get("event", "message")
                event_data = json.dumps(payload.get("data", {}))
                msg = f"event: {event_name}\ndata: {event_data}\n\n".encode()
                await response.write(msg)
            except asyncio.TimeoutError:
                # Send periodic keep-alive ping to prevent proxy/Undici body timeouts
                await response.write(b": ping\n\n")
    except (asyncio.CancelledError, ConnectionResetError, Exception):
        pass
    finally:
        _sse_clients.discard(queue)
    return response


def json_response(data, status=200):
    return web.Response(
        text=json.dumps(data),
        status=status,
        content_type="application/json",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Bypass-Tunnel-Reminder, localtunnel-bypass-warning",
        },
    )


async def handle_options(request):
    return web.Response(
        status=204,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Bypass-Tunnel-Reminder, localtunnel-bypass-warning",
        },
    )


async def handle_get_escalations(request):
    try:
        tickets = db.get_all_escalations()
        return json_response(tickets)
    except Exception as e:
        logger.error(f"Error in GET /api/escalations: {e}")
        return json_response({"error": str(e)}, status=500)


async def handle_get_pending_count(request):
    try:
        open_count = db.get_pending_escalations_count()
        tickets = db.get_all_escalations()
        unread_count = sum(1 for t in tickets if t.get("has_unread_reply") == 1)
        return json_response(
            {
                "count": open_count,
                "has_unread_replies": unread_count > 0,
                "unread_count": unread_count,
            }
        )
    except Exception as e:
        logger.error(f"Error in GET /api/escalations/pending-count: {e}")
        return json_response({"error": str(e)}, status=500)


async def handle_mark_read(request):
    try:
        body = await request.json()
        ticket_id = body.get("ticket_id")
        if not ticket_id:
            return json_response({"error": "Missing ticket_id"}, status=400)
        success = db.mark_reply_read(ticket_id)
        await broadcast_event("ticket_updated", {"ticket_id": ticket_id})
        return json_response({"success": success})
    except Exception as e:
        logger.error(f"Error in POST /api/escalations/mark-read: {e}")
        return json_response({"error": str(e)}, status=500)


async def handle_resolve(request):
    try:
        body = await request.json()
        ticket_id = body.get("ticket_id")
        if not ticket_id:
            return json_response({"error": "Missing ticket_id"}, status=400)
        success = db.resolve_ticket(ticket_id)
        pruned = db.prune_old_resolved_tickets(limit=3)
        await broadcast_event("ticket_updated", {"ticket_id": ticket_id})
        return json_response({"success": success, "pruned": pruned})
    except Exception as e:
        logger.error(f"Error in POST /api/escalations/resolve: {e}")
        return json_response({"error": str(e)}, status=500)


async def handle_update_status(request):
    try:
        body = await request.json()
        ticket_id = body.get("ticket_id")
        status_val = body.get("status")
        if not ticket_id or not status_val:
            return json_response({"error": "Missing ticket_id or status"}, status=400)
        success = db.update_escalation_status(ticket_id, status_val)
        await broadcast_event("ticket_updated", {"ticket_id": ticket_id, "status": status_val})
        return json_response({"success": success})
    except Exception as e:
        logger.error(f"Error in POST /api/escalations/update-status: {e}")
        return json_response({"error": str(e)}, status=500)


async def handle_sync_email(request):
    try:
        import email_listener

        await email_listener.check_support_replies()
        await broadcast_event("ticket_updated", {})
        return json_response(
            {
                "success": True,
                "message": "Email inbox scanned and database synced successfully.",
            }
        )
    except Exception as e:
        logger.error(f"Error in POST /api/escalations/sync-email: {e}")
        return json_response({"error": str(e)}, status=500)


async def handle_get_analytics(request):
    try:
        analytics = db.get_call_analytics()
        return json_response(analytics)
    except Exception as e:
        logger.error(f"Error in GET /api/analytics: {e}")
        return json_response({"error": str(e)}, status=500)


async def handle_log_call(request):
    try:
        body = await request.json()
        call_type = body.get("call_type", "BROWSER")
        topic = body.get("topic", "General Inquiry")
        duration_seconds = int(body.get("duration_seconds", 0))
        outcome = body.get("outcome", "SUCCESS")
        caller_id = body.get("caller_id", "Browser User")
        failure_reason = body.get("failure_reason")

        call_id = db.log_call_outcome(
            call_type=call_type,
            topic=topic,
            duration_seconds=duration_seconds,
            outcome=outcome,
            caller_id=caller_id,
            failure_reason=failure_reason,
        )
        await broadcast_event("new_call_logged", {"call_id": call_id})
        return json_response({"success": True, "call_id": call_id})
    except Exception as e:
        logger.error(f"Error in POST /api/analytics/log-call: {e}")
        return json_response({"error": str(e)}, status=500)


async def handle_twilio_status(request):
    """Twilio StatusCallback webhook handler. Called automatically by Twilio when phone calls complete or get declined."""
    try:
        try:
            data = await request.post()
        except Exception:
            data = {}

        call_status = str(data.get("CallStatus", "")).lower()
        call_duration = int(data.get("CallDuration") or 0)
        to_number = data.get("To", "User")

        logger.info(
            f"[Twilio Webhook]: CallStatus={call_status}, Duration={call_duration}s, To={to_number}"
        )

        if call_status in ("completed", "in-progress", "answered") or call_duration > 0:
            db.log_call_outcome(
                call_type="SIP_OUTBOUND",
                topic="Outbound Call",
                duration_seconds=max(call_duration, 15),
                outcome="SUCCESS",
                caller_id=f"Phone {to_number}",
            )
            await broadcast_event("new_call_logged", {"status": "SUCCESS"})
        elif call_status in ("no-answer", "busy", "canceled", "failed"):
            db.log_call_outcome(
                call_type="SIP_OUTBOUND",
                topic="Outbound Call",
                duration_seconds=0,
                outcome="FAILED",
                caller_id=f"Phone {to_number}",
                failure_reason="Call unanswered or declined by recipient",
            )
            await broadcast_event("new_call_logged", {"status": "FAILED"})

        return web.Response(text="<Response/>", content_type="text/xml")
    except Exception as e:
        logger.error(f"Error handling Twilio status webhook: {e}")
        return web.Response(text="<Response/>", content_type="text/xml")


def create_app():
    app = web.Application()
    app.router.add_options("/{tail:.*}", handle_options)
    app.router.add_get("/api/events", handle_sse)
    app.router.add_get("/api/escalations", handle_get_escalations)
    app.router.add_get("/api/escalations/pending-count", handle_get_pending_count)
    app.router.add_post("/api/escalations/mark-read", handle_mark_read)
    app.router.add_post("/api/escalations/resolve", handle_resolve)
    app.router.add_post("/api/escalations/update-status", handle_update_status)
    app.router.add_post("/api/escalations/sync-email", handle_sync_email)
    app.router.add_get("/api/analytics", handle_get_analytics)
    app.router.add_post("/api/analytics/log-call", handle_log_call)
    app.router.add_post("/api/twilio/status", handle_twilio_status)
    app.router.add_get("/api/twilio/status", handle_twilio_status)
    return app


def start_api_server_thread(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Starts the aiohttp REST API server in a background daemon thread."""

    def _run():
        global _server_loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _server_loop = loop
        app = create_app()
        runner = web.AppRunner(app)
        loop.run_until_complete(runner.setup())
        try:
            site = web.TCPSite(runner, host, port)
            loop.run_until_complete(site.start())
            print(
                f"🌐 [REST API Server]: Listening for HTTP requests at http://{host}:{port}",
                flush=True,
            )
            logger.info(f"REST API Server running at http://{host}:{port}")
            loop.run_forever()
        except OSError:
            print(
                f"🌐 [REST API Server]: Port {port} is already active.",
                flush=True,
            )

    t = threading.Thread(target=_run, daemon=True, name="api_server_thread")
    t.start()


def _run_api_server_worker(host: str, port: int) -> None:
    global _server_loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _server_loop = loop
    app = create_app()
    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    try:
        site = web.TCPSite(runner, host, port)
        loop.run_until_complete(site.start())
        print(
            f"🌐 [REST API Server]: Listening for HTTP requests at http://{host}:{port}",
            flush=True,
        )
        logger.info(f"REST API Server running at http://{host}:{port}")
        loop.run_forever()
    except OSError:
        print(
            f"🌐 [REST API Server]: Port {port} is already active.",
            flush=True,
        )


def start_api_server_process(
    host: str = "0.0.0.0", port: int = 8080
) -> multiprocessing.Process:
    """Starts the aiohttp REST API server in an isolated background Process."""
    p = multiprocessing.Process(
        target=_run_api_server_worker,
        args=(host, port),
        daemon=True,
        name="api_server_process",
    )
    p.start()
    return p
