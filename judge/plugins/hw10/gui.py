#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HW10 Qt GUI judge."""

from __future__ import annotations

import os
import json
import re
import subprocess
import sys
import time
import threading
import traceback
import math
import hashlib
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import Qt, QObject, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QBrush, QPalette, QLinearGradient, QGradient
from PyQt5.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from judge.core.standard_page import (
    StandardJudgeSpec,
    StandardJudgeWindow,
    build_standard_page,
)
from judge.core.target_matching import direct_target_entry, matching_target_entries

from judge.core.ui import (
    DARK_COLORS,
    BadgeLabel,
    CaseEditorCard,
    CopyButton,
    StatusChip,
    TargetOutputCard,
    build_dark_stylesheet,
)

from .generator import generate_all
from .engine import (
    clear_directory,
    compile_project,
    expected_output,
    parse_main_class,
    sanitize_key,
    choose_source_dir,
)


# Data models

@dataclass
class GuiCase:
    case_id: str
    display_name: str
    source: str
    input_text: str


@dataclass
class RunConfig:
    co_judge_dir: Path
    official_jar: Path
    build_dir: Path
    out_dir: Path
    report_dir: Path
    problem_dir: Path
    target_pattern: str
    soft_timeout: float
    hard_timeout: float
    compile_timeout: float
    max_workers: int
    mutual_mode: bool



@dataclass
class ReferenceCase:
    input_text: str
    expected_lines: List[str]
    input_errors: List[str]


PassengerRequest = ReferenceCase


@dataclass
class MaintRequestInput:
    expected_lines: List[str]


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


def discover_projects(co_judge_dir: Path, pattern: str, build_root: Path,
                      classpath: str, compile_timeout: float) -> List[TargetProject]:
    official_src = Path(classpath).resolve()
    targets: List[Tuple[str, Path]] = []
    base = Path(co_judge_dir).resolve()
    if pattern == "src":
        targets.append(("self", base))
    elif direct := direct_target_entry(pattern):
        targets.append((direct.name, direct))
    else:
        for entry in matching_target_entries(sorted(base.iterdir(), key=lambda p: p.name.lower()), pattern):
            targets.append((entry.name, entry))
    projects: List[TargetProject] = []
    for idx, (name, project_dir) in enumerate(targets, start=1):
        if project_dir.is_file() and project_dir.suffix.lower() == ".jar":
            key = sanitize_key(f"{project_dir.stem}_jar", idx)
            projects.append(TargetProject(
                key=key, display_name=project_dir.name,
                project_dir=project_dir.parent, source_dir=project_dir.parent,
                main_class="<jar>", build_dir=build_root / key,
                command=["java", "-jar", str(project_dir.resolve())],
            ))
            continue
        source_dir, main_file = choose_source_dir(project_dir)
        key = sanitize_key(name, idx)
        build_dir = build_root / key
        ok, msg = compile_project(source_dir, official_src, build_dir, compile_timeout)
        if not ok:
            print(f"[WARN] skipped target {name}: {msg}", file=sys.stderr)
            continue
        main_class = parse_main_class(main_file)
        projects.append(TargetProject(
            key=key, display_name=name, project_dir=project_dir, source_dir=source_dir,
            main_class=main_class, build_dir=build_dir,
            command=["java", "-cp", str(build_dir), main_class],
        ))
    return projects

def parse_input_requests(input_text: str, mutual_mode: bool = False) -> Tuple[ReferenceCase, MaintRequestInput, List[str]]:
    expected, input_errors = expected_output(input_text)
    case = ReferenceCase(input_text, expected, input_errors)
    return case, MaintRequestInput(expected), input_errors


def build_input_schedule(input_text: str) -> List[Tuple[float, str]]:
    return [(0.0, line + "\n") for line in input_text.splitlines() if line.strip()]


