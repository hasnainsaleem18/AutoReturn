# Test Case Matrix

| Test ID | Level | Feature | Technique | Preconditions | Steps | Expected Outcome |
|---|---|---|---|---|---|---|
| UT-EVT-001 | Unit | Relative date extraction | Boundary + Equivalence | Event extractor initialized | Parse message with "tomorrow at 7pm" | At least one candidate, date maps to next day, timed event |
| UT-EVT-002 | Unit | Birthday extraction | Equivalence | Event extractor initialized | Parse birthday message without explicit time | Candidate marked all-day |
| UT-EVT-003 | Unit | Irrelevant message filtering | Equivalence | Event extractor initialized | Parse non-event informational text | No event candidates |
| UT-TZ-001 | Unit | Timezone normalization | Equivalence | Timezone utility importable | Normalize `PKT` | Returns `Asia/Karachi` |
| UT-TZ-002 | Unit | Unknown timezone fallback | Error Guessing | Timezone utility importable | Normalize unsupported tz string | Returns fallback `UTC` |
| UT-AI-001 | Unit | Summary generation success path | Equivalence | AI service with mocked request | Simulate 200 response with summary body | Non-empty summary returned |
| UT-AI-002 | Unit | Summary generation timeout path | Error Guessing | AI service with mocked request | Raise timeout exception from request call | Returns `None` and no crash |
| INT-QUEUE-001 | Integration | Queue acceptance filter | Decision Table | Queue generator initialized | Add mixed messages (empty summary and pre-summarized) | Only eligible items added to queue |
| INT-QUEUE-002 | Integration | Progress accounting | State Transition | Queue generator initialized | Trigger `_on_summary_ready` manually | Completed count increments and progress signal emitted |
| SYS-UI-001 | System | Login and startup | Scenario | App launchable | Login and reach inbox | Main window loads and user metadata visible |
| SYS-AI-001 | System | Batch summarization | Scenario + Performance | Ollama reachable | Trigger generate summaries on inbox | Progress updates occur; failure count documented |
| SYS-CAL-001 | System | Schedule suggestion review | Scenario | Gmail messages with date/time content | Open message content and review suggestions | Suggestions are shown with expected date/time |
| SYS-CAL-002 | System | Conflict check flow | Decision Table | Existing calendar items present | Add suggested item at occupied slot | Conflict feedback appears and user can choose outcome |
| NFR-PERF-001 | Non-functional | Summary throughput | Benchmark | Stable environment + dataset | Run summary batch sizes 25/100/500 | Throughput and timeout rates captured |
| NFR-REL-001 | Non-functional | Graceful degradation | Error Guessing | Ollama unavailable | Trigger summarization | App remains responsive and errors are surfaced |
