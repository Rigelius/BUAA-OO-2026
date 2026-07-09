"""HW15 · 图书馆管理（信用） plugin."""
from __future__ import annotations

from .gui import build_page

PLUGIN = {
    "hw_id": "hw15",
    "unit": 4,
    "order": 15,
    "title": "HW15 · 图书馆管理（信用）",
    "build_page": build_page,
}
