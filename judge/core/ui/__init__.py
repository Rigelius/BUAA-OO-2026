"""Shared PyQt UI components for judge pages."""

from .theme import DARK_COLORS, apply_dark_palette, build_dark_stylesheet
from .widgets import BadgeLabel, CaseEditorCard, CopyButton, StatusChip, TargetOutputCard

__all__ = [
    "DARK_COLORS",
    "apply_dark_palette",
    "build_dark_stylesheet",
    "BadgeLabel",
    "CaseEditorCard",
    "CopyButton",
    "StatusChip",
    "TargetOutputCard",
]
