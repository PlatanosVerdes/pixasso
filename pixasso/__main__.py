import asyncio
import logging
import os
import signal

from aiohttp import web
from telegram import Update

from . import bot, config

log = logging.getLogger("pixasso")


async def serve(cfg: config.Config) -> None:
    app = bot.build(cfg)
    async with app:
        await app.start()
        if app.post_init:
            await app.post_init(app)

        async def update(request: web.Request) -> web.Response:
            # Queued, not handled inline: switchboard waits only 15 s and a photo takes longer.
            await app.update_queue.put(Update.de_json(await request.json(), app.bot))
            return web.Response(status=202)

        async def commands(_: web.Request) -> web.Response:
            return web.json_response([{"command": cfg.prefix + name, "description": help}
                                      for name, help in bot.COMMANDS])

        async def healthz(_: web.Request) -> web.Response:
            return web.json_response({"status": "ok"})

        server = web.Application()
        server.add_routes([web.post("/telegram/update", update),
                           web.get("/telegram/commands", commands),
                           web.get("/healthz", healthz)])
        runner = web.AppRunner(server)
        await runner.setup()
        await web.TCPSite(runner, port=cfg.port).start()
        log.info("listening on :%d", cfg.port)

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
        await stop.wait()

        await runner.cleanup()
        await app.stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    cfg = config.load()
    if cfg.push:
        asyncio.run(serve(cfg))
    else:
        bot.build(cfg).run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
