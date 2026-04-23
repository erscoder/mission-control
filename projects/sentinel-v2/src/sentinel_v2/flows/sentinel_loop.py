"""
SentinelLoopFlow — The Sentinel Loop in CrewAI Flow form.

Uses CrewAI built-ins:
- Flow state (Pydantic BaseModel)
- CrewAI Memory (self.remember / self.recall via Flow)
- @start, @listen, @router, @human_feedback decorators
"""
from datetime import datetime, timezone
import logging
import os
import signal
import threading
from typing import Optional

from crewai.flow.flow import Flow, listen, start, router
from pydantic import BaseModel, Field

log = logging.getLogger("sentinel_v2.flow")


# ── State ────────────────────────────────────────────────────────────────────

class SentinelState(BaseModel):
    """Flow state — lives inside the Flow, serialized on kickoff/resume."""

    cycle_count: int = 0
    current_phase: str = "research"
    last_update: str = ""
    error: Optional[str] = None

    # Research
    opportunities: list[dict] = []
    top_opportunity: Optional[dict] = None

    # Match
    user_profile: dict = {}
    match_score: float = 0.0

    # Build
    draft: Optional[dict] = None
    draft_file: Optional[str] = None
    build_output: Optional[str] = None

    # Approve
    approved: bool = False
    revision_notes: Optional[str] = None
    pending_since: Optional[str] = None

    # Deploy
    deployed: bool = False
    deployed_url: Optional[str] = None
    deployment_id: Optional[str] = None


# ── Main Flow ────────────────────────────────────────────────────────────────

