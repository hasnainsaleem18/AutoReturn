# -------------------------
# PRIORITY ENGINE
# -------------------------
"""
Custom Priority Scoring Algorithm that classifies every email and Slack
message as High, Medium, or Low using a weighted urgency formula:

    Urgency = (w1 x Keyword Score) + (w2 x Deadline Score) + (w3 x Sender Score)

Classification Thresholds:
    High   : 6.7 - 10.0
    Medium : 3.4 -  6.6
    Low    : 0.0 -  3.3
"""

import re
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any


class PriorityEngine:
    """
    Core Priority Engine.
    Scores messages 0-10 using keyword, deadline, and sender algorithms.
    """

    # -------------------------
    # CONSTRUCTOR: LOAD CONFIG
    # Sets up all weights, word lists, and thresholds from the JSON dataset.
    # Also loads the SpaCy NLP model for smart negation detection.
    # -------------------------
    def __init__(self, dataset_path: str = None):
        if not dataset_path:
            project_root = os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..', '..', '..')
            )
            dataset_path = os.path.join(project_root, "data", "priority_dataset.json")

        self.dataset = self._load_dataset(dataset_path)

        weights = self.dataset.get("weights", {})
        self.w_keyword  = weights.get("w_keyword",  0.45)   # 45% weight - keywords
        self.w_deadline = weights.get("w_deadline", 0.30)   # 30% weight - deadlines
        self.w_sender   = weights.get("w_sender",   0.25)   # 25% weight - sender

        thresholds = self.dataset.get("thresholds", {})
        self.theta_high   = thresholds.get("high",   6.7)   # Above this -> "High"
        self.theta_medium = thresholds.get("medium", 3.4)   # Above this -> "Medium"

        self.delta      = self.dataset.get("delta", {}).get("value", 10)       # Max score cap
        self.time_bonus = self.dataset.get("time_remaining_bonus", {}).get("bonus_value", 5)  # <24hr bonus

        keyword_data = self.dataset.get("keyword_scores", {})
        self.direct_urgency_words = {k: v for k, v in keyword_data.get("direct_urgency", {}).items() if not k.startswith("_")}
        self.time_pressure_words  = {k: v for k, v in keyword_data.get("time_pressure", {}).items()  if not k.startswith("_")}
        self.action_call_words    = {k: v for k, v in keyword_data.get("action_call", {}).items()    if not k.startswith("_")}

        deadline_data = self.dataset.get("deadline_scores", {})
        self.relative_deadlines       = {k: v for k, v in deadline_data.get("relative_deadlines", {}).items() if not k.startswith("_")}
        self.absolute_deadline_base   = deadline_data.get("absolute_deadline_base_score", 5)

        sender_data = self.dataset.get("sender_scores", {})
        self.user_priority_list  = {k: v for k, v in sender_data.get("user_priority_list", {}).items() if not k.startswith("_")}
        self.cc_weight_multiplier = sender_data.get("cc_weight_multiplier", 0.5)

        print(f"Priority dataset loaded from {dataset_path}")
        print(f"PriorityEngine loaded: {len(self.direct_urgency_words)} urgency words, "
              f"{len(self.time_pressure_words)} time words, "
              f"{len(self.action_call_words)} action words, "
              f"{len(self.user_priority_list)} sender rules")

        try:
            import spacy
            print("PriorityEngine: Loading Semantic Analysis model (en_core_web_md)...")
            self.nlp = spacy.load("en_core_web_md")
            print("Semantic Analysis ready. Engine will detect negations like 'not urgent'.")
        except Exception as e:
            print(f"Semantic Analysis model failed to load: {e}")
            self.nlp = None

    # -------------------------
    # LOAD DATASET FROM JSON FILE
    # Reads priority_dataset.json which holds all scoring words and weights.
    # Returns empty dict if file is missing so the engine still runs safely.
    # -------------------------
    def _load_dataset(self, path: str) -> dict:
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            return data
        except FileNotFoundError:
            print(f"Priority dataset not found at {path}. Using empty defaults.")
            return {}
        except json.JSONDecodeError as e:
            print(f"Priority dataset JSON error: {e}. Using empty defaults.")
            return {}

    # -------------------------
    # ALGORITHM 01 - MAIN PRIORITY CLASSIFIER
    # Combines all three sub-scores into one final High/Medium/Low label.
    # Formula: urgency = (0.45 x K) + (0.30 x D) + (0.25 x S)
    # -------------------------
    def calculate_priority(self, message: Dict[str, Any]) -> str:
        k_score = self.keyword_score(message)   # Run Algorithm 02: keyword scanning
        d_score = self.deadline_score(message)  # Run Algorithm 03: deadline detection
        s_score = self.sender_score(message)    # Run Algorithm 04: sender priority check

        urgency = (self.w_keyword * k_score) + \
                  (self.w_deadline * d_score) + \
                  (self.w_sender * s_score)

        if urgency >= self.theta_high:      # 6.7+ -> High
            label = "High"
        elif urgency >= self.theta_medium:  # 3.4+ -> Medium
            label = "Medium"
        else:                               # Below 3.4 -> Low
            label = "Low"

        print(f"   Priority: K={k_score:.1f} D={d_score:.1f} S={s_score:.1f} "
              f"\u2192 urgency={urgency:.2f} \u2192 {label}")
        return label

    # -------------------------
    # ALGORITHM 02 - KEYWORD SCORE
    # Scans subject + body for 3 keyword categories: direct urgency,
    # time pressure, and action call. Uses SpaCy to ignore negations
    # like "NOT urgent" so they do not inflate the score.
    # -------------------------
    def keyword_score(self, message: Dict[str, Any]) -> float:
        subject = message.get('subject', '')
        body    = message.get('full_content', '') or message.get('content_preview', '') or ''
        text    = (subject + " " + body).lower()

        direct_urgency = 0.0
        time_pressure  = 0.0
        action_call    = 0.0

        # --- Smart path: SpaCy negation detection ---
        if getattr(self, 'nlp', None):
            try:
                doc     = self.nlp(text)
                lemmas  = [t.lemma_.lower() for t in doc if t.is_alpha]
                negations = {"not", "never", "no", "none", "hardly", "barely", "n't"}

                for i, lemma in enumerate(lemmas):
                    context    = lemmas[max(0, i - 3):i]              # 3-word look-back window
                    is_negated = any(n in context for n in negations) # True if word is negated

                    if not is_negated:
                        if lemma in self.direct_urgency_words:
                            direct_urgency += self.direct_urgency_words[lemma]
                        if lemma in self.time_pressure_words:
                            time_pressure  += self.time_pressure_words[lemma]
                        if lemma in self.action_call_words:
                            action_call    += self.action_call_words[lemma]

                # Also match multi-word phrases (e.g., "immediate response required")
                for phrase, value in self.direct_urgency_words.items():
                    if " " in phrase and phrase in text:
                        direct_urgency += value
                for phrase, value in self.time_pressure_words.items():
                    if " " in phrase and phrase in text:
                        time_pressure += value
                for phrase, value in self.action_call_words.items():
                    if " " in phrase and phrase in text:
                        action_call += value

                return min(direct_urgency + time_pressure + action_call, self.delta)

            except Exception as e:
                print(f"Semantic context check failed: {e}. Falling back to basic match.")

        # --- Fallback path: simple substring matching (no SpaCy) ---
        for word, value in self.direct_urgency_words.items():
            if word in text:
                direct_urgency += value
        for phrase, value in self.time_pressure_words.items():
            if phrase in text:
                time_pressure += value
        for phrase, value in self.action_call_words.items():
            if phrase in text:
                action_call += value

        return min(direct_urgency + time_pressure + action_call, self.delta)

    # -------------------------
    # ALGORITHM 03 - DEADLINE SCORE
    # Detects relative phrases ("by tomorrow") and absolute dates ("12/25/2026").
    # Regex handles absolute dates because infinite date combinations exist.
    # Adds a +5 bonus if extreme urgency phrases like "ASAP" or "today" appear.
    # -------------------------
    def deadline_score(self, message: Dict[str, Any]) -> float:
        body    = message.get('full_content', '') or message.get('content_preview', '') or ''
        subject = message.get('subject', '')
        text    = (subject + " " + body).lower()

        absolute_score = 0.0
        relative_score = 0.0

        # Step 1: Check relative deadline phrases from dataset
        for phrase, value in self.relative_deadlines.items():
            if phrase in text:
                relative_score += value

        # Step 2: Detect absolute date strings using Regex
        date_patterns = [
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',   # e.g., 12/25/2026 or 25-12-26
            r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',       # e.g., 2026-12-25 (ISO format)
        ]
        for pattern in date_patterns:
            if re.search(pattern, text):
                absolute_score += self.absolute_deadline_base   # Add base score (default 5)
                break   # Count each message only once regardless of how many dates found

        deadline_total = absolute_score + relative_score

        # Step 3: Apply <24 hour bonus if extreme urgency phrases are present
        urgent_time_phrases = [
            "today", "tonight", "within 24 hours", "within the hour",
            "right now", "immediately", "asap", "eod", "by noon", "by morning"
        ]
        for phrase in urgent_time_phrases:
            if phrase in text:
                deadline_total += self.time_bonus   # +5 points bonus
                break   # Apply once only

        return min(deadline_total, self.delta)

    # -------------------------
    # ALGORITHM 04 - SENDER SCORE
    # Checks if the sender or CC contacts are in the user's priority list.
    # Direct sender gets full weight (x0.8), CC contacts get half weight (x0.5 x0.2).
    # Formula: total = (0.8 x sender_score) + (0.2 x cc_total)
    # -------------------------
    def sender_score(self, message: Dict[str, Any]) -> float:
        sender          = message.get('sender', '').lower()
        sender_email    = message.get('email', '').lower()
        sender_combined = sender + " " + sender_email   # Search both name and email together

        cc_list = message.get('cc', [])
        if isinstance(cc_list, str):    # Handle cases where CC is a single string, not a list
            cc_list = [cc_list]

        sd       = 0.0   # Direct sender score (highest matching priority value)
        cc_total = 0.0   # Cumulative score from all CC priority contacts

        # Check if direct sender is in the priority list
        for keyword, value in self.user_priority_list.items():
            if keyword in sender_combined:
                sd = max(sd, value)   # Take highest match to avoid double-counting

        # Check every CC address against the priority list
        for cc_entry in cc_list:
            cc_lower = cc_entry.lower()
            for keyword, value in self.user_priority_list.items():
                if keyword in cc_lower:
                    cc_total += value * self.cc_weight_multiplier   # Half-weight for CC contacts

        cw1   = 0.8   # Direct sender contribution weight
        cw2   = 0.2   # CC contacts contribution weight
        total = (cw1 * sd) + (cw2 * cc_total)

        return min(total, self.delta)

    # -------------------------
    # UPDATE USER PRIORITY LIST AT RUNTIME
    # Called from Settings UI when user adds/removes priority contacts.
    # Takes a dict like {"boss@company.com": 10.0} and merges into existing list.
    # -------------------------
    def set_user_priority_list(self, priorities: Dict[str, float]):
        self.user_priority_list.update(priorities)
        print(f"Sender priority list updated: {len(self.user_priority_list)} entries")
