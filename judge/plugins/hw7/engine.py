#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HW7 multi-target consensus judge.

Compared with earlier iterations, this validator adds support for:
- UPDATE / RECYCLE requests and outputs
- dual-car runtime constraints (main car + standby car)
- shaft-level state machine transitions for MAINT / UPDATE / RECYCLE

Public interfaces intentionally stay aligned with the existing GUI backend.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock, Thread
from typing import Dict, List, Optional, Set, Tuple

from judge.core.target_matching import direct_target_entry, matching_target_entries

EPSILON = 1e-9
NUM_SHAFTS = 6
NUM_ELEVATORS = 12
DEFAULT_MOVE_TIME = 0.4
TEST_MOVE_TIME = 0.2
DOOR_OPEN_CLOSE_TIME = 0.4
MAX_LOAD = 400
POLL_INTERVAL = 0.1
# Allow startup clock skew between runner feed time and target timestamp base.
INPUT_TIME_TOLERANCE = 0.15
# Delay feeding input timestamps slightly to align with target startup epoch.
INPUT_FEED_STARTUP_DELAY = 0.30

MAINT_STOP_TIME = 1.0
MAINT_COMPLETE_TIMEOUT = 7.0
UPDATE_STOP_TIME = 1.0
UPDATE_COMPLETE_TIMEOUT = 6.0
RECYCLE_STOP_TIME = 1.0
RECYCLE_COMPLETE_TIMEOUT = 6.0

POWER_OPEN = 0.1
POWER_CLOSE = 0.1
POWER_MOVE = 0.4

MAIN_FLOOR_MIN = -4
MAIN_FLOOR_MAX = 7
DOUBLE_MAIN_MIN = 2
DOUBLE_MAIN_MAX = 7
DOUBLE_BACKUP_MIN = -4
DOUBLE_BACKUP_MAX = 2

MAINT_TARGET_FLOORS = {-2, -1, 2, 3}  # B2, B1, F2, F3

FLOOR_MAP_STR_TO_INT = {
    "B4": -4,
    "B3": -3,
    "B2": -2,
    "B1": -1,
    "F1": 1,
    "F2": 2,
    "F3": 3,
    "F4": 4,
    "F5": 5,
    "F6": 6,
    "F7": 7,
}
FLOOR_MAP_INT_TO_STR = {v: k for k, v in FLOOR_MAP_STR_TO_INT.items()}

RE_INPUT_PASSENGER = re.compile(
    r"^\[\s*([\d.]+)\s*\](\d+)-WEI-(\d+)-FROM-([BF]\d+)-TO-([BF]\d+)$"
)
RE_INPUT_MAINT = re.compile(
    r"^\[\s*([\d.]+)\s*\]MAINT-(\d+)-(\d+)-([BF]\d+)$"
)
RE_INPUT_UPDATE = re.compile(
    r"^\[\s*([\d.]+)\s*\]UPDATE-(\d+)$"
)
RE_INPUT_RECYCLE = re.compile(
    r"^\[\s*([\d.]+)\s*\]RECYCLE-(\d+)$"
)

RE_TIMESTAMP = re.compile(r"^\[\s*([\d.]+)\s*\]")
RE_RECEIVE = re.compile(r"^\[\s*([\d.]+)\s*\]RECEIVE-(\d+)-(\d+)$")
RE_ARRIVE = re.compile(r"^\[\s*([\d.]+)\s*\]ARRIVE-([BF]\d+)-(\d+)$")
RE_OPEN = re.compile(r"^\[\s*([\d.]+)\s*\]OPEN-([BF]\d+)-(\d+)$")
RE_CLOSE = re.compile(r"^\[\s*([\d.]+)\s*\]CLOSE-([BF]\d+)-(\d+)$")
RE_IN = re.compile(r"^\[\s*([\d.]+)\s*\]IN-(\d+)-([BF]\d+)-(\d+)$")
RE_OUT = re.compile(r"^\[\s*([\d.]+)\s*\]OUT-([SF])-(\d+)-([BF]\d+)-(\d+)$")

RE_MAINT_ACCEPT = re.compile(
    r"^\[\s*([\d.]+)\s*\]MAINT-ACCEPT-(\d+)-(\d+)-([BF]\d+)$"
)
RE_MAINT1_BEGIN = re.compile(r"^\[\s*([\d.]+)\s*\]MAINT1-BEGIN-(\d+)$")
RE_MAINT2_BEGIN = re.compile(r"^\[\s*([\d.]+)\s*\]MAINT2-BEGIN-(\d+)$")
RE_MAINT_END = re.compile(r"^\[\s*([\d.]+)\s*\]MAINT-END-(\d+)$")

RE_UPDATE_ACCEPT = re.compile(r"^\[\s*([\d.]+)\s*\]UPDATE-ACCEPT-(\d+)$")
RE_UPDATE_BEGIN = re.compile(r"^\[\s*([\d.]+)\s*\]UPDATE-BEGIN-(\d+)$")
RE_UPDATE_END = re.compile(r"^\[\s*([\d.]+)\s*\]UPDATE-END-(\d+)$")

RE_RECYCLE_ACCEPT = re.compile(r"^\[\s*([\d.]+)\s*\]RECYCLE-ACCEPT-(\d+)$")
RE_RECYCLE_BEGIN = re.compile(r"^\[\s*([\d.]+)\s*\]RECYCLE-BEGIN-(\d+)$")
RE_RECYCLE_END = re.compile(r"^\[\s*([\d.]+)\s*\]RECYCLE-END-(\d+)$")

RE_MAIN_METHOD = re.compile(r"\bpublic\s+static\s+void\s+main\s*\(")


@dataclass
class PassengerRequest:
    request_time: float
    pid: int
    weight: int
    from_floor: int
    to_floor: int


@dataclass
class MaintRequestInput:
    request_time: float
    elevator_id: int  # main car id: 1..6
    worker_id: int
    target_floor: int


@dataclass
class UpdateRequestInput:
    request_time: float
    main_eid: int


@dataclass
class RecycleRequestInput:
    request_time: float
    backup_eid: int


@dataclass
class ControlRequests:
    maints_by_worker: Dict[int, MaintRequestInput] = field(default_factory=dict)
    maints_by_shaft: Dict[int, List[MaintRequestInput]] = field(default_factory=dict)
    updates_by_shaft: Dict[int, List[UpdateRequestInput]] = field(default_factory=dict)
    recycles_by_shaft: Dict[int, List[RecycleRequestInput]] = field(default_factory=dict)


@dataclass
class PassengerState:
    pid: int
    weight: int
    destination: int
    request_time: float
    state: str = "OUTSIDE"  # OUTSIDE / INSIDE / ARRIVED
    location: int = 0
    current_receive_eid: Optional[int] = None
    arrival_time: Optional[float] = None


@dataclass
class WorkerState:
    worker_id: int
    shaft_id: int
    main_eid: int
    state: str = "OUTSIDE"  # OUTSIDE / INSIDE / OUT
    location: int = 1


@dataclass
class CarState:
    cid: int
    shaft_id: int
    is_main: bool
    active: bool
    darkroom: bool
    floor: int = 1
    door_open: bool = False
    open_time: float = -1.0
    last_action_time: float = 0.0
    last_arrive_time: float = 0.0
    min_floor: int = MAIN_FLOOR_MIN
    max_floor: int = MAIN_FLOOR_MAX
    active_receives: Set[int] = field(default_factory=set)
    passengers: Set[int] = field(default_factory=set)
    passenger_weights: Dict[int, int] = field(default_factory=dict)


@dataclass
class ShaftRuntime:
    sid: int
    main_id: int
    backup_id: int
    mode: str = "NORMAL"

    maint_queue: List[MaintRequestInput] = field(default_factory=list)
    update_queue: List[UpdateRequestInput] = field(default_factory=list)
    recycle_queue: List[RecycleRequestInput] = field(default_factory=list)

    active_maint: Optional[MaintRequestInput] = None
    active_update: Optional[UpdateRequestInput] = None
    active_recycle: Optional[RecycleRequestInput] = None

    maint_accept_time: float = -1.0
    maint1_begin_time: float = -1.0
    maint2_begin_time: float = -1.0

    update_accept_time: float = -1.0
    update_begin_time: float = -1.0

    recycle_accept_time: float = -1.0
    recycle_begin_time: float = -1.0

    worker_id: Optional[int] = None
    worker_locked_after_in: bool = False

    test_route: List[int] = field(default_factory=list)
    test_open_done: bool = False
    worker_out_during_test: bool = False


@dataclass
class TargetProject:
    key: str
    display_name: str
    project_dir: Path
    source_dir: Path
    main_class: str
    build_dir: Path
    command: List[str]


@dataclass
class TargetRunResult:
    status: str
    stdout: str
    stderr: str
    elapsed_sec: float
    sim_time: float
    power: float
    avg_time: float
    errors: List[str]
    normalized_events: List[str]
    raw_output_path: str


@dataclass
class CaseSummary:
    case_name: str
    all_correct: bool
    all_consistent: bool
    effective: bool
    targets: Dict[str, TargetRunResult]


def floor_to_int(floor_str: str) -> Optional[int]:
    return FLOOR_MAP_STR_TO_INT.get(floor_str)


def int_to_floor(floor_int: int) -> str:
    return FLOOR_MAP_INT_TO_STR.get(floor_int, f"InvalidFloor({floor_int})")


def is_valid_step(prev_floor: int, next_floor: int) -> bool:
    if prev_floor == -1 and next_floor == 1:
        return True
    if prev_floor == 1 and next_floor == -1:
        return True
    return abs(next_floor - prev_floor) == 1


def build_route(start: int, end: int) -> List[int]:
    route: List[int] = []
    current = start
    if start == end:
        return route
    direction = 1 if end > start else -1
    while current != end:
        nxt = current + direction
        if nxt == 0:
            nxt += direction
        route.append(nxt)
        current = nxt
    return route


def shaft_id_from_car(cid: int) -> Optional[int]:
    if 1 <= cid <= 6:
        return cid
    if 7 <= cid <= 12:
        return cid - 6
    return None


