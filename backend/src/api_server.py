import asyncio
import json
import logging
import threading

from aiohttp import web

import db

logger = logging.getLogger("api_server")


def json_response(data, status=200):
    return web.Response(
        text=json.dumps(data),
        status=status,
        content_type="application/json",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
    )


async def handle_options(request):
    return web.Response(
        status=204,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
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
        return json_response({"success": success})
    except Exception as e:
        logger.error(f"Error in POST /api/escalations/update-status: {e}")
        return json_response({"error": str(e)}, status=500)


def create_app():
    app = web.Application()
    app.router.add_options("/{tail:.*}", handle_options)
    app.router.add_get("/api/escalations", handle_get_escalations)
    app.router.add_get("/api/escalations/pending-count", handle_get_pending_count)
    app.router.add_post("/api/escalations/mark-read", handle_mark_read)
    app.router.add_post("/api/escalations/resolve", handle_resolve)
    app.router.add_post("/api/escalations/update-status", handle_update_status)
    return app


def start_api_server_thread(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Starts the aiohttp REST API server in a background daemon thread."""

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        app = create_app()
        runner = web.AppRunner(app)
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, host, port)
        loop.run_until_complete(site.start())
        print(
            f"🌐 [REST API Server]: Listening for HTTP requests at http://{host}:{port}",
            flush=True,
        )
        logger.info(f"REST API Server running at http://{host}:{port}")
        loop.run_forever()

    t = threading.Thread(target=_run, daemon=True, name="api_server_thread")
    t.start()
