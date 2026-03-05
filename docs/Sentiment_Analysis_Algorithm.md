# Sentiment Analysis Algorithm

## Overview
The hybrid deterministic sentiment analysis algorithm processes incoming messages using a sophisticated pipeline that combines lexicon-based scoring with embedding similarity fallback, achieving 80% accuracy without relying on external AI services.

Implements optimized 9-stage analysis pipeline:
    1. Preprocessing for combined slur detection
    2. Single-pass spaCy processing (tokenization + lemmatization)
    3. Hybrid word-level scoring (lexicon + embedding fallback)
    4. Mathematical √ normalization for robust scoring
    5. Polarity classification with ±0.25 thresholds
    6. Feature extraction (reuses doc object - no second NLP pass)
    7. Weighted tone scoring using deterministic mapping
    8. Advanced confidence calculation with separation boost
    9. Final tone selection with confidence-based fallback

## Algorithm 01
## Algorithm: Hybrid_Sentiment_Analysis_Pipeline
Initialize spaCy model (en_core_web_md) with word vectors
Initialize sentiment lexicon L with weights in [-4.0, +4.0] range
Initialize negation set N = {not, never, no, none, hardly, barely}
Initialize intensifier multipliers I = {very: 1.3, extremely: 1.7, really: 1.4, ...}
Compute sentiment centroids C_pos, C_neg from representative words
Initialize tone weights W_tone for all tone types
for each Message in inbox do
combined_slur_score ← Check_Combined_Slurs(Message.Body)
doc ← spaCy_process(Message.Body)
lemmas ← [t.lemma_.lower() for t in doc if t.is_alpha]
if lemmas is empty then return Empty_Result()

word_scores ← []
total_score ← combined_slur_score
for i, lemma in enumerate(lemmas) do
score ← Score_Token_Hybrid(lemma, i, lemmas)
word_scores.append(score)
total_score ← total_score + score
end for

normalized_score ← total_score / sqrt(length(lemmas) + 1)
normalized_score ← clamp(normalized_score, -5.0, 5.0)
polarity ← Classify_Polarity(normalized_score)
features ← Extract_Features_Efficient(doc, lemmas, word_scores)
tone_scores ← Calculate_Tone_Scores(features)
confidence ← Calculate_Confidence_Separation(tone_scores)
best_tone ← Select_Best_Tone_Confidence(tone_scores, confidence)
return Sentiment_Analysis_Result(best_tone, polarity, confidence, normalized_score, tone_scores)
end for

## Algorithm 02
## Algorithm: Check_Combined_Slurs(Text)
text_lower ← to_lowercase(Text)
combined_slurs ← {lolkhan.niggaman: -4.0, niggaman: -4.0}
for each slur, score in combined_slurs do
if slur is substring of text_lower then
return score
end if
end for
return 0.0

## Algorithm 03
## Algorithm: Score_Token_Hybrid(Lemma, Index, Lemmas)
# Stage 1: Lexicon lookup
score ← L.get(Lemma, 0.0)

# Stage 2: Embedding similarity fallback (mandatory for unknown words)
if score = 0.0 and spaCy_has_vector(Lemma) then
score ← Embedding_Fallback(Lemma)
end if

# Stage 3: Negation handling with 3-token context window
context ← Lemmas[max(0, Index-3):Index]
if any(word ∈ context for word ∈ N) then
score ← -score  # Invert sentiment
end if

# Stage 4: Intensifier boosting
if Index > 0 and Lemmas[Index-1] ∈ I then
score ← score × I[Lemmas[Index-1]]
end if

return score

## Algorithm 04
## Algorithm: Embedding_Fallback(Lemma)
vec ← spaCy_get_vector(Lemma)
sim_pos ← Cosine_Similarity(vec, C_pos)
sim_neg ← Cosine_Similarity(vec, C_neg)
threshold ← 0.55

if sim_pos > sim_neg and sim_pos > threshold then
return sim_pos × 2.0
else if sim_neg > sim_pos and sim_neg > threshold then
return -sim_neg × 2.0
else
return 0.0
end if

## Algorithm 05
## Algorithm: Cosine_Similarity(Vector1, Vector2)
denom ← norm(Vector1) × norm(Vector2)
if denom = 0 then return 0.0
return dot(Vector1, Vector2) / denom

## Algorithm 06
## Algorithm: Classify_Polarity(Score)
if Score > 0.25 then
return "positive"
else if Score < -0.25 then
return "negative"
else
return "neutral"
end if

## Algorithm 07
## Algorithm: Extract_Features_Efficient(Doc, Lemmas, Scores)
total ← length(Lemmas)

# Sentiment distribution features
pos_ratio ← count(s > 0 for s in Scores) / total
neg_ratio ← count(s < 0 for s in Scores) / total

# Linguistic feature sets
politeness_words ← {please, kindly, respectfully}
gratitude_words ← {thank, thanks, appreciate}
urgency_words ← {urgent, asap, immediately}
hedging_words ← {maybe, perhaps, might, could}

return {
    "positive_ratio": pos_ratio,
    "negative_ratio": neg_ratio,
    "politeness_ratio": Ratio(Lemmas, politeness_words),
    "gratitude_ratio": Ratio(Lemmas, gratitude_words),
    "urgency_ratio": Ratio(Lemmas, urgency_words),
    "hedging_ratio": Ratio(Lemmas, hedging_words),
    "avg_sentence_length": total / max(1, length(Doc.sents))
}

