import logging

from . import bot, config


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    bot.build(config.load()).run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
