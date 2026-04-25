"""Unit tests for OllamaService with mocked network I/O."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import requests

from src.backend.services.ai_service import OllamaService


class _MockResponse:
    # -------------------------
    # FUNCTION: __init__
    # Purpose: Execute   init   logic for this module.
    # -------------------------
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    # -------------------------
    # FUNCTION: json
    # Purpose: Execute json logic for this module.
    # -------------------------
    def json(self):
        return self._payload


class TestAIServiceFormal(unittest.TestCase):
    # -------------------------
    # FUNCTION: setUp
    # Purpose: Execute setUp logic for this module.
    # -------------------------
    def setUp(self):
        self.service = OllamaService(model_name="unit-test-model", base_url="http://localhost:11434")

    @patch("src.backend.services.ai_service.requests.get")
    # -------------------------
    # FUNCTION: test_check_connection_success
    # Purpose: Validate the check connection success scenario.
    # -------------------------
    def test_check_connection_success(self, mock_get):
        mock_get.return_value = _MockResponse(200, {})
        self.assertTrue(self.service.check_connection())

    @patch("src.backend.services.ai_service.requests.get")
    # -------------------------
    # FUNCTION: test_check_connection_failure
    # Purpose: Validate the check connection failure scenario.
    # -------------------------
    def test_check_connection_failure(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("offline")
        self.assertFalse(self.service.check_connection())

    @patch("src.backend.services.ai_service.requests.post")
    # -------------------------
    # FUNCTION: test_generate_summary_success
    # Purpose: Validate the generate summary success scenario.
    # -------------------------
    def test_generate_summary_success(self, mock_post):
        mock_post.return_value = _MockResponse(
            200,
            {"response": "Summary: The sender requested confirmation.\n\nTask: Auto Reply"},
        )

        result = self.service.generate_summary("Please confirm tomorrow meeting.", sender="x", subject="y")

        self.assertIsInstance(result, str)
        self.assertIn("Summary:", result)

    @patch("src.backend.services.ai_service.requests.post")
    # -------------------------
    # FUNCTION: test_generate_summary_timeout
    # Purpose: Validate the generate summary timeout scenario.
    # -------------------------
    def test_generate_summary_timeout(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("timeout")
        result = self.service.generate_summary("message")
        self.assertIsNone(result)

    @patch("src.backend.services.ai_service.requests.post")
    # -------------------------
    # FUNCTION: test_generate_text_non_200
    # Purpose: Validate the generate text non 200 scenario.
    # -------------------------
    def test_generate_text_non_200(self, mock_post):
        mock_post.return_value = _MockResponse(500, {"response": ""})
        self.assertIsNone(self.service.generate_text("draft this"))


if __name__ == "__main__":
    unittest.main()
