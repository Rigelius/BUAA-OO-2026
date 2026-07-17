#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HW7 Qt GUI judge."""

from __future__ import annotations

import os
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

from judge.core.pipeline_plugin import PipelinePluginConfig, build_pipeline_page, run_pipeline_main
from .generator import generate_all
from .engine import (
    CaseSummary,
    PassengerRequest,
    MaintRequestInput,
    TargetProject,
    TargetRunResult,
    Validator,
    build_input_schedule,
    clear_directory,
    discover_projects,
    normalize_events,
    parse_input_requests,
    run_java_command,
    run_target_case,
    write_problem_case,
    write_summary_report,
)

CONFIG = PipelinePluginConfig(
    hw_id="hw7",
    unit=2,
    title="OO HW7 评测机",
    self_work_subdir="U2/hw7",
    official_subpath="lib/elevator3-2026.jar",
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
    official_must_be_file=True,
    official_missing_message="未找到官方包",
    generator_uses_strict_mutual=True,
    include_fixed_pool=True,
    show_metrics=True,
    show_scores=False,
    metric_labels=("Tr", "Ta", "W", "S"),
    include_stderr=True,
    custom_placeholder="输入完整样例内容",
    score_in_finished_message=True,
    stderr_is_error=True,
)

def build_page(parent: QWidget) -> QWidget:
    return build_pipeline_page(CONFIG, parent)

def main() -> None:
    run_pipeline_main(CONFIG)

if __name__ == "__main__":
    main()
