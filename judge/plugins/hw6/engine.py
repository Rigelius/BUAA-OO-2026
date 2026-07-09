#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HW6 multi-target consensus judge.

Adapted from HW5 judge to handle HW6 changes:
  - Passenger input format no longer contains BY-<elevatorID>
  - Added MAINT (maintenance) requests and state machine validation
  - RECEIVE is self-assigned by the program (not fixed to input elevator)
  - Maintenance outputs: MAINT-ACCEPT, MAINT1-BEGIN, MAINT2-BEGIN, MAINT-END
  - Maintenance worker IN/OUT same as regular passengers
  - Weight-based capacity: 400kg
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
from typing import Dict, List, Optional, Set, Tuple, Any

from judge.core.target_matching import direct_target_entry, matching_target_entries

EPSILON = 1e-9
NUM_ELEVATORS = 6
MOVE_TIME_PER_FLOOR = 0.4
DOOR_OPEN_CLOSE_TIME = 0.4
MAX_LOAD = 400
POLL_INTERVAL = 0.1

# Maintenance constants
MAINT_STOP_TIME = 1.0       # REPAIR stage minimum duration
MAINT_COMPLETE_TIMEOUT = 7.0  # MAINT-ACCEPT to MAINT-END max 7s
MAINT_TEST_SPEED = 0.2      # TEST state elevator speed: 0.2s/floor
MAINT_TARGET_FLOORS = {-2, -1, 2, 3}  # B2, B1, F2, F3

POWER_OPEN = 0.1
POWER_CLOSE = 0.1
POWER_MOVE = 0.4

FLOOR_MAP_STR_TO_INT = {
    "B4": -4, "B3": -3, "B2": -2, "B1": -1,
    "F1": 1, "F2": 2, "F3": 3, "F4": 4,
    "F5": 5, "F6": 6, "F7": 7,
}
FLOOR_MAP_INT_TO_STR = {v: k for k, v in FLOOR_MAP_STR_TO_INT.items()}

# HW6 input patterns
# Passenger: [ts]pid-WEI-weight-FROM-floor-TO-floor  (no BY)
RE_INPUT_PASSENGER = re.compile(
    r"^\[\s*([\d.]+)\s*\](\d+)-WEI-(\d+)-FROM-([BF]\d+)-TO-([BF]\d+)$"
)
# MAINT: [ts]MAINT-elevatorID-workerID-targetFloor
RE_INPUT_MAINT = re.compile(
    r"^\[\s*([\d.]+)\s*\]MAINT-(\d+)-(\d+)-([BF]\d+)$"
)

# Output patterns
RE_TIMESTAMP = re.compile(r"^\[\s*([\d.]+)\s*\]")
RE_RECEIVE = re.compile(r"^\[\s*([\d.]+)\s*\]RECEIVE-(\d+)-(\d+)$")
RE_ARRIVE = re.compile(r"^\[\s*([\d.]+)\s*\]ARRIVE-([BF]\d+)-(\d+)$")
RE_OPEN = re.compile(r"^\[\s*([\d.]+)\s*\]OPEN-([BF]\d+)-(\d+)$")
RE_CLOSE = re.compile(r"^\[\s*([\d.]+)\s*\]CLOSE-([BF]\d+)-(\d+)$")
RE_IN = re.compile(r"^\[\s*([\d.]+)\s*\]IN-(\d+)-([BF]\d+)-(\d+)$")
RE_OUT = re.compile(r"^\[\s*([\d.]+)\s*\]OUT-([SF])-(\d+)-([BF]\d+)-(\d+)$")

# Maintenance output patterns
RE_MAINT_ACCEPT = re.compile(
    r"^\[\s*([\d.]+)\s*\]MAINT-ACCEPT-(\d+)-(\d+)-([BF]\d+)$"
)
RE_MAINT1_BEGIN = re.compile(r"^\[\s*([\d.]+)\s*\]MAINT1-BEGIN-(\d+)$")
RE_MAINT2_BEGIN = re.compile(r"^\[\s*([\d.]+)\s*\]MAINT2-BEGIN-(\d+)$")
RE_MAINT_END = re.compile(r"^\[\s*([\d.]+)\s*\]MAINT-END-(\d+)$")
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
    elevator_id: int
    worker_id: int
    target_floor: int


@dataclass
class PassengerState:
    pid: int
    weight: int
    destination: int
    request_time: float
    state: str = "OUTSIDE"           # OUTSIDE / INSIDE / ARRIVED
    location: int = 0                # floor_int or elevator_id when INSIDE
    current_receive_eid: Optional[int] = None
    arrival_time: Optional[float] = None


@dataclass
class MaintWorkerState:
    worker_id: int
    elevator_id: int
    target_floor: int
    state: str = "OUTSIDE"    # OUTSIDE / INSIDE / OUT
    location: int = 1         # always F1


