# AutoReturn Formal Testing Package

This folder contains a separate, presentation-ready testing package for the project.

## Goals
- Demonstrate feasibility with preliminary evidence.
- Provide clear methodology and measurable metrics.
- Provide reproducible test cases and outcomes for FYP review.

## Folder Structure
- `TEST_PLAN.md`: test levels, techniques, scope, entry/exit criteria.
- `TEST_CASE_MATRIX.md`: formal test-case definitions and coverage map.
- `METRICS_FRAMEWORK.md`: metrics, formulas, and reporting method.
- `manual/SYSTEM_TEST_CHECKLIST.md`: manual execution checklist for system/UAT.
- `tests/`: automated test scaffolding (unit + integration).
- `scripts/run_preliminary_tests.py`: feasibility smoke run + JSON report.
- `scripts/export_results_csv.py`: converts JSON report into CSV row format.
- `metrics/`: result templates for preliminary/final reporting.
- `results/`: generated run outputs.

## Quick Run
```bash
cd AutoReturn
source .venv/bin/activate
PYTHONPATH=. python testing_formal/scripts/run_preliminary_tests.py
```

## Full Project-Wide Run (Deep Coverage)
```bash
cd AutoReturn
source .venv/bin/activate
PYTHONPATH=. python testing_formal/scripts/run_full_formal_suite.py
```

This executes the full formal suite and writes:
- JSON summary: `testing_formal/results/full_suite_<run_id>.json`
- Per-file CSV: `testing_formal/results/full_suite_<run_id>.csv`

## Full Automated Suite (after installing test dependencies)
```bash
cd AutoReturn
source .venv/bin/activate
pip install -r testing_formal/requirements-test.txt
PYTHONPATH=. pytest -c testing_formal/pytest.ini testing_formal/tests -v
```

## Notes
- This package is intentionally separated from existing `tests/` so that formal evaluation artifacts remain isolated and traceable.
- Current tests avoid live Gmail/Slack writes and focus on deterministic or mocked validation.
- Coverage reporting uses Python stdlib `trace` so it works even without third-party coverage tools.
