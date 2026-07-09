#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HW9 consensus judge backend.

The GUI-facing API mirrors the HW7 judge, but validation is HW9-specific:
generated input is interpreted by a Python reference model and each target's
stdout is compared against the model output.
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
from collections import Counter, deque
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from threading import Lock, Thread
from typing import Dict, List, Optional, Set, Tuple

from judge.core.target_matching import direct_target_entry, matching_target_entries


RE_MAIN_METHOD = re.compile(r"\bpublic\s+static\s+void\s+main\s*\(")
JUDGE_DIR = Path(__file__).resolve().parent
DEFAULT_OFFICIAL_SRC = JUDGE_DIR / "lib"


def _fallback_search_roots() -> List[Path]:
    roots: List[Path] = []
    cur = JUDGE_DIR
    for _ in range(6):
        cur = cur.parent
        roots.append(cur)
        u3 = cur / "U3"
        if u3.is_dir():
            roots.append(u3)
    return roots


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


def clear_directory(path: Path) -> None:
    if not path.exists():
        return
    for item in path.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def sanitize_key(name: str, idx: int) -> str:
    key = re.sub(r"[^0-9A-Za-z_.-]+", "_", name).strip("._")
    return key or f"target_{idx}"


def parse_main_class(java_file: Path) -> str:
    text = java_file.read_text(encoding="utf-8", errors="replace")
    pkg = ""
    cls = java_file.stem
    m = re.search(r"^\s*package\s+([A-Za-z_][\w.]*)\s*;", text, re.MULTILINE)
    if m:
        pkg = m.group(1)
    m = re.search(r"\bpublic\s+class\s+([A-Za-z_]\w*)", text)
    if m:
        cls = m.group(1)
    return f"{pkg}.{cls}" if pkg else cls


def _contains_main_method(java_file: Path) -> bool:
    try:
        return RE_MAIN_METHOD.search(java_file.read_text(encoding="utf-8", errors="replace")) is not None
    except OSError:
        return False


def choose_source_dir(project_dir: Path) -> Tuple[Path, Path]:
    candidates = sorted(project_dir.rglob("MainClass.java"))
    if not candidates:
        candidates = sorted(project_dir.rglob("Main.java"))
    if not candidates:
        candidates = sorted(p for p in project_dir.rglob("*.java") if _contains_main_method(p))
    if not candidates:
        raise RuntimeError(f"no Java entry with main method found under {project_dir}")
    main_file = candidates[0]
    source_dir = main_file.parent
    try:
        rel_parts = main_file.relative_to(project_dir).parts
        for i, part in enumerate(rel_parts):
            if part.lower() == "src":
                source_dir = project_dir.joinpath(*rel_parts[: i + 1])
                break
    except Exception:
        pass
    return source_dir, main_file


def _resolve_official_source(classpath: str) -> Path:
    if classpath:
        p = Path(classpath)
        if p.is_dir():
            return p
    if DEFAULT_OFFICIAL_SRC.is_dir() and any(DEFAULT_OFFICIAL_SRC.rglob("*.java")):
        return DEFAULT_OFFICIAL_SRC
    for base in _fallback_search_roots():
        try:
            candidates = list(base.rglob("面向对象第三单元第一次作业官方包"))
        except OSError:
            continue
        for cand in candidates:
            if cand.is_dir() and any(cand.rglob("*.java")):
                return cand
    return DEFAULT_OFFICIAL_SRC


def compile_project(source_dir: Path, build_dir: Path, official_src: Path, timeout_sec: float) -> Tuple[bool, str]:
    java_files = [str(p) for p in source_dir.rglob("*.java")]
    if official_src.is_dir():
        java_files.extend(str(p) for p in official_src.rglob("*.java"))
    if not java_files:
        return False, f"no java files under {source_dir}"
    build_dir.mkdir(parents=True, exist_ok=True)
    clear_directory(build_dir)
    cmd = ["javac", "-encoding", "UTF-8", "-d", str(build_dir)] + java_files
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
        return False, f"javac failed (exit={p.returncode})\n{((p.stdout or '') + (p.stderr or '')).strip()}"
    return True, "compile ok"


