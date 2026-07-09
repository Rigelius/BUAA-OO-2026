#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HW6 consensus judge data generator.

All generated cases satisfy HW6 mutual-test constraints:
- total instruction count: 1..70 (passenger + MAINT)
- first timestamp >= 1.0
- last  timestamp <= 50.0
- passenger weight: 50..100
- floor range: B4..B1, F1..F7
- passenger format: [ts]pid-WEI-weight-FROM-floor-TO-floor  (no BY)
- MAINT format:     [ts]MAINT-elevatorID-workerID-targetFloor
- MAINT target floors in {B2, B1, F2, F3}
- at most 1 MAINT per elevator
- all IDs (passenger + MAINT worker) are unique positive integers
- same elevator's two MAINT commands at least 8s apart (guaranteed by max 1)
"""

from __future__ import annotations

import argparse
import os
import random
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

FLOORS = [-4, -3, -2, -1, 1, 2, 3, 4, 5, 6, 7]
FLOOR_STR = {
    -4: "B4", -3: "B3", -2: "B2", -1: "B1",
    1: "F1", 2: "F2", 3: "F3", 4: "F4",
    5: "F5", 6: "F6", 7: "F7",
}

ELEVATOR_MIN = 1
ELEVATOR_MAX = 6
MAX_TOTAL_INSTRUCTIONS = 70
MIN_TS = 1.0
MAX_TS = 50.0
MIN_WEIGHT = 50
MAX_WEIGHT = 100

# MAINT target floors: B2, B1, F2, F3
MAINT_TARGET_FLOORS = [-2, -1, 2, 3]

RE_PASSENGER_LINE = re.compile(
    r"^\[\s*([\d.]+)\s*\](\d+)-WEI-(\d+)-FROM-([BF]\d+)-TO-([BF]\d+)$"
)
RE_MAINT_LINE = re.compile(
    r"^\[\s*([\d.]+)\s*\]MAINT-(\d+)-(\d+)-([BF]\d+)$"
)


@dataclass
class PassengerRequest:
    ts: float
    pid: int
    wei: int
    from_floor: int
    to_floor: int

    def to_line(self) -> str:
        return (
            f"[{self.ts:.1f}]"
            f"{self.pid}-WEI-{self.wei}"
            f"-FROM-{FLOOR_STR[self.from_floor]}"
            f"-TO-{FLOOR_STR[self.to_floor]}"
        )


@dataclass
class MaintRequest:
    ts: float
    elevator_id: int
    worker_id: int
    target_floor: int

    def to_line(self) -> str:
        return (
            f"[{self.ts:.1f}]"
            f"MAINT-{self.elevator_id}"
            f"-{self.worker_id}"
            f"-{FLOOR_STR[self.target_floor]}"
        )


class CaseBuilder:
    """Builds a single test case with both passenger and MAINT requests."""

    def __init__(self, start_id: int) -> None:
        self._next_id = start_id
        self._used_ids: Set[int] = set()
        self._rows: List[object] = []   # PassengerRequest | MaintRequest
        self._last_maint_ts: Dict[int, float] = {}  # elevator_id -> last MAINT timestamp

    @property
    def next_id(self) -> int:
        return self._next_id

    def _alloc_id(self) -> int:
        pid = self._next_id
        self._used_ids.add(pid)
        self._next_id += 1
        return pid

    def add_passenger(self, ts: float, wei: int, from_floor: int, to_floor: int) -> None:
        if len(self._rows) >= MAX_TOTAL_INSTRUCTIONS:
            raise ValueError("too many instructions in one case")
        if from_floor == to_floor:
            raise ValueError("from == to is not allowed")
        if from_floor not in FLOOR_STR or to_floor not in FLOOR_STR:
            raise ValueError("invalid floor")
        if not (MIN_WEIGHT <= wei <= MAX_WEIGHT):
            raise ValueError("invalid weight")
        if not (MIN_TS <= ts <= MAX_TS):
            raise ValueError("timestamp out of range")

        pid = self._alloc_id()
        self._rows.append(PassengerRequest(
            ts=round(ts, 1), pid=pid, wei=wei,
            from_floor=from_floor, to_floor=to_floor,
        ))

    def add_maint(self, ts: float, elevator_id: int, target_floor: int) -> None:
        if len(self._rows) >= MAX_TOTAL_INSTRUCTIONS:
            raise ValueError("too many instructions in one case")
        if elevator_id < ELEVATOR_MIN or elevator_id > ELEVATOR_MAX:
            raise ValueError("invalid elevator id")
        if elevator_id in self._last_maint_ts and ts < self._last_maint_ts[elevator_id] + 8.0:
            raise ValueError(f"elevator {elevator_id} MAINT interval < 8.0s")
        if target_floor not in MAINT_TARGET_FLOORS:
            raise ValueError(f"invalid MAINT target floor {target_floor}")
        if not (MIN_TS <= ts <= MAX_TS):
            raise ValueError("timestamp out of range")

        worker_id = self._alloc_id()
        self._last_maint_ts[elevator_id] = ts
        self._rows.append(MaintRequest(
            ts=round(ts, 1), elevator_id=elevator_id,
            worker_id=worker_id, target_floor=target_floor,
        ))

    def lines(self) -> List[str]:
        self._rows.sort(key=lambda r: (r.ts, getattr(r, 'pid', 0) or getattr(r, 'worker_id', 0)))
        return [r.to_line() for r in self._rows]


# Helper

def rand_to_floor(rng: random.Random, frm: int) -> int:
    to = rng.choice(FLOORS)
    while to == frm:
        to = rng.choice(FLOORS)
    return to


def floor_to_int(floor_str: str) -> Optional[int]:
    for k, v in FLOOR_STR.items():
        if v == floor_str:
            return k
    return None


# Fixed cases

# [EASY ADD] Put raw strings here to add fixed cases.
# File names are auto-generated as custom_auto_XX.txt by list order.
CUSTOM_STRING_CASES = [
    """
