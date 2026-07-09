#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HW14 testcase generator for the library judge."""

from __future__ import annotations

import argparse
import os
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


MAX_COMMANDS = 3000
FIXED_CASES_DIR = Path(__file__).resolve().parent / "fixed_cases_hw14"
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


def _builtin_fixed_cases(profile: str = "public") -> List[Tuple[str, List[str]]]:
    public_cases = [
        ("h14_public_01_borrow_read_grade.txt", _normalize_lines("""
            3
            A-0000 2
            B-0000 2
            C-0000 2
            [2026-01-05] OPEN
            [2026-01-05] 23370001 borrowed A-0000
            [2026-01-05] 23370002 borrowed B-0000
            [2026-01-05] 23370003 read C-0000
            [2026-01-05] 23370002 graded B-0000 5
            [2026-01-05] CLOSE
            [2026-01-06] OPEN
            [2026-01-06] 23370001 read A-0000
            [2026-01-06] 23370002 borrowed B-0000
            [2026-01-06] 23370003 queried C-0000-01
            [2026-01-06] CLOSE
        """)),
        ("h14_public_02_order_arrange_pick_probe.txt", _normalize_lines("""
            2
            B-0000 1
            C-0000 1
            [2026-01-05] OPEN
            [2026-01-05] 23370001 ordered B-0000
            [2026-01-05] 23370002 ordered C-0000
            [2026-01-05] CLOSE
            [2026-01-06] OPEN
            [2026-01-06] 23370003 queried B-0000-01
            [2026-01-06] 23370001 borrowed B-0000
            [2026-01-06] CLOSE
            [2026-01-12] OPEN
            [2026-01-12] 23370003 queried C-0000-01
            [2026-01-12] CLOSE
        """)),
        ("h14_public_03_treasured_shelf.txt", _normalize_lines("""
            2
            B-0000 2
            C-0000 2
            [2026-01-06] OPEN
            [2026-01-06] 24370001 graded B-0000 5
            [2026-01-06] 24370002 graded C-0000 3
            [2026-01-06] CLOSE
            [2026-01-09] OPEN
            [2026-01-09] 24370001 borrowed B-0000
            [2026-01-09] 24370002 read B-0000
            [2026-01-09] 24370003 queried B-0000-01
            [2026-01-09] CLOSE
        """)),
        ("h14_public_04_reading_room_cleanup.txt", _normalize_lines("""
            2
            A-0000 2
            C-0000 1
            [2026-01-05] OPEN
            [2026-01-05] 23370001 read A-0000
            [2026-01-05] 23370001 read C-0000
            [2026-01-05] CLOSE
            [2026-01-06] OPEN
            [2026-01-06] 23370001 read A-0000
            [2026-01-06] 23370002 read C-0000
            [2026-01-06] CLOSE
            [2026-01-09] OPEN
            [2026-01-09] 23370003 queried A-0000-01
            [2026-01-09] CLOSE
        """)),
    ]
    if profile == "public":
        return public_cases
    return [
        *public_cases,
        ("h14_fixed_01_borrow_return_trace.txt", _normalize_lines("""
            3
            A-0000 2
            B-0000 2
            C-0000 2
            [2026-01-05] OPEN
            [2026-01-05] 23370001 borrowed A-0000
            [2026-01-05] 23370002 borrowed B-0000
            [2026-01-05] 23370003 borrowed C-0000
            [2026-01-05] CLOSE
            [2026-01-06] OPEN
            [2026-01-06] 23370002 returned B-0000-01
            [2026-01-06] 23370003 returned C-0000-01
            [2026-01-06] CLOSE
            [2026-01-07] OPEN
            [2026-01-07] 23370003 queried C-0000-01
            [2026-01-07] CLOSE
        """)),
        ("h14_fixed_02_order_pick_expire.txt", _normalize_lines("""
            2
            B-0000 1
            C-0000 1
            [2026-01-05] OPEN
            [2026-01-05] 23370001 ordered B-0000
            [2026-01-05] 23370001 ordered C-0000
            [2026-01-05] CLOSE
            [2026-01-06] OPEN
            [2026-01-06] 23370001 picked B-0000
            [2026-01-06] 23370001 picked B-0000
            [2026-01-06] CLOSE
            [2026-01-12] OPEN
            [2026-01-12] 23370002 ordered C-0000
            [2026-01-12] CLOSE
        """)),
        ("h14_fixed_03_read_restore.txt", _normalize_lines("""
            2
            A-0000 2
            C-0000 1
            [2026-01-05] OPEN
            [2026-01-05] 23370001 read A-0000
            [2026-01-05] 23370001 read C-0000
            [2026-01-05] 23370001 restored A-0000-01
            [2026-01-05] CLOSE
            [2026-01-06] OPEN
            [2026-01-06] 23370001 read C-0000
            [2026-01-06] CLOSE
            [2026-01-07] OPEN
            [2026-01-07] 23370001 queried A-0000-01
            [2026-01-07] CLOSE
        """)),
        ("h14_fixed_04_grade_treasured.txt", _normalize_lines("""
            2
            B-0000 2
            C-0000 2
            [2026-01-06] OPEN
            [2026-01-06] 24370001 borrowed B-0000
            [2026-01-06] 24370001 returned B-0000-01
            [2026-01-06] 24370001 graded B-0000 5
            [2026-01-06] CLOSE
            [2026-01-09] OPEN
            [2026-01-09] 24370002 borrowed B-0000
            [2026-01-09] 24370002 returned B-0000-02
            [2026-01-09] 24370002 graded B-0000 1
            [2026-01-09] CLOSE
            [2026-01-10] OPEN
            [2026-01-10] 24370001 queried B-0000-01
            [2026-01-10] CLOSE
        """)),
        ("h14_fixed_05_mixed_public.txt", _normalize_lines("""
            4
            A-0000 2
            B-0000 2
            B-0001 1
            C-0000 2
            [2026-01-01] OPEN
            [2026-01-01] 23370001 read A-0000
            [2026-01-01] 23370002 borrowed B-0000
            [2026-01-01] 23370003 ordered C-0000
            [2026-01-01] CLOSE
            [2026-01-02] OPEN
            [2026-01-02] 23370003 picked C-0000
            [2026-01-02] 23370001 restored A-0000-01
            [2026-01-02] 23370002 returned B-0000-01
            [2026-01-02] 23370002 graded B-0000 4
            [2026-01-02] CLOSE
            [2026-01-03] OPEN
            [2026-01-03] 23370002 borrowed B-0001
            [2026-01-03] 23370002 borrowed B-0000
            [2026-01-03] 23370003 returned C-0000-01
            [2026-01-03] CLOSE
        """)),
    ]


