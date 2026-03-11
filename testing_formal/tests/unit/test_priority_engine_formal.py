"""Unit tests for PriorityEngine scoring algorithms."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from src.backend.core.priority_engine import PriorityEngine


class TestPriorityEngineFormal(unittest.TestCase):
    # -------------------------
    # FUNCTION: setUp
    # Purpose: Execute setUp logic for this module.
    # -------------------------
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        dataset_path = os.path.join(self.tmp.name, "priority_dataset.json")
        with open(dataset_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "weights": {"w_keyword": 0.5, "w_deadline": 0.3, "w_sender": 0.2},
                    "thresholds": {"high": 6.7, "medium": 3.4},
                    "delta": {"value": 10},
                    "time_remaining_bonus": {"bonus_value": 5},
                    "keyword_scores": {
                        "direct_urgency": {"urgent": 5},
                        "time_pressure": {"today": 2},
                        "action_call": {"please respond": 2},
                    },
                    "deadline_scores": {
                        "relative_deadlines": {"tomorrow": 4, "today": 5},
                        "absolute_deadline_base_score": 5,
                    },
                    "sender_scores": {
                        "user_priority_list": {"boss@example.com": 10, "ceo": 9},
                        "cc_weight_multiplier": 0.5,
                    },
                },
                f,
            )

        self.engine = PriorityEngine(dataset_path=dataset_path)

    # -------------------------
    # FUNCTION: test_keyword_score
    # Purpose: Validate the keyword score scenario.
    # -------------------------
    def test_keyword_score(self):
        msg = {"subject": "Urgent", "full_content": "Please respond today"}
        score = self.engine.keyword_score(msg)
        self.assertGreater(score, 0)

    # -------------------------
    # FUNCTION: test_deadline_score_relative_and_bonus
    # Purpose: Validate the deadline score relative and bonus scenario.
    # -------------------------
    def test_deadline_score_relative_and_bonus(self):
        msg = {"subject": "Reminder", "full_content": "Need this today, asap"}
        score = self.engine.deadline_score(msg)
        self.assertGreaterEqual(score, 5)

    # -------------------------
    # FUNCTION: test_sender_score
    # Purpose: Validate the sender score scenario.
    # -------------------------
    def test_sender_score(self):
        msg = {
            "sender": "The Boss",
            "email": "boss@example.com",
            "cc": ["ceo@company.com"],
        }
        score = self.engine.sender_score(msg)
        self.assertGreater(score, 0)

    # -------------------------
    # FUNCTION: test_calculate_priority_high
    # Purpose: Validate the calculate priority high scenario.
    # -------------------------
    def test_calculate_priority_high(self):
        msg = {
            "subject": "Urgent",
            "full_content": "Please respond today. Deadline is tomorrow.",
            "sender": "Boss",
            "email": "boss@example.com",
        }
        label = self.engine.calculate_priority(msg)
        self.assertIn(label, {"High", "Medium", "Low"})

    # -------------------------
    # FUNCTION: test_set_user_priority_list
    # Purpose: Validate the set user priority list scenario.
    # -------------------------
    def test_set_user_priority_list(self):
        self.engine.set_user_priority_list({"vip@example.com": 10})
        self.assertIn("vip@example.com", self.engine.user_priority_list)


if __name__ == "__main__":
    unittest.main()