[1.0]MAINT-2-102-F2
[1.0]MAINT-3-103-F3
[1.0]MAINT-4-104-B1
[1.0]MAINT-5-105-B2
[1.0]MAINT-6-106-F2
[1.5]1-WEI-100-FROM-B4-TO-F7
[1.5]2-WEI-100-FROM-B4-TO-F7
[1.5]3-WEI-100-FROM-B4-TO-F7
[1.5]4-WEI-100-FROM-B4-TO-F7
[1.5]5-WEI-100-FROM-B4-TO-F7
[1.5]6-WEI-100-FROM-B4-TO-F7
[1.5]7-WEI-100-FROM-B4-TO-F7
[1.5]8-WEI-100-FROM-B4-TO-F7
[1.5]9-WEI-100-FROM-B4-TO-F7
[1.5]10-WEI-100-FROM-B4-TO-F7
[1.5]11-WEI-100-FROM-B4-TO-F7
[1.5]12-WEI-100-FROM-B4-TO-F7
[1.5]13-WEI-100-FROM-B4-TO-F7
[1.5]14-WEI-100-FROM-B4-TO-F7
[1.5]15-WEI-100-FROM-B4-TO-F7
[1.5]16-WEI-100-FROM-B4-TO-F7
[1.5]17-WEI-100-FROM-B4-TO-F7
[1.5]18-WEI-100-FROM-B4-TO-F7
[1.5]19-WEI-100-FROM-B4-TO-F7
[1.5]20-WEI-100-FROM-B4-TO-F7
[1.5]21-WEI-100-FROM-B4-TO-F7
[1.5]22-WEI-100-FROM-B4-TO-F7
[1.5]23-WEI-100-FROM-B4-TO-F7
[1.5]24-WEI-100-FROM-B4-TO-F7
[1.5]25-WEI-100-FROM-B4-TO-F7
[1.5]26-WEI-100-FROM-B4-TO-F7
[1.5]27-WEI-100-FROM-B4-TO-F7
[1.5]28-WEI-100-FROM-B4-TO-F7
[1.5]29-WEI-100-FROM-B4-TO-F7
[1.5]30-WEI-100-FROM-B4-TO-F7
[1.5]31-WEI-100-FROM-B4-TO-F7
[1.5]32-WEI-100-FROM-B4-TO-F7
[1.5]33-WEI-100-FROM-B4-TO-F7
[1.5]34-WEI-100-FROM-B4-TO-F7
[1.5]35-WEI-100-FROM-B4-TO-F7
[1.5]36-WEI-100-FROM-B4-TO-F7
[1.5]37-WEI-100-FROM-B4-TO-F7
[1.5]38-WEI-100-FROM-B4-TO-F7
[1.5]39-WEI-100-FROM-B4-TO-F7
[1.5]40-WEI-100-FROM-B4-TO-F7
[1.5]41-WEI-100-FROM-B4-TO-F7
[1.5]42-WEI-100-FROM-B4-TO-F7
[1.5]43-WEI-100-FROM-B4-TO-F7
[1.5]44-WEI-100-FROM-B4-TO-F7
[1.5]45-WEI-100-FROM-B4-TO-F7
[1.5]46-WEI-100-FROM-B4-TO-F7
[1.5]47-WEI-100-FROM-B4-TO-F7
[1.5]48-WEI-100-FROM-B4-TO-F7
[1.5]49-WEI-100-FROM-B4-TO-F7
[1.5]50-WEI-100-FROM-B4-TO-F7
[1.5]51-WEI-100-FROM-B4-TO-F7
[1.5]52-WEI-100-FROM-B4-TO-F7
[1.5]53-WEI-100-FROM-B4-TO-F7
[1.5]54-WEI-100-FROM-B4-TO-F7
[1.5]55-WEI-100-FROM-B4-TO-F7
[1.5]56-WEI-100-FROM-B4-TO-F7
[1.5]57-WEI-100-FROM-B4-TO-F7
[1.5]58-WEI-100-FROM-B4-TO-F7
[1.5]59-WEI-100-FROM-B4-TO-F7
[1.5]60-WEI-100-FROM-B4-TO-F7
""",
"""
[1.0]1-WEI-100-FROM-F1-TO-F7
[1.0]2-WEI-100-FROM-F1-TO-F7
[1.0]3-WEI-100-FROM-F1-TO-F7
[1.0]4-WEI-100-FROM-F1-TO-F7
[1.0]5-WEI-100-FROM-F1-TO-F7
[1.0]6-WEI-100-FROM-F1-TO-F7
[1.0]7-WEI-100-FROM-F1-TO-F7
[1.0]8-WEI-100-FROM-F1-TO-F7
[1.0]9-WEI-100-FROM-F1-TO-F7
[1.0]10-WEI-100-FROM-F1-TO-F7
[1.0]11-WEI-100-FROM-F1-TO-F7
[1.0]12-WEI-100-FROM-F1-TO-F7
[1.0]13-WEI-100-FROM-F1-TO-F7
[1.0]14-WEI-100-FROM-F1-TO-F7
[1.0]15-WEI-100-FROM-F1-TO-F7
[1.0]16-WEI-100-FROM-F1-TO-F7
[1.0]17-WEI-100-FROM-F1-TO-F7
[1.0]18-WEI-100-FROM-F1-TO-F7
[1.0]19-WEI-100-FROM-F1-TO-F7
[1.0]20-WEI-100-FROM-F1-TO-F7
[1.0]21-WEI-100-FROM-F1-TO-F7
[1.0]22-WEI-100-FROM-F1-TO-F7
[1.0]23-WEI-100-FROM-F1-TO-F7
[1.0]24-WEI-100-FROM-F1-TO-F7
[1.0]25-WEI-100-FROM-F1-TO-F7
[1.0]26-WEI-100-FROM-F1-TO-F7
[1.0]27-WEI-100-FROM-F1-TO-F7
[1.0]28-WEI-100-FROM-F1-TO-F7
[1.0]29-WEI-100-FROM-F1-TO-F7
[1.0]30-WEI-100-FROM-F1-TO-F7
[1.0]31-WEI-100-FROM-F1-TO-F7
[1.0]32-WEI-100-FROM-F1-TO-F7
[1.0]33-WEI-100-FROM-F1-TO-F7
[1.0]34-WEI-100-FROM-F1-TO-F7
[1.0]35-WEI-100-FROM-F1-TO-F7
[1.0]36-WEI-100-FROM-F1-TO-F7
[1.0]37-WEI-100-FROM-F1-TO-F7
[1.0]38-WEI-100-FROM-F1-TO-F7
[1.0]39-WEI-100-FROM-F1-TO-F7
[1.0]40-WEI-100-FROM-F1-TO-F7
""",
"""
[1.0]1-WEI-60-FROM-F1-TO-F7
[1.0]2-WEI-65-FROM-F2-TO-B1
[1.0]3-WEI-70-FROM-F3-TO-B2
[1.0]4-WEI-75-FROM-F4-TO-B3
[1.0]5-WEI-80-FROM-F5-TO-B4
[1.0]6-WEI-85-FROM-F6-TO-F1
[1.0]7-WEI-90-FROM-F7-TO-F2
[1.0]8-WEI-95-FROM-B1-TO-F6
[1.0]9-WEI-100-FROM-B2-TO-F5
[1.0]10-WEI-50-FROM-B3-TO-F4
[1.0]11-WEI-55-FROM-B4-TO-F3
[3.5]MAINT-1-101-F2
[3.5]MAINT-2-102-F2
[3.5]MAINT-3-103-F2
[3.5]MAINT-4-104-F2
[3.5]MAINT-5-105-F2
[3.5]MAINT-6-106-F2
""",
    
    """[1.0]1-WEI-60-FROM-F2-TO-F7
