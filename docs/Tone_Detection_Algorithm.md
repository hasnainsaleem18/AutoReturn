# Tone Detection Algorithm

This document describes the complete Tone Preference feature in AutoReturn:
- incoming tone detection
- tone recommendation
- tone adjustment for outgoing replies

## Goal
Detect the incoming message tone with a confidence score, then suggest a reply tone.

## Feature Scope
- Detect incoming message tone with confidence.
- Suggest a reply tone (`Formal` or `Informal`).
- Allow user manual tone override.
- Rewrite outgoing draft text to match selected tone.

## Components
- Backend:
  - `src/backend/core/tone_engine.py`
  - `src/backend/services/tone_service.py`
  - `src/backend/models/tone_models.py`
  - `config/tone_detection_rules.json`
- Frontend:
  - `src/frontend/widgets/tone_selector.py`
  - `src/frontend/widgets/tone_detection_display.py`
  - Gmail/Slack reply dialogs

## Output
- `detected_tone`: `formal` or `informal`
- `tone_signal`: `formal_leaning`, `informal_leaning`, or `neutral`
- `confidence`: `0.0` to `1.0`
- `tone_scores`: per-tone score map

## High-Level Flow
1. Preprocess input text with spaCy.
2. Load configurable rules from `config/tone_detection_rules.json`.
3. Extract feature signals:
   - lexical ratios (`politeness`, `slang`, `greetings`, `hedging`, `urgency`)
   - style signals (`contractions`, `exclamation ratio`, normalized sentence length)
   - regex signals for office/client communication markers and informal chat cues
4. Compute tone scores for `formal` and `informal` using configurable feature weights.
5. Select detected tone and compute confidence from score separation.
6. Use source/context rules (Gmail/Slack, urgency hints) to finalize recommendation.

## Recommendation Rule
- Urgent or formal-context message: suggest `formal`
- Casual-context or Slack-like context: suggest `informal`
- Otherwise, use deterministic detection result when confidence is sufficient
- Fall back to default tone when confidence is low

## Default Behavior
- Default tone: `Formal`
- Auto-suggest can preselect a recommended tone
- Manual user selection always takes precedence

## Algorithm Details
- Detection vocabulary, regex cues, and feature weights are externalized in `config/tone_detection_rules.json`.
- Behavior tuning can be done by editing config values, without code changes.
- Regex signals capture communication style patterns that simple single-word matching misses.

## Regex Signals Used
- Formal style patterns:
  - formal salutations (e.g., `Dear Sir/Madam`, `Respected ...`)
  - professional openers (e.g., `I hope this email finds you well`)
  - office/client requests (e.g., `kindly`, `please find`, `for your review`)
  - professional closings (e.g., `Best regards`, `Sincerely`)
- Informal style patterns:
  - casual openers (e.g., `hey`, `yo`)
  - conversational/slang phrases (e.g., `what's up`, `bro`, `bruh`)
  - chat abbreviations (e.g., `lol`, `idk`, `tbh`)
  - expressive punctuation (e.g., repeated `!`/`?`)