def run_java_command(command: List[str], input_schedule: List[Tuple[float, str]],
                     soft_timeout: float, hard_timeout: float) -> Tuple[str, str, float, Optional[str]]:
    input_text = "".join(payload for _, payload in input_schedule)
    start = time.monotonic()
    try:
        proc = subprocess.run(command, input=input_text, capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=hard_timeout)
    except FileNotFoundError:
        return "", "java command not found", time.monotonic() - start, "JAVA_NOT_FOUND"
    except subprocess.TimeoutExpired as exc:
        return exc.stdout or "", exc.stderr or "", time.monotonic() - start, "KILLED"
    except Exception as exc:
        return "", f"runner error: {exc}", time.monotonic() - start, "EXEC_ERROR"
    elapsed = time.monotonic() - start
    status = "EXEC_ERROR" if proc.returncode != 0 else ("TLE" if elapsed > soft_timeout else None)
    return proc.stdout, proc.stderr, elapsed, status


def normalize_events(stdout_text: str) -> List[str]:
    return [line.strip() for line in stdout_text.splitlines() if line.strip()]


class Validator:
    def __init__(self, reference: ReferenceCase, _unused: MaintRequestInput = None) -> None:
        self.reference = reference
        self.actual: List[str] = []
        self.errors: List[str] = []
        self.last_timestamp = 0.0

    def validate_line(self, line: str) -> None:
        stripped = line.strip()
        if stripped:
            self.actual.append(stripped)

    def final_checks(self) -> None:
        expected = self.reference.expected_lines
        actual = self.actual
        if actual == expected:
            return
        n = min(len(actual), len(expected))
        for i in range(n):
            if actual[i] != expected[i]:
                self.errors.append(f"line {i + 1}: expected '{expected[i]}', got '{actual[i]}'")
                break
        if len(actual) != len(expected):
            self.errors.append(f"line count mismatch: expected {len(expected)}, got {len(actual)}")

    def power_consumption(self) -> float:
        return float(len(self.actual))

    def average_completion_time(self) -> float:
        return 0.0


def run_target_case(target: TargetProject, case_name: str, input_text: str,
                    passengers: ReferenceCase, maints: MaintRequestInput,
                    out_dir: Path, soft_timeout: float, hard_timeout: float) -> TargetRunResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{target.key}__{Path(case_name).stem}.txt"
    stdout_text, stderr_text, elapsed, run_status = run_java_command(
        target.command, build_input_schedule(input_text), soft_timeout, hard_timeout)
    out_path.write_text(stdout_text, encoding="utf-8", errors="replace")
    status = "PASSED"
    errors: List[str] = []
    if run_status == "JAVA_NOT_FOUND":
        status = "JAVA_ERROR"; errors.append("java command not found")
    elif run_status == "KILLED":
        status = "TIMEOUT_HARD"; errors.append("hard timeout exceeded")
    elif run_status == "TLE":
        status = "TIMEOUT_SOFT"; errors.append("soft timeout exceeded")
    elif run_status == "EXEC_ERROR":
        status = "RUNTIME_ERROR"; errors.append("runtime error")
    validator = Validator(passengers, maints)
    for line in stdout_text.splitlines():
        validator.validate_line(line)
    validator.final_checks()
    if validator.errors and status == "PASSED":
        status = "WRONG_ANSWER"
    errors.extend(validator.errors)
    return TargetRunResult(status, stdout_text, stderr_text, elapsed, 0.0,
                           float(len(stdout_text)), 0.0, errors,
                           normalize_events(stdout_text), str(out_path))


