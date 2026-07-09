"""HW2 评测页面 — 使用统一 StandardJudgeWindow + hw2 engine 适配器。"""
from __future__ import annotations

from pathlib import Path
from typing import List

from PyQt5.QtWidgets import QWidget

from judge.core.u1_page import CaseView, U1Adapter, Verdict
from judge.core.u1_standard import build_u1_page
from . import engine as eng


class HW2Adapter(U1Adapter):
    hw_id = "hw2"
    supports_shortest_audit = True
    grammar_hint = (
        "HW2 · 引入 exp(factor)、自定义函数 f(x)、三目 [(A==B)?C:D]. "
        "exp 参数须为 factor. 输出仅保留必要 exp 内部括号。"
    )

    def build_cases(self, seed: int, random_count: int) -> List[CaseView]:
        raw_cases = eng.build_cases(seed=seed, random_count=random_count, quiet=True)
        # HW2 中固定用例的 id 以 F/B/E 打头，随机用例以 R 打头，直接按前缀分类
        result: List[CaseView] = []
        for c in raw_cases:
            kind = "random" if c.case_id.startswith("R") else "fixed"
            result.append(CaseView(
                case_id=c.case_id,
                input_text=c.input_text,
                kind=kind,
                raw_case=c,
            ))
        return result

    def evaluate(self, case: CaseView, output: str, shortest_audit: bool) -> Verdict:
        raw = case.raw_case if case.raw_case is not None else eng.Case(
            case_id=case.case_id, input_text=case.input_text,
        )
        res = eng.evaluate_case(raw, output, shortest_audit)
        return Verdict(ok=res.ok, reason=res.reason, shorter_candidate=res.shorter_candidate)

    def wrap_custom(self, cid: str, text: str):
        return eng.Case(case_id=cid, input_text=text)


def build_page(parent: QWidget) -> QWidget:
    hw_root = Path(__file__).resolve().parents[3] / "U1" / "hw2"
    return build_u1_page(HW2Adapter(), hw_root=hw_root, parent=parent)
