# Formal Test Plan (Simplified)

## Objective
Validate the project by running the formal test suite.

## Only Acceptance Criteria
- `PASS`: all tests pass (0 failures, 0 errors).
- `FAIL`: any test fails or errors.

## Execution
Run:
```bash
cd AutoReturn
source .venv/bin/activate
PYTHONPATH=. python testing_formal/scripts/run_full_formal_suite.py
```

## Evidence
Use the generated files in `testing_formal/results/` as proof of execution.
