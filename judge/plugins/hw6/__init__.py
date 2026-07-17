"""HW6 电梯调度（检修） plugin."""
from __future__ import annotations

from .gui import build_page

PLUGIN = {
    "hw_id": "hw6",
    "unit": 2,
    "order": 6,
    "title": "HW6 电梯调度（检修）",
    "build_page": build_page,
}
