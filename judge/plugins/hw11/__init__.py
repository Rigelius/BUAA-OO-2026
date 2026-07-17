"""HW11 社交网络（推荐） plugin."""
from __future__ import annotations

from .gui import build_page

PLUGIN = {
    "hw_id": "hw11",
    "unit": 3,
    "order": 11,
    "title": "HW11 社交网络（推荐）",
    "build_page": build_page,
}
