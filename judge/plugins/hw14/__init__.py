"""HW14 图书馆管理（预约） plugin."""
from __future__ import annotations

from .gui import build_page

PLUGIN = {
    "hw_id": "hw14",
    "unit": 4,
    "order": 14,
    "title": "HW14 图书馆管理（预约）",
    "build_page": build_page,
}
