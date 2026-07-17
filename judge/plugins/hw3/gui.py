"""HW3 评测页面 — 使用统一 StandardJudgeWindow + hw3 engine 适配器。"""
from __future__ import annotations

from pathlib import Path
from typing import List

from PyQt5.QtWidgets import QWidget

from judge.core.simple_io import SimpleCase, SimpleIoAdapter, SimpleIoJudgeWindow, Verdict
from judge.core.standard_page import build_standard_page
from . import engine as eng


class HW3Adapter(SimpleIoAdapter):
    hw_id = "hw3"
    supports_shortest_audit = True
    grammar_hint = (
        "HW3 引入变量 y、导数 dx/dy/grad、递归 f{n}(x) (n≤5). "
        "函数体不含 y / 三目 / 导数 / 相互调用。"
    )

    def build_cases(self, seed: int, random_count: int) -> List[SimpleCase]:
        raw_cases = eng.build_cases(seed=seed, random_count=random_count, quiet=True)
        result: List[SimpleCase] = []
        for c in raw_cases:
            source = "random" if c.case_id.startswith("R") else "fixed"
            result.append(SimpleCase(
                case_id=c.case_id,
                input_text=c.input_text,
                source=source,
                raw_case=c,
            ))
        return result

    def evaluate(self, case: SimpleCase, output: str, shortest_audit: bool) -> Verdict:
        raw = case.raw_case if case.raw_case is not None else eng.Case(
            case_id=case.case_id, input_text=case.input_text,
        )
        res = eng.evaluate_case(raw, output, shortest_audit)
        return Verdict(ok=res.ok, reason=res.reason, shorter_candidate=res.shorter_candidate)

    def wrap_custom(self, cid: str, text: str):
        return eng.Case(case_id=cid, input_text=text)


class HW3JudgeWindow(SimpleIoJudgeWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        base_dir = Path(__file__).resolve().parent
        super().__init__(
            adapter=HW3Adapter(),
            unit=1,
            base_dir=base_dir,
            self_work_dir=(base_dir.parents[2] / "U1" / "hw3").resolve(),
            parent=parent,
        )


def build_page(parent: QWidget) -> QWidget:
    return build_standard_page(HW3JudgeWindow, parent)