[1.0]2-WEI-60-FROM-F2-TO-F7
[1.0]3-WEI-60-FROM-F2-TO-F7
[1.0]4-WEI-60-FROM-F2-TO-F7
[1.0]5-WEI-60-FROM-F2-TO-F7
[3.5]6-WEI-100-FROM-F1-TO-F2
[3.5]7-WEI-100-FROM-F1-TO-F2
[3.5]8-WEI-100-FROM-F1-TO-F2
[3.5]9-WEI-100-FROM-F1-TO-F2
[3.5]10-WEI-100-FROM-F1-TO-F2
[3.5]11-WEI-100-FROM-F1-TO-F2
[3.5]12-WEI-100-FROM-F1-TO-F2
[3.5]13-WEI-100-FROM-F1-TO-F2
[3.5]14-WEI-100-FROM-F1-TO-F2
[3.5]15-WEI-100-FROM-F1-TO-F2
[3.5]16-WEI-100-FROM-F1-TO-F2
[3.5]17-WEI-100-FROM-F1-TO-F2
[3.5]18-WEI-100-FROM-F1-TO-F2
[3.5]19-WEI-100-FROM-F1-TO-F2
[3.5]20-WEI-100-FROM-F1-TO-F2
[3.5]21-WEI-100-FROM-F1-TO-F2
[3.5]22-WEI-100-FROM-F1-TO-F2
[3.5]23-WEI-100-FROM-F1-TO-F2
[3.5]24-WEI-100-FROM-F1-TO-F2
[3.5]25-WEI-100-FROM-F1-TO-F2
""",
"""
[1.0]MAINT-2-102-F2
[1.0]MAINT-3-103-F2
[1.0]MAINT-4-104-F2
[1.0]MAINT-5-105-F2
[1.0]MAINT-6-106-F2
[1.2]26-WEI-80-FROM-F1-TO-F7
[1.2]27-WEI-80-FROM-F1-TO-F7
[1.2]28-WEI-80-FROM-F1-TO-F7
[1.2]29-WEI-80-FROM-F1-TO-F7
[1.2]30-WEI-80-FROM-F1-TO-F7
[1.2]31-WEI-80-FROM-F1-TO-F7
[1.2]32-WEI-80-FROM-F1-TO-F7
[1.2]33-WEI-80-FROM-F1-TO-F7
[1.2]34-WEI-80-FROM-F1-TO-F7
[1.2]35-WEI-80-FROM-F1-TO-F7
[1.2]36-WEI-80-FROM-F1-TO-F7
[1.2]37-WEI-80-FROM-F1-TO-F7
[1.2]38-WEI-80-FROM-F1-TO-F7
[1.2]39-WEI-80-FROM-F1-TO-F7
[1.2]40-WEI-80-FROM-F1-TO-F7
[5.0]41-WEI-90-FROM-F1-TO-B4
[5.0]42-WEI-90-FROM-F1-TO-B4
[5.0]43-WEI-90-FROM-F1-TO-B4
[5.0]44-WEI-90-FROM-F1-TO-B4
[5.0]45-WEI-90-FROM-F1-TO-B4
[5.0]46-WEI-90-FROM-F1-TO-B4
[5.0]47-WEI-90-FROM-F1-TO-B4
[5.0]48-WEI-90-FROM-F1-TO-B4
[5.0]49-WEI-90-FROM-F1-TO-B4
[5.0]50-WEI-90-FROM-F1-TO-B4
""",

    
"""
[1.0]51-WEI-100-FROM-F1-TO-F2
[1.0]52-WEI-100-FROM-F1-TO-F2
[1.0]53-WEI-100-FROM-F1-TO-F2
[1.0]54-WEI-100-FROM-F1-TO-F2
[1.0]55-WEI-100-FROM-F1-TO-F2
[1.0]56-WEI-100-FROM-F1-TO-F2
[1.0]57-WEI-100-FROM-F1-TO-F2
[1.0]58-WEI-100-FROM-F1-TO-F2
[1.0]59-WEI-100-FROM-F1-TO-F2
[1.0]60-WEI-100-FROM-F1-TO-F2
[1.0]61-WEI-100-FROM-F1-TO-F2
[1.0]62-WEI-100-FROM-F1-TO-F2
[1.0]63-WEI-100-FROM-F1-TO-F2
[1.0]64-WEI-100-FROM-F1-TO-F2
[1.0]65-WEI-100-FROM-F1-TO-F2
[1.0]66-WEI-100-FROM-F1-TO-F2
[1.0]67-WEI-100-FROM-F1-TO-F2
[1.0]68-WEI-100-FROM-F1-TO-F2
[1.0]69-WEI-100-FROM-F1-TO-F2
[1.0]70-WEI-100-FROM-F1-TO-F2
[1.0]71-WEI-100-FROM-F1-TO-F2
[1.0]72-WEI-100-FROM-F1-TO-F2
[1.0]73-WEI-100-FROM-F1-TO-F2
[1.0]74-WEI-100-FROM-F1-TO-F2
[1.0]75-WEI-100-FROM-F1-TO-F2
[1.0]76-WEI-100-FROM-F1-TO-F2
[1.0]77-WEI-100-FROM-F1-TO-F2
[1.0]78-WEI-100-FROM-F1-TO-F2
[1.0]79-WEI-100-FROM-F1-TO-F2
[1.0]80-WEI-100-FROM-F1-TO-F2
[1.0]81-WEI-100-FROM-F1-TO-F2
[1.0]82-WEI-100-FROM-F1-TO-F2
[1.0]83-WEI-100-FROM-F1-TO-F2
[1.0]84-WEI-100-FROM-F1-TO-F2
[1.0]85-WEI-100-FROM-F1-TO-F2
[1.0]86-WEI-100-FROM-F1-TO-F2
[1.0]87-WEI-100-FROM-F1-TO-F2
[1.0]88-WEI-100-FROM-F1-TO-F2
[1.0]89-WEI-100-FROM-F1-TO-F2
[1.0]90-WEI-100-FROM-F1-TO-F2
[1.0]91-WEI-100-FROM-F1-TO-F2
[1.0]92-WEI-100-FROM-F1-TO-F2
[1.0]93-WEI-100-FROM-F1-TO-F2
[1.0]94-WEI-100-FROM-F1-TO-F2
[1.0]95-WEI-100-FROM-F1-TO-F2
[1.0]96-WEI-100-FROM-F1-TO-F2
[1.0]97-WEI-100-FROM-F1-TO-F2
[1.0]98-WEI-100-FROM-F1-TO-F2
[1.0]99-WEI-100-FROM-F1-TO-F2
[1.0]100-WEI-100-FROM-F1-TO-F2
[1.0]101-WEI-100-FROM-F1-TO-F2
[1.0]102-WEI-100-FROM-F1-TO-F2
[1.0]103-WEI-100-FROM-F1-TO-F2
[1.0]104-WEI-100-FROM-F1-TO-F2
[1.0]105-WEI-100-FROM-F1-TO-F2
[1.0]106-WEI-100-FROM-F1-TO-F2
[1.0]107-WEI-100-FROM-F1-TO-F2
[1.0]108-WEI-100-FROM-F1-TO-F2
[1.0]109-WEI-100-FROM-F1-TO-F2
[1.0]110-WEI-100-FROM-F1-TO-F2
[1.0]111-WEI-100-FROM-F1-TO-F2
[1.0]112-WEI-100-FROM-F1-TO-F2
[1.0]113-WEI-100-FROM-F1-TO-F2
[1.0]114-WEI-100-FROM-F1-TO-F2
[1.0]115-WEI-100-FROM-F1-TO-F2
""",

    
"""
[1.0]1-WEI-60-FROM-F1-TO-F7
[1.0]2-WEI-70-FROM-F1-TO-F5
[1.0]3-WEI-80-FROM-F1-TO-F4
[1.1]MAINT-1-100-F2
""",
"""
[1.0]4-WEI-50-FROM-F7-TO-B1
[1.2]MAINT-1-101-F3
""",
"""
[1.0]MAINT-1-101-F2
[1.0]MAINT-2-102-F2
[1.0]MAINT-3-103-F2
[1.0]MAINT-4-104-F2
[1.0]MAINT-5-105-F2
[1.0]MAINT-6-106-F2
[1.5]5-WEI-60-FROM-F2-TO-F7
[1.6]6-WEI-60-FROM-B1-TO-F4
[1.7]7-WEI-60-FROM-F3-TO-F5
""",
"""[1.0]MAINT-1-101-F2
[1.0]MAINT-2-102-F3
[1.0]MAINT-3-103-B1
[1.0]MAINT-4-104-B2
[1.0]MAINT-5-105-F2
[1.5]1-WEI-80-FROM-F1-TO-F7
[1.5]2-WEI-80-FROM-F1-TO-F7
[1.5]3-WEI-80-FROM-F1-TO-F7
[1.5]4-WEI-80-FROM-F1-TO-F7
[1.5]5-WEI-80-FROM-F1-TO-F7
[1.5]6-WEI-80-FROM-F2-TO-B4
[1.5]7-WEI-80-FROM-F2-TO-B4
[1.5]8-WEI-80-FROM-F2-TO-B4
[1.5]9-WEI-80-FROM-F2-TO-B4
[1.5]10-WEI-80-FROM-F2-TO-B4
[1.6]11-WEI-80-FROM-F3-TO-B3
[1.6]12-WEI-80-FROM-F3-TO-B3
[1.6]13-WEI-80-FROM-F3-TO-B3
[1.6]14-WEI-80-FROM-F3-TO-B3
[1.6]15-WEI-80-FROM-F3-TO-B3
[1.7]16-WEI-80-FROM-F4-TO-B2
[1.7]17-WEI-80-FROM-F4-TO-B2
[1.7]18-WEI-80-FROM-F4-TO-B2
[1.7]19-WEI-80-FROM-F4-TO-B2
[1.7]20-WEI-80-FROM-F4-TO-B2
[1.8]21-WEI-80-FROM-F5-TO-B1
[1.8]22-WEI-80-FROM-F5-TO-B1
[1.8]23-WEI-80-FROM-F5-TO-B1
[1.8]24-WEI-80-FROM-F5-TO-B1
[1.8]25-WEI-80-FROM-F5-TO-B1
[1.9]26-WEI-80-FROM-F6-TO-F1
[1.9]27-WEI-80-FROM-F6-TO-F1
[1.9]28-WEI-80-FROM-F6-TO-F1
[1.9]29-WEI-80-FROM-F6-TO-F1
[1.9]30-WEI-80-FROM-F6-TO-F1
[2.0]31-WEI-80-FROM-F7-TO-F2
[2.0]32-WEI-80-FROM-F7-TO-F2
[2.0]33-WEI-80-FROM-F7-TO-F2
[2.0]34-WEI-80-FROM-F7-TO-F2
[2.0]35-WEI-80-FROM-F7-TO-F2
[2.0]36-WEI-80-FROM-F1-TO-F7
[2.0]37-WEI-80-FROM-F1-TO-F7
[2.0]38-WEI-80-FROM-F1-TO-F7
[2.0]39-WEI-80-FROM-F1-TO-F7
[2.0]40-WEI-80-FROM-F1-TO-F7
""",
    """[1.0]1-WEI-100-FROM-B4-TO-F7
