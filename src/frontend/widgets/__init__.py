# -------------------------
# FRONTEND WIDGETS PACKAGE
# -------------------------
"""
UI widget components for AutoReturn application.
Contains reusable UI elements for tone selection, tone detection display, and other features.
"""

# -------------------------
# IMPORTS
# -------------------------
from .tone_selector import ToneSelector
from .tone_detection_display import ToneDetectionDisplay

# -------------------------
# EXPORTS
# -------------------------
__all__ = ['ToneSelector', 'ToneDetectionDisplay']
