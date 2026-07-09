#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HW5 (WEI) data generator.

Generates multiple categorized test cases for the elevator homework.
Output files are written to ./data by default.
"""

from __future__ import annotations

import argparse
import os
import random
from dataclasses import dataclass
from typing import Dict, List, Optional

FLOORS_INT = [-4, -3, -2, -1, 1, 2, 3, 4, 5, 6, 7]
FLOORS_STR = {
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

NUM_ELEVATORS = 6
MAX_REQ_PER_ELEVATOR = 30
MAX_TOTAL_REQ = 70
MIN_TIMESTAMP = 1.0
MAX_TIMESTAMP = 50.0
MIN_WEIGHT = 50
MAX_WEIGHT = 100


@dataclass
class Request:
    ts: float
    pid: int
    wei: int
    from_floor: int
    to_floor: int
    by: int

    def serialize(self) -> str:
        return (
            f"[{self.ts:.1f}]"
            f"{self.pid}-WEI-{self.wei}"
            f"-FROM-{FLOORS_STR[self.from_floor]}"
            f"-TO-{FLOORS_STR[self.to_floor]}"
            f"-BY-{self.by}"
        )


class CaseBuilder:
    def __init__(self, start_pid: int) -> None:
        self.requests: List[Request] = []
        self.next_pid = start_pid
        self.used_ids = set()
        self.elevator_counts: Dict[int, int] = {i: 0 for i in range(1, NUM_ELEVATORS + 1)}

    def add(self, ts: float, wei: int, from_floor: int, to_floor: int, by: int) -> None:
        if len(self.requests) >= MAX_TOTAL_REQ:
            raise ValueError("too many requests in one case")
        if by < 1 or by > NUM_ELEVATORS:
            raise ValueError("invalid elevator id")
        if self.elevator_counts[by] >= MAX_REQ_PER_ELEVATOR:
            raise ValueError(f"elevator {by} exceeds per-elevator limit")
        if from_floor == to_floor:
            raise ValueError("from floor equals to floor")
        if from_floor not in FLOORS_STR or to_floor not in FLOORS_STR:
            raise ValueError("invalid floor")
        if not (MIN_WEIGHT <= wei <= MAX_WEIGHT):
            raise ValueError("invalid weight")
        if ts < MIN_TIMESTAMP or ts > MAX_TIMESTAMP:
            raise ValueError("timestamp out of range")

        pid = self.next_pid
        self.next_pid += 1
        self.used_ids.add(pid)
        self.elevator_counts[by] += 1
        self.requests.append(Request(ts=round(ts, 1), pid=pid, wei=wei, from_floor=from_floor, to_floor=to_floor, by=by))

    def dump(self) -> List[str]:
        self.requests.sort(key=lambda x: (x.ts, x.pid))
        return [req.serialize() for req in self.requests]


def _rand_floor_diff(rng: random.Random, floor: int) -> int:
    to_floor = rng.choice(FLOORS_INT)
    while to_floor == floor:
        to_floor = rng.choice(FLOORS_INT)
    return to_floor


def case_smoke(start_pid: int) -> List[str]:
    b = CaseBuilder(start_pid)
    b.add(1.0, 65, -1, 3, 3)
    return b.dump()


def case_same_timestamp(start_pid: int) -> List[str]:
    b = CaseBuilder(start_pid)
    t = 1.0
    b.add(t, 80, 2, 6, 3)
    b.add(t, 55, 1, 5, 4)
    b.add(t, 100, -3, 4, 1)
    b.add(t, 50, 7, -2, 6)
    b.add(1.1, 70, -1, 1, 2)
    b.add(1.1, 85, 1, -1, 5)
    return b.dump()


def case_weight_boundary(start_pid: int) -> List[str]:
    b = CaseBuilder(start_pid)
    rows = [
        (1.0, 50, 1, 7, 1),
        (1.2, 100, 7, -4, 1),
        (1.4, 50, -4, 2, 1),
        (1.6, 100, 2, -3, 1),
        (1.8, 50, -3, 6, 1),
        (2.0, 100, 6, -1, 1),
    ]
    for ts, wei, frm, to, by in rows:
        b.add(ts, wei, frm, to, by)
    return b.dump()


def case_b1_f1_switch(start_pid: int) -> List[str]:
    b = CaseBuilder(start_pid)
    rows = [
        (1.0, 65, -1, 3, 2),
        (1.3, 90, 1, -2, 2),
        (1.6, 75, -1, 1, 2),
        (1.9, 60, 1, -1, 2),
        (2.2, 95, -2, 1, 2),
        (2.5, 52, 1, -4, 2),
    ]
    for ts, wei, frm, to, by in rows:
        b.add(ts, wei, frm, to, by)
    return b.dump()


def case_dense_single_elevator(start_pid: int) -> List[str]:
    b = CaseBuilder(start_pid)
    rng = random.Random(2026040601)
    t = 1.0
    for _ in range(30):
        frm = rng.choice(FLOORS_INT)
        to = _rand_floor_diff(rng, frm)
        wei = rng.randint(MIN_WEIGHT, MAX_WEIGHT)
        b.add(round(t, 1), wei, frm, to, 1)
        t = min(MAX_TIMESTAMP, t + rng.choice([0.2, 0.3, 0.4, 0.5]))
    return b.dump()


def case_dense_multi_elevator(start_pid: int) -> List[str]:
    b = CaseBuilder(start_pid)
    rng = random.Random(2026040602)
    t = 1.0
    for i in range(60):
        eid = (i % NUM_ELEVATORS) + 1
        frm = rng.choice(FLOORS_INT)
        to = _rand_floor_diff(rng, frm)
        wei = rng.randint(MIN_WEIGHT, MAX_WEIGHT)
        b.add(round(t, 1), wei, frm, to, eid)
        t = min(MAX_TIMESTAMP, t + rng.choice([0.1, 0.2, 0.2, 0.3]))
    return b.dump()


def case_random(seed: int, n: int, start_pid: int) -> List[str]:
    b = CaseBuilder(start_pid)
    rng = random.Random(seed)
    t = 1.0
    for _ in range(n):
        available = [eid for eid, cnt in b.elevator_counts.items() if cnt < MAX_REQ_PER_ELEVATOR]
        if not available:
            break
        eid = rng.choice(available)
        frm = rng.choice(FLOORS_INT)
        to = _rand_floor_diff(rng, frm)
        wei = rng.randint(MIN_WEIGHT, MAX_WEIGHT)
        b.add(round(t, 1), wei, frm, to, eid)
        t = min(MAX_TIMESTAMP, t + rng.choice([0.1, 0.2, 0.3, 0.4, 0.5]))
    return b.dump()


def write_case(out_dir: str, name: str, lines: List[str]) -> None:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")


def generate_all(
    out_dir: str,
    random_count: int,
    base_seed: Optional[int] = None,
    strict_mutual: bool = False,
) -> List[str]:
    """Generate fixed + random HW5 cases.

    Signature aligned with hw6/hw14/hw15 for GUI compatibility. ``strict_mutual``
    is accepted for symmetry but currently HW5 has no mutual-only constraints
    to enforce, so it is ignored.
    """
    _ = strict_mutual
    generated = []
    pid_cursor = 1000

    cases = [
        ("01_smoke.txt", case_smoke),
        ("02_same_timestamp.txt", case_same_timestamp),
        ("03_weight_boundary.txt", case_weight_boundary),
        ("04_b1_f1_switch.txt", case_b1_f1_switch),
        ("05_dense_single_elevator.txt", case_dense_single_elevator),
        ("06_dense_multi_elevator.txt", case_dense_multi_elevator),
    ]

    for filename, factory in cases:
        lines = factory(pid_cursor)
        pid_cursor += 200
        write_case(out_dir, filename, lines)
        generated.append(filename)

    for i in range(max(0, random_count)):
        n = 25 + (i % 4) * 10
        seed = (base_seed + i) if base_seed is not None else (2026040700 + i)
        filename = f"{7 + i:02d}_random_{n}.txt"
        lines = case_random(seed=seed, n=n, start_pid=pid_cursor)
        pid_cursor += 300
        write_case(out_dir, filename, lines)
        generated.append(filename)

    return generated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate HW5 WEI-format test cases")
    parser.add_argument("--out", default="data", help="output directory")
    parser.add_argument("--count", type=int, default=4, help="number of extra random cases")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    count = max(0, args.count)
    generated = generate_all(args.out, count)
    print(f"Generated {len(generated)} case files in '{args.out}':")
    for name in generated:
        print(f"  - {name}")


if __name__ == "__main__":
    main()
