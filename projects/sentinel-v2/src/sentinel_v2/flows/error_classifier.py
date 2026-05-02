"""Error classification + escalation for the Sentinel build/deploy retry loops.

The retry loops in ``sentinel_loop.py`` retry up to MAX_*_RETRIES on any
exception. Some errors are recoverable with feedback (peer dep mismatch,
syntax error, missing file). Others are external blockers that no amount of
retrying will fix (rate-limit, expired API key, exhausted quota, payment
required). For the latter category we should:

  1. Stop the retry loop immediately to save tokens.
  2. Mark the draft as ``blocked`` (distinct from ``failed``).
  3. Append an entry to ``$SENTINEL_TMPDIR/sentinel_v2_escalations.json``
     (default ``/tmp``) with enough detail for the operator to take a
     one-shot manual action (rotate key, top up balance, wait until reset).

This module is the single source of truth for that classification. Patterns
are intentionally permissive: a false positive only delays a retry; a false
negative wastes the full retry budget and confuses the operator.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger("sentinel_v2.error_classifier")


def resolve_state_path(
    filename: str,
    *,
    env_override: Optional[str] = None,
) -> Path:
    """Resolve a sentinel state file path.

    Order of precedence:

      1. ``$<env_override>`` if that env var name is provided and set
         (legacy callers, e.g. ``SENTINEL_ESCALATIONS_FILE``).
      2. ``$SENTINEL_TMPDIR/<filename>`` if ``SENTINEL_TMPDIR`` is set
         (the docker-compose volume mount).
      3. ``/tmp/<filename>`` as the last-resort default.

    Always returns a :class:`pathlib.Path` (never a string).
    """
    if env_override:
        override_value = os.environ.get(env_override)
        if override_value:
            return Path(override_value)

    tmp_dir = os.environ.get("SENTINEL_TMPDIR")
    if tmp_dir:
        return Path(tmp_dir) / filename

    return Path("/tmp") / filename


ESCALATION_FILE = resolve_state_path(
    "sentinel_v2_escalations.json",
    env_override="SENTINEL_ESCALATIONS_FILE",
)


# Transient network failures (DNS blips, registry hiccups, idle TCP resets,
# upstream socket timeouts) look like exceptions but are not bugs in the
# generated code and are not escalations either. The retry loop already
# tries again with feedback, so the only thing missing was a way to tell
# the operator (and the LLM, downstream) that the error is environmental.
# Patterns are matched against the lowercased error message with re.search.
# Order does not matter here because all patterns share the same category;
# the most generic pattern is listed last as documentation.
RECOVERABLE_PATTERNS: list[tuple[str, str]] = [
    ("transient_network", r"econnrefused"),
    ("transient_network", r"econnreset"),
    ("transient_network", r"etimedout"),
    ("transient_network", r"socket hang up"),
    ("transient_network", r"enotfound"),
    ("transient_network", r"read timeout"),
    ("transient_network", r"network is unreachable"),
    # Generic last-resort. Matches "request timed out", "operation timed
    # out", etc. Kept last so a more specific pattern wins if one is added
    # later that needs different handling.
    ("transient_network", r"timed out"),
]


# Order matters: more specific patterns first. Each pattern is matched against
# the lowercased error message with re.search.
ESCALATION_PATTERNS: list[tuple[str, str]] = [
    # Anthropic / Claude Code Token Plan rate-limit (very specific wording)
    ("blocked_token_plan", r"token plan is designed"),
    ("blocked_token_plan", r"interactive developer workflow"),

    # Generic rate-limit / quota exhaustion
    ("blocked_quota", r"\b429\b"),
    ("blocked_quota", r"rate[_ \-]?limit"),
    ("blocked_quota", r"too many requests"),
    ("blocked_quota", r"quota.*exceed"),
    ("blocked_quota", r"usage limit"),

    # Authentication / authorization
    ("blocked_auth", r"\b401\b"),
    ("blocked_auth", r"\b403\b"),
    ("blocked_auth", r"invalid[_ ]api[_ ]key"),
    ("blocked_auth", r"unauthorized"),
    ("blocked_auth", r"authentication.*fail"),
    ("blocked_auth", r"expired.*token"),
    ("blocked_auth", r"token.*expired"),

    # Payment / balance
    ("blocked_payment", r"\b402\b"),
    ("blocked_payment", r"payment.*required"),
    ("blocked_payment", r"insufficient.*balance"),
    ("blocked_payment", r"insufficient.*funds"),
    ("blocked_payment", r"billing.*issue"),

    # CrewAI agent emitted tool_calls instead of a plain-text final answer
    # after hitting max_iter. CrewAI then tries to set TaskOutput.raw=<list of
    # ChatCompletionMessageFunctionTool> and Pydantic raises because the field
    # requires str. Retrying never helps: a max-iter agent on the next attempt
    # will hit the same wall with the same model. Better to escalate so the
    # operator can either bump the agent's max_iter, simplify the task, or
    # switch to a less tool-call-happy model.
    ("blocked_agent_loop", r"validation error for taskoutput"),
    ("blocked_agent_loop", r"chatcompletionmessagefunctiontool"),
]


# Human-readable action hints per category. Shown in escalations file so the
# operator knows what to do without grepping logs.
ACTION_HINTS: dict[str, str] = {
    "blocked_token_plan": (
        "Anthropic Token Plan rate-limit hit. Wait until your daily quota "
        "resets, or upgrade to a higher tier. The pipeline cannot proceed "
        "until the limit clears."
    ),
    "blocked_quota": (
        "API quota / rate-limit exhausted. Check the provider dashboard "
        "(MiniMax / OpenAI / Jina / Anthropic) and either wait for the "
        "reset window or top up the plan."
    ),
    "blocked_auth": (
        "API authentication failed. The relevant API key is missing, "
        "invalid, or expired. Rotate the key in .env and restart the "
        "container."
    ),
    "blocked_payment": (
        "Provider reports payment required. Check the billing dashboard "
        "for the affected provider and update the payment method."
    ),
    "blocked_agent_loop": (
        "Agent hit max_iter and emitted tool_calls as its final answer; "
        "CrewAI cannot coerce list[FunctionTool] into TaskOutput.raw (str). "
        "Retrying will reproduce the same failure. Bump the failing agent's "
        "max_iter in the crew config, simplify its task description so it "
        "converges sooner, or swap to a less tool-call-happy model."
    ),
}


def is_transient(error_msg: str) -> bool:
    """Return True if ``error_msg`` looks like a transient network failure.

    Used by the build/deploy retry loops to log a clearly-tagged INFO line
    when a retry is caused by an environmental blip (DNS, TCP reset, upstream
    timeout) rather than a bug in the generated code. Always safe to call
    with ``None`` or an empty string.
    """
    if not error_msg:
        return False
    msg_low = error_msg.lower()
    for _category, pattern in RECOVERABLE_PATTERNS:
        if re.search(pattern, msg_low):
            return True
    return False


def classify_error(error_msg: str) -> Optional[str]:
    """Return an escalation category for ``error_msg`` or None if recoverable.

    Categories:
        ``blocked_token_plan`` - Anthropic Token Plan limiter
        ``blocked_quota``       - generic rate-limit or quota exhaustion
        ``blocked_auth``        - auth/key/token issue
        ``blocked_payment``     - payment / billing issue
        None                    - recoverable, retry with feedback

    Option A short-circuit: if the message matches a transient-network
    pattern we return ``None`` even if it would also match an escalation
    pattern. A flapping registry that happens to spit "timed out" must not
    burn the token budget by being treated as a quota block.
    """
    if not error_msg:
        return None
    msg_low = error_msg.lower()
    if is_transient(error_msg):
        return None
    for category, pattern in ESCALATION_PATTERNS:
        if re.search(pattern, msg_low):
            return category
    return None


def write_escalation(
    category: str,
    error_msg: str,
    *,
    phase: str,
    draft_id: Optional[str] = None,
    cycle: Optional[int] = None,
    extra: Optional[dict] = None,
) -> None:
    """Append an escalation entry to ``ESCALATION_FILE``.

    File format is a JSON list of entries. Each entry has timestamp, category,
    action hint, the error message (truncated at 2KB so a runaway stack trace
    cannot blow up the file), the phase it happened in, and any extra context
    the caller wants to attach (slug, opportunity title, attempt #, etc.).

    Best-effort: if the file is unreadable / malformed we start a fresh list.
    """
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "category": category,
        "action_required": ACTION_HINTS.get(category, "Manual investigation required."),
        "phase": phase,
        "draft_id": draft_id,
        "cycle": cycle,
        "error_excerpt": (error_msg or "")[:2048],
    }
    if extra:
        entry["extra"] = extra

    try:
        ESCALATION_FILE.parent.mkdir(parents=True, exist_ok=True)
        existing: list = []
        if ESCALATION_FILE.exists():
            try:
                loaded = json.loads(ESCALATION_FILE.read_text())
                if isinstance(loaded, list):
                    existing = loaded
            except (json.JSONDecodeError, OSError):
                existing = []
        existing.append(entry)
        ESCALATION_FILE.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
    except Exception as write_err:  # noqa: BLE001 - file write best-effort
        log.warning("Could not write escalation file: %s", write_err)

    log.critical(
        "[ESCALATION] category=%s phase=%s draft=%s cycle=%s | %s",
        category,
        phase,
        draft_id,
        cycle,
        entry["action_required"],
    )
