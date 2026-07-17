"""HW10 社交网络（消息） plugin."""
from __future__ import annotations

from .gui import build_page

PLUGIN = {
    "hw_id": "hw10",
    "unit": 3,
    "order": 10,
    "title": "HW10 社交网络（消息）",
    "build_page": build_page,
}