[1.0]2-WEI-100-FROM-B4-TO-F7
[1.0]3-WEI-100-FROM-B4-TO-F7
[1.0]4-WEI-100-FROM-B4-TO-F7
[1.0]5-WEI-100-FROM-B4-TO-F7
[1.0]6-WEI-100-FROM-B4-TO-F7
[1.0]7-WEI-100-FROM-B4-TO-F7
[1.0]8-WEI-100-FROM-B4-TO-F7
[1.0]9-WEI-100-FROM-B4-TO-F7
[1.0]10-WEI-100-FROM-B4-TO-F7
[1.1]11-WEI-100-FROM-B4-TO-F7
[1.1]12-WEI-100-FROM-B4-TO-F7
[1.1]13-WEI-100-FROM-B4-TO-F7
[1.1]14-WEI-100-FROM-B4-TO-F7
[1.1]15-WEI-100-FROM-B4-TO-F7
[1.1]16-WEI-100-FROM-B4-TO-F7
[1.1]17-WEI-100-FROM-B4-TO-F7
[1.1]18-WEI-100-FROM-B4-TO-F7
[1.1]19-WEI-100-FROM-B4-TO-F7
[1.1]20-WEI-100-FROM-B4-TO-F7
[1.2]21-WEI-100-FROM-B4-TO-F7
[1.2]22-WEI-100-FROM-B4-TO-F7
[1.2]23-WEI-100-FROM-B4-TO-F7
[1.2]24-WEI-100-FROM-B4-TO-F7
[1.2]25-WEI-100-FROM-B4-TO-F7
[1.2]26-WEI-100-FROM-B4-TO-F7
[1.2]27-WEI-100-FROM-B4-TO-F7
[1.2]28-WEI-100-FROM-B4-TO-F7
[1.2]29-WEI-100-FROM-B4-TO-F7
[1.2]30-WEI-100-FROM-B4-TO-F7
""",
"""[1.0]1-WEI-60-FROM-F1-TO-F7
[1.0]2-WEI-60-FROM-F1-TO-F7
[1.0]3-WEI-60-FROM-F1-TO-F7
[1.0]4-WEI-60-FROM-F1-TO-F7
[1.0]5-WEI-60-FROM-F1-TO-F7
[1.0]6-WEI-60-FROM-F2-TO-B4
[1.0]7-WEI-60-FROM-F2-TO-B4
[1.0]8-WEI-60-FROM-F2-TO-B4
[1.0]9-WEI-60-FROM-F2-TO-B4
[1.0]10-WEI-60-FROM-F2-TO-B4
[1.5]11-WEI-60-FROM-F3-TO-B3
[1.5]12-WEI-60-FROM-F3-TO-B3
[1.5]13-WEI-60-FROM-F3-TO-B3
[1.5]14-WEI-60-FROM-F3-TO-B3
[1.5]15-WEI-60-FROM-F3-TO-B3
[1.5]16-WEI-60-FROM-F4-TO-B2
[1.5]17-WEI-60-FROM-F4-TO-B2
[1.5]18-WEI-60-FROM-F4-TO-B2
[1.5]19-WEI-60-FROM-F4-TO-B2
[1.5]20-WEI-60-FROM-F4-TO-B2
[2.0]21-WEI-60-FROM-F5-TO-B1
[2.0]22-WEI-60-FROM-F5-TO-B1
[2.0]23-WEI-60-FROM-F5-TO-B1
[2.0]24-WEI-60-FROM-F5-TO-B1
[2.0]25-WEI-60-FROM-F5-TO-B1
[2.0]26-WEI-60-FROM-F6-TO-F1
[2.0]27-WEI-60-FROM-F6-TO-F1
[2.0]28-WEI-60-FROM-F6-TO-F1
[2.0]29-WEI-60-FROM-F6-TO-F1
[2.0]30-WEI-60-FROM-F6-TO-F1
[3.5]MAINT-1-101-B2
[3.6]MAINT-2-102-B1
[3.7]MAINT-3-103-F2
[3.8]MAINT-4-104-F3
[3.9]MAINT-5-105-B1
""",
    
    """
