"""Project-wide static checks for syntax and module importability."""

from __future__ import annotations

import importlib
import os
import py_compile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


class TestProjectWideStaticFormal(unittest.TestCase):
    # -------------------------
    # FUNCTION: test_all_python_files_compile
    # Purpose: Validate the all python files compile scenario.
    # -------------------------
    def test_all_python_files_compile(self):
        failures = []
        for path in ROOT.rglob("*.py"):
            # Skip virtual environment and cache paths.
            if ".venv" in path.parts or "__pycache__" in path.parts:
                continue
            try:
                py_compile.compile(str(path), doraise=True)
            except Exception as exc:
                failures.append(f"{path}: {exc}")

        self.assertEqual(failures, [], "Compile failures:\n" + "\n".join(failures))

    # -------------------------
    # FUNCTION: test_src_modules_importable
    # Purpose: Validate the src modules importable scenario.
    # -------------------------
    def test_src_modules_importable(self):
        failures = []

        # Import main entry module.
        try:
            importlib.import_module("main")
        except Exception as exc:
            failures.append(f"main: {exc}")

        # Import each src module path.
        src_root = ROOT / "src"
        for path in src_root.rglob("*.py"):
            if ".venv" in path.parts or "__pycache__" in path.parts:
                continue
            rel = path.relative_to(ROOT).with_suffix("")
            module_name = ".".join(rel.parts)
            try:
                importlib.import_module(module_name)
            except Exception as exc:
                failures.append(f"{module_name}: {exc}")

        self.assertEqual(failures, [], "Import failures:\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
