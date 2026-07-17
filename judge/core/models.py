"""Shared runtime models and status helpers for judge plugins."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


@dataclass
class GuiCase:
    case_id: str
    display_name: str
    source: str
    input_text: str


@dataclass
class RunConfig:
    co_judge_dir: Path
    official_jar: Path
    build_dir: Path
    out_dir: Path
    report_dir: Path
    problem_dir: Path
    target_pattern: str
    soft_timeout: float
    hard_timeout: float
    compile_timeout: float
    max_workers: int
    mutual_mode: bool
    shortest_audit: bool = False


def target_status_to_case_code(status: str) -> str:
    if status == "PASSED":
        return "AC"
    if status in {"TIMEOUT_SOFT", "TIMEOUT_HARD"}:
        return "TLE"
    if status in {"RUNTIME_ERROR", "JAVA_ERROR", "EXEC_ERROR"}:
        return "RE"
    if status == "INPUT_ERROR":
        return "IE"
    if status == "SKIPPED_STOP":
        return "STOP"
    return "WA"


def aggregate_case_status(targets: Dict[str, Any]) -> str:
    if not targets:
        return "IE"
    codes = [target_status_to_case_code(rr.status) for rr in targets.values()]
    if all(code == "AC" for code in codes):
        return "AC"
    for code in ("IE", "RE", "TLE", "WA", "STOP"):
        if code in codes:
            return code
    return "WA"


def compute_r(x: float, x_min: float, x_max: float, x_avg: float, p: float = 0.10) -> float:
    base_min = p * x_avg + (1 - p) * x_min
    base_max = p * x_avg + (1 - p) * x_max
    if base_max <= base_min:
        return 1.0
    if x <= base_min:
        return 1.0
    if x > base_max:
        return 0.0
    return (base_max - x) / (base_max - base_min)


def compute_score_across_samples(samples: List[Tuple[float, float, float]]) -> List[float]:
    if not samples:
        return []
    trs = [s[0] for s in samples]
    tas = [s[1] for s in samples]
    ws = [s[2] for s in samples]

    tr_min, tr_max, tr_avg = min(trs), max(trs), sum(trs) / len(trs)
    ta_min, ta_max, ta_avg = min(tas), max(tas), sum(tas) / len(tas)
    w_min, w_max, w_avg = min(ws), max(ws), sum(ws) / len(ws)

    scores = []
    for tr, ta, w in samples:
        r_tr = compute_r(tr, tr_min, tr_max, tr_avg)
        r_ta = compute_r(ta, ta_min, ta_max, ta_avg)
        r_w = compute_r(w, w_min, w_max, w_avg)
        scores.append(15.0 * (0.3 * r_tr + 0.3 * r_ta + 0.4 * r_w))
    return scores


def effective_output_length(text: str) -> int:
    return len("".join(text.split()))


def compute_expression_length_score(length: int, best_length: int) -> float:
    if best_length <= 0:
        return 0.0
    x = length / best_length
    if x <= 1:
        ratio = 1.0
    elif x <= 1.5:
        ratio = (
            -31.8239 * x ** 4
            + 155.9038 * x ** 3
            - 279.2180 * x ** 2
            + 214.0743 * x
            - 57.9370
        )
    else:
        ratio = 0.0
    ratio = max(0.0, min(1.0, ratio))
    return 15.0 * ratio
