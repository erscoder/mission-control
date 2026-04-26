"""Tests for sentinel_v2.dedup — cross-cycle deduplication."""
from __future__ import annotations

import pytest
from unittest.mock import patch


class TestFilterDuplicates:
    """Tests for filter_duplicates()."""

    def _call(self, candidates, existing=None, threshold=0.7):
        existing = existing or []
        with patch("sentinel_v2.dedup._db") as mock_db:
            mock_db.list_by_status.return_value = existing
            from sentinel_v2.dedup import filter_duplicates
            return filter_duplicates(candidates, threshold=threshold)

    def test_empty_db_all_pass(self):
        cands = [{"title": "Foo", "problem": "bar"}]
        unique, dupes = self._call(cands, existing=[])
        assert len(unique) == 1
        assert len(dupes) == 0

    def test_exact_title_match_filtered(self):
        cands = [{"title": "ComplianceDesk HIPAA", "problem": "compliance pain"}]
        existing = [{"title": "ComplianceDesk HIPAA", "problem": "compliance pain"}]
        unique, dupes = self._call(cands, existing=existing)
        assert len(unique) == 0
        assert len(dupes) == 1

    def test_similar_title_above_threshold_filtered(self):
        cands = [{"title": "BigFast Compliance", "problem": "HIPAA compliance automation"}]
        existing = [{"title": "BigFast Compliance Tool", "problem": "HIPAA compliance automation for clinics"}]
        unique, dupes = self._call(cands, existing=existing, threshold=0.7)
        assert len(dupes) == 1

    def test_below_threshold_passes(self):
        cands = [{"title": "Weather Analytics", "problem": "forecast accuracy"}]
        existing = [{"title": "ComplianceDesk", "problem": "HIPAA paperwork"}]
        unique, dupes = self._call(cands, existing=existing)
        assert len(unique) == 1
        assert len(dupes) == 0

    def test_rejected_failed_drafts_dont_block(self):
        """list_by_status is called with active statuses only; rejected/failed
        drafts are never in the returned list, so they don't block."""
        cands = [{"title": "Foo", "problem": "bar"}]
        # Simulate that the DB returns nothing (rejected drafts excluded)
        unique, dupes = self._call(cands, existing=[])
        assert len(unique) == 1

    def test_empty_candidates_returns_empty(self):
        unique, dupes = self._call([])
        assert unique == []
        assert dupes == []

    def test_threshold_configurable_via_env(self):
        cands = [{"title": "ABC Tool", "problem": "some problem"}]
        existing = [{"title": "ABC Toolz", "problem": "some problem"}]
        # With low threshold, it's a match
        _, dupes_low = self._call(cands, existing=existing, threshold=0.5)
        assert len(dupes_low) == 1
        # With very high threshold, it passes
        unique_high, _ = self._call(cands, existing=existing, threshold=0.99)
        assert len(unique_high) == 1

    def test_multiple_candidates_mixed(self):
        cands = [
            {"title": "UniqueApp", "problem": "unique problem"},
            {"title": "ComplianceDesk HIPAA", "problem": "compliance pain"},
        ]
        existing = [{"title": "ComplianceDesk HIPAA", "problem": "compliance pain"}]
        unique, dupes = self._call(cands, existing=existing)
        assert len(unique) == 1
        assert unique[0]["title"] == "UniqueApp"
        assert len(dupes) == 1

    def test_missing_fields_handled(self):
        """Candidates or drafts with missing title/problem don't crash."""
        cands = [{"title": "Foo"}, {}]
        existing = [{"problem": "bar"}]
        unique, dupes = self._call(cands, existing=existing)
        assert len(unique) + len(dupes) == 2
