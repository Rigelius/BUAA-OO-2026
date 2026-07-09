"""HW3 · 表达式化简（多变量 · 求导） plugin."""
from __future__ import annotations

from PyQt5.QtWidgets import QWidget

from .gui import build_page as _build_page


PLUGIN = {
    "hw_id": "hw3",
    "unit": 1,
    "order": 3,
    "title": "HW3 · 表达式化简（多变量 · 求导）",
    "build_page": _build_page,
}
