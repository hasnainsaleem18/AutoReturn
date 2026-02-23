"""
Priority Classification Engine
Implements the 4-part Priority Algorithm:
    Algorithm 01: Main Urgency Classification (0-10 scale)
    Algorithm 02: Keyword_Score (Direct Urgency + Time Pressure + Action Call)
    Algorithm 03: Deadline_Score (Absolute + Relative + Time Remaining Bonus)
    Algorithm 04: Sender_Score (User Priority List + CC List)

Final score is clustered into: High (6.7-10), Medium (3.4-6.6), Low (0-3.3)
"""

import re
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any


class PriorityEngine:
    """
    Core Priority Engine that scores messages on a 0-10 scale 
    using keyword analysis, deadline detection, and sender importance.
    """

    def __init__(self, dataset_path: str = None):
        """
        Initialize the engine by loading the priority dataset.

        Args:
            dataset_path: Path to priority_dataset.json. 
                          If None, auto-discovers from project root.
        """
        # Auto-discover dataset path
        if not dataset_path:
            project_root = os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..', '..', '..')
            )
            dataset_path = os.path.join(project_root, "data", "priority_dataset.json")

        # Load dataset
        self.dataset = self._load_dataset(dataset_path)

        # --- Algorithm 01: Weights ---
        weights = self.dataset.get("weights", {})
        self.w_keyword = weights.get("w_keyword", 0.45)
        self.w_deadline = weights.get("w_deadline", 0.30)
        self.w_sender = weights.get("w_sender", 0.25)

        # --- Thresholds ---
        thresholds = self.dataset.get("thresholds", {})
        self.theta_high = thresholds.get("high", 6.7)
        self.theta_medium = thresholds.get("medium", 3.4)

        # --- Delta (max cap) ---
        self.delta = self.dataset.get("delta", {}).get("value", 10)

        # --- Time Remaining Bonus ---
        self.time_bonus = self.dataset.get("time_remaining_bonus", {}).get("bonus_value", 5)

        # --- Algorithm 02: Keyword data ---
        keyword_data = self.dataset.get("keyword_scores", {})
        self.direct_urgency_words = {
            k: v for k, v in keyword_data.get("direct_urgency", {}).items()
            if not k.startswith("_")
        }
        self.time_pressure_words = {
            k: v for k, v in keyword_data.get("time_pressure", {}).items()
            if not k.startswith("_")
        }
        self.action_call_words = {
            k: v for k, v in keyword_data.get("action_call", {}).items()
            if not k.startswith("_")
        }

        # --- Algorithm 03: Deadline data ---
        deadline_data = self.dataset.get("deadline_scores", {})
        self.relative_deadlines = {
            k: v for k, v in deadline_data.get("relative_deadlines", {}).items()
            if not k.startswith("_")
        }
        self.absolute_deadline_base = deadline_data.get("absolute_deadline_base_score", 5)

        # --- Algorithm 04: Sender data ---
        sender_data = self.dataset.get("sender_scores", {})
        self.user_priority_list = {
            k: v for k, v in sender_data.get("user_priority_list", {}).items()
            if not k.startswith("_")
        }
        self.cc_weight_multiplier = sender_data.get("cc_weight_multiplier", 0.5)

        print(f"📊 PriorityEngine loaded: {len(self.direct_urgency_words)} urgency words, "
              f"{len(self.time_pressure_words)} time words, "
              f"{len(self.action_call_words)} action words, "
              f"{len(self.user_priority_list)} sender rules")

    def _load_dataset(self, path: str) -> dict:
        """Load the priority dataset JSON file."""
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            print(f"✅ Priority dataset loaded from {path}")
            return data
        except FileNotFoundError:
            print(f"⚠️ Priority dataset not found at {path}. Using empty defaults.")
            return {}
        except json.JSONDecodeError as e:
            print(f"⚠️ Priority dataset JSON error: {e}. Using empty defaults.")
            return {}

    # =========================================================
    # ALGORITHM 01: Main Priority Classification
    # =========================================================
    def calculate_priority(self, message: Dict[str, Any]) -> str:
        """
        Main classification algorithm.
        
        Combines keyword, deadline, and sender scores using weighted formula:
            urgency = w1 × keyword + w2 × deadline + w3 × sender
        
        Then clusters the result:
            0.0 - 3.3  → "Low"
            3.4 - 6.6  → "Medium"
            6.7 - 10.0 → "High"
        
        Args:
            message: Message dictionary with 'subject', 'full_content', 'sender', etc.
        
        Returns:
            "High", "Medium", or "Low"
        """
        k_score = self.keyword_score(message)
        d_score = self.deadline_score(message)
        s_score = self.sender_score(message)

        # Weighted combination (all on 0-10 scale)
        urgency = (self.w_keyword * k_score) + \
                  (self.w_deadline * d_score) + \
                  (self.w_sender * s_score)

        # Cluster into High / Medium / Low
        if urgency >= self.theta_high:
            label = "High"
        elif urgency >= self.theta_medium:
            label = "Medium"
        else:
            label = "Low"

        # Debug log
        print(f"   📊 Priority: K={k_score:.1f} D={d_score:.1f} S={s_score:.1f} "
              f"→ urgency={urgency:.2f} → {label}")

        return label

    # =========================================================
    # ALGORITHM 02: Keyword_Score
    # =========================================================
    def keyword_score(self, message: Dict[str, Any]) -> float:
        """
        Algorithm 02: Keyword_Score(Message)
        
        Extracts keywords from Subject + Body and scores them across
        3 categories: Direct Urgency, Time Pressure, Action Call.
        
        Returns:
            Score from 0 to 10 (capped at delta).
        """
        subject = message.get('subject', '')
        body = message.get('full_content', '') or message.get('content_preview', '') or ''
        text = (subject + " " + body).lower()

        direct_urgency = 0.0
        time_pressure = 0.0
        action_call = 0.0

        # Calc_Value_Direct: Check each word in the Direct Urgency set
        for word, value in self.direct_urgency_words.items():
            if word in text:
                direct_urgency += value

        # Calc_Value_TimePressure: Check each phrase in Time Pressure set
        for phrase, value in self.time_pressure_words.items():
            if phrase in text:
                time_pressure += value

        # Calc_Value_Action: Check each phrase in Action Call set
        for phrase, value in self.action_call_words.items():
            if phrase in text:
                action_call += value

        total = direct_urgency + time_pressure + action_call

        # Cap at delta (10)
        return min(total, self.delta)

    # =========================================================
    # ALGORITHM 03: Deadline_Score
    # =========================================================
    def deadline_score(self, message: Dict[str, Any]) -> float:
        """
        Algorithm 03: Deadline_Score(Message)
        
        Extracts deadlines from Body and calculates score.
        Two types: Absolute (actual dates) and Relative (today, tomorrow).
        
        If Time_Remaining < 24 hours: add delta/2 bonus.
        Cap at delta.
        
        Returns:
            Score from 0 to 10 (capped at delta).
        """
        body = message.get('full_content', '') or message.get('content_preview', '') or ''
        subject = message.get('subject', '')
        text = (subject + " " + body).lower()

        absolute_score = 0.0
        relative_score = 0.0

        # --- Relative Deadlines ---
        # Check each known relative deadline phrase
        for phrase, value in self.relative_deadlines.items():
            if phrase in text:
                relative_score += value

        # --- Absolute Deadlines ---
        # Match date patterns: DD/MM/YYYY, MM-DD-YYYY, YYYY-MM-DD, etc.
        date_patterns = [
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',  # 12/25/2026 or 25-12-26
            r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',      # 2026-12-25
        ]
        for pattern in date_patterns:
            if re.search(pattern, text):
                absolute_score += self.absolute_deadline_base
                break  # Only count once

        deadline_total = absolute_score + relative_score

        # --- Time Remaining Bonus ---
        # If there's a hint of < 24 hour urgency, apply delta/2
        urgent_time_phrases = ["today", "tonight", "within 24 hours",
                               "within the hour", "right now", "immediately",
                               "asap", "eod", "by noon", "by morning"]
        for phrase in urgent_time_phrases:
            if phrase in text:
                deadline_total += self.time_bonus  # delta / 2 = 5
                break  # Apply bonus only once

        # Cap at delta (10)
        return min(deadline_total, self.delta)

    # =========================================================
    # ALGORITHM 04: Sender_Score
    # =========================================================
    def sender_score(self, message: Dict[str, Any]) -> float:
        """
        Algorithm 04: Sender_Score(Message)
        
        Checks if sender is in User_Priority_List.
        Also checks CC list.
        
        Formula: cw1 × sd + cw2 × cc_total
        where cw1 = 0.8, cw2 = 0.2
        
        Returns:
            Score from 0 to 10 (capped at delta).
        """
        sender = message.get('sender', '').lower()
        sender_email = message.get('email', '').lower()
        sender_combined = sender + " " + sender_email

        cc_list = message.get('cc', [])
        if isinstance(cc_list, str):
            cc_list = [cc_list]

        sd = 0.0  # Sender direct score
        cc_total = 0.0  # CC cumulative score

        # --- Sender Score ---
        for keyword, value in self.user_priority_list.items():
            if keyword in sender_combined:
                sd = max(sd, value)  # Take the highest match

        # --- CC Score ---
        for cc_entry in cc_list:
            cc_lower = cc_entry.lower()
            for keyword, value in self.user_priority_list.items():
                if keyword in cc_lower:
                    cc_total += value * self.cc_weight_multiplier

        # Weighted combination
        cw1 = 0.8
        cw2 = 0.2
        total = (cw1 * sd) + (cw2 * cc_total)

        # Cap at delta (10)
        return min(total, self.delta)

    # =========================================================
    # UTILITY: Update user priority list at runtime
    # =========================================================
    def set_user_priority_list(self, priorities: Dict[str, float]):
        """
        Allows the UI/Settings to update the sender priority list.
        
        Example: {"my_boss@company.com": 10, "newsletter@spam.com": 0}
        """
        self.user_priority_list.update(priorities)
        print(f"📊 Sender priority list updated: {len(self.user_priority_list)} entries")