def write_problem_case(case_summary: CaseSummary, input_text: str, problem_dir: Path,
                       target_order: List[TargetProject]) -> None:
    problem_dir.mkdir(parents=True, exist_ok=True)
    path = problem_dir / f"{Path(case_summary.case_name).stem}.md"
    lines = [f"# Problem Case: {case_summary.case_name}", "", "## Input", "",
             "```text", input_text.rstrip(), "```", "", "## Targets", "",
             "| target | status | raw_output |", "|---|---|---|"]
    for target in target_order:
        rr = case_summary.targets[target.key]
        lines.append(f"| {target.display_name} | {rr.status} | {rr.raw_output_path} |")
        if rr.errors:
            lines.append("")
            lines.append(f"### {target.display_name} errors")
            for err in rr.errors[:20]:
                lines.append(f"- {err}")
            lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary_report(report_dir: Path, summaries: List[CaseSummary],
                         target_order: List[TargetProject]) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = {"total_cases": len(summaries),
               "effective_cases": sum(1 for s in summaries if s.effective),
               "targets": [t.display_name for t in target_order]}
    (report_dir / "consensus_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# HW10 Judge Summary", "", f"- total cases: {len(summaries)}",
             f"- effective cases: {payload['effective_cases']}", ""]
    for summary in summaries:
        mark = "PASS" if summary.effective else "FAIL"
        lines.append(f"## {summary.case_name} [{mark}]")
        for target in target_order:
            rr = summary.targets[target.key]
            lines.append(f"- {target.display_name}: {rr.status} ({rr.elapsed_sec:.3f}s)")
            for err in rr.errors[:3]:
                lines.append(f"  - {err}")
        lines.append("")
    (report_dir / "consensus_summary.md").write_text("\n".join(lines), encoding="utf-8")

# Performance scoring (guidebook §6, treating samples as population)

def compute_r(x: float, x_min: float, x_max: float, x_avg: float, p: float = 0.10) -> float:
    """Guidebook r(x) function."""
    base_min = p * x_avg + (1 - p) * x_min
    base_max = p * x_avg + (1 - p) * x_max
    if base_max <= base_min:
        return 1.0
    if x <= base_min:
        return 1.0
    if x > base_max:
        return 0.0
    return (base_max - x) / (base_max - base_min)


def compute_score_across_samples(
    samples: List[Tuple[float, float, float]]  # list of (Tr, Ta, W) per sample
) -> List[float]:
    """
    Given N samples of (Tr, Ta, W), compute s for each sample using
    population min/max/avg across all samples (as per guidebook).
    Returns list of s values (length N), or [] if no samples.
    """
    if not samples:
        return []
    trs = [s[0] for s in samples]
    tas = [s[1] for s in samples]
    ws  = [s[2] for s in samples]

    tr_min, tr_max, tr_avg = min(trs), max(trs), sum(trs) / len(trs)
    ta_min, ta_max, ta_avg = min(tas), max(tas), sum(tas) / len(tas)
    w_min,  w_max,  w_avg  = min(ws),  max(ws),  sum(ws) / len(ws)

    scores = []
    for tr, ta, w in samples:
        r_tr = compute_r(tr, tr_min, tr_max, tr_avg)
        r_ta = compute_r(ta, ta_min, ta_max, ta_avg)
        r_w  = compute_r(w,  w_min,  w_max,  w_avg)
        s = 15.0 * (0.3 * r_tr + 0.3 * r_ta + 0.4 * r_w)
        scores.append(s)
    return scores


def target_status_to_case_code(status: str) -> str:
    if status == "PASSED":
        return "AC"
    if status in {"TIMEOUT_SOFT", "TIMEOUT_HARD"}:
        return "TLE"
    if status in {"RUNTIME_ERROR", "JAVA_ERROR", "EXEC_ERROR"}:
        return "RE"
    if status == "INPUT_ERROR":
        return "IE"
    if status == "SKIPPED_STOP":
        return "STOP"
    return "WA"


def aggregate_case_status(targets: Dict[str, TargetRunResult]) -> str:
    if not targets:
        return "IE"

    codes = [target_status_to_case_code(rr.status) for rr in targets.values()]
    if all(code == "AC" for code in codes):
        return "AC"

    # Priority when mixed statuses exist in one case.
    for code in ("IE", "RE", "TLE", "WA", "STOP"):
        if code in codes:
            return code
    return "WA"



# Shared UI widgets are imported from judge.core.ui.


# Worker

