"""Unit tests for timezone utility functions."""

from __future__ import annotations

import unittest

from src.backend.utils.timezone_utils import normalize_timezone


class TestTimezoneUtilsFormal(unittest.TestCase):
    def test_normalize_known_abbreviation(self):
        self.assertEqual(normalize_timezone("PKT"), "Asia/Karachi")

    def test_normalize_valid_tz(self):
        self.assertEqual(normalize_timezone("Asia/Karachi"), "Asia/Karachi")

    def test_normalize_unknown_tz_fallback(self):
        self.assertEqual(normalize_timezone("Invalid/Zone"), "UTC")


if __name__ == "__main__":
    unittest.main()
