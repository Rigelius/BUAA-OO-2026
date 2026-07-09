import argparse
import os
import random
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# -----------------------------
# Polynomial utilities
# -----------------------------

Poly = Dict[int, int]  # exponent -> coefficient


def poly_add(a: Poly, b: Poly) -> Poly:
    res = dict(a)
    for e, c in b.items():
        res[e] = res.get(e, 0) + c
        if res[e] == 0:
            del res[e]
    return res


def poly_neg(a: Poly) -> Poly:
    return {e: -c for e, c in a.items()}


def poly_mul(a: Poly, b: Poly) -> Poly:
    if not a or not b:
        return {}
    res: Poly = {}
    for e1, c1 in a.items():
        for e2, c2 in b.items():
            e = e1 + e2
            res[e] = res.get(e, 0) + c1 * c2
            if res[e] == 0:
                del res[e]
    return res


def poly_pow(a: Poly, exp: int) -> Poly:
    if exp == 0:
        return {0: 1}
    res: Poly = {0: 1}
    for _ in range(exp):
        res = poly_mul(res, a)
    return res


# -----------------------------
# Grammar parser (guidebook-compliant subset)
# -----------------------------


class ParseError(Exception):
    pass


class Lexer:
    def __init__(self, s: str) -> None:
        self.s = s
        self.n = len(s)
        self.i = 0

    def skip_ws(self) -> None:
        while self.i < self.n and self.s[self.i] in (' ', '\t'):
            self.i += 1

    def peek(self) -> Optional[str]:
        self.skip_ws()
        if self.i >= self.n:
            return None
        return self.s[self.i]

    def take(self, ch: str) -> bool:
        self.skip_ws()
        if self.i < self.n and self.s[self.i] == ch:
            self.i += 1
            return True
        return False

    def expect(self, ch: str) -> None:
        if not self.take(ch):
            raise ParseError(f"expected '{ch}' at index {self.i}")

    def take_digits(self) -> Optional[str]:
        self.skip_ws()
        j = self.i
        while j < self.n and self.s[j].isdigit():
            j += 1
        if j == self.i:
            return None
        out = self.s[self.i:j]
        self.i = j
        return out


class ExprParser:
    def __init__(
        self,
        text: str,
        max_depth: Optional[int] = 3,
        enforce_exp_upper_bound: bool = False,
    ) -> None:
        self.lex = Lexer(text)
        self.max_depth = max_depth
        self.enforce_exp_upper_bound = enforce_exp_upper_bound

    def parse_all(self) -> Poly:
        p = self.parse_expr(depth=0)
        if self.lex.peek() is not None:
            raise ParseError(f"trailing token at index {self.lex.i}")
        return p

    def parse_expr(self, depth: int) -> Poly:
        first_sign = 1
        while True:
            if self.lex.take('+'):
                continue
            if self.lex.take('-'):
                first_sign *= -1
                continue
            break

        term = self.parse_term(depth)
        if first_sign < 0:
            term = poly_neg(term)
        res = term

        while True:
            if self.lex.take('+'):
                res = poly_add(res, self.parse_term(depth))
            elif self.lex.take('-'):
                res = poly_add(res, poly_neg(self.parse_term(depth)))
            else:
                break
        return res

    def parse_term(self, depth: int) -> Poly:
        sign = 1
        while True:
            if self.lex.take('+'):
                continue
            if self.lex.take('-'):
                sign *= -1
                continue
            break

        p = self.parse_factor(depth)
        while self.lex.take('*'):
            p = poly_mul(p, self.parse_factor(depth))

        if sign < 0:
            p = poly_neg(p)
        return p

    def parse_factor(self, depth: int) -> Poly:
        ch = self.lex.peek()
        if ch is None:
            raise ParseError("unexpected end while parsing factor")

        if ch == 'x':
            self.lex.take('x')
            exp = self.parse_optional_exponent(default=1)
            return {exp: 1}

        if ch == '(':
            if self.max_depth is not None and depth >= self.max_depth:
                raise ParseError("parenthesis depth exceeds guidebook limit")
            self.lex.take('(')
            inner = self.parse_expr(depth + 1)
            self.lex.expect(')')
            exp = self.parse_optional_exponent(default=1)
            return poly_pow(inner, exp)

        # signed integer: [+-]? digits
        sign = 1
        if self.lex.take('+'):
            sign = 1
        elif self.lex.take('-'):
            sign = -1

        digits = self.lex.take_digits()
        if digits is None:
            raise ParseError(f"invalid number token at index {self.lex.i}")
        val = int(digits)
        if sign < 0:
            val = -val
        return {0: val} if val != 0 else {}

    def parse_optional_exponent(self, default: int) -> int:
        if not self.lex.take('^'):
            return default
        self.lex.take('+')
        digits = self.lex.take_digits()
        if digits is None:
            raise ParseError(f"invalid exponent at index {self.lex.i}")
        exp = int(digits)
        if exp < 0:
            raise ParseError("negative exponent not allowed")
        if self.enforce_exp_upper_bound and exp > 8:
            raise ParseError("exponent exceeds guidebook limit")
        return exp


