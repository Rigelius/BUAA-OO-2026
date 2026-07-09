"""HW2 · 表达式化简（三目 · 函数） plugin."""
from __future__ import annotations

from PyQt5.QtWidgets import QWidget

from .gui import build_page as _build_page


PLUGIN = {
    "hw_id": "hw2",
    "unit": 1,
    "order": 2,
    "title": "HW2 · 表达式化简（三目 · 函数）",
    "build_page": _build_page,
}