@dataclass
class ElevatorState:
    eid: int
    floor: int = 1                     # F1 = 1
    door_open: bool = False
    open_time: float = -1.0
    last_action_time: float = 0.0
    passengers: Set[int] = field(default_factory=set)           # pid
    active_receives: Set[int] = field(default_factory=set)      # pid
    passenger_weights: Dict[int, int] = field(default_factory=dict)

    # Maintenance state machine
    maint_state: str = "NORMAL"        # NORMAL / REP_ACCEPT / REPAIR / TEST
    maint_worker_id: Optional[int] = None
    maint_target_floor: Optional[int] = None
    maint_accept_time: float = -1.0
    maint1_begin_time: float = -1.0
    maint2_begin_time: float = -1.0
    maint_worker_inside: bool = False

    # TEST state tracking
    test_phase: str = ""               # "" / "TO_TARGET" / "TO_F1" / "DONE"
    test_visits: List = field(default_factory=list)


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


# Validator

class Validator:
    """Full HW6 output validator with maintenance state machine."""

    def __init__(
        self,
        passenger_requests: Dict[int, PassengerRequest],
        maint_requests: Dict[int, MaintRequestInput],
    ) -> None:
        self.errors: List[str] = []
        self.p_requests = passenger_requests
        self.m_requests = maint_requests
        self.last_timestamp = 0.0

        self.arrive_count = 0
        self.open_count = 0
        self.close_count = 0

        self.elevators: Dict[int, ElevatorState] = {
            eid: ElevatorState(eid=eid) for eid in range(1, NUM_ELEVATORS + 1)
        }
        self.passengers: Dict[int, PassengerState] = {}
        for req in passenger_requests.values():
            self.passengers[req.pid] = PassengerState(
                pid=req.pid,
                weight=req.weight,
                destination=req.to_floor,
                request_time=req.request_time,
                location=req.from_floor,
            )

        self.maint_workers: Dict[int, MaintWorkerState] = {}
        for mreq in maint_requests.values():
            self.maint_workers[mreq.worker_id] = MaintWorkerState(
                worker_id=mreq.worker_id,
                elevator_id=mreq.elevator_id,
                target_floor=mreq.target_floor,
            )

        # Track which MAINT input has been accepted
        self.maint_accepted: Set[int] = set()  # elevator IDs that have accepted MAINT

    def add_error(self, message: str) -> None:
        self.errors.append(f"[t~{self.last_timestamp:.4f}] {message}")

    def _parse_time(self, line: str) -> Optional[float]:
        m = RE_TIMESTAMP.match(line)
        if not m:
            self.add_error(f"Malformed line without timestamp: {line}")
            return None
        try:
            return float(m.group(1))
        except ValueError:
            self.add_error(f"Invalid timestamp value: {line}")
            return None

    def _advance_time(self, t: float) -> None:
        if t < self.last_timestamp - EPSILON:
            self.add_error(f"Timestamp decreases: {t:.4f} < {self.last_timestamp:.4f}")
        self.last_timestamp = max(self.last_timestamp, t)

    def _load_of(self, eid: int) -> int:
        e = self.elevators[eid]
        total = 0
        for pid in e.passengers:
            w = e.passenger_weights.get(pid, 0)
            total += w
        return total

    def _get_elevator(self, eid: int) -> Optional[ElevatorState]:
        e = self.elevators.get(eid)
        if e is None:
            self.add_error(f"Invalid elevator id {eid}")
        return e

    def _get_passenger(self, pid: int) -> Optional[PassengerState]:
        p = self.passengers.get(pid)
        if p is None:
            self.add_error(f"Unknown passenger id {pid}")
        return p

    # Line validation

    def validate_line(self, line: str) -> None:
        text = line.strip()
        if not text or "[LOG]" in text:
            return

        t = self._parse_time(text)
        if t is None:
            return
        self._advance_time(t)

        # Try all patterns
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

        self.add_error(f"Unrecognized output format: {text}")

    # RECEIVE

    def _handle_receive(self, t: float, pid: int, eid: int) -> None:
        p = self._get_passenger(pid)
        e = self._get_elevator(eid)
        if p is None or e is None:
            return

        # HW6: RECEIVE can assign to any elevator (no BY constraint)
        if p.state == "ARRIVED":
            self.add_error(f"RECEIVE-{pid}-{eid}: passenger already ARRIVED")
        if p.state != "OUTSIDE":
            self.add_error(f"RECEIVE-{pid}-{eid}: passenger not OUTSIDE (state={p.state})")
        if p.current_receive_eid is not None:
            self.add_error(
                f"RECEIVE-{pid}-{eid}: previous RECEIVE not ended (eid={p.current_receive_eid})"
            )

        # Cannot RECEIVE during REPAIR or TEST state
        if e.maint_state in ("REPAIR", "TEST"):
            self.add_error(f"RECEIVE-{pid}-{eid}: elevator in {e.maint_state} state, RECEIVE forbidden")

        p.current_receive_eid = eid
        e.active_receives.add(pid)

    # ARRIVE

    def _handle_arrive(self, t: float, floor_s: str, eid: int) -> None:
        e = self._get_elevator(eid)
        floor_i = floor_to_int(floor_s)
        if e is None or floor_i is None:
            self.add_error(f"ARRIVE-{floor_s}-{eid}: invalid floor/elevator")
            return

        if e.door_open:
            self.add_error(f"ARRIVE-{floor_s}-{eid}: move while door OPEN")

        if not is_valid_step(e.floor, floor_i):
            self.add_error(f"ARRIVE-{floor_s}-{eid}: invalid move from {int_to_floor(e.floor)}")

        # Determine expected move time based on state
        if e.maint_state == "TEST":
            expected_move_time = MAINT_TEST_SPEED  # 0.2s/floor during TEST
        else:
            expected_move_time = MOVE_TIME_PER_FLOOR  # 0.4s/floor normally

        min_time = e.last_action_time + expected_move_time
        if t < min_time - EPSILON:
            self.add_error(f"ARRIVE-{floor_s}-{eid}: move too fast ({t:.4f} < {min_time:.4f})")

        # NORMAL state: need active_receives / passengers to move,
        # but also allow movement when the maint worker is already inside
        # (e.g. during REP_ACCEPT before MAINT1-BEGIN, elevator heads to F1)
        if e.maint_state == "NORMAL" and not e.active_receives and not e.passengers and not e.maint_worker_inside:
            self.add_error(f"ARRIVE-{floor_s}-{eid}: idle move without unfinished RECEIVE")
        # REP_ACCEPT: elevator may move freely (heading to F1 or finishing existing passengers)
        # No extra error here — the elevator is allowed to maneuver before MAINT1-BEGIN.

        # REPAIR state: no movement allowed
        if e.maint_state == "REPAIR":
            self.add_error(f"ARRIVE-{floor_s}-{eid}: movement forbidden during REPAIR state")

        # TEST state: track the route
        if e.maint_state == "TEST":
            e.test_visits.append(floor_i)

        e.floor = floor_i
        e.last_action_time = t
        self.arrive_count += 1

    # OPEN

    def _handle_open(self, t: float, floor_s: str, eid: int) -> None:
        e = self._get_elevator(eid)
        floor_i = floor_to_int(floor_s)
        if e is None or floor_i is None:
            self.add_error(f"OPEN-{floor_s}-{eid}: invalid floor/elevator")
            return

        if e.door_open:
            self.add_error(f"OPEN-{floor_s}-{eid}: repeated OPEN while already OPEN")
        if e.floor != floor_i:
            self.add_error(f"OPEN-{floor_s}-{eid}: elevator at {int_to_floor(e.floor)}")

        # REPAIR state: no open allowed
        if e.maint_state == "REPAIR":
            self.add_error(f"OPEN-{floor_s}-{eid}: OPEN forbidden during REPAIR state")

        # TEST state: can only open at F1, and only once
        if e.maint_state == "TEST":
            if floor_i != 1:  # F1 = 1
                self.add_error(f"OPEN-{floor_s}-{eid}: TEST state can only OPEN at F1")

        e.door_open = True
        e.open_time = t
        e.last_action_time = t
        self.open_count += 1

    # CLOSE

    def _handle_close(self, t: float, floor_s: str, eid: int) -> None:
        e = self._get_elevator(eid)
        floor_i = floor_to_int(floor_s)
        if e is None or floor_i is None:
            self.add_error(f"CLOSE-{floor_s}-{eid}: invalid floor/elevator")
            return

        if not e.door_open:
            self.add_error(f"CLOSE-{floor_s}-{eid}: CLOSE while door CLOSED")
        if e.floor != floor_i:
            self.add_error(f"CLOSE-{floor_s}-{eid}: elevator at {int_to_floor(e.floor)}")

        # Door open-close minimum duration
        if e.open_time >= 0:
            min_close = e.open_time + DOOR_OPEN_CLOSE_TIME
            if t < min_close - EPSILON:
                self.add_error(
                    f"CLOSE-{floor_s}-{eid}: door open duration too short ({t:.4f} < {min_close:.4f})"
                )

        # Load check (excluding maintenance workers whose weight is unknown)
        load = self._load_of(eid)
        if load > MAX_LOAD:
            self.add_error(f"CLOSE-{floor_s}-{eid}: overload {load}kg > {MAX_LOAD}kg")

        # REPAIR state: no close allowed
        if e.maint_state == "REPAIR":
            self.add_error(f"CLOSE-{floor_s}-{eid}: CLOSE forbidden during REPAIR state")

        e.door_open = False
        e.open_time = -1.0
        e.last_action_time = t
        self.close_count += 1

    # IN

    def _handle_in(self, t: float, pid: int, floor_s: str, eid: int) -> None:
        e = self._get_elevator(eid)
        floor_i = floor_to_int(floor_s)
        if e is None or floor_i is None:
            self.add_error(f"IN-{pid}-{floor_s}-{eid}: invalid floor/elevator")
            return

        # Check if this is a maintenance worker
        maint_worker = self.maint_workers.get(pid)
        if maint_worker is not None:
            self._handle_maint_worker_in(t, maint_worker, floor_s, floor_i, eid, e)
            return

        # Regular passenger
        p = self._get_passenger(pid)
        if p is None:
            return

        if not e.door_open:
            self.add_error(f"IN-{pid}-{floor_s}-{eid}: door not OPEN")
        if e.floor != floor_i:
            self.add_error(f"IN-{pid}-{floor_s}-{eid}: elevator not at floor")
        if p.state != "OUTSIDE":
            self.add_error(f"IN-{pid}-{floor_s}-{eid}: passenger state={p.state}, not OUTSIDE")
        if p.location != floor_i:
            self.add_error(f"IN-{pid}-{floor_s}-{eid}: passenger at {int_to_floor(p.location)}")
        if p.current_receive_eid != eid or pid not in e.active_receives:
            self.add_error(f"IN-{pid}-{floor_s}-{eid}: missing active RECEIVE for this elevator")

        # Cannot enter during REPAIR or TEST states
        if e.maint_state in ("REPAIR", "TEST"):
            self.add_error(f"IN-{pid}-{floor_s}-{eid}: passenger cannot enter during {e.maint_state} state")

        e.passengers.add(pid)
        e.passenger_weights[pid] = p.weight
        p.state = "INSIDE"
        p.location = eid  # type: ignore

    def _handle_maint_worker_in(
        self, t: float, worker: MaintWorkerState,
        floor_s: str, floor_i: int, eid: int, e: ElevatorState,
    ) -> None:
        """Maintenance worker enters elevator — same rules as regular passenger for IN,
        but no RECEIVE needed."""
        if not e.door_open:
            self.add_error(f"IN-{worker.worker_id}-{floor_s}-{eid}: (worker) door not OPEN")
        if e.floor != floor_i:
            self.add_error(f"IN-{worker.worker_id}-{floor_s}-{eid}: (worker) elevator not at floor")
        if worker.state != "OUTSIDE":
            self.add_error(f"IN-{worker.worker_id}-{floor_s}-{eid}: (worker) not OUTSIDE")
        if floor_i != 1:  # Workers enter at F1
            self.add_error(f"IN-{worker.worker_id}-{floor_s}-{eid}: (worker) must enter at F1")
        if eid != worker.elevator_id:
            self.add_error(f"IN-{worker.worker_id}-{floor_s}-{eid}: (worker) wrong elevator (should be {worker.elevator_id})")

        # Worker can only enter in REP_ACCEPT state (after MAINT-ACCEPT, before MAINT1-BEGIN)
        if e.maint_state != "REP_ACCEPT":
            self.add_error(
                f"IN-{worker.worker_id}-{floor_s}-{eid}: (worker) elevator not in REP_ACCEPT state (current: {e.maint_state})"
            )

        # All regular passengers must be out before worker enters
        regular_passengers_inside = [p for p in e.passengers if p not in self.maint_workers]
        if regular_passengers_inside:
            self.add_error(
                f"IN-{worker.worker_id}-{floor_s}-{eid}: (worker) regular passengers still inside: {regular_passengers_inside}"
            )

        worker.state = "INSIDE"
        worker.location = eid
        e.maint_worker_inside = True
        # Worker weight is not tracked (guaranteed < capacity)

    # OUT

    def _handle_out(self, t: float, out_flag: str, pid: int, floor_s: str, eid: int) -> None:
        e = self._get_elevator(eid)
        floor_i = floor_to_int(floor_s)
        if e is None or floor_i is None:
            self.add_error(f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: invalid floor/elevator")
            return

        # Check if this is a maintenance worker
        maint_worker = self.maint_workers.get(pid)
        if maint_worker is not None:
            self._handle_maint_worker_out(t, out_flag, maint_worker, floor_s, floor_i, eid, e)
            return

        # Regular passenger
        p = self._get_passenger(pid)
        if p is None:
            return

        if not e.door_open:
            self.add_error(f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: door not OPEN")
        if e.floor != floor_i:
            self.add_error(f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: elevator not at floor")
        if p.state != "INSIDE":
            self.add_error(f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: passenger state={p.state}, not INSIDE")
        if p.location != eid:
            self.add_error(f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: passenger not in elevator {eid}")
        if pid not in e.passengers:
            self.add_error(f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: passenger not in elevator set")

        # Cannot enter/exit during REPAIR
        if e.maint_state == "REPAIR":
            self.add_error(f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: OUT forbidden during REPAIR state")

        # TEST state: passengers cannot exit (only worker can)
        if e.maint_state == "TEST":
            self.add_error(f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: passenger cannot exit during TEST state")

        if pid in e.passengers:
            e.passengers.remove(pid)
        if pid in e.passenger_weights:
            del e.passenger_weights[pid]

        # End of RECEIVE
        if p.current_receive_eid == eid:
            p.current_receive_eid = None
        if pid in e.active_receives:
            e.active_receives.remove(pid)

        on_target = floor_i == p.destination
        if out_flag == "S" and not on_target:
            self.add_error(
                f"OUT-S-{pid}-{floor_s}-{eid}: floor is not target {int_to_floor(p.destination)}"
            )
        if out_flag == "F" and on_target:
            self.add_error(f"OUT-F-{pid}-{floor_s}-{eid}: floor is already target")

        if on_target:
            p.state = "ARRIVED"
            p.location = floor_i
            p.arrival_time = t
        else:
            p.state = "OUTSIDE"
            p.location = floor_i

    def _handle_maint_worker_out(
        self, t: float, out_flag: str, worker: MaintWorkerState,
        floor_s: str, floor_i: int, eid: int, e: ElevatorState,
    ) -> None:
        """Maintenance worker exits elevator."""
        if not e.door_open:
            self.add_error(f"OUT-{out_flag}-{worker.worker_id}-{floor_s}-{eid}: (worker) door not OPEN")
        if e.floor != floor_i:
            self.add_error(f"OUT-{out_flag}-{worker.worker_id}-{floor_s}-{eid}: (worker) elevator not at floor")
        if worker.state != "INSIDE":
            self.add_error(f"OUT-{out_flag}-{worker.worker_id}-{floor_s}-{eid}: (worker) state={worker.state}")

        # Worker exits at F1 (destination = F1)
        if floor_i != 1:
            self.add_error(f"OUT-{out_flag}-{worker.worker_id}-{floor_s}-{eid}: (worker) must exit at F1")

        # Flag should be S since target is F1
        if out_flag != "S":
            self.add_error(f"OUT-{out_flag}-{worker.worker_id}-{floor_s}-{eid}: (worker) should use OUT-S flag")

        worker.state = "OUT"
        worker.location = floor_i
        e.maint_worker_inside = False

    # MAINT-ACCEPT (output by official package automatically)

    def _handle_maint_accept(self, t: float, eid: int, worker_id: int, target_floor_s: str) -> None:
        e = self._get_elevator(eid)
        if e is None:
            return
        target_floor_i = floor_to_int(target_floor_s)

        # Validate against input
        found = False
        for mreq in self.m_requests.values():
            if mreq.elevator_id == eid and mreq.worker_id == worker_id:
                found = True
                if target_floor_i != mreq.target_floor:
                    self.add_error(
                        f"MAINT-ACCEPT-{eid}-{worker_id}: target mismatch "
                        f"{target_floor_s} vs {int_to_floor(mreq.target_floor)}"
                    )
                break

        if not found:
            self.add_error(f"MAINT-ACCEPT-{eid}-{worker_id}: no matching MAINT input")

        if e.maint_state != "NORMAL":
            self.add_error(f"MAINT-ACCEPT-{eid}: elevator not in NORMAL state (current: {e.maint_state})")

        e.maint_state = "REP_ACCEPT"
        e.maint_worker_id = worker_id
        e.maint_target_floor = target_floor_i
        e.maint_accept_time = t
        self.maint_accepted.add(eid)

    # MAINT1-BEGIN

    def _handle_maint1_begin(self, t: float, eid: int) -> None:
        e = self._get_elevator(eid)
        if e is None:
            return

        if e.maint_state != "REP_ACCEPT":
            self.add_error(f"MAINT1-BEGIN-{eid}: elevator not in REP_ACCEPT state (current: {e.maint_state})")

        if e.door_open:
            self.add_error(f"MAINT1-BEGIN-{eid}: door must be CLOSED")

        if e.floor != 1:  # Must be at F1
            self.add_error(f"MAINT1-BEGIN-{eid}: elevator must be at F1 (current: {int_to_floor(e.floor)})")

        # All regular passengers must be out
        regular_passengers = [p for p in e.passengers if p not in self.maint_workers]
        if regular_passengers:
            self.add_error(f"MAINT1-BEGIN-{eid}: regular passengers still inside: {regular_passengers}")

        # Maintenance worker must be inside
        if not e.maint_worker_inside:
            self.add_error(f"MAINT1-BEGIN-{eid}: maintenance worker not inside elevator")

        # Guidebook: 电梯部件检修开始时(MAINT1-BEGIN)，该电梯此时所有RECEIVE结束
        if e.active_receives:
            for pid in list(e.active_receives):
                p = self.passengers.get(pid)
                if p and p.current_receive_eid == eid:
                    p.current_receive_eid = None
            e.active_receives.clear()

        e.maint_state = "REPAIR"
        e.maint1_begin_time = t

    # MAINT2-BEGIN

    def _handle_maint2_begin(self, t: float, eid: int) -> None:
        e = self._get_elevator(eid)
        if e is None:
            return

        if e.maint_state != "REPAIR":
            self.add_error(f"MAINT2-BEGIN-{eid}: elevator not in REPAIR state (current: {e.maint_state})")

        # Must wait at least T_stop = 1s since MAINT1-BEGIN
        min_time = e.maint1_begin_time + MAINT_STOP_TIME
        if t < min_time - EPSILON:
            self.add_error(
                f"MAINT2-BEGIN-{eid}: repair too short ({t:.4f} < {min_time:.4f}), need >= {MAINT_STOP_TIME}s"
            )

        if e.door_open:
            self.add_error(f"MAINT2-BEGIN-{eid}: door must be CLOSED")

        e.maint_state = "TEST"
        e.maint2_begin_time = t
        e.test_phase = "TO_TARGET"
        e.test_visits = []

    # MAINT-END

    def _handle_maint_end(self, t: float, eid: int) -> None:
        e = self._get_elevator(eid)
        if e is None:
            return

        if e.maint_state != "TEST":
            self.add_error(f"MAINT-END-{eid}: elevator not in TEST state (current: {e.maint_state})")

        if e.door_open:
            self.add_error(f"MAINT-END-{eid}: door must be CLOSED")

        if e.floor != 1:  # Must be at F1
            self.add_error(f"MAINT-END-{eid}: elevator must be at F1 (current: {int_to_floor(e.floor)})")

        # Worker should have exited
        if e.maint_worker_inside:
            self.add_error(f"MAINT-END-{eid}: maintenance worker still inside")

        # No regular passengers should be in
        regular = [p for p in e.passengers if p not in self.maint_workers]
        if regular:
            self.add_error(f"MAINT-END-{eid}: regular passengers inside: {regular}")

        # Validate TEST route: F1 -> target -> F1
        if e.maint_target_floor is not None and e.test_visits:
            target = e.maint_target_floor
            # Build expected route
            expected = build_route(1, target) + build_route(target, 1)
            if e.test_visits != expected:
                self.add_error(
                    f"MAINT-END-{eid}: TEST route mismatch. "
                    f"Expected {[int_to_floor(f) for f in expected]}, "
                    f"got {[int_to_floor(f) for f in e.test_visits]}"
                )

        # Check T_complete constraint
        if e.maint_accept_time >= 0:
            t_complete = t - e.maint_accept_time
            if t_complete > MAINT_COMPLETE_TIMEOUT + EPSILON:
                self.add_error(
                    f"MAINT-END-{eid}: T_complete={t_complete:.4f}s > {MAINT_COMPLETE_TIMEOUT}s"
                )

        # Reset state
        e.maint_state = "NORMAL"
        e.maint_worker_id = None
        e.maint_target_floor = None
        e.maint_accept_time = -1.0
        e.maint1_begin_time = -1.0
        e.maint2_begin_time = -1.0
        e.test_phase = ""
        e.test_visits = []

    # Final checks

    def final_checks(self) -> None:
        for pid, p in self.passengers.items():
            if p.state != "ARRIVED":
                loc = f"elevator {p.location}" if p.state == "INSIDE" else int_to_floor(p.location)
                self.add_error(f"Passenger {pid} not ARRIVED, final state={p.state}, location={loc}")
            if p.current_receive_eid is not None:
                self.add_error(
                    f"Passenger {pid} has unfinished RECEIVE on elevator {p.current_receive_eid}"
                )

        for eid, e in self.elevators.items():
            if e.door_open:
                self.add_error(f"Elevator {eid} is OPEN at the end")
            # Regular passengers should not be trapped
            regular_passengers = [p for p in e.passengers if p not in self.maint_workers]
            if regular_passengers:
                self.add_error(f"Elevator {eid} still has passengers: {sorted(regular_passengers)}")
            if e.maint_state != "NORMAL":
                self.add_error(f"Elevator {eid} finished in {e.maint_state} state, not NORMAL")

        # Check all MAINT requests were processed
        for mreq in self.m_requests.values():
            if mreq.elevator_id not in self.maint_accepted:
                self.add_error(f"MAINT for elevator {mreq.elevator_id} was never accepted")

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


# Helpers

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
    """Build floor-by-floor route from start to end (excluding start, including end).
    Handles the B1-F1 gap correctly."""
    route = []
    current = start
    direction = 1 if end > start else -1

    while current != end:
        next_floor = current + direction
        # Handle the B1-F1 gap: -1 -> 1 or 1 -> -1 (no floor 0)
        if next_floor == 0:
            next_floor += direction
        route.append(next_floor)
        current = next_floor

    return route


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
    try:
        for line in main_file.read_text(encoding="utf-8", errors="replace").splitlines()[:60]:
            m = re.match(r"\s*package\s+([\w.]+)\s*;", line)
            if m:
                package_name = m.group(1)
                break
    except OSError:
        pass
    cls = main_file.stem
    return f"{package_name}.{cls}" if package_name else cls


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
                source_dir = project_dir.joinpath(*rel_parts[:idx + 1])
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
            cmd, check=False, capture_output=True,
            text=True, encoding="utf-8", errors="replace",
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


def discover_projects(co_judge_dir: Path, pattern: str, build_root: Path, classpath: str, compile_timeout: float) -> List[TargetProject]:
    projects: List[TargetProject] = []
    project_errors: List[str] = []
    base = Path(co_judge_dir).resolve()
    if pattern == "src":
        targets = [base]
    elif direct := direct_target_entry(pattern):
        targets = [direct]
    else:
        targets = matching_target_entries(sorted(base.iterdir(), key=lambda p: p.name.lower()), pattern)

    for idx, project_dir in enumerate(targets, start=1):
        try:
            if project_dir.is_file() and project_dir.suffix.lower() == ".jar":
                key = sanitize_key(f"{project_dir.stem}_jar", idx)
                projects.append(TargetProject(
                    key=key,
                    display_name=project_dir.name,
                    project_dir=project_dir.parent,
                    source_dir=project_dir.parent,
                    main_class="<jar>",
                    build_dir=build_root / key,
                    command=["java", "-jar", str(project_dir.resolve())],
                ))
                continue
            source_dir, main_file = choose_source_dir(project_dir)
            main_class = parse_main_class(main_file)
            key = sanitize_key(project_dir.name, idx)
            build_dir = build_root / key

            ok, msg = compile_project(source_dir, build_dir, classpath, compile_timeout)
            if not ok:
                raise RuntimeError(f"compile failed: {msg}")

            cp_items = [str(build_dir)] + ([classpath] if classpath else [])
            command = ["java", "-cp", os.pathsep.join(cp_items), main_class]

            projects.append(TargetProject(
                key=key, display_name=project_dir.name,
                project_dir=project_dir, source_dir=source_dir,
                main_class=main_class, build_dir=build_dir, command=command,
            ))
        except Exception as exc:
            project_errors.append(f"{project_dir.name}: {exc}")
            continue

    if not projects:
        details = "; ".join(project_errors[:5]) if project_errors else "no matched directories"
        raise RuntimeError(f"未发现可用目标项目，详情: {details}")

    if project_errors:
        print("[WARN] skipped invalid targets:", file=sys.stderr)
        for err in project_errors:
            print(f"  - {err}", file=sys.stderr)

    return projects


# Input parsing

def parse_input_requests(
    input_text: str,
    mutual_mode: bool = False,
) -> Tuple[Dict[int, PassengerRequest], Dict[int, MaintRequestInput], List[str]]:
    """Parse HW6 input: passengers + MAINT requests.
    Returns (passenger_dict, maint_dict, errors).
    """
    passengers: Dict[int, PassengerRequest] = {}
    maints: Dict[int, MaintRequestInput] = {}
    errors: List[str] = []
    last_ts = -1.0
    first_ts: Optional[float] = None
    all_ids: Set[int] = set()
    last_maint_ts: Dict[int, float] = {}
    maint_count_per_eid: Dict[int, int] = {}
    total_count = 0

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

        # Try passenger pattern
        m = RE_INPUT_PASSENGER.match(line)
        if m:
            ts_s, pid_s, wei_s, frm_s, to_s = m.groups()
            ts = float(ts_s)
            pid = int(pid_s)
            wei = int(wei_s)
            frm = floor_to_int(frm_s)
            to = floor_to_int(to_s)

            if frm is None or to is None:
                errors.append(f"input line {idx} invalid floor: {line}")
                continue
            if frm == to:
                errors.append(f"input line {idx} has same FROM/TO")
            if pid <= 0:
                errors.append(f"input line {idx} invalid pid")
            if pid in all_ids:
                errors.append(f"input line {idx} duplicate id {pid}")
            if wei < 50 or wei > 100:
                errors.append(f"input line {idx} invalid weight {wei}")
            if ts < last_ts - EPSILON:
                errors.append(f"input timestamp decreases at line {idx}")
            if mutual_mode and not has_one_decimal(ts_s):
                errors.append(f"input line {idx} timestamp must keep one decimal")

            last_ts = max(last_ts, ts)
            if first_ts is None:
                first_ts = ts
            all_ids.add(pid)

            passengers[pid] = PassengerRequest(
                request_time=ts, pid=pid, weight=wei,
                from_floor=frm, to_floor=to,
            )
            continue

        # Try MAINT pattern
        m = RE_INPUT_MAINT.match(line)
        if m:
            ts_s, eid_s, wid_s, target_s = m.groups()
            ts = float(ts_s)
            eid = int(eid_s)
            wid = int(wid_s)
            target_i = floor_to_int(target_s)

            if target_i is None:
                errors.append(f"input line {idx} invalid MAINT target floor: {line}")
                continue
            if target_i not in MAINT_TARGET_FLOORS:
                errors.append(f"input line {idx} MAINT target floor not in {{B2, B1, F2, F3}}")
            if eid < 1 or eid > NUM_ELEVATORS:
                errors.append(f"input line {idx} invalid MAINT elevator id {eid}")
            if wid <= 0:
                errors.append(f"input line {idx} invalid worker id")
            if wid in all_ids:
                errors.append(f"input line {idx} duplicate id {wid}")
            if eid in last_maint_ts and ts < last_maint_ts[eid] + 8.0 - EPSILON:
                errors.append(f"input line {idx} elevator {eid} MAINT interval < 8s")
            if ts < last_ts - EPSILON:
                errors.append(f"input timestamp decreases at line {idx}")
            if mutual_mode and not has_one_decimal(ts_s):
                errors.append(f"input line {idx} timestamp must keep one decimal")
            if mutual_mode:
                maint_count_per_eid[eid] = maint_count_per_eid.get(eid, 0) + 1
                if maint_count_per_eid[eid] > 1:
                    errors.append(f"input line {idx} elevator {eid} has more than one MAINT")

            last_ts = max(last_ts, ts)
            if first_ts is None:
                first_ts = ts
            all_ids.add(wid)
            last_maint_ts[eid] = ts

            maints[wid] = MaintRequestInput(
                request_time=ts, elevator_id=eid,
                worker_id=wid, target_floor=target_i,
            )
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

    return passengers, maints, errors


# Schedule builder

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


# Java runner

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
            start_feed = time.monotonic()
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


# Normalize + diff

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


# Target case runner

def run_target_case(
    target: TargetProject,
    case_name: str,
    input_text: str,
    passengers: Dict[int, PassengerRequest],
    maints: Dict[int, MaintRequestInput],
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


# Report writers

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
    lines.append("# HW6 Consensus Judge Report")
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


# CLI entry

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HW6 consensus judge")
    parser.add_argument("--mode", choices=["self", "mutual"], default="mutual", help="input constraint mode")
    parser.add_argument("--co-judge-dir", default="..", help="co_judge root directory")
    parser.add_argument("--target-pattern", default="互测代码_*", help="target glob/regex (directory or .jar)")
    parser.add_argument("--official-jar", default="lib/elevator2-2026.jar", help="official package jar")
    parser.add_argument("--build-dir", default=".build_targets", help="compiled classes directory")

    parser.add_argument("--generate", action="store_true", help="generate data before running")
    parser.add_argument("--generator", default="data_generator_hw6.py", help="generator script path")
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
        case_files = case_files[:args.max_cases]

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
        passengers, maints, input_errors = parse_input_requests(
            input_text,
            mutual_mode=(args.mode == "mutual"),
        )
        if input_errors:
            fake_targets: Dict[str, TargetRunResult] = {}
            for p_proj in projects:
                fake_targets[p_proj.key] = TargetRunResult(
                    status="INPUT_ERROR", stdout="", stderr="",
                    elapsed_sec=0.0, sim_time=0.0, power=0.0, avg_time=0.0,
                    errors=input_errors, normalized_events=[], raw_output_path="",
                )
            case_summary = CaseSummary(
                case_name=case_name, all_correct=False,
                all_consistent=False, effective=False, targets=fake_targets,
            )
            summaries.append(case_summary)
            write_problem_case(case_summary, input_text, problem_dir, projects)
            print("    -> INPUT_ERROR")
            continue

        per_target: Dict[str, TargetRunResult] = {}
        for p_proj in projects:
            result = run_target_case(
                target=p_proj, case_name=case_name,
                input_text=input_text,
                passengers=passengers, maints=maints,
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
            all_consistent = all(per_target[p_proj.key].normalized_events == baseline for p_proj in projects)

        effective = all_correct and all_consistent
        case_summary = CaseSummary(
            case_name=case_name, all_correct=all_correct,
            all_consistent=all_consistent, effective=effective,
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