[1.0]16300-WEI-50-FROM-F3-TO-B1
[1.3]16301-WEI-85-FROM-F7-TO-F6
[1.7]16302-WEI-64-FROM-F4-TO-B4
[1.9]MAINT-5-16303-B1
[2.1]16304-WEI-90-FROM-F2-TO-B4
[2.6]16305-WEI-85-FROM-F1-TO-F2
[3.1]16306-WEI-85-FROM-B1-TO-F4
[3.6]16307-WEI-98-FROM-F3-TO-F4
[3.9]16308-WEI-92-FROM-B2-TO-F3
[4.3]16309-WEI-73-FROM-F6-TO-F4
[4.6]16310-WEI-86-FROM-F3-TO-F4
[4.8]16311-WEI-94-FROM-F1-TO-B3
[5.0]16312-WEI-66-FROM-F3-TO-B4
[5.2]16313-WEI-59-FROM-B4-TO-B3
[5.5]16314-WEI-99-FROM-B3-TO-F2
[5.7]16315-WEI-87-FROM-F5-TO-F2
[5.9]16316-WEI-83-FROM-F5-TO-F3
[6.0]16317-WEI-99-FROM-B4-TO-F6
[6.3]16318-WEI-93-FROM-F1-TO-B1
[6.8]16319-WEI-56-FROM-B2-TO-F7
[7.1]16320-WEI-87-FROM-F1-TO-B4
[7.4]16321-WEI-86-FROM-F3-TO-B2
[7.7]16322-WEI-64-FROM-F6-TO-F7
[7.8]MAINT-6-16323-F2
[8.2]16324-WEI-56-FROM-F5-TO-B1
[8.6]16325-WEI-59-FROM-F6-TO-F3
[8.8]16326-WEI-88-FROM-B3-TO-B2
[9.0]16327-WEI-63-FROM-F1-TO-F5
[9.4]16328-WEI-71-FROM-F4-TO-F3
[9.6]16329-WEI-78-FROM-F7-TO-B3
[10.0]16330-WEI-60-FROM-B3-TO-B2
[10.2]16331-WEI-76-FROM-B4-TO-F7
[10.6]16332-WEI-69-FROM-B3-TO-F3
[11.1]16333-WEI-88-FROM-F3-TO-F6
[11.5]16334-WEI-59-FROM-F5-TO-B2
[11.6]16335-WEI-94-FROM-B4-TO-F7
[12.0]16336-WEI-60-FROM-F5-TO-B4
[12.3]16337-WEI-70-FROM-F7-TO-F1
[12.8]16338-WEI-58-FROM-B2-TO-B4
[13.1]16339-WEI-87-FROM-F6-TO-B3
[13.2]16340-WEI-92-FROM-F2-TO-B4
[13.6]16341-WEI-97-FROM-B3-TO-F2
[14.1]16342-WEI-52-FROM-B4-TO-B2
[14.6]16343-WEI-68-FROM-B1-TO-B3
[14.7]16344-WEI-81-FROM-B3-TO-F2
[15.1]16345-WEI-57-FROM-B2-TO-F5
[15.6]16346-WEI-76-FROM-F7-TO-B3
[16.0]16347-WEI-76-FROM-F5-TO-B2
[16.2]16348-WEI-89-FROM-F3-TO-F2
[16.7]16349-WEI-82-FROM-B4-TO-F3
[16.9]16350-WEI-66-FROM-F4-TO-F7
[17.2]MAINT-1-16351-F3
[17.4]16352-WEI-89-FROM-B2-TO-F6
[17.5]MAINT-2-16353-F3
[17.8]16354-WEI-60-FROM-F4-TO-F1
""",
    """
[1.0]28200-WEI-90-FROM-B3-TO-B1
[1.4]28201-WEI-100-FROM-F6-TO-B4
[1.7]28202-WEI-59-FROM-F3-TO-B4
[1.9]28203-WEI-86-FROM-F2-TO-F5
[2.1]28204-WEI-55-FROM-B4-TO-B2
[2.6]28205-WEI-65-FROM-F5-TO-F3
[2.7]28206-WEI-53-FROM-F6-TO-F5
[3.1]MAINT-5-28207-F2
[3.2]MAINT-2-28208-B2
[3.7]28209-WEI-66-FROM-F5-TO-F1
[4.0]28210-WEI-97-FROM-F1-TO-F5
[4.3]28211-WEI-61-FROM-B1-TO-F2
[4.5]28212-WEI-58-FROM-B1-TO-F4
[4.7]28213-WEI-72-FROM-B2-TO-F1
[5.2]28214-WEI-81-FROM-F2-TO-F3
[5.4]MAINT-6-28215-B1
[5.8]28216-WEI-65-FROM-B4-TO-B3
[6.1]28217-WEI-83-FROM-B4-TO-B2
[6.5]28218-WEI-51-FROM-B2-TO-F3
[6.7]28219-WEI-62-FROM-B3-TO-B2
[7.0]28220-WEI-59-FROM-F3-TO-F2
[7.3]28221-WEI-74-FROM-F7-TO-B1
[7.8]28222-WEI-92-FROM-B1-TO-B4
[8.3]MAINT-1-28223-F3
[8.4]28224-WEI-63-FROM-F3-TO-B2
""",
    """
[1.0]32400-WEI-64-FROM-F1-TO-F3
[1.2]32401-WEI-80-FROM-B3-TO-B2
[1.4]32402-WEI-92-FROM-B1-TO-F4
[1.9]MAINT-6-32403-F2
[2.0]32404-WEI-73-FROM-B1-TO-F5
[2.4]32405-WEI-77-FROM-F5-TO-B2
[2.6]32406-WEI-90-FROM-F1-TO-F4
[3.1]32407-WEI-75-FROM-B4-TO-F6
[3.2]32408-WEI-82-FROM-F4-TO-B2
[3.4]32409-WEI-100-FROM-F7-TO-F6
[3.9]32410-WEI-75-FROM-F5-TO-F6
[4.1]MAINT-5-32411-B2
[4.3]32412-WEI-52-FROM-F3-TO-B1
[4.8]MAINT-1-32413-B1
[4.9]MAINT-4-32414-B2
[5.4]32415-WEI-66-FROM-B2-TO-F4
[5.9]MAINT-3-32416-F3
[6.3]32417-WEI-62-FROM-B2-TO-F3
[6.7]32418-WEI-78-FROM-F3-TO-F1
[6.8]32419-WEI-88-FROM-B3-TO-F7
""",
    """
[1.0]1-WEI-50-FROM-F1-TO-F7
[1.0]2-WEI-100-FROM-F2-TO-B4
[1.0]3-WEI-60-FROM-F3-TO-B3
[1.0]4-WEI-70-FROM-F4-TO-B2
[1.0]5-WEI-80-FROM-F5-TO-B1
[1.0]6-WEI-90-FROM-F6-TO-F1
[1.0]7-WEI-55-FROM-F7-TO-F2
[1.0]8-WEI-65-FROM-B4-TO-F3
[1.0]9-WEI-75-FROM-B3-TO-F4
[1.0]10-WEI-85-FROM-B2-TO-F5
[1.0]11-WEI-95-FROM-B1-TO-F6
[1.0]12-WEI-100-FROM-F1-TO-F6
[1.0]13-WEI-50-FROM-F2-TO-F7
[1.0]14-WEI-60-FROM-F3-TO-B4
[1.0]15-WEI-70-FROM-F4-TO-B3
[1.0]16-WEI-80-FROM-F5-TO-B2
[1.0]17-WEI-90-FROM-F6-TO-B1
[1.0]18-WEI-55-FROM-F7-TO-F1
[1.0]19-WEI-65-FROM-B4-TO-F2
[1.0]20-WEI-75-FROM-B3-TO-F3
[1.0]21-WEI-85-FROM-B2-TO-F4
[1.0]22-WEI-95-FROM-B1-TO-F5
[1.0]23-WEI-100-FROM-F1-TO-F5
[1.0]24-WEI-50-FROM-F2-TO-F6
[1.0]25-WEI-60-FROM-F3-TO-F7
[1.0]26-WEI-70-FROM-F4-TO-B4
[1.0]27-WEI-80-FROM-F5-TO-B3
[1.0]28-WEI-90-FROM-F6-TO-B2
[1.0]29-WEI-55-FROM-F7-TO-B1
[1.0]30-WEI-65-FROM-B4-TO-F1
[1.0]31-WEI-75-FROM-B3-TO-F2
[1.0]32-WEI-85-FROM-B2-TO-F3
[1.0]33-WEI-95-FROM-B1-TO-F4
[1.0]34-WEI-100-FROM-F1-TO-F4
[1.0]35-WEI-50-FROM-F2-TO-F5
[1.0]36-WEI-60-FROM-F3-TO-F6
[1.0]37-WEI-70-FROM-F4-TO-F7
[1.0]38-WEI-80-FROM-F5-TO-B4
[1.0]39-WEI-90-FROM-F6-TO-B3
[1.0]40-WEI-55-FROM-F7-TO-B2
[1.0]41-WEI-65-FROM-B4-TO-B1
[1.0]42-WEI-75-FROM-B3-TO-F1
[1.0]43-WEI-85-FROM-B2-TO-F2
[1.0]44-WEI-95-FROM-B1-TO-F3
[1.0]45-WEI-100-FROM-F1-TO-F3
[1.0]46-WEI-50-FROM-F2-TO-F4
[1.0]47-WEI-60-FROM-F3-TO-F5
[1.0]48-WEI-70-FROM-F4-TO-F6
[1.0]49-WEI-80-FROM-F5-TO-F7
[1.0]50-WEI-90-FROM-F6-TO-B4
[1.0]51-WEI-55-FROM-F7-TO-B3
[1.0]52-WEI-65-FROM-B4-TO-B2
[1.0]53-WEI-75-FROM-B3-TO-B1
[1.0]54-WEI-85-FROM-B2-TO-F1
[1.0]55-WEI-95-FROM-B1-TO-F2
[1.0]56-WEI-100-FROM-F1-TO-F2
[1.0]57-WEI-50-FROM-F2-TO-F3
[1.0]58-WEI-60-FROM-F3-TO-F4
[1.0]59-WEI-70-FROM-F4-TO-F5
[1.0]60-WEI-80-FROM-F5-TO-F6
[1.0]61-WEI-90-FROM-F6-TO-F7
[1.0]62-WEI-55-FROM-F7-TO-B4
[1.0]63-WEI-65-FROM-B4-TO-B3
[1.0]64-WEI-75-FROM-B3-TO-B2
[1.0]65-WEI-85-FROM-B2-TO-B1
[1.0]66-WEI-95-FROM-B1-TO-F1
[1.0]67-WEI-50-FROM-F1-TO-B4
[1.0]68-WEI-60-FROM-F2-TO-B3
[1.0]69-WEI-70-FROM-F3-TO-B2
[1.0]70-WEI-80-FROM-F4-TO-B1
""",
    """
