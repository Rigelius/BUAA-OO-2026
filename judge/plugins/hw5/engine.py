#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HW5 custom judge (WEI version).

Core flow:
1. Optional data generation.
2. Discover jars and testcases.
3. Run each jar with each testcase under timeout control.
4. Validate output legality with a rule-based state machine.
5. Save raw outputs and per-jar reports.
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
NUM_ELEVATORS = 6
MOVE_TIME_PER_FLOOR = 0.4
DOOR_OPEN_CLOSE_TIME = 0.4
MAX_LOAD = 400

DEFAULT_SOFT_TIMEOUT = 120.0
DEFAULT_HARD_TIMEOUT = 150.0
POLL_INTERVAL = 0.1

POWER_OPEN = 0.1
POWER_CLOSE = 0.1
POWER_MOVE = 0.4

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

RE_INPUT = re.compile(
    r"^\[\s*([\d.]+)\s*\](\d+)-WEI-(\d+)-FROM-([BF]\d+)-TO-([BF]\d+)-BY-(\d+)$"
)

RE_RECEIVE = re.compile(r"^\[\s*([\d.]+)\s*\]RECEIVE-(\d+)-(\d+)$")
RE_ARRIVE = re.compile(r"^\[\s*([\d.]+)\s*\]ARRIVE-([BF]\d+)-(\d+)$")
RE_OPEN = re.compile(r"^\[\s*([\d.]+)\s*\]OPEN-([BF]\d+)-(\d+)$")
RE_CLOSE = re.compile(r"^\[\s*([\d.]+)\s*\]CLOSE-([BF]\d+)-(\d+)$")
RE_IN = re.compile(r"^\[\s*([\d.]+)\s*\]IN-(\d+)-([BF]\d+)-(\d+)$")
RE_OUT = re.compile(r"^\[\s*([\d.]+)\s*\]OUT-([SF])-(\d+)-([BF]\d+)-(\d+)$")
RE_TIMESTAMP = re.compile(r"^\[\s*([\d.]+)\s*\]")


@dataclass
class Request:
    request_time: float
    pid: int
    weight: int
    from_floor: int
    to_floor: int
    by_elevator: int


@dataclass
class PassengerState:
    pid: int
    weight: int
    destination: int
    assigned_elevator: int
    request_time: float
    state: str = "OUTSIDE"  # OUTSIDE / INSIDE / ARRIVED
    location: int = 0
    current_receive_eid: Optional[int] = None
    arrival_time: Optional[float] = None


@dataclass
class ElevatorState:
    eid: int
    floor: int = 1
    door_open: bool = False
    open_time: float = -1.0
    last_action_time: float = 0.0
    passengers: Set[int] = field(default_factory=set)
    active_receives: Set[int] = field(default_factory=set)


@dataclass
class CaseResult:
    data_file: str
    status: str
    sim_time: float
    exec_time: float
    power: float
    avg_time: float
    errors: List[str]


@dataclass
class RunnerTarget:
    name: str
    display: str
    command: List[str]
    input_mode: str = "raw"


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


def clear_directory(dir_path: str) -> None:
    if not os.path.isdir(dir_path):
        return
    for item in os.listdir(dir_path):
        target = os.path.join(dir_path, item)
        try:
            if os.path.isfile(target) or os.path.islink(target):
                os.unlink(target)
            elif os.path.isdir(target):
                shutil.rmtree(target)
        except OSError as e:
            print(f"Warning: failed to remove '{target}': {e}", file=sys.stderr)


def find_files(directory: str, extension: str) -> List[str]:
    if not os.path.isdir(directory):
        return []
    return sorted(
        [
            f
            for f in os.listdir(directory)
            if f.endswith(extension) and os.path.isfile(os.path.join(directory, f))
        ]
    )


def split_classpath(raw: str) -> List[str]:
    if not raw:
        return []
    return [p for p in raw.split(os.pathsep) if p]


def sanitize_target_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_") or "target"


def strip_timestamp_prefix(line: str) -> str:
    m = re.match(r"^\[\s*[\d.]+\s*\](.*)$", line)
    return m.group(1) if m else line


def prepare_input_for_target(raw_input: str, input_mode: str) -> str:
    if input_mode == "strip_timestamp":
        lines = [strip_timestamp_prefix(line) for line in raw_input.splitlines()]
        return "\n".join(lines) + ("\n" if raw_input.endswith("\n") else "")
    return raw_input


def build_timed_input_schedule(
    raw_input: str,
    strip_timestamp: bool,
) -> List[Tuple[float, str]]:
    schedule: List[Tuple[float, str]] = []
    for raw_line in raw_input.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = re.match(r"^\[\s*([\d.]+)\s*\](.*)$", line)
        if m:
            ts = float(m.group(1))
            payload = m.group(2) if strip_timestamp else line
            schedule.append((ts, payload + "\n"))
        else:
            # Fallback for malformed lines: feed immediately.
            schedule.append((0.0, (strip_timestamp_prefix(line) if strip_timestamp else line) + "\n"))
    return schedule


