"""HW1 评测页面 — 使用统一 StandardJudgeWindow + hw1 engine 适配器。"""
from __future__ import annotations

from pathlib import Path
from typing import List

from PyQt5.QtWidgets import QWidget

from judge.core.u1_page import CaseView, U1Adapter, Verdict
from judge.core.u1_standard import build_u1_page
from . import engine as eng


class HW1Adapter(U1Adapter):
    hw_id = "hw1"
    supports_shortest_audit = False
    grammar_hint = (
        "HW1 · 单变量 x, 指数 exp ∈ [0, 8], 0^0=1. "
        "输出禁止空白与括号, 判定为多项式系数等价。"
    )

    def build_cases(self, seed: int, random_count: int) -> List[CaseView]:
        raw_cases = eng.build_cases(seed=seed, random_count=random_count)
        result: List[CaseView] = []
        fixed_ids = {c.case_id for c in eng.CaseGenerator(seed, 0).fixed_cases()}
        for c in raw_cases:
            kind = "fixed" if c.case_id in fixed_ids else "random"
            result.append(CaseView(
                case_id=c.case_id,
                input_text=c.expr,
                kind=kind,
                raw_case=c,
            ))
        return result

    def evaluate(self, case: CaseView, output: str, shortest_audit: bool) -> Verdict:
        ok, reason = eng.evaluate_case(case.input_text, output)
        return Verdict(ok=ok, reason=reason)

    def wrap_custom(self, cid: str, text: str):
        return eng.Case(case_id=cid, expr=text)


def build_page(parent: QWidget) -> QWidget:
    hw_root = Path(__file__).resolve().parents[3] / "U1" / "hw1"
    return build_u1_page(HW1Adapter(), hw_root=hw_root, parent=parent)