[1.0]MAINT-1-100-F2
[1.1]MAINT-2-101-B1
[1.2]MAINT-3-102-F3
[1.3]MAINT-4-103-B2
[1.4]MAINT-5-104-F2
[1.5]MAINT-6-105-B1
[1.6]10-WEI-50-FROM-F2-TO-F7
[1.6]11-WEI-60-FROM-F2-TO-F7
[1.6]12-WEI-70-FROM-F3-TO-B4
[1.6]13-WEI-80-FROM-F3-TO-B4
[1.7]14-WEI-90-FROM-B2-TO-F5
[1.7]15-WEI-100-FROM-B2-TO-F5
""",
    """
[1.0]201-WEI-100-FROM-B4-TO-F7
[1.0]202-WEI-100-FROM-B4-TO-F7
[1.0]203-WEI-100-FROM-B4-TO-F7
[1.0]204-WEI-100-FROM-B4-TO-F7
[1.0]205-WEI-100-FROM-B4-TO-F7
[1.0]206-WEI-100-FROM-B4-TO-F7
""",
    """
[1.0]301-WEI-65-FROM-F7-TO-B4
[1.0]302-WEI-75-FROM-F6-TO-B4
[1.0]303-WEI-85-FROM-F5-TO-B4
[1.2]MAINT-1-110-B2
[1.2]MAINT-2-111-F3
[1.2]MAINT-3-112-B1
""",
    """
[1.0]1-WEI-58-FROM-B4-TO-F7
[1.0]2-WEI-58-FROM-B4-TO-F7
[1.0]3-WEI-58-FROM-B4-TO-F7
[1.0]4-WEI-58-FROM-B4-TO-F7
[1.0]5-WEI-58-FROM-B4-TO-F7
[1.0]6-WEI-58-FROM-B4-TO-F7
[1.0]7-WEI-58-FROM-B4-TO-F7
[1.5]8-WEI-58-FROM-F7-TO-B4
[1.5]9-WEI-58-FROM-F7-TO-B4
[1.5]10-WEI-58-FROM-F7-TO-B4
[1.5]11-WEI-58-FROM-F7-TO-B4
[1.5]12-WEI-58-FROM-F7-TO-B4
[1.5]13-WEI-58-FROM-F7-TO-B4
[1.5]14-WEI-58-FROM-F7-TO-B4
""",
    """
[1.0]15-WEI-70-FROM-F1-TO-F7
[1.0]16-WEI-80-FROM-B3-TO-F5
[1.0]17-WEI-60-FROM-F6-TO-B2
[1.0]18-WEI-90-FROM-F2-TO-F4
[2.0]MAINT-1-101-B2
[3.0]19-WEI-65-FROM-F5-TO-B1
[3.0]20-WEI-75-FROM-B4-TO-F3
[4.0]MAINT-2-102-F2
[5.0]21-WEI-85-FROM-F7-TO-F1
[5.0]22-WEI-55-FROM-B2-TO-F6
[6.0]MAINT-3-103-B1
[7.0]23-WEI-95-FROM-F3-TO-F7
[7.0]24-WEI-100-FROM-F4-TO-B3
[8.0]MAINT-4-104-F3
[9.0]25-WEI-50-FROM-F1-TO-B4
[9.0]26-WEI-80-FROM-B1-TO-F2
[10.0]MAINT-5-105-B2
[10.5]27-WEI-60-FROM-F2-TO-F5
[10.5]28-WEI-70-FROM-F6-TO-B2
[10.5]29-WEI-80-FROM-B3-TO-F7
[10.5]30-WEI-90-FROM-F5-TO-B4
""",
    """
[1.5]31-WEI-60-FROM-F1-TO-F6
[1.5]32-WEI-70-FROM-F2-TO-F7
[1.5]33-WEI-80-FROM-F3-TO-B2
[1.5]34-WEI-90-FROM-F4-TO-B3
[1.5]35-WEI-100-FROM-F5-TO-B4
[1.5]MAINT-1-111-B2
[1.5]MAINT-2-112-F3
[1.5]MAINT-3-113-F2
[1.5]MAINT-4-114-B1
[1.5]MAINT-5-115-B2
""",
    """
