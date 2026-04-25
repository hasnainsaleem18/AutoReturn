"""Integration tests for summary queue behavior without live AI/network."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from src.backend.services.ai_service import QueueSummaryGenerator


class _DummyService:
    # -------------------------
    # FUNCTION: generate_summary
    # Purpose: Execute generate summary logic for this module.
    # -------------------------
    def generate_summary(self, *_args, **_kwargs):
        return "Summary: ok"


class TestSummaryQueueIntegration(unittest.TestCase):
    # -------------------------
    # FUNCTION: setUp
    # Purpose: Execute setUp logic for this module.
    # -------------------------
    def setUp(self):
        self.generator = QueueSummaryGenerator(_DummyService(), max_concurrent=2)

    # -------------------------
    # FUNCTION: test_add_to_queue_accepts_only_unsummarized_messages
    # Purpose: Validate the add to queue accepts only unsummarized messages scenario.
    # -------------------------
    def test_add_to_queue_accepts_only_unsummarized_messages(self):
        # Existing queue already has one message; incoming duplicate should be ignored.
        self.generator.queue = [{"id": "m_existing", "summary": ""}]

        messages = [
            {"id": "m_existing", "summary": ""},
            {"id": "m_new", "summary": ""},
            {"id": "m_done", "summary": "already summarized"},
        ]

        with patch.object(self.generator, "process_queue") as mocked_process:
            self.generator.add_to_queue(messages)

        self.assertEqual(len(self.generator.queue), 2)
        self.assertTrue(any(m.get("id") == "m_new" for m in self.generator.queue))
        mocked_process.assert_called_once()

    # -------------------------
    # FUNCTION: test_progress_updates_after_summary_ready
    # Purpose: Validate the progress updates after summary ready scenario.
    # -------------------------
    def test_progress_updates_after_summary_ready(self):
        captured = []
        self.generator.total_count = 3
        self.generator.progress_update.connect(lambda current, total: captured.append((current, total)))

        self.generator._on_summary_ready("m1", "Summary: done")

        self.assertEqual(self.generator.completed_count, 1)
        self.assertEqual(captured[-1], (1, 3))


if __name__ == "__main__":
    unittest.main()
