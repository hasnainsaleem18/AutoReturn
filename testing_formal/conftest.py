"""Shared test configuration for formal testing package."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Force deterministic timezone behavior where needed.
os.environ.setdefault("TZ", "UTC")
# Allow Qt widgets to initialize in headless environments.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
