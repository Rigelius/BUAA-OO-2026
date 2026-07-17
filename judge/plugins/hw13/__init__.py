"""HW13 图书馆管理（基础） plugin."""
from __future__ import annotations

from .gui import build_page

PLUGIN = {
    "hw_id": "hw13",
    "unit": 4,
    "order": 13,
    "title": "HW13 图书馆管理（基础）",
    "build_page": build_page,
}
