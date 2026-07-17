#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HW11 Qt GUI judge."""

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

from judge.core.target_matching import direct_target_entry, matching_target_entries

from judge.core.pipeline_plugin import PipelinePluginConfig, build_pipeline_page, run_pipeline_main
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
    lines = ["# HW11 Judge Summary", "", f"- total cases: {len(summaries)}",
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

CONFIG = PipelinePluginConfig(
    hw_id="hw11",
    unit=3,
    title="OO HW11 评测机",
    self_work_subdir="U3/hw11",
    official_subpath="lib",
    generate_all_func=generate_all,
    clear_directory=clear_directory,
    discover_projects=discover_projects,
    parse_input_requests=parse_input_requests,
    build_input_schedule=build_input_schedule,
    run_java_command=run_java_command,
    normalize_events=normalize_events,
    write_problem_case=write_problem_case,
    write_summary_report=write_summary_report,
    target_result_cls=TargetRunResult,
    case_summary_cls=CaseSummary,
    validator_factory=lambda passengers, maints: Validator(passengers, maints),
    fixed_cases_dirname="fixed_cases",
    official_must_be_file=False,
    official_missing_message="未找到官方包",
    generator_uses_strict_mutual=False,
    generator_seed=20260515,
    generator_limit=3000,
    include_fixed_pool=True,
    show_metrics=True,
    show_scores=False,
    metric_labels=("Time",),
    score_mode="elapsed",
    include_stderr=False,
    custom_placeholder="输入完整样例内容",
    score_in_finished_message=False,
    stderr_is_error=False,
)

def build_page(parent: QWidget) -> QWidget:
    return build_pipeline_page(CONFIG, parent)

def main() -> None:
    run_pipeline_main(CONFIG)

if __name__ == "__main__":
    main()
