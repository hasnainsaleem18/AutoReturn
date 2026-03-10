# -------------------------
# TONE ENGINE 
# -------------------------
"""
Tone Engine integrates deterministic tone 
detection Algorithm with Tone Preference
"""

# -------------------------
# IMPORTS
# -------------------------
import asyncio
import json
import os
import math
import re
import threading
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from datetime import datetime

import numpy as np
import spacy

from src.backend.models.tone_models import (
    ToneType, ToneProfile, ToneRecommendation,
    ToneAdjustmentRequest, ToneAdjustmentResponse
)
from src.backend.services.tone_service import ToneService
from src.backend.services.ai_service import OllamaService


@dataclass
class ToneDetectionResult:
    detected_tone: ToneType
    tone_signal: str
    confidence_score: float
    tone_signal_score: float
    tone_scores: Dict[ToneType, float]


class ToneDetector:
    """Embedded deterministic tone detector used by ToneEngine."""

    # -------------------------
    # INIT
    # Initializes the class instance and sets up default routing or UI states.
    # -------------------------
    def __init__(self):
        self.nlp = spacy.load("en_core_web_md")
        self.rules = self._load_detection_rules()
        self.lexicon = self.rules.get("lexicon", {})
        self.word_sets = self.rules.get("word_sets", {})
        self.regex_patterns = self._compile_regex_patterns(self.rules.get("regex_signals", {}))
        self.negations = {"not", "never", "no", "none", "hardly", "barely"}
        self.intensifiers = {
            "very": 1.3,
            "extremely": 1.7,
            "really": 1.4,
            "quite": 1.2,
            "slightly": 0.5,
            "absolutely": 1.8,
        }
        self.pos_centroid, self.neg_centroid = self._compute_centroids()
        self.tone_weights = self._load_tone_weights(self.rules.get("feature_weights", {}))

    # -------------------------
    # ANALYZE MESSAGE
    # Handles analyze functionality for message.
    # -------------------------
    def analyze_message(self, text: str) -> ToneDetectionResult:
        doc = self.nlp(text)
        lemmas = [t.lemma_.lower() for t in doc if t.is_alpha]
        if not lemmas:
            return self._empty_result()

        word_scores: List[float] = []
        total_score = 0.0
        for i, lemma in enumerate(lemmas):
            score = self._score_token(lemma, i, lemmas)
            word_scores.append(score)
            total_score += score

        normalized_score = total_score / math.sqrt(len(lemmas) + 1)
        normalized_score = max(-5.0, min(5.0, normalized_score))
        features = self._extract_features(doc, lemmas, word_scores)
        tone_scores = self._calculate_tone_scores(features)
        confidence = self._calculate_confidence(tone_scores)
        detected_tone = self._select_best_tone(tone_scores, confidence)
        tone_signal = self._derive_tone_signal(tone_scores)

        return ToneDetectionResult(
            detected_tone=detected_tone,
            tone_signal=tone_signal,
            confidence_score=confidence,
            tone_signal_score=normalized_score,
            tone_scores=tone_scores,
        )

    # -------------------------
    # SCORE TOKEN
    # Handles score functionality for token.
    # -------------------------
    def _score_token(self, lemma: str, index: int, lemmas: List[str]) -> float:
        score = self.lexicon.get(lemma, 0.0)
        if score == 0.0 and self.nlp.vocab.has_vector(lemma):
            score = self._embedding_fallback(lemma)
        context = lemmas[max(0, index - 3):index]
        if any(w in self.negations for w in context):
            score = -score
        if index > 0 and lemmas[index - 1] in self.intensifiers:
            score *= self.intensifiers[lemmas[index - 1]]
        return score

    # -------------------------
    # EMBEDDING FALLBACK
    # Handles embedding functionality for fallback.
    # -------------------------
    def _embedding_fallback(self, lemma: str) -> float:
        vec = self.nlp.vocab.get_vector(lemma)
        sim_pos = self._cosine(vec, self.pos_centroid)
        sim_neg = self._cosine(vec, self.neg_centroid)
        threshold = 0.55
        if sim_pos > sim_neg and sim_pos > threshold:
            return sim_pos * 2.0
        if sim_neg > sim_pos and sim_neg > threshold:
            return -sim_neg * 2.0
        return 0.0

    # -------------------------
    # EXTRACT FEATURES
    # Handles extract functionality for features.
    # -------------------------
    def _extract_features(self, doc, lemmas, scores) -> Dict[str, float]:
        total = len(lemmas)
        pos_ratio = sum(1 for s in scores if s > 0) / total
        neg_ratio = sum(1 for s in scores if s < 0) / total
        formal_salutations = self._get_word_set("formal_salutations")
        casual_greetings = self._get_word_set("casual_greetings")
        slang_words = self._get_word_set("slang_words")
        politeness_words = self._get_word_set("politeness_words")
        gratitude_words = self._get_word_set("gratitude_words")
        urgency_words = self._get_word_set("urgency_words")
        hedging_words = self._get_word_set("hedging_words")
        exclamation_ratio = doc.text.count("!") / max(1, len(doc.text))
        contraction_ratio = sum(1 for t in doc if "'" in t.text) / total
        sentence_len_normalized = min((total / max(1, len(list(doc.sents)))) / 20.0, 1.0)
        formal_regex_score = self._regex_score(doc.text, "formal")
        informal_regex_score = self._regex_score(doc.text, "informal")
        return {
            "positive_ratio": pos_ratio,
            "negative_ratio": neg_ratio,
            "formal_salutation_ratio": self._ratio(lemmas, formal_salutations),
            "casual_greeting_ratio": self._ratio(lemmas, casual_greetings),
            "slang_ratio": self._ratio(lemmas, slang_words),
            "politeness_ratio": self._ratio(lemmas, politeness_words),
            "gratitude_ratio": self._ratio(lemmas, gratitude_words),
            "urgency_ratio": self._ratio(lemmas, urgency_words),
            "hedging_ratio": self._ratio(lemmas, hedging_words),
            "contraction_ratio": contraction_ratio,
            "exclamation_ratio": exclamation_ratio,
            "avg_sentence_length": sentence_len_normalized,
            "formal_regex_score": formal_regex_score,
            "informal_regex_score": informal_regex_score,
        }

    # -------------------------
    # CALCULATE TONE SCORES
    # Handles calculate functionality for tone scores.
    # -------------------------
    def _calculate_tone_scores(self, features: Dict[str, float]) -> Dict[ToneType, float]:
        scores: Dict[ToneType, float] = {}
        for tone, weights in self.tone_weights.items():
            score = 0.0
            for feat, weight in weights.items():
                score += features.get(feat, 0.0) * weight
            scores[tone] = max(0.0, score)
        return scores

    # -------------------------
    # CALCULATE CONFIDENCE
    # Handles calculate functionality for confidence.
    # -------------------------
    def _calculate_confidence(self, tone_scores: Dict[ToneType, float]) -> float:
        positives = [v for v in tone_scores.values() if v > 0]
        if not positives:
            return 0.0
        max_score = max(positives)
        total_score = sum(positives)
        base = max_score / total_score
        sorted_scores = sorted(tone_scores.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_scores) > 1 and sorted_scores[0][1] > 0:
            separation = (sorted_scores[0][1] - sorted_scores[1][1]) / sorted_scores[0][1]
        else:
            separation = 0.5
        return max(0.0, min(1.0, (0.7 * base) + (0.3 * separation)))

    # -------------------------
    # SELECT BEST TONE
    # Handles select functionality for best tone.
    # -------------------------
    def _select_best_tone(self, scores: Dict[ToneType, float], confidence: float) -> ToneType:
        if not scores or all(v <= 0 for v in scores.values()):
            return ToneType.FORMAL
        return max(scores.items(), key=lambda x: x[1])[0]

    # -------------------------
    # DERIVE TONE SIGNAL
    # Handles derive functionality for tone signal.
    # -------------------------
    def _derive_tone_signal(self, scores: Dict[ToneType, float]) -> str:
        formal_score = scores.get(ToneType.FORMAL, 0.0)
        informal_score = scores.get(ToneType.INFORMAL, 0.0)
        delta = informal_score - formal_score
        if delta > 0.08:
            return "informal_leaning"
        if delta < -0.08:
            return "formal_leaning"
        return "neutral"

    # -------------------------
    # CLASSIFY TONE SIGNAL
    # Handles classify functionality for tone signal.
    # -------------------------
    def _classify_tone_signal(self, score: float) -> str:
        if score > 0.3:
            return "informal_leaning"
        if score < -0.3:
            return "formal_leaning"
        return "neutral"

    # -------------------------
    # LOAD DETECTION RULES
    # Loads data into detection rules.
    # -------------------------
    def _load_detection_rules(self) -> Dict[str, Any]:
        rules_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "config", "tone_detection_rules.json"
        )
        default_rules = self._default_detection_rules()
        try:
            if os.path.exists(rules_path):
                with open(rules_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    for key in ("lexicon", "word_sets", "regex_signals", "feature_weights"):
                        if isinstance(loaded.get(key), dict):
                            merged = dict(default_rules.get(key, {}))
                            merged.update(loaded.get(key, {}))
                            default_rules[key] = merged
        except Exception as e:
            print(f"Could not load tone detection rules: {e}")
        return default_rules

    # -------------------------
    # DEFAULT DETECTION RULES
    # Handles default functionality for detection rules.
    # -------------------------
    def _default_detection_rules(self) -> Dict[str, Any]:
        return {
            "lexicon": {
                "excellent": 3.5, "amazing": 3.8, "great": 2.8, "good": 2.0, "thanks": 2.1,
                "thank": 1.7, "appreciate": 2.3, "happy": 2.5, "love": 3.2, "please": 0.3,
                "kindly": 0.4, "respectfully": 0.6, "important": 0.5, "urgent": -0.5,
                "terrible": -3.5, "awful": -3.6, "worst": -4.0, "hate": -3.8, "horrible": -3.9,
                "bad": -2.0, "angry": -2.5, "frustrated": -2.8, "problem": -1.5, "error": -2.6,
                "issue": -1.8, "wrong": -2.1, "fail": -2.3, "sorry": -0.9, "busy": -0.8,
            },
            "word_sets": {
                "formal_salutations": ["dear", "respected", "sir", "madam", "mr", "mrs", "ms", "dr"],
                "casual_greetings": ["hey", "hi", "yo", "bro", "sup", "hiya", "whatsup", "wassup", "wazzup"],
                "slang_words": ["bro", "bruh", "dude", "yo", "sup", "whatsup", "wassup", "wazzup", "lol", "lmao", "omg", "btw"],
                "politeness_words": ["please", "kindly", "respectfully", "would", "could"],
                "gratitude_words": ["thank", "thanks", "appreciate"],
                "urgency_words": ["urgent", "asap", "immediately", "priority", "eod"],
                "hedging_words": ["maybe", "perhaps", "might", "could", "possibly"],
            },
            "regex_signals": {
                "formal": [
                    {"pattern": r"^(dear|respected)\s+(sir|madam|team|all|mr\\.?|mrs\\.?|ms\\.?|dr\\.?)\\b", "weight": 1.0},
                    {"pattern": r"\\b(i\\s+hope\\s+you\\s+are\\s+well|i\\s+hope\\s+this\\s+email\\s+finds\\s+you\\s+well)\\b", "weight": 0.8},
                    {"pattern": r"\\b(kindly|please\\s+find|for\\s+your\\s+review|at\\s+your\\s+earliest\\s+convenience)\\b", "weight": 0.8},
                    {"pattern": r"\\b(best\\s+regards|kind\\s+regards|sincerely|yours\\s+faithfully)\\b", "weight": 1.0}
                ],
                "informal": [
                    {"pattern": r"^(hey|yo|hi)\\b", "weight": 1.0},
                    {"pattern": r"\\b(what'?s\\s*up|wassup|whatsup|sup|bro|bruh|dude)\\b", "weight": 1.2},
                    {"pattern": r"\\b(lol|lmao|omg|btw|idk|imo|tbh)\\b", "weight": 0.8},
                    {"pattern": r"[!?]{2,}", "weight": 0.5}
                ]
            },
            "feature_weights": {
                "formal": {
                    "formal_salutation_ratio": 1.0,
                    "politeness_ratio": 0.8,
                    "hedging_ratio": 0.3,
                    "avg_sentence_length": 0.5,
                    "negative_ratio": -0.2,
                    "slang_ratio": -0.9,
                    "formal_regex_score": 1.4,
                    "informal_regex_score": -1.2,
                },
                "informal": {
                    "casual_greeting_ratio": 1.0,
                    "slang_ratio": 1.3,
                    "positive_ratio": 0.5,
                    "gratitude_ratio": 0.2,
                    "avg_sentence_length": -0.15,
                    "urgency_ratio": 0.1,
                    "contraction_ratio": 0.5,
                    "exclamation_ratio": 0.4,
                    "informal_regex_score": 1.5,
                    "formal_regex_score": -1.0,
                },
            },
        }

    # -------------------------
    # COMPILE REGEX PATTERNS
    # Handles compile functionality for regex patterns.
    # -------------------------
    def _compile_regex_patterns(self, regex_rules: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        compiled: Dict[str, List[Dict[str, Any]]] = {"formal": [], "informal": []}
        for tone_key in ("formal", "informal"):
            for entry in regex_rules.get(tone_key, []):
                try:
                    pattern = entry.get("pattern", "")
                    if not pattern:
                        continue
                    compiled[tone_key].append({
                        "regex": re.compile(pattern, re.IGNORECASE),
                        "weight": float(entry.get("weight", 1.0)),
                    })
                except re.error:
                    continue
        return compiled

    # -------------------------
    # LOAD TONE WEIGHTS
    # Loads data into tone weights.
    # -------------------------
    def _load_tone_weights(self, raw_weights: Dict[str, Any]) -> Dict[ToneType, Dict[str, float]]:
        formal = raw_weights.get("formal", {})
        informal = raw_weights.get("informal", {})
        return {
            ToneType.FORMAL: {k: float(v) for k, v in formal.items()},
            ToneType.INFORMAL: {k: float(v) for k, v in informal.items()},
        }

    # -------------------------
    # GET WORD SET
    # Retrieves word set.
    # -------------------------
    def _get_word_set(self, key: str) -> set:
        return {str(w).lower() for w in self.word_sets.get(key, [])}

    # -------------------------
    # REGEX SCORE
    # Handles regex functionality for score.
    # -------------------------
    def _regex_score(self, text: str, tone_key: str) -> float:
        if not text.strip():
            return 0.0
        score = 0.0
        for item in self.regex_patterns.get(tone_key, []):
            match_count = len(item["regex"].findall(text))
            if match_count > 0:
                score += item["weight"] * min(match_count, 2)
        return min(score / 2.0, 1.0)

    # -------------------------
    # COMPUTE CENTROIDS
    # Handles compute functionality for centroids.
    # -------------------------
    def _compute_centroids(self):
        pos_words = ["excellent", "amazing", "great", "good", "love"]
        neg_words = ["terrible", "awful", "bad", "worst", "angry"]
        pos_vecs = [self.nlp.vocab.get_vector(w) for w in pos_words if self.nlp.vocab.has_vector(w)]
        neg_vecs = [self.nlp.vocab.get_vector(w) for w in neg_words if self.nlp.vocab.has_vector(w)]
        return np.mean(pos_vecs, axis=0), np.mean(neg_vecs, axis=0)

    # -------------------------
    # COSINE
    # Handles cosine functionality for the operation.
    # -------------------------
    def _cosine(self, v1, v2) -> float:
        denom = np.linalg.norm(v1) * np.linalg.norm(v2)
        return float(np.dot(v1, v2) / denom) if denom != 0 else 0.0

    # -------------------------
    # RATIO
    # Handles ratio functionality for the operation.
    # -------------------------
    def _ratio(self, words, wordset) -> float:
        return sum(1 for w in words if w in wordset) / len(words)

    # -------------------------
    # EMPTY RESULT
    # Handles empty functionality for result.
    # -------------------------
    def _empty_result(self) -> ToneDetectionResult:
        return ToneDetectionResult(
            detected_tone=ToneType.FORMAL,
            tone_signal="neutral",
            confidence_score=0.0,
            tone_signal_score=0.0,
            tone_scores={},
        )


# -------------------------
# TONE ENGINE CLASS
# -------------------------
class ToneEngine:
    """Tone engine combines tone preference logic and embedded tone detection."""
    
    # -------------------------
    # INIT
    # Initializes the class instance and sets up default routing or UI states.
    # -------------------------
    def __init__(self, ai_service: OllamaService):
        self.ai_service = ai_service
        self.tone_detector = ToneDetector()
        self.tone_service = ToneService(ai_service, tone_detector=self.tone_detector)
        self._detector_lock = threading.RLock()
        
        self.user_profile = self._load_user_profile()
        self.tone_cache = {}  # Cache for tone recommendations
        
        print(f"Tone Engine initialized with embedded tone detection")
        print(f"   Default tone: {self.user_profile.default_tone}")

    # -------------------------
    # ANALYZE MESSAGE THREADSAFE
    # Handles analyze functionality for message threadsafe.
    # -------------------------
    def _analyze_message_threadsafe(self, text: str) -> ToneDetectionResult:
        """Serialize tone detector access to avoid cross-thread spaCy crashes."""
        with self._detector_lock:
            return self.tone_detector.analyze_message(text)
    
    # -------------------------
    # LOAD USER PROFILE
    # Loads data into user profile.
    # -------------------------
    def _load_user_profile(self) -> ToneProfile:
        """Load user tone profile from configuration"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'tone_profile.json')
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    data = json.load(f)
                    # Backward compatibility for older tone values.
                    data["default_tone"] = self._normalize_legacy_tone(data.get("default_tone", "informal"))
                    data["sender_preferences"] = {
                        k: self._normalize_legacy_tone(v) for k, v in (data.get("sender_preferences") or {}).items()
                    }
                    data["domain_preferences"] = {
                        k: self._normalize_legacy_tone(v) for k, v in (data.get("domain_preferences") or {}).items()
                    }
                    return ToneProfile(**data)
        except Exception as e:
            print(f"Could not load tone profile: {e}")
        
        return ToneProfile()
    
    # -------------------------
    # SAVE USER PROFILE
    # Saves the current state of user profile.
    # -------------------------
    def _save_user_profile(self):
        """Save user tone profile to configuration"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'tone_profile.json')
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            with open(config_path, 'w') as f:
                json.dump(self.user_profile.dict(), f, indent=2, default=str)
        except Exception as e:
            print(f"Could not save tone profile: {e}")
    
    # -------------------------
    # ANALYZE INCOMING TONE
    # Handles analyze functionality for incoming tone.
    # -------------------------
    def analyze_incoming_tone(self, message_text: str) -> Dict[str, Any]:
        """
        Deterministic tone detection 
        Uses feature-engineered pipeline for reliable analysis.
        """
        try:
            # Use deterministic tone detector
            result = self._analyze_message_threadsafe(message_text)
            
            return {
                'tone_signal': result.tone_signal,
                'detected_tone': result.detected_tone.value,
                'confidence': result.confidence_score,
                'feature_vector': result.tone_signal_score,
                'tone_scores': {tone.value: score for tone, score in result.tone_scores.items()}
            }
        except Exception as e:
            print(f"Tone detection error: {e}")
            return {'tone_signal': 'neutral', 'detected_tone': ToneType.FORMAL.value, 'confidence': 0.5}
    
    # -------------------------
    # ANALYZE MESSAGE CONTEXT
    # Handles analyze functionality for message context.
    # -------------------------
    async def analyze_message_context(self, message_data: Dict[str, Any]) -> Optional[ToneRecommendation]:
        """Analyze message to recommend appropriate tone using deterministic analysis"""
        
        message_id = message_data.get('id', 'unknown')
        
        # Check cache first
        if message_id in self.tone_cache:
            cached_analysis = self.tone_cache[message_id]
            if (datetime.now() - cached_analysis.get('timestamp', datetime.now())).seconds < 300:
                return cached_analysis['recommendation']
        
        # Use deterministic tone detection (not LLM)
        content = message_data.get('full_content', '') or message_data.get('content', '')
        if not content:
            return None
        
        # Perform deterministic analysis
        analysis_result = self._analyze_message_threadsafe(content)
        
        # Create recommendation based on deterministic analysis
        recommendation = ToneRecommendation(
            recommended_tone=analysis_result.detected_tone,
            confidence=analysis_result.confidence_score,
            reasoning=f"Detected {analysis_result.tone_signal} signal with {analysis_result.detected_tone.value} tone (confidence: {analysis_result.confidence_score:.2f})",
            tone_signal_score=max(-1.0, min(1.0, analysis_result.tone_signal_score)),
            urgency_level="medium",
            detected_tone_signal=analysis_result.tone_signal,
            detected_tone=analysis_result.detected_tone
        )
        
        # Cache the result
        self.tone_cache[message_id] = {
            'recommendation': recommendation,
            'timestamp': datetime.now()
        }
        
        return recommendation
    
    # -------------------------
    # GET EFFECTIVE TONE
    # Retrieves effective tone.
    # -------------------------
    async def get_effective_tone(self, message_data: Dict[str, Any], 
                                manual_tone: Optional[ToneType] = None) -> ToneType:
        """Get effective tone using deterministic analysis and orchestration logic"""
        
        if manual_tone:
            # User manually selected tone - learn from this
            self._learn_from_manual_selection(manual_tone, message_data)
            return manual_tone
        
        if self.user_profile.auto_tone_enabled:
            try:
                # Use deterministic tone detection for recommendation
                content = message_data.get('full_content', '') or message_data.get('content', '')
                if content:
                    analysis_result = self._analyze_message_threadsafe(content)
                    
                    # Apply orchestration logic based on deterministic analysis
                    suggested_tone = self._orchestrate_tone_decision(
                        analysis_result, message_data
                    )
                    
                    if analysis_result.confidence_score > 0.4:
                        return suggested_tone
                        
            except Exception as e:
                print(f"Error in deterministic tone orchestration: {e}")
        
        # Use user's default tone
        return self.user_profile.default_tone
    
    # -------------------------
    # ORCHESTRATE TONE DECISION
    # Handles orchestrate functionality for tone decision.
    # -------------------------
    def _orchestrate_tone_decision(self, analysis_result: ToneDetectionResult, 
                                 message_data: Dict[str, Any]) -> ToneType:
        """
        Tone orchestration logic based on deterministic analysis output.
        Applies source and priority rules to select the final reply tone.
        """
        tone_signal = analysis_result.tone_signal
        detected_tone = analysis_result.detected_tone
        confidence = analysis_result.confidence_score
        
        # Priority-based override (hook for future algorithm)
        priority = message_data.get('priority', 'normal').lower()
        if priority in ['urgent', 'high']:
            return ToneType.FORMAL
        
        # Signal-based orchestration
        if tone_signal == 'formal_leaning':
            return ToneType.FORMAL
        
        # Source-based adjustment
        source = message_data.get('source', '').lower()
        if source == 'slack':
            return ToneType.INFORMAL
        elif source == 'gmail':
            return ToneType.FORMAL
        
        # Return detected tone if confident enough
        if confidence > 0.6:
            return detected_tone
        
        # Default fallback
        return ToneType.FORMAL
    
    # -------------------------
    # ADJUST MESSAGE TONE
    # Handles adjust functionality for message tone.
    # -------------------------
    async def adjust_message_tone(self, original_text: str, target_tone: ToneType,
                                message_context: Dict[str, Any] = None) -> ToneAdjustmentResponse:
        """Adjust message tone using existing AI service (LLM only for stylistic rewriting)"""
        
        return await self.tone_service.adjust_tone(
            original_text=original_text,
            target_tone=target_tone,
            message_context=message_context or {}
        )
    
    # -------------------------
    # PROCESS OUTGOING MESSAGE
    # Executes processing logic for outgoing message.
    # -------------------------
    async def process_outgoing_message(self, original_message: Dict[str, Any],
                                   draft_text: str = "",
                                   manual_tone: Optional[ToneType] = None) -> Dict[str, Any]:
        """Process outgoing message with tone adjustment using existing draft generation"""
        
        try:
            # Get effective tone using deterministic analysis
            effective_tone = await self.get_effective_tone(original_message, manual_tone)
            
            # Adjust or generate draft
            if draft_text and draft_text.strip():
                # Adjust existing draft using LLM (only for stylistic rewriting)
                response = await self.adjust_message_tone(draft_text, effective_tone, original_message)
                adjusted_draft = response.adjusted_text
            else:
                # Generate new draft using existing AI service with tone instruction
                adjusted_draft = await self._generate_draft_with_tone(original_message, effective_tone)
            
            # Get deterministic analysis for reasoning
            content = original_message.get('full_content', '') or original_message.get('content', '')
            if content:
                analysis_result = self._analyze_message_threadsafe(content)
                recommendation = ToneRecommendation(
                    recommended_tone=analysis_result.detected_tone,
                    confidence=analysis_result.confidence_score,
                    reasoning=f"Based on deterministic analysis: {analysis_result.tone_signal} signal detected",
                    tone_signal_score=max(-1.0, min(1.0, analysis_result.tone_signal_score)),
                    urgency_level="medium",
                    detected_tone_signal=analysis_result.tone_signal,
                    detected_tone=analysis_result.detected_tone
                )
            else:
                recommendation = None
            
            return {
                'adjusted_draft': adjusted_draft,
                'final_tone': effective_tone,
                'recommended_tone': recommendation.recommended_tone if recommendation else effective_tone,
                'confidence': recommendation.confidence if recommendation else 0.5,
                'reasoning': recommendation.reasoning if recommendation else "Using default tone",
                'tone_detection': {
                    'tone_signal': analysis_result.tone_signal,
                    'detected_tone': analysis_result.detected_tone.value,
                    'confidence': analysis_result.confidence_score,
                    'feature_vector': analysis_result.tone_signal_score
                } if content else None
            }
            
        except Exception as e:
            print(f"Error in tone processing: {e}")
            return {
                'adjusted_draft': draft_text,
                'final_tone': manual_tone or self.user_profile.default_tone,
                'recommended_tone': self.user_profile.default_tone,
                'confidence': 0.0,
                'reasoning': 'Error in tone processing',
                'tone_detection': None
            }
    
    # -------------------------
    # GENERATE DRAFT WITH TONE
    # Creates and returns draft with tone.
    # -------------------------
    async def _generate_draft_with_tone(self, original_message: Dict[str, Any], target_tone: ToneType) -> str:
        """Generate draft with tone using existing AI service (LLM only for generation)"""
        
        try:
            # Use existing AI service with tone-specific prompt
            sender = original_message.get('sender', 'Unknown')
            subject = original_message.get('subject', 'No subject')
            content = (
                original_message.get('full_content', '')
                or original_message.get('content', '')
                or original_message.get('preview', '')
                or original_message.get('content_preview', '')
                or original_message.get('text', '')
            )
            content = str(content or "").strip()
            content = content[:1200] if content else ""
            
            tone_instructions = {
                ToneType.FORMAL: "Generate a formal response with proper titles and complete sentences.",
                ToneType.INFORMAL: "Generate an informal, conversational response."
            }
            
            instruction = tone_instructions.get(target_tone, "Generate a formal response.")
            
            prompt = f"""
            {instruction}

            Write a concise human-written reply. Avoid robotic phrases, avoid over-explaining,
            and do not mention that this is AI generated.

            Message details:
            From: {sender}
            Subject: {subject}
            Content: {content}

            Requirements:
            - Reply directly to the sender's likely intent
            - Keep it practical and natural
            - Use {target_tone.value} tone
            - Keep it between 3 and 8 sentences
            - Output only the final reply text
            """

            draft = await self.ai_service.generate_text_async(prompt, temperature=0.55, max_tokens=280)
            if draft and draft.strip():
                return draft.strip()
            return self._build_specific_fallback_draft(sender, subject, content, target_tone)
            
        except Exception as e:
            print(f"Error in draft generation: {e}")
            sender = original_message.get('sender', 'there')
            subject = original_message.get('subject', 'your message')
            content = (
                original_message.get('full_content', '')
                or original_message.get('content', '')
                or original_message.get('preview', '')
                or original_message.get('content_preview', '')
                or original_message.get('text', '')
            )
            return self._build_specific_fallback_draft(sender, subject, str(content or ""), target_tone)

    # -------------------------
    # BUILD SPECIFIC FALLBACK DRAFT
    # Handles build functionality for specific fallback draft.
    # -------------------------
    def _build_specific_fallback_draft(self, sender: str, subject: str, content: str, target_tone: ToneType) -> str:
        """Build a message-specific fallback draft when model generation is unavailable."""
        subject_clean = (subject or "your message").strip()
        sender_name = (sender or "there").strip()
        text = (content or "").lower()

        if "attach" in text or "file" in text or "document" in text:
            body = (
                f"Hi {sender_name},\n\n"
                f"Thanks for your message regarding \"{subject_clean}\". I am preparing the requested file and will share it shortly.\n\n"
                "Best regards,"
            )
        elif "meeting" in text or "schedule" in text or "availability" in text:
            body = (
                f"Hi {sender_name},\n\n"
                f"Thank you for your message about \"{subject_clean}\". I have noted the scheduling request and will confirm a suitable time shortly.\n\n"
                "Best regards,"
            )
        elif "confirm" in text or "confirmation" in text:
            body = (
                f"Hi {sender_name},\n\n"
                f"Thank you for your message about \"{subject_clean}\". This is confirmed on my side.\n\n"
                "Best regards,"
            )
        else:
            body = (
                f"Hi {sender_name},\n\n"
                f"Thanks for your message regarding \"{subject_clean}\". I have reviewed it and will follow up with the requested details shortly.\n\n"
                "Best regards,"
            )

        if target_tone == ToneType.INFORMAL:
            body = body.replace("Best regards,", "Thanks,")

        return body
    
    # -------------------------
    # UPDATE USER PREFERENCES
    # Refreshes or updates user preferences.
    # -------------------------
    def update_user_preferences(self, tone_selection: ToneType, 
                                message_context: Dict[str, Any]):
        """Learn from user's manual tone selections"""
        
        sender = message_context.get('sender', '')
        domain = self._extract_domain(sender)
        
        # Update sender preferences
        if sender:
            self.user_profile.sender_preferences[sender] = tone_selection
        
        # Update domain preferences
        if domain:
            self.user_profile.domain_preferences[domain] = tone_selection
        
        # Record override for learning
        self.user_profile.manual_override_history.append({
            'timestamp': datetime.now().isoformat(),
            'selected_tone': tone_selection.value,
            'message_context': {
                'sender': sender,
                'subject': message_context.get('subject', ''),
                'priority': message_context.get('priority', ''),
                'source': message_context.get('source', '')
            }
        })
        
        # Limit history size
        if len(self.user_profile.manual_override_history) > 1000:
            self.user_profile.manual_override_history = self.user_profile.manual_override_history[-500:]
        
        # Save preferences
        self._save_user_profile()
    
    # -------------------------
    # SET DEFAULT TONE
    # Assigns values for default tone.
    # -------------------------
    def set_default_tone(self, tone: ToneType):
        """Set user's default tone"""
        self.user_profile.default_tone = tone
        self._save_user_profile()
        print(f"Default tone updated to: {tone.value}")
    
    # -------------------------
    # SET AUTO TONE ENABLED
    # Assigns values for auto tone enabled.
    # -------------------------
    def set_auto_tone_enabled(self, enabled: bool):
        """Enable/disable auto-tone recommendations"""
        self.user_profile.auto_tone_enabled = enabled
        self._save_user_profile()
        print(f"Auto-tone {'enabled' if enabled else 'disabled'}")
    
    # -------------------------
    # GET SENDER PREFERENCES
    # Retrieves sender preferences.
    # -------------------------
    def get_sender_preferences(self, sender: str) -> Optional[ToneType]:
        """Get preferred tone for a specific sender"""
        return self.user_profile.sender_preferences.get(sender)
    
    # -------------------------
    # GET TONE STATISTICS
    # Retrieves tone statistics.
    # -------------------------
    def get_tone_statistics(self) -> Dict[str, Any]:
        """Get tone usage statistics"""
        stats = {
            'default_tone': self.user_profile.default_tone.value,
            'auto_tone_enabled': self.user_profile.auto_tone_enabled,
            'total_manual_overrides': len(self.user_profile.manual_override_history),
            'sender_preferences_count': len(self.user_profile.sender_preferences),
            'domain_preferences_count': len(self.user_profile.domain_preferences),
            'most_used_tones': self._get_most_used_tones()
        }
        return stats
    
    # -------------------------
    # PRIVATE HELPER METHODS
    # -------------------------
    
    def _learn_from_manual_selection(self, selected_tone: ToneType, message_context: Dict[str, Any]):
        """Learn from user's manual tone selections"""
        # Update effectiveness scores
        current_score = self.user_profile.tone_effectiveness_scores.get(selected_tone, 0.5)
        self.user_profile.tone_effectiveness_scores[selected_tone] = min(1.0, current_score + 0.1)

    # -------------------------
    # NORMALIZE LEGACY TONE
    # Handles normalize functionality for legacy tone.
    # -------------------------
    def _normalize_legacy_tone(self, tone_value: Any) -> str:
        """Map historical tone values to the 2-tone model."""
        text = str(tone_value or "").lower()
        if text in {"informal"}:
            return ToneType.INFORMAL.value
        return ToneType.FORMAL.value
    
    # -------------------------
    # EXTRACT DOMAIN
    # Handles extract functionality for domain.
    # -------------------------
    def _extract_domain(self, sender: str) -> str:
        """Extract domain from email address"""
        if '@' in sender:
            return sender.split('@')[1].lower()
        return 'unknown'
    
    # -------------------------
    # GET MOST USED TONES
    # Retrieves most used tones.
    # -------------------------
    def _get_most_used_tones(self) -> Dict[str, int]:
        """Get most used tones from history"""
        tone_counts = {}
        for override in self.user_profile.manual_override_history:
            tone = override.get('selected_tone', 'unknown')
            tone_counts[tone] = tone_counts.get(tone, 0) + 1
        
        # Return top 5 most used tones
        sorted_tones = sorted(tone_counts.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_tones[:5])


# Backward compatibility alias for existing imports/usages.
ToneManager = ToneEngine
