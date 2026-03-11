"""Unit tests for attachment resolution logic."""

from __future__ import annotations

import os
import tempfile
import unittest

from src.backend.core.attachment_resolver import AttachmentResolver


class TestAttachmentResolverFormal(unittest.TestCase):
    # -------------------------
    # FUNCTION: setUp
    # Purpose: Execute setUp logic for this module.
    # -------------------------
    def setUp(self):
        self.resolver = AttachmentResolver()

    # -------------------------
    # FUNCTION: test_no_attachment_request
    # Purpose: Validate the no attachment request scenario.
    # -------------------------
    def test_no_attachment_request(self):
        msg = {"subject": "hello", "full_content": "Thanks for the update."}
        result = self.resolver.resolve(msg, allowed_paths=[])
        self.assertFalse(result["requested"])
        self.assertEqual(result["attachments"], [])

    # -------------------------
    # FUNCTION: test_explicit_filename_match
    # Purpose: Validate the explicit filename match scenario.
    # -------------------------
    def test_explicit_filename_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "monthly_report.pdf")
            with open(target, "w", encoding="utf-8") as f:
                f.write("dummy")

            msg = {
                "subject": "Please attach monthly_report.pdf",
                "full_content": "Can you send monthly_report.pdf today?",
            }
            result = self.resolver.resolve(msg, allowed_paths=[tmp])
            self.assertTrue(result["requested"])
            self.assertIn(target, result["attachments"])

    # -------------------------
    # FUNCTION: test_ambiguous_candidates_require_manual_choice
    # Purpose: Validate the ambiguous candidates require manual choice scenario.
    # -------------------------
    def test_ambiguous_candidates_require_manual_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = os.path.join(tmp, "report_q1.pdf")
            b = os.path.join(tmp, "report_q2.pdf")
            for path in (a, b):
                with open(path, "w", encoding="utf-8") as f:
                    f.write("dummy")

            msg = {
                "subject": "Please send the report file",
                "full_content": "I need the report document.",
            }
            result = self.resolver.resolve(msg, allowed_paths=[tmp])
            self.assertTrue(result["requested"])
            self.assertEqual(result["attachments"], [])
            self.assertGreaterEqual(len(result["candidates"]), 2)

    # -------------------------
    # FUNCTION: test_respects_max_attachments
    # Purpose: Validate the respects max attachments scenario.
    # -------------------------
    def test_respects_max_attachments(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = []
            for idx in range(4):
                path = os.path.join(tmp, f"invoice_{idx}.pdf")
                with open(path, "w", encoding="utf-8") as f:
                    f.write("x")
                files.append(path)

            msg = {
                "subject": "Please send invoice files",
                "full_content": "Attach invoice documents.",
            }
            result = self.resolver.resolve(msg, allowed_paths=[tmp], max_auto_attachments=2)
            self.assertLessEqual(len(result["attachments"]), 2)


if __name__ == "__main__":
    unittest.main()
