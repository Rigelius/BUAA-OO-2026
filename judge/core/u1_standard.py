"""StandardJudgeWindow adapter for HW1-HW3 expression judges."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any, List, Optional, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget

from judge.core.standard_page import (
    StandardJudgeSpec,
    StandardJudgeWindow,
)
from judge.core.u1_page import CaseView, JudgeWorker, RunConfig, U1Adapter


def _noop_generate_all(*_args: Any, **_kwargs: Any) -> List[str]:
    return []


def _noop_clear_directory(_path: Path) -> None:
    return None


class U1JudgeWindow(StandardJudgeWindow):
    def __init__(
        self,
        adapter: U1Adapter,
        hw_root: Path,
        parent: Optional[QWidget] = None,
    ) -> None:
        self.adapter = adapter
        self.hw_root = hw_root.resolve()
        self.buaa_root = self.hw_root
        for _ in range(6):
            if (self.buaa_root / "judge").exists():
                break
            self.buaa_root = self.buaa_root.parent

        self.tmp_build_root = Path(tempfile.gettempdir()) / f"buaaoo_{adapter.hw_id}_build"
        self.tmp_build_root.mkdir(parents=True, exist_ok=True)
        self.tmp_out_root = Path(tempfile.gettempdir()) / f"buaaoo_{adapter.hw_id}_out"
        self.tmp_out_root.mkdir(parents=True, exist_ok=True)
        plugin_root = Path(__file__).resolve().parents[1] / "plugins" / adapter.hw_id

        spec = StandardJudgeSpec(
            hw_id=adapter.hw_id,
            unit=1,
            title=f"OO {adapter.hw_id.upper()} 评测机",
            base_dir=plugin_root,
            self_work_dir=self.hw_root,
            official_default=self.hw_root,
            fixed_cases_dirname="fixed_cases",
            show_official_package=False,
            show_metrics=True,
            show_scores=False,
            include_stderr=True,
            metric_labels=("Len", "Time", "S"),
            score_mode="u1_length",
            custom_placeholder=self._custom_placeholder(adapter),
        )
        super().__init__(
            spec=spec,
            run_config_cls=RunConfig,
            gui_case_cls=CaseView,
            worker_cls=JudgeWorker,
            generate_all_func=_noop_generate_all,
            clear_directory_func=_noop_clear_directory,
            parent=parent,
        )

    @staticmethod
    def _custom_placeholder(adapter: U1Adapter) -> str:
        hint = adapter.grammar_hint.strip()
        if hint:
            return "输入完整样例内容\n" + hint
        return "输入完整样例内容"

    def create_worker(self, cfg: Any, cases: List[Any]) -> JudgeWorker:
        return JudgeWorker(self.adapter, cfg, cases, self.stop_event)

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
            work_dir=self.hw_root,
            build_dir=self.tmp_build_root,
            out_dir=self.tmp_out_root,
            target_pattern=pattern,
            target_mode="path",
            my_target=self.edt_my_target.text().strip() or self.my_target_default,
            soft_timeout=timeout,
            hard_timeout=timeout,
            compile_timeout=timeout,
            max_workers=self.compute_workers(8),
            shortest_audit=self.adapter.supports_shortest_audit,
            seed=int(time.time()) & 0x7FFFFFFF,
            random_count=int(self.spn_random.value()) if self.chk_random.isChecked() else 0,
        )

    def load_fixed_pool_cases(self) -> List[CaseView]:
        if not self.fixed_cases_dir.is_dir():
            return []
        cases: List[CaseView] = []
        for idx, fp in enumerate(sorted(self.fixed_cases_dir.glob("*.txt")), start=1):
            text = fp.read_text(encoding="utf-8", errors="replace").strip()
            if not text:
                continue
            cases.append(CaseView(
                case_id=f"fixed_pool::{idx:04d}::{fp.name}",
                input_text=text,
                kind="fixed",
            ))
        return cases

    def collect_cases(self) -> List[CaseView]:
        cases: List[CaseView] = []
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
                if case.kind == "fixed" and not use_fixed:
                    continue
                if case.kind == "random" and not use_random:
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
                    wrap = getattr(self.adapter, "wrap_custom", None)
                    if callable(wrap):
                        raw = wrap(case_id, text)
                except Exception as exc:
                    self.append_log(f"自定义用例 {case_id} 解析失败: {exc}")
                    continue
                cases.append(CaseView(
                    case_id=case_id,
                    input_text=text,
                    kind="custom",
                    raw_case=raw,
                ))
        return cases


def build_u1_page(adapter: U1Adapter, hw_root: Path, parent: QWidget) -> QWidget:
    win = U1JudgeWindow(adapter, hw_root, parent)
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
