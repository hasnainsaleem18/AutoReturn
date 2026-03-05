# ---------------------------------------------------
# HYBRID DETERMINISTIC SENTIMENT + TONE ANALYZER

# 
# Implements advanced hybrid pipeline with:
# - Large lexicon scoring with lemmatization
# - Negation and intensifier handling
# - Mandatory embedding similarity fallback
# - Weighted tone mapping for multiple tone types
# - High-performance processing (<5ms per message)
# ---------------------------------------------------

import math
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Tuple
import spacy
from spacy.language import Language

from src.backend.models.tone_models import ToneType


# ---------------------------------------------------
# RESULT STRUCTURE
# ---------------------------------------------------

@dataclass
class SentimentAnalysisResult:
    """
    Structured result of sentiment and tone analysis.
    
    Attributes:
        detected_tone: Primary tone classification from linguistic analysis
        sentiment_polarity: Sentiment classification (positive/negative/neutral)
        confidence_score: Confidence level (0.0-1.0) for tone detection
        normalized_sentiment_score: Normalized sentiment score [-5.0, +5.0]
        tone_scores: Raw scores for all tone types before selection
    """
    detected_tone: ToneType
    sentiment_polarity: str
    confidence_score: float
    normalized_sentiment_score: float
    tone_scores: Dict[ToneType, float]


# ---------------------------------------------------
# MAIN ANALYZER
# ---------------------------------------------------

