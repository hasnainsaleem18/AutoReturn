# AutoReturn Formal Testing Package

This folder contains the formal testing suite for the project.

## Single Pass Criteria
- `PASS` only if **all tests run successfully** (no failures, no errors).

## Main Files
- `PASS_CRITERIA.md`: the only acceptance criterion.
- `TEST_PLAN.md`: simplified plan aligned with pass/fail only.
- `tests/`: automated test cases (unit + integration).
- `manual/SYSTEM_TEST_CHECKLIST.md`: manual/system checklist.
- `results/`: generated test outputs.

## Run Full Suite
```bash
cd AutoReturn
source .venv/bin/activate
PYTHONPATH=. python testing_formal/scripts/run_full_formal_suite.py
```

## Run With Pytest
```bash
cd AutoReturn
source .venv/bin/activate
pip install -r testing_formal/requirements-test.txt
PYTHONPATH=. pytest -c testing_formal/pytest.ini testing_formal/tests -v
```
