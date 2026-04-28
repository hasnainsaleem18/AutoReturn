# Formal Test Plan

## 1. Scope
The testing scope covers:
- Authentication and core app startup behavior.
- Message ingest and summarization pipeline.
- Event extraction and scheduling suggestion flow.
- Priority and utility logic used in decision-making.
- Error handling and resilience for AI/network dependencies.

Out of scope for automated runs:
- Real Gmail and Slack write operations in unattended test mode.
- Production deployment infrastructure (desktop-only project).

## 2. Test Levels
### Unit Testing
- Purpose: validate deterministic logic in isolation.
- Targets: event extraction, timezone normalization, AI service request handling.

### Integration Testing
- Purpose: validate interactions between queue manager, AI service wrappers, and signal propagation.
- Targets: summary queue behavior and progress accounting.

### System Testing
- Purpose: validate end-to-end user journeys through UI and backend orchestration.
- Method: manual checklist with evidence capture.

### Non-Functional Testing
- Purpose: evaluate feasibility and practical behavior.
- Targets: summary throughput, failure rate, responsiveness, startup viability.

### Project-Wide Static Coverage
- Purpose: ensure every Python source file is syntactically valid and importable.
- Targets: `main.py` plus all modules under `src/`.

## 3. Test Techniques
- Equivalence Partitioning: valid/invalid message formats.
- Boundary Value Analysis: short/long message text, queue size bands.
- Decision Table Testing: automation policy combinations.
- State Transition Testing: disconnected/connected/authenticated states.
- Error Guessing: missing model, timeout, connection errors, invalid credentials.
- Scenario-Based Testing: realistic user workflows across inbox + details + actions.

## 4. Entry Criteria
- Python 3.12 virtual environment is active.
- Dependencies installed from `requirements.txt`.
- Core project imports succeed.

## 5. Exit Criteria
- All critical unit tests pass.
- Integration tests pass with no critical defects.
- Preliminary feasibility report generated.
- System checklist executed with documented outcomes.

## 6. Evidence and Traceability
- Automated run artifacts are written to `testing_formal/results/`.
- Manual/system outcomes are logged in checklist format.
- Metrics are summarized using templates in `testing_formal/metrics/`.
- Full suite run additionally generates per-file coverage-style CSV/JSON artifacts.
