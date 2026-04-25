#!/usr/bin/env python3
"""Run feasibility-focused preliminary checks and write a structured JSON report."""

from __future__ import annotations

import asyncio
import json
import platform
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


# -------------------------
# FUNCTION: _check_python_version
# Purpose: Execute  check python version logic for this module.
# -------------------------
def _check_python_version() -> CheckResult:
    ok = sys.version_info >= (3, 12)
    return CheckResult(
        name="python_version",
        passed=ok,
        detail=f"Detected Python {platform.python_version()} (required >= 3.12)",
    )


# -------------------------
# FUNCTION: _check_imports
# Purpose: Execute  check imports logic for this module.
# -------------------------
def _check_imports() -> CheckResult:
    modules = [
        "src.backend.core.event_extractor",
        "src.backend.services.ai_service",
        "src.backend.core.orchestrator",
        "src.frontend.ui.autoreturn_app",
    ]
    failures = []
    for module_name in modules:
        try:
            __import__(module_name)
        except Exception as exc:
            failures.append(f"{module_name}: {exc}")

    if failures:
        return CheckResult("core_imports", False, "; ".join(failures))
    return CheckResult("core_imports", True, f"Imported {len(modules)} modules")


# -------------------------
# FUNCTION: _check_event_extraction_async
# Purpose: Execute  check event extraction async logic for this module.
# -------------------------
async def _check_event_extraction_async() -> CheckResult:
    from src.backend.core.event_extractor import EventExtractor

    extractor = EventExtractor(ai_service=None, enable_llm_fallback=False)
    msg = {
        "id": "pre_evt_001",
        "source": "gmail",
        "subject": "Meeting schedule",
        "full_content": "Quick confirmation: meeting tomorrow at 7pm.",
    }
    events = await extractor.extract_from_message(msg)
    ok = len(events) >= 1
    return CheckResult(
        name="event_extraction_feasibility",
        passed=ok,
        detail=f"Extracted {len(events)} candidate(s)",
    )


# -------------------------
# FUNCTION: _check_ollama_connectivity
# Purpose: Execute  check ollama connectivity logic for this module.
# -------------------------
def _check_ollama_connectivity() -> CheckResult:
    from src.backend.services.ai_service import OllamaService

    service = OllamaService()
    connected = service.check_connection()
    detail = "Ollama reachable" if connected else "Ollama not reachable from this environment"
    return CheckResult("ollama_connectivity", connected, detail)


# -------------------------
# FUNCTION: _write_report
# Purpose: Execute  write report logic for this module.
# -------------------------
def _write_report(report: dict) -> Path:
    output_dir = ROOT / "testing_formal" / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    run_id = report["run_id"]
    output_file = output_dir / f"preliminary_{run_id}.json"
    output_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return output_file


# -------------------------
# FUNCTION: main
# Purpose: Execute main logic for this module.
# -------------------------
def main() -> int:
    started = datetime.now(timezone.utc)
    run_id = started.strftime("%Y%m%d_%H%M%S")

    checks = [_check_python_version(), _check_imports()]
    checks.append(asyncio.run(_check_event_extraction_async()))
    checks.append(_check_ollama_connectivity())

    passed = sum(1 for c in checks if c.passed)
    failed = len(checks) - passed

    report = {
        "run_id": run_id,
        "run_timestamp_utc": started.isoformat(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "checks": [asdict(c) for c in checks],
        "summary": {
            "executed": len(checks),
            "passed": passed,
            "failed": failed,
            "pass_rate": round((passed / len(checks)) * 100, 2) if checks else 0.0,
        },
    }

    output_file = _write_report(report)

    print("=== Preliminary Feasibility Run ===")
    print(f"Run ID: {run_id}")
    print(f"Executed: {len(checks)} | Passed: {passed} | Failed: {failed}")
    for check in checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"- [{status}] {check.name}: {check.detail}")
    print(f"Report written to: {output_file}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
