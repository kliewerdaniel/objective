"""Main entry point."""

import asyncio
import signal
import structlog
from pathlib import Path

from src.config import Config
from src.daemon.orchestrator import Orchestrator

logger = structlog.get_logger()


async def main(headless: bool = False):
    from src.config import DATA_DIR
    config_path = DATA_DIR / "config.yaml"
    config = Config.load(str(config_path) if config_path.exists() else None)
    config.ensure_dirs()

    orchestrator = Orchestrator(config, headless=headless)

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: orchestrator.handle_signal(s))

    try:
        await orchestrator.bootstrap()
        await orchestrator.run()
    except Exception as e:
        logger.critical("main.crash", error=str(e))
        raise
    finally:
        await orchestrator.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
