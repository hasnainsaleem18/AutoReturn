"""Unit tests for ToneDetector with a mocked spaCy model."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np


class _FakeToken:
    # -------------------------
    # FUNCTION: __init__
    # Purpose: Execute   init   logic for this module.
    # -------------------------
    def __init__(self, text: str):
        self.text = text
        lemma = text.strip(".,!?;:").lower()
        self.lemma_ = lemma
        self.is_alpha = lemma.isalpha()


class _FakeDoc:
    # -------------------------
    # FUNCTION: __init__
    # Purpose: Execute   init   logic for this module.
    # -------------------------
    def __init__(self, text: str):
        self.text = text
        self._tokens = [_FakeToken(t) for t in text.split()]

    # -------------------------
    # FUNCTION: __iter__
    # Purpose: Execute   iter   logic for this module.
    # -------------------------
    def __iter__(self):
        return iter(self._tokens)

    @property
    # -------------------------
    # FUNCTION: sents
    # Purpose: Execute sents logic for this module.
    # -------------------------
    def sents(self):
        return [self._tokens]


class _FakeVocab:
    # -------------------------
    # FUNCTION: __init__
    # Purpose: Execute   init   logic for this module.
    # -------------------------
    def __init__(self):
        base = np.array([1.0, 0.5, -0.2], dtype=float)
        self._vec = {
            "excellent": base,
            "amazing": base,
            "great": base,
            "good": base,
            "love": base,
            "terrible": -base,
            "awful": -base,
            "bad": -base,
            "worst": -base,
            "angry": -base,
            "urgent": -base,
            "please": np.array([0.2, 0.1, 0.0], dtype=float),
            "hey": np.array([0.4, 0.2, 0.1], dtype=float),
            "thanks": np.array([0.6, 0.2, 0.0], dtype=float),
        }

    # -------------------------
    # FUNCTION: has_vector
    # Purpose: Execute has vector logic for this module.
    # -------------------------
    def has_vector(self, word: str) -> bool:
        return word.lower() in self._vec

    # -------------------------
    # FUNCTION: get_vector
    # Purpose: Execute get vector logic for this module.
    # -------------------------
    def get_vector(self, word: str):
        return self._vec[word.lower()]


class _FakeNLP:
    # -------------------------
    # FUNCTION: __init__
    # Purpose: Execute   init   logic for this module.
    # -------------------------
    def __init__(self):
        self.vocab = _FakeVocab()

    # -------------------------
    # FUNCTION: __call__
    # Purpose: Execute   call   logic for this module.
    # -------------------------
    def __call__(self, text: str):
        return _FakeDoc(text)


class TestToneDetectorFormal(unittest.TestCase):
    @patch("src.backend.core.tone_engine.spacy.load", return_value=_FakeNLP())
    # -------------------------
    # FUNCTION: test_analyze_message
    # Purpose: Validate the analyze message scenario.
    # -------------------------
    def test_analyze_message(self, _mock_spacy_load):
        from src.backend.core.tone_engine import ToneDetector

        detector = ToneDetector()
        result = detector.analyze_message("Hey team thanks for the update")

        self.assertIn(result.detected_tone.value, {"formal", "informal"})
        self.assertGreaterEqual(result.confidence_score, 0.0)
        self.assertIn(result.tone_signal, {"formal_leaning", "informal_leaning", "neutral"})


if __name__ == "__main__":
    unittest.main()
