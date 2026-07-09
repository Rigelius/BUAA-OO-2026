#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HW7 consensus judge data generator.

Design goals:
- Add HW7-specific fixed/random cases containing UPDATE/RECYCLE
- Keep mutual-mode constraints when strict_mutual=True
"""

from __future__ import annotations

import argparse
import os
import random
import re
from pathlib import Path
from typing import List, Optional, Tuple

from .engine import parse_input_requests

FLOORS = [-4, -3, -2, -1, 1, 2, 3, 4, 5, 6, 7]
FLOOR_STR = {
    -4: "B4",
    -3: "B3",
    -2: "B2",
    -1: "B1",
    1: "F1",
    2: "F2",
    3: "F3",
    4: "F4",
    5: "F5",
    6: "F6",
    7: "F7",
}

MAINT_TARGET_FLOORS = [-2, -1, 2, 3]
FIXED_CASES_DIR = Path(__file__).resolve().parent / "fixed_cases"

RE_PASSENGER = re.compile(
    r"^\[(\d+\.\d)\](\d+)-WEI-(\d+)-FROM-([BF]\d+)-TO-([BF]\d+)$"
)
RE_MAINT = re.compile(r"^\[(\d+\.\d)\]MAINT-(\d+)-(\d+)-([BF]\d+)$")
RE_UPDATE = re.compile(r"^\[(\d+\.\d)\]UPDATE-(\d+)$")
RE_RECYCLE = re.compile(r"^\[(\d+\.\d)\]RECYCLE-(\d+)$")


def _format_floor(floor: int) -> str:
    return FLOOR_STR[floor]


def _normalize_lines(text: str) -> List[str]:
    return [line.strip() for line in text.strip().splitlines() if line.strip()]


def _write_case(out_dir: str, filename: str, lines: List[str]) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, filename), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")


def _load_fixed_cases_from_dir() -> List[Tuple[str, List[str]]]:
    cases: List[Tuple[str, List[str]]] = []
    if not FIXED_CASES_DIR.is_dir():
        return cases

    for case_file in sorted(FIXED_CASES_DIR.glob("*.txt")):
        try:
            raw = case_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = _normalize_lines(raw)
        if lines:
            cases.append((case_file.name, lines))
    return cases


def _is_mutual_valid(lines: List[str]) -> bool:
    text = "\n".join(lines) + "\n"
    _, _, errors = parse_input_requests(text, mutual_mode=True)
    return len(errors) == 0


def _hw7_fixed_cases() -> List[Tuple[str, List[str]]]:
    cases: List[Tuple[str, List[str]]] = []

    cases.append(
        (
            "h7_fixed_01_update_recycle_basic.txt",
            _normalize_lines(
                """
                [1.0]UPDATE-1
                [8.0]1001-WEI-65-FROM-B1-TO-F5
                [20.0]RECYCLE-7
                """
            ),
        )
    )

    cases.append(
        (
            "h7_fixed_02_maint_basic.txt",
            _normalize_lines(
                """
                [1.0]1002-WEI-80-FROM-B2-TO-F6
                [2.0]MAINT-2-2002-F2
                [12.0]1003-WEI-70-FROM-F6-TO-B3
                """
            ),
        )
    )

    cases.append(
        (
            "h7_fixed_03_mixed_multi_shaft.txt",
            _normalize_lines(
                """
                [1.0]UPDATE-3
                [2.5]1004-WEI-70-FROM-F1-TO-F7
                [3.0]1005-WEI-55-FROM-B4-TO-F3
                [9.5]MAINT-5-2005-B1
                [15.0]RECYCLE-9
                [18.5]1006-WEI-92-FROM-F7-TO-B2
                """
            ),
        )
    )

    cases.append(
        (
            "h7_fixed_04_transfer_pressure.txt",
            _normalize_lines(
                """
                [1.0]UPDATE-4
                [6.0]1007-WEI-90-FROM-B3-TO-F6
                [6.1]1008-WEI-88-FROM-B2-TO-F7
                [6.2]1009-WEI-76-FROM-F7-TO-B4
                [6.3]1010-WEI-60-FROM-F6-TO-B3
                [18.0]RECYCLE-10
                """
            ),
        )
    )

    cases.append(
        (
            "h7_fixed_05_parallel_specials.txt",
            _normalize_lines(
                """
                [1.0]UPDATE-1
                [1.2]UPDATE-2
                [1.4]MAINT-3-3003-F3
                [1.6]MAINT-4-3004-B1
                [2.0]1011-WEI-100-FROM-B4-TO-F7
                [2.0]1012-WEI-95-FROM-F7-TO-B4
                [18.0]RECYCLE-7
                [19.0]RECYCLE-8
                """
            ),
        )
    )

    cases.append(
        (
            "h7_fixed_06_tail_window.txt",
            _normalize_lines(
                """
                [1.0]UPDATE-6
                [4.0]1013-WEI-75-FROM-F2-TO-B4
                [40.0]1014-WEI-66-FROM-B1-TO-F7
                [48.5]RECYCLE-12
                [49.5]1015-WEI-58-FROM-F7-TO-F2
                """
            ),
        )
    )

    cases.append(
        (
            "h7_fixed_07_update_then_maint_other_shaft.txt",
            _normalize_lines(
                """
                [1.0]UPDATE-2
                [5.0]1016-WEI-65-FROM-B2-TO-F7
                [11.0]MAINT-6-3606-B2
                [16.0]RECYCLE-8
                [22.0]1017-WEI-82-FROM-F7-TO-B2
                """
            ),
        )
    )

    cases.append(
        (
            "h7_fixed_08_dense_passenger_with_double.txt",
            _normalize_lines(
                """
                [1.0]UPDATE-5
                [3.0]1018-WEI-80-FROM-B4-TO-F7
                [3.1]1019-WEI-80-FROM-B3-TO-F6
                [3.2]1020-WEI-80-FROM-B2-TO-F5
                [3.3]1021-WEI-80-FROM-B1-TO-F4
                [3.4]1022-WEI-80-FROM-F1-TO-F7
                [3.5]1023-WEI-80-FROM-F2-TO-B4
                [17.0]RECYCLE-11
                """
            ),
        )
    )

    return cases


def _gen_random_passenger(rng: random.Random, pid: int) -> str:
    frm = rng.choice(FLOORS)
    to = rng.choice(FLOORS)
    while to == frm:
        to = rng.choice(FLOORS)
    wei = rng.randint(50, 100)
    ts = round(rng.uniform(1.0, 50.0), 1)
    return f"[{ts:.1f}]{pid}-WEI-{wei}-FROM-{_format_floor(frm)}-TO-{_format_floor(to)}"


def _generate_hw7_random_case(seed: Optional[int], start_id: int, strict_mutual: bool) -> List[str]:
    rng = random.Random(seed)
    next_id = start_id

    events: List[Tuple[float, int, str]] = []
    order = 0

    # Per-shaft special action plan:
    # 0: none, 1: maint, 2: update+recycle
    for sid in range(1, 7):
        pick = rng.random()
        if pick < 0.28:
            t_maint = round(rng.uniform(2.0, 38.0), 1)
            worker_id = next_id
            next_id += 1
            target = rng.choice(MAINT_TARGET_FLOORS)
            line = f"[{t_maint:.1f}]MAINT-{sid}-{worker_id}-{_format_floor(target)}"
            events.append((t_maint, order, line))
            order += 1
        elif pick < 0.62:
            t_update = round(rng.uniform(2.0, 20.0), 1)
            t_recycle = round(min(49.5, t_update + rng.uniform(9.0, 24.0)), 1)
            line_u = f"[{t_update:.1f}]UPDATE-{sid}"
            line_r = f"[{t_recycle:.1f}]RECYCLE-{sid + 6}"
            events.append((t_update, order, line_u))
            order += 1
            events.append((t_recycle, order, line_r))
            order += 1

    max_total = 70 if strict_mutual else 100
    special_count = len(events)
    max_passengers = max(1, max_total - special_count)
    min_passengers = min(12, max_passengers)
    passenger_count = rng.randint(min_passengers, max_passengers)

    for _ in range(passenger_count):
        line = _gen_random_passenger(rng, next_id)
        next_id += 1
        ts = float(line.split("]", 1)[0][1:])
        events.append((ts, order, line))
        order += 1

    events.sort(key=lambda x: (x[0], x[1]))
    lines = [e[2] for e in events]

    # Keep one-decimal formatting and mutual constraints.
    if strict_mutual and not _is_mutual_valid(lines):
        # Retry once with fewer passengers.
        trimmed = [line for line in lines if "-WEI-" not in line]
        pid_base = next_id + 1000
        for i in range(max(8, max_total - len(trimmed))):
            p_line = _gen_random_passenger(rng, pid_base + i)
            ts = float(p_line.split("]", 1)[0][1:])
            trimmed.append(p_line)
        trimmed.sort(key=lambda s: float(s.split("]", 1)[0][1:]))
        while len(trimmed) > max_total:
            # Drop last passenger first.
            for j in range(len(trimmed) - 1, -1, -1):
                if "-WEI-" in trimmed[j]:
                    trimmed.pop(j)
                    break
            else:
                trimmed.pop()
        lines = trimmed

    return lines


def generate_all(
    out_dir: str,
    random_count: int,
    base_seed: Optional[int] = None,
    strict_mutual: bool = False,
) -> List[str]:
    files: List[str] = []

    # Add fixed samples from dedicated folder first, then built-in HW7 fallback.
    seen_names = set()
    all_fixed_cases = _load_fixed_cases_from_dir() + _hw7_fixed_cases()
    for filename, lines in all_fixed_cases:
        if filename in seen_names:
            continue
        seen_names.add(filename)
        if strict_mutual and not _is_mutual_valid(lines):
            continue
        _write_case(out_dir, filename, lines)
        files.append(filename)

    # Add HW7 random samples.
    target = max(0, random_count)
    sid_cursor = 700000
    produced = 0
    attempts = 0
    max_attempts = max(20, target * 10)
    while produced < target and attempts < max_attempts:
        seed = (base_seed + attempts) if base_seed is not None else None
        lines = _generate_hw7_random_case(seed, sid_cursor, strict_mutual)
        if not strict_mutual or _is_mutual_valid(lines):
            filename = f"h7_random_{produced + 1:02d}.txt"
            _write_case(out_dir, filename, lines)
            files.append(filename)
            produced += 1
            sid_cursor += 10000
        attempts += 1

    return files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate HW7 testcases for consensus judge")
    parser.add_argument("--out", default="data", help="output directory")
    parser.add_argument("--count", type=int, default=8, help="number of HW7 random cases")
    parser.add_argument("--seed", type=int, default=None, help="base random seed")
    parser.add_argument(
        "--strict-mutual",
        action="store_true",
        help="enforce mutual-mode constraints and skip invalid cases",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generated = generate_all(args.out, args.count, args.seed, strict_mutual=args.strict_mutual)
    print(f"Generated {len(generated)} files in '{args.out}':")
    for name in generated:
        print(f"  - {name}")


if __name__ == "__main__":
    main()