[1.0]36-WEI-50-FROM-F1-TO-F2
[1.0]37-WEI-50-FROM-F2-TO-F3
[50.0]MAINT-1-121-B1
[50.0]MAINT-2-122-F3
[50.0]38-WEI-100-FROM-B4-TO-F7
[50.0]39-WEI-100-FROM-B3-TO-F6
[50.0]40-WEI-100-FROM-B2-TO-F5
[50.0]41-WEI-100-FROM-B1-TO-F4
[50.0]42-WEI-100-FROM-F1-TO-F3
[50.0]43-WEI-100-FROM-F2-TO-F1
[50.0]44-WEI-100-FROM-F3-TO-B1
[50.0]45-WEI-100-FROM-F4-TO-B2
[50.0]46-WEI-100-FROM-F5-TO-B3
[50.0]47-WEI-100-FROM-F6-TO-B4
[50.0]48-WEI-50-FROM-F7-TO-B4
"""
]

def smoke_case(sid: int) -> List[str]:
    """Single passenger request."""
    b = CaseBuilder(sid)
    b.add_passenger(1.0, 65, -1, 3)  # B1->F3
    return b.lines()


def same_timestamp_case(sid: int) -> List[str]:
    """Multiple passengers arriving at the same time."""
    b = CaseBuilder(sid)
    ts = 1.0
    b.add_passenger(ts, 80, 2, 6)
    b.add_passenger(ts, 55, 1, 5)
    b.add_passenger(ts, 100, -3, 4)
    b.add_passenger(ts, 50, 7, -2)
    b.add_passenger(1.1, 70, -1, 1)
    b.add_passenger(1.1, 85, 1, -1)
    return b.lines()


def weight_boundary_case(sid: int) -> List[str]:
    """Load boundary: alternate 50kg and 100kg to stress weight validation."""
    b = CaseBuilder(sid)
    rows = [
        (1.0, 50, 1, 7),
        (1.1, 100, 7, -4),
        (1.2, 50, -4, 6),
        (1.3, 100, 6, -3),
        (1.4, 50, -3, 5),
        (1.5, 100, 5, -2),
        (1.6, 100, -2, 7),
        (1.7, 100, 7, 1),
    ]
    for ts, wei, frm, to in rows:
        b.add_passenger(ts, wei, frm, to)
    return b.lines()


def maint_only_case(sid: int) -> List[str]:
    """Single maintenance request, no passengers."""
    b = CaseBuilder(sid)
    b.add_maint(1.0, 2, 2)  # elevator 2, target F2
    return b.lines()


def maint_with_passenger_case(sid: int) -> List[str]:
    """Passenger on an elevator that later receives MAINT."""
    b = CaseBuilder(sid)
    b.add_passenger(1.0, 65, -1, 5)
    b.add_maint(2.0, 1, 2)
    b.add_passenger(3.0, 80, 2, 6)
    b.add_passenger(4.0, 60, 1, -2)
    return b.lines()


def multi_maint_case(sid: int) -> List[str]:
    """Multiple elevators under maintenance at different times."""
    b = CaseBuilder(sid)
    b.add_passenger(1.0, 70, 1, 5)
    b.add_passenger(1.0, 65, -1, 3)
    b.add_maint(2.0, 1, -2)   # elevator 1, target B2
    b.add_maint(3.0, 3, 3)    # elevator 3, target F3
    b.add_passenger(4.0, 55, 2, 7)
    b.add_passenger(5.0, 90, -3, 1)
    b.add_maint(6.0, 5, -1)   # elevator 5, target B1
    b.add_passenger(7.0, 75, 4, -4)
    return b.lines()


def dense_passenger_case(sid: int) -> List[str]:
    """Dense passenger-only case (no MAINT) — stresses scheduling."""
    b = CaseBuilder(sid)
    rng = random.Random()
    ts = 1.0
    for _ in range(60):
        frm = rng.choice(FLOORS)
        to = rand_to_floor(rng, frm)
        wei = rng.randint(MIN_WEIGHT, MAX_WEIGHT)
        b.add_passenger(ts, wei, frm, to)
        ts = min(MAX_TS, round(ts + rng.choice([0.1, 0.2, 0.3, 0.4, 0.5]), 1))
    return b.lines()


def maint_stress_case(sid: int) -> List[str]:
    """Elevators receive MAINT requests throughout the session, allowing recurrent maintenance."""
    b = CaseBuilder(sid)
    rng = random.Random()
    ts = 1.0
    
    # 1. Add baseline passengers
    for _ in range(15):
        frm = rng.choice(FLOORS)
        to = rand_to_floor(rng, frm)
        b.add_passenger(ts, rng.randint(MIN_WEIGHT, MAX_WEIGHT), frm, to)
        ts = min(MAX_TS, round(ts + rng.uniform(0.1, 0.5), 1))

    # 2. Maintain elevators randomly (up to 12 MAINT requests total across 6 elevators)
    for _ in range(12):
        eid = rng.randint(1, 6)
        target = rng.choice(MAINT_TARGET_FLOORS)
        
        # Enforce 8.5s gap for safety in generator
        last_t = b._last_maint_ts.get(eid, -10.0)
        if ts > last_t + 8.5:
            b.add_maint(ts, eid, target)
        
        # Add intermittent passengers
        for _ in range(2):
            if ts < MAX_TS - 5:
                frm = rng.choice(FLOORS)
                to = rand_to_floor(rng, frm)
                b.add_passenger(ts, rng.randint(MIN_WEIGHT, MAX_WEIGHT), frm, to)
        
        ts = min(MAX_TS, round(ts + rng.uniform(2.0, 5.0), 1))
    
    # 3. Filling the rest with passengers
    while ts < MAX_TS - 2 and len(b._rows) < 80:
        frm = rng.choice(FLOORS)
        to = rand_to_floor(rng, frm)
        b.add_passenger(ts, rng.randint(MIN_WEIGHT, MAX_WEIGHT), frm, to)
        ts = min(MAX_TS, round(ts + rng.uniform(1.0, 4.0), 1))

    return b.lines()


def maint_interleave_case(sid: int) -> List[str]:
    """Passengers board elevators, then MAINT arrives almost simultaneously.
    Tests the scheduler's ability to handle mid-service maintenance interruptions."""
    b = CaseBuilder(sid)
    # Several passengers request trips that need to go through specific elevators
    b.add_passenger(1.0, 75, 1, 7)   # likely boards elevator 1
    b.add_passenger(1.0, 80, 1, -4)  # likely boards elevator 2
    b.add_passenger(1.1, 65, 1, 5)
    b.add_passenger(1.1, 90, 1, 3)
    # MAINT arrives very shortly after, targeting the elevators that may have taken passengers
    b.add_maint(1.5, 1, -1)   # elevator 1 -> B1
    b.add_maint(1.5, 2, 2)    # elevator 2 -> F2
    # More passengers pile in during the MAINT transition window
    b.add_passenger(2.0, 55, 3, -3)
    b.add_passenger(2.0, 100, 5,  1)
    b.add_passenger(2.5, 70, -4, 7)
    b.add_maint(3.0, 3, 3)    # elevator 3 -> F3
    b.add_passenger(3.5, 85, 2, -2)
    b.add_passenger(4.0, 60, 7, -1)
    return b.lines()


def all_elev_maint_plus_flood_case(sid: int) -> List[str]:
    """All 6 elevators under MAINT simultaneously with a flood of passengers.
    Maximum concurrency pressure: scheduler must reroute all passengers."""
    b = CaseBuilder(sid)
    # Send MAINT to all 6 elevators at the very start
    for eid, floor in enumerate(MAINT_TARGET_FLOORS[:4], start=1):
        b.add_maint(1.0, eid, floor)
    b.add_maint(1.0, 5, -2)
    b.add_maint(1.0, 6, -1)
    # Flood of passengers arriving right when all elevators are in maintenance
    rng = random.Random()
    ts = 1.0
    for _ in range(30):
        frm = rng.choice(FLOORS)
        to = rand_to_floor(rng, frm)
        b.add_passenger(ts, rng.randint(MIN_WEIGHT, MAX_WEIGHT), frm, to)
        ts = min(MAX_TS, round(ts + rng.choice([0.2, 0.3, 0.5]), 1))
        if len(b._rows) >= MAX_TOTAL_INSTRUCTIONS:
            break
    return b.lines()


def weight_overload_edge_case(sid: int) -> List[str]:
    """Near-overload scenario: passengers near 400kg capacity limit.
    Tests that the validator catches overload attempts."""
    b = CaseBuilder(sid)
    # 4 passengers, each 100kg, all requesting the same trip at the same time
    # The scheduler must refuse to load more than 4 at once (4*100=400kg, exactly at limit)
    ts = 1.0
    for _ in range(4):
        b.add_passenger(ts, 100, 1, 7)
    # 5th 100kg passenger: cannot board with the others (would be 500kg)
    b.add_passenger(1.0, 100, 1, 7)
    # Mix in some lighter passengers
    b.add_passenger(1.0, 50, -3, 4)
    b.add_passenger(1.0, 50, 2, 6)
    b.add_passenger(1.1, 75, -1, 5)
    b.add_passenger(1.1, 80, 3, -4)
    b.add_passenger(1.2, 60, 7, -2)
    return b.lines()


# Random case