def discover_projects(
    co_judge_dir: Path,
    pattern: str,
    build_root: Path,
    classpath: str,
    compile_timeout: float,
) -> List[TargetProject]:
    official_src = _resolve_official_source(classpath)
    projects: List[TargetProject] = []
    errors: List[str] = []
    entries = sorted(co_judge_dir.iterdir(), key=lambda p: p.name.lower())
    direct = direct_target_entry(pattern)
    targets = [direct] if direct else matching_target_entries(entries, pattern)
    for idx, target in enumerate(targets, start=1):
        try:
            if target.is_file():
                key = sanitize_key(f"{target.stem}_jar", idx)
                projects.append(TargetProject(key, target.name, target.parent, target.parent, "<jar>", build_root / key, ["java", "-jar", str(target)]))
                continue
            source_dir, main_file = choose_source_dir(target)
            main_class = parse_main_class(main_file)
            key = sanitize_key(target.name, idx)
            build_dir = build_root / key
            ok, msg = compile_project(source_dir, build_dir, official_src, compile_timeout)
            if not ok:
                raise RuntimeError(msg)
            projects.append(
                TargetProject(
                    key=key,
                    display_name=target.name,
                    project_dir=target,
                    source_dir=source_dir,
                    main_class=main_class,
                    build_dir=build_dir,
                    command=["java", "-cp", str(build_dir), main_class],
                )
            )
        except Exception as exc:
            errors.append(f"{target.name}: {exc}")
    if errors:
        print("[WARN] skipped invalid targets:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
    if not projects:
        detail = "; ".join(errors[:5]) if errors else "no matched directories"
        raise RuntimeError(f"未发现可用目标项目: {detail}")
    return projects


class ErrorStats:
    def __init__(self) -> None:
        self.single: Dict[str, Counter] = {
            "eui": Counter(), "evi": Counter(), "uinf": Counter(), "vinf": Counter(),
            "ss": Counter(),
        }
        self.pair: Dict[str, Counter] = {"ds": Counter(), "flnf": Counter(), "uc": Counter()}
        self.pair_total: Counter = Counter()
        self.invalid_age_count = 0

    def one(self, code: str, value: int) -> str:
        self.single[code][value] += 1
        return f"{code}-{sum(self.single[code].values())}, {value}-{self.single[code][value]}"

    def age(self, value: int) -> str:
        self.invalid_age_count += 1
        return f"ia-{self.invalid_age_count}, {value}"

    def two(self, code: str, a: int, b: int, sort_ids: bool = False) -> str:
        if sort_ids and a > b:
            a, b = b, a
        self.pair_total[code] += 1
        self.pair[code][a] += 1
        if a != b:
            self.pair[code][b] += 1
        return f"{code}-{self.pair_total[code]}, {a}-{self.pair[code][a]}, {b}-{self.pair[code][b]}"


class ReferenceModel:
    def __init__(self) -> None:
        self.users: Dict[int, Tuple[str, int]] = {}
        self.following: Dict[int, Set[int]] = {}
        self.followers: Dict[int, Set[int]] = {}
        self.videos: Dict[int, int] = {}
        self.received: Dict[int, List[int]] = {}
        self.mutual = 0
        self.err = ErrorStats()
        self.out: List[str] = []

    def add_user(self, uid: int, age: int, name: str) -> None:
        if uid in self.users:
            self.out.append(self.err.one("eui", uid))
        elif age < 0 or age > 110:
            self.out.append(self.err.age(age))
        else:
            self.users[uid] = (name, age)
            self.following[uid] = set()
            self.followers[uid] = set()
            self.received[uid] = []
            self.out.append("add_user succeeded")

    def upload_video(self, uid: int, vid: int) -> None:
        if uid not in self.users:
            self.out.append(self.err.one("uinf", uid))
        elif vid in self.videos:
            self.out.append(self.err.one("evi", vid))
        else:
            self.videos[vid] = uid
            for fan in list(self.followers[uid]):
                self.received[fan].insert(0, vid)
            self.out.append("upload_video succeeded")

    def follow_user(self, a: int, b: int) -> None:
        if a not in self.users:
            self.out.append(self.err.one("uinf", a))
        elif b not in self.users:
            self.out.append(self.err.one("uinf", b))
        elif a == b:
            self.out.append(self.err.one("ss", a))
        elif b in self.following[a]:
            self.out.append(self.err.two("ds", a, b))
        else:
            self.following[a].add(b)
            self.followers[b].add(a)
            if a in self.following[b]:
                self.mutual += 1
            self.out.append("follow_user succeeded")

    def unfollow_user(self, a: int, b: int) -> None:
        if a not in self.users:
            self.out.append(self.err.one("uinf", a))
        elif b not in self.users:
            self.out.append(self.err.one("uinf", b))
        elif b not in self.following[a]:
            self.out.append(self.err.two("flnf", a, b))
        else:
            if a in self.following[b]:
                self.mutual -= 1
            self.following[a].remove(b)
            self.followers[b].remove(a)
            self.out.append("unfollow_user succeeded")

    def watch_video(self, uid: int, vid: int) -> None:
        if uid not in self.users:
            self.out.append(self.err.one("uinf", uid))
        elif vid not in self.videos:
            self.out.append(self.err.one("vinf", vid))
        else:
            self.received[uid] = [x for x in self.received[uid] if x != vid]
            self.out.append("watch_video succeeded")

    def query_received(self, uid: int) -> None:
        if uid not in self.users:
            self.out.append(self.err.one("uinf", uid))
            return
        self.out.append("query_received_unwatched_videos succeeded")
        first = self.received[uid][:5]
        self.out.append(" ".join(str(x) for x in first) if first else "None")

    def query_ratio(self, uid: int) -> None:
        if uid not in self.users:
            self.out.append(self.err.one("uinf", uid))
            return
        fans = list(self.followers[uid])
        counts = [0, 0, 0, 0]
        for fid in fans:
            age = self.users[fid][1]
            if age <= 16:
                counts[0] += 1
            elif age <= 30:
                counts[1] += 1
            elif age <= 45:
                counts[2] += 1
            else:
                counts[3] += 1
        n = len(fans)
        ratios = [0.0 if n == 0 else c / n for c in counts]
        self.out.append("query_up_followers_age_ratio succeeded")
        rendered = [
            "0.00" if n == 0
            else str((Decimal(c) / Decimal(n)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            for c in counts
        ]
        self.out.append(f"{self.users[uid][0]} {' '.join(rendered)}")

    def query_shortest(self, a: int, b: int) -> None:
        if a not in self.users:
            self.out.append(self.err.one("uinf", a))
        elif b not in self.users:
            self.out.append(self.err.one("uinf", b))
        elif a == b:
            self.out.append("0")
        else:
            q = deque([(a, 0)])
            seen = {a}
            while q:
                cur, dist = q.popleft()
                for nxt in self.following[cur]:
                    if nxt == b:
                        self.out.append(str(dist + 1))
                        return
                    if nxt not in seen:
                        seen.add(nxt)
                        q.append((nxt, dist + 1))
            self.out.append(self.err.two("uc", a, b, sort_ids=True))

    def run_line(self, line: str) -> Optional[str]:
        parts = line.strip().split()
        if not parts:
            return None
        try:
            cmd = parts[0]
            if cmd == "add_user" and len(parts) >= 4:
                self.add_user(int(parts[1]), int(parts[2]), parts[3])
            elif cmd == "upload_video" and len(parts) == 3:
                self.upload_video(int(parts[1]), int(parts[2]))
            elif cmd == "follow_user" and len(parts) == 3:
                self.follow_user(int(parts[1]), int(parts[2]))
            elif cmd == "unfollow_user" and len(parts) == 3:
                self.unfollow_user(int(parts[1]), int(parts[2]))
            elif cmd == "watch_video" and len(parts) == 3:
                self.watch_video(int(parts[1]), int(parts[2]))
            elif cmd == "query_received_unwatched_videos" and len(parts) == 2:
                self.query_received(int(parts[1]))
            elif cmd == "query_up_followers_age_ratio" and len(parts) == 2:
                self.query_ratio(int(parts[1]))
            elif cmd == "query_mutual_following_sum" and len(parts) == 1:
                self.out.append(str(self.mutual))
            elif cmd == "query_shortest_path" and len(parts) == 3:
                self.query_shortest(int(parts[1]), int(parts[2]))
            elif cmd == "end":
                return "end"
            else:
                return f"invalid command format: {line}"
        except ValueError:
            return f"invalid integer in command: {line}"
        return None


def evaluate_reference(input_text: str, mutual_mode: bool = False) -> ReferenceCase:
    model = ReferenceModel()
    errors: List[str] = []
    command_count = 0
    for idx, raw in enumerate(input_text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        command_count += 1
        if mutual_mode and command_count > 3000:
            errors.append(f"line {idx}: mutual command limit exceeded")
            break
        err = model.run_line(line)
        if err == "end":
            break
        if err:
            errors.append(f"line {idx}: {err}")
    return ReferenceCase(input_text=input_text, expected_lines=model.out, input_errors=errors)


def parse_input_requests(input_text: str, mutual_mode: bool = False) -> Tuple[ReferenceCase, MaintRequestInput, List[str]]:
    case = evaluate_reference(input_text, mutual_mode=mutual_mode)
    return case, MaintRequestInput(case.expected_lines), case.input_errors


def build_input_schedule(input_text: str) -> List[Tuple[float, str]]:
    return [(0.0, line + "\n") for line in input_text.splitlines() if line.strip()]


def run_java_command(
    command: List[str],
    input_schedule: List[Tuple[float, str]],
    soft_timeout: float,
    hard_timeout: float,
) -> Tuple[str, str, float, Optional[str]]:
    input_text = "".join(payload for _, payload in input_schedule)
    start = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=hard_timeout,
        )
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
        if stripped and not stripped.startswith("--- STDERR ---"):
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


def run_target_case(
    target: TargetProject,
    case_name: str,
    input_text: str,
    passengers: ReferenceCase,
    maints: MaintRequestInput,
    out_dir: Path,
    soft_timeout: float,
    hard_timeout: float,
) -> TargetRunResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{target.key}__{Path(case_name).stem}.txt"
    stdout_text, stderr_text, elapsed, run_status = run_java_command(target.command, build_input_schedule(input_text), soft_timeout, hard_timeout)
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
    return TargetRunResult(status, stdout_text, stderr_text, elapsed, 0.0, float(len(stdout_text)), 0.0, errors, normalize_events(stdout_text), str(out_path))


def write_problem_case(case_summary: CaseSummary, input_text: str, problem_dir: Path, target_order: List[TargetProject]) -> None:
    problem_dir.mkdir(parents=True, exist_ok=True)
    path = problem_dir / f"{Path(case_summary.case_name).stem}.md"
    lines = [f"# Problem Case: {case_summary.case_name}", "", "## Input", "", "```text", input_text.rstrip(), "```", "", "## Targets", ""]
    lines.append("| target | status | raw_output |")
    lines.append("|---|---|---|")
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


def write_summary_report(report_dir: Path, summaries: List[CaseSummary], target_order: List[TargetProject]) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "total_cases": len(summaries),
        "effective_cases": sum(1 for s in summaries if s.effective),
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
                        "errors": s.targets[t.key].errors,
                        "raw_output": s.targets[t.key].raw_output_path,
                    }
                    for t in target_order
                },
            }
            for s in summaries
        ],
    }
    (report_dir / "consensus_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# HW9 Consensus Judge Report", "", f"- total_cases: {len(summaries)}", f"- effective_cases: {payload['effective_cases']}", "", "| case | effective |", "|---|---|"]
    for s in summaries:
        lines.append(f"| {s.case_name} | {s.effective} |")
    (report_dir / "consensus_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HW9 consensus judge")
    parser.add_argument("--mode", choices=["self", "mutual"], default="mutual")
    parser.add_argument("--co-judge-dir", default=".")
    parser.add_argument("--target-pattern", default="互测代码_*")
    parser.add_argument("--official-src", default=str(DEFAULT_OFFICIAL_SRC))
    parser.add_argument("--build-dir", default=".build_targets")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--generator", default="data_generator_hw9.py")
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--out-dir", default="out_raw")
    parser.add_argument("--report-dir", default="report")
    parser.add_argument("--problem-dir", default="problem_cases")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--compile-timeout", type=float, default=90.0)
    parser.add_argument("--max-cases", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    from data_generator_hw9 import generate_all

    args = parse_args()
    base = Path(__file__).resolve().parent
    data_dir = (base / args.data_dir).resolve()
    if args.generate:
        data_dir.mkdir(parents=True, exist_ok=True)
        clear_directory(data_dir)
        generate_all(str(data_dir), args.count, strict_mutual=(args.mode == "mutual"))
    projects = discover_projects((base / args.co_judge_dir).resolve(), args.target_pattern, (base / args.build_dir).resolve(), args.official_src, args.compile_timeout)
    cases = sorted(data_dir.glob("*.txt"))
    if args.max_cases > 0:
        cases = cases[: args.max_cases]
    summaries: List[CaseSummary] = []
    out_dir = (base / args.out_dir).resolve()
    report_dir = (base / args.report_dir).resolve()
    problem_dir = (base / args.problem_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    clear_directory(out_dir)
    problem_dir.mkdir(parents=True, exist_ok=True)
    clear_directory(problem_dir)
    for i, case_path in enumerate(cases, start=1):
        print(f"[{i}/{len(cases)}] {case_path.name}")
        text = case_path.read_text(encoding="utf-8", errors="replace")
        ref, aux, errors = parse_input_requests(text, mutual_mode=(args.mode == "mutual"))
        per: Dict[str, TargetRunResult] = {}
        for p in projects:
            if errors:
                rr = TargetRunResult("INPUT_ERROR", "", "", 0.0, 0.0, 0.0, 0.0, errors, [], "")
            else:
                rr = run_target_case(p, case_path.name, text, ref, aux, out_dir, args.timeout, args.timeout)
            per[p.key] = rr
            print(f"  - {p.display_name}: {rr.status}")
        ok = all(per[p.key].status == "PASSED" for p in projects)
        summary = CaseSummary(case_path.name, ok, ok, ok, per)
        summaries.append(summary)
        if not ok:
            write_problem_case(summary, text, problem_dir, projects)
    write_summary_report(report_dir, summaries, projects)
    print(f"summary md: {report_dir / 'consensus_summary.md'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise SystemExit(3)