def parse_input_requests(input_text: str) -> Tuple[Dict[int, Request], List[str]]:
    errors: List[str] = []
    requests: Dict[int, Request] = {}
    last_ts = -1.0

    for idx, raw_line in enumerate(input_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        match = RE_INPUT.match(line)
        if not match:
            errors.append(f"Input line {idx} malformed: {line}")
            continue

        ts_s, pid_s, wei_s, frm_s, to_s, by_s = match.groups()
        try:
            ts = float(ts_s)
            pid = int(pid_s)
            wei = int(wei_s)
            frm = floor_to_int(frm_s)
            to = floor_to_int(to_s)
            by = int(by_s)
        except ValueError:
            errors.append(f"Input line {idx} has invalid numeric field: {line}")
            continue

        if frm is None or to is None:
            errors.append(f"Input line {idx} has invalid floor: {line}")
            continue
        if frm == to:
            errors.append(f"Input line {idx} has same FROM/TO: {line}")
        if pid <= 0:
            errors.append(f"Input line {idx} has invalid pid <= 0: {line}")
        if pid in requests:
            errors.append(f"Input line {idx} has duplicate pid {pid}: {line}")
        if wei < 50 or wei > 100:
            errors.append(f"Input line {idx} has invalid weight {wei}: {line}")
        if by < 1 or by > NUM_ELEVATORS:
            errors.append(f"Input line {idx} has invalid elevator id {by}: {line}")
        if ts < 0:
            errors.append(f"Input line {idx} has negative timestamp {ts}: {line}")
        if ts < last_ts - EPSILON:
            errors.append(
                f"Input timestamp decreases at line {idx}: {ts:.1f} < {last_ts:.1f}"
            )
        last_ts = max(last_ts, ts)

        requests[pid] = Request(
            request_time=ts,
            pid=pid,
            weight=wei,
            from_floor=frm,
            to_floor=to,
            by_elevator=by,
        )

    if not requests:
        errors.append("Input contains no valid request")
    return requests, errors


class Validator:
    def __init__(self, requests: Dict[int, Request]) -> None:
        self.errors: List[str] = []
        self.requests = requests
        self.last_timestamp = 0.0

        self.arrive_count = 0
        self.open_count = 0
        self.close_count = 0

        self.elevators: Dict[int, ElevatorState] = {
            eid: ElevatorState(eid=eid, floor=1) for eid in range(1, NUM_ELEVATORS + 1)
        }
        self.passengers: Dict[int, PassengerState] = {}
        for req in requests.values():
            self.passengers[req.pid] = PassengerState(
                pid=req.pid,
                weight=req.weight,
                destination=req.to_floor,
                assigned_elevator=req.by_elevator,
                request_time=req.request_time,
                state="OUTSIDE",
                location=req.from_floor,
                current_receive_eid=None,
                arrival_time=None,
            )

    def add_error(self, message: str) -> None:
        self.errors.append(f"[t~{self.last_timestamp:.4f}] {message}")

    def _parse_time(self, line: str) -> Optional[float]:
        match = RE_TIMESTAMP.match(line)
        if not match:
            self.add_error(f"Malformed line without timestamp: {line}")
            return None
        try:
            return float(match.group(1))
        except ValueError:
            self.add_error(f"Invalid timestamp value: {line}")
            return None

    def _advance_time(self, t: float) -> None:
        if t < self.last_timestamp - EPSILON:
            self.add_error(
                f"Timestamp decreases: {t:.4f} < {self.last_timestamp:.4f}"
            )
        self.last_timestamp = max(self.last_timestamp, t)

    def validate_line(self, line: str) -> None:
        text = line.strip()
        if not text:
            return
        if "[LOG]" in text:
            return

        t = self._parse_time(text)
        if t is None:
            return
        self._advance_time(t)

        m = RE_RECEIVE.match(text)
        if m:
            _, pid_s, eid_s = m.groups()
            self._handle_receive(int(pid_s), int(eid_s))
            return

        m = RE_ARRIVE.match(text)
        if m:
            _, floor_s, eid_s = m.groups()
            self._handle_arrive(t, floor_s, int(eid_s))
            return

        m = RE_OPEN.match(text)
        if m:
            _, floor_s, eid_s = m.groups()
            self._handle_open(t, floor_s, int(eid_s))
            return

        m = RE_CLOSE.match(text)
        if m:
            _, floor_s, eid_s = m.groups()
            self._handle_close(t, floor_s, int(eid_s))
            return

        m = RE_IN.match(text)
        if m:
            _, pid_s, floor_s, eid_s = m.groups()
            self._handle_in(int(pid_s), floor_s, int(eid_s))
            return

        m = RE_OUT.match(text)
        if m:
            _, out_flag, pid_s, floor_s, eid_s = m.groups()
            self._handle_out(t, out_flag, int(pid_s), floor_s, int(eid_s))
            return

        self.add_error(f"Unrecognized output format: {text}")

    def _load_of(self, eid: int) -> int:
        e = self.elevators[eid]
        total = 0
        for pid in e.passengers:
            p = self.passengers.get(pid)
            if p is not None:
                total += p.weight
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

    def _handle_receive(self, pid: int, eid: int) -> None:
        p = self._get_passenger(pid)
        e = self._get_elevator(eid)
        if p is None or e is None:
            return

        if p.assigned_elevator != eid:
            self.add_error(
                f"RECEIVE-{pid}-{eid}: assigned elevator is {p.assigned_elevator}"
            )
        if p.state == "ARRIVED":
            self.add_error(f"RECEIVE-{pid}-{eid}: passenger already ARRIVED")
        if p.state != "OUTSIDE":
            self.add_error(f"RECEIVE-{pid}-{eid}: passenger not OUTSIDE (state={p.state})")
        if p.current_receive_eid is not None:
            self.add_error(
                f"RECEIVE-{pid}-{eid}: previous RECEIVE not ended (eid={p.current_receive_eid})"
            )

        # Keep state moving forward even after reporting errors.
        p.current_receive_eid = eid
        e.active_receives.add(pid)

    def _handle_arrive(self, t: float, floor_s: str, eid: int) -> None:
        e = self._get_elevator(eid)
        floor_i = floor_to_int(floor_s)
        if e is None or floor_i is None:
            self.add_error(f"ARRIVE-{floor_s}-{eid}: invalid floor/elevator")
            return

        if e.door_open:
            self.add_error(f"ARRIVE-{floor_s}-{eid}: move while door OPEN")
        if not e.active_receives:
            self.add_error(f"ARRIVE-{floor_s}-{eid}: move without unfinished RECEIVE")
        if not is_valid_step(e.floor, floor_i):
            self.add_error(
                f"ARRIVE-{floor_s}-{eid}: invalid move from {int_to_floor(e.floor)}"
            )

        min_time = e.last_action_time + MOVE_TIME_PER_FLOOR
        if t < min_time - EPSILON:
            self.add_error(
                f"ARRIVE-{floor_s}-{eid}: move too fast ({t:.4f} < {min_time:.4f})"
            )

        e.floor = floor_i
        e.last_action_time = t
        self.arrive_count += 1

    def _handle_open(self, t: float, floor_s: str, eid: int) -> None:
        e = self._get_elevator(eid)
        floor_i = floor_to_int(floor_s)
        if e is None or floor_i is None:
            self.add_error(f"OPEN-{floor_s}-{eid}: invalid floor/elevator")
            return

        if e.door_open:
            self.add_error(f"OPEN-{floor_s}-{eid}: repeated OPEN while already OPEN")
        if e.floor != floor_i:
            self.add_error(
                f"OPEN-{floor_s}-{eid}: elevator at {int_to_floor(e.floor)}"
            )

        e.door_open = True
        e.open_time = t
        e.last_action_time = t
        self.open_count += 1

    def _handle_close(self, t: float, floor_s: str, eid: int) -> None:
        e = self._get_elevator(eid)
        floor_i = floor_to_int(floor_s)
        if e is None or floor_i is None:
            self.add_error(f"CLOSE-{floor_s}-{eid}: invalid floor/elevator")
            return

        if not e.door_open:
            self.add_error(f"CLOSE-{floor_s}-{eid}: CLOSE while door CLOSED")
        if e.floor != floor_i:
            self.add_error(
                f"CLOSE-{floor_s}-{eid}: elevator at {int_to_floor(e.floor)}"
            )
        if e.open_time >= 0:
            min_close = e.open_time + DOOR_OPEN_CLOSE_TIME
            if t < min_close - EPSILON:
                self.add_error(
                    f"CLOSE-{floor_s}-{eid}: door open duration too short "
                    f"({t:.4f} < {min_close:.4f})"
                )
        load = self._load_of(eid)
        if load > MAX_LOAD:
            self.add_error(
                f"CLOSE-{floor_s}-{eid}: overload {load}kg > {MAX_LOAD}kg"
            )

        e.door_open = False
        e.open_time = -1.0
        e.last_action_time = t
        self.close_count += 1

    def _handle_in(self, pid: int, floor_s: str, eid: int) -> None:
        p = self._get_passenger(pid)
        e = self._get_elevator(eid)
        floor_i = floor_to_int(floor_s)
        if p is None or e is None or floor_i is None:
            self.add_error(f"IN-{pid}-{floor_s}-{eid}: invalid pid/floor/elevator")
            return

        if p.assigned_elevator != eid:
            self.add_error(
                f"IN-{pid}-{floor_s}-{eid}: assigned elevator is {p.assigned_elevator}"
            )
        if not e.door_open:
            self.add_error(f"IN-{pid}-{floor_s}-{eid}: door not OPEN")
        if e.floor != floor_i:
            self.add_error(f"IN-{pid}-{floor_s}-{eid}: elevator not at floor")
        if p.state != "OUTSIDE":
            self.add_error(f"IN-{pid}-{floor_s}-{eid}: passenger state={p.state}, not OUTSIDE")
        if p.location != floor_i:
            self.add_error(
                f"IN-{pid}-{floor_s}-{eid}: passenger at {int_to_floor(p.location)}"
            )
        if p.current_receive_eid != eid or pid not in e.active_receives:
            self.add_error(f"IN-{pid}-{floor_s}-{eid}: missing active RECEIVE")

        e.passengers.add(pid)
        p.state = "INSIDE"
        p.location = eid

    def _handle_out(self, t: float, out_flag: str, pid: int, floor_s: str, eid: int) -> None:
        p = self._get_passenger(pid)
        e = self._get_elevator(eid)
        floor_i = floor_to_int(floor_s)
        if p is None or e is None or floor_i is None:
            self.add_error(f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: invalid pid/floor/elevator")
            return

        if p.assigned_elevator != eid:
            self.add_error(
                f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: assigned elevator is {p.assigned_elevator}"
            )
        if not e.door_open:
            self.add_error(f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: door not OPEN")
        if e.floor != floor_i:
            self.add_error(f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: elevator not at floor")
        if p.state != "INSIDE":
            self.add_error(
                f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: passenger state={p.state}, not INSIDE"
            )
        if p.location != eid:
            self.add_error(
                f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: passenger not in elevator {eid}"
            )
        if pid not in e.passengers:
            self.add_error(
                f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: passenger not in elevator set"
            )

        if pid in e.passengers:
            e.passengers.remove(pid)

        # A RECEIVE ends when passenger gets out (target floor or middle floor).
        if p.current_receive_eid != eid:
            self.add_error(
                f"OUT-{out_flag}-{pid}-{floor_s}-{eid}: no matching unfinished RECEIVE"
            )
        p.current_receive_eid = None
        if pid in e.active_receives:
            e.active_receives.remove(pid)

        on_target = floor_i == p.destination
        if out_flag == "S" and not on_target:
            self.add_error(
                f"OUT-S-{pid}-{floor_s}-{eid}: floor is not target {int_to_floor(p.destination)}"
            )
        if out_flag == "F" and on_target:
            self.add_error(
                f"OUT-F-{pid}-{floor_s}-{eid}: floor is already target {int_to_floor(p.destination)}"
            )

        if on_target:
            p.state = "ARRIVED"
            p.location = floor_i
            p.arrival_time = t
        else:
            p.state = "OUTSIDE"
            p.location = floor_i

    def final_checks(self) -> None:
        for pid, p in self.passengers.items():
            if p.state != "ARRIVED":
                loc = (
                    f"elevator {p.location}" if p.state == "INSIDE" else int_to_floor(p.location)
                )
                self.add_error(
                    f"Passenger {pid} not ARRIVED, final state={p.state}, location={loc}"
                )
            if p.current_receive_eid is not None:
                self.add_error(
                    f"Passenger {pid} has unfinished RECEIVE on elevator {p.current_receive_eid}"
                )

        for eid, e in self.elevators.items():
            if e.door_open:
                self.add_error(f"Elevator {eid} is OPEN at the end")
            if e.passengers:
                self.add_error(
                    f"Elevator {eid} still has passengers: {sorted(e.passengers)}"
                )
            if e.active_receives:
                self.add_error(
                    f"Elevator {eid} still has unfinished RECEIVEs: {sorted(e.active_receives)}"
                )

    def power_consumption(self) -> float:
        return (
            self.arrive_count * POWER_MOVE
            + self.open_count * POWER_OPEN
            + self.close_count * POWER_CLOSE
        )

    def average_completion_time(self) -> float:
        total = 0.0
        count = 0
        for p in self.passengers.values():
            if p.arrival_time is None:
                continue
            total += p.arrival_time - p.request_time
            count += 1
        return total / count if count else 0.0


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
    input_text: str,
    soft_timeout: float,
    hard_timeout: float,
    input_schedule: Optional[List[Tuple[float, str]]] = None,
) -> Tuple[str, str, float, Optional[str]]:
    """Returns (stdout, stderr, exec_time, status_code).

    status_code values:
    - None: normal exit code 0
    - TLE: soft timeout exceeded
    - KILLED: hard timeout exceeded
    - EXEC_ERROR: process exited non-zero or subprocess failure
    - JAVA_NOT_FOUND: java command unavailable
    """

    start = time.monotonic()
    stdout_chunks: List[str] = []
    stderr_chunks: List[str] = []
    out_lock = Lock()
    err_lock = Lock()

    process = None
    out_thread = None
    err_thread = None
    input_thread = None
    status_code: Optional[str] = None
    tle_marked = False

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

        out_thread = Thread(
            target=_stream_reader,
            args=(process.stdout, stdout_chunks, out_lock),
            daemon=True,
        )
        err_thread = Thread(
            target=_stream_reader,
            args=(process.stderr, stderr_chunks, err_lock),
            daemon=True,
        )
        out_thread.start()
        err_thread.start()

        try:
            if input_schedule is None:
                if input_text:
                    process.stdin.write(input_text)
                process.stdin.close()
            else:
                def _timed_feeder() -> None:
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
                        # Process exited early; let process status decide final result.
                        pass
                    except Exception:
                        pass
                    finally:
                        try:
                            process.stdin.close()
                        except Exception:
                            pass

                input_thread = Thread(target=_timed_feeder, daemon=True)
                input_thread.start()
        except Exception:
            status_code = "EXEC_ERROR"

        process_ended = False
        while status_code != "EXEC_ERROR":
            elapsed = time.monotonic() - start
            if elapsed > hard_timeout:
                status_code = "KILLED"
                try:
                    process.kill()
                except Exception:
                    pass
                break

            code = process.poll()
            if code is not None:
                process_ended = True
                if code != 0:
                    status_code = "EXEC_ERROR"
                elif tle_marked:
                    status_code = "TLE"
                else:
                    status_code = None
                break

            if (not tle_marked) and elapsed > soft_timeout:
                tle_marked = True
                status_code = "TLE"

            time.sleep(POLL_INTERVAL)

        if (not process_ended) and process.poll() is None:
            try:
                process.wait(timeout=max(0.1, hard_timeout - (time.monotonic() - start) + 2.0))
            except subprocess.TimeoutExpired:
                status_code = "KILLED"
                try:
                    process.kill()
                except Exception:
                    pass

        if out_thread is not None:
            out_thread.join(timeout=5.0)
        if err_thread is not None:
            err_thread.join(timeout=5.0)
        if input_thread is not None:
            input_thread.join(timeout=1.0)

        with out_lock:
            stdout_text = "".join(stdout_chunks)
        with err_lock:
            stderr_text = "".join(stderr_chunks)

        end = time.monotonic()
        return stdout_text, stderr_text, end - start, status_code

    except FileNotFoundError:
        end = time.monotonic()
        return "", "java command not found", end - start, "JAVA_NOT_FOUND"
    except Exception as e:
        end = time.monotonic()
        return "", f"runner internal error: {e}", end - start, "EXEC_ERROR"
    finally:
        if process is not None and process.poll() is None:
            try:
                process.kill()
                process.wait(timeout=1.0)
            except Exception:
                pass


def run_single_case(
    target: RunnerTarget,
    data_file: str,
    data_dir: str,
    out_dir: str,
    soft_timeout: float,
    hard_timeout: float,
) -> CaseResult:
    errors: List[str] = []
    input_path = os.path.join(data_dir, data_file)

    try:
        with open(input_path, "r", encoding="utf-8", errors="replace") as f:
            input_text = f.read()
    except Exception as e:
        return CaseResult(
            data_file=data_file,
            status="CHECKER_ERROR",
            sim_time=0.0,
            exec_time=0.0,
            power=0.0,
            avg_time=0.0,
            errors=[f"failed to read input: {e}"],
        )

    requests, input_errors = parse_input_requests(input_text)
    if input_errors:
        return CaseResult(
            data_file=data_file,
            status="INPUT_ERROR",
            sim_time=0.0,
            exec_time=0.0,
            power=0.0,
            avg_time=0.0,
            errors=input_errors,
        )

    input_schedule: Optional[List[Tuple[float, str]]] = None
    if target.input_mode == "timed_strip_timestamp":
        runtime_input = ""
        input_schedule = build_timed_input_schedule(input_text, strip_timestamp=True)
    else:
        runtime_input = prepare_input_for_target(input_text, target.input_mode)

    stdout_text, stderr_text, exec_time, run_status = run_java_command(
        command=target.command,
        input_text=runtime_input,
        soft_timeout=soft_timeout,
        hard_timeout=hard_timeout,
        input_schedule=input_schedule,
    )

    os.makedirs(out_dir, exist_ok=True)
    target_base = target.name
    data_base = os.path.splitext(data_file)[0]
    out_path = os.path.join(out_dir, f"{target_base}_{data_base}.txt")
    try:
        with open(out_path, "w", encoding="utf-8", errors="replace") as f:
            f.write(stdout_text)
            if stderr_text:
                f.write("\n\n--- STDERR ---\n")
                f.write(stderr_text)
    except Exception as e:
        errors.append(f"failed to write output file '{out_path}': {e}")

    status = "PASSED"
    if run_status == "JAVA_NOT_FOUND":
        status = "JAVA_ERROR"
    elif run_status == "KILLED":
        status = "TIMEOUT_HARD"
    elif run_status == "TLE":
        status = "TIMEOUT_SOFT"
    elif run_status == "EXEC_ERROR":
        status = "RUNTIME_ERROR"

    if status == "JAVA_ERROR":
        errors.append("java command not found")
        return CaseResult(
            data_file=data_file,
            status=status,
            sim_time=0.0,
            exec_time=exec_time,
            power=0.0,
            avg_time=0.0,
            errors=errors,
        )

    sim_time = 0.0
    power = 0.0
    avg_time = 0.0

    if stdout_text.strip():
        validator = Validator(requests)
        for line in stdout_text.splitlines():
            validator.validate_line(line)
        validator.final_checks()

        sim_time = validator.last_timestamp
        power = validator.power_consumption()
        avg_time = validator.average_completion_time()

        validation_errors = validator.errors
        if validation_errors:
            errors.extend(validation_errors)
            if status == "PASSED":
                status = "WRONG_ANSWER"
    else:
        errors.append("no output")
        if status == "PASSED":
            status = "WRONG_ANSWER"

    if stderr_text.strip() and status in {"PASSED", "WRONG_ANSWER"}:
        errors.append("stderr is non-empty")

    return CaseResult(
        data_file=data_file,
        status=status,
        sim_time=sim_time,
        exec_time=exec_time,
        power=power,
        avg_time=avg_time,
        errors=errors,
    )


def write_report(
    report_dir: str,
    report_key: str,
    report_display: str,
    results: List[CaseResult],
) -> None:
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"{report_key}.report")

    total = len(results)
    passed = sum(1 for r in results if r.status == "PASSED")

    lines = []
    lines.append(f"Report for: {report_display}")
    lines.append(f"Overall: {passed}/{total} passed")
    lines.append("=" * 24)

    for result in results:
        shown_time = result.sim_time if result.status == "PASSED" else result.exec_time
        lines.append(f"{result.data_file}: {result.status} ({shown_time:.2f}s)")
        if result.status == "PASSED":
            lines.append(
                f"    metrics: power={result.power:.2f}, avg_completion={result.avg_time:.2f}s"
            )
        else:
            for msg in result.errors:
                lines.append(f"    - {msg}")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")


def run_generator(script: str, data_dir: str, count: int) -> int:
    if not os.path.isfile(script):
        print(f"Error: generator script '{script}' not found", file=sys.stderr)
        return 1

    os.makedirs(data_dir, exist_ok=True)
    clear_directory(data_dir)
    cmd = [sys.executable, script, "--out", data_dir, "--count", str(count)]
    print("Running generator:", " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    return result.returncode


def discover_jars() -> List[str]:
    jars: List[str] = []
    seen = set()

    for directory in [".", "jars"]:
        if not os.path.isdir(directory):
            continue
        for name in find_files(directory, ".jar"):
            p = os.path.normpath(os.path.join(directory, name))
            if p not in seen:
                seen.add(p)
                jars.append(p)

    jars.sort()
    return jars


def compile_java_sources(
    src_dir: str,
    build_dir: str,
    extra_classpath: str,
    timeout: float,
) -> Tuple[bool, str]:
    if not os.path.isdir(src_dir):
        return False, f"source directory not found: {src_dir}"

    java_files: List[str] = []
    for root, _, files in os.walk(src_dir):
        for name in files:
            if name.endswith(".java"):
                java_files.append(os.path.join(root, name))

    if not java_files:
        return False, f"no .java files found under {src_dir}"

    os.makedirs(build_dir, exist_ok=True)
    clear_directory(build_dir)

    cmd = ["javac", "-encoding", "UTF-8", "-d", build_dir]
    cp_entries = split_classpath(extra_classpath)
    if cp_entries:
        cmd.extend(["-cp", os.pathsep.join(cp_entries)])
    cmd.extend(java_files)

    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError:
        return False, "javac command not found"
    except subprocess.TimeoutExpired:
        return False, f"javac timeout after {timeout:.1f}s"
    except Exception as e:
        return False, f"javac execution error: {e}"

    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        msg_parts = [f"javac failed with exit code {result.returncode}"]
        if stdout:
            msg_parts.append("[stdout]")
            msg_parts.append(stdout)
        if stderr:
            msg_parts.append("[stderr]")
            msg_parts.append(stderr)
        return False, "\n".join(msg_parts)

    return True, "compile success"


def build_source_target(
    main_class: str,
    build_dir: str,
    extra_classpath: str,
) -> RunnerTarget:
    cp_entries = [build_dir] + split_classpath(extra_classpath)
    command = ["java", "-cp", os.pathsep.join(cp_entries), main_class]
    name = sanitize_target_name(f"source_{main_class}")
    return RunnerTarget(
        name=name,
        display=f"source:{main_class}",
        command=command,
        input_mode="timed_strip_timestamp",
    )


def resolve_targets(args: argparse.Namespace) -> Tuple[List[RunnerTarget], Optional[str]]:
    mode = args.mode
    targets: List[RunnerTarget] = []

    if mode in {"jar", "auto"}:
        jars = discover_jars()
        for jar in jars:
            base = os.path.splitext(os.path.basename(jar))[0]
            targets.append(
                RunnerTarget(
                    name=sanitize_target_name(base),
                    display=jar,
                    command=["java", "-jar", jar],
                    input_mode="raw",
                )
            )
        if mode == "jar" and not targets:
            return [], "no .jar found in current directory or ./jars"

    if mode == "auto" and targets:
        return targets, None

    if mode in {"source", "auto"}:
        ok, msg = compile_java_sources(
            src_dir=args.src_dir,
            build_dir=args.build_dir,
            extra_classpath=args.classpath,
            timeout=args.compile_timeout,
        )
        if not ok:
            if not args.classpath:
                msg = (
                    msg
                    + "\nHint: official package classes are missing. "
                    + "Try --classpath <path_to_official_package_jar>."
                )
            return [], msg
        source_target = build_source_target(
            main_class=args.main_class,
            build_dir=args.build_dir,
            extra_classpath=args.classpath,
        )
        return [source_target], None

    return targets, None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HW5 custom judge (WEI)")
    parser.add_argument(
        "--mode",
        choices=["auto", "jar", "source"],
        default="auto",
        help="run mode: auto prefers jar, source compiles and runs main class",
    )
    parser.add_argument("--generate", action="store_true", help="generate new data first")
    parser.add_argument("--count", type=int, default=4, help="extra random case count")
    parser.add_argument("--generator", default="data_generator.py", help="generator script path")
    parser.add_argument("--data-dir", default="data", help="input testcase directory")
    parser.add_argument("--out-dir", default="out", help="raw output directory")
    parser.add_argument("--report-dir", default="report", help="report directory")
    parser.add_argument("--main-class", default="MainClass", help="main class for source mode")
    parser.add_argument(
        "--src-dir",
        default=os.path.normpath(os.path.join("..", "src")),
        help="java source directory for source mode",
    )
    parser.add_argument(
        "--build-dir",
        default=".judge_build",
        help="compiled class output directory for source mode",
    )
    parser.add_argument(
        "--classpath",
        default="",
        help=f"extra classpath entries separated by '{os.pathsep}'",
    )
    parser.add_argument(
        "--compile-timeout",
        type=float,
        default=60.0,
        help="timeout for javac in source mode",
    )
    parser.add_argument("--soft-timeout", type=float, default=DEFAULT_SOFT_TIMEOUT)
    parser.add_argument("--hard-timeout", type=float, default=DEFAULT_HARD_TIMEOUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.hard_timeout <= 0 or args.soft_timeout <= 0:
        print("Error: timeout must be positive", file=sys.stderr)
        return 2
    if args.hard_timeout < args.soft_timeout:
        print("Error: hard-timeout must be >= soft-timeout", file=sys.stderr)
        return 2

    for d in [args.data_dir, args.out_dir, args.report_dir]:
        os.makedirs(d, exist_ok=True)

    if args.generate:
        ret = run_generator(args.generator, args.data_dir, max(0, args.count))
        if ret != 0:
            print("Error: data generation failed", file=sys.stderr)
            return 2

    if args.compile_timeout <= 0:
        print("Error: compile-timeout must be positive", file=sys.stderr)
        return 2

    targets, target_error = resolve_targets(args)
    if target_error:
        print(f"Error: {target_error}", file=sys.stderr)
        return 2
    if not targets:
        print("Error: no runnable target resolved", file=sys.stderr)
        return 2

    data_files = find_files(args.data_dir, ".txt")
    if not data_files:
        print(f"Error: no .txt testcase found in '{args.data_dir}'", file=sys.stderr)
        return 2

    print("Detected targets:")
    for target in targets:
        print(f"  - {target.display}")

    print(f"Detected testcases: {len(data_files)}")

    overall_ok = True
    for target in targets:
        print("=" * 48)
        print(f"Testing target: {target.display}")
        case_results: List[CaseResult] = []

        for i, data_file in enumerate(data_files, start=1):
            print(f"  [{i}/{len(data_files)}] {data_file}")
            result = run_single_case(
                target=target,
                data_file=data_file,
                data_dir=args.data_dir,
                out_dir=args.out_dir,
                soft_timeout=args.soft_timeout,
                hard_timeout=args.hard_timeout,
            )
            case_results.append(result)
            if result.status != "PASSED":
                overall_ok = False
                shown_time = result.exec_time if result.exec_time > 0 else result.sim_time
                print(f"      -> {result.status} ({shown_time:.2f}s)")
                for msg in result.errors[:3]:
                    print(f"         - {msg}")
                if len(result.errors) > 3:
                    print(f"         - ... and {len(result.errors) - 3} more")
            else:
                print(
                    f"      -> PASSED (sim={result.sim_time:.2f}s, power={result.power:.2f}, avg={result.avg_time:.2f}s)"
                )

        write_report(args.report_dir, target.name, target.display, case_results)
        passed = sum(1 for r in case_results if r.status == "PASSED")
        print(f"Summary for {target.display}: {passed}/{len(case_results)} passed")

    print("=" * 48)
    print("All done.")
    return 0 if overall_ok else 1


# hw6/hw14 兼容 shim
#
# Below re-exposes hw5 internals with the same names/signatures used by
# hw6/hw14/hw15 engines, so that ``hw5/gui.py`` can be a near-copy of
# ``hw6/gui.py``. Only additive; nothing above changes.


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


PassengerRequest = Dict[int, Request]
MaintRequestInput = Dict[int, None]


def sanitize_key(text: str, index: int) -> str:
    """hw6 兼容的 target key 生成: 尽量保留可读性 + 唯一性。"""
    safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in text)
    if not safe:
        safe = f"target{index}"
    return f"{safe}_{index}"


def _contains_main(java_file: Path) -> bool:
    try:
        text = java_file.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False
    return re.search(r"public\s+static\s+void\s+main\s*\(", text) is not None


def choose_source_dir(project_dir: Path) -> Tuple[Path, Path]:
    """返回 (source_dir, main_java_file). main_java_file 用来解析 main class 名。"""
    if (project_dir / "src").is_dir():
        src = project_dir / "src"
    else:
        src = project_dir
    for jf in src.rglob("*.java"):
        if _contains_main(jf):
            return src, jf
    # fallback: 找不到 main, 使用 MainClass.java 占位
    for jf in src.rglob("MainClass.java"):
        return src, jf
    # 再退化: 返回第一个 java
    java_files = list(src.rglob("*.java"))
    if java_files:
        return src, java_files[0]
    return src, src / "MainClass.java"


def parse_main_class(main_file: Path) -> str:
    try:
        text = main_file.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return "MainClass"
    m = re.search(r"public\s+class\s+(\w+)", text)
    return m.group(1) if m else "MainClass"


def find_official_src(classpath: str) -> str:
    """hw5 官方包实际是 jar; 直接返回 classpath 字符串, 编译时作为 -cp 使用."""
    return classpath or ""


def compile_project(
    source_dir: Path,
    build_dir: Path,
    classpath: str,
    timeout_sec: float,
) -> Tuple[bool, str]:
    build_dir.mkdir(parents=True, exist_ok=True)
    return compile_java_sources(
        src_dir=str(source_dir),
        build_dir=str(build_dir),
        extra_classpath=classpath,
        timeout=timeout_sec,
    )


def discover_projects(
    co_judge_dir: Path,
    pattern: str,
    build_root: Path,
    classpath: str,
    compile_timeout: float,
) -> List[TargetProject]:
    """按 hw6 语义扫描 co_judge_dir 下满足 pattern 的目录, 依次编译。

    pattern = "src" 表示自评 (直接用 co_judge_dir 作为项目根)。
    """
    cp_sep = os.pathsep
    projects: List[TargetProject] = []
    base = Path(co_judge_dir).resolve()

    if pattern == "src":
        candidates = [("self", base)]
    elif direct := direct_target_entry(pattern):
        candidates = [(direct.name, direct)]
    else:
        candidates = []
        for entry in matching_target_entries(sorted(base.iterdir(), key=lambda p: p.name.lower()), pattern):
            candidates.append((entry.name, entry))

    for idx, (name, project_dir) in enumerate(candidates, start=1):
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
        key = sanitize_key(name, idx)
        build_dir = build_root / key
        ok, msg = compile_project(source_dir, build_dir, classpath, compile_timeout)
        if not ok:
            print(f"[WARN] hw5 discover: skip target {name}: {msg}", file=sys.stderr)
            continue
        main_class = parse_main_class(main_file)
        cp_parts = [str(build_dir)]
        if classpath and Path(classpath).exists():
            cp_parts.append(classpath)
        cmd = ["java", "-cp", cp_sep.join(cp_parts), main_class]
        projects.append(TargetProject(
            key=key,
            display_name=name,
            project_dir=project_dir,
            source_dir=source_dir,
            main_class=main_class,
            build_dir=build_dir,
            command=cmd,
        ))
    return projects


def parse_input_requests_v2(
    input_text: str,
    mutual_mode: bool = False,
) -> Tuple[Dict[int, Request], Dict[int, None], List[str]]:
    """hw6 风格三元组返回。hw5 没有 MAINT/UPDATE, 第二个元素恒为空 dict。"""
    _ = mutual_mode
    requests, errors = parse_input_requests(input_text)
    return requests, {}, errors


def build_input_schedule(input_text: str) -> List[Tuple[float, str]]:
    """Compatibility signature used by the shared GUI worker.

    HW5's official ElevatorInput receives timed requests without the leading
    [timestamp] prefix; the judge delays each line according to that prefix.
    """
    return build_timed_input_schedule(input_text, strip_timestamp=True)


def run_java_command_v2(
    command: List[str],
    input_schedule: List[Tuple[float, str]],
    soft_timeout: float,
    hard_timeout: float,
) -> Tuple[str, str, float, Optional[str]]:
    """hw6 gui 里 run_java_command 是 (stdout, stderr, elapsed, status)."""
    stdout, stderr, elapsed, status = run_java_command(
        command=command,
        input_text="",
        soft_timeout=soft_timeout,
        hard_timeout=hard_timeout,
        input_schedule=input_schedule,
    )
    return stdout, stderr, elapsed, status


def normalize_events(stdout_text: str) -> List[str]:
    """去除时间戳后按行返回, 用于跨目标一致性 diff。"""
    events: List[str] = []
    for line in stdout_text.splitlines():
        line = line.strip()
        if not line:
            continue
        stripped = strip_timestamp_prefix(line)
        events.append(stripped)
    return events


def run_target_case(
    target: TargetProject,
    case_name: str,
    input_text: str,
    passengers: Dict[int, Request],
    maints: Dict[int, None],
    out_dir: Path,
    soft_timeout: float,
    hard_timeout: float,
) -> TargetRunResult:
    _ = maints  # hw5 无 MAINT
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{target.key}__{Path(case_name).stem}.txt"

    schedule = build_input_schedule(input_text)
    stdout_text, stderr_text, elapsed, run_status = run_java_command_v2(
        target.command, schedule, soft_timeout, hard_timeout,
    )
    try:
        with out_path.open("w", encoding="utf-8", errors="replace") as f:
            f.write(stdout_text)
            if stderr_text:
                f.write("\n\n--- STDERR ---\n")
                f.write(stderr_text)
    except Exception:
        pass

    status = "PASSED"
    errors: List[str] = []
    if run_status == "JAVA_NOT_FOUND":
        status, err = "JAVA_ERROR", "java command not found"
        errors.append(err)
    elif run_status == "KILLED":
        status, err = "TIMEOUT_HARD", "hard timeout exceeded"
        errors.append(err)
    elif run_status == "TLE":
        status, err = "TIMEOUT_SOFT", "soft timeout exceeded"
        errors.append(err)
    elif run_status == "EXEC_ERROR":
        status, err = "RUNTIME_ERROR", "runtime error"
        errors.append(err)

    sim_time = 0.0
    power = 0.0
    avg_time = 0.0

    if stdout_text.strip():
        validator = Validator(passengers)
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
        errors.append("no output")
        if status == "PASSED":
            status = "WRONG_ANSWER"

    if stderr_text.strip() and status in {"PASSED", "WRONG_ANSWER"}:
        errors.append("stderr is non-empty")

    return TargetRunResult(
        status=status,
        stdout=stdout_text,
        stderr=stderr_text,
        elapsed_sec=elapsed,
        sim_time=sim_time,
        power=power,
        avg_time=avg_time,
        errors=errors,
        normalized_events=normalize_events(stdout_text),
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
    lines = [
        f"# Problem Case: {case_summary.case_name}", "",
        "## Input", "", "```text", input_text.rstrip(), "```", "",
        "## Targets", "",
        "| target | status | raw_output |",
        "|---|---|---|",
    ]
    for target in target_order:
        rr = case_summary.targets.get(target.key)
        if rr is None:
            lines.append(f"| {target.display_name} | (missing) | |")
            continue
        lines.append(f"| {target.display_name} | {rr.status} | {rr.raw_output_path} |")
        if rr.errors:
            lines.append("")
            lines.append(f"### {target.display_name} errors")
            for err in rr.errors[:20]:
                lines.append(f"- {err}")
            lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary_report(
    report_dir: Path,
    summaries: List[CaseSummary],
    target_order: List[TargetProject],
) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "total_cases": len(summaries),
        "effective_cases": sum(1 for s in summaries if s.effective),
        "targets": [t.display_name for t in target_order],
    }
    (report_dir / "consensus_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# HW5 Judge Summary", "",
        f"- total cases: {len(summaries)}",
        f"- effective cases: {payload['effective_cases']}",
        "",
    ]
    for summary in summaries:
        mark = "PASS" if summary.effective else "FAIL"
        lines.append(f"## {summary.case_name} [{mark}]")
        for target in target_order:
            rr = summary.targets.get(target.key)
            if rr is None:
                lines.append(f"- {target.display_name}: (missing)")
                continue
            lines.append(
                f"- {target.display_name}: {rr.status} ({rr.elapsed_sec:.3f}s)"
            )
            for err in rr.errors[:3]:
                lines.append(f"  - {err}")
        lines.append("")
    (report_dir / "consensus_summary.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted by user", file=sys.stderr)
        raise SystemExit(130)
    except Exception as e:
        print(f"Fatal checker error: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise SystemExit(3)