# -----------------------------
# Case generation (all legal by guidebook)
# -----------------------------


@dataclass
class Case:
    case_id: str
    expr: str


class CaseGenerator:
    def __init__(self, seed: int, count_random: int) -> None:
        self.rng = random.Random(seed)
        self.count_random = count_random

    def maybe_ws(self) -> str:
        # Only legal whitespaces: space or tab.
        k = self.rng.randint(0, 2)
        if k == 0:
            return ""
        if k == 1:
            return " " * self.rng.randint(1, 2)
        return "\t" * self.rng.randint(1, 2)

    def sign_str(self) -> str:
        return self.rng.choice(['+', '-'])

    def gen_digits(self, max_val: int) -> str:
        base = str(self.rng.randint(0, max_val))
        if self.rng.random() < 0.45:
            return '0' * self.rng.randint(1, 3) + base
        return base

    def gen_signed_integer(self) -> str:
        s = self.sign_str() if self.rng.random() < 0.5 else ''
        return s + self.gen_digits(40)

    def gen_pow(self) -> str:
        if self.rng.random() < 0.65:
            exp = self.gen_digits(8)
            return f"x{self.maybe_ws()}^{self.maybe_ws()}{exp}"
        return "x"

    def gen_factor(self, depth: int) -> str:
        kind = self.rng.random()
        if kind < 0.35:
            return self.gen_signed_integer()
        if kind < 0.7:
            return self.gen_pow()

        if depth >= 3:
            return self.gen_pow()

        inner = self.gen_expr(depth + 1)
        if self.rng.random() < 0.7:
            exp = self.gen_digits(8)
            return f"({inner}){self.maybe_ws()}^{self.maybe_ws()}{exp}"
        return f"({inner})"

    def gen_term(self, depth: int) -> str:
        pieces: List[str] = []
        # optional unary sign before first factor
        if self.rng.random() < 0.35:
            pieces.append(self.sign_str())
            pieces.append(self.maybe_ws())

        pieces.append(self.gen_factor(depth))
        factor_cnt = self.rng.randint(1, 5)
        for _ in range(1, factor_cnt):
            pieces.append(self.maybe_ws())
            pieces.append('*')
            pieces.append(self.maybe_ws())
            pieces.append(self.gen_factor(depth))
        return ''.join(pieces)

    def gen_expr(self, depth: int) -> str:
        pieces: List[str] = []
        # optional unary sign before first term
        if self.rng.random() < 0.35:
            pieces.append(self.sign_str())
            pieces.append(self.maybe_ws())

        pieces.append(self.gen_term(depth))
        term_cnt = self.rng.randint(1, 5)
        for _ in range(1, term_cnt):
            pieces.append(self.maybe_ws())
            pieces.append(self.sign_str())
            pieces.append(self.maybe_ws())
            pieces.append(self.gen_term(depth))
        return ''.join(pieces)

    def fixed_cases(self) -> List[Case]:
        return [
            Case("F001", "1"),
            Case("F002", "x"),
            Case("F003", "x+2*x"),
            Case("F004", "x+2*x+x^2"),
            Case("F005", "-3*(x)"),
            Case("F006", "-3*(x-1)"),
            Case("F007", "(x-1)^2"),
            Case("F008", "(x+2*x^2+1)^0"),
            Case("F009", "(x+1)^3+1"),
            Case("F010", "(x*x*3*x)^2*x"),
            Case("F011", "(x+1)*(x+2)"),
            Case("F012", "x*(x-(x+1))"),
            Case("B001", "00012*x^08+0003*x^8"),
            Case("B002", "(x+1)^8"),
            Case("B003", "(0)^0"),
            Case("B004", "- +3 * x + +0004"),
            Case("B005", "\t(\tx\t+\t1\t)\t*\t(\t x\t-\t2\t)\t"),
            # More legal edge/complex cases (all satisfy HW1 grammar constraints)
            Case("E001", "((x+1)*(x-1))^2"),
            Case("E002", "((x^2+2*x+1)^2-(x^2-2*x+1)^2)"),
            Case("E003", "(x^2+x+1)^3-(x^3+1)*(x^3-1)+1"),
            Case("E004", "(x-1)*(x-1)*(x-1)*(x-1)"),
            Case("E005", "(x+1)^8-(x-1)^8"),
            Case("E006", "(x^2+1)^4-(x^8+4*x^6+6*x^4+4*x^2+1)"),
            Case("E007", "(x+0)^8+0000000"),
            Case("E008", "- - -x + + +x - (+0)"),
            Case("E009", "((x+2)*(x+3))*(x-5)"),
            Case("E010", "(x*(x*(x+1)))"),
            Case("E011", "(x^8+x^7+x^6+x^5+x^4+x^3+x^2+x+1)*(x-1)"),
            Case("E012", "((x+1)^2+(x-1)^2)^2"),
            Case("E013", "(x^2-1)^3-(x-1)^3*(x+1)^3"),
            Case("E014", "(x^2+2*x+1)^0 + (x^2-2*x+1)^0"),
            Case("E015", "(((((x)))))".replace("(((((x)))))", "(((x)))")),
        ]

    def random_cases(self) -> List[Case]:
        out: List[Case] = []
        i = 1
        while len(out) < self.count_random:
            expr = self.gen_expr(0)
            # guidebook effective length <= 200 (excluding whitespace)
            eff_len = len(expr.replace(' ', '').replace('\t', ''))
            if 20 <= eff_len <= 200:
                out.append(Case(f"R{i:03d}", expr))
                i += 1
        return out


