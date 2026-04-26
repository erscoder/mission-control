"""Cross-cycle deduplication for Sentinel V2 opportunities.

Compares candidate opportunities against existing drafts in the DB
to filter out duplicates before writing new drafts.
"""
from __future__ import annotations

import logging
import os
from difflib import SequenceMatcher

from sentinel_v2 import db as _db

log = logging.getLogger(__name__)

_ACTIVE_STATUSES = {
    "pending", "queued", "approved", "building", "built",
    "review", "deployed", "validated",
}


def filter_duplicates(
    candidates: list[dict],
    threshold: float | None = None,
) -> tuple[list[dict], list[dict]]:
    """Compare candidates against existing drafts (status != rejected/failed).

    Returns ``(unique, duplicates)``.
    Uses :class:`difflib.SequenceMatcher` on ``title + problem`` text.
    """
    if threshold is None:
        threshold = float(os.getenv("SENTINEL_DEDUP_THRESHOLD", "0.7"))

    if not candidates:
        return [], []

    existing = _db.list_by_status(_ACTIVE_STATUSES)
    if not existing:
        return list(candidates), []

    existing_texts = [
        _normalise(d.get("title", "") + " " + d.get("problem", ""))
        for d in existing
    ]

    unique: list[dict] = []
    duplicates: list[dict] = []

    for cand in candidates:
        cand_text = _normalise(
            cand.get("title", "") + " " + cand.get("problem", "")
        )
        is_dup = any(
            SequenceMatcher(None, cand_text, et).ratio() >= threshold
            for et in existing_texts
        )
        if is_dup:
            duplicates.append(cand)
        else:
            unique.append(cand)

    if duplicates:
        log.info(
            "Dedup: filtered %d duplicate(s): %s",
            len(duplicates),
            [d.get("title", "?") for d in duplicates],
        )

    return unique, duplicates


def _normalise(text: str) -> str:
    return " ".join(text.lower().split())
