"""hw1/hw2/hw3 共享的评测页面，通过 U1Adapter 封装三次作业的差异。"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PyQt5.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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

from judge.core.target_matching import matching_target_entries
from judge.core.ui import (
    DARK_COLORS,
    BadgeLabel,
    CaseEditorCard,
    CopyButton,
    StatusChip,
    TargetOutputCard,
    apply_dark_palette,
    build_dark_stylesheet,
)


# Adapter contract


@dataclass
class CaseView:
    """GUI 层用的用例数据 (兼容 hw1 的 Case.expr 与 hw2/3 的 Case.input_text)."""
    case_id: str
    input_text: str
    kind: str  # "fixed" | "random" | "custom"
    raw_case: Any = None  # 原始 Case 对象, 传回 adapter.evaluate 时使用

    @property
    def display_name(self) -> str:
        return self.case_id

    @property
    def source(self) -> str:
        return self.kind


@dataclass
class Verdict:
    ok: bool
    reason: str = ""
    shorter_candidate: str = ""


class U1Adapter:
    """子类需实现下列方法, 页面通过它们与 hw 特定 engine 通信。"""

    hw_id: str = "hwX"
    supports_shortest_audit: bool = False
    grammar_hint: str = ""  # 显示在配置区提示当前语法版本

    def build_cases(self, seed: int, random_count: int) -> List[CaseView]:
        raise NotImplementedError

    def evaluate(self, case: CaseView, output: str, shortest_audit: bool) -> Verdict:
        raise NotImplementedError

    def wrap_custom(self, cid: str, text: str) -> Any:
        return None


# Data models (与 hw14 对齐, 但去掉 sim_time/power/avg_time)


@dataclass
class RunConfig:
    work_dir: Path
    build_dir: Path
    out_dir: Path
    target_pattern: str
    target_mode: str  # "self" | "mutual"
    my_target: str
    soft_timeout: float
    hard_timeout: float
    compile_timeout: float
    max_workers: int
    shortest_audit: bool
    seed: int
    random_count: int


@dataclass
class TargetProject:
    key: str
    display_name: str
    project_dir: Path
    source_dir: Path
    main_class: str
    build_dir: Path
    command: List[str]
    jar_path: Optional[Path] = None


@dataclass
class TargetRunResult:
    status: str  # PASSED / WRONG_ANSWER / TIMEOUT_HARD / TIMEOUT_SOFT / RUNTIME_ERROR / JAVA_ERROR / EXEC_ERROR / SKIPPED_STOP / INPUT_ERROR
    stdout: str
    stderr: str
    elapsed_sec: float
    errors: List[str]
    reason: str = ""
    shorter_candidate: str = ""
    raw_output_path: str = ""


@dataclass
class CaseSummary:
    case_name: str
    all_correct: bool
    targets: Dict[str, TargetRunResult]


# Compilation & execution helpers


def _list_java_files(src_dir: Path) -> List[str]:
    files: List[str] = []
    for root, _dirs, fns in os.walk(src_dir):
        for fn in fns:
            if fn.endswith(".java"):
                files.append(str(Path(root) / fn))
    return files


def _compile_java(src_dir: Path, build_dir: Path, timeout_s: float = 60.0) -> Tuple[bool, str]:
    """在 ``src_dir`` 下编译所有 .java 到 ``build_dir``. 返回 (是否成功, 编译器 stderr)."""
    build_dir.mkdir(parents=True, exist_ok=True)
    java_files = _list_java_files(src_dir)
    if not java_files:
        return False, f"no .java files under {src_dir}"
    cmd = ["javac", "-encoding", "UTF-8", "-d", str(build_dir)] + java_files
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout_s,
        )
    except FileNotFoundError:
        return False, "javac not found in PATH — is JDK installed?"
    except subprocess.TimeoutExpired:
        return False, f"javac timed out (>{timeout_s}s)"
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "").strip()
    return True, ""


def _find_main_class(build_dir: Path) -> Optional[str]:
    """在 build_dir 下找带 psvm 的 class 文件. 找不到就退回 ``MainClass``."""
    parent = build_dir.parent
    if parent.exists():
        src = parent / "src"
        candidates = _list_java_files(src) if src.exists() else []
        for jf in candidates:
            try:
                text = Path(jf).read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if re.search(r"public\s+static\s+void\s+main\s*\(", text):
                m = re.search(r"public\s+class\s+(\w+)", text)
                if m:
                    return m.group(1)
    for pref in ("MainClass", "Main"):
        if (build_dir / f"{pref}.class").exists():
            return pref
    for f in build_dir.iterdir():
        if f.suffix == ".class":
            return f.stem
    return None


def _run_java_command(command: List[str], input_text: str,
                     soft_timeout: float, hard_timeout: float) -> Tuple[str, str, float, Optional[str]]:
    start = time.monotonic()
    try:
        proc = subprocess.run(
            command, input=input_text, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=hard_timeout,
        )
    except FileNotFoundError:
        return "", "java command not found", time.monotonic() - start, "JAVA_NOT_FOUND"
    except subprocess.TimeoutExpired as exc:
        return exc.stdout or "", exc.stderr or "", time.monotonic() - start, "KILLED"
    except Exception as exc:
        return "", f"runner error: {exc}", time.monotonic() - start, "EXEC_ERROR"
    elapsed = time.monotonic() - start
    status = "EXEC_ERROR" if proc.returncode != 0 else ("TLE" if elapsed > soft_timeout else None)
    return proc.stdout or "", proc.stderr or "", elapsed, status


def _sanitize_key(name: str, idx: int) -> str:
    key = re.sub(r"[^A-Za-z0-9_.-]", "_", name).strip("_")
    if not key:
        key = f"t{idx}"
    return f"{idx:02d}_{key}"


def _target_status_to_case_code(status: str) -> str:
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


def _aggregate_case_status(targets: Dict[str, TargetRunResult]) -> str:
    if not targets:
        return "IE"
    codes = [_target_status_to_case_code(rr.status) for rr in targets.values()]
    if all(code == "AC" for code in codes):
        return "AC"
    for code in ("IE", "RE", "TLE", "WA", "STOP"):
        if code in codes:
            return code
    return "WA"


def _make_jar_target(jar_path: Path, idx: int, build_root: Path) -> TargetProject:
    return TargetProject(
        key=_sanitize_key(f"{jar_path.stem}_jar", idx),
        display_name=jar_path.name,
        project_dir=jar_path.parent,
        source_dir=jar_path.parent,
        main_class="<jar>",
        build_dir=build_root / f"jar_{jar_path.stem}_{idx}",
        command=["java", "-jar", str(jar_path.resolve())],
        jar_path=jar_path.resolve(),
    )



# Shared UI widgets are imported from judge.core.ui.


# Worker


class JudgeWorker(QObject):
    sig_log = pyqtSignal(str)
    sig_targets = pyqtSignal(object)
    sig_case_started = pyqtSignal(object)
    sig_target_done = pyqtSignal(str, str, object)
    sig_case_done = pyqtSignal(str, bool)
    sig_finished = pyqtSignal(str)
    sig_error = pyqtSignal(str)

    def __init__(self, adapter: U1Adapter, cfg: RunConfig, cases: List[CaseView],
                 stop_event: threading.Event) -> None:
        super().__init__()
        self.adapter = adapter
        self.cfg = cfg
        self.cases = cases
        self.stop_event = stop_event

    # target discovery + compile
    def _discover_and_compile(self) -> List[TargetProject]:
        cfg = self.cfg
        projects: List[TargetProject] = []
        entries: List[Tuple[str, Path]] = []

        direct = Path(cfg.target_pattern)
        if direct.is_file() and direct.suffix.lower() == ".jar":
            return [_make_jar_target(direct, 1, cfg.build_dir)]

        if cfg.target_mode == "self" and not any(ch in cfg.target_pattern for ch in "*?[]"):
            target = Path(cfg.target_pattern)
            if not target.exists():
                raise RuntimeError(f"目标不存在: {target}")
            if target.is_file() and target.suffix.lower() == ".jar":
                return [_make_jar_target(target, 1, cfg.build_dir)]
            entries.append(("self", target))
        else:
            pattern_path = Path(cfg.target_pattern)
            pattern_dir = pattern_path.parent if str(pattern_path.parent) else Path(".")
            pattern_name = pattern_path.name
            if pattern_dir.is_dir():
                matches = matching_target_entries(
                    sorted(pattern_dir.iterdir(), key=lambda p: p.name.lower()),
                    pattern_name,
                )
            else:
                matches = []
            for p in matches:
                if p.is_file() and p.suffix.lower() == ".jar":
                    projects.append(_make_jar_target(p, len(projects) + 1, cfg.build_dir))
                elif p.is_dir():
                    entries.append((p.name, p))

        for idx, (name, project_dir) in enumerate(entries, start=1):
            if self.stop_event.is_set():
                break
            src = project_dir / "src" if (project_dir / "src").exists() and (project_dir / "src").is_dir() else project_dir
            key = _sanitize_key(name, idx)
            build_dir = cfg.build_dir / key
            if build_dir.exists():
                shutil.rmtree(build_dir, ignore_errors=True)
            self.sig_log.emit(f"[{name}] javac …")
            ok, err = _compile_java(src, build_dir, cfg.compile_timeout)
            if not ok:
                self.sig_log.emit(f"[{name}] 编译失败: {err.splitlines()[0] if err else '(no message)'}")
                continue
            main_class = _find_main_class(build_dir) or "MainClass"
            projects.append(TargetProject(
                key=key,
                display_name=name,
                project_dir=project_dir,
                source_dir=src,
                main_class=main_class,
                build_dir=build_dir,
                command=["java", "-cp", str(build_dir), main_class],
            ))
            self.sig_log.emit(f"[{name}] 编译完成 → {main_class}")
        return projects

    def _run_one(self, target: TargetProject, case: CaseView) -> TargetRunResult:
        out_dir = self.cfg.out_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{target.key}__{case.case_id}.txt"
        stdout_text, stderr_text, elapsed, run_status = _run_java_command(
            target.command, case.input_text,
            self.cfg.soft_timeout, self.cfg.hard_timeout,
        )
        try:
            out_path.write_text(stdout_text, encoding="utf-8", errors="replace")
        except Exception:
            pass

        status = "PASSED"
        errors: List[str] = []
        reason = ""
        shorter = ""

        if run_status == "JAVA_NOT_FOUND":
            status = "JAVA_ERROR"; errors.append("java command not found")
        elif run_status == "KILLED":
            status = "TIMEOUT_HARD"; errors.append("hard timeout exceeded")
        elif run_status == "TLE":
            status = "TIMEOUT_SOFT"; errors.append("soft timeout exceeded")
        elif run_status == "EXEC_ERROR":
            status = "RUNTIME_ERROR"; errors.append("runtime error")

        if status == "PASSED":
            try:
                verdict = self.adapter.evaluate(case, stdout_text.strip(), self.cfg.shortest_audit)
            except Exception as exc:
                verdict = Verdict(ok=False, reason=f"EVAL_ERROR: {type(exc).__name__}: {exc}")
            if not verdict.ok:
                status = "WRONG_ANSWER"
                reason = verdict.reason or "wrong answer"
                errors.append(reason)
            shorter = verdict.shorter_candidate

        return TargetRunResult(
            status=status,
            stdout=stdout_text,
            stderr=stderr_text,
            elapsed_sec=elapsed,
            errors=errors,
            reason=reason,
            shorter_candidate=shorter,
            raw_output_path=str(out_path),
        )

    def run(self) -> None:
        try:
            self.cfg.out_dir.mkdir(parents=True, exist_ok=True)
            self.cfg.build_dir.mkdir(parents=True, exist_ok=True)

            self.sig_log.emit(f"发现并编译目标，匹配模式 {self.cfg.target_pattern}")
            projects = self._discover_and_compile()
            if not projects:
                raise RuntimeError("未发现任何可用目标 (检查目标通配/正则 / 编译错误)")

            self.sig_targets.emit(projects)
            self.sig_log.emit(f"目标数量 {len(projects)}，并发线程 {self.cfg.max_workers}")

            total = len(self.cases)
            with ThreadPoolExecutor(max_workers=self.cfg.max_workers,
                                    thread_name_prefix="u1run") as pool:
                for idx, case in enumerate(self.cases, start=1):
                    if self.stop_event.is_set():
                        self.sig_log.emit("用户请求停止，已在样例切换点终止")
                        break

                    self.sig_case_started.emit({"case": case, "index": idx, "total": total})

                    fut_map: Dict[Future, TargetProject] = {
                        pool.submit(self._run_one, t, case): t for t in projects
                    }
                    per_target: Dict[str, TargetRunResult] = {}
                    for fut, t in fut_map.items():
                        try:
                            rr = fut.result()
                        except Exception as exc:
                            rr = TargetRunResult(
                                status="EXEC_ERROR", stdout="", stderr="",
                                elapsed_sec=0.0, errors=[f"并发执行异常: {exc}"],
                            )
                        per_target[t.display_name] = rr
                        self.sig_target_done.emit(case.case_id, t.display_name, rr)

                    all_correct = all(rr.status == "PASSED" for rr in per_target.values())
                    self.sig_case_done.emit(case.case_id, all_correct)

            status_counts = {"AC": 0, "WA": 0, "TLE": 0, "RE": 0, "IE": 0, "STOP": 0}
            self.sig_finished.emit(f"评测完成 (共 {total} 个样例)")
        except Exception as exc:
            err = "\n".join(traceback.format_exception_only(type(exc), exc)).strip()
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            self.sig_error.emit(err + "\n" + tb)
