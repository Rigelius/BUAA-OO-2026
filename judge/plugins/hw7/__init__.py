"""HW7 · 电梯调度（双轿厢） plugin."""
from __future__ import annotations

from .gui import build_page

PLUGIN = {
    "hw_id": "hw7",
    "unit": 2,
    "order": 7,
    "title": "HW7 · 电梯调度（双轿厢）",
    "build_page": build_page,
}
