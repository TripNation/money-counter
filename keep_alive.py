import asyncio
import os
from aiohttp import web

async def handle_ping(request):
    return web.Response(text="Bot is alive and running!")

async def start_web_server():
    """Starts a minimal web server on the port provided by Render (or 8080)."""
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"[Web Server] Listening on port {port} for keep-alive pings.", flush=True)
