"""HW1 · 表达式化简（基础） plugin."""
from __future__ import annotations

from .gui import build_page

PLUGIN = {
    "hw_id": "hw1",
    "unit": 1,
    "order": 1,
    "title": "HW1 · 表达式化简（基础）",
    "build_page": build_page,
}