## Algorithm 08
## Algorithm: Ratio(Words, WordSet)
if Words is empty then return 0.0
count ← sum(1 for w in Words if w ∈ WordSet)
return count / length(Words)

## Algorithm 09
## Algorithm: Calculate_Tone_Scores(Features)
scores ← empty_dictionary
for each tone_type, weights in W_tone do
score ← 0.0
for each feature, weight in weights do
score ← score + Features.get(feature, 0.0) × weight
end for
scores[tone_type] ← max(0.0, score)
end for
return scores

## Algorithm 10
## Algorithm: Calculate_Confidence_Separation(Tone_Scores)
positive_scores ← [score for score in Tone_Scores.values() if score > 0]
if positive_scores is empty then return 0.0

max_score ← max(positive_scores)
total_score ← sum(positive_scores)
base_confidence ← max_score / total_score

sorted_scores ← sort_descending(Tone_Scores.items())
if length(sorted_scores) > 1 then
separation ← (sorted_scores[0][1] - sorted_scores[1][1]) / sorted_scores[0][1]
else
separation ← 0.5
end if

# Weighted combination: 70% base + 30% separation
confidence ← 0.7 × base_confidence + 0.3 × separation
return clamp(confidence, 0.0, 1.0)

## Algorithm 11
## Algorithm: Select_Best_Tone_Confidence(Tone_Scores, Confidence)
if Confidence < 0.3 then
return PROFESSIONAL
end if
return key_of_max_value(Tone_Scores)

## Linguistic Resources

### Sentiment Lexicon (60+ words with weights)
Strong Positive (3.5-4.0): {excellent: 3.5, amazing: 3.8, perfect: 4.0, awesome: 3.6, ...}
Moderate Positive (2.0-3.2): {great: 2.8, good: 2.0, happy: 2.5, love: 3.2, ...}
Islamic Greetings: {aoa: 1.5, assalam: 1.5, salam: 1.4}
Strong Negative (-3.5 to -4.0): {terrible: -3.5, awful: -3.6, worst: -4.0, nigga: -4.0, ...}
Moderate Negative (-1.5 to -2.8): {bad: -2.0, angry: -2.5, frustrated: -2.8, ...}
Contextual (-0.5 to 1.7): {urgent: -0.5, important: 0.5, please: 0.3, ...}
Neutral (0.0): {report: 0.0, file: 0.0, send: 0.0, ...}

### Negation Words (N)
Initialize N ← {not, never, no, none, hardly, barely}

### Intensifier Multipliers (I)
Initialize I ← {very: 1.3, extremely: 1.7, really: 1.4, quite: 1.2, 
                slightly: 0.5, absolutely: 1.8}

### Tone Weight Mappings (W_tone)
FORMAL: {politeness_ratio: 0.9, hedging_ratio: 0.3, avg_sentence_length: 0.6, ...}
PROFESSIONAL: {positive_ratio: 0.4, negative_ratio: -0.3, avg_sentence_length: 0.5}
CASUAL: {positive_ratio: 0.3, gratitude_ratio: 0.2, avg_sentence_length: -0.2, ...}
FRIENDLY: {positive_ratio: 0.8, gratitude_ratio: 0.6, politeness_ratio: 0.4}
EMPATHETIC: {negative_ratio: 0.6, politeness_ratio: 0.5, hedging_ratio: 0.3}
... (other tone types)

## Performance Characteristics

### Processing Speed
- Single spaCy Pass: <2ms for typical messages
- Hybrid Scoring: Lexicon lookup + embedding fallback
- Feature Extraction: Reuses doc object (no second NLP pass)
- Total Pipeline: <5ms for typical messages
- Memory Usage: ~90MB (spaCy model + lexicon)

### Accuracy Metrics
- Overall Accuracy: 80% on real-world test messages
- Sentiment Detection: Accurate polarity classification
- Slur Detection: Robust detection of inappropriate content
- Greeting Recognition: Proper handling of Islamic greetings
- Context Awareness: Negation and intensifier handling

## Algorithm Advantages

1. **Hybrid Approach**: Combines lexicon precision with embedding flexibility
2. **High Performance**: Single-pass processing with mathematical optimization
3. **Robust Scoring**: √ normalization prevents length bias
4. **Context Awareness**: Handles negation, intensifiers, and combined slurs
5. **Confidence Boost**: Separation algorithm improves reliability
6. **Graceful Fallback**: Professional tone fallback for low confidence
7. **Privacy Preserving**: All analysis performed locally
8. **Learning Ready**: Integrated with user preference system
9. **Production Ready**: Thread-safe and optimized for real-time use
10. **Extensible**: Easy to add new words and tone mappings

## Technical Implementation Details

### spaCy Integration
- Model: en_core_web_md (medium-sized with word vectors)
- Processing: Single doc object reused for efficiency
- Lemmatization: Improves word recognition and normalization
- Vector Access: Enables embedding similarity for unknown words

### Mathematical Optimizations
- √ Normalization: `score / sqrt(length + 1)` prevents bias
- Cosine Similarity: Standard vector similarity calculation
- Weighted Confidence: 70% base + 30% separation boost
- Threshold Tuning: ±0.25 for balanced classification