class Validator:
    """Full HW7 output validator."""

    def __init__(self, passenger_requests: Dict[int, PassengerRequest], controls: ControlRequests) -> None:
        self.errors: List[str] = []
        self.last_timestamp = 0.0

        self.arrive_count = 0
        self.open_count = 0
        self.close_count = 0

        self.p_requests = passenger_requests
        self.controls = controls

        self.passengers: Dict[int, PassengerState] = {}
        for req in passenger_requests.values():
            self.passengers[req.pid] = PassengerState(
                pid=req.pid,
                weight=req.weight,
                destination=req.to_floor,
                request_time=req.request_time,
                location=req.from_floor,
            )

        self.workers: Dict[int, WorkerState] = {}
        for worker_id, req in controls.maints_by_worker.items():
            sid = req.elevator_id
            self.workers[worker_id] = WorkerState(
                worker_id=worker_id,
                shaft_id=sid,
                main_eid=req.elevator_id,
            )

        self.cars: Dict[int, CarState] = {}
        self.shafts: Dict[int, ShaftRuntime] = {}
        for sid in range(1, NUM_SHAFTS + 1):
            main_id = sid
            backup_id = sid + 6

            self.cars[main_id] = CarState(
                cid=main_id,
                shaft_id=sid,
                is_main=True,
                active=True,
                darkroom=False,
                floor=1,
                min_floor=MAIN_FLOOR_MIN,
                max_floor=MAIN_FLOOR_MAX,
            )
            self.cars[backup_id] = CarState(
                cid=backup_id,
                shaft_id=sid,
                is_main=False,
                active=False,
                darkroom=True,
                floor=1,
                min_floor=MAIN_FLOOR_MIN,
                max_floor=MAIN_FLOOR_MAX,
            )

            self.shafts[sid] = ShaftRuntime(
                sid=sid,
                main_id=main_id,
                backup_id=backup_id,
                maint_queue=list(controls.maints_by_shaft.get(sid, [])),
                update_queue=list(controls.updates_by_shaft.get(sid, [])),
                recycle_queue=list(controls.recycles_by_shaft.get(sid, [])),
            )

    def add_error(self, message: str) -> None:
        self.errors.append(f"[t~{self.last_timestamp:.4f}] {message}")

    def _advance_time(self, t: float) -> None:
        if t < self.last_timestamp - EPSILON:
            self.add_error(f"Timestamp decreases: {t:.4f} < {self.last_timestamp:.4f}")
        self.last_timestamp = max(self.last_timestamp, t)

    def _parse_time(self, line: str) -> Optional[float]:
        m = RE_TIMESTAMP.match(line)
        if not m:
            self.add_error(f"Malformed output line: {line}")
            return None
        try:
            return float(m.group(1))
        except ValueError:
            self.add_error(f"Invalid timestamp value: {line}")
            return None

    def _get_car(self, cid: int) -> Optional[CarState]:
        c = self.cars.get(cid)
        if c is None:
            self.add_error(f"Invalid elevator id {cid}")
        return c

    def _get_shaft_by_car(self, cid: int) -> Optional[ShaftRuntime]:
        sid = shaft_id_from_car(cid)
        if sid is None:
            self.add_error(f"Invalid car id {cid}")
            return None
        shaft = self.shafts.get(sid)
        if shaft is None:
            self.add_error(f"Invalid shaft for car {cid}")
        return shaft

    def _get_passenger(self, pid: int) -> Optional[PassengerState]:
        p = self.passengers.get(pid)
        if p is None:
            self.add_error(f"Unknown passenger id {pid}")
        return p

    def _get_worker(self, worker_id: int) -> Optional[WorkerState]:
        w = self.workers.get(worker_id)
        if w is None:
            self.add_error(f"Unknown maintenance worker id {worker_id}")
        return w

    def _clear_car_receives(self, cid: int) -> None:
        car = self.cars.get(cid)
        if car is None:
            return
        for pid in list(car.active_receives):
            p = self.passengers.get(pid)
            if p is not None and p.current_receive_eid == cid:
                p.current_receive_eid = None
        car.active_receives.clear()

    def _car_load(self, cid: int) -> int:
        car = self.cars[cid]
        total = 0
        for pid in car.passengers:
            total += car.passenger_weights.get(pid, 0)
        return total

    def _is_car_silent(self, car: CarState, shaft: ShaftRuntime) -> bool:
        if shaft.mode == "UPDATE":
            return True
        if car.is_main and shaft.mode == "REPAIR":
            return True
        if (not car.is_main) and shaft.mode == "RECYCLE":
            return True
        return False

    def _can_receive(self, car: CarState, shaft: ShaftRuntime) -> Tuple[bool, str]:
        if not car.active or car.darkroom:
            return False, "car not active (darkroom)"

        if shaft.mode == "UPDATE":
            return False, "UPDATE state forbids RECEIVE"

        if car.is_main and shaft.mode in {"REPAIR", "TEST"}:
            return False, f"{shaft.mode} state forbids RECEIVE"

        if (not car.is_main) and shaft.mode == "RECYCLE":
            return False, "RECYCLE state forbids backup RECEIVE"

        return True, ""

    def _move_special_allowed(self, car: CarState, shaft: ShaftRuntime, next_floor: int) -> bool:
        if shaft.mode in {"DOUBLE", "REC_ACCEPT", "RECYCLE"}:
            if car.floor == 2 and is_valid_step(car.floor, next_floor):
                return True

        if car.is_main:
            if shaft.mode in {"REP_ACCEPT", "UP_ACCEPT", "TEST"}:
                return True
        else:
            if shaft.mode == "REC_ACCEPT":
                return True

        return False

    def _check_rep_locked(self, car: CarState, shaft: ShaftRuntime, action: str) -> None:
        # RECEIVE is valid until explicit BEGIN markers are emitted.
        if action == "RECEIVE":
            return
        if car.is_main and shaft.mode == "REP_ACCEPT" and shaft.worker_locked_after_in:
            if action not in {"CLOSE", "MAINT1-BEGIN"}:
                self.add_error(
                    f"{action}-{car.cid}: forbidden after worker IN before MAINT1-BEGIN"
                )

    def _check_double_safety(self, sid: int) -> None:
        shaft = self.shafts[sid]
        if shaft.mode not in {"DOUBLE", "REC_ACCEPT", "RECYCLE"}:
            return
        main = self.cars[shaft.main_id]
        backup = self.cars[shaft.backup_id]
        if not main.active or not backup.active:
            return

        if main.floor == backup.floor:
            self.add_error(
                f"shaft {sid} collision risk: main and backup both at {int_to_floor(main.floor)}"
            )

        if backup.floor > main.floor:
            self.add_error(
                f"shaft {sid} order violation: backup {int_to_floor(backup.floor)} above main {int_to_floor(main.floor)}"
            )

    def validate_line(self, line: str) -> None:
        text = line.strip()
        if not text or "[LOG]" in text:
            return

        t = self._parse_time(text)
        if t is None:
            return
        self._advance_time(t)

        m = RE_RECEIVE.match(text)
        if m:
            self._handle_receive(t, int(m.group(2)), int(m.group(3)))
            return

        m = RE_ARRIVE.match(text)
        if m:
            self._handle_arrive(t, m.group(2), int(m.group(3)))
            return

        m = RE_OPEN.match(text)
        if m:
            self._handle_open(t, m.group(2), int(m.group(3)))
            return

        m = RE_CLOSE.match(text)
        if m:
            self._handle_close(t, m.group(2), int(m.group(3)))
            return

        m = RE_IN.match(text)
        if m:
            self._handle_in(t, int(m.group(2)), m.group(3), int(m.group(4)))
            return

        m = RE_OUT.match(text)
        if m:
            self._handle_out(t, m.group(2), int(m.group(3)), m.group(4), int(m.group(5)))
            return

        m = RE_MAINT_ACCEPT.match(text)
        if m:
            self._handle_maint_accept(t, int(m.group(2)), int(m.group(3)), m.group(4))
            return

        m = RE_MAINT1_BEGIN.match(text)
        if m:
            self._handle_maint1_begin(t, int(m.group(2)))
            return

        m = RE_MAINT2_BEGIN.match(text)
        if m:
            self._handle_maint2_begin(t, int(m.group(2)))
            return

        m = RE_MAINT_END.match(text)
        if m:
            self._handle_maint_end(t, int(m.group(2)))
            return

        m = RE_UPDATE_ACCEPT.match(text)
        if m:
            self._handle_update_accept(t, int(m.group(2)))
            return

        m = RE_UPDATE_BEGIN.match(text)
        if m:
            self._handle_update_begin(t, int(m.group(2)))
            return

        m = RE_UPDATE_END.match(text)
        if m:
            self._handle_update_end(t, int(m.group(2)))
            return

        m = RE_RECYCLE_ACCEPT.match(text)
        if m:
            self._handle_recycle_accept(t, int(m.group(2)))
            return

        m = RE_RECYCLE_BEGIN.match(text)
        if m:
            self._handle_recycle_begin(t, int(m.group(2)))
            return

        m = RE_RECYCLE_END.match(text)
        if m:
            self._handle_recycle_end(t, int(m.group(2)))
            return

        self.add_error(f"Unrecognized output format: {text}")

    def _handle_receive(self, t: float, pid: int, eid: int) -> None:
        p = self._get_passenger(pid)
        car = self._get_car(eid)
        shaft = self._get_shaft_by_car(eid)
        if p is None or car is None or shaft is None:
            return

        self._check_rep_locked(car, shaft, "RECEIVE")

        ok, reason = self._can_receive(car, shaft)
        if not ok:
            self.add_error(f"RECEIVE-{pid}-{eid}: {reason}")

        if p.state == "ARRIVED":
            self.add_error(f"RECEIVE-{pid}-{eid}: passenger already ARRIVED")
        if t + INPUT_TIME_TOLERANCE < p.request_time:
            self.add_error(
                f"RECEIVE-{pid}-{eid}: output earlier than request time {p.request_time:.1f}"
            )
        if p.state != "OUTSIDE":
            self.add_error(f"RECEIVE-{pid}-{eid}: passenger state={p.state}, not OUTSIDE")
        if p.current_receive_eid is not None:
            self.add_error(
                f"RECEIVE-{pid}-{eid}: previous RECEIVE not ended on car {p.current_receive_eid}"
            )

        p.current_receive_eid = eid
        car.active_receives.add(pid)

    def _handle_arrive(self, t: float, floor_s: str, eid: int) -> None:
        floor_i = floor_to_int(floor_s)
        car = self._get_car(eid)
        shaft = self._get_shaft_by_car(eid)
        if floor_i is None or car is None or shaft is None:
            self.add_error(f"ARRIVE-{floor_s}-{eid}: invalid floor/elevator")
            return

        if not car.active or car.darkroom:
            self.add_error(f"ARRIVE-{floor_s}-{eid}: inactive/darkroom elevator cannot move")

        self._check_rep_locked(car, shaft, "ARRIVE")

        if self._is_car_silent(car, shaft):
            self.add_error(f"ARRIVE-{floor_s}-{eid}: movement forbidden during {shaft.mode}")

        if car.door_open:
            self.add_error(f"ARRIVE-{floor_s}-{eid}: move while door OPEN")

        if floor_i < car.min_floor or floor_i > car.max_floor:
            self.add_error(
                f"ARRIVE-{floor_s}-{eid}: outside range [{int_to_floor(car.min_floor)}-{int_to_floor(car.max_floor)}]"
            )

        if not is_valid_step(car.floor, floor_i):
            self.add_error(f"ARRIVE-{floor_s}-{eid}: invalid step from {int_to_floor(car.floor)}")

        move_time = TEST_MOVE_TIME if (car.is_main and shaft.mode == "TEST") else DEFAULT_MOVE_TIME
        min_time = car.last_action_time + move_time
        if t < min_time - EPSILON:
            self.add_error(
                f"ARRIVE-{floor_s}-{eid}: move too fast ({t:.4f} < {min_time:.4f})"
            )

        allow_move = bool(car.active_receives) or self._move_special_allowed(car, shaft, floor_i)
        if not allow_move:
            self.add_error(
                f"ARRIVE-{floor_s}-{eid}: move without RECEIVE/special-request permission"
            )

        car.floor = floor_i
        car.last_action_time = t
        car.last_arrive_time = t
        self.arrive_count += 1

        if car.is_main and shaft.mode == "TEST":
            shaft.test_route.append(floor_i)

        self._check_double_safety(car.shaft_id)

    def _handle_open(self, t: float, floor_s: str, eid: int) -> None:
        floor_i = floor_to_int(floor_s)
        car = self._get_car(eid)
        shaft = self._get_shaft_by_car(eid)
        if floor_i is None or car is None or shaft is None:
            self.add_error(f"OPEN-{floor_s}-{eid}: invalid floor/elevator")
            return

        if not car.active or car.darkroom:
            self.add_error(f"OPEN-{floor_s}-{eid}: inactive/darkroom elevator cannot OPEN")

        self._check_rep_locked(car, shaft, "OPEN")

        if self._is_car_silent(car, shaft):
            self.add_error(f"OPEN-{floor_s}-{eid}: OPEN forbidden during {shaft.mode}")

        if car.door_open:
            self.add_error(f"OPEN-{floor_s}-{eid}: repeated OPEN")
        if car.floor != floor_i:
            self.add_error(f"OPEN-{floor_s}-{eid}: elevator at {int_to_floor(car.floor)}")

        if car.is_main and shaft.mode == "TEST":
            if floor_i != 1:
                self.add_error(f"OPEN-{floor_s}-{eid}: TEST can OPEN only at F1")
            if shaft.test_open_done:
                self.add_error(f"OPEN-{floor_s}-{eid}: TEST must OPEN only once")
            shaft.test_open_done = True

        car.door_open = True
        car.open_time = t
        car.last_action_time = t
        self.open_count += 1

    def _handle_close(self, t: float, floor_s: str, eid: int) -> None:
        floor_i = floor_to_int(floor_s)
        car = self._get_car(eid)
        shaft = self._get_shaft_by_car(eid)
        if floor_i is None or car is None or shaft is None:
            self.add_error(f"CLOSE-{floor_s}-{eid}: invalid floor/elevator")
            return

        if not car.active or car.darkroom:
            self.add_error(f"CLOSE-{floor_s}-{eid}: inactive/darkroom elevator cannot CLOSE")

        if self._is_car_silent(car, shaft):
            self.add_error(f"CLOSE-{floor_s}-{eid}: CLOSE forbidden during {shaft.mode}")

        if not car.door_open:
            self.add_error(f"CLOSE-{floor_s}-{eid}: CLOSE while door CLOSED")
        if car.floor != floor_i:
            self.add_error(f"CLOSE-{floor_s}-{eid}: elevator at {int_to_floor(car.floor)}")

        if car.open_time >= 0:
            min_close = car.open_time + DOOR_OPEN_CLOSE_TIME
            if t < min_close - EPSILON:
                self.add_error(
                    f"CLOSE-{floor_s}-{eid}: door open duration too short ({t:.4f} < {min_close:.4f})"
                )

        load = self._car_load(eid)
        if load > MAX_LOAD:
            self.add_error(f"CLOSE-{floor_s}-{eid}: overload {load}kg > {MAX_LOAD}kg")

        if car.is_main and shaft.mode == "TEST" and not shaft.worker_out_during_test:
            self.add_error(f"CLOSE-{floor_s}-{eid}: TEST close requires worker OUT during this open")

        car.door_open = False
        car.open_time = -1.0
        car.last_action_time = t
        self.close_count += 1

    def _handle_in(self, t: float, pid: int, floor_s: str, eid: int) -> None:
        floor_i = floor_to_int(floor_s)
        car = self._get_car(eid)
        shaft = self._get_shaft_by_car(eid)
        if floor_i is None or car is None or shaft is None:
            self.add_error(f"IN-{pid}-{floor_s}-{eid}: invalid floor/elevator")
            return

        worker = self.workers.get(pid)
        if worker is not None:
            self._handle_worker_in(t, worker, floor_i, floor_s, car, shaft)
            return

        p = self._get_passenger(pid)
        if p is None:
            return

        self._check_rep_locked(car, shaft, "IN")

        if self._is_car_silent(car, shaft):
            self.add_error(f"IN-{pid}-{floor_s}-{eid}: IN forbidden during {shaft.mode}")

        if car.is_main and shaft.mode == "TEST":
            self.add_error(f"IN-{pid}-{floor_s}-{eid}: passenger cannot IN during TEST")

        if not car.active or car.darkroom:
            self.add_error(f"IN-{pid}-{floor_s}-{eid}: inactive/darkroom car")

        if not car.door_open:
            self.add_error(f"IN-{pid}-{floor_s}-{eid}: door not OPEN")
        if car.floor != floor_i:
            self.add_error(f"IN-{pid}-{floor_s}-{eid}: elevator not at floor")

        if p.state != "OUTSIDE":
            self.add_error(f"IN-{pid}-{floor_s}-{eid}: passenger state={p.state}, not OUTSIDE")
        if p.location != floor_i:
            self.add_error(f"IN-{pid}-{floor_s}-{eid}: passenger at {int_to_floor(p.location)}")

        if p.current_receive_eid != eid or pid not in car.active_receives:
            self.add_error(f"IN-{pid}-{floor_s}-{eid}: missing active RECEIVE")

        car.passengers.add(pid)
        car.passenger_weights[pid] = p.weight
        p.state = "INSIDE"
        p.location = eid

    def _handle_worker_in(
        self,
        t: float,
        worker: WorkerState,
        floor_i: int,
        floor_s: str,
        car: CarState,
        shaft: ShaftRuntime,
    ) -> None:
        if car.cid != worker.main_eid:
            self.add_error(
                f"IN-{worker.worker_id}-{floor_s}-{car.cid}: worker must enter car {worker.main_eid}"
            )

        if not car.is_main:
            self.add_error(
                f"IN-{worker.worker_id}-{floor_s}-{car.cid}: worker cannot enter backup car"
            )

        if shaft.mode != "REP_ACCEPT":
            self.add_error(
                f"IN-{worker.worker_id}-{floor_s}-{car.cid}: worker IN only allowed in REP_ACCEPT"
            )

        if floor_i != 1:
            self.add_error(
                f"IN-{worker.worker_id}-{floor_s}-{car.cid}: worker must enter at F1"
            )

        if worker.state != "OUTSIDE":
            self.add_error(
                f"IN-{worker.worker_id}-{floor_s}-{car.cid}: worker state={worker.state}"
            )

        if not car.door_open:
            self.add_error(
                f"IN-{worker.worker_id}-{floor_s}-{car.cid}: door not OPEN"
            )
        if car.floor != floor_i:
            self.add_error(
                f"IN-{worker.worker_id}-{floor_s}-{car.cid}: elevator not at floor"
            )

        regular_inside = [pid for pid in car.passengers if pid not in self.workers]
        if regular_inside:
            self.add_error(
                f"IN-{worker.worker_id}-{floor_s}-{car.cid}: regular passengers still inside {regular_inside}"
            )

        if shaft.active_maint and shaft.active_maint.worker_id != worker.worker_id:
            self.add_error(
                f"IN-{worker.worker_id}-{floor_s}-{car.cid}: worker id mismatch with MAINT request"
            )

        worker.state = "INSIDE"
        worker.location = car.cid
        shaft.worker_locked_after_in = True
        shaft.worker_id = worker.worker_id

    def _handle_out(self, t: float, out_flag: str, pid: int, floor_s: str, eid: int) -> None:
        floor_i = floor_to_int(floor_s)
        car = self._get_car(eid)
        shaft = self._get_shaft_by_car(eid)
        if floor_i is None or car is None or shaft is None:
            self.add_error(f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: invalid floor/elevator")
            return

        worker = self.workers.get(pid)
        if worker is not None:
            self._handle_worker_out(t, out_flag, worker, floor_i, floor_s, car, shaft)
            return

        p = self._get_passenger(pid)
        if p is None:
            return

        self._check_rep_locked(car, shaft, "OUT")

        if self._is_car_silent(car, shaft):
            self.add_error(f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: OUT forbidden during {shaft.mode}")

        if car.is_main and shaft.mode == "TEST":
            self.add_error(f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: passenger cannot OUT during TEST")

        if not car.active or car.darkroom:
            self.add_error(f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: inactive/darkroom car")

        if not car.door_open:
            self.add_error(f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: door not OPEN")
        if car.floor != floor_i:
            self.add_error(f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: elevator not at floor")

        if p.state != "INSIDE":
            self.add_error(f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: passenger state={p.state}, not INSIDE")
        if p.location != eid:
            self.add_error(f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: passenger not in car {eid}")
        if pid not in car.passengers:
            self.add_error(f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: passenger missing in car set")

        if pid in car.passengers:
            car.passengers.remove(pid)
        car.passenger_weights.pop(pid, None)

        if p.current_receive_eid != eid or pid not in car.active_receives:
            self.add_error(f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: RECEIVE not active on this car")
        p.current_receive_eid = None
        car.active_receives.discard(pid)

        on_target = floor_i == p.destination
        if out_flag == "S" and not on_target:
            self.add_error(
                f"OUT-S-{pid}-{floor_s}-{eid}: not destination {int_to_floor(p.destination)}"
            )
        if out_flag == "F" and on_target:
            self.add_error(f"OUT-F-{pid}-{floor_s}-{eid}: already at destination")

        if on_target:
            p.state = "ARRIVED"
            p.location = floor_i
            p.arrival_time = t
        else:
            p.state = "OUTSIDE"
            p.location = floor_i

    def _handle_worker_out(
        self,
        t: float,
        out_flag: str,
        worker: WorkerState,
        floor_i: int,
        floor_s: str,
        car: CarState,
        shaft: ShaftRuntime,
    ) -> None:
        if not car.is_main or car.cid != worker.main_eid:
            self.add_error(
                f"OUT-{out_flag}-{worker.worker_id}-{floor_s}-{car.cid}: worker on wrong car"
            )

        if shaft.mode != "TEST":
            self.add_error(
                f"OUT-{out_flag}-{worker.worker_id}-{floor_s}-{car.cid}: worker OUT only allowed in TEST"
            )

        if floor_i != 1:
            self.add_error(
                f"OUT-{out_flag}-{worker.worker_id}-{floor_s}-{car.cid}: worker must OUT at F1"
            )

        if out_flag != "S":
            self.add_error(
                f"OUT-{out_flag}-{worker.worker_id}-{floor_s}-{car.cid}: worker should use OUT-S"
            )

        if not car.door_open:
            self.add_error(
                f"OUT-{out_flag}-{worker.worker_id}-{floor_s}-{car.cid}: door not OPEN"
            )

        if worker.state != "INSIDE":
            self.add_error(
                f"OUT-{out_flag}-{worker.worker_id}-{floor_s}-{car.cid}: worker state={worker.state}"
            )

        worker.state = "OUT"
        worker.location = 1
        shaft.worker_out_during_test = True

    def _handle_maint_accept(self, t: float, eid: int, worker_id: int, target_floor_s: str) -> None:
        target_floor_i = floor_to_int(target_floor_s)
        if target_floor_i is None:
            self.add_error(f"MAINT-ACCEPT-{eid}-{worker_id}: invalid target floor {target_floor_s}")
            return

        if eid < 1 or eid > 6:
            self.add_error(f"MAINT-ACCEPT-{eid}-{worker_id}: MAINT elevator id must be 1..6")

        shaft = self.shafts.get(eid)
        if shaft is None:
            self.add_error(f"MAINT-ACCEPT-{eid}-{worker_id}: invalid shaft")
            return

        if shaft.mode != "NORMAL":
            self.add_error(
                f"MAINT-ACCEPT-{eid}-{worker_id}: shaft not in NORMAL (current {shaft.mode})"
            )

        req = shaft.maint_queue.pop(0) if shaft.maint_queue else None
        if req is None:
            self.add_error(f"MAINT-ACCEPT-{eid}-{worker_id}: no pending MAINT input")
        else:
            if t + INPUT_TIME_TOLERANCE < req.request_time:
                self.add_error(
                    f"MAINT-ACCEPT-{eid}-{worker_id}: output before input time {req.request_time:.1f}"
                )
            if req.elevator_id != eid or req.worker_id != worker_id or req.target_floor != target_floor_i:
                self.add_error(
                    f"MAINT-ACCEPT-{eid}-{worker_id}: mismatch with input MAINT request"
                )

        shaft.active_maint = req
        shaft.mode = "REP_ACCEPT"
        shaft.maint_accept_time = t
        shaft.worker_id = worker_id
        shaft.worker_locked_after_in = False
        shaft.test_route = []
        shaft.test_open_done = False
        shaft.worker_out_during_test = False

    def _handle_maint1_begin(self, t: float, eid: int) -> None:
        if eid < 1 or eid > 6:
            self.add_error(f"MAINT1-BEGIN-{eid}: invalid main elevator id")
            return

        shaft = self.shafts[eid]
        main = self.cars[eid]

        self._check_rep_locked(main, shaft, "MAINT1-BEGIN")

        if shaft.mode != "REP_ACCEPT":
            self.add_error(f"MAINT1-BEGIN-{eid}: shaft not in REP_ACCEPT")

        if main.door_open:
            self.add_error(f"MAINT1-BEGIN-{eid}: door must be CLOSED")
        if main.floor != 1:
            self.add_error(f"MAINT1-BEGIN-{eid}: main must be at F1")

        regular_inside = [pid for pid in main.passengers if pid not in self.workers]
        if regular_inside:
            self.add_error(f"MAINT1-BEGIN-{eid}: regular passengers still inside {regular_inside}")

        worker_id = shaft.worker_id
        if worker_id is None:
            self.add_error(f"MAINT1-BEGIN-{eid}: no worker id bound")
        else:
            worker = self.workers.get(worker_id)
            if worker is None or worker.state != "INSIDE" or worker.location != eid:
                self.add_error(f"MAINT1-BEGIN-{eid}: worker not INSIDE main car")

        self._clear_car_receives(eid)

        shaft.mode = "REPAIR"
        shaft.maint1_begin_time = t
        shaft.worker_locked_after_in = False

    def _handle_maint2_begin(self, t: float, eid: int) -> None:
        if eid < 1 or eid > 6:
            self.add_error(f"MAINT2-BEGIN-{eid}: invalid main elevator id")
            return

        shaft = self.shafts[eid]
        main = self.cars[eid]

        if shaft.mode != "REPAIR":
            self.add_error(f"MAINT2-BEGIN-{eid}: shaft not in REPAIR")

        if shaft.maint1_begin_time < 0:
            self.add_error(f"MAINT2-BEGIN-{eid}: MAINT1-BEGIN missing")
        elif t < shaft.maint1_begin_time + MAINT_STOP_TIME - EPSILON:
            self.add_error(
                f"MAINT2-BEGIN-{eid}: repair too short ({t:.4f} < {shaft.maint1_begin_time + MAINT_STOP_TIME:.4f})"
            )

        if main.door_open:
            self.add_error(f"MAINT2-BEGIN-{eid}: door must be CLOSED")
        if main.floor != 1:
            self.add_error(f"MAINT2-BEGIN-{eid}: main must start TEST at F1")

        shaft.mode = "TEST"
        shaft.maint2_begin_time = t
        shaft.test_route = []
        shaft.test_open_done = False
        shaft.worker_out_during_test = False

    def _handle_maint_end(self, t: float, eid: int) -> None:
        if eid < 1 or eid > 6:
            self.add_error(f"MAINT-END-{eid}: invalid main elevator id")
            return

        shaft = self.shafts[eid]
        main = self.cars[eid]

        if shaft.mode != "TEST":
            self.add_error(f"MAINT-END-{eid}: shaft not in TEST")

        if main.door_open:
            self.add_error(f"MAINT-END-{eid}: door must be CLOSED")
        if main.floor != 1:
            self.add_error(f"MAINT-END-{eid}: main must be at F1")

        regular_inside = [pid for pid in main.passengers if pid not in self.workers]
        if regular_inside:
            self.add_error(f"MAINT-END-{eid}: regular passengers still inside {regular_inside}")

        if not shaft.test_open_done:
            self.add_error(f"MAINT-END-{eid}: TEST phase missed OPEN-F1")
        if not shaft.worker_out_during_test:
            self.add_error(f"MAINT-END-{eid}: worker did not OUT during TEST")

        active = shaft.active_maint
        if active is not None:
            expected_route = build_route(1, active.target_floor) + build_route(active.target_floor, 1)
            if shaft.test_route != expected_route:
                self.add_error(
                    f"MAINT-END-{eid}: TEST route mismatch, expected "
                    f"{[int_to_floor(f) for f in expected_route]} got {[int_to_floor(f) for f in shaft.test_route]}"
                )

        if shaft.maint_accept_time >= 0:
            t_complete = t - shaft.maint_accept_time
            if t_complete > MAINT_COMPLETE_TIMEOUT + EPSILON:
                self.add_error(
                    f"MAINT-END-{eid}: T_complete {t_complete:.4f}s > {MAINT_COMPLETE_TIMEOUT}s"
                )

        shaft.mode = "NORMAL"
        shaft.active_maint = None
        shaft.maint_accept_time = -1.0
        shaft.maint1_begin_time = -1.0
        shaft.maint2_begin_time = -1.0
        shaft.worker_id = None
        shaft.worker_locked_after_in = False
        shaft.test_route = []
        shaft.test_open_done = False
        shaft.worker_out_during_test = False

        main.min_floor = MAIN_FLOOR_MIN
        main.max_floor = MAIN_FLOOR_MAX

    def _handle_update_accept(self, t: float, main_eid: int) -> None:
        if main_eid < 1 or main_eid > 6:
            self.add_error(f"UPDATE-ACCEPT-{main_eid}: main id must be 1..6")
            return

        shaft = self.shafts[main_eid]
        if shaft.mode != "NORMAL":
            self.add_error(
                f"UPDATE-ACCEPT-{main_eid}: shaft not in NORMAL (current {shaft.mode})"
            )

        req = shaft.update_queue.pop(0) if shaft.update_queue else None
        if req is None:
            self.add_error(f"UPDATE-ACCEPT-{main_eid}: no pending UPDATE input")
        else:
            if t + INPUT_TIME_TOLERANCE < req.request_time:
                self.add_error(
                    f"UPDATE-ACCEPT-{main_eid}: output before input time {req.request_time:.1f}"
                )
            if req.main_eid != main_eid:
                self.add_error(f"UPDATE-ACCEPT-{main_eid}: mismatch with UPDATE input")

        shaft.active_update = req
        shaft.mode = "UP_ACCEPT"
        shaft.update_accept_time = t

    def _handle_update_begin(self, t: float, main_eid: int) -> None:
        if main_eid < 1 or main_eid > 6:
            self.add_error(f"UPDATE-BEGIN-{main_eid}: invalid main id")
            return

        shaft = self.shafts[main_eid]
        main = self.cars[main_eid]
        backup = self.cars[shaft.backup_id]

        if shaft.mode != "UP_ACCEPT":
            self.add_error(f"UPDATE-BEGIN-{main_eid}: shaft not in UP_ACCEPT")

        if main.door_open:
            self.add_error(f"UPDATE-BEGIN-{main_eid}: main door must be CLOSED")
        if main.floor != 3:
            self.add_error(f"UPDATE-BEGIN-{main_eid}: main must be at F3")

        regular_inside = [pid for pid in main.passengers if pid not in self.workers]
        if regular_inside:
            self.add_error(
                f"UPDATE-BEGIN-{main_eid}: main still has regular passengers {regular_inside}"
            )

        self._clear_car_receives(main_eid)
        self._clear_car_receives(backup.cid)

        shaft.mode = "UPDATE"
        shaft.update_begin_time = t

    def _handle_update_end(self, t: float, main_eid: int) -> None:
        if main_eid < 1 or main_eid > 6:
            self.add_error(f"UPDATE-END-{main_eid}: invalid main id")
            return

        shaft = self.shafts[main_eid]
        main = self.cars[main_eid]
        backup = self.cars[shaft.backup_id]

        if shaft.mode != "UPDATE":
            self.add_error(f"UPDATE-END-{main_eid}: shaft not in UPDATE")

        if shaft.update_begin_time < 0:
            self.add_error(f"UPDATE-END-{main_eid}: UPDATE-BEGIN missing")
        elif t < shaft.update_begin_time + UPDATE_STOP_TIME - EPSILON:
            self.add_error(
                f"UPDATE-END-{main_eid}: update wait too short ({t:.4f} < {shaft.update_begin_time + UPDATE_STOP_TIME:.4f})"
            )

        if shaft.update_accept_time >= 0:
            t_complete = t - shaft.update_accept_time
            if t_complete > UPDATE_COMPLETE_TIMEOUT + EPSILON:
                self.add_error(
                    f"UPDATE-END-{main_eid}: T_complete {t_complete:.4f}s > {UPDATE_COMPLETE_TIMEOUT}s"
                )

        if main.door_open:
            self.add_error(f"UPDATE-END-{main_eid}: main door must be CLOSED")

        main.min_floor = DOUBLE_MAIN_MIN
        main.max_floor = DOUBLE_MAIN_MAX

        if main.floor < DOUBLE_MAIN_MIN or main.floor > DOUBLE_MAIN_MAX:
            self.add_error(
                f"UPDATE-END-{main_eid}: main floor {int_to_floor(main.floor)} out of DOUBLE range"
            )

        backup.active = True
        backup.darkroom = False
        backup.floor = 1
        backup.door_open = False
        backup.open_time = -1.0
        backup.last_action_time = t
        backup.last_arrive_time = t
        backup.min_floor = DOUBLE_BACKUP_MIN
        backup.max_floor = DOUBLE_BACKUP_MAX

        shaft.mode = "DOUBLE"
        shaft.active_update = None
        shaft.update_accept_time = -1.0
        shaft.update_begin_time = -1.0

        self._check_double_safety(shaft.sid)

    def _handle_recycle_accept(self, t: float, backup_eid: int) -> None:
        if backup_eid < 7 or backup_eid > 12:
            self.add_error(f"RECYCLE-ACCEPT-{backup_eid}: backup id must be 7..12")
            return

        sid = backup_eid - 6
        shaft = self.shafts[sid]

        if shaft.mode != "DOUBLE":
            self.add_error(
                f"RECYCLE-ACCEPT-{backup_eid}: shaft not in DOUBLE (current {shaft.mode})"
            )

        req = shaft.recycle_queue.pop(0) if shaft.recycle_queue else None
        if req is None:
            self.add_error(f"RECYCLE-ACCEPT-{backup_eid}: no pending RECYCLE input")
        else:
            if t + INPUT_TIME_TOLERANCE < req.request_time:
                self.add_error(
                    f"RECYCLE-ACCEPT-{backup_eid}: output before input time {req.request_time:.1f}"
                )
            if req.backup_eid != backup_eid:
                self.add_error(f"RECYCLE-ACCEPT-{backup_eid}: mismatch with RECYCLE input")

        shaft.active_recycle = req
        shaft.mode = "REC_ACCEPT"
        shaft.recycle_accept_time = t

    def _handle_recycle_begin(self, t: float, backup_eid: int) -> None:
        if backup_eid < 7 or backup_eid > 12:
            self.add_error(f"RECYCLE-BEGIN-{backup_eid}: backup id must be 7..12")
            return

        sid = backup_eid - 6
        shaft = self.shafts[sid]
        backup = self.cars[backup_eid]

        if shaft.mode != "REC_ACCEPT":
            self.add_error(f"RECYCLE-BEGIN-{backup_eid}: shaft not in REC_ACCEPT")

        if not backup.active or backup.darkroom:
            self.add_error(f"RECYCLE-BEGIN-{backup_eid}: backup not active in shaft")

        if backup.floor != 1:
            self.add_error(f"RECYCLE-BEGIN-{backup_eid}: backup must be at F1")
        if backup.door_open:
            self.add_error(f"RECYCLE-BEGIN-{backup_eid}: backup door must be CLOSED")

        regular_inside = [pid for pid in backup.passengers if pid not in self.workers]
        if regular_inside:
            self.add_error(
                f"RECYCLE-BEGIN-{backup_eid}: backup still has regular passengers {regular_inside}"
            )

        self._clear_car_receives(backup_eid)

        shaft.mode = "RECYCLE"
        shaft.recycle_begin_time = t

    def _handle_recycle_end(self, t: float, backup_eid: int) -> None:
        if backup_eid < 7 or backup_eid > 12:
            self.add_error(f"RECYCLE-END-{backup_eid}: backup id must be 7..12")
            return

        sid = backup_eid - 6
        shaft = self.shafts[sid]
        main = self.cars[sid]
        backup = self.cars[backup_eid]

        if shaft.mode != "RECYCLE":
            self.add_error(f"RECYCLE-END-{backup_eid}: shaft not in RECYCLE")

        if shaft.recycle_begin_time < 0:
            self.add_error(f"RECYCLE-END-{backup_eid}: RECYCLE-BEGIN missing")
        elif t < shaft.recycle_begin_time + RECYCLE_STOP_TIME - EPSILON:
            self.add_error(
                f"RECYCLE-END-{backup_eid}: recycle wait too short ({t:.4f} < {shaft.recycle_begin_time + RECYCLE_STOP_TIME:.4f})"
            )

        if shaft.recycle_accept_time >= 0:
            t_complete = t - shaft.recycle_accept_time
            if t_complete > RECYCLE_COMPLETE_TIMEOUT + EPSILON:
                self.add_error(
                    f"RECYCLE-END-{backup_eid}: T_complete {t_complete:.4f}s > {RECYCLE_COMPLETE_TIMEOUT}s"
                )

        if backup.floor != 1:
            self.add_error(f"RECYCLE-END-{backup_eid}: backup must be at F1")
        if backup.door_open:
            self.add_error(f"RECYCLE-END-{backup_eid}: backup door must be CLOSED")

        regular_inside = [pid for pid in backup.passengers if pid not in self.workers]
        if regular_inside:
            self.add_error(
                f"RECYCLE-END-{backup_eid}: backup still has regular passengers {regular_inside}"
            )

        backup.passengers.clear()
        backup.passenger_weights.clear()
        backup.active_receives.clear()
        backup.active = False
        backup.darkroom = True
        backup.floor = 1
        backup.door_open = False
        backup.open_time = -1.0
        backup.min_floor = MAIN_FLOOR_MIN
        backup.max_floor = MAIN_FLOOR_MAX
        backup.last_action_time = t

        main.min_floor = MAIN_FLOOR_MIN
        main.max_floor = MAIN_FLOOR_MAX

        shaft.mode = "NORMAL"
        shaft.active_recycle = None
        shaft.recycle_accept_time = -1.0
        shaft.recycle_begin_time = -1.0

    def final_checks(self) -> None:
        for pid, p in self.passengers.items():
            if p.state != "ARRIVED":
                if p.state == "INSIDE":
                    loc = f"car {p.location}"
                else:
                    loc = int_to_floor(p.location)
                self.add_error(
                    f"Passenger {pid} not ARRIVED, final state={p.state}, location={loc}"
                )
            if p.current_receive_eid is not None:
                self.add_error(
                    f"Passenger {pid} has unfinished RECEIVE on car {p.current_receive_eid}"
                )

        for cid, car in self.cars.items():
            if car.door_open:
                self.add_error(f"Car {cid} is OPEN at end")

            regular_inside = [pid for pid in car.passengers if pid not in self.workers]
            if regular_inside:
                self.add_error(f"Car {cid} still has passengers: {sorted(regular_inside)}")

            if car.active_receives:
                self.add_error(f"Car {cid} still has active RECEIVEs: {sorted(car.active_receives)}")

            if car.darkroom and (car.active or cid <= 6):
                # main cars never darkroom; backup in darkroom must be inactive
                if cid <= 6:
                    self.add_error(f"Main car {cid} cannot be darkroom")
                elif car.active:
                    self.add_error(f"Backup car {cid} darkroom but active")

        for sid, shaft in self.shafts.items():
            if shaft.mode not in {"NORMAL", "DOUBLE"}:
                self.add_error(f"Shaft {sid} finished in non-terminal mode: {shaft.mode}")

            if shaft.maint_queue:
                self.add_error(f"Shaft {sid} has unaccepted MAINT requests")
            if shaft.update_queue:
                self.add_error(f"Shaft {sid} has unaccepted UPDATE requests")
            if shaft.recycle_queue:
                self.add_error(f"Shaft {sid} has unaccepted RECYCLE requests")

            if shaft.active_maint is not None:
                self.add_error(f"Shaft {sid} has unfinished active MAINT")
            if shaft.active_update is not None:
                self.add_error(f"Shaft {sid} has unfinished active UPDATE")
            if shaft.active_recycle is not None:
                self.add_error(f"Shaft {sid} has unfinished active RECYCLE")

            self._check_double_safety(sid)

        for worker_id, worker in self.workers.items():
            if worker.state != "OUT":
                self.add_error(
                    f"Worker {worker_id} final state={worker.state}, location={worker.location}"
                )

    def power_consumption(self) -> float:
        return self.arrive_count * POWER_MOVE + self.open_count * POWER_OPEN + self.close_count * POWER_CLOSE

    def average_completion_time(self) -> float:
        total = 0.0
        count = 0
        for p in self.passengers.values():
            if p.arrival_time is None:
                continue
            total += p.arrival_time - p.request_time
            count += 1
        return total / count if count else 0.0


def clear_directory(dir_path: Path) -> None:
    if not dir_path.is_dir():
        return
    for item in dir_path.iterdir():
        if item.is_file() or item.is_symlink():
            item.unlink(missing_ok=True)
        elif item.is_dir():
            shutil.rmtree(item)


def sanitize_key(text: str, index: int) -> str:
    ascii_text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")
    if not ascii_text:
        ascii_text = f"target_{index:02d}"
    return ascii_text


def parse_main_class(main_file: Path) -> str:
    package_name = ""
    cls_name = ""
    try:
        text = main_file.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines()[:80]:
            m_pkg = re.match(r"^\s*package\s+([\w.]+)\s*;", line)
            if m_pkg and not package_name:
                package_name = m_pkg.group(1)
            
            m_cls = re.search(r"\bclass\s+([A-Za-z0-9_]+)", line)
            if m_cls and not cls_name:
                cls_name = m_cls.group(1)
                
            if package_name and cls_name:
                break
    except OSError:
        pass

    if not cls_name:
        try:
            cls_name = main_file.resolve().stem
        except Exception:
            cls_name = main_file.stem
            
    return f"{package_name}.{cls_name}" if package_name else cls_name


def _contains_main_method(java_file: Path) -> bool:
    try:
        text = java_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return RE_MAIN_METHOD.search(text) is not None


def choose_source_dir(project_dir: Path) -> Tuple[Path, Path]:
    main_candidates = sorted(project_dir.rglob("MainClass.java"))
    if not main_candidates:
        main_candidates = sorted(project_dir.rglob("Main.java"))
    if not main_candidates:
        main_candidates = sorted(p for p in project_dir.rglob("*.java") if p.name.startswith("Main"))
    if not main_candidates:
        main_candidates = sorted(
            p for p in project_dir.rglob("*.java") if _contains_main_method(p)
        )
    if not main_candidates:
        raise RuntimeError(f"no Java entry with main method found under {project_dir}")

    main_file = main_candidates[0]
    source_dir = main_file.parent

    try:
        rel_parts = main_file.relative_to(project_dir).parts
        for idx, part in enumerate(rel_parts):
            if part.lower() == "src":
                source_dir = project_dir.joinpath(*rel_parts[: idx + 1])
                break
    except Exception:
        pass

    return source_dir, main_file


def compile_project(source_dir: Path, build_dir: Path, classpath: str, timeout_sec: float) -> Tuple[bool, str]:
    java_files = [str(p) for p in source_dir.rglob("*.java")]
    if not java_files:
        return False, f"no java files under {source_dir}"

    build_dir.mkdir(parents=True, exist_ok=True)
    clear_directory(build_dir)

    cmd = ["javac", "-encoding", "UTF-8", "-d", str(build_dir)]
    if classpath:
        cmd.extend(["-cp", classpath])
    cmd.extend(java_files)

    try:
        p = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
        )
    except FileNotFoundError:
        return False, "javac not found"
    except subprocess.TimeoutExpired:
        return False, f"javac timeout after {timeout_sec:.1f}s"
    except Exception as exc:
        return False, f"javac error: {exc}"

    if p.returncode != 0:
        detail = (p.stdout or "") + "\n" + (p.stderr or "")
        return False, f"javac failed (exit={p.returncode})\n{detail.strip()}"

    return True, "compile ok"


def discover_projects(
    co_judge_dir: Path,
    pattern: str,
    build_root: Path,
    classpath: str,
    compile_timeout: float,
) -> List[TargetProject]:
    projects: List[TargetProject] = []
    project_errors: List[str] = []
    entries = sorted(co_judge_dir.iterdir(), key=lambda p: p.name.lower())
    direct = direct_target_entry(pattern)
    targets = [direct] if direct else matching_target_entries(entries, pattern)

    for idx, target_path in enumerate(targets, start=1):
        try:
            if target_path.is_dir():
                source_dir, main_file = choose_source_dir(target_path)
                main_class = parse_main_class(main_file)
                key = sanitize_key(target_path.name, idx)
                build_dir = build_root / key

                ok, msg = compile_project(source_dir, build_dir, classpath, compile_timeout)
                if not ok:
                    raise RuntimeError(f"compile failed: {msg}")

                cp_items = [str(build_dir)] + ([classpath] if classpath else [])
                command = ["java", "-cp", os.pathsep.join(cp_items), main_class]

                projects.append(
                    TargetProject(
                        key=key,
                        display_name=target_path.name,
                        project_dir=target_path,
                        source_dir=source_dir,
                        main_class=main_class,
                        build_dir=build_dir,
                        command=command,
                    )
                )
            else:
                key = sanitize_key(f"{target_path.stem}_jar", idx)
                projects.append(
                    TargetProject(
                        key=key,
                        display_name=target_path.name,
                        project_dir=target_path.parent,
                        source_dir=target_path.parent,
                        main_class="<jar>",
                        build_dir=build_root / key,
                        command=["java", "-jar", str(target_path.resolve())],
                    )
                )
        except Exception as exc:
            project_errors.append(f"{target_path.name}: {exc}")
            continue

    if not projects:
        details = "; ".join(project_errors[:5]) if project_errors else "no matched directories"
        raise RuntimeError(f"未发现可用目标项目，详情: {details}")

    if project_errors:
        print("[WARN] skipped invalid targets:", file=sys.stderr)
        for err in project_errors:
            print(f"  - {err}", file=sys.stderr)

    return projects


def parse_input_requests(
    input_text: str,
    mutual_mode: bool = False,
) -> Tuple[Dict[int, PassengerRequest], ControlRequests, List[str]]:
    passengers: Dict[int, PassengerRequest] = {}
    controls = ControlRequests()
    errors: List[str] = []

    all_ids: Set[int] = set()  # passenger id + worker id uniqueness
    total_count = 0
    first_ts: Optional[float] = None
    last_ts = -1.0

    last_special_ts_by_shaft: Dict[int, float] = {}
    maint_count_by_main: Dict[int, int] = {}
    update_count_by_shaft: Dict[int, int] = {}
    recycle_count_by_shaft: Dict[int, int] = {}

    def has_one_decimal(ts_text: str) -> bool:
        if "." not in ts_text:
            return False
        frac = ts_text.split(".", 1)[1]
        return len(frac) == 1 and frac.isdigit()

    for idx, raw_line in enumerate(input_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        total_count += 1

        m = RE_INPUT_PASSENGER.match(line)
        if m:
            ts_s, pid_s, wei_s, frm_s, to_s = m.groups()
            ts = float(ts_s)
            pid = int(pid_s)
            wei = int(wei_s)
            frm = floor_to_int(frm_s)
            to = floor_to_int(to_s)

            if frm is None or to is None:
                errors.append(f"input line {idx} invalid floor")
            elif frm == to:
                errors.append(f"input line {idx} FROM equals TO")

            if pid <= 0:
                errors.append(f"input line {idx} invalid passenger id")
            if pid in all_ids:
                errors.append(f"input line {idx} duplicate id {pid}")
            if not (50 <= wei <= 100):
                errors.append(f"input line {idx} invalid weight {wei}")

            if ts < last_ts - EPSILON:
                errors.append(f"input timestamp decreases at line {idx}")
            if mutual_mode and not has_one_decimal(ts_s):
                errors.append(f"input line {idx} timestamp must keep one decimal")

            all_ids.add(pid)
            if frm is not None and to is not None:
                passengers[pid] = PassengerRequest(ts, pid, wei, frm, to)

            last_ts = max(last_ts, ts)
            if first_ts is None:
                first_ts = ts
            continue

        m = RE_INPUT_MAINT.match(line)
        if m:
            ts_s, eid_s, wid_s, target_s = m.groups()
            ts = float(ts_s)
            eid = int(eid_s)
            wid = int(wid_s)
            target = floor_to_int(target_s)

            if eid < 1 or eid > 6:
                errors.append(f"input line {idx} invalid MAINT main id {eid}")
            if wid <= 0:
                errors.append(f"input line {idx} invalid worker id")
            if wid in all_ids:
                errors.append(f"input line {idx} duplicate id {wid}")
            if target not in MAINT_TARGET_FLOORS:
                errors.append(f"input line {idx} invalid MAINT target floor {target_s}")

            if ts < last_ts - EPSILON:
                errors.append(f"input timestamp decreases at line {idx}")
            if mutual_mode and not has_one_decimal(ts_s):
                errors.append(f"input line {idx} timestamp must keep one decimal")

            sid = eid
            if sid in last_special_ts_by_shaft and ts < last_special_ts_by_shaft[sid] + 8.0 - EPSILON:
                errors.append(f"input line {idx} same-shaft special interval < 8s")
            last_special_ts_by_shaft[sid] = ts

            maint_count_by_main[eid] = maint_count_by_main.get(eid, 0) + 1
            if mutual_mode and maint_count_by_main[eid] > 1:
                errors.append(f"input line {idx} elevator {eid} has more than one MAINT in mutual mode")

            all_ids.add(wid)
            if target is not None:
                req = MaintRequestInput(ts, eid, wid, target)
                controls.maints_by_worker[wid] = req
                controls.maints_by_shaft.setdefault(sid, []).append(req)

            last_ts = max(last_ts, ts)
            if first_ts is None:
                first_ts = ts
            continue

        m = RE_INPUT_UPDATE.match(line)
        if m:
            ts_s, eid_s = m.groups()
            ts = float(ts_s)
            eid = int(eid_s)
            if eid < 1 or eid > 6:
                errors.append(f"input line {idx} invalid UPDATE main id {eid}")

            if ts < last_ts - EPSILON:
                errors.append(f"input timestamp decreases at line {idx}")
            if mutual_mode and not has_one_decimal(ts_s):
                errors.append(f"input line {idx} timestamp must keep one decimal")

            sid = eid
            if sid in last_special_ts_by_shaft and ts < last_special_ts_by_shaft[sid] + 8.0 - EPSILON:
                errors.append(f"input line {idx} same-shaft special interval < 8s")
            last_special_ts_by_shaft[sid] = ts

            update_count_by_shaft[sid] = update_count_by_shaft.get(sid, 0) + 1
            if update_count_by_shaft[sid] > 1:
                errors.append(f"input line {idx} shaft {sid} has more than one UPDATE")

            req = UpdateRequestInput(ts, eid)
            controls.updates_by_shaft.setdefault(sid, []).append(req)

            last_ts = max(last_ts, ts)
            if first_ts is None:
                first_ts = ts
            continue

        m = RE_INPUT_RECYCLE.match(line)
        if m:
            ts_s, beid_s = m.groups()
            ts = float(ts_s)
            beid = int(beid_s)
            if beid < 7 or beid > 12:
                errors.append(f"input line {idx} invalid RECYCLE backup id {beid}")

            if ts < last_ts - EPSILON:
                errors.append(f"input timestamp decreases at line {idx}")
            if mutual_mode and not has_one_decimal(ts_s):
                errors.append(f"input line {idx} timestamp must keep one decimal")

            sid = beid - 6
            if sid in last_special_ts_by_shaft and ts < last_special_ts_by_shaft[sid] + 8.0 - EPSILON:
                errors.append(f"input line {idx} same-shaft special interval < 8s")
            last_special_ts_by_shaft[sid] = ts

            recycle_count_by_shaft[sid] = recycle_count_by_shaft.get(sid, 0) + 1
            if recycle_count_by_shaft[sid] > 1:
                errors.append(f"input line {idx} shaft {sid} has more than one RECYCLE")

            req = RecycleRequestInput(ts, beid)
            controls.recycles_by_shaft.setdefault(sid, []).append(req)

            last_ts = max(last_ts, ts)
            if first_ts is None:
                first_ts = ts
            continue

        errors.append(f"input line {idx} malformed: {line}")

    if total_count < 1 or total_count > 100:
        errors.append(f"total instruction count must be 1..100, got {total_count}")

    if mutual_mode:
        if total_count > 70:
            errors.append(f"mutual mode instruction count must be <=70, got {total_count}")
        if first_ts is not None and first_ts < 1.0 - EPSILON:
            errors.append(f"mutual mode first timestamp must be >=1.0, got {first_ts:.4f}")
        if last_ts > 50.0 + EPSILON:
            errors.append(f"mutual mode last timestamp must be <=50.0, got {last_ts:.4f}")

    for sid, recycles in controls.recycles_by_shaft.items():
        updates = controls.updates_by_shaft.get(sid, [])
        if recycles and not updates:
            errors.append(f"shaft {sid} has RECYCLE input but no UPDATE input")

    for sid in range(1, NUM_SHAFTS + 1):
        controls.maints_by_shaft.setdefault(sid, [])
        controls.updates_by_shaft.setdefault(sid, [])
        controls.recycles_by_shaft.setdefault(sid, [])

    return passengers, controls, errors


def build_input_schedule(input_text: str) -> List[Tuple[float, str]]:
    schedule: List[Tuple[float, str]] = []
    for raw_line in input_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = re.match(r"^\[\s*([\d.]+)\s*\](.*)$", line)
        if m:
            ts = float(m.group(1))
            payload = m.group(2).strip()
            schedule.append((ts, payload + "\n"))
        else:
            schedule.append((0.0, line + "\n"))
    return schedule


def _stream_reader(stream, chunks: List[str], lock: Lock) -> None:
    try:
        for chunk in iter(lambda: stream.read(8192), ""):
            with lock:
                chunks.append(chunk)
    except Exception:
        pass
    finally:
        try:
            stream.close()
        except Exception:
            pass


def run_java_command(
    command: List[str],
    input_schedule: List[Tuple[float, str]],
    soft_timeout: float,
    hard_timeout: float,
) -> Tuple[str, str, float, Optional[str]]:
    start = time.monotonic()
    stdout_chunks: List[str] = []
    stderr_chunks: List[str] = []
    out_lock = Lock()
    err_lock = Lock()

    process = None
    out_thread = None
    err_thread = None
    in_thread = None
    status_code: Optional[str] = None
    soft_marked = False

    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        out_thread = Thread(target=_stream_reader, args=(process.stdout, stdout_chunks, out_lock), daemon=True)
        err_thread = Thread(target=_stream_reader, args=(process.stderr, stderr_chunks, err_lock), daemon=True)
        out_thread.start()
        err_thread.start()

        def feed_inputs() -> None:
            start_feed = time.monotonic() + INPUT_FEED_STARTUP_DELAY
            try:
                for ts, payload in input_schedule:
                    target = start_feed + max(0.0, ts)
                    delay = target - time.monotonic()
                    if delay > 0:
                        time.sleep(delay)
                    if process.poll() is not None:
                        break
                    process.stdin.write(payload)
                    process.stdin.flush()
            except (BrokenPipeError, OSError):
                pass
            finally:
                try:
                    process.stdin.close()
                except Exception:
                    pass

        in_thread = Thread(target=feed_inputs, daemon=True)
        in_thread.start()

        while True:
            elapsed = time.monotonic() - start
            if elapsed > hard_timeout:
                status_code = "KILLED"
                process.kill()
                break

            ret = process.poll()
            if ret is not None:
                if ret != 0:
                    status_code = "EXEC_ERROR"
                elif soft_marked:
                    status_code = "TLE"
                else:
                    status_code = None
                break

            if (not soft_marked) and elapsed > soft_timeout:
                soft_marked = True
                status_code = "TLE"

            time.sleep(POLL_INTERVAL)

        if process.poll() is None:
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                process.kill()
                status_code = "KILLED"

        if out_thread is not None:
            out_thread.join(timeout=5.0)
        if err_thread is not None:
            err_thread.join(timeout=5.0)
        if in_thread is not None:
            in_thread.join(timeout=1.0)

        with out_lock:
            out_text = "".join(stdout_chunks)
        with err_lock:
            err_text = "".join(stderr_chunks)

        return out_text, err_text, time.monotonic() - start, status_code

    except FileNotFoundError:
        return "", "java command not found", time.monotonic() - start, "JAVA_NOT_FOUND"
    except Exception as exc:
        return "", f"runner error: {exc}", time.monotonic() - start, "EXEC_ERROR"
    finally:
        if process is not None and process.poll() is None:
            try:
                process.kill()
            except Exception:
                pass


def normalize_events(stdout_text: str) -> List[str]:
    lines: List[str] = []
    for raw in stdout_text.splitlines():
        line = raw.strip()
        if not line or "[LOG]" in line:
            continue
        line = re.sub(r"^\[\s*[\d.]+\s*\]", "", line).strip()
        if line:
            lines.append(line)
    return lines


def first_diff(a: List[str], b: List[str]) -> Tuple[int, str, str]:
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i, a[i], b[i]
    if len(a) == len(b):
        return -1, "", ""
    if len(a) > len(b):
        return n, a[n], "<missing>"
    return n, "<missing>", b[n]


def run_target_case(
    target: TargetProject,
    case_name: str,
    input_text: str,
    passengers: Dict[int, PassengerRequest],
    maints: ControlRequests,
    out_dir: Path,
    soft_timeout: float,
    hard_timeout: float,
) -> TargetRunResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{target.key}__{Path(case_name).stem}.txt"

    schedule = build_input_schedule(input_text)
    stdout_text, stderr_text, elapsed_sec, run_status = run_java_command(
        command=target.command,
        input_schedule=schedule,
        soft_timeout=soft_timeout,
        hard_timeout=hard_timeout,
    )

    with out_path.open("w", encoding="utf-8", errors="replace") as f:
        f.write(stdout_text)
        if stderr_text:
            f.write("\n\n--- STDERR ---\n")
            f.write(stderr_text)

    status = "PASSED"
    errors: List[str] = []

    if run_status == "JAVA_NOT_FOUND":
        status = "JAVA_ERROR"
        errors.append("java command not found")
    elif run_status == "KILLED":
        status = "TIMEOUT_HARD"
        errors.append("hard timeout exceeded")
    elif run_status == "TLE":
        status = "TIMEOUT_SOFT"
        errors.append("soft timeout exceeded")
    elif run_status == "EXEC_ERROR":
        status = "RUNTIME_ERROR"
        errors.append("runtime error")

    sim_time = 0.0
    power = 0.0
    avg_time = 0.0

    if stdout_text.strip():
        validator = Validator(passengers, maints)
        for line in stdout_text.splitlines():
            validator.validate_line(line)
        validator.final_checks()

        sim_time = validator.last_timestamp
        power = validator.power_consumption()
        avg_time = validator.average_completion_time()

        if validator.errors:
            errors.extend(validator.errors)
            if status == "PASSED":
                status = "WRONG_ANSWER"
    else:
        if status == "PASSED":
            status = "WRONG_ANSWER"
        errors.append("no output")

    if stderr_text.strip() and status in {"PASSED", "WRONG_ANSWER"}:
        errors.append("stderr is non-empty")

    normalized = normalize_events(stdout_text)

    return TargetRunResult(
        status=status,
        stdout=stdout_text,
        stderr=stderr_text,
        elapsed_sec=elapsed_sec,
        sim_time=sim_time,
        power=power,
        avg_time=avg_time,
        errors=errors,
        normalized_events=normalized,
        raw_output_path=str(out_path),
    )


def write_problem_case(
    case_summary: CaseSummary,
    input_text: str,
    problem_dir: Path,
    target_order: List[TargetProject],
) -> None:
    problem_dir.mkdir(parents=True, exist_ok=True)
    path = problem_dir / f"{Path(case_summary.case_name).stem}.md"

    baseline_target = target_order[0]
    baseline = case_summary.targets[baseline_target.key].normalized_events

    lines: List[str] = []
    lines.append(f"# Problem Case: {case_summary.case_name}")
    lines.append("")
    lines.append(f"- all_correct: {case_summary.all_correct}")
    lines.append(f"- all_consistent: {case_summary.all_consistent}")
    lines.append(f"- effective: {case_summary.effective}")
    lines.append("")
    lines.append("## Input")
    lines.append("")
    lines.append("```text")
    lines.append(input_text.rstrip("\n"))
    lines.append("```")
    lines.append("")
    lines.append("## Per-target status")
    lines.append("")
    lines.append("| target | status | sim_time | exec_time | raw_output |")
    lines.append("|---|---|---:|---:|---|")

    for target in target_order:
        r = case_summary.targets[target.key]
        lines.append(
            f"| {target.display_name} | {r.status} | {r.sim_time:.3f} | {r.elapsed_sec:.3f} | {r.raw_output_path} |"
        )

    lines.append("")
    lines.append("## Differences")
    lines.append("")

    for target in target_order[1:]:
        r = case_summary.targets[target.key]
        idx, left, right = first_diff(baseline, r.normalized_events)
        if idx == -1:
            lines.append(f"- {target.display_name}: no event difference with baseline")
        else:
            lines.append(
                f"- {target.display_name}: first diff at event #{idx + 1}; baseline='{left}' vs target='{right}'"
            )

    lines.append("")
    lines.append("## Error snippets")
    lines.append("")
    for target in target_order:
        r = case_summary.targets[target.key]
        lines.append(f"### {target.display_name}")
        if r.errors:
            for msg in r.errors[:12]:
                lines.append(f"- {msg}")
            if len(r.errors) > 12:
                lines.append(f"- ... and {len(r.errors) - 12} more")
        else:
            lines.append("- (none)")
        lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary_report(report_dir: Path, summaries: List[CaseSummary], target_order: List[TargetProject]) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)

    total = len(summaries)
    all_correct = sum(1 for s in summaries if s.all_correct)
    effective = sum(1 for s in summaries if s.effective)

    json_path = report_dir / "consensus_summary.json"
    md_path = report_dir / "consensus_summary.md"

    payload = {
        "total_cases": total,
        "all_correct_cases": all_correct,
        "effective_cases": effective,
        "all_correct_rate": (all_correct / total) if total else 0.0,
        "effective_rate": (effective / total) if total else 0.0,
        "targets": [t.display_name for t in target_order],
        "cases": [
            {
                "case_name": s.case_name,
                "all_correct": s.all_correct,
                "all_consistent": s.all_consistent,
                "effective": s.effective,
                "targets": {
                    t.display_name: {
                        "status": s.targets[t.key].status,
                        "sim_time": s.targets[t.key].sim_time,
                        "exec_time": s.targets[t.key].elapsed_sec,
                        "errors": s.targets[t.key].errors,
                        "raw_output": s.targets[t.key].raw_output_path,
                    }
                    for t in target_order
                },
            }
            for s in summaries
        ],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: List[str] = []
    lines.append("# HW7 Consensus Judge Report")
    lines.append("")
    lines.append(f"- total_cases: {total}")
    lines.append(f"- all_correct_cases: {all_correct}")
    lines.append(f"- effective_cases: {effective}")
    lines.append(f"- all_correct_rate: {((all_correct / total) if total else 0.0):.3f}")
    lines.append(f"- effective_rate: {((effective / total) if total else 0.0):.3f}")
    lines.append("")
    lines.append("## Case summary")
    lines.append("")
    lines.append("| case | all_correct | all_consistent | effective |")
    lines.append("|---|---|---|---|")
    for s in summaries:
        lines.append(f"| {s.case_name} | {s.all_correct} | {s.all_consistent} | {s.effective} |")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HW7 consensus judge")
    parser.add_argument("--mode", choices=["self", "mutual"], default="mutual", help="input constraint mode")
    parser.add_argument("--co-judge-dir", default="..", help="co_judge root directory")
    parser.add_argument("--target-pattern", default="互测代码_*", help="target glob/regex (directory or .jar)")
    parser.add_argument("--official-jar", default="lib/elevator3-2026.jar", help="official package jar")
    parser.add_argument("--build-dir", default=".build_targets", help="compiled classes directory")

    parser.add_argument("--generate", action="store_true", help="generate data before running")
    parser.add_argument("--generator", default="data_generator_hw7.py", help="generator script path")
    parser.add_argument("--count", type=int, default=8, help="extra random case count")

    parser.add_argument("--data-dir", default="data", help="testcase directory")
    parser.add_argument("--out-dir", default="out_raw", help="raw output directory")
    parser.add_argument("--report-dir", default="report", help="report directory")
    parser.add_argument("--problem-dir", default="problem_cases", help="problem case detail directory")

    parser.add_argument("--timeout", type=float, default=180.0, help="merged timeout per target")
    parser.add_argument("--soft-timeout", type=float, default=None, help="deprecated, override timeout")
    parser.add_argument("--hard-timeout", type=float, default=None, help="deprecated, override timeout")
    parser.add_argument("--compile-timeout", type=float, default=90.0, help="compile timeout per target")
    parser.add_argument("--max-cases", type=int, default=0, help="0 means all cases")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    base = Path(__file__).resolve().parent
    co_judge_dir = (base / args.co_judge_dir).resolve()
    build_dir = (base / args.build_dir).resolve()
    data_dir = (base / args.data_dir).resolve()
    out_dir = (base / args.out_dir).resolve()
    report_dir = (base / args.report_dir).resolve()
    problem_dir = (base / args.problem_dir).resolve()
    generator_script = (base / args.generator).resolve()
    official_jar = (base / args.official_jar).resolve()

    soft_timeout = args.soft_timeout if args.soft_timeout is not None else args.timeout
    hard_timeout = args.hard_timeout if args.hard_timeout is not None else args.timeout

    if soft_timeout <= 0 or hard_timeout <= 0:
        print("Error: timeout must be positive", file=sys.stderr)
        return 2

    if hard_timeout < soft_timeout:
        print("Error: hard-timeout must be >= soft-timeout", file=sys.stderr)
        return 2

    if not official_jar.is_file():
        print(f"Error: official jar not found: {official_jar}", file=sys.stderr)
        return 2

    if args.generate:
        if not generator_script.is_file():
            print(f"Error: generator script not found: {generator_script}", file=sys.stderr)
            return 2
        data_dir.mkdir(parents=True, exist_ok=True)
        clear_directory(data_dir)
        cmd = [sys.executable, str(generator_script), "--out", str(data_dir), "--count", str(max(0, args.count))]
        if args.mode == "mutual":
            cmd.append("--strict-mutual")
        proc = subprocess.run(cmd, check=False)
        if proc.returncode != 0:
            print(f"Error: generator failed with exit code {proc.returncode}", file=sys.stderr)
            return 2

    data_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    problem_dir.mkdir(parents=True, exist_ok=True)

    clear_directory(out_dir)
    clear_directory(problem_dir)

    classpath = str(official_jar)
    projects = discover_projects(
        co_judge_dir=co_judge_dir,
        pattern=args.target_pattern,
        build_root=build_dir,
        classpath=classpath,
        compile_timeout=args.compile_timeout,
    )

    case_files = sorted(p for p in data_dir.glob("*.txt") if p.is_file())
    if args.max_cases > 0:
        case_files = case_files[: args.max_cases]

    if not case_files:
        print(f"Error: no testcase in {data_dir}", file=sys.stderr)
        return 2

    print("Detected targets:")
    for p in projects:
        print(f"  - {p.display_name} ({p.main_class})")
    print(f"Detected cases: {len(case_files)}")

    summaries: List[CaseSummary] = []

    for i, case_path in enumerate(case_files, start=1):
        case_name = case_path.name
        print(f"[{i}/{len(case_files)}] {case_name}")

        input_text = case_path.read_text(encoding="utf-8", errors="replace")
        passengers, controls, input_errors = parse_input_requests(
            input_text,
            mutual_mode=(args.mode == "mutual"),
        )
        if input_errors:
            fake_targets: Dict[str, TargetRunResult] = {}
            for p_proj in projects:
                fake_targets[p_proj.key] = TargetRunResult(
                    status="INPUT_ERROR",
                    stdout="",
                    stderr="",
                    elapsed_sec=0.0,
                    sim_time=0.0,
                    power=0.0,
                    avg_time=0.0,
                    errors=input_errors,
                    normalized_events=[],
                    raw_output_path="",
                )
            case_summary = CaseSummary(
                case_name=case_name,
                all_correct=False,
                all_consistent=False,
                effective=False,
                targets=fake_targets,
            )
            summaries.append(case_summary)
            write_problem_case(case_summary, input_text, problem_dir, projects)
            print("    -> INPUT_ERROR")
            continue

        per_target: Dict[str, TargetRunResult] = {}
        for p_proj in projects:
            result = run_target_case(
                target=p_proj,
                case_name=case_name,
                input_text=input_text,
                passengers=passengers,
                maints=controls,
                out_dir=out_dir,
                soft_timeout=soft_timeout,
                hard_timeout=hard_timeout,
            )
            per_target[p_proj.key] = result
            print(f"    - {p_proj.display_name}: {result.status}")

        all_correct = all(per_target[p_proj.key].status == "PASSED" for p_proj in projects)
        all_consistent = False
        if all_correct:
            baseline = per_target[projects[0].key].normalized_events
            all_consistent = all(
                per_target[p_proj.key].normalized_events == baseline for p_proj in projects
            )

        effective = all_correct and all_consistent
        case_summary = CaseSummary(
            case_name=case_name,
            all_correct=all_correct,
            all_consistent=all_consistent,
            effective=effective,
            targets=per_target,
        )
        summaries.append(case_summary)

        if not effective:
            write_problem_case(case_summary, input_text, problem_dir, projects)

        print(f"    -> effective={effective}")

    write_summary_report(report_dir, summaries, projects)

    effective_count = sum(1 for s in summaries if s.effective)
    print("=" * 56)
    print(f"effective cases: {effective_count}/{len(summaries)}")
    print(f"summary json: {report_dir / 'consensus_summary.json'}")
    print(f"summary md:   {report_dir / 'consensus_summary.md'}")
    print(f"problem dir:  {problem_dir}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted by user", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise SystemExit(3)
