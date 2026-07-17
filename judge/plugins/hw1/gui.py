"""HW1 评测页面 — 使用统一 StandardJudgeWindow + hw1 engine 适配器。"""
from __future__ import annotations

from pathlib import Path
from typing import List

from PyQt5.QtWidgets import QWidget

from judge.core.simple_io import SimpleCase, SimpleIoAdapter, SimpleIoJudgeWindow, Verdict
from judge.core.standard_page import build_standard_page
from . import engine as eng


class HW1Adapter(SimpleIoAdapter):
    hw_id = "hw1"
    supports_shortest_audit = False
    grammar_hint = (
        "HW1 单变量 x, 指数 exp ∈ [0, 8], 0^0=1. "
        "输出禁止空白与括号, 判定为多项式系数等价。"
    )

    def build_cases(self, seed: int, random_count: int) -> List[SimpleCase]:
        raw_cases = eng.build_cases(seed=seed, random_count=random_count)
        result: List[SimpleCase] = []
        fixed_ids = {c.case_id for c in eng.CaseGenerator(seed, 0).fixed_cases()}
        for c in raw_cases:
            source = "fixed" if c.case_id in fixed_ids else "random"
            result.append(SimpleCase(
                case_id=c.case_id,
                input_text=c.expr,
                source=source,
                raw_case=c,
            ))
        return result

    def evaluate(self, case: SimpleCase, output: str, shortest_audit: bool) -> Verdict:
        ok, reason = eng.evaluate_case(case.input_text, output)
        return Verdict(ok=ok, reason=reason)

    def wrap_custom(self, cid: str, text: str):
        return eng.Case(case_id=cid, expr=text)


class HW1JudgeWindow(SimpleIoJudgeWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        base_dir = Path(__file__).resolve().parent
        super().__init__(
            adapter=HW1Adapter(),
            unit=1,
            base_dir=base_dir,
            self_work_dir=(base_dir.parents[2] / "U1" / "hw1").resolve(),
            parent=parent,
        )


def build_page(parent: QWidget) -> QWidget:
    return build_standard_page(HW1JudgeWindow, parent)
