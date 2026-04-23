"""
Sentinel V2 — Main entry point.

Usage:
    python -m sentinel_v2.main --mode once          # Una iteración
    python -m sentinel_v2.main --mode daemon        # Loop continuo (default)
    python -m sentinel_v2.main --mode plot          # Visualiza el grafo
"""
import argparse
import logging
import os
import sys
from pathlib import Path

# Add sentinel-v2 src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

log = logging.getLogger("sentinel_v2")


def setup_logging():
    level = os.getenv("SENTINEL_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def run_once():
    """Run one full cycle."""
    from sentinel_v2.flows.sentinel_loop import SentinelLoopFlow

    flow = SentinelLoopFlow()
    flow.kickoff()
    log.info("Cycle complete")


def run_daemon():
    """Run Sentinel in daemon mode (loop)."""
    import asyncio
    import threading
    
    logging.basicConfig(level=logging.INFO)
    log.info("Starting Sentinel V2 daemon...")

    from sentinel_v2.flows.sentinel_loop import SentinelLoopFlow
    from sentinel_v2.tools.telegram_tool import TelegramTool

    # Track flow's sleep interval
    interval_hours = float(os.getenv("SENTINEL_LOOP_INTERVAL_HOURS", "1"))
    interval_seconds = interval_hours * 3600

    # Track shutdown signal
    _shutdown = False

    def _on_signal(signum, frame):
        nonlocal _shutdown
        log.info("Received signal %s — will stop after current cycle", signum)
        _shutdown = True

    import signal
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    # Start telegram listener in background
    tool = TelegramTool()
    listener_thread = threading.Thread(target=tool.start_listening, daemon=True)
    listener_thread.start()

    # Approval callback
    def _on_approve(action: str, cycle: int):
        log.info("Telegram approval: %s for cycle %d", action, cycle)

    tool._set_approval_callback(_on_approve)

    async def _run_cycles():
        flow = SentinelLoopFlow()
        cycle = 0

        while not _shutdown:
            cycle += 1
            log.info("=== Cycle #%d ===", cycle)
            print(f"\n{'='*50}\nCycle #{cycle}\n{'='*50}")

            try:
                kickoff_result = flow.kickoff()
                log.info("Cycle #%d complete: %s", cycle, kickoff_result)
            except Exception as e:
                log.error("Cycle #%d failed: %s", cycle, e)
                continue

            # Wait before next cycle
            if not _shutdown:
                log.info("Sleeping %.1fh before next cycle", interval_hours)
                await asyncio.sleep(interval_seconds)

            # Update env if shutdown requested
            if os.getenv("SENTINEL_SHUTDOWN") == "1":
                _shutdown = True

        log.info("Sentinel stopped cleanly")

    asyncio.run(_run_cycles())


def run_plot():
    """Visualize the Flow graph."""
    from sentinel_v2.flows.sentinel_loop import SentinelLoopFlow

    flow = SentinelLoopFlow()
    flow.plot()
    log.info("Flow graph saved")


def main():
    setup_logging()

    parser = argparse.ArgumentParser(
        prog="sentinel-v2",
        description="Sentinel V2 — CrewAI-powered agent swarm",
    )
    parser.add_argument(
        "--mode",
        choices=["once", "daemon", "plot"],
        default="daemon",
        help="Run mode (default: daemon)",
    )
    args = parser.parse_args()

    if args.mode == "once":
        run_once()
    elif args.mode == "daemon":
        run_daemon()
    elif args.mode == "plot":
        run_plot()


if __name__ == "__main__":
    main()
