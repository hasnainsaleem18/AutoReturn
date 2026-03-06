# Tone Detection Algorithm

This document describes the complete Tone Preference feature in AutoReturn:
- incoming tone detection
- tone recommendation
- tone adjustment for outgoing replies

## Goal
Detect incoming message tone with confidence, then recommend a reply tone.

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
3. Extract signals:
   - lexical ratios (`politeness`, `slang`, `greetings`, `hedging`, `urgency`)
   - style signals (`contractions`, `exclamation ratio`, normalized sentence length)
   - regex signals for office/client communication markers and informal chat cues
4. Compute `formal` and `informal` tone scores via configurable feature weights.
5. Select detected tone and compute confidence from score separation.
6. Apply source/context orchestration (Gmail/Slack, urgency) to finalize recommendation.

## Recommendation Rules
- Urgent or formal-context message: suggest `formal`
- Casual-context or Slack-like context: suggest `informal`
- Otherwise use deterministic detection when confidence is sufficient
- Fall back to default tone when confidence is low

## Default Behavior
- Default tone: `Formal`
- Auto-suggest can preselect a recommended tone
- Manual user selection always takes precedence

## Algorithm  Details
- Detection vocabulary, regex cues, and feature weights are externalized in `config/tone_detection_rules.json`.
- Behavior tuning is done via config edits, without code changes.
- Regex signals capture communication style patterns that single-word matching can miss.

## Regex Signals Used
- Formal style patterns:
  - formal salutations (`Dear Sir/Madam`, `Respected ...`)
  - professional openers (`I hope this email finds you well`)
  - office/client requests (`kindly`, `please find`, `for your review`)
  - professional closings (`Best regards`, `Sincerely`)
- Informal style patterns:
  - casual openers (`hey`, `yo`)
  - conversational/slang phrases (`what's up`, `bro`, `bruh`)
  - chat abbreviations (`lol`, `idk`, `tbh`)
  - expressive punctuation (repeated `!`/`?`)

