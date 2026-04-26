"""Unit tests for message analysis cache helpers."""

from __future__ import annotations

import unittest

from src.backend.utils.message_analysis_cache import (
    apply_cached_analysis,
    build_message_analysis_cache,
    extract_analysis_cache,
    has_event_analysis,
    has_priority_analysis,
)


class TestMessageAnalysisCacheFormal(unittest.TestCase):
    # -------------------------
    # FUNCTION: test_build_cache_keeps_empty_event_list
    # Purpose: Validate empty event results are cached as completed analysis.
    # -------------------------
    def test_build_cache_keeps_empty_event_list(self):
        cache = build_message_analysis_cache(
            [
                {
                    "id": "m1",
                    "source": "gmail",
                    "priority": "Low",
                    "ai_priority_score": "Low",
                    "ai_tasks": ["Informational"],
                    "ai_events": [],
                    "ai_events_count": 0,
                    "summary": "",
                }
            ],
            source="gmail",
        )

        self.assertIn("m1", cache)
        self.assertEqual(cache["m1"]["ai_events"], [])
        self.assertEqual(cache["m1"]["ai_events_count"], 0)
        self.assertNotIn("summary", cache["m1"])

    # -------------------------
    # FUNCTION: test_apply_cached_analysis_marks_analysis_present
    # Purpose: Validate cached fields are copied onto a fetched message.
    # -------------------------
    def test_apply_cached_analysis_marks_analysis_present(self):
        message = {"id": "m1", "source": "gmail", "priority": "normal"}
        cache = {
            "m1": {
                "priority": "High",
                "ai_priority_score": "High",
                "ai_events": [],
                "ai_events_count": 0,
            }
        }

        self.assertTrue(apply_cached_analysis(message, cache))
        self.assertTrue(has_priority_analysis(message))
        self.assertTrue(has_event_analysis(message))
        self.assertEqual(message["priority"], "High")

    # -------------------------
    # FUNCTION: test_extract_source_scoped_cache
    # Purpose: Validate orchestrator source caches are routed to the right agent.
    # -------------------------
    def test_extract_source_scoped_cache(self):
        params = {
            "analysis_cache_by_source": {
                "gmail": {"g1": {"ai_priority_score": "Low"}},
                "slack": {"s1": {"ai_priority_score": "High"}},
            }
        }

        self.assertIn("g1", extract_analysis_cache(params, "gmail"))
        self.assertNotIn("s1", extract_analysis_cache(params, "gmail"))


if __name__ == "__main__":
    unittest.main()
