"""Generic worker pipeline for standard judge plugins."""

from __future__ import annotations

import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PyQt5.QtCore import QObject, pyqtSignal

from judge.core.models import aggregate_case_status, compute_score_across_samples


@dataclass(frozen=True)
class PipelineBackend:
    hw_id: str
    clear_directory: Callable[[Path], None]
    discover_projects: Callable[..., List[Any]]
    parse_input_requests: Callable[..., Tuple[Any, Any, List[str]]]
    build_input_schedule: Callable[[str], List[Tuple[float, str]]]
    run_java_command: Callable[..., Tuple[str, str, float, Optional[str]]]
    normalize_events: Callable[[str], List[str]]
    write_problem_case: Callable[[Any, str, Path, List[Any]], None]
    write_summary_report: Callable[[Path, List[Any], List[Any]], None]
    target_result_cls: type
    case_summary_cls: type
    validator_factory: Callable[[Any, Any], Any]
    case_context_func: Optional[Callable[[Any, bool], Tuple[Any, Any, List[str]]]] = None
    validate_result_func: Optional[Callable[..., Any]] = None
    score_in_finished_message: bool = False
    stderr_is_error: bool = False


class PipelineJudgeWorker(QObject):
    sig_log = pyqtSignal(str)
    sig_targets = pyqtSignal(object)
    sig_case_started = pyqtSignal(object)
    sig_target_done = pyqtSignal(str, str, object)
    sig_case_done = pyqtSignal(str, bool, bool, bool)
    sig_finished = pyqtSignal(str)
    sig_error = pyqtSignal(str)

    def __init__(
        self,
        backend: PipelineBackend,
        cfg: Any,
        cases: List[Any],
        stop_event: Any,
    ) -> None:
        super().__init__()
        self.backend = backend
        self.cfg = cfg
        self.cases = cases
        self.stop_event = stop_event

    def _make_result(
        self,
        status: str,
        stdout: str = "",
        stderr: str = "",
        elapsed_sec: float = 0.0,
        sim_time: float = 0.0,
        power: float = 0.0,
        avg_time: float = 0.0,
        errors: Optional[List[str]] = None,
        normalized_events: Optional[List[str]] = None,
        raw_output_path: str = "",
    ) -> Any:
        kwargs = {
            "status": status,
            "stdout": stdout,
            "stderr": stderr,
            "elapsed_sec": elapsed_sec,
            "sim_time": sim_time,
            "power": power,
            "avg_time": avg_time,
            "errors": errors or [],
            "normalized_events": normalized_events or [],
            "raw_output_path": raw_output_path,
        }
        try:
            return self.backend.target_result_cls(**kwargs)
        except TypeError:
            accepted = getattr(self.backend.target_result_cls, "__dataclass_fields__", {})
            if accepted:
                kwargs = {key: value for key, value in kwargs.items() if key in accepted}
            return self.backend.target_result_cls(**kwargs)

    def _make_summary(
        self,
        case_name: str,
        all_correct: bool,
        all_consistent: bool,
        effective: bool,
        targets: Dict[str, Any],
    ) -> Any:
        kwargs = {
            "case_name": case_name,
            "all_correct": all_correct,
            "all_consistent": all_consistent,
            "effective": effective,
            "targets": targets,
        }
        try:
            return self.backend.case_summary_cls(**kwargs)
        except TypeError:
            accepted = getattr(self.backend.case_summary_cls, "__dataclass_fields__", {})
            if accepted:
                kwargs = {key: value for key, value in kwargs.items() if key in accepted}
            return self.backend.case_summary_cls(**kwargs)

    def _run_java_only(
        self,
        target: Any,
        case_name: str,
        input_text: str,
        out_dir: Path,
        soft_timeout: float,
        hard_timeout: float,
    ) -> Tuple[Any, str, str, str, float, str]:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{target.key}__{Path(case_name).stem}.txt"
        schedule = self.backend.build_input_schedule(input_text)
        stdout_text, stderr_text, elapsed_sec, run_status = self.backend.run_java_command(
            command=target.command,
            input_schedule=schedule,
            soft_timeout=soft_timeout,
            hard_timeout=hard_timeout,
        )
        with out_path.open("w", encoding="utf-8", errors="replace") as f:
            f.write(stdout_text)
            if self.backend.stderr_is_error and stderr_text:
                f.write("\n\n--- STDERR ---\n")
                f.write(stderr_text)
        return target, stdout_text, stderr_text, str(out_path), elapsed_sec, run_status or ""

    def _validate_only(
        self,
        target: Any,
        stdout_text: str,
        stderr_text: str,
        raw_output_path: str,
        elapsed_sec: float,
        run_status: str,
        passengers: Any,
        maints: Any,
    ) -> Any:
        if self.backend.validate_result_func is not None:
            return self.backend.validate_result_func(
                target=target,
                stdout_text=stdout_text,
                stderr_text=stderr_text,
                raw_output_path=raw_output_path,
                elapsed_sec=elapsed_sec,
                run_status=run_status,
                passengers=passengers,
                maints=maints,
                cfg=self.cfg,
            )

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
            validator = self.backend.validator_factory(passengers, maints)
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

        if self.backend.stderr_is_error and stderr_text.strip() and status in {"PASSED", "WRONG_ANSWER"}:
            errors.append("stderr is non-empty")

        return self._make_result(
            status=status,
            stdout=stdout_text,
            stderr=stderr_text,
            elapsed_sec=elapsed_sec,
            sim_time=sim_time,
            power=power,
            avg_time=avg_time,
            errors=errors,
            normalized_events=self.backend.normalize_events(stdout_text),
            raw_output_path=raw_output_path,
        )

    def _finish_case(
        self,
        projects: List[Any],
        run_futures: Dict[Any, Tuple[Any, Any]],
        passengers: Any,
        maints: Any,
        validate_pool: ThreadPoolExecutor,
    ) -> Dict[str, Any]:
        per_raw: Dict[str, Any] = {}

        for future, (target, _case) in list(run_futures.items()):
            if self.stop_event.is_set():
                future.cancel()
                continue
            try:
                tgt, stdout, stderr, out_path, elapsed, run_status = future.result()
            except Exception as exc:
                per_raw[target.key] = self._make_result(
                    status="EXEC_ERROR",
                    errors=[f"concurrent execution error: {exc}"],
                )
                continue
            per_raw[target.key] = (tgt, stdout, stderr, out_path, elapsed, run_status)

        vf_map: Dict[str, Any] = {}
        for target in projects:
            raw = per_raw.get(target.key)
            if raw is None:
                continue
            if isinstance(raw, self.backend.target_result_cls):
                vf_map[target.key] = raw
                continue
            tgt, stdout, stderr, out_path, elapsed, run_status = raw
            vf_map[target.key] = validate_pool.submit(
                self._validate_only,
                tgt, stdout, stderr, out_path, elapsed, run_status,
                passengers, maints,
            )
        return vf_map

    def _discover_projects(self) -> List[Any]:
        return self.backend.discover_projects(
            co_judge_dir=self.cfg.co_judge_dir,
            pattern=self.cfg.target_pattern,
            build_root=self.cfg.build_dir,
            classpath=str(self.cfg.official_jar),
            compile_timeout=self.cfg.compile_timeout,
        )

    def _score_message(self, summaries: List[Any], projects: List[Any]) -> str:
        if not self.backend.score_in_finished_message or not summaries or not projects:
            return ""
        target_score_lists = {p.key: [] for p in projects}
        for summary in summaries:
            samples = []
            keys = []
            for project in projects:
                rr = summary.targets.get(project.key)
                if rr and rr.status == "PASSED":
                    samples.append((rr.sim_time, rr.avg_time, rr.power))
                    keys.append(project.key)
            if samples:
                for key, score in zip(keys, compute_score_across_samples(samples)):
                    target_score_lists[key].append(score)

        avg_scores = {}
        for project in projects:
            scores = target_score_lists[project.key]
            if scores:
                avg_scores[project.display_name] = sum(scores) / len(scores)
        if not avg_scores:
            return ""
        return " \n[Average S] " + " , ".join(f"{k}: {v:.2f}" for k, v in avg_scores.items())

    def run(self) -> None:
        summaries: List[Any] = []
        try:
            self.cfg.out_dir.mkdir(parents=True, exist_ok=True)
            self.cfg.report_dir.mkdir(parents=True, exist_ok=True)
            self.cfg.problem_dir.mkdir(parents=True, exist_ok=True)

            self.backend.clear_directory(self.cfg.out_dir)
            self.backend.clear_directory(self.cfg.problem_dir)

            self.sig_log.emit(f"Start compiling targets: {self.cfg.target_pattern}")
            projects = self._discover_projects()
            if not projects:
                raise RuntimeError("no target project found")

            run_workers = max(1, min(self.cfg.max_workers, len(projects)))
            validate_workers = max(1, min(self.cfg.max_workers, len(projects)))
            self.sig_targets.emit(projects)
            self.sig_log.emit(
                f"Targets {len(projects)}, run workers {run_workers}, "
                f"validate workers {validate_workers}"
            )

            with ThreadPoolExecutor(
                max_workers=run_workers * 2,
                thread_name_prefix=f"{self.backend.hw_id}run",
            ) as run_pool, ThreadPoolExecutor(
                max_workers=validate_workers,
                thread_name_prefix=f"{self.backend.hw_id}val",
            ) as validate_pool:
                total = len(self.cases)
                for idx, case in enumerate(self.cases, start=1):
                    if self.stop_event.is_set():
                        self.sig_log.emit("Stopped before next case")
                        break

                    self.sig_case_started.emit({"case": case, "index": idx, "total": total})

                    if self.backend.case_context_func is not None:
                        passengers, maints, input_errors = self.backend.case_context_func(
                            case,
                            self.cfg.mutual_mode,
                        )
                    else:
                        passengers, maints, input_errors = self.backend.parse_input_requests(
                            case.input_text,
                            mutual_mode=self.cfg.mutual_mode,
                        )

                    if input_errors:
                        per_target = {}
                        for project in projects:
                            rr = self._make_result(
                                status="INPUT_ERROR",
                                errors=list(input_errors),
                            )
                            per_target[project.key] = rr
                            self.sig_target_done.emit(case.case_id, project.display_name, rr)

                        summary = self._make_summary(
                            case.display_name, False, False, False, per_target
                        )
                        summaries.append(summary)
                        self.backend.write_problem_case(
                            summary, case.input_text, self.cfg.problem_dir, projects
                        )
                        self.sig_case_done.emit(case.case_id, False, False, False)
                        continue

                    run_futures = {
                        run_pool.submit(
                            self._run_java_only,
                            project, case.display_name, case.input_text,
                            self.cfg.out_dir,
                            self.cfg.soft_timeout, self.cfg.hard_timeout,
                        ): (project, case)
                        for project in projects
                    }
                    vf_map = self._finish_case(projects, run_futures, passengers, maints, validate_pool)

                    per_target = {}
                    for project in projects:
                        vf_or_rr = vf_map.get(project.key)
                        if vf_or_rr is None:
                            rr = self._make_result(
                                status="SKIPPED_STOP",
                                errors=["stopped by user"],
                            )
                        elif isinstance(vf_or_rr, self.backend.target_result_cls):
                            rr = vf_or_rr
                        else:
                            try:
                                rr = vf_or_rr.result()
                            except Exception as exc:
                                rr = self._make_result(
                                    status="EXEC_ERROR",
                                    errors=[f"validation error: {exc}"],
                                )
                        per_target[project.key] = rr
                        self.sig_target_done.emit(case.case_id, project.display_name, rr)

                    all_correct = all(per_target[p.key].status == "PASSED" for p in projects)
                    all_consistent = False
                    if all_correct and projects:
                        baseline = getattr(
                            per_target[projects[0].key],
                            "normalized_events",
                            [per_target[projects[0].key].stdout.strip()],
                        )
                        all_consistent = all(
                            getattr(
                                per_target[p.key],
                                "normalized_events",
                                [per_target[p.key].stdout.strip()],
                            ) == baseline
                            for p in projects
                        )
                    effective = all_correct and all_consistent
                    summary = self._make_summary(
                        case.display_name,
                        all_correct,
                        all_consistent,
                        effective,
                        per_target,
                    )
                    summaries.append(summary)

                    if not effective:
                        self.backend.write_problem_case(
                            summary, case.input_text, self.cfg.problem_dir, projects
                        )

                    self.sig_case_done.emit(case.case_id, all_correct, all_consistent, effective)

                    if self.stop_event.is_set():
                        self.sig_log.emit("Stopped by user")
                        break

            if summaries and projects:
                self.backend.write_summary_report(self.cfg.report_dir, summaries, projects)

            status_counts = {"AC": 0, "WA": 0, "TLE": 0, "RE": 0, "IE": 0, "STOP": 0}
            for summary in summaries:
                code = aggregate_case_status(summary.targets)
                status_counts[code] = status_counts.get(code, 0) + 1

            count_msg = (
                f"AC {status_counts['AC']}, WA {status_counts['WA']}, "
                f"TLE {status_counts['TLE']}, RE {status_counts['RE']}, IE {status_counts['IE']}"
            )
            if status_counts["STOP"] > 0:
                count_msg += f", STOP {status_counts['STOP']}"

            self.sig_finished.emit(
                f"Finished {len(summaries)} cases, {count_msg}{self._score_message(summaries, projects)}"
            )
        except Exception as exc:
            err = "\n".join(traceback.format_exception_only(type(exc), exc)).strip()
            self.sig_error.emit(err)
