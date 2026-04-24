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

    # Draft tracking (dashboard pipeline id)
    draft_id: Optional[str] = None

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
                "trend_signals": self._get_trend_signals(),
                "operator_capacity": self._get_operator_capacity(),
                "cycle": self.state.cycle_count,
            }
        )

        self.state.opportunities = self._parse_opportunities(result)
        self.state.top_opportunity = (
            self.state.opportunities[0] if self.state.opportunities else None
        )

        # Publish a draft entry to the dashboard pipeline (human will approve/reject)
        if self.state.top_opportunity:
            from sentinel_v2.dashboard_state import write_draft, make_draft_id
            opp = self.state.top_opportunity
            self.state.draft_id = make_draft_id(self.state.cycle_count, opp)
            write_draft(
                draft_id=self.state.draft_id,
                cycle=self.state.cycle_count,
                title=opp.get("title", "Untitled opportunity"),
                tagline=opp.get("tagline") or opp.get("summary") or "",
                description=opp.get("description") or opp.get("solution") or "",
                problem=opp.get("problem") or opp.get("problem_statement") or "",
                solution=opp.get("solution") or "",
                tech_fit=float(opp.get("tech_fit", 0.0) or 0.0),
                complexity=int(opp.get("complexity", 0) or 0),
                estimated_hours=opp.get("estimated_hours"),
                tags=opp.get("tags") or [],
                status="pending",
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

    # ─── Gate 1: DRAFT APPROVAL (dashboard) ──────────────────────────────

    @listen(run_research)
    def wait_for_draft_approval(self) -> str:
        """Block until Kike approves the draft from the dashboard (or rejects it)."""
        if self._shutdown_requested or not self.state.draft_id:
            return "stop"

        from sentinel_v2.dashboard_state import wait_for_draft_status, get_draft, update_draft

        auto = os.getenv("SENTINEL_AUTO_APPROVE", "").lower() in {"1", "true", "yes"}
        if auto:
            update_draft(self.state.draft_id, status="queued")
            log.info("AUTO_APPROVE=1 — draft %s queued without human input", self.state.draft_id)
            return "approved"

        log.info("Waiting for dashboard approval on draft %s", self.state.draft_id)
        status = wait_for_draft_status(
            self.state.draft_id,
            target_statuses={"queued", "approved", "rejected"},
            timeout_seconds=int(os.getenv("SENTINEL_APPROVAL_TIMEOUT_SECONDS", "3600")),
        )
        if status in (None, "rejected"):
            log.info("Draft %s not approved (status=%s) — ending cycle", self.state.draft_id, status)
            self._shutdown_requested = status is None  # timeout stops the loop
            return "rejected"
        return "approved"

    # ─── Phase 2: MATCH ──────────────────────────────────────────────────

    @listen(wait_for_draft_approval)
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
                "operator_capacity": self._get_operator_capacity(),
            }
        )

        parsed = self._parse_match_result(result)
        self.state.user_profile = parsed.get("profile", self.state.user_profile)
        self.state.match_score = parsed.get("score", 0.0)

        if self.state.draft_id:
            from sentinel_v2.dashboard_state import update_draft
            update_draft(
                self.state.draft_id,
                tech_fit=float(self.state.match_score or 0.0),
            )

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

        if self.state.draft_id:
            from sentinel_v2.dashboard_state import update_draft
            update_draft(self.state.draft_id, status="building", build_progress=0.1)

        crew = build_crew()
        result = crew.kickoff(
            inputs={
                "opportunity": self.state.top_opportunity,
                "operator_capacity": self._get_operator_capacity(),
            }
        )

        self.state.build_output = str(result.raw) if hasattr(result, "raw") else str(result)

        if self.state.draft_id:
            from sentinel_v2.dashboard_state import update_draft
            # Move to review first (code-review + security-audit), then built with metrics.
            update_draft(self.state.draft_id, status="review", build_progress=0.7)
            update_draft(
                self.state.draft_id,
                status="built",
                build_progress=1.0,
                coverage_percent=self._extract_metric(result, "coverage_percent"),
                tests_passed=self._extract_metric(result, "tests_passed"),
                tests_total=self._extract_metric(result, "tests_total"),
                issues_count=self._extract_metric(result, "issues_count"),
            )

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
        """Block until the Deploy/Reject gate is resolved via the dashboard."""
        from sentinel_v2.dashboard_state import (
            wait_for_draft_status,
            write_state,
            write_flow_breakdown,
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
            current_task="Waiting for deploy approval",
            pending_tasks=["Dashboard approval", "Deploy to production"],
            activity={
                "type": "awaiting_approval",
                "agent": "sentinel",
                "message": "Built — awaiting deploy approval from dashboard",
            },
        )

        if not self.state.draft_id:
            return "stop"

        auto = os.getenv("SENTINEL_AUTO_APPROVE", "").lower() in {"1", "true", "yes"}
        if auto:
            self.state.approved = True
            log.info("AUTO_APPROVE=1 — deploying draft %s without human input", self.state.draft_id)
            return "approved"

        log.info("Waiting for deploy gate on draft %s", self.state.draft_id)
        status = wait_for_draft_status(
            self.state.draft_id,
            target_statuses={"deployed", "failed"},
            timeout_seconds=int(os.getenv("SENTINEL_APPROVAL_TIMEOUT_SECONDS", "3600")),
        )
        if status == "deployed":
            self.state.approved = True
            return "approved"
        log.info("Deploy gate on %s resolved as %s — stopping cycle", self.state.draft_id, status)
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

        if self.state.draft_id:
            from sentinel_v2.dashboard_state import update_draft
            update_draft(
                self.state.draft_id,
                status="deployed",
                deployment_url=self.state.deployed_url,
                build_progress=1.0,
            )

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

    def _get_operator_capacity(self) -> dict:
        """Execution constraints for the build crew. NOT a personal profile — what the
        agent swarm can ship, not who the operator is. Research/match must stay demand-driven.
        """
        return {
            "build_window_hours": 60,       # 1–2 week solo MVP ceiling
            "max_mvp_features": 8,
            "delivery_stack": {
                "frontend": "Next.js 14 App Router + TypeScript + Tailwind + Radix UI",
                "backend": "Next.js Route Handlers or NestJS; Prisma + PostgreSQL",
                "payments": "Stripe Checkout + webhooks (live from day 1)",
                "auth": "Supabase auth or NextAuth magic link",
                "hosting": "Vercel + Neon/Supabase Postgres",
                "telemetry": "PostHog or Plausible, Sentry for errors",
            },
            "pricing_range": {
                "saas_monthly_usd": [9, 299],
                "one_off_usd": [200, 2000],
            },
            "distribution_budget_usd_per_month": 200,
            "team_size": 1,
            "timezone": "Europe/Madrid",
            "locale_support": ["en", "es"],
        }

    def _get_trend_signals(self) -> list[dict]:
        """Optional seed of demand signals. Fetched from memory if present; empty list is
        valid — the research crew is expected to source signals itself."""
        try:
            matches = self.recall("demand signal", limit=8)
            if matches:
                return [{"source": "memory", "snippet": str(m)[:400]} for m in matches]
        except Exception as e:
            log.debug("Memory recall skipped: %s", e)
        return []

    def _parse_opportunities(self, result) -> list[dict]:
        """Accept list, JSON string (plain/fenced), or CrewOutput with .raw/.pydantic."""
        raw = self._extract_raw(result)
        parsed = self._coerce_json(raw)
        if isinstance(parsed, list):
            return [x for x in parsed if isinstance(x, dict)]
        if isinstance(parsed, dict):
            for key in ("opportunities", "top_opportunities", "items", "results"):
                if isinstance(parsed.get(key), list):
                    return [x for x in parsed[key] if isinstance(x, dict)]
            if "title" in parsed:
                return [parsed]
        return []

    def _parse_match_result(self, result) -> dict:
        raw = self._extract_raw(result)
        parsed = self._coerce_json(raw)
        return parsed if isinstance(parsed, dict) else {}

    def _parse_deploy_result(self, result) -> dict:
        raw = self._extract_raw(result)
        parsed = self._coerce_json(raw)
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _extract_metric(result, key: str):
        raw = SentinelLoopFlow._extract_raw(result)
        if isinstance(raw, dict) and key in raw:
            return raw[key]
        parsed = SentinelLoopFlow._coerce_json(raw)
        if isinstance(parsed, dict) and key in parsed:
            return parsed[key]
        pydantic = getattr(result, "pydantic", None)
        if pydantic is not None:
            value = getattr(pydantic, key, None)
            if value is not None:
                return value
        return None

    @staticmethod
    def _extract_raw(result):
        if result is None:
            return None
        if hasattr(result, "pydantic") and result.pydantic is not None:
            try:
                return result.pydantic.model_dump()
            except Exception:
                pass
        if hasattr(result, "json_dict") and result.json_dict is not None:
            return result.json_dict
        if hasattr(result, "raw"):
            return result.raw
        return result

    @staticmethod
    def _coerce_json(value):
        """Accept dict/list/str. For strings, try plain JSON, fenced ```json blocks,
        then a loose [...] / {...} substring match. Return best-effort parsed value or None."""
        import json
        import re

        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        if not isinstance(value, str):
            try:
                value = str(value)
            except Exception:
                return None

        s = value.strip()
        if not s:
            return None

        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass

        fence = re.search(r"```(?:json)?\s*([\[{].*?[\]}])\s*```", s, re.DOTALL)
        if fence:
            try:
                return json.loads(fence.group(1))
            except json.JSONDecodeError:
                pass

        for pattern in (r"\[[\s\S]*\]", r"\{[\s\S]*\}"):
            m = re.search(pattern, s)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    continue

        return None

    def _build_approval_summary(self) -> str:
        opp = self.state.top_opportunity or {}
        build_preview = self.state.build_output[:500] if self.state.build_output else "N/A"
        title = opp.get("title", "?")
        tagline = opp.get("tagline", "")
        problem = opp.get("problem") or opp.get("problem_statement") or "?"
        icp = opp.get("icp", "?")
        price = opp.get("suggested_price", "?")
        commercial_score = opp.get("commercial_score") or opp.get("tech_fit") or "?"
        return (
            f"🛠️ *Sentinel V2 — Cycle #{self.state.cycle_count}*\n\n"
            f"📋 *{title}*\n"
            f"_{tagline}_\n\n"
            f"🎯 *ICP:* {icp}\n"
            f"💵 *Price:* {price}\n"
            f"📝 *Problem:* {problem}\n"
            f"📊 *Commercial score:* {commercial_score}\n\n"
            f"💼 *Build preview:*\n{build_preview}\n\n"
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
