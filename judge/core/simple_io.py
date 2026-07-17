"""Reusable backend for simple stdin/stdout judge plugins."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

from PyQt5.QtWidgets import QWidget

from judge.core.models import RunConfig
from judge.core.pipeline_worker import PipelineBackend, PipelineJudgeWorker
from judge.core.standard_page import StandardJudgeSpec, StandardJudgeWindow
from judge.core.target_matching import matching_target_entries


@dataclass
class SimpleCase:
    case_id: str
    input_text: str
    source: str
    display_name: str = ""
    raw_case: Any = None

    def __post_init__(self) -> None:
        if not self.display_name:
            self.display_name = self.case_id


@dataclass
class Verdict:
    ok: bool
    reason: str = ""
    shorter_candidate: str = ""


class SimpleIoAdapter:
    hw_id: str = "hwX"
    supports_shortest_audit: bool = False
    grammar_hint: str = ""

    def build_cases(self, seed: int, random_count: int) -> List[SimpleCase]:
        raise NotImplementedError

    def evaluate(self, case: SimpleCase, output: str, shortest_audit: bool) -> Verdict:
        raise NotImplementedError

    def wrap_custom(self, cid: str, text: str) -> Any:
        return None


@dataclass
class SimpleTargetProject:
    key: str
    display_name: str
    project_dir: Path
    source_dir: Path
    main_class: str
    build_dir: Path
    command: List[str]
    jar_path: Optional[Path] = None


@dataclass
class SimpleTargetRunResult:
    status: str
    stdout: str = ""
    stderr: str = ""
    elapsed_sec: float = 0.0
    errors: List[str] = field(default_factory=list)
    reason: str = ""
    shorter_candidate: str = ""
    raw_output_path: str = ""
    sim_time: float = 0.0
    power: float = 0.0
    avg_time: float = 0.0
    normalized_events: List[str] = field(default_factory=list)


@dataclass
class SimpleCaseSummary:
    case_name: str
    all_correct: bool
    targets: dict[str, SimpleTargetRunResult]


def _list_java_files(src_dir: Path) -> List[str]:
    files: List[str] = []
    for root, _dirs, fns in os.walk(src_dir):
        for fn in fns:
            if fn.endswith(".java"):
                files.append(str(Path(root) / fn))
    return files


def _compile_java(src_dir: Path, build_dir: Path, timeout_s: float = 60.0) -> Tuple[bool, str]:
    build_dir.mkdir(parents=True, exist_ok=True)
    java_files = _list_java_files(src_dir)
    if not java_files:
        return False, f"no .java files under {src_dir}"
    cmd = ["javac", "-encoding", "UTF-8", "-d", str(build_dir)] + java_files
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
    except FileNotFoundError:
        return False, "javac not found in PATH; is JDK installed?"
    except subprocess.TimeoutExpired:
        return False, f"javac timed out (>{timeout_s}s)"
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "").strip()
    return True, ""


def _find_main_class(build_dir: Path) -> Optional[str]:
    parent = build_dir.parent
    if parent.exists():
        src = parent / "src"
        candidates = _list_java_files(src) if src.exists() else []
        for jf in candidates:
            try:
                text = Path(jf).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if re.search(r"public\s+static\s+void\s+main\s*\(", text):
                m = re.search(r"public\s+class\s+(\w+)", text)
                if m:
                    return m.group(1)
    for pref in ("MainClass", "Main"):
        if (build_dir / f"{pref}.class").exists():
            return pref
    for fp in build_dir.iterdir():
        if fp.suffix == ".class":
            return fp.stem
    return None


def _run_java_command(
    command: List[str],
    input_text: str,
    soft_timeout: float,
    hard_timeout: float,
) -> Tuple[str, str, float, Optional[str]]:
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
    return proc.stdout or "", proc.stderr or "", elapsed, status


def _sanitize_key(name: str, idx: int) -> str:
    key = re.sub(r"[^A-Za-z0-9_.-]", "_", name).strip("_")
    if not key:
        key = f"t{idx}"
    return f"{idx:02d}_{key}"


def _make_jar_target(jar_path: Path, idx: int, build_root: Path) -> SimpleTargetProject:
    return SimpleTargetProject(
        key=_sanitize_key(f"{jar_path.stem}_jar", idx),
        display_name=jar_path.name,
        project_dir=jar_path.parent,
        source_dir=jar_path.parent,
        main_class="<jar>",
        build_dir=build_root / f"jar_{jar_path.stem}_{idx}",
        command=["java", "-jar", str(jar_path.resolve())],
        jar_path=jar_path.resolve(),
    )


def clear_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)


def discover_projects(
    co_judge_dir: Path,
    pattern: str,
    build_root: Path,
    classpath: str,
    compile_timeout: float,
) -> List[SimpleTargetProject]:
    _ = co_judge_dir, classpath
    projects: List[SimpleTargetProject] = []
    entries: List[Tuple[str, Path]] = []

    direct = Path(pattern)
    if direct.is_file() and direct.suffix.lower() == ".jar":
        return [_make_jar_target(direct, 1, build_root)]

    if direct.exists() and not any(ch in pattern for ch in "*?[]"):
        if direct.is_file() and direct.suffix.lower() == ".jar":
            return [_make_jar_target(direct, 1, build_root)]
        entries.append((direct.name or "self", direct))
    else:
        pattern_path = Path(pattern)
        pattern_dir = pattern_path.parent if str(pattern_path.parent) else Path(".")
        pattern_name = pattern_path.name
        matches = []
        if pattern_dir.is_dir():
            matches = matching_target_entries(
                sorted(pattern_dir.iterdir(), key=lambda p: p.name.lower()),
                pattern_name,
            )
        for item in matches:
            if item.is_file() and item.suffix.lower() == ".jar":
                projects.append(_make_jar_target(item, len(projects) + 1, build_root))
            elif item.is_dir():
                entries.append((item.name, item))

    for idx, (name, project_dir) in enumerate(entries, start=1):
        src = project_dir / "src" if (project_dir / "src").is_dir() else project_dir
        key = _sanitize_key(name, idx)
        build_dir = build_root / key
        if build_dir.exists():
            shutil.rmtree(build_dir, ignore_errors=True)
        ok, err = _compile_java(src, build_dir, compile_timeout)
        if not ok:
            print(f"[WARN] skipped target {name}: {err}", file=sys.stderr)
            continue
        main_class = _find_main_class(build_dir) or "MainClass"
        projects.append(SimpleTargetProject(
            key=key,
            display_name=name,
            project_dir=project_dir,
            source_dir=src,
            main_class=main_class,
            build_dir=build_dir,
            command=["java", "-cp", str(build_dir), main_class],
        ))
    return projects


def build_input_schedule(input_text: str) -> List[Tuple[float, str]]:
    return [(0.0, input_text)]


def run_java_command(
    command: List[str],
    input_schedule: List[Tuple[float, str]],
    soft_timeout: float,
    hard_timeout: float,
) -> Tuple[str, str, float, Optional[str]]:
    input_text = "".join(payload for _, payload in input_schedule)
    return _run_java_command(command, input_text, soft_timeout, hard_timeout)


def parse_input_requests(input_text: str, mutual_mode: bool = False) -> Tuple[str, None, List[str]]:
    _ = mutual_mode
    return input_text, None, []


def case_context(case: SimpleCase, mutual_mode: bool = False) -> Tuple[SimpleCase, None, List[str]]:
    _ = mutual_mode
    return case, None, []


def normalize_events(stdout_text: str) -> List[str]:
    stripped = stdout_text.strip()
    return [stripped] if stripped else []


def write_problem_case(
    case_summary: SimpleCaseSummary,
    input_text: str,
    problem_dir: Path,
    target_order: List[SimpleTargetProject],
) -> None:
    _ = case_summary, input_text, target_order
    problem_dir.mkdir(parents=True, exist_ok=True)


def write_summary_report(
    report_dir: Path,
    summaries: List[SimpleCaseSummary],
    target_order: List[SimpleTargetProject],
) -> None:
    _ = summaries, target_order
    report_dir.mkdir(parents=True, exist_ok=True)


def _status_from_run_status(run_status: str) -> Tuple[str, List[str]]:
    if run_status == "JAVA_NOT_FOUND":
        return "JAVA_ERROR", ["java command not found"]
    if run_status == "KILLED":
        return "TIMEOUT_HARD", ["hard timeout exceeded"]
    if run_status == "TLE":
        return "TIMEOUT_SOFT", ["soft timeout exceeded"]
    if run_status == "EXEC_ERROR":
        return "RUNTIME_ERROR", ["runtime error"]
    return "PASSED", []


def _make_validate_result(adapter: SimpleIoAdapter) -> Callable[..., SimpleTargetRunResult]:
    def validate_result(
        target: SimpleTargetProject,
        stdout_text: str,
        stderr_text: str,
        raw_output_path: str,
        elapsed_sec: float,
        run_status: str,
        passengers: SimpleCase,
        maints: Any,
        cfg: RunConfig,
    ) -> SimpleTargetRunResult:
        _ = target, maints
        status, errors = _status_from_run_status(run_status)
        reason = ""
        shorter = ""
        if status == "PASSED":
            try:
                verdict = adapter.evaluate(
                    passengers,
                    stdout_text.strip(),
                    getattr(cfg, "shortest_audit", False),
                )
            except Exception as exc:
                verdict = Verdict(ok=False, reason=f"EVAL_ERROR: {type(exc).__name__}: {exc}")
            if not verdict.ok:
                status = "WRONG_ANSWER"
                reason = verdict.reason or "wrong answer"
                errors.append(reason)
            shorter = verdict.shorter_candidate
        return SimpleTargetRunResult(
            status=status,
            stdout=stdout_text,
            stderr=stderr_text,
            elapsed_sec=elapsed_sec,
            errors=errors,
            reason=reason,
            shorter_candidate=shorter,
            raw_output_path=raw_output_path,
            normalized_events=normalize_events(stdout_text),
        )
    return validate_result


def make_backend(adapter: SimpleIoAdapter) -> PipelineBackend:
    return PipelineBackend(
        hw_id=adapter.hw_id,
        clear_directory=clear_directory,
        discover_projects=discover_projects,
        parse_input_requests=parse_input_requests,
        build_input_schedule=build_input_schedule,
        run_java_command=run_java_command,
        normalize_events=normalize_events,
        write_problem_case=write_problem_case,
        write_summary_report=write_summary_report,
        target_result_cls=SimpleTargetRunResult,
        case_summary_cls=SimpleCaseSummary,
        validator_factory=lambda _passengers, _maints: None,
        case_context_func=case_context,
        validate_result_func=_make_validate_result(adapter),
    )


class SimpleIoJudgeWorker(PipelineJudgeWorker):
    def __init__(
        self,
        adapter: SimpleIoAdapter,
        cfg: RunConfig,
        cases: List[SimpleCase],
        stop_event: threading.Event,
    ) -> None:
        super().__init__(make_backend(adapter), cfg, cases, stop_event)


def _noop_generate_all(*_args: Any, **_kwargs: Any) -> List[str]:
    return []


class SimpleIoJudgeWindow(StandardJudgeWindow):
    def __init__(
        self,
        adapter: SimpleIoAdapter,
        unit: int,
        base_dir: Path,
        self_work_dir: Path,
        parent: Optional[QWidget] = None,
    ) -> None:
        self.adapter = adapter
        spec = StandardJudgeSpec(
            hw_id=adapter.hw_id,
            unit=unit,
            title=f"OO {adapter.hw_id.upper()} 评测机",
            base_dir=base_dir,
            self_work_dir=self_work_dir,
            official_default=self_work_dir,
            fixed_cases_dirname="fixed_cases",
            show_official_package=False,
            show_metrics=True,
            show_scores=False,
            include_stderr=True,
            metric_labels=("Len", "Time", "S"),
            score_mode="expression_length",
            custom_placeholder=self._custom_placeholder(adapter),
        )
        super().__init__(
            spec=spec,
            run_config_cls=RunConfig,
            gui_case_cls=SimpleCase,
            worker_cls=SimpleIoJudgeWorker,
            generate_all_func=_noop_generate_all,
            clear_directory_func=clear_directory,
            parent=parent,
        )

    @staticmethod
    def _custom_placeholder(adapter: SimpleIoAdapter) -> str:
        return "输入完整样例内容"

    def collect_run_config(self) -> RunConfig:
        try:
            timeout = float(self.edt_timeout.text().strip())
        except ValueError as exc:
            raise ValueError("超时必须为数字") from exc
        if timeout <= 0:
            raise ValueError("超时必须为正数")

        work_dir, target_pattern = self.resolve_target_selection()
        pattern_path = Path(target_pattern)
        if pattern_path.is_absolute():
            pattern = target_pattern
        else:
            pattern = str((work_dir / target_pattern).resolve())

        return RunConfig(
            co_judge_dir=work_dir,
            official_jar=self.spec.official_default,
            build_dir=(self.base_dir / ".build_targets").resolve(),
            out_dir=(self.base_dir / "out_raw").resolve(),
            report_dir=(self.base_dir / "report").resolve(),
            problem_dir=(self.base_dir / "problem_cases").resolve(),
            target_pattern=pattern,
            soft_timeout=timeout,
            hard_timeout=timeout,
            compile_timeout=timeout,
            max_workers=self.compute_workers(8),
            mutual_mode=self.is_mutual_target_path(),
            shortest_audit=self.adapter.supports_shortest_audit,
        )

    def collect_cases(self) -> List[SimpleCase]:
        cases: List[SimpleCase] = []
        use_fixed = self.chk_fixed.isChecked()
        use_random = self.chk_random.isChecked()
        use_custom = self.chk_custom.isChecked()
        add_custom_to_fixed = self.chk_custom_into_fixed.isChecked()

        if use_fixed or use_random:
            seed = int(time.time()) & 0x7FFFFFFF
            random_count = int(self.spn_random.value()) if use_random else 0
            try:
                built = self.adapter.build_cases(seed, random_count)
            except Exception as exc:
                raise RuntimeError(f"用例生成失败: {exc}") from exc
            for case in built:
                if case.source == "fixed" and not use_fixed:
                    continue
                if case.source == "random" and not use_random:
                    continue
                cases.append(case)

        if use_fixed:
            cases.extend(self.load_fixed_pool_cases())

        custom_inputs: List[Tuple[int, str]] = []
        if use_custom or add_custom_to_fixed:
            custom_inputs = self._collect_custom_inputs()

        if add_custom_to_fixed and custom_inputs:
            self.persist_custom_cases_to_fixed_pool(custom_inputs)

        if use_custom:
            for idx, text in custom_inputs:
                case_id = f"C{idx:03d}"
                raw = None
                try:
                    raw = self.adapter.wrap_custom(case_id, text)
                except Exception as exc:
                    self.append_log(f"自定义用例 {case_id} 解析失败: {exc}")
                    continue
                cases.append(SimpleCase(
                    case_id=case_id,
                    input_text=text,
                    source="custom",
                    raw_case=raw,
                ))
        return cases

    def create_worker(self, cfg: Any, cases: List[Any]) -> SimpleIoJudgeWorker:
        return SimpleIoJudgeWorker(self.adapter, cfg, cases, self.stop_event)
