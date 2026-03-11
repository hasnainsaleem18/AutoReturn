#!/usr/bin/env python3
"""Convert a preliminary JSON report into one CSV summary row."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


# -------------------------
# FUNCTION: main
# Purpose: Execute main logic for this module.
# -------------------------
def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python testing_formal/scripts/export_results_csv.py <preliminary_report.json>")
        return 1

    input_path = Path(sys.argv[1]).resolve()
    if not input_path.exists():
        print(f"Input report not found: {input_path}")
        return 1

    data = json.loads(input_path.read_text(encoding="utf-8"))
    summary = data.get("summary", {})
    checks = {item.get("name"): item.get("passed") for item in data.get("checks", [])}

    output_path = input_path.with_suffix(".csv")
    with output_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "run_id",
                "run_timestamp_utc",
                "python_version",
                "platform",
                "tests_executed",
                "tests_passed",
                "tests_failed",
                "ollama_reachable",
                "event_extraction_feasible",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "run_id": data.get("run_id", ""),
                "run_timestamp_utc": data.get("run_timestamp_utc", ""),
                "python_version": data.get("python_version", ""),
                "platform": data.get("platform", ""),
                "tests_executed": summary.get("executed", 0),
                "tests_passed": summary.get("passed", 0),
                "tests_failed": summary.get("failed", 0),
                "ollama_reachable": checks.get("ollama_connectivity", False),
                "event_extraction_feasible": checks.get("event_extraction_feasibility", False),
                "notes": "Generated from preliminary JSON report",
            }
        )

    print(f"CSV exported: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
