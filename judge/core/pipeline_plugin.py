"""Declarative helpers for pipeline-based judge plugins."""

from __future__ import annotations

import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QWidget

from judge.core.models import GuiCase, RunConfig
from judge.core.pipeline_worker import PipelineBackend, PipelineJudgeWorker
from judge.core.standard_page import StandardJudgeSpec, StandardJudgeWindow, build_standard_page


@dataclass(frozen=True)
class PipelinePluginConfig:
    hw_id: str
    unit: int
    title: str
    self_work_subdir: str
    official_subpath: str
    generate_all_func: Callable[..., List[str]]
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
    fixed_cases_dirname: str = "fixed_cases"
    official_must_be_file: bool = False
    official_missing_message: str = "未找到官方包"
    generator_uses_strict_mutual: bool = True
    generator_seed: Optional[int] = None
    generator_limit: Optional[int] = None
    include_fixed_pool: bool = True
    show_metrics: bool = True
    show_scores: bool = False
    metric_labels: Tuple[str, ...] = ("Time",)
    score_mode: str = "u2"
    include_stderr: bool = False
    custom_placeholder: str = "输入完整样例内容"
    score_in_finished_message: bool = False
    stderr_is_error: bool = False


def make_pipeline_backend(config: PipelinePluginConfig) -> PipelineBackend:
    return PipelineBackend(
        hw_id=config.hw_id,
        clear_directory=config.clear_directory,
        discover_projects=config.discover_projects,
        parse_input_requests=config.parse_input_requests,
        build_input_schedule=config.build_input_schedule,
        run_java_command=config.run_java_command,
        normalize_events=config.normalize_events,
        write_problem_case=config.write_problem_case,
        write_summary_report=config.write_summary_report,
        target_result_cls=config.target_result_cls,
        case_summary_cls=config.case_summary_cls,
        validator_factory=config.validator_factory,
        score_in_finished_message=config.score_in_finished_message,
        stderr_is_error=config.stderr_is_error,
    )


def make_pipeline_worker_class(config: PipelinePluginConfig) -> type[PipelineJudgeWorker]:
    backend = make_pipeline_backend(config)

    class ConfiguredPipelineJudgeWorker(PipelineJudgeWorker):
        def __init__(self, cfg: RunConfig, cases: List[GuiCase], stop_event: threading.Event) -> None:
            super().__init__(backend, cfg, cases, stop_event)

    ConfiguredPipelineJudgeWorker.__name__ = f"{config.hw_id.upper()}JudgeWorker"
    return ConfiguredPipelineJudgeWorker


def make_standard_spec(config: PipelinePluginConfig, base_dir: Path) -> StandardJudgeSpec:
    return StandardJudgeSpec(
        hw_id=config.hw_id,
        unit=config.unit,
        title=config.title,
        base_dir=base_dir,
        self_work_dir=(base_dir.parents[2] / config.self_work_subdir).resolve(),
        official_default=(base_dir / config.official_subpath).resolve(),
        fixed_cases_dirname=config.fixed_cases_dirname,
        official_must_be_file=config.official_must_be_file,
        official_missing_message=config.official_missing_message,
        generator_uses_strict_mutual=config.generator_uses_strict_mutual,
        generator_seed=config.generator_seed,
        generator_limit=config.generator_limit,
        include_fixed_pool=config.include_fixed_pool,
        show_metrics=config.show_metrics,
        show_scores=config.show_scores,
        metric_labels=config.metric_labels,
        score_mode=config.score_mode,
        include_stderr=config.include_stderr,
        custom_placeholder=config.custom_placeholder,
    )


def make_pipeline_window_class(config: PipelinePluginConfig) -> type[StandardJudgeWindow]:
    worker_cls = make_pipeline_worker_class(config)

    class ConfiguredPipelineJudgeWindow(StandardJudgeWindow):
        def __init__(self, parent: QWidget | None = None) -> None:
            base_dir = Path(__file__).resolve().parents[1] / "plugins" / config.hw_id
            super().__init__(
                spec=make_standard_spec(config, base_dir),
                run_config_cls=RunConfig,
                gui_case_cls=GuiCase,
                worker_cls=worker_cls,
                generate_all_func=config.generate_all_func,
                clear_directory_func=config.clear_directory,
                parent=parent,
            )

    ConfiguredPipelineJudgeWindow.__name__ = f"{config.hw_id.upper()}JudgeWindow"
    return ConfiguredPipelineJudgeWindow


def build_pipeline_page(config: PipelinePluginConfig, parent: QWidget) -> QWidget:
    return build_standard_page(make_pipeline_window_class(config), parent)


def run_pipeline_main(config: PipelinePluginConfig) -> None:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = make_pipeline_window_class(config)()
    win.show()
    sys.exit(app.exec_())