class JudgeWorker(QObject):
    sig_log = pyqtSignal(str)
    sig_targets = pyqtSignal(object)
    sig_case_started = pyqtSignal(object)
    sig_target_done = pyqtSignal(str, str, object)
    sig_case_done = pyqtSignal(str, bool, bool, bool)
    sig_finished = pyqtSignal(str)
    sig_error = pyqtSignal(str)

    def __init__(self, cfg: RunConfig, cases: List[GuiCase], stop_event: threading.Event) -> None:
        super().__init__()
        self.cfg = cfg
        self.cases = cases
        self.stop_event = stop_event

    def _run_java_only(
        self,
        target: "TargetProject",
        case_name: str,
        input_text: str,
        out_dir: "Path",
        soft_timeout: float,
        hard_timeout: float,
    ) -> Tuple["TargetProject", str, str, str, float, str]:
        from pathlib import Path as _Path
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{target.key}__{_Path(case_name).stem}.txt"
        schedule = build_input_schedule(input_text)
        stdout_text, stderr_text, elapsed_sec, run_status = run_java_command(
            command=target.command,
            input_schedule=schedule,
            soft_timeout=soft_timeout,
            hard_timeout=hard_timeout,
        )
        with out_path.open("w", encoding="utf-8", errors="replace") as f:
            f.write(stdout_text)
        return target, stdout_text, stderr_text, str(out_path), elapsed_sec, run_status or ""

    def _validate_only(
        self,
        target: "TargetProject",
        stdout_text: str,
        stderr_text: str,
        raw_output_path: str,
        elapsed_sec: float,
        run_status: str,
        passengers: Dict,
        maints: Dict,
    ) -> TargetRunResult:
        status = "PASSED"
        errors: List[str] = []

        if run_status == "JAVA_NOT_FOUND":
            status = "JAVA_ERROR"; errors.append("java command not found")
        elif run_status == "KILLED":
            status = "TIMEOUT_HARD"; errors.append("hard timeout exceeded")
        elif run_status == "TLE":
            status = "TIMEOUT_SOFT"; errors.append("soft timeout exceeded")
        elif run_status == "EXEC_ERROR":
            status = "RUNTIME_ERROR"; errors.append("runtime error")

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
            raw_output_path=raw_output_path,
        )

    def _finish_case(
        self,
        case: "GuiCase",
        projects: List,
        run_futures: Dict,
        passengers: Dict,
        maints: Dict,
        validate_pool: "ThreadPoolExecutor",
    ) -> Tuple[Dict[str, TargetRunResult], Dict]:
        validate_futures: Dict = {}
        per_raw: Dict = {}

        for future, (target, _case) in list(run_futures.items()):
            if self.stop_event.is_set():
                future.cancel()
                continue
            try:
                tgt, stdout, stderr, out_path, elapsed, run_st = future.result()
            except Exception as exc:
                err_rr = TargetRunResult(
                    status="EXEC_ERROR", stdout="", stderr="",
                    elapsed_sec=0.0, sim_time=0.0, power=0.0, avg_time=0.0,
                    errors=[f"并发执行异常: {exc}"],
                    normalized_events=[], raw_output_path="",
                )
                per_raw[target.key] = err_rr
                continue
            per_raw[target.key] = (tgt, stdout, stderr, out_path, elapsed, run_st)

        vf_map: Dict = {}
        for target in projects:
            raw = per_raw.get(target.key)
            if raw is None:
                continue
            if isinstance(raw, TargetRunResult):
                vf_map[target.key] = raw
                continue
            tgt, stdout, stderr, out_path, elapsed, run_st = raw
            vf = validate_pool.submit(
                self._validate_only,
                tgt, stdout, stderr, out_path, elapsed, run_st,
                passengers, maints,
            )
            vf_map[target.key] = vf

        return vf_map, per_raw

    def run(self) -> None:
        summaries: List[CaseSummary] = []
        try:
            self.cfg.out_dir.mkdir(parents=True, exist_ok=True)
            self.cfg.report_dir.mkdir(parents=True, exist_ok=True)
            self.cfg.problem_dir.mkdir(parents=True, exist_ok=True)

            clear_directory(self.cfg.out_dir)
            clear_directory(self.cfg.problem_dir)

            self.sig_log.emit(f"开始编译并发现目标，匹配模式 {self.cfg.target_pattern}")
            projects = discover_projects(
                co_judge_dir=self.cfg.co_judge_dir,
                pattern=self.cfg.target_pattern,
                build_root=self.cfg.build_dir,
                classpath=str(self.cfg.official_jar),
                compile_timeout=self.cfg.compile_timeout,
            )
            if not projects:
                raise RuntimeError("未发现任何目标项目")

            run_workers = max(1, min(self.cfg.max_workers, len(projects)))
            validate_workers = max(1, min(self.cfg.max_workers, len(projects)))
            self.sig_targets.emit(projects)
            self.sig_log.emit(
                f"目标数量 {len(projects)}，运行线程 {run_workers}，"
                f"校验线程 {validate_workers}（流水线并发模式）"
            )

            with ThreadPoolExecutor(
                max_workers=run_workers * 2,
                thread_name_prefix="hw10run"
            ) as run_pool, ThreadPoolExecutor(
                max_workers=validate_workers,
                thread_name_prefix="hw10val"
            ) as validate_pool:

                pending_validate: Dict[str, Dict] = {}
                pending_meta: Dict[str, Tuple] = {}
                total = len(self.cases)

                for idx, case in enumerate(self.cases, start=1):
                    if self.stop_event.is_set():
                        self.sig_log.emit("用户请求停止，已在样例切换点终止")
                        break

                    self.sig_case_started.emit({"case": case, "index": idx, "total": total})

                    passengers, maints, input_errors = parse_input_requests(
                        case.input_text,
                        mutual_mode=self.cfg.mutual_mode,
                    )

                    if input_errors:
                        per_target: Dict[str, TargetRunResult] = {}
                        for p in projects:
                            rr = TargetRunResult(
                                status="INPUT_ERROR", stdout="", stderr="",
                                elapsed_sec=0.0, sim_time=0.0, power=0.0, avg_time=0.0,
                                errors=list(input_errors),
                                normalized_events=[], raw_output_path="",
                            )
                            per_target[p.key] = rr
                            self.sig_target_done.emit(case.case_id, p.display_name, rr)

                        summary = CaseSummary(
                            case_name=case.display_name,
                            all_correct=False, all_consistent=False, effective=False,
                            targets=per_target,
                        )
                        summaries.append(summary)
                        write_problem_case(summary, case.input_text, self.cfg.problem_dir, projects)
                        self.sig_case_done.emit(case.case_id, False, False, False)
                        continue

                    run_futures: Dict["Future", Tuple] = {
                        run_pool.submit(
                            self._run_java_only,
                            p, case.display_name, case.input_text,
                            self.cfg.out_dir,
                            self.cfg.soft_timeout, self.cfg.hard_timeout,
                        ): (p, case)
                        for p in projects
                    }

                    vf_map, _ = self._finish_case(
                        case, projects, run_futures, passengers, maints, validate_pool
                    )
                    pending_validate[case.case_id] = vf_map
                    pending_meta[case.case_id] = (case, passengers, maints)

                    per_target = {}
                    for p in projects:
                        vf_or_rr = vf_map.get(p.key)
                        if vf_or_rr is None:
                            rr = TargetRunResult(
                                status="SKIPPED_STOP", stdout="", stderr="",
                                elapsed_sec=0.0, sim_time=0.0, power=0.0, avg_time=0.0,
                                errors=["用户手动停止"],
                                normalized_events=[], raw_output_path="",
                            )
                        elif isinstance(vf_or_rr, TargetRunResult):
                            rr = vf_or_rr
                        else:
                            try:
                                rr = vf_or_rr.result()
                            except Exception as exc:
                                rr = TargetRunResult(
                                    status="EXEC_ERROR", stdout="", stderr="",
                                    elapsed_sec=0.0, sim_time=0.0, power=0.0, avg_time=0.0,
                                    errors=[f"校验异常: {exc}"],
                                    normalized_events=[], raw_output_path="",
                                )

                        per_target[p.key] = rr
                        self.sig_target_done.emit(case.case_id, p.display_name, rr)

                    all_correct = all(per_target[p.key].status == "PASSED" for p in projects)
                    all_consistent = False
                    if all_correct and projects:
                        baseline = per_target[projects[0].key].normalized_events
                        all_consistent = all(
                            per_target[p.key].normalized_events == baseline for p in projects
                        )

                    effective = all_correct and all_consistent
                    summary = CaseSummary(
                        case_name=case.display_name,
                        all_correct=all_correct,
                        all_consistent=all_consistent,
                        effective=effective,
                        targets=per_target,
                    )
                    summaries.append(summary)

                    if not effective:
                        write_problem_case(summary, case.input_text, self.cfg.problem_dir, projects)

                    self.sig_case_done.emit(case.case_id, all_correct, all_consistent, effective)

                    if self.stop_event.is_set():
                        self.sig_log.emit("评测已按用户请求停止")
                        break

            if summaries and projects:
                write_summary_report(self.cfg.report_dir, summaries, projects)

            score_msg = ""
            if False and summaries and projects:
                target_score_lists = {p.key: [] for p in projects}
                for s in summaries:
                    samples = []
                    keys = []
                    for p in projects:
                        rr = s.targets.get(p.key)
                        if rr and rr.status == "PASSED":
                            samples.append((rr.sim_time, rr.avg_time, rr.power))
                            keys.append(p.key)
                    if samples:
                        s_list = compute_score_across_samples(samples)
                        for k, score in zip(keys, s_list):
                            target_score_lists[k].append(score)
                
                avg_scores = {}
                for p in projects:
                    lst = target_score_lists[p.key]
                    if lst:
                        avg_scores[p.display_name] = sum(lst) / len(lst)
                
                if avg_scores:
                    score_msg = " \n[平均性能分 S] " + " , ".join(f"{k}: {v:.2f}" for k, v in avg_scores.items())

            status_counts = {"AC": 0, "WA": 0, "TLE": 0, "RE": 0, "IE": 0, "STOP": 0}
            for s in summaries:
                code = aggregate_case_status(s.targets)
                status_counts[code] = status_counts.get(code, 0) + 1

            count_msg = (
                f"AC {status_counts['AC']}，WA {status_counts['WA']}，"
                f"TLE {status_counts['TLE']}，RE {status_counts['RE']}，IE {status_counts['IE']}"
            )
            if status_counts["STOP"] > 0:
                count_msg += f"，STOP {status_counts['STOP']}"

            self.sig_finished.emit(
                f"评测完成，样例总数 {len(summaries)}，{count_msg}{score_msg}"
            )

        except Exception as exc:
            err = "\n".join(traceback.format_exception_only(type(exc), exc)).strip()
            self.sig_error.emit(err)