class SentinelLoopFlow(Flow[SentinelState]):
    """
    The Sentinel Loop — fully powered by CrewAI.

    RESEARCH → MATCH → BUILD → APPROVE (human feedback) → DEPLOY
    """

    # ─── Lifecycle ───────────────────────────────────────────────────────

    _shutdown_requested: bool = False

    def __init__(self):
        super().__init__()
        # Set _state directly to avoid the read-only `state` property setter error.
        # Accessing self.state for the first time triggers lazy init from
        # Flow[SentinelState].initial_state_class via _create_initial_state().
        object.__setattr__(self, "_state", SentinelState())
        self._shutdown_requested = False

        # Register signals only on main thread
        try:
            if threading.current_thread() is threading.main_thread():
                signal.signal(signal.SIGTERM, self._on_signal)
                signal.signal(signal.SIGINT, self._on_signal)
        except Exception:
            pass

    def _on_signal(self, signum, frame):
        log.info("Received signal %s — will stop after current cycle", signum)
        self._shutdown_requested = True

    def _touch(self):
        self.state.last_update = datetime.now(timezone.utc).isoformat()

    # ─── Phase 1: RESEARCH ───────────────────────────────────────────────

    @start()
    def start_cycle(self):
        """Begin a new cycle."""
        if self._shutdown_requested:
            log.info("Shutdown requested — skipping start_cycle")
            return

        self.state.cycle_count += 1
        self.state.current_phase = "research"
        self._touch()
        log.info("=== Sentinel Loop Cycle #%d ===", self.state.cycle_count)
        print(f"\n{'='*50}\nCycle #{self.state.cycle_count}\n{'='*50}")

    @listen(start_cycle)
    def run_research(self):
        """Phase 1: Run research crew to scout opportunities."""
        if self._shutdown_requested:
            return

        self.state.current_phase = "research"
        self._touch()
        log.info("Phase 1: RESEARCH")
        print("Phase 1: RESEARCH — scouting web...")

        from sentinel_v2.crews.research_crew.research_crew import research_crew
        from sentinel_v2.dashboard_state import write_state, write_flow_breakdown

        # Emit state update
        write_state(
            cycle=self.state.cycle_count,
            phase="research",
            opportunity=self.state.top_opportunity if self.state.top_opportunity else None,
        )

        write_flow_breakdown(
            cycle=self.state.cycle_count,
            phase="research",
            sub_phase="scouting-opportunities",
            status="running",
            progress=0.3,
            current_task="Scouting web for opportunities",
            pending_tasks=["Analyze opportunities", "Select top opportunity"],
            activity={
                "type": "phase_start",
                "agent": "web-scout",
                "message": "Starting web research for opportunities",
            },
        )

        crew = research_crew()
        result = crew.kickoff(
            inputs={
                "kike_profile": self._get_kike_profile(),
                "cycle": self.state.cycle_count,
            }
        )

        self.state.opportunities = self._parse_opportunities(result)
        self.state.top_opportunity = (
            self.state.opportunities[0] if self.state.opportunities else None
        )

        # Update state after research
        opp_title = self.state.top_opportunity.get("title", "?") if self.state.top_opportunity else None
        write_state(
            cycle=self.state.cycle_count,
            phase="research_completed",
            opportunity=self.state.top_opportunity,
        )

        write_flow_breakdown(
            cycle=self.state.cycle_count,
            phase="research",
            sub_phase="scouting-opportunities",
            status="completed",
            progress=1.0,
            completed_tasks=["Scout web for opportunities", "Fetch top opportunity"],
            pending_tasks=[],
            opportunity_title=opp_title,
            activity={
                "type": "phase_complete",
                "agent": "sentinel",
                "message": f"Research complete — {len(self.state.opportunities)} opportunities found",
            },
        )

        # Store in CrewAI memory
        if self.state.opportunities:
            try:
                self.remember(
                    f"Cycle #{self.state.cycle_count} research: top opportunity = {self.state.top_opportunity.get('title', '?')}",
                    scope="/sentinel/research",
                )
            except Exception as e:
                log.warning("Memory save failed: %s", e)

        self._touch()

    # ─── Phase 2: MATCH ──────────────────────────────────────────────────

    @listen(run_research)
    def run_match(self):
        """Phase 2: Match top opportunity to Kike's profile."""
        if self._shutdown_requested or not self.state.top_opportunity:
            return

        self.state.current_phase = "match"
        self._touch()
        log.info("Phase 2: MATCH")
        print("Phase 2: MATCH — profiling Kike and matching...")

        from sentinel_v2.crews.match_crew.match_crew import match_crew
        from sentinel_v2.dashboard_state import write_state, write_flow_breakdown

        # Emit state update
        write_state(
            cycle=self.state.cycle_count,
            phase="match",
            opportunity=self.state.top_opportunity,
        )

        write_flow_breakdown(
            cycle=self.state.cycle_count,
            phase="match",
            sub_phase="profile-matching",
            status="running",
            progress=0.3,
            current_task="Fetching Kike profile and matching",
            pending_tasks=["Calculate match score"],
            activity={
                "type": "phase_start",
                "agent": "matcher",
                "message": "Starting profile matching",
            },
        )

        crew = match_crew()
        result = crew.kickoff(
            inputs={
                "opportunity": self.state.top_opportunity,
                "kike_profile": self._get_kike_profile(),
            }
        )

        parsed = self._parse_match_result(result)
        self.state.user_profile = parsed.get("profile", self.state.user_profile)
        self.state.match_score = parsed.get("score", 0.0)

        # Store in CrewAI memory
        try:
            self.remember(
                f"Cycle #{self.state.cycle_count} match: score={self.state.match_score}",
                scope="/sentinel/match",
            )
        except Exception as e:
            log.warning("Memory save failed: %s", e)

        # Update state after match
        write_state(
            cycle=self.state.cycle_count,
            phase="match_completed",
            opportunity=self.state.top_opportunity,
        )

        write_flow_breakdown(
            cycle=self.state.cycle_count,
            phase="match",
            sub_phase="profile-matching",
            status="completed",
            progress=1.0,
            completed_tasks=["Fetch Kike profile", "Match opportunity to profile"],
            pending_tasks=[],
            match_score=self.state.match_score,
            activity={
                "type": "phase_complete",
                "agent": "matcher",
                "message": f"Match complete — score: {self.state.match_score}",
            },
        )

        self._touch()

    # ─── Phase 3: BUILD ───────────────────────────────────────────────────

    @listen(run_match)
    def run_build(self):
        """Phase 3: Build micro-business draft with hierarchical crew."""
        if self._shutdown_requested or not self.state.top_opportunity:
            return

        self.state.current_phase = "build"
        self._touch()
        log.info("Phase 3: BUILD")
        print("Phase 3: BUILD — building micro-business draft...")

        from sentinel_v2.crews.build_crew.build_crew import build_crew
        from sentinel_v2.dashboard_state import write_state, write_flow_breakdown

        # Emit state update
        write_state(
            cycle=self.state.cycle_count,
            phase="build",
            opportunity=self.state.top_opportunity,
        )

        write_flow_breakdown(
            cycle=self.state.cycle_count,
            phase="build",
            sub_phase="draft-generation",
            status="running",
            progress=0.3,
            current_task="Generating micro-business draft",
            pending_tasks=["Validate draft", "Write output files"],
            activity={
                "type": "phase_start",
                "agent": "manager",
                "message": "Starting build phase",
            },
        )

        crew = build_crew()
        result = crew.kickoff(
            inputs={
                "opportunity": self.state.top_opportunity,
                "kike_profile": self.state.user_profile,
            }
        )

        self.state.build_output = str(result.raw) if hasattr(result, "raw") else str(result)

        # Update state after build
        write_state(
            cycle=self.state.cycle_count,
            phase="build_completed",
            opportunity=self.state.top_opportunity,
            build_output=self.state.build_output[:1000] if self.state.build_output else "",  # Truncate
        )

        write_flow_breakdown(
            cycle=self.state.cycle_count,
            phase="build",
            sub_phase="draft-generation",
            status="completed",
            progress=1.0,
            completed_tasks=["Generate draft", "Write output files"],
            pending_tasks=[],
            activity={
                "type": "phase_complete",
                "agent": "builder",
                "message": "Build draft complete",
            },
        )

        # Store in CrewAI memory
        try:
            self.remember(
                f"Cycle #{self.state.cycle_count} build: draft complete",
                scope="/sentinel/build",
            )
        except Exception as e:
            log.warning("Memory save failed: %s", e)

        self._touch()

    # ─── Phase 4: APPROVE (human feedback) ───────────────────────────────

    @listen(run_build)
    def request_approval(self) -> str:
        """
        Phase 4: Present draft to Kike for approval.
        Send Telegram notification with inline buttons.
        """
        self.state.current_phase = "approve"
        self.state.pending_since = datetime.now(timezone.utc).isoformat()
        self._touch()
        log.info("Phase 4: APPROVE — waiting for Kike")
        print("Phase 4: APPROVE — sending to Kike for review...")

        summary = self._build_approval_summary()

        # Send Telegram poll
        from sentinel_v2.tools.telegram_tool import TelegramTool
        tool = TelegramTool()
        tool.send_approval_poll(summary, self.state.cycle_count)

        # Store in CrewAI memory
        try:
            self.remember(
                f"Cycle #{self.state.cycle_count} pending approval since {self.state.pending_since}",
                scope="/sentinel/approvals",
            )
        except Exception as e:
            log.warning("Memory save failed: %s", e)

        return "pending"

    @listen(request_approval)
    def check_approval(self) -> str:
        """
        Poll approval state from the shared JSON file written by Telegram callback.
        Blocks until Kike approves/requests revision/times out (1h default).
        """
        from sentinel_v2.tools.approval_state import ApprovalState
        from sentinel_v2.dashboard_state import write_state, write_flow_breakdown

        approval = ApprovalState()
        cycle = self.state.cycle_count

        # Write pending state so Telegram callback can find it
        approval.set_pending(
            cycle=cycle,
            summary=self._build_approval_summary(),
            timeout_seconds=int(os.getenv("SENTINEL_APPROVAL_TIMEOUT_SECONDS", "3600")),
        )

        # Emit state update for approval waiting
        write_state(
            cycle=self.state.cycle_count,
            phase="approve",
            opportunity=self.state.top_opportunity,
            build_output=self.state.build_output[:1000] if self.state.build_output else "",
        )

        write_flow_breakdown(
            cycle=self.state.cycle_count,
            phase="approve",
            sub_phase="human-review",
            status="running",
            progress=0.5,
            current_task="Waiting for Kike approval",
            pending_tasks=["Kike approval", "Deploy to production"],
            activity={
                "type": "awaiting_approval",
                "agent": "sentinel",
                "message": "Awaiting Kike approval on draft",
            },
        )

        import time
        poll_interval = int(os.getenv("SENTINEL_APPROVAL_POLL_INTERVAL", "5"))
        log.info("Waiting for approval (poll every %ds, timeout 1h)...", poll_interval)

        while not self._shutdown_requested:
            if approval.is_stop_requested():
                log.info("Stop requested by Kike")
                self._shutdown_requested = True
                return "stop"

            if approval.is_revison_requested(cycle):
                self.state.approved = False
                self.state.revision_notes = "revision requested"
                self.state.current_phase = "build"
                log.info("Revision requested for cycle #%d", cycle)
                self._touch()
                return "revision"

            if approval.is_approved(cycle):
                self.state.approved = True
                action = approval.get_action(cycle)
                log.info("Cycle #%d %s", cycle, action)
                approval.clear_pending(cycle)
                self._touch()
                return "approved"

            time.sleep(poll_interval)

        # Shutdown while waiting
        log.info("Shutdown while waiting for approval")
        return "stop"

    # ─── Phase 5: DEPLOY ──────────────────────────────────────────────────

    @listen(check_approval)
    def run_deploy(self):
        """Phase 5: Deploy approved build."""
        if not self.state.approved or self._shutdown_requested:
            log.info("Not approved or shutdown — skipping deploy")
            return

        self.state.current_phase = "deploy"
        self._touch()
        log.info("Phase 5: DEPLOY")
        print("Phase 5: DEPLOY — deploying to production...")

        from sentinel_v2.crews.deploy_crew.deploy_crew import deploy_crew
        from sentinel_v2.dashboard_state import write_state, write_flow_breakdown

        # Emit state update for deploy phase
        write_state(
            cycle=self.state.cycle_count,
            phase="deploy",
            opportunity=self.state.top_opportunity,
            build_output=self.state.build_output[:1000] if self.state.build_output else "",
        )

        write_flow_breakdown(
            cycle=self.state.cycle_count,
            phase="deploy",
            sub_phase="deployment",
            status="running",
            progress=0.5,
            current_task="Deploying to production",
            pending_tasks=["Deploy", "Verify deployment"],
            activity={
                "type": "phase_start",
                "agent": "deployer",
                "message": "Starting deployment to production",
            },
        )

        crew = deploy_crew()
        result = crew.kickoff(
            inputs={
                "draft": self.state.build_output,
                "opportunity": self.state.top_opportunity,
            }
        )

        parsed = self._parse_deploy_result(result)
        self.state.deployed = True
        self.state.deployed_url = parsed.get("url")
        self.state.deployment_id = parsed.get("deployment_id")

        try:
            self.remember(
                f"Cycle #{self.state.cycle_count} deployed at {self.state.deployed_url}",
                scope="/sentinel/deployments",
            )
        except Exception as e:
            log.warning("Memory save failed: %s", e)

        self._touch()

    # ─── Loop Router ─────────────────────────────────────────────────────

    @router(check_approval)
    def route_after_approval(self) -> str:
        """
        Router: after approval check, decide next step.
        - approved → deploy
        - revision → run_build (rebuild with feedback)
        - stop → stop
        """
        if self._shutdown_requested or not self.state.approved:
            return "stop"
        return "deploy"

    # ─── Helpers ──────────────────────────────────────────────────────────

    def _get_kike_profile(self) -> dict:
        """Retrieve Kike's profile from CrewAI memory."""
        profile = {
            "name": "Kike (Enrique Rubio)",
            "mission": "Construir una organización autónoma de agentes IA que trabaja 24/7",
            "twitter": "@kikerub",
            "email": "enrique.rubio.developer@gmail.com",
            "skills": ["Next.js", "TypeScript", "Tailwind", "NestJS", "PostgreSQL", "Prisma", "Hyperliquid"],
            "timezone": "Europe/Madrid",
        }

        # Enrich from memory (open ai embedding may fail, just skip)
        try:
            matches = self.recall("Kike profile", limit=5)
            if matches:
                log.info("Enriched Kike profile from memory (%d matches)", len(matches))
        except Exception as e:
            # Memory recall failed (likely OpenAI quota). Skip enrichment.
            log.debug("Memory recall skipped: %s", e)
            matches = []

        return profile

    def _parse_opportunities(self, result) -> list[dict]:
        try:
            raw = result.raw if hasattr(result, "raw") else str(result)
            if isinstance(raw, list):
                return raw
            return []
        except Exception:
            return []

    def _parse_match_result(self, result) -> dict:
        try:
            raw = result.raw if hasattr(result, "raw") else str(result)
            if isinstance(raw, dict):
                return raw
            return {}
        except Exception:
            return {}

    def _parse_deploy_result(self, result) -> dict:
        try:
            raw = result.raw if hasattr(result, "raw") else str(result)
            if isinstance(raw, dict):
                return raw
            return {}
        except Exception:
            return {}

    def _build_approval_summary(self) -> str:
        opp = self.state.top_opportunity or {}
        build_preview = self.state.build_output[:500] if self.state.build_output else "N/A"
        return (
            f"🛠️ *Sentinel V2 — Cycle #{self.state.cycle_count}*\n\n"
            f"📋 *Opportunity:* {opp.get('title', '?')}\n"
            f"📝 *Problem:* {opp.get('problem_statement', '?')}\n\n"
            f"💼 *Build Output:*\n{build_preview}\n\n"
            f"⏱️ *Pending since:* {self.state.pending_since}\n\n"
            f"Choose an option:\n"
            f"✅ Approve — Deploy to production\n"
            f"🔁 Revision — Rebuild with feedback\n"
            f"⏸ Pause — Stop Sentinel"
        )


# ── Entry Points ─────────────────────────────────────────────────────────────

def kickoff():
    """Run the Sentinel Loop once."""
    SentinelLoopFlow().kickoff()


def plot():
    """Visualize the Flow graph."""
    SentinelLoopFlow().plot()


if __name__ == "__main__":
    kickoff()