class CaseBuilder:
    def __init__(self, seed: Optional[int], max_lines: int,
                 profile: str = "public") -> None:
        self.rng = random.Random(seed)
        self.max_lines = max(20, min(MAX_COMMANDS, max_lines))
        self.profile = profile
        self.inventory: Dict[str, int] = {
            isbn: self.rng.randint(1, 3) for isbn in ISBNS
        }
        self.lines: List[str] = []
        self.day = date(2026, 1, 1)

    def emit(self, line: str) -> bool:
        if len(self.lines) >= self.max_lines:
            return False
        self.lines.append(line)
        return True

    def header(self) -> None:
        nonzero = [(isbn, count) for isbn, count in self.inventory.items() if count > 0]
        self.emit(str(len(nonzero)))
        for isbn, count in nonzero:
            self.emit(f"{isbn} {count}")

    def dated(self, text: str) -> str:
        return f"[{self.day.isoformat()}] {text}"

    def random_request(self) -> str:
        student = self.rng.choice(STUDENTS)
        isbn = self.rng.choice(ISBNS)
        copy = f"{isbn}-{self.rng.randint(1, max(1, self.inventory.get(isbn, 1))):02d}"
        if self.profile == "public":
            ops = ["borrowed", "ordered", "queried", "read", "graded"]
            weights = [24, 18, 14, 24, 20]
        else:
            ops = ["borrowed", "ordered", "picked", "returned", "queried", "read", "restored", "graded"]
            weights = [20, 15, 10, 10, 10, 15, 10, 10]
        op = self.rng.choices(ops, weights=weights)[0]
        if op in {"returned", "queried", "restored"}:
            return self.dated(f"{student} {op} {copy}")
        if op == "graded":
            return self.dated(f"{student} graded {isbn} {self.rng.randint(1, 5)}")
        return self.dated(f"{student} {op} {isbn}")

    def build(self) -> List[str]:
        self.header()
        while len(self.lines) < self.max_lines - 2:
            self.emit(self.dated("OPEN"))
            for _ in range(self.rng.randint(3, 8)):
                if not self.emit(self.random_request()):
                    break
            self.emit(self.dated("CLOSE"))
            self.day += timedelta(days=self.rng.randint(1, 2))
        return self.lines[:self.max_lines]


def generate_all(out_dir: str, random_count: int,
                 base_seed: Optional[int] = None, max_lines: int = 3000,
                 profile: str = "public") -> List[str]:
    files: List[str] = []
    seen = set()
    for name, lines in _load_fixed_cases_from_dir() + _builtin_fixed_cases(profile):
        if name in seen:
            continue
        seen.add(name)
        _write_case(out_dir, name, lines[:MAX_COMMANDS])
        files.append(name)
    for i in range(max(0, random_count)):
        seed = (base_seed + i) if base_seed is not None else None
        filename = f"h14_random_{i + 1:02d}.txt"
        _write_case(out_dir, filename, CaseBuilder(seed, max_lines, profile).build())
        files.append(filename)
    return files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate HW14 testcases")
    parser.add_argument("--out", default="data_hw14")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260607)
    parser.add_argument("--max-lines", type=int, default=3000)
    parser.add_argument("--profile", choices=["public", "full"], default="public")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    files = generate_all(args.out, args.count, args.seed, args.max_lines, args.profile)
    print(f"Generated {len(files)} files in '{args.out}':")
    for name in files:
        print(f"  - {name}")


if __name__ == "__main__":
    main()