# Main window

class HW10JudgeWindow(StandardJudgeWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        base_dir = Path(__file__).resolve().parent
        spec = StandardJudgeSpec(
            hw_id='hw10',
            unit=3,
            title='OO HW10 评测机',
            base_dir=base_dir,
            self_work_dir=(base_dir.parents[2] / 'U3/hw10').resolve(),
            official_default=(base_dir / 'lib').resolve(),
            fixed_cases_dirname='fixed_cases',
            official_must_be_file=False,
            official_missing_message='未找到官方包',
            generator_uses_strict_mutual=False,
        generator_seed=20260515,
        generator_limit=3000,
            include_fixed_pool=True,
            show_metrics=True,
            show_scores=False,
            metric_labels=('Time',),
            score_mode='elapsed',
            include_stderr=False,
            custom_placeholder='输入完整样例内容',
        )
        super().__init__(
            spec=spec,
            run_config_cls=RunConfig,
            gui_case_cls=GuiCase,
            worker_cls=JudgeWorker,
            generate_all_func=generate_all,
            clear_directory_func=clear_directory,
            parent=parent,
        )

# Entry point


def build_page(parent: QWidget) -> QWidget:
    return build_standard_page(HW10JudgeWindow, parent)

def main() -> None:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    win = HW10JudgeWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