def random_case(seed: Optional[int], n: int, sid: int) -> List[str]:
    b = CaseBuilder(sid)
    rng = random.Random(seed)
    ts = 1.0

    request_count = min(MAX_TOTAL_INSTRUCTIONS, n)
    # Decide how many MAINT requests (0 to min(6, request_count//3))
    max_maint = min(6, request_count // 3)
    num_maint = rng.randint(0, max_maint)
    num_passenger = request_count - num_maint

    # Decide which elevators get MAINT
    maint_elevators = rng.sample(range(ELEVATOR_MIN, ELEVATOR_MAX + 1), num_maint)

    # Generate mixed list: 'P' for passenger, ('M', eid) for MAINT
    actions: list = ['P'] * num_passenger + [('M', eid) for eid in maint_elevators]
    rng.shuffle(actions)

    for action in actions:
        if action == 'P':
            frm = rng.choice(FLOORS)
            to = rand_to_floor(rng, frm)
            wei = rng.randint(MIN_WEIGHT, MAX_WEIGHT)
            try:
                b.add_passenger(ts, wei, frm, to)
            except ValueError:
                break
        else:
            _, eid = action
            target = rng.choice(MAINT_TARGET_FLOORS)
            try:
                b.add_maint(ts, eid, target)
            except ValueError:
                # elevator already used or too many instructions
                pass
        ts = min(MAX_TS, round(ts + rng.choice([0.1, 0.2, 0.3, 0.4, 0.5]), 1))

    return b.lines()


# File IO

def write_case(out_dir: str, filename: str, lines: List[str]) -> None:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")


def _normalize_case_lines(raw_str: str) -> List[str]:
    return [line.strip() for line in raw_str.strip().splitlines() if line.strip()]


def _iter_custom_string_cases() -> List[Tuple[str, List[str]]]:
    if not isinstance(CUSTOM_STRING_CASES, list):
        raise TypeError("CUSTOM_STRING_CASES must be list[str]")

    result: List[Tuple[str, List[str]]] = []
    for idx, raw_str in enumerate(CUSTOM_STRING_CASES, start=1):
        if not isinstance(raw_str, str):
            raise TypeError("CUSTOM_STRING_CASES items must be str")
        filename = f"custom_auto_{idx:02d}.txt"
        result.append((filename, _normalize_case_lines(raw_str)))

    return result


def _has_one_decimal(ts_text: str) -> bool:
    if "." not in ts_text:
        return False
    frac = ts_text.split(".", 1)[1]
    return len(frac) == 1 and frac.isdigit()


def _validate_case_lines_for_mutual(lines: List[str]) -> List[str]:
    errors: List[str] = []
    if not lines:
        return ["empty case"]
    if len(lines) > MAX_TOTAL_INSTRUCTIONS:
        errors.append(f"instruction count {len(lines)} exceeds {MAX_TOTAL_INSTRUCTIONS}")

    all_ids: Set[int] = set()
    maint_elevators: Set[int] = set()
    first_ts: Optional[float] = None
    last_ts = -1.0

    for idx, line in enumerate(lines, start=1):
        passenger = RE_PASSENGER_LINE.match(line)
        maint = None if passenger else RE_MAINT_LINE.match(line)
        if passenger:
            ts_s, pid_s, wei_s, frm_s, to_s = passenger.groups()
            ts = float(ts_s)
            pid = int(pid_s)
            wei = int(wei_s)
            frm = floor_to_int(frm_s)
            to = floor_to_int(to_s)

            if frm is None or to is None:
                errors.append(f"line {idx}: invalid floor")
            elif frm == to:
                errors.append(f"line {idx}: FROM equals TO")

            if pid <= 0:
                errors.append(f"line {idx}: invalid passenger id")
            elif pid in all_ids:
                errors.append(f"line {idx}: duplicate id {pid}")
            else:
                all_ids.add(pid)

            if not (MIN_WEIGHT <= wei <= MAX_WEIGHT):
                errors.append(f"line {idx}: invalid weight {wei}")
        elif maint:
            ts_s, eid_s, wid_s, target_s = maint.groups()
            ts = float(ts_s)
            eid = int(eid_s)
            wid = int(wid_s)
            target = floor_to_int(target_s)

            if eid < ELEVATOR_MIN or eid > ELEVATOR_MAX:
                errors.append(f"line {idx}: invalid elevator id {eid}")
            elif eid in maint_elevators:
                errors.append(f"line {idx}: elevator {eid} has more than one MAINT")
            else:
                maint_elevators.add(eid)

            if wid <= 0:
                errors.append(f"line {idx}: invalid worker id")
            elif wid in all_ids:
                errors.append(f"line {idx}: duplicate id {wid}")
            else:
                all_ids.add(wid)

            if target not in MAINT_TARGET_FLOORS:
                errors.append(f"line {idx}: invalid MAINT target floor {target_s}")
        else:
            errors.append(f"line {idx}: malformed input")
            continue

        if not _has_one_decimal(ts_s):
            errors.append(f"line {idx}: timestamp must keep one decimal place")

        if first_ts is None:
            first_ts = ts
        if ts < last_ts:
            errors.append(f"line {idx}: timestamp decreases")
        last_ts = max(last_ts, ts)

    if first_ts is not None and first_ts < MIN_TS:
        errors.append(f"first timestamp {first_ts:.1f} < {MIN_TS:.1f}")
    if last_ts > MAX_TS:
        errors.append(f"last timestamp {last_ts:.1f} > {MAX_TS:.1f}")
    return errors


def generate_all(
    out_dir: str,
    random_count: int,
    base_seed: Optional[int] = None,
    strict_mutual: bool = False,
) -> List[str]:
    files: List[str] = []
    pid_cursor = 1000

    def maybe_write(filename: str, lines: List[str]) -> bool:
        if strict_mutual:
            errs = _validate_case_lines_for_mutual(lines)
            if errs:
                return False
        write_case(out_dir, filename, lines)
        files.append(filename)
        return True

    base_cases = [
        ("01_smoke.txt", smoke_case),
        ("02_same_timestamp.txt", same_timestamp_case),
        ("03_weight_boundary.txt", weight_boundary_case),
        ("04_maint_only.txt", maint_only_case),
        ("05_maint_with_passenger.txt", maint_with_passenger_case),
        ("06_multi_maint.txt", multi_maint_case),
        ("07_dense_passenger.txt", dense_passenger_case),
        ("08_maint_stress.txt", maint_stress_case),
        ("09_maint_interleave.txt", maint_interleave_case),
        ("10_all_elev_maint_flood.txt", all_elev_maint_plus_flood_case),
        ("11_weight_overload_edge.txt", weight_overload_edge_case),
    ]

    # Add custom string-based fixed cases first
    for filename, lines in _iter_custom_string_cases():
        maybe_write(filename, lines)

    # Add function-based fixed cases after custom string cases
    for filename, factory in base_cases:
        try:
            lines = factory(pid_cursor)
        except ValueError:
            lines = []
        if lines:
            maybe_write(filename, lines)
        pid_cursor += 500

    # Random cases: cycle through a wider variety of sizes for better coverage
    sizes = [15, 25, 35, 45, 55, 65, 70, 20, 40, 60]
    target_count = max(0, random_count)
    produced = 0
    attempts = 0
    max_attempts = max(20, target_count * 30)
    file_index = 12

    while produced < target_count and attempts < max_attempts:
        req_count = sizes[produced % len(sizes)]
        seed = (base_seed + attempts) if base_seed is not None else None
        lines = random_case(seed, req_count, pid_cursor)
        filename = f"{file_index:02d}_random_{req_count:02d}.txt"
        if maybe_write(filename, lines):
            produced += 1
            file_index += 1
            pid_cursor += 700
        attempts += 1

    return files


# CLI entry

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate HW6 testcases for consensus judge")
    parser.add_argument("--out", default="data", help="output directory")
    parser.add_argument("--count", type=int, default=8, help="number of extra random cases")
    parser.add_argument("--seed", type=int, default=None, help="optional base seed for reproducible random cases")
    parser.add_argument(
        "--strict-mutual",
        action="store_true",
        help="enforce mutual-test constraints and skip non-compliant fixed cases",
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
