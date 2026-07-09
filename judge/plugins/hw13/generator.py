#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HW13 testcase generator — 图书馆基础版 (无阅览室 / 无精品架 / 无评分)."""

from __future__ import annotations

import argparse
import os
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


MAX_COMMANDS = 3000
FIXED_CASES_DIR = Path(__file__).resolve().parent / "fixed_cases_hw13"
ISBNS = ["A-0000", "A-0001", "B-0000", "B-0001", "C-0000", "C-0001"]
STUDENTS = ["23370001", "23370002", "23370003", "24370001", "24370002"]


def _normalize_lines(text: str) -> List[str]:
    return [line.strip() for line in text.strip().splitlines() if line.strip()]


def _write_case(out_dir: str, filename: str, lines: List[str]) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, filename), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines).rstrip())
        f.write("\n")


def _load_fixed_cases_from_dir() -> List[Tuple[str, List[str]]]:
    cases: List[Tuple[str, List[str]]] = []
    if not FIXED_CASES_DIR.is_dir():
        return cases
    for path in sorted(FIXED_CASES_DIR.glob("*.txt")):
        lines = _normalize_lines(path.read_text(encoding="utf-8", errors="replace"))
        if lines:
            cases.append((path.name, lines[:MAX_COMMANDS]))
    return cases


def _builtin_fixed_cases() -> List[Tuple[str, List[str]]]:
    """HW13 基础固定用例。只包含 queried/borrowed/ordered/returned/picked。"""
    return [
        ("h13_public_01_borrow_return.txt", _normalize_lines("""
            3
            A-0000 2
            B-0000 2
            C-0000 2
            [2026-01-05] OPEN
            [2026-01-05] 23370001 borrowed B-0000
            [2026-01-05] 23370002 borrowed C-0000
            [2026-01-05] 23370003 queried A-0000-01
            [2026-01-05] CLOSE
            [2026-01-06] OPEN
            [2026-01-06] 23370001 returned B-0000-01
            [2026-01-06] 23370002 queried C-0000-01
            [2026-01-06] CLOSE
        """)),
        ("h13_public_02_order_and_pick.txt", _normalize_lines("""
            2
            B-0000 1
            C-0000 1
            [2026-01-05] OPEN
            [2026-01-05] 23370001 ordered B-0000
            [2026-01-05] 23370002 ordered C-0000
            [2026-01-05] CLOSE
            [2026-01-06] OPEN
            [2026-01-06] 23370001 picked B-0000
            [2026-01-06] 23370002 picked C-0000
            [2026-01-06] CLOSE
        """)),
        ("h13_public_03_order_expire.txt", _normalize_lines("""
            1
            B-0000 1
            [2026-01-05] OPEN
            [2026-01-05] 23370001 ordered B-0000
            [2026-01-05] CLOSE
            [2026-01-10] OPEN
            [2026-01-10] 23370002 ordered B-0000
            [2026-01-10] CLOSE
            [2026-01-11] OPEN
            [2026-01-11] 23370002 picked B-0000
            [2026-01-11] CLOSE
        """)),
        ("h13_fixed_01_typeA_reject.txt", _normalize_lines("""
            1
            A-0000 1
            [2026-01-05] OPEN
            [2026-01-05] 23370001 borrowed A-0000
            [2026-01-05] 23370001 ordered A-0000
            [2026-01-05] 23370001 queried A-0000-01
            [2026-01-05] CLOSE
        """)),
        ("h13_fixed_02_typeB_only_one.txt", _normalize_lines("""
            2
            B-0000 1
            B-0001 1
            [2026-01-05] OPEN
            [2026-01-05] 23370001 borrowed B-0000
            [2026-01-05] 23370001 borrowed B-0001
            [2026-01-05] CLOSE
            [2026-01-06] OPEN
            [2026-01-06] 23370001 returned B-0000-01
            [2026-01-06] 23370001 borrowed B-0001
            [2026-01-06] CLOSE
        """)),
        ("h13_fixed_03_typeC_per_isbn.txt", _normalize_lines("""
            1
            C-0000 2
            [2026-01-05] OPEN
            [2026-01-05] 23370001 borrowed C-0000
            [2026-01-05] 23370001 borrowed C-0000
            [2026-01-05] CLOSE
        """)),
    ]


class CaseBuilder:
    def __init__(self, seed: Optional[int], max_lines: int) -> None:
        self.rng = random.Random(seed)
        self.max_lines = max(20, min(MAX_COMMANDS, max_lines))
        self.lines: List[str] = []
        self.day: date = date(2026, 3, 1)

    def emit(self, line: str) -> bool:
        if len(self.lines) >= self.max_lines:
            return False
        self.lines.append(line)
        return True

    def dated(self, body: str) -> str:
        return f"[{self.day.isoformat()}] {body}"

    def build(self) -> List[str]:
        selected = self.rng.sample(ISBNS, k=self.rng.randint(3, len(ISBNS)))
        inventory: Dict[str, int] = {
            isbn: self.rng.randint(1, 3) for isbn in selected
        }
        self.emit(str(len(inventory)))
        for isbn, count in inventory.items():
            self.emit(f"{isbn} {count}")

        while len(self.lines) < self.max_lines - 2:
            self.emit(self.dated("OPEN"))
            for _ in range(self.rng.randint(3, 8)):
                if not self.emit(self._one_cmd(inventory)):
                    break
            self.emit(self.dated("CLOSE"))
            self.day += timedelta(days=self.rng.randint(1, 3))
        return self.lines[:self.max_lines]

    def _one_cmd(self, inventory: Dict[str, int]) -> str:
        student = self.rng.choice(STUDENTS)
        isbn = self.rng.choice(list(inventory.keys()))
        # HW13 basic ops only (no read/restored/graded)
        ops = ["borrowed", "ordered", "queried", "returned", "picked"]
        op = self.rng.choice(ops)
        if op in {"returned", "queried"}:
            copy = self.rng.randint(1, inventory[isbn])
            return self.dated(f"{student} {op} {isbn}-{copy:02d}")
        return self.dated(f"{student} {op} {isbn}")


def generate_all(out_dir: str, random_count: int,
                 base_seed: Optional[int] = None,
                 max_lines: int = 3000) -> List[str]:
    generated: List[str] = []

    fixed = _load_fixed_cases_from_dir()
    if not fixed:
        fixed = _builtin_fixed_cases()
    for name, lines in fixed:
        _write_case(out_dir, name, lines[:MAX_COMMANDS])
        generated.append(name)

    for i in range(max(0, random_count)):
        seed = (base_seed + i) if base_seed is not None else (2026070500 + i)
        builder = CaseBuilder(seed=seed, max_lines=max_lines)
        lines = builder.build()
        filename = f"h13_random_{i + 1:02d}.txt"
        _write_case(out_dir, filename, lines)
        generated.append(filename)

    return generated


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="HW13 baseline library case generator")
    p.add_argument("--out-dir", default="data_hw13")
    p.add_argument("--count", type=int, default=4)
    p.add_argument("--seed", type=int, default=20260705)
    p.add_argument("--max-lines", type=int, default=260)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    names = generate_all(args.out_dir, args.count, args.seed, args.max_lines)
    for n in names:
        print(n)


if __name__ == "__main__":
    main()
