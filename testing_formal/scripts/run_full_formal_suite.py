#!/usr/bin/env python3
"""Run the full formal test suite and generate coverage-style metrics using stdlib trace."""

from __future__ import annotations

import ast
import csv
import json
import os
import platform
import sys
import time
import trace
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Set


ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = ROOT / "testing_formal" / "tests"
RESULTS_DIR = ROOT / "testing_formal" / "results"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# -------------------------
# FUNCTION: _target_files
# Purpose: Execute  target files logic for this module.
# -------------------------
def _target_files() -> list[Path]:
    targets = [ROOT / "main.py"]
    targets.extend(sorted((ROOT / "src").rglob("*.py")))
    return [p for p in targets if p.exists()]


# -------------------------
# FUNCTION: _statement_lines
# Purpose: Execute  statement lines logic for this module.
# -------------------------
def _statement_lines(path: Path) -> Set[int]:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception:
        return set()

    lines: Set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and hasattr(node, "lineno"):
            lines.add(int(node.lineno))
    return lines


# -------------------------
# FUNCTION: _collect_coverage
# Purpose: Execute  collect coverage logic for this module.
# -------------------------
def _collect_coverage(counts: Dict[tuple, int], files: Iterable[Path]) -> tuple[list[dict], dict]:
    by_file = []
    total_statements = 0
    total_covered = 0

    normalized_counts: Dict[str, Set[int]] = {}
    for (filename, lineno), hit_count in counts.items():
        if hit_count <= 0:
            continue
        key = os.path.realpath(filename)
        normalized_counts.setdefault(key, set()).add(int(lineno))

    for path in files:
        stmt = _statement_lines(path)
        covered_lines = normalized_counts.get(os.path.realpath(str(path)), set())
        covered_stmt = sorted(stmt.intersection(covered_lines))

        statement_count = len(stmt)
        covered_count = len(covered_stmt)
        coverage_pct = round((covered_count / statement_count) * 100, 2) if statement_count else 100.0

        by_file.append(
            {
                "file": str(path.relative_to(ROOT)),
                "statements": statement_count,
                "covered_statements": covered_count,
                "coverage_percent": coverage_pct,
            }
        )

        total_statements += statement_count
        total_covered += covered_count

    overall = {
        "total_statements": total_statements,
        "covered_statements": total_covered,
        "coverage_percent": round((total_covered / total_statements) * 100, 2) if total_statements else 100.0,
    }
    return by_file, overall


# -------------------------
# FUNCTION: _write_reports
# Purpose: Execute  write reports logic for this module.
# -------------------------
def _write_reports(run_id: str, summary: dict, file_rows: list[dict]) -> tuple[Path, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    json_path = RESULTS_DIR / f"full_suite_{run_id}.json"
    csv_path = RESULTS_DIR / f"full_suite_{run_id}.csv"

    payload = {
        "run_id": run_id,
        "summary": summary,
        "files": file_rows,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=["file", "statements", "covered_statements", "coverage_percent"],
        )
        writer.writeheader()
        writer.writerows(file_rows)

    return json_path, csv_path


# -------------------------
# FUNCTION: main
# Purpose: Execute main logic for this module.
# -------------------------
def main() -> int:
    start = time.perf_counter()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(TEST_ROOT), pattern="test_*.py")

    tracer = trace.Trace(
        count=True,
        trace=False,
        ignoremods=("unittest", "importlib", "pkgutil", "encodings", "asyncio", "collections"),
    )
    runner = unittest.TextTestRunner(verbosity=2)
    result = tracer.runfunc(runner.run, suite)

    counts = tracer.results().counts
    files = _target_files()
    file_rows, coverage_summary = _collect_coverage(counts, files)

    duration = round(time.perf_counter() - start, 3)
    summary = {
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "duration_seconds": duration,
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(getattr(result, "skipped", [])),
        "successful": result.wasSuccessful(),
        "coverage": coverage_summary,
    }

    json_path, csv_path = _write_reports(run_id, summary, file_rows)

    print("\n=== Full Formal Suite Summary ===")
    print(f"Run ID: {run_id}")
    print(f"Tests run: {summary['tests_run']}")
    print(f"Failures: {summary['failures']} | Errors: {summary['errors']}")
    print(
        f"Coverage: {coverage_summary['coverage_percent']}% "
        f"({coverage_summary['covered_statements']}/{coverage_summary['total_statements']})"
    )
    print(f"Duration: {duration}s")
    print(f"JSON report: {json_path}")
    print(f"CSV report:  {csv_path}")

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