# -----------------------------
# Judge core
# -----------------------------


def normalize_poly(p: Poly) -> Poly:
    return {e: c for e, c in p.items() if c != 0}


def run_target(
    cmd: List[str],
    input_text: str,
) -> Tuple[bool, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return True, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "TIMEOUT"
    except Exception as exc:
        return False, "", f"RUN_ERROR: {exc}"


def check_output_format(out: str) -> bool:
    # Guidebook output constraints for HW1:
    # 1) no whitespace; 2) no parentheses.
    if re.search(r"[\s()]", out):
        return False
    return True


def evaluate_case(expr_in: str, out: str) -> Tuple[bool, str]:
    if not out:
        return False, "EMPTY_OUTPUT"
    if not check_output_format(out):
        return False, "FORMAT_VIOLATION"

    try:
        expected_poly = normalize_poly(
            ExprParser(expr_in, enforce_exp_upper_bound=True).parse_all()
        )
    except Exception as exc:
        return False, f"INTERNAL_CASE_PARSE_ERROR: {exc}"

    try:
        # Output is judged by semantic equivalence only.
        # For output grammar, do not reuse input-only upper bound constraints.
        actual_poly = normalize_poly(ExprParser(out, max_depth=None).parse_all())
    except Exception as exc:
        return False, f"OUTPUT_PARSE_ERROR: {exc}"

    if expected_poly == actual_poly:
        return True, "PASS"
    return False, "NOT_EQUIVALENT"


def ensure_dirs(base: str) -> Tuple[str, str, str]:
    data_dir = os.path.join(base, "data")
    out_dir = os.path.join(base, "out")
    bug_dir = os.path.join(base, "bug")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(bug_dir, exist_ok=True)
    return data_dir, out_dir, bug_dir


def write_case_file(data_dir: str, case: Case) -> str:
    path = os.path.join(data_dir, f"{case.case_id}.in")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(case.expr)
    return path


def write_bug_report(
    bug_dir: str,
    case: Case,
    reason: str,
    stdout_text: str,
    stderr_text: str,
) -> None:
    path = os.path.join(bug_dir, f"{case.case_id}.txt")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"[Reason]\n{reason}\n\n")
        f.write(f"[Input]\n{case.expr}\n\n")
        f.write(f"[Stdout]\n{stdout_text}\n\n")
        f.write(f"[Stderr]\n{stderr_text}\n")


