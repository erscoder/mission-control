"""Error classification + escalation for the Sentinel build/deploy retry loops.

The retry loops in ``sentinel_loop.py`` retry up to MAX_*_RETRIES on any
exception. Some errors are recoverable with feedback (peer dep mismatch,
syntax error, missing file). Others are external blockers that no amount of
retrying will fix (rate-limit, expired API key, exhausted quota, payment
required). For the latter category we should:

  1. Stop the retry loop immediately to save tokens.
  2. Mark the draft as ``blocked`` (distinct from ``failed``).
  3. Append an entry to ``/tmp/sentinel_v2_escalations.json`` with enough
     detail for the operator to take a one-shot manual action (rotate key,
     top up balance, wait until reset).

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

ESCALATION_FILE = Path(
    os.environ.get(
        "SENTINEL_ESCALATIONS_FILE",
        "/tmp/sentinel_v2_escalations.json",
    )
)


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
}


def classify_error(error_msg: str) -> Optional[str]:
    """Return an escalation category for ``error_msg`` or None if recoverable.

    Categories:
        ``blocked_token_plan`` — Anthropic Token Plan limiter
        ``blocked_quota``       — generic rate-limit or quota exhaustion
        ``blocked_auth``        — auth/key/token issue
        ``blocked_payment``     — payment / billing issue
        None                    — recoverable, retry with feedback
    """
    if not error_msg:
        return None
    msg_low = error_msg.lower()
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
