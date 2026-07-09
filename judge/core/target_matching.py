"""Shared target-name matching for source directories and jar files."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


def is_target_entry(path: Path) -> bool:
    return path.is_dir() or (path.is_file() and path.suffix.lower() == ".jar")


def is_source_project_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    if (path / "src").is_dir():
        return True
    return any(path.glob("*.java"))


def direct_target_entry(pattern: str) -> Optional[Path]:
    path = Path(pattern)
    if path.exists() and is_target_entry(path):
        return path.resolve()
    return None


def target_name_matches(name: str, pattern: str) -> bool:
    """Match a target name by shell-style glob first, then regex fullmatch."""
    if fnmatch.fnmatch(name, pattern):
        return True
    try:
        return re.fullmatch(pattern, name) is not None
    except re.error:
        return False


def matching_target_entries(entries: Iterable[Path], pattern: str) -> List[Path]:
    return [
        entry
        for entry in entries
        if is_target_entry(entry) and target_name_matches(entry.name, pattern)
    ]


def _split_existing_parent(full_text: str) -> Optional[Tuple[Path, str]]:
    separators = [idx for idx, ch in enumerate(full_text) if ch in "\\/"]
    for idx in reversed(separators):
        parent_text = full_text[:idx]
        pattern = full_text[idx + 1:]
        if not parent_text or not pattern:
            continue
        parent = Path(parent_text)
        if parent.is_dir():
            return parent.resolve(), pattern
    return None


def target_selection_from_text(
    text: str,
    default_text: str,
    relative_bases: Sequence[Path],
) -> Tuple[Path, str]:
    """Resolve UI target text to ``(scan_dir, name_or_direct_path_pattern)``.

    Existing source directories and jar files are treated as direct targets.
    Existing container directories without their own Java/src are scanned with
    pattern ``*`` so all immediate child directories/jars are considered.
    """
    raw = (text or "").strip() or default_text
    raw_path = Path(raw)

    candidates: List[Path] = []
    if raw_path.is_absolute():
        candidates.append(raw_path)
        split = _split_existing_parent(raw)
        if split is not None and not raw_path.exists():
            return split
    else:
        for base in relative_bases:
            direct = (base / raw_path).resolve()
            candidates.append(direct)
        for direct in candidates:
            if direct.exists():
                selected = direct
                break
        else:
            for base in relative_bases:
                split = _split_existing_parent(str(base.resolve()) + "\\" + raw)
                if split is not None:
                    return split

    selected = candidates[-1]
    for candidate in candidates:
        if candidate.exists() or candidate.parent.exists():
            selected = candidate
            break

    if selected.exists():
        if selected.is_dir() and not is_source_project_dir(selected):
            children = sorted(selected.iterdir(), key=lambda p: p.name.lower())
            if matching_target_entries(children, "*"):
                return selected, "*"
        return selected.parent, str(selected)

    return selected.parent, selected.name