def auto_target_cmd(args: argparse.Namespace, base: str) -> List[str]:
    if args.jar:
        return ["java", "-jar", args.jar]

    src_dir = os.path.abspath(os.path.join(base, "..", "src"))
    java_files = [f for f in os.listdir(src_dir) if f.endswith(".java")]
    if not java_files:
        raise RuntimeError(f"no java files found in {src_dir}")

    compile_cmd = ["javac", "-encoding", "UTF-8"] + java_files
    cp = subprocess.run(
        compile_cmd,
        cwd=src_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if cp.returncode != 0:
        raise RuntimeError("javac failed:\n" + cp.stdout + "\n" + cp.stderr)

    return ["java", "-cp", src_dir, "MainClass"]


def build_cases(seed: int, random_count: int) -> List[Case]:
    gen = CaseGenerator(seed=seed, count_random=random_count)
    cases = gen.fixed_cases() + gen.random_cases()
    # Ensure all generated cases are legal per parser/constraints.
    checked: List[Case] = []
    for c in cases:
        ExprParser(c.expr, enforce_exp_upper_bound=True).parse_all()
        checked.append(c)
    return checked


def main() -> None:
    parser = argparse.ArgumentParser(description="HW1 guidebook-compliant auto judge")
    parser.add_argument("--jar", default="", help="path to target jar; if empty, compile/run ../src/MainClass")
    parser.add_argument("--seed", type=int, default=20260306, help="random seed")
    parser.add_argument("--random-count", type=int, default=120, help="number of random legal cases")
    args = parser.parse_args()

    base = os.path.dirname(os.path.abspath(__file__))
    data_dir, out_dir, bug_dir = ensure_dirs(base)

    cases = build_cases(args.seed, args.random_count)

    target_cmd = auto_target_cmd(args, base)

    total = len(cases)
    passed = 0
    failed = 0

    report_rows: List[str] = []

    for case in cases:
        write_case_file(data_dir, case)
        ok_run, stdout_text, stderr_text = run_target(target_cmd, case.expr)

        out_path = os.path.join(out_dir, f"{case.case_id}.out")
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(stdout_text)

        if not ok_run:
            failed += 1
            reason = stderr_text
            write_bug_report(bug_dir, case, reason, stdout_text, stderr_text)
            report_rows.append(f"{case.case_id}|FAIL|{reason}")
            continue

        ok, reason = evaluate_case(case.expr, stdout_text)
        if ok:
            passed += 1
            report_rows.append(f"{case.case_id}|PASS|PASS")
        else:
            failed += 1
            write_bug_report(bug_dir, case, reason, stdout_text, stderr_text)
            report_rows.append(f"{case.case_id}|FAIL|{reason}")

    summary_path = os.path.join(base, "summary.md")
    with open(summary_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("# HW1 Auto Judge Summary\n\n")
        f.write(f"- Total: {total}\n")
        f.write(f"- Passed: {passed}\n")
        f.write(f"- Failed: {failed}\n\n")
        f.write("## Detail\n\n")
        f.write("| Case | Result | Reason |\n")
        f.write("|---|---|---|\n")
        for row in report_rows:
            case_id, res, reason = row.split("|", 2)
            f.write(f"| {case_id} | {res} | {reason} |\n")

    print(f"DONE: pass={passed}, fail={failed}, total={total}")
    print(f"summary: {summary_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FATAL: {exc}")
        sys.exit(1)
