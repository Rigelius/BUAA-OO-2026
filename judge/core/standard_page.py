#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared Qt window for OO judge plugins.

The engines and workers stay in each HW plugin; this module owns the common
page frame, controls, result table, target cards, logging, and worker wiring.
"""

from __future__ import annotations

import hashlib
import os
import sys
import time
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PyQt5.QtCore import Qt, QThread
from PyQt5.QtGui import QFont, QColor, QBrush
from PyQt5.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
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

from judge.core.target_matching import target_name_matches, target_selection_from_text
from judge.core.models import (
    aggregate_case_status,
    compute_score_across_samples,
    compute_expression_length_score,
    effective_output_length,
    target_status_to_case_code,
)
from judge.core.ui import (
    DARK_COLORS,
    BadgeLabel,
    CaseEditorCard,
    CopyButton,
    StatusChip,
    TargetOutputCard,
    build_dark_stylesheet,
)


@dataclass(frozen=True)
class StandardJudgeSpec:
    hw_id: str
    unit: int
    title: str
    base_dir: Path
    self_work_dir: Path
    official_default: Path
    fixed_cases_dirname: str = "fixed_cases"
    official_label: str = "官方包"
    official_must_be_file: bool = False
    official_missing_message: str = "未找到官方包"
    random_default: int = 8
    timeout_default: str = "180"
    my_target_default: str = "src"
    my_target_placeholder: str = "默认：src；可填写目标名、目录名或 .jar 路径"
    other_targets_default: str = "*"
    other_targets_placeholder: str = "例如：*、互测代码_*、student_[0-9]+、*.jar；支持 glob 和正则"
    target_pattern_self: str = "src"
    target_pattern_mutual: str = "互测代码_*"
    target_pattern_placeholder: str = "例如：src、submissions、submissions/*.jar、submissions/互测代码_[0-9]+"
    custom_placeholder: str = "输入完整样例内容"
    generator_seed: Optional[int] = None
    generator_limit: Optional[int] = None
    generator_uses_strict_mutual: bool = True
    include_fixed_pool: bool = False
    show_official_package: bool = True
    show_metrics: bool = False
    show_scores: bool = False
    include_stderr: bool = False
    metric_labels: Tuple[str, ...] = ("Tr", "Ta", "W")
    score_mode: str = "u2"


class StandardJudgeWindow(QMainWindow):
    def __init__(
        self,
        spec: StandardJudgeSpec,
        run_config_cls: type,
        gui_case_cls: type,
        worker_cls: type,
        generate_all_func: Callable[..., List[str]],
        clear_directory_func: Callable[[Path], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        if parent is None:
            super().__init__()
        else:
            super().__init__(parent, Qt.Widget)
        self.spec = spec
        self.run_config_cls = run_config_cls
        self.gui_case_cls = gui_case_cls
        self.worker_cls = worker_cls
        self.generate_all_func = generate_all_func
        self.clear_directory_func = clear_directory_func

        self.setWindowTitle(spec.title)

        self.base_dir = spec.base_dir.resolve()
        self.fixed_cases_dir = (self.base_dir / spec.fixed_cases_dirname).resolve()
        self.fixed_cases_dir.mkdir(parents=True, exist_ok=True)
        self.ui_font  = QFont("Segoe UI", 10)
        self.code_font = QFont("Consolas", 10)
        self.box_gap = 10

        self.colors = dict(DARK_COLORS)

        # Per-target samples: {target_display_name: [(Tr,Ta,W), ...]} across all cases
        self._target_samples: Dict[str, List[Tuple[float, float, float]]] = {}

        self.case_data: Dict[str, Dict[str, object]] = {}
        self.case_row_to_id: Dict[int, str] = {}
        self.selected_case_id: Optional[str] = None

        self.projects: List[Any] = []
        self.tianquan_name: Optional[str] = None
        self.my_target_default = spec.my_target_default
        self._visible_target_names: set[str] = set()

        self.worker_thread: Optional[QThread] = None
        self.worker: Optional[Any] = None
        self.stop_event = threading.Event()

        self.custom_cards: List[CaseEditorCard] = []
        self.target_cards: Dict[str, TargetOutputCard] = {}

        self._adapt_window_size()
        self._build_ui()
        self._apply_styles()

    def _adapt_window_size(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            self.resize(1400, 860)
            return
        geo = screen.availableGeometry()
        w = min(1600, max(1200, int(geo.width() * 0.80)))
        h = min(960,  max(760,  int(geo.height() * 0.85)))
        self.resize(w, h)
        self.move(geo.x() + (geo.width() - w) // 2, geo.y() + (geo.height() - h) // 2)

    # UI construction

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        main = QHBoxLayout(root)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(self.box_gap)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        main.addWidget(splitter)

        left = QWidget()
        right = QWidget()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([390, 1190])
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)

        self._build_left(left)
        self._build_right(right)

    def _build_left(self, parent: QWidget) -> None:
        self.left_layout = QVBoxLayout(parent)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(self.box_gap)

        cfg_box = QGroupBox("评测配置")
        cfg = QVBoxLayout(cfg_box)
        cfg.setSpacing(self.box_gap)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("目标路径"))
        self.edt_pattern = QLineEdit(self.spec.target_pattern_self)
        self.edt_pattern.setFont(self.code_font)
        self.edt_pattern.setMinimumWidth(240)
        self.edt_pattern.setPlaceholderText(self.spec.target_pattern_placeholder)
        r1.addWidget(self.edt_pattern)
        r1.addStretch(1)
        cfg.addLayout(r1)

        self.lbl_target_hint = QLabel("")
        self.lbl_target_hint.setObjectName("muted")
        self.lbl_target_hint.setWordWrap(True)
        self.lbl_target_hint.setMinimumHeight(40)
        cfg.addWidget(self.lbl_target_hint)

        r2 = QHBoxLayout()
        r2.setSpacing(8)
        self.chk_fixed  = QCheckBox("固定样例")
        self.chk_random = QCheckBox("随机样例")
        self.chk_custom = QCheckBox("自定义样例")
        self.chk_custom_into_fixed = QCheckBox("加入固定样例")
        self.chk_fixed.setChecked(True)
        self.chk_custom.setChecked(True)
        self.chk_custom_into_fixed.setEnabled(True)
        r2.addWidget(self.chk_fixed)
        r2.addWidget(self.chk_random)
        r2.addWidget(QLabel("随机数量"))
        self.spn_random = QSpinBox()
        self.spn_random.setRange(0, 2147483647)
        self.spn_random.setValue(self.spec.random_default)
        self.spn_random.setFixedWidth(86)
        self.spn_random.setFont(self.code_font)
        r2.addWidget(self.spn_random)
        r2.addWidget(self.chk_custom)
        r2.addWidget(self.chk_custom_into_fixed)
        r2.addStretch(1)
        cfg.addLayout(r2)

        r3 = QHBoxLayout()
        r3.addWidget(QLabel("我的目标"))
        self.edt_my_target = QLineEdit(self.my_target_default)
        self.edt_my_target.setFont(self.code_font)
        self.edt_my_target.setMinimumWidth(130)
        self.edt_my_target.setPlaceholderText(self.spec.my_target_placeholder)
        r3.addWidget(self.edt_my_target)
        r3.addSpacing(10)
        r3.addWidget(QLabel("其余目标"))
        self.edt_other_targets = QLineEdit(self.spec.other_targets_default)
        self.edt_other_targets.setFont(self.code_font)
        self.edt_other_targets.setMinimumWidth(130)
        self.edt_other_targets.setPlaceholderText(self.spec.other_targets_placeholder)
        r3.addWidget(self.edt_other_targets)
        r3.addStretch(1)
        cfg.addLayout(r3)

        r4 = QHBoxLayout()
        r4.addWidget(QLabel("超时"))
        self.edt_timeout = QLineEdit(self.spec.timeout_default)
        self.edt_timeout.setFont(self.code_font)
        self.edt_timeout.setFixedWidth(60)
        r4.addWidget(self.edt_timeout)
        r4.addStretch(1)
        cfg.addLayout(r4)

        r5 = QHBoxLayout()
        r5.addWidget(QLabel(self.spec.official_label))
        self.edt_jar = QLineEdit(str(self.spec.official_default.resolve()))
        self.edt_jar.setFont(self.code_font)
        r5.addWidget(self.edt_jar)
        if self.spec.show_official_package:
            cfg.addLayout(r5)

        r6 = QHBoxLayout()
        self.btn_start = QPushButton("▶  开始评测")
        self.btn_start.setObjectName("primaryBtn")
        self.btn_stop = QPushButton("■  停止")
        self.btn_stop.setObjectName("dangerBtn")
        self.btn_stop.setEnabled(False)
        self.btn_clear = QPushButton("清空")
        self.btn_clear.setObjectName("ghostBtn")
        r6.addWidget(self.btn_start)
        r6.addWidget(self.btn_stop)
        r6.addWidget(self.btn_clear)
        r6.addStretch(1)
        self.lbl_run_status = QLabel("准备就绪")
        self.lbl_run_status.setObjectName("muted")
        r6.addWidget(self.lbl_run_status)
        cfg.addLayout(r6)

        self.left_layout.addWidget(cfg_box)

        # Custom cases
        self.custom_box = QGroupBox("自定义样例")
        custom = QVBoxLayout(self.custom_box)
        custom.setSpacing(self.box_gap)
        ctop = QHBoxLayout()
        self.btn_add_case = QPushButton("＋ 新增输入框")
        self.btn_add_case.setObjectName("ghostBtn")
        self.btn_reset_custom = QPushButton("重置示例")
        self.btn_reset_custom.setObjectName("ghostBtn")
        ctop.addWidget(self.btn_add_case)
        ctop.addWidget(self.btn_reset_custom)
        ctop.addStretch(1)
        custom.addLayout(ctop)

        self.custom_scroll = QScrollArea()
        self.custom_scroll.setWidgetResizable(True)
        self.custom_scroll.setObjectName("customScroll")
        self.custom_inner = QWidget()
        self.custom_layout = QVBoxLayout(self.custom_inner)
        self.custom_layout.setContentsMargins(6, 6, 6, 6)
        self.custom_layout.setSpacing(self.box_gap)
        self.custom_layout.addStretch(1)
        self.custom_scroll.setWidget(self.custom_inner)
        custom.addWidget(self.custom_scroll)
        self.left_layout.addWidget(self.custom_box, stretch=3)

        # Case results table (3 cols: 样例 / 来源 / 判定)
        self.cases_box = QGroupBox("样例结果")
        cases = QVBoxLayout(self.cases_box)
        cases.setSpacing(self.box_gap)
        self.tbl_cases = QTableWidget(0, 3)
        self.tbl_cases.setHorizontalHeaderLabels(["样例", "来源", "判定"])
        self.tbl_cases.verticalHeader().setVisible(False)
        self.tbl_cases.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_cases.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_cases.setAlternatingRowColors(True)
        self.tbl_cases.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in [1, 2]:
            self.tbl_cases.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        cases.addWidget(self.tbl_cases)
        self.left_layout.addWidget(self.cases_box, stretch=2)

        # My output (manual target)
        self.mine_box = QGroupBox("我的输出")
        mine = QVBoxLayout(self.mine_box)
        mine.setSpacing(self.box_gap)

        # Title row with chip + score
        mtop = QHBoxLayout()
        mtop.setSpacing(6)
        self.lbl_tq_title = QLabel(self.my_target_default)
        self.lbl_tq_title.setObjectName("targetTitle")
        mtop.addWidget(self.lbl_tq_title)
        self.tq_chip = QLabel("···")
        self.tq_chip.setAlignment(Qt.AlignCenter)
        self.tq_chip.setStyleSheet(
            "background:#37474F;color:#B0BEC5;border-radius:8px;"
            "padding:2px 8px;font-weight:800;font-size:9pt;min-width:30px;"
        )
        mtop.addWidget(self.tq_chip)
        self.tq_score = QLabel("")
        self.tq_score.setStyleSheet(
            "color:#90CAF9;font-weight:700;font-size:9pt;background:transparent;"
        )
        self.tq_score.setVisible(self.spec.show_scores)
        mtop.addStretch(1)
        self.btn_copy_tianquan = CopyButton()
        mtop.addWidget(self.btn_copy_tianquan)
        mine.addLayout(mtop)

        # Metrics row
        self.tq_metrics_widget = QWidget()
        mmetrics = QHBoxLayout(self.tq_metrics_widget)
        mmetrics.setContentsMargins(0, 0, 0, 0)
        mmetrics.setSpacing(4)
        self.tq_metric_labels: List[QLabel] = []
        for idx, name in enumerate(self.spec.metric_labels):
            if idx:
                mmetrics.addWidget(self._sep())
            lbl = self._make_metric_lbl(name, "—")
            self.tq_metric_labels.append(lbl)
            mmetrics.addWidget(lbl)
        mmetrics.addStretch(1)
        mine.addWidget(self.tq_metrics_widget)
        self.tq_metrics_widget.setVisible(self.spec.show_metrics)

        self.txt_tianquan = QPlainTextEdit()
        self.txt_tianquan.setReadOnly(True)
        self.txt_tianquan.setObjectName("output")
        self.txt_tianquan.setFont(self.code_font)
        mine.addWidget(self.txt_tianquan)

        self.left_layout.addWidget(self.mine_box, stretch=3)

        # Signals
        self.btn_start.clicked.connect(self.on_start)
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_clear.clicked.connect(self.on_clear)
        self.edt_pattern.textChanged.connect(self.on_target_path_changed)
        self.edt_my_target.textChanged.connect(self.on_my_target_changed)
        self.edt_other_targets.textChanged.connect(self.on_other_targets_changed)
        self.btn_add_case.clicked.connect(lambda _=False: self.add_custom_case_card())
        self.btn_reset_custom.clicked.connect(self.reset_custom_examples)
        self.chk_custom.toggled.connect(self.on_custom_mode_changed)
        self.tbl_cases.itemSelectionChanged.connect(self.on_case_selected)
        self.btn_copy_tianquan.clicked.connect(
            lambda: self.copy_from_editor(self.txt_tianquan, self.btn_copy_tianquan)
        )
        self.reset_custom_examples()
        self.on_custom_mode_changed(self.chk_custom.isChecked())
        self.on_target_path_changed(self.edt_pattern.text())

    # table verdict helpers
    _VERDICT_CHIP = {
        "AC":  ("AC",  "#1B5E20", "#C8E6C9"),
        "WA":  ("WA",  "#7B1D1D", "#FFCDD2"),
        "TLE": ("TLE", "#4A3000", "#FFE0B2"),
        "RE":  ("RE",  "#4A004A", "#E1BEE7"),
        "IE":  ("IE",  "#283593", "#C5CAE9"),
        "STOP":("STOP","#455A64", "#CFD8DC"),
        "RUNNING": ("...", "#1A3A6B", "#9EC8FF"),
        "...": ("···", "#37474F", "#B0BEC5"),
    }

    def _make_verdict_widget(self, key: str, score: Optional[float] = None) -> QWidget:
        """Return a small widget with a coloured chip + optional score for the table cell."""
        label_text, bg, fg = self._VERDICT_CHIP.get(key, self._VERDICT_CHIP["..."])
        if self.spec.show_scores and score is not None:
            label_text += f"  S:{score:.1f}"
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(0)
        w = QLabel(label_text)
        w.setAlignment(Qt.AlignCenter)
        w.setMinimumWidth(42)
        w.setStyleSheet(
            f"background:{bg};color:{fg};border-radius:8px;"
            "padding:2px 6px;font-weight:800;font-size:9pt;"
        )
        lay.addStretch(1)
        lay.addWidget(w)
        lay.addStretch(1)
        return wrap

    @staticmethod
    def _make_metric_lbl(name: str, val: str) -> QLabel:
        lbl = QLabel(f"{name}  {val}")
        lbl.setObjectName("metricPill")
        lbl.setStyleSheet(
            "background:#262C3A;color:#8FA8C8;border-radius:6px;"
            "padding:2px 8px;font-size:8pt;font-weight:600;"
        )
        return lbl

    @staticmethod
    def _sep() -> QLabel:
        s = QLabel("·")
        s.setStyleSheet("color:#485162;background:transparent;font-size:10pt;")
        return s

    def _build_right(self, parent: QWidget) -> None:
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.box_gap)

        current_box = QGroupBox("当前样例")
        current = QVBoxLayout(current_box)

        top = QHBoxLayout()
        self.lbl_case_name = QLabel("未选择样例")
        self.lbl_case_name.setObjectName("subTitle")
        top.addWidget(self.lbl_case_name)
        top.addStretch(1)
        self.btn_copy_case_input = CopyButton()
        top.addWidget(self.btn_copy_case_input)
        current.addLayout(top)

        badge_row = QHBoxLayout()
        self.badge_source  = BadgeLabel("来源")
        self.badge_status  = BadgeLabel("状态")
        for b in [self.badge_source, self.badge_status]:
            badge_row.addWidget(b)
        badge_row.addStretch(1)
        current.addLayout(badge_row)

        self.txt_case_input = QPlainTextEdit()
        self.txt_case_input.setReadOnly(True)
        self.txt_case_input.setObjectName("editor")
        self.txt_case_input.setFont(self.code_font)
        current.addWidget(self.txt_case_input)

        layout.addWidget(current_box, stretch=2)

        others_box = QGroupBox("其余目标输出")
        others = QVBoxLayout(others_box)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self.targets_panel = QWidget()
        self.targets_grid = QGridLayout(self.targets_panel)
        self.targets_grid.setContentsMargins(4, 4, 4, 4)
        self.targets_grid.setHorizontalSpacing(self.box_gap)
        self.targets_grid.setVerticalSpacing(self.box_gap)
        scroll.setWidget(self.targets_panel)
        others.addWidget(scroll)
        layout.addWidget(others_box, stretch=7)

        log_box = QGroupBox("运行日志")
        log = QVBoxLayout(log_box)
        ltop = QHBoxLayout()
        self.lbl_log_title = QLabel("日志")
        self.lbl_log_title.setObjectName("muted")
        ltop.addWidget(self.lbl_log_title)
        ltop.addStretch(1)
        self.btn_copy_log = CopyButton()
        ltop.addWidget(self.btn_copy_log)
        log.addLayout(ltop)
        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setObjectName("output")
        self.txt_log.setFont(self.code_font)
        log.addWidget(self.txt_log)
        layout.addWidget(log_box, stretch=2)

        self.btn_copy_case_input.clicked.connect(
            lambda: self.copy_from_editor(self.txt_case_input, self.btn_copy_case_input)
        )
        self.btn_copy_log.clicked.connect(
            lambda: self.copy_from_editor(self.txt_log, self.btn_copy_log)
        )

    # Styles

    def _apply_styles(self) -> None:
        self.setFont(self.ui_font)
        self.setStyleSheet(build_dark_stylesheet(self.colors))

    # Helpers

    def compute_workers(self, project_count: int) -> int:
        cpu = os.cpu_count() or 2
        return max(1, min(4, cpu - 1 if cpu > 1 else 1, project_count))

    def current_mode(self) -> str:
        return "path"

    def resolve_work_dir(self, mode: Optional[str] = None) -> Path:
        work_dir, _pattern = self.resolve_target_selection()
        return work_dir

    def default_pattern_for_mode(self, mode: Optional[str] = None) -> str:
        return self.spec.target_pattern_self

    def resolve_target_selection(self, text: Optional[str] = None) -> Tuple[Path, str]:
        raw = self.edt_pattern.text().strip() if text is None else text
        return target_selection_from_text(
            raw,
            self.spec.target_pattern_self,
            (
                self.spec.self_work_dir.resolve(),
                self.base_dir.resolve(),
                Path(__file__).resolve().parents[2],
            ),
        )

    def is_mutual_target_path(self) -> bool:
        work_dir, pattern = self.resolve_target_selection()
        default_src = (self.spec.self_work_dir.resolve() / self.spec.target_pattern_self).resolve()
        try:
            pattern_path = Path(pattern).resolve() if Path(pattern).is_absolute() else (work_dir / pattern).resolve()
        except OSError:
            pattern_path = work_dir / pattern
        return pattern_path != default_src

    def current_my_target_keyword(self) -> str:
        text = self.edt_my_target.text().strip()
        if text:
            return text
        return text if text else self.my_target_default

    def current_other_target_pattern(self) -> str:
        return self.edt_other_targets.text().strip() or self.spec.other_targets_default

    def resolve_my_target_name(self, target_names: List[str]) -> Optional[str]:
        if not target_names:
            return None
        keyword = self.current_my_target_keyword()
        keyword_path = Path(keyword)
        candidates = [keyword]
        path_name = keyword_path.name
        if path_name and path_name not in candidates:
            candidates.append(path_name)
        path_stem = keyword_path.stem
        if path_stem and path_stem not in candidates:
            candidates.append(path_stem)
        for candidate in candidates:
            for name in target_names:
                if name == candidate:
                    return name
        for candidate in candidates:
            for name in target_names:
                if candidate and candidate in name:
                    return name
        return None

    def is_other_target_visible(self, target_name: str) -> bool:
        pattern_text = self.current_other_target_pattern()
        parts = [p.strip() for p in pattern_text.replace(",", ";").split(";") if p.strip()]
        if not parts:
            return True
        return any(target_name_matches(target_name, part) for part in parts)

    def visible_targets_map(self, targets_map: Dict[str, Any]) -> Dict[str, Any]:
        if not self._visible_target_names:
            return dict(targets_map)
        return {
            name: rr
            for name, rr in targets_map.items()
            if name in self._visible_target_names
        }

    def refresh_my_target_header(self, resolved_name: Optional[str] = None) -> None:
        title = resolved_name if resolved_name else self.current_my_target_keyword()
        self.lbl_tq_title.setText(title)
        self.mine_box.setTitle("我的输出")

    def on_target_path_changed(self, text: str) -> None:
        work_dir, pattern = self.resolve_target_selection(text)
        display = pattern if len(pattern) <= 42 else "..." + pattern[-39:]
        self.lbl_target_hint.setText(f"扫描目录：{work_dir}\n目标匹配：{display}")

    def on_my_target_changed(self, _text: str) -> None:
        self.refresh_my_target_header(self.tianquan_name)
        if self.projects:
            names = [p.display_name for p in self.projects]
            self.rebuild_target_cards(names)
            self.refresh_case_verdict_rows()
            if self.selected_case_id:
                self.show_case(self.selected_case_id)

    def on_other_targets_changed(self, _text: str) -> None:
        if self.projects:
            names = [p.display_name for p in self.projects]
            self.rebuild_target_cards(names)
            self.refresh_case_verdict_rows()
            if self.selected_case_id:
                self.show_case(self.selected_case_id)

    def copy_from_editor(self, editor: QPlainTextEdit, btn: CopyButton) -> None:
        QApplication.clipboard().setText(editor.toPlainText())
        btn.flash_done()

    def add_custom_case_card(self, text: str = "", title: Optional[str] = None) -> None:
        if isinstance(text, bool):
            text = ""
        card_id    = f"custom_{int(time.time() * 1000)}_{len(self.custom_cards)}"
        card_title = title if title else f"自定义样例 {len(self.custom_cards) + 1}"
        card = CaseEditorCard(
            card_id,
            card_title,
            self.code_font,
            text=text,
            placeholder=self.spec.custom_placeholder,
        )
        card.remove_requested.connect(self.remove_custom_case_card)
        card.copy_btn.clicked.connect(
            lambda _=False, e=card.editor, b=card.copy_btn: self.copy_from_editor(e, b)
        )
        self.custom_cards.append(card)
        self.custom_layout.insertWidget(self.custom_layout.count() - 1, card)
        self.refresh_custom_titles()

    def remove_custom_case_card(self, card_id: str) -> None:
        if len(self.custom_cards) <= 1:
            QMessageBox.information(self, "提示", "至少保留一个输入框")
            return
        target = next((c for c in self.custom_cards if c.card_id == card_id), None)
        if target is None:
            return
        self.custom_cards.remove(target)
        target.setParent(None)
        target.deleteLater()
        self.refresh_custom_titles()

    def refresh_custom_titles(self) -> None:
        for idx, c in enumerate(self.custom_cards, start=1):
            c.set_title(f"自定义样例 {idx}")

    def on_custom_mode_changed(self, checked: bool) -> None:
        self.update_custom_section_visibility(checked)
        self.chk_custom_into_fixed.setEnabled(checked)
        if not checked:
            self.chk_custom_into_fixed.setChecked(False)

    def update_custom_section_visibility(self, checked: bool) -> None:
        self.custom_box.setVisible(checked)
        if checked:
            self.left_layout.setStretchFactor(self.custom_box, 3)
            self.left_layout.setStretchFactor(self.cases_box, 2)
        else:
            self.left_layout.setStretchFactor(self.custom_box, 0)
            self.left_layout.setStretchFactor(self.cases_box, 5)
        self.left_layout.setStretchFactor(self.mine_box, 3)

    def reset_custom_examples(self) -> None:
        for c in self.custom_cards:
            c.setParent(None)
            c.deleteLater()
        self.custom_cards.clear()
        self.add_custom_case_card(text="")

    def _collect_custom_inputs(self) -> List[Tuple[int, str]]:
        custom_inputs: List[Tuple[int, str]] = []
        idx = 0
        for card in self.custom_cards:
            txt = card.get_text().strip()
            if not txt:
                continue
            idx += 1
            if not txt.endswith("\n"):
                txt += "\n"
            custom_inputs.append((idx, txt))
        return custom_inputs

    def persist_custom_cases_to_fixed_pool(self, custom_inputs: List[Tuple[int, str]]) -> None:
        self.fixed_cases_dir.mkdir(parents=True, exist_ok=True)
        for idx, txt in custom_inputs:
            digest = hashlib.sha1(txt.encode("utf-8", errors="replace")).hexdigest()[:12]
            fp = self.fixed_cases_dir / f"user_custom_{digest}.txt"
            if not fp.exists():
                fp.write_text(txt, encoding="utf-8", errors="replace")

    def load_fixed_pool_cases(self) -> List[Any]:
        if not self.fixed_cases_dir.is_dir():
            return []
        cases: List[Any] = []
        for idx, fp in enumerate(sorted(self.fixed_cases_dir.glob("*.txt")), start=1):
            text = fp.read_text(encoding="utf-8", errors="replace")
            cases.append(self.gui_case_cls(
                case_id=f"fixed_pool::{idx:02d}::{fp.name}",
                display_name=fp.name,
                source="fixed",
                input_text=text,
            ))
        return cases

    def append_log(self, text: str) -> None:
        self.txt_log.appendPlainText(f"[{time.strftime('%H:%M:%S')}] {text}")

    def source_to_cn(self, source: str) -> str:
        return {"fixed": "固定", "random": "随机", "custom": "自定义"}.get(source, source)

    def status_to_cn(self, status: str) -> str:
        return {
            "PASSED":       "通过",
            "WRONG_ANSWER": "输出不合法",
            "TIMEOUT_SOFT": "软超时",
            "TIMEOUT_HARD": "硬超时",
            "RUNTIME_ERROR": "运行错误",
            "INPUT_ERROR":  "输入错误",
            "JAVA_ERROR":   "Java环境错误",
            "EXEC_ERROR":   "执行错误",
            "SKIPPED_STOP": "已停止",
            "AC":           "AC",
            "WA":           "WA",
            "TLE":          "TLE",
            "RE":           "RE",
            "IE":           "IE",
            "STOP":         "STOP",
            "RUNNING":      "运行中",
            "DONE":         "完成",
            "N/A":          "未运行",
        }.get(status, status)

    def status_to_chip(self, rr: Optional[Any]) -> str:
        """Convert TargetRunResult status to short chip key."""
        if rr is None:
            return "..."
        return target_status_to_case_code(rr.status)

    def note_to_cn(self, text: str) -> str:
        mapping = {
            "java command not found": "未找到 Java 命令",
            "hard timeout exceeded":  "超过硬超时",
            "soft timeout exceeded":  "超过软超时",
            "runtime error":          "运行时错误",
            "no output":              "无输出",
            "stderr is non-empty":    "标准错误非空",
        }
        out = text
        for en, cn in mapping.items():
            out = out.replace(en, cn)
        return out

    def format_output(self, rr: Optional[Any]) -> str:
        if rr is None:
            return ""
        chunks: List[str] = []
        if rr.stdout.strip():
            chunks.append(rr.stdout.rstrip("\n"))
        if self.spec.include_stderr and rr.stderr.strip():
            chunks.append("--- 标准错误 ---\n" + rr.stderr.rstrip("\n"))
        if rr.errors:
            chunks.append("--- 校验备注 ---\n" + "\n".join(self.note_to_cn(e) for e in rr.errors))
        return "\n\n".join(chunks).strip()

    def set_badges(self, source: str, status: str,
                   all_correct: object, all_consistent: object) -> None:
        self.badge_source.set_badge(f"来源 {self.source_to_cn(source)}", "info")

        status_cn   = self.status_to_cn(status)
        status_kind = {
            "AC": "ok",
            "WA": "bad",
            "TLE": "warn",
            "RE": "bad",
            "IE": "info",
            "STOP": "warn",
            "RUNNING": "info",
            "N/A": "neutral",
        }.get(status, "info")
        self.badge_status.set_badge(f"状态 {status_cn}", status_kind)

    # Score computation helpers

    def _get_case_verdict_chip(self, verdict: str) -> Tuple[str, str, str]:
        """Return (text, bg_color, fg_color) for table verdict cell."""
        return self._VERDICT_CHIP.get(verdict, self._VERDICT_CHIP["..."])

    def _aggregate_case_verdict(self, targets_map: Dict[str, Any]) -> str:
        return aggregate_case_status(targets_map)

    def _compute_case_scores(self, targets_map: Dict[str, Any]) -> Dict[str, float]:
        if not self.spec.show_scores:
            return {}
        if self.spec.score_mode == "expression_length":
            lengths = {
                k: effective_output_length(v.stdout)
                for k, v in targets_map.items()
                if v and v.status == "PASSED"
            }
            if not lengths:
                return {}
            best = min(lengths.values())
            return {k: compute_expression_length_score(length, best) for k, length in lengths.items()}
        samples = []
        keys = []
        for k, v in targets_map.items():
            if v and v.status == "PASSED":
                samples.append((v.sim_time, v.avg_time, v.power))
                keys.append(k)
        if not samples:
            return {}
        s_list = compute_score_across_samples(samples)
        return dict(zip(keys, s_list))

    def _metric_values(
        self,
        rr: Optional[Any],
        targets_map: Optional[Dict[str, Any]] = None,
    ) -> Optional[List[Tuple[str, str, bool]]]:
        if not self.spec.show_metrics or rr is None:
            return None
        if self.spec.score_mode == "expression_length":
            length = effective_output_length(rr.stdout)
            elapsed = getattr(rr, "elapsed_sec", None)
            best: Optional[int] = None
            if targets_map:
                passed_lengths = [
                    effective_output_length(v.stdout)
                    for v in targets_map.values()
                    if v and v.status == "PASSED"
                ]
                if passed_lengths:
                    best = min(passed_lengths)
            score = compute_expression_length_score(length, best) if best else None
            return [
                (self.spec.metric_labels[0], str(length), True),
                (
                    self.spec.metric_labels[1],
                    f"{elapsed:.3f}s" if elapsed is not None else "—",
                    elapsed is not None,
                ),
                (
                    self.spec.metric_labels[2],
                    f"{score:.2f}" if score is not None else "—",
                    score is not None,
                ),
            ]
        if self.spec.score_mode == "elapsed":
            elapsed = getattr(rr, "elapsed_sec", None)
            return [
                (
                    self.spec.metric_labels[0],
                    f"{elapsed:.3f}s" if elapsed is not None else "—",
                    elapsed is not None,
                )
            ]
        sim_time = getattr(rr, "sim_time", None)
        avg_time = getattr(rr, "avg_time", None)
        power = getattr(rr, "power", None)
        values = [
            (self.spec.metric_labels[0], f"{sim_time:.3f}s" if sim_time is not None else "—", sim_time is not None),
            (self.spec.metric_labels[1], f"{avg_time:.3f}s" if avg_time is not None else "—", avg_time is not None),
            (self.spec.metric_labels[2], f"{power:.2f}" if power is not None else "—", power is not None),
        ]
        if len(self.spec.metric_labels) >= 4:
            score: Optional[float] = None
            if targets_map:
                keys = []
                samples = []
                current_key = None
                for key, value in targets_map.items():
                    if value is rr:
                        current_key = key
                    if value and value.status == "PASSED":
                        keys.append(key)
                        samples.append((value.sim_time, value.avg_time, value.power))
                if samples:
                    score_map = dict(zip(keys, compute_score_across_samples(samples)))
                    if current_key is not None:
                        score = score_map.get(current_key)
            values.append((
                self.spec.metric_labels[3],
                f"{score:.2f}" if score is not None else "—",
                score is not None,
            ))
        return values

    # Config/case collection

    def collect_run_config(self) -> Any:
        try:
            timeout = float(self.edt_timeout.text().strip())
        except ValueError as exc:
            raise ValueError("超时必须为数字") from exc
        if timeout <= 0:
            raise ValueError("超时必须为正数")

        soft = timeout
        hard = timeout
        comp = timeout

        jar = Path(self.edt_jar.text().strip()).resolve()
        if self.spec.official_must_be_file:
            missing = not jar.is_file()
        else:
            missing = not jar.exists()
        if missing:
            raise ValueError(f"{self.spec.official_missing_message} {jar}")

        work_dir, pattern = self.resolve_target_selection()
        max_workers = self.compute_workers(8)

        return self.run_config_cls(
            co_judge_dir=work_dir,
            official_jar=jar,
            build_dir=(self.base_dir / ".build_targets").resolve(),
            out_dir=(self.base_dir / "out_raw").resolve(),
            report_dir=(self.base_dir / "report").resolve(),
            problem_dir=(self.base_dir / "problem_cases").resolve(),
            target_pattern=pattern,
            soft_timeout=soft,
            hard_timeout=hard,
            compile_timeout=comp,
            max_workers=max_workers,
            mutual_mode=self.is_mutual_target_path(),
        )

    def collect_cases(self) -> List[Any]:
        cases: List[Any] = []
        use_fixed  = self.chk_fixed.isChecked()
        use_random = self.chk_random.isChecked()
        use_custom = self.chk_custom.isChecked()
        add_custom_to_fixed = self.chk_custom_into_fixed.isChecked()

        custom_inputs: List[Tuple[int, str]] = []
        if use_custom or add_custom_to_fixed:
            custom_inputs = self._collect_custom_inputs()

        if add_custom_to_fixed and custom_inputs:
            self.persist_custom_cases_to_fixed_pool(custom_inputs)

        if use_fixed or use_random:
            temp = (self.base_dir / ".gui_tmp_cases").resolve()
            temp.mkdir(parents=True, exist_ok=True)
            self.clear_directory_func(temp)
            generated = self._generate_cases(temp, self.spn_random.value() if use_random else 0)

            if use_fixed:
                # All generated cases that are NOT random are considered 'fixed' samples
                for name in [n for n in generated if "_random_" not in n]:
                    p = temp / name
                    if p.is_file():
                        txt = p.read_text(encoding="utf-8", errors="replace")
                        cases.append(self.gui_case_cls(
                            case_id=f"fixed::{name}", display_name=name,
                            source="fixed", input_text=txt
                        ))

                if self.spec.include_fixed_pool:
                    cases.extend(self.load_fixed_pool_cases())

            if use_random:
                for name in [n for n in generated if "_random_" in n]:
                    p = temp / name
                    if p.is_file():
                        txt = p.read_text(encoding="utf-8", errors="replace")
                        cases.append(self.gui_case_cls(
                            case_id=f"random::{name}", display_name=name,
                            source="random", input_text=txt
                        ))

        if use_custom:
            for idx, txt in custom_inputs:
                name = f"custom_{idx:02d}.txt"
                cases.append(self.gui_case_cls(
                    case_id=f"custom::{idx:02d}", display_name=name,
                    source="custom", input_text=txt
                ))

        return cases

    def _generate_cases(self, temp: Path, random_count: int) -> List[str]:
        if self.spec.generator_uses_strict_mutual:
            return self.generate_all_func(
                str(temp),
                random_count,
                strict_mutual=self.is_mutual_target_path(),
            )
        args: List[Any] = [str(temp), random_count]
        if self.spec.generator_seed is not None:
            args.append(self.spec.generator_seed)
        if self.spec.generator_limit is not None:
            args.append(self.spec.generator_limit)
        return self.generate_all_func(*args)

    def create_worker(self, cfg: Any, cases: List[Any]) -> Any:
        return self.worker_cls(cfg, cases, self.stop_event)

    # Event handlers

    def on_start(self) -> None:
        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.information(self, "提示", "已有评测任务在运行")
            return
        try:
            cfg   = self.collect_run_config()
            cases = self.collect_cases()
        except Exception as exc:
            QMessageBox.critical(self, "配置错误", str(exc))
            return
        if not cases:
            QMessageBox.warning(self, "无样例", "请至少勾选一种样例来源并准备样例")
            return

        self.on_clear(reset_custom=False)
        self._target_samples.clear()
        self.stop_event.clear()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl_run_status.setText("评测中…")

        self.worker_thread = QThread(self)
        self.worker = self.create_worker(cfg, cases)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.sig_log.connect(self.on_worker_log)
        self.worker.sig_targets.connect(self.on_worker_targets)
        self.worker.sig_case_started.connect(self.on_worker_case_started)
        self.worker.sig_target_done.connect(self.on_worker_target_done)
        self.worker.sig_case_done.connect(self.on_worker_case_done)
        self.worker.sig_finished.connect(self.on_worker_finished)
        self.worker.sig_error.connect(self.on_worker_error)

        self.worker.sig_finished.connect(self.worker.deleteLater)
        self.worker.sig_error.connect(self.worker.deleteLater)
        self.worker.sig_finished.connect(self.worker_thread.quit)
        self.worker.sig_error.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.on_worker_thread_finished)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.start()

    def on_stop(self) -> None:
        self.stop_event.set()
        self.append_log("已请求停止：当前正在执行的目标结束后终止")

    def on_clear(self, reset_custom: bool = False) -> None:
        self.tbl_cases.setRowCount(0)
        self.case_data.clear()
        self.case_row_to_id.clear()
        self.selected_case_id = None
        self._target_samples.clear()

        self.lbl_case_name.setText("未选择样例")
        self.txt_case_input.setPlainText("")
        self.set_badges("-", "N/A", None, None)  # reset source/status badges

        self._reset_tq_metrics()
        self.txt_tianquan.setPlainText("")

        self.txt_log.setPlainText("")
        self.clear_target_cards()
        self.lbl_run_status.setText("准备就绪")

        if reset_custom:
            self.reset_custom_examples()

    def _reset_tq_metrics(self) -> None:
        self._set_tq_chip("···", "#37474F", "#B0BEC5")
        self.tq_score.setText("")
        for lbl, name in zip(self.tq_metric_labels, self.spec.metric_labels):
            lbl.setText(f"{name}  —")
            lbl.setStyleSheet(
                "background:#262C3A;color:#8FA8C8;border-radius:6px;"
                "padding:2px 8px;font-size:8pt;font-weight:600;"
            )

    def _set_tq_chip(self, text: str, bg: str, fg: str) -> None:
        self.tq_chip.setText(text)
        self.tq_chip.setStyleSheet(
            f"background:{bg};color:{fg};border-radius:8px;"
            "padding:2px 8px;font-weight:800;font-size:9pt;min-width:30px;"
        )

    def clear_target_cards(self) -> None:
        self.tianquan_name = None
        self._visible_target_names.clear()
        self.refresh_my_target_header(None)
        self.target_cards.clear()
        while self.targets_grid.count():
            item   = self.targets_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    # Worker signal handlers

    def on_worker_log(self, text: str) -> None:
        self.append_log(text)

    def on_worker_targets(self, projects_obj: object) -> None:
        self.projects = list(projects_obj)
        names = [p.display_name for p in self.projects]
        self.rebuild_target_cards(names)
        visible = [n for n in names if n in self._visible_target_names]
        self.append_log("已加载目标: " + ", ".join(names))
        self.append_log("当前参与展示/汇总: " + (", ".join(visible) if visible else "无"))

    def on_worker_case_started(self, payload: object) -> None:
        data = dict(payload)
        case: Any = data["case"]
        idx   = data["index"]
        total = data["total"]

        self.case_data[case.case_id] = {
            "display_name": case.display_name,
            "source":       case.source,
            "input_text":   case.input_text,
            "targets":      {},
            "scores":       {},   # target_name -> latest score
            "all_correct":  None,
            "all_consistent": None,
            "effective":    None,
            "case_verdict": "...",
            "status":       "RUNNING",
        }

        row = self.tbl_cases.rowCount()
        self.tbl_cases.insertRow(row)
        self.case_row_to_id[row] = case.case_id

        # cols: 样例 / 来源 / 判定
        for c, v in enumerate([case.display_name, self.source_to_cn(case.source), "运行中"]):
            item = QTableWidgetItem(v)
            item.setTextAlignment(Qt.AlignCenter)
            if c == 2:  # 判定
                item.setBackground(QBrush(QColor(self.colors["info"])))
                item.setForeground(QBrush(QColor("#ffffff")))
            self.tbl_cases.setItem(row, c, item)
        self.tbl_cases.setCellWidget(row, 2, self._make_verdict_widget("RUNNING"))

        self.lbl_run_status.setText(f"正在执行样例 {idx}/{total}")
        self.append_log(f"开始样例 [{idx}/{total}] {case.display_name}")

        if self.selected_case_id is None:
            self.tbl_cases.selectRow(row)
            self.show_case(case.case_id)

    def on_worker_target_done(self, case_id: str, target_name: str, rr_obj: object) -> None:
        rr: Any = rr_obj
        item = self.case_data.get(case_id)
        if item is None:
            return
        targets_map: Dict[str, Any] = item["targets"]  # type: ignore
        targets_map[target_name] = rr

        if self.selected_case_id == case_id:
            # We skip score computation here, the case isn't fully completed yet.
            self.show_target_result(target_name, rr)

    def on_worker_case_done(self, case_id: str,
                            all_correct: bool, all_consistent: bool = True,
                            effective: bool = True) -> None:
        item = self.case_data.get(case_id)
        if item is None:
            return

        item["all_correct"]    = all_correct
        item["all_consistent"] = all_consistent
        item["effective"]      = effective

        targets_map: Dict[str, Any] = item["targets"]  # type: ignore
        visible_targets = self.visible_targets_map(targets_map)
        case_verdict = self._aggregate_case_verdict(visible_targets)
        item["case_verdict"] = case_verdict
        item["status"] = case_verdict

        row = None
        for r, cid in self.case_row_to_id.items():
            if cid == case_id:
                row = r
                break

        if row is not None:
            # col 2 = 判定
            verdict_text, verdict_bg, verdict_fg = self._get_case_verdict_chip(case_verdict)
            verdict_item = self.tbl_cases.item(row, 2)
            if verdict_item is not None:
                verdict_item.setText(verdict_text)
                verdict_item.setTextAlignment(Qt.AlignCenter)
                verdict_item.setBackground(QBrush(QColor(verdict_bg)))
                verdict_item.setForeground(QBrush(QColor(verdict_fg)))
            self.tbl_cases.setCellWidget(row, 2, self._make_verdict_widget(case_verdict))

        self.append_log(
            f"样例完成 {item['display_name']} | {case_verdict}"
        )

        if self.selected_case_id == case_id:
            self.show_case(case_id)

    def on_worker_finished(self, msg: str) -> None:
        self.append_log(msg)
        self.lbl_run_status.setText("评测结束 ✓")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if self.worker_thread is not None and self.worker_thread.isRunning():
            self.worker_thread.quit()
        # Refresh scores for all currently visible cards
        if self.selected_case_id:
            self.show_case(self.selected_case_id)

    def on_worker_error(self, msg: str) -> None:
        self.append_log("错误: " + msg)
        self.lbl_run_status.setText("发生错误")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if self.worker_thread is not None and self.worker_thread.isRunning():
            self.worker_thread.quit()
        QMessageBox.critical(self, "运行错误", msg)

    def on_worker_thread_finished(self) -> None:
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.worker = None
        self.worker_thread = None

    # Card management

    def rebuild_target_cards(self, target_names: List[str]) -> None:
        self.clear_target_cards()

        self.tianquan_name = self.resolve_my_target_name(target_names)
        self.refresh_my_target_header(self.tianquan_name)

        others  = [
            n for n in target_names
            if n != self.tianquan_name and self.is_other_target_visible(n)
        ]
        self._visible_target_names = set(others)
        if self.tianquan_name:
            self._visible_target_names.add(self.tianquan_name)
        columns = 3

        for i, name in enumerate(others):
            card = TargetOutputCard(
                name,
                self.code_font,
                show_metrics=self.spec.show_metrics,
                show_score=self.spec.show_scores,
                metric_labels=self.spec.metric_labels,
            )
            card.copy_btn.clicked.connect(
                lambda _=False, e=card.output_edit, b=card.copy_btn: self.copy_from_editor(e, b)
            )
            r = i // columns
            c = i % columns
            self.targets_grid.addWidget(card, r, c)
            self.targets_grid.setColumnStretch(c, 1)
            self.targets_grid.setRowStretch(r, 1)
            self.target_cards[name] = card

    def on_case_selected(self) -> None:
        row = self.tbl_cases.currentRow()
        if row < 0:
            return
        cid = self.case_row_to_id.get(row)
        if cid:
            self.show_case(cid)

    def refresh_case_verdict_rows(self) -> None:
        for row, cid in self.case_row_to_id.items():
            item = self.case_data.get(cid)
            if item is None:
                continue
            targets_map: Dict[str, Any] = item["targets"]  # type: ignore
            status = str(item.get("status", ""))
            if status == "RUNNING":
                verdict = "RUNNING"
            elif targets_map:
                verdict = self._aggregate_case_verdict(self.visible_targets_map(targets_map))
                item["case_verdict"] = verdict
                item["status"] = verdict
            else:
                verdict = str(item.get("case_verdict", "..."))
            verdict_text, verdict_bg, verdict_fg = self._get_case_verdict_chip(verdict)
            verdict_item = self.tbl_cases.item(row, 2)
            if verdict_item is not None:
                verdict_item.setText(verdict_text)
                verdict_item.setTextAlignment(Qt.AlignCenter)
                verdict_item.setBackground(QBrush(QColor(verdict_bg)))
                verdict_item.setForeground(QBrush(QColor(verdict_fg)))
            self.tbl_cases.setCellWidget(row, 2, self._make_verdict_widget(verdict))

    def show_case(self, case_id: str) -> None:
        item = self.case_data.get(case_id)
        if item is None:
            return

        self.selected_case_id = case_id
        display_name  = str(item["display_name"])
        source        = str(item["source"])
        status        = str(item["status"])
        all_correct   = item["all_correct"]
        all_consistent = item["all_consistent"]

        self.lbl_case_name.setText(display_name)
        self.txt_case_input.setPlainText(str(item["input_text"]))
        self.set_badges(source, status, all_correct, all_consistent)

        targets_map: Dict[str, Any] = item["targets"]  # type: ignore
        visible_targets = self.visible_targets_map(targets_map)

        scores_map = self._compute_case_scores(visible_targets)

        if self.tianquan_name:
            tq_rr    = targets_map.get(self.tianquan_name)
            tq_score = scores_map.get(self.tianquan_name)
            self.show_tianquan_result(tq_rr, tq_score)
        else:
            self.show_tianquan_result(None, None)

        for name, card in self.target_cards.items():
            rr       = targets_map.get(name)
            chip_key = self.status_to_chip(rr)
            score    = scores_map.get(name)
            out_text = self.format_output(rr)
            metrics = self._metric_values(rr, targets_map)
            card.set_result(rr, out_text, chip_key, score, metrics=metrics)

    def show_tianquan_result(self, rr: Optional[Any],
                              score: Optional[float] = None) -> None:
        if not self.spec.show_scores:
            score = None
        chip_key = self.status_to_chip(rr)

        STATUS_MAP = {
            "AC":  ("#1B5E20", "#C8E6C9"),
            "WA":  ("#7B1D1D", "#FFCDD2"),
            "TLE": ("#4A3000", "#FFE0B2"),
            "RE":  ("#4A004A", "#E1BEE7"),
            "IE":  ("#283593", "#C5CAE9"),
        }
        bg, fg = STATUS_MAP.get(chip_key, ("#37474F", "#B0BEC5"))
        self._set_tq_chip(chip_key, bg, fg)

        if score is not None:
            s_color = "#69F0AE" if score >= 12 else "#FFD740" if score >= 8 else "#FF5252"
            self.tq_score.setText(f"S: {score:.2f}")
            self.tq_score.setStyleSheet(
                f"color:{s_color};font-weight:700;font-size:9pt;background:transparent;"
            )
        else:
            self.tq_score.setText("")

        targets_map = None
        if self.selected_case_id and self.selected_case_id in self.case_data:
            targets_map = self.case_data[self.selected_case_id].get("targets")  # type: ignore[assignment]
            if isinstance(targets_map, dict):
                targets_map = self.visible_targets_map(targets_map)
        metrics = self._metric_values(rr, targets_map) if isinstance(targets_map, dict) else self._metric_values(rr)
        if metrics is not None:
            for lbl, (name, val, hlt) in zip(
                self.tq_metric_labels,
                metrics,
            ):
                color = "#E2F0FF" if hlt else "#8FA8C8"
                lbl.setText(f"{name}  {val}")
                lbl.setStyleSheet(
                    f"background:#262C3A;color:{color};border-radius:6px;"
                    "padding:2px 8px;font-size:8pt;font-weight:600;"
                )
        elif rr is None:
            self._reset_tq_metrics()

        self.txt_tianquan.setPlainText(self.format_output(rr))

    def show_target_result(self, target_name: str, rr: Optional[Any]) -> None:
        score = None
        if self.spec.show_scores and self.selected_case_id:
            item = self.case_data.get(self.selected_case_id)
            if item:
                targets_map: Dict[str, Any] = item["targets"]  # type: ignore
                score = self._compute_case_scores(self.visible_targets_map(targets_map)).get(target_name)
        if target_name == self.tianquan_name:
            self.show_tianquan_result(rr, score)
            return
        card = self.target_cards.get(target_name)
        if card is None:
            return
        chip_key = self.status_to_chip(rr)
        metrics = None
        if self.selected_case_id:
            item = self.case_data.get(self.selected_case_id)
            if item:
                targets_map = item["targets"]  # type: ignore[assignment]
                if isinstance(targets_map, dict):
                    metrics = self._metric_values(rr, self.visible_targets_map(targets_map))
        card.set_result(rr, self.format_output(rr), chip_key, score, metrics=metrics)


def build_standard_page(window_cls: type[StandardJudgeWindow], parent: QWidget) -> QWidget:
    win = window_cls(parent)
    page = win.takeCentralWidget()
    if page is None:
        page = QWidget()
    win.hide()
    page.setStyleSheet(win.styleSheet())
    page.setFont(win.font())
    page.setParent(parent)
    win.setParent(page, Qt.Widget)
    page._owner_window = win  # type: ignore[attr-defined]
    return page
