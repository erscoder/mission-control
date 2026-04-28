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

# Pin TMPDIR to a stable location BEFORE any CrewAI/LiteLLM imports. These libs
# cache a lock-file path derived from tempfile.gettempdir() at import time; if
# TMPDIR points to an ephemeral sandbox dir that gets cleaned up between invocations
# we end up with "No such file or directory: '.../.ctx-mode-XXX/crewai:HASH.lock'".
_stable_tmp = Path(os.environ.get("SENTINEL_TMPDIR", "/tmp"))
_stable_tmp.mkdir(parents=True, exist_ok=True)
os.environ["TMPDIR"] = str(_stable_tmp) + "/"
os.environ.setdefault("TMP", str(_stable_tmp))
os.environ.setdefault("TEMP", str(_stable_tmp))

from dotenv import load_dotenv

load_dotenv(override=True)

log = logging.getLogger("sentinel_v2")


def setup_logging():
    level = os.getenv("SENTINEL_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _load_resumable_state():
    """Return a SentinelState from the latest checkpoint, or None.

    Drops the checkpoint and returns None if the draft has reached a terminal
    or wait-state where the loop should NOT resume into the same flow:
      - pending: research surfaced it, waiting for user. Re-running this draft
        would loop on the approval gate. start_cycle's queued-draft pickup
        handles real progress instead.
      - rejected, validated, deployed, rejected_deploy: terminal.
    """
    try:
        from sentinel_v2 import db
        from sentinel_v2.dashboard_state import get_draft
        from sentinel_v2.flows.sentinel_loop import SentinelState
        state_json = db.load_active_flow_checkpoint()
        if state_json is None:
            return None
        state = SentinelState.model_validate_json(state_json)
        if state.deployed or not state.draft_id:
            return None

        # Drop checkpoints whose draft is in a terminal/wait state.
        try:
            draft = get_draft(state.draft_id)
        except Exception:
            draft = None
        terminal = {
            "pending", "rejected", "validated", "deployed",
            "rejected_deploy", "failed",
        }
        if draft and (draft.get("status") or "") in terminal:
            log.info(
                "Dropping stale checkpoint for draft %s (status=%s)",
                state.draft_id, draft.get("status"),
            )
            try:
                db.clear_flow_checkpoint(state.draft_id)
            except Exception:
                pass
            return None

        log.info(
            "Found resumable checkpoint: cycle=%d phase=%s draft=%s",
            state.cycle_count, state.current_phase, state.draft_id,
        )
        return state
    except Exception as e:
        log.warning("Could not load checkpoint: %s", e)
        return None


def _recover_orphaned_drafts() -> None:
    """Mark in-flight drafts as failed on daemon start.

    Skips drafts that have an active checkpoint — those will be resumed.
    """
    import json as _json
    from sentinel_v2.dashboard_state import list_drafts_by_status, update_draft
    from sentinel_v2 import db

    checkpointed: set[str] = set()
    try:
        state_json = db.load_active_flow_checkpoint()
        if state_json:
            data = _json.loads(state_json)
            if data.get("draft_id"):
                checkpointed.add(data["draft_id"])
    except Exception:
        pass

    # "queued" = approved, awaiting daemon pickup → NOT in-flight, leave alone.
    # "pending_deploy" = user clicked approve, awaiting daemon pickup → leave alone too.
    # "rejected_deploy" = terminal user intent, do not touch.
    # Only mark drafts that were actively being processed (had the daemon
    # actively running a phase on them) when the daemon died.
    orphaned_statuses = {"building", "review", "built", "deploying"}
    orphans = list_drafts_by_status(orphaned_statuses)
    for draft in orphans:
        if draft["id"] in checkpointed:
            log.info("Skipping orphan recovery for %s — has active checkpoint (will resume)", draft["id"])
            continue
        update_draft(
            draft["id"],
            status="failed",
            revision_notes="marked failed on daemon restart (was in-flight)",
        )
        log.info(
            "Recovered orphaned draft %s (was %s → failed)",
            draft["id"],
            draft.get("status"),
        )


def run_once():
    """Run one full cycle."""
    from sentinel_v2.flows.sentinel_loop import SentinelLoopFlow

    _recover_orphaned_drafts()
    flow = SentinelLoopFlow()
    resumable = _load_resumable_state()
    if resumable:
        object.__setattr__(flow, "_state", resumable)
    flow.kickoff()
    log.info("Cycle complete")


def run_daemon():
    """Run Sentinel in daemon mode (loop)."""
    import asyncio

    logging.basicConfig(level=logging.INFO)
    log.info("Starting Sentinel V2 daemon...")

    _recover_orphaned_drafts()

    from sentinel_v2.flows.sentinel_loop import SentinelLoopFlow

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

    async def _run_cycles():
        nonlocal _shutdown  # ensure assignments below bind to the enclosing scope
        cycle = 0

        while not _shutdown:
            cycle += 1
            flow = SentinelLoopFlow()  # fresh state each cycle

            resumable = _load_resumable_state()
            if resumable:
                object.__setattr__(flow, "_state", resumable)
            else:
                # Pre-set cycle so start_cycle() increments to the right number
                flow.state.cycle_count = cycle - 1

            log.info("=== Cycle #%d ===", cycle)
            print(f"\n{'='*50}\nCycle #{cycle}\n{'='*50}")

            try:
                kickoff_result = flow.kickoff()
                log.info("Cycle #%d complete: %s", cycle, kickoff_result)
            except Exception as e:
                log.error("Cycle #%d failed: %s", cycle, e)
                continue

            # Skip sleep if there are still queued drafts to process
            if not _shutdown:
                try:
                    from sentinel_v2.dashboard_state import list_drafts_by_status
                    remaining = list_drafts_by_status({"queued"})
                    if remaining:
                        log.info(
                            "%d queued draft(s) remaining — starting next cycle immediately",
                            len(remaining),
                        )
                        continue
                except Exception:
                    pass  # fallback to normal sleep

            # Wait before next cycle, but poll for queued drafts every 30s so
            # the daemon wakes promptly when the user clicks Approve / Retry /
            # Request Changes (any of which can re-queue a draft mid-sleep).
            if not _shutdown:
                poll_interval = min(30.0, interval_seconds)
                log.info(
                    "No queued drafts — sleeping up to %.1fh, polling every %.0fs",
                    interval_hours, poll_interval,
                )
                slept = 0.0
                while slept < interval_seconds and not _shutdown:
                    await asyncio.sleep(poll_interval)
                    slept += poll_interval
                    try:
                        from sentinel_v2.dashboard_state import list_drafts_by_status
                        if list_drafts_by_status({"queued"}):
                            log.info("Queued draft appeared during sleep — waking now")
                            break
                    except Exception:
                        pass

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
