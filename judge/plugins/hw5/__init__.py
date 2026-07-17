"""HW5 电梯调度（基础） plugin."""
from __future__ import annotations

from .gui import build_page

PLUGIN = {
    "hw_id": "hw5",
    "unit": 2,
    "order": 5,
    "title": "HW5 电梯调度（基础）",
    "build_page": build_page,
}