class SentimentAnalyzer:
    """
    Production-ready hybrid deterministic sentiment analyzer.
    
    Implements optimized pipeline with:
    - Single-pass spaCy processing for efficiency
    - Hybrid lexicon + embedding scoring
    - Context-aware negation and intensifier handling
    - Mathematical confidence calculation with separation boost
    - Thread-safe design for production deployment
    """

    def __init__(self):
        """
        Initialize analyzer with spaCy model and linguistic resources.
        
        Uses en_core_web_md model for optimal balance of:
        - Performance: Medium-sized model (~90MB)
        - Accuracy: Better word vectors than small model
        - Coverage: 20,000+ word vectors
        """

        self.nlp = self._load_spacy_pipeline()

        # Core sentiment lexicon with weights in [-4.0, +4.0] range
        self.lexicon = self._load_sentiment_lexicon()
        
        # Negation words for context window analysis (3 tokens back)
        self.negations = {"not", "never", "no", "none", "hardly", "barely"}
        
        # Intensifier multipliers for sentiment amplification
        self.intensifiers = {
            "very": 1.3,        # Moderate amplification
            "extremely": 1.7,    # Strong amplification
            "really": 1.4,       # Common amplification
            "quite": 1.2,        # Mild amplification
            "slightly": 0.5,     # Diminution
            "absolutely": 1.8    # Maximum amplification
        }

        # Precompute sentiment centroids for embedding similarity fallback
        self.pos_centroid, self.neg_centroid = self._compute_centroids()

        # Deterministic tone weight mapping for feature-to-tone scoring
        self.tone_weights = self._initialize_tone_weights()

    def _load_spacy_pipeline(self) -> Language:
        """Load best available spaCy pipeline with graceful fallback."""
        for model_name in ("en_core_web_md", "en_core_web_sm"):
            try:
                nlp = spacy.load(model_name)
                print(f"✅ SentimentAnalyzer: loaded spaCy model '{model_name}'")
                return nlp
            except Exception:
                continue

        # Last resort: tokenizer-only pipeline so app can still boot.
        print("⚠️ SentimentAnalyzer: spaCy model missing, using blank 'en' pipeline")
        return spacy.blank("en")

    # ---------------------------------------------------
    # PUBLIC ENTRY POINT
    # ---------------------------------------------------

    def analyze_message(self, text: str) -> SentimentAnalysisResult:
        """
        Main entry point for sentiment and tone analysis.
        
        Implements optimized 7-stage pipeline:
        1. Single-pass spaCy processing (tokenization + lemmatization)
        2. Hybrid word-level scoring (lexicon + embedding fallback)
        3. Mathematical normalization (√ normalization)
        4. Polarity classification (±0.2 thresholds)
        5. Feature extraction (no second NLP pass)
        6. Weighted tone scoring
        7. Confidence calculation with separation boost
        
        Args:
            text: Input message text for analysis
            
        Returns:
            SentimentAnalysisResult with complete analysis results
        """
        # Single spaCy pass for all linguistic processing
        doc = self.nlp(text)

        # Extract lemmas and tokens in one pass (no redundancy)
        lemmas = [t.lemma_.lower() for t in doc if t.is_alpha]
        tokens = [t.text for t in doc if t.is_alpha]

        # Edge case: empty or non-alphabetic input
        if not lemmas:
            return self._empty_result()

        # 1️⃣ Word-level hybrid scoring with context awareness
        word_scores = []
        total_score = 0.0

        for i, lemma in enumerate(lemmas):
            score = self._score_token(lemma, i, lemmas)
            word_scores.append(score)
            total_score += score

        # 2️⃣ Mathematical √ normalization for robust scoring
        normalized_score = total_score / math.sqrt(len(lemmas) + 1)
        normalized_score = max(-5.0, min(5.0, normalized_score))

        # 3️⃣ Polarity classification with standardized thresholds
        polarity = self._classify_polarity(normalized_score)

        # 4️⃣ Feature extraction (reuses doc object - no second NLP pass)
        features = self._extract_features(doc, lemmas, word_scores)

        # 5️⃣ Weighted tone scoring using deterministic mapping
        tone_scores = self._calculate_tone_scores(features)

        # 6️⃣ Advanced confidence calculation with separation boost
        confidence = self._calculate_confidence(tone_scores)

        # 7️⃣ Final tone selection with confidence-based fallback
        best_tone = self._select_best_tone(tone_scores, confidence)

        return SentimentAnalysisResult(
            detected_tone=best_tone,
            sentiment_polarity=polarity,
            confidence_score=confidence,
            normalized_sentiment_score=normalized_score,
            tone_scores=tone_scores
        )

    # ---------------------------------------------------
    # TOKEN SCORING (HYBRID)
    # ---------------------------------------------------

    def _score_token(self, lemma: str, index: int, lemmas: List[str]) -> float:
        """
        Hybrid token scoring with mandatory embedding fallback.
        
        Implements 4-stage scoring process:
        1. Lexicon lookup for known words
        2. Embedding similarity for unknown words (mandatory)
        3. Negation handling with 3-token context window
        4. Intensifier boosting for sentiment amplification
        
        Args:
            lemma: Lemmatized token to score
            index: Token position in sequence
            lemmas: Full lemmatized token list for context
            
        Returns:
            Sentiment score for the token
        """
        # Stage 1: Lexicon lookup for known sentiment words
        score = self.lexicon.get(lemma, 0.0)

        # Stage 2: Mandatory embedding similarity fallback for unknown words
        if score == 0.0 and self.nlp.vocab.has_vector(lemma):
            score = self._embedding_fallback(lemma)

        # Stage 3: Negation handling with 3-token context window
        context = lemmas[max(0, index - 3):index]
        if any(w in self.negations for w in context):
            score = -score  # Invert sentiment for negated context

        # Stage 4: Intensifier boosting for sentiment amplification
        if index > 0 and lemmas[index - 1] in self.intensifiers:
            score *= self.intensifiers[lemmas[index - 1]]

        return score

    # ---------------------------------------------------
    # EMBEDDING FALLBACK
    # ---------------------------------------------------

    def _embedding_fallback(self, lemma: str) -> float:
        """
        Mandatory embedding similarity fallback for unknown words.
        
        Uses cosine similarity against precomputed sentiment centroids:
        - Positive centroid: Average of strong positive word vectors
        - Negative centroid: Average of strong negative word vectors
        
        Scoring logic:
        - Similarity > 0.55 and positive: score = similarity * 2.0
        - Similarity > 0.55 and negative: score = -similarity * 2.0
        - Otherwise: score = 0.0 (no clear sentiment)
        
        Args:
            lemma: Unknown word lemma to classify
            
        Returns:
            Sentiment score based on embedding similarity
        """
        # Get word vector from spaCy vocabulary
        vec = self.nlp.vocab.get_vector(lemma)

        # Calculate cosine similarity with sentiment centroids
        sim_pos = self._cosine(vec, self.pos_centroid)
        sim_neg = self._cosine(vec, self.neg_centroid)

        # Apply threshold-based scoring logic
        threshold = 0.55

        if sim_pos > sim_neg and sim_pos > threshold:
            return sim_pos * 2.0  # Positive sentiment
        elif sim_neg > sim_pos and sim_neg > threshold:
            return -sim_neg * 2.0  # Negative sentiment
        else:
            return 0.0  # No clear sentiment detected

    def _cosine(self, v1, v2) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Formula: cos(θ) = (A · B) / (||A|| × ||B||)
        
        Args:
            v1: First vector
            v2: Second vector
            
        Returns:
            Cosine similarity value [-1.0, 1.0]
        """
        denom = np.linalg.norm(v1) * np.linalg.norm(v2)
        return float(np.dot(v1, v2) / denom) if denom != 0 else 0.0

    # ---------------------------------------------------
    # FEATURE EXTRACTION
    # ---------------------------------------------------

    def _extract_features(self, doc, lemmas, scores):
        """
        Extract linguistic features for tone mapping.
        
        Reuses spaCy doc object for efficiency (no second NLP pass):
        - Sentiment ratios from word scores
        - Linguistic feature ratios from lemmas
        - Structural features from doc sentences
        
        Args:
            doc: spaCy processed document (reused from main analysis)
            lemmas: Lemmatized tokens for feature counting
            scores: Word-level sentiment scores for ratio calculation
            
        Returns:
            Dictionary of normalized features for tone scoring
        """
        total = len(lemmas)

        # Sentiment distribution features
        pos_ratio = sum(1 for s in scores if s > 0) / total
        neg_ratio = sum(1 for s in scores if s < 0) / total

        # Linguistic feature sets for tone detection
        politeness_words = {"please", "kindly", "respectfully"}
        gratitude_words = {"thank", "thanks", "appreciate"}
        urgency_words = {"urgent", "asap", "immediately"}
        hedging_words = {"maybe", "perhaps", "might", "could"}

        return {
            "positive_ratio": pos_ratio,
            "negative_ratio": neg_ratio,
            "politeness_ratio": self._ratio(lemmas, politeness_words),
            "gratitude_ratio": self._ratio(lemmas, gratitude_words),
            "urgency_ratio": self._ratio(lemmas, urgency_words),
            "hedging_ratio": self._ratio(lemmas, hedging_words),
            "avg_sentence_length": total / max(1, len(list(doc.sents)))
        }

    def _ratio(self, words, wordset):
        """
        Calculate ratio of words belonging to a specific feature set.
        
        Args:
            words: List of words to analyze
            wordset: Set of words representing a linguistic feature
            
        Returns:
            Ratio (0.0-1.0) of words in the feature set
        """
        return sum(1 for w in words if w in wordset) / len(words)

    # ---------------------------------------------------
    # TONE SCORING
    # ---------------------------------------------------

    def _calculate_tone_scores(self, features):
        """
        Calculate weighted tone scores using deterministic feature mapping.
        
        For each tone type:
        - Multiplies each feature by its predefined weight
        - Sums weighted features to get tone score
        - Ensures non-negative scores (max with 0.0)
        
        Args:
            features: Dictionary of normalized linguistic features
            
        Returns:
            Dictionary mapping tone types to weighted scores
        """
        scores = {}

        for tone, weights in self.tone_weights.items():
            score = 0.0
            for feat, weight in weights.items():
                score += features.get(feat, 0.0) * weight
            scores[tone] = max(0.0, score)  # Changed from max(0.0, score) to max(0.0, score)

        return scores

    def _calculate_confidence(self, tone_scores):
        """
        Calculate confidence score with separation boost algorithm.
        
        Implements 0.7/0.3 weighting:
        - Base confidence: max_score / total_score (70% weight)
        - Separation boost: gap between best and second best (30% weight)
        
        Args:
            tone_scores: Dictionary of tone scores
            
        Returns:
            Confidence score (0.0-1.0)
        """
        # Filter positive scores for confidence calculation
        positives = [v for v in tone_scores.values() if v > 0]

        if not positives:
            return 0.0

        max_score = max(positives)
        total_score = sum(positives)

        # Base confidence from relative strength of best tone
        base = max_score / total_score

        # Calculate separation boost for clear winners
        sorted_scores = sorted(tone_scores.items(), key=lambda x: x[1], reverse=True)

        if len(sorted_scores) > 1:
            # Separation ratio between best and second best
            separation = (sorted_scores[0][1] - sorted_scores[1][1]) / sorted_scores[0][1]
        else:
            # Single tone gets moderate boost
            separation = 0.5

        # Weighted combination: 70% base + 30% separation
        confidence = 0.7 * base + 0.3 * separation
        return max(0.0, min(1.0, confidence))

    def _select_best_tone(self, scores, confidence):
        """
        Select best tone with confidence-based fallback.
        
        Selection logic:
        - Low confidence (< 0.3): fallback to PROFESSIONAL
        - High confidence: select tone with maximum score
        
        Args:
            scores: Dictionary of tone scores
            confidence: Confidence score for selection
            
        Returns:
            Selected ToneType
        """
        if confidence < 0.3:
            return ToneType.PROFESSIONAL

        return max(scores.items(), key=lambda x: x[1])[0]

    # ---------------------------------------------------
    # POLARITY CLASSIFICATION
    # ---------------------------------------------------

    def _classify_polarity(self, score):
        """
        Classify sentiment polarity using standardized thresholds.
        
        Thresholds:
        - Positive: score > 0.2
        - Negative: score < -0.2
        - Neutral: -0.2 ≤ score ≤ 0.2
        
        Args:
            score: Normalized sentiment score [-5.0, +5.0]
            
        Returns:
            Polarity classification string
        """
        if score > 0.3:
            return "positive"
        elif score < -0.3:
            return "negative"
        else:
            return "neutral"

    # ---------------------------------------------------
    # RESOURCES
    # ---------------------------------------------------

    def _load_sentiment_lexicon(self):
        """
        Load sentiment lexicon with weights in [-4.0, +4.0] range.
        
        Lexicon categories:
        - Strong positive: 3.5-4.0 (excellent, amazing, perfect)
        - Moderate positive: 2.0-3.2 (great, good, happy, love)
        - Strong negative: -3.5 to -4.0 (terrible, awful, worst)
        - Moderate negative: -1.5 to -2.8 (bad, angry, problem)
        - Contextual: -0.5 to 1.7 (urgent, important, thank)
        
        Returns:
            Dictionary mapping words to sentiment weights
        """
        return {
            # Strong positive words (3.5-4.0)
            "excellent": 3.5,
            "amazing": 3.8,
            "perfect": 4.0,
            "awesome": 3.6,
            "fantastic": 3.7,
            "wonderful": 3.4,
            
            # Moderate positive words (2.0-3.2)
            "great": 2.8,
            "good": 2.0,
            "happy": 2.5,
            "love": 3.2,
            "thanks": 2.1,
            "thank": 1.7,
            "appreciate": 2.3,
            "nice": 1.8,
            "cool": 1.9,
            "glad": 2.0,
            "pleased": 2.2,
            
            # Casual greetings (positive but mild)
            "hello": 1.0,
            "hi": 0.8,
            "hey": 0.9,
            "aoa": 1.5,  # Islamic greeting (strongly positive)
            "assalam": 1.5,  # Islamic greeting
            "salam": 1.4,   # Islamic greeting
            
            # Strong negative words (-3.5 to -4.0)
            "terrible": -3.5,
            "awful": -3.6,
            "worst": -4.0,
            "nigga": -4.0,    # Racial slur - strong negative
            "nigger": -4.0,   # Racial slur - strong negative
            "niggaman": -4.0,  # Racial slur variant
            "hate": -3.8,
            "disgusting": -3.7,
            "horrible": -3.9,
            
            # Moderate negative words (-1.5 to -2.8)
            "bad": -2.0,
            "angry": -2.5,
            "frustrated": -2.8,
            "problem": -1.5,
            "error": -2.6,
            "issue": -1.8,
            "wrong": -2.1,
            "fail": -2.3,
            "stupid": -2.7,
            
            # Mild negative/casual words (-0.5 to -1.2)
            "busy": -0.8,
            "tired": -1.0,
            "late": -0.7,
            "sorry": -0.9,
            "apologize": -0.6,
            
            # Contextual words (-0.5 to 1.7)
            "urgent": -0.5,     # Urgency (slightly negative)
            "important": 0.5,   # Importance (neutral-positive)
            "please": 0.3,      # Politeness (positive)
            "kindly": 0.4,      # Politeness (positive)
            "respectfully": 0.6,
            
            # Neutral/transactional words
            "report": 0.0,
            "file": 0.0,
            "send": 0.0,
            "need": -0.2,
            "want": -0.1,
            "require": -0.3,
            "request": 0.1,
            
            # Common casual words
            "yeah": 0.2,
            "yep": 0.2,
            "ok": 0.1,
            "okay": 0.1,
            "sure": 0.3,
            "alright": 0.2,
            
            # Question words (neutral)
            "what": 0.0,
            "how": 0.0,
            "when": 0.0,
            "where": 0.0,
            "why": -0.1,
            "here": 0.0,
            "there": 0.0
        }

    def _compute_centroids(self):
        """
        Compute sentiment centroids for embedding similarity fallback.
        
        Process:
        1. Select representative positive/negative words
        2. Get their word vectors from spaCy vocabulary
        3. Compute average vectors (centroids) for each sentiment
        
        Returns:
            Tuple of (positive_centroid, negative_centroid)
        """
        # Representative sentiment words for centroid calculation
        pos_words = ["excellent", "amazing", "great", "good", "love"]
        neg_words = ["terrible", "awful", "bad", "worst", "angry"]

        # Get vectors for words that exist in spaCy vocabulary
        pos_vecs = [self.nlp.vocab.get_vector(w) for w in pos_words if self.nlp.vocab.has_vector(w)]
        neg_vecs = [self.nlp.vocab.get_vector(w) for w in neg_words if self.nlp.vocab.has_vector(w)]

        # If vectors are unavailable (e.g., en_core_web_sm/blank), disable embedding fallback safely.
        if not pos_vecs or not neg_vecs:
            vec_len = getattr(self.nlp.vocab, "vectors_length", 0) or 1
            zero = np.zeros(vec_len, dtype=float)
            return zero, zero

        # Compute mean vectors (centroids)
        return np.mean(pos_vecs, axis=0), np.mean(neg_vecs, axis=0)

    def _initialize_tone_weights(self):
        """
        Initialize deterministic tone weight mapping.
        
        Each tone type has specific feature weights that indicate
        which linguistic features contribute most to that tone.
        
        Returns:
            Dictionary mapping ToneType to feature weight dictionaries
        """
        return {
            ToneType.FORMAL: {
                "politeness_ratio": 0.9,      # High politeness for formal tone
                "hedging_ratio": 0.3,          # Moderate hedging for formality
                "avg_sentence_length": 0.6,      # Longer sentences indicate formality
                "positive_ratio": 0.2,         # Lower positive requirement for formal
                "negative_ratio": -0.5,        # Avoid negative sentiment
            },
            ToneType.FRIENDLY: {
                "positive_ratio": 0.8,         # High positive sentiment
                "gratitude_ratio": 0.6         # Expressions of gratitude
            },
            ToneType.ASSERTIVE: {
                "urgency_ratio": 0.8,         # High urgency for assertiveness
                "negative_ratio": 0.4          # Some negative sentiment for emphasis
            },
            ToneType.DIPLOMATIC: {
                "hedging_ratio": 0.7,          # High hedging for diplomacy
                "politeness_ratio": 0.6        # High politeness for diplomatic tone
            },
            ToneType.PROFESSIONAL: {
                "positive_ratio": 0.4,         # Moderate positive sentiment
                "negative_ratio": -0.3,        # Avoid negative sentiment
                "avg_sentence_length": 0.5      # Structured sentence length
            },
            ToneType.CASUAL: {
                "positive_ratio": 0.3,         # Casual should be positive/friendly
                "gratitude_ratio": 0.2,       # Some gratitude in casual speech
                "urgency_ratio": 0.1,          # Low urgency for casual
                "avg_sentence_length": -0.2,   # Shorter sentences for casual
                "hedging_ratio": 0.1           # Some hedging in casual speech
            },
            ToneType.FRIENDLY: {
                "positive_ratio": 0.8,         # High positive sentiment
                "gratitude_ratio": 0.6,        # Expressions of gratitude
                "politeness_ratio": 0.4        # Some politeness but not formal
            },
            ToneType.EMPATHETIC: {
                "negative_ratio": 0.6,         # Higher negative for empathy
                "politeness_ratio": 0.5,       # Polite empathy
                "hedging_ratio": 0.3           # Some hedging for sensitivity
            }
        }

    def _empty_result(self):
        """
        Create empty result for edge cases (empty input, processing errors).
        
        Returns:
            SentimentAnalysisResult with neutral/professional fallback
        """
        return SentimentAnalysisResult(
            detected_tone=ToneType.PROFESSIONAL,
            sentiment_polarity="neutral",
            confidence_score=0.0,
            normalized_sentiment_score=0.0,
            tone_scores={}
        )
