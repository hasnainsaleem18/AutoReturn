# System Test Checklist

## Execution Metadata
- Tester:
- Date:
- Platform (macOS/Windows/Linux):
- Python version:
- Ollama model:

## Checklist
| ID | Scenario | Steps | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|
| SYS-01 | Auth dialog flow | Launch app, login, continue | Inbox opens with authenticated user |  |  |  |
| SYS-02 | Gmail sync | Press Sync with valid token | Messages populate and update counts |  |  |  |
| SYS-03 | Slack sync | Connect Slack and receive messages | New rows appear with source Slack |  |  |  |
| SYS-04 | AI summary run | Trigger Generate Summaries | Progress updates and summaries fill |  |  |  |
| SYS-05 | Message details drilldown | Click sender/content/summary/priority cells | Correct detail dialog content appears |  |  |  |
| SYS-06 | Schedule suggestions | Open message containing event phrase | Suggestions list is shown with date/time |  |  |  |
| SYS-07 | Calendar add/export | Add selected suggestions to Google Calendar/ICS | Success status or explicit error feedback |  |  |  |
| SYS-08 | Conflict check | Add event on occupied slot | Conflict prompt appears with clear options |  |  |  |
| SYS-09 | Pagination/filter behavior | Use rows-per-page and filters | Table updates correctly without UI glitch |  |  |  |
| SYS-10 | Degraded AI dependency | Stop Ollama and trigger summaries | App stays responsive and surfaces failure |  |  |  |

## Defect Log
| Defect ID | Severity | Component | Repro Steps | Expected | Actual | Status |
|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |
