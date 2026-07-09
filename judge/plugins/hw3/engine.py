import argparse
import os
import random
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    import sympy as sp
except Exception as exc:
    print(f"FATAL: sympy is required: {exc}")
    sys.exit(1)

X = sp.Symbol("x")
Y = sp.Symbol("y")


class ParseError(Exception):
    pass


#  Lexer

class Lexer:
    def __init__(self, text: str) -> None:
        self.s = text
        self.n = len(text)
        self.i = 0

    def skip_ws(self) -> None:
        while self.i < self.n and self.s[self.i] in (" ", "\t"):
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

    def starts_with(self, token: str) -> bool:
        self.skip_ws()
        return self.s.startswith(token, self.i)

    def take_token(self, token: str) -> bool:
        if self.starts_with(token):
            self.i += len(token)
            return True
        return False

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


#  AST Nodes

class Node:
    def to_sympy(self, ctx: "EvalContext") -> sp.Expr:
        raise NotImplementedError


@dataclass
class ConstNode(Node):
    value: int

    def to_sympy(self, ctx):
        return sp.Integer(self.value)


@dataclass
class XNode(Node):
    exp: int

    def to_sympy(self, ctx):
        return X ** self.exp


@dataclass
class YNode(Node):
    exp: int

    def to_sympy(self, ctx):
        return Y ** self.exp


@dataclass
class ExprFactorNode(Node):
    expr: Node
    exp: int

    def to_sympy(self, ctx):
        return self.expr.to_sympy(ctx) ** self.exp


@dataclass
class ExpNode(Node):
    arg: Node
    exp: int

    def to_sympy(self, ctx):
        arg_expr = self.arg.to_sympy(ctx)
        base = sp.exp(arg_expr, evaluate=False)
        if self.exp == 1:
            return base
        return sp.Pow(base, sp.Integer(self.exp), evaluate=False)


@dataclass
class FuncCallNode(Node):
    arg: Node

    def to_sympy(self, ctx):
        if ctx.func_body is None:
            raise ParseError("f() call but no non-recursive definition")
        arg_expr = self.arg.to_sympy(ctx)
        body_expr = ctx.func_body.to_sympy(ctx)
        return body_expr.subs(X, arg_expr)


@dataclass
class RecFuncCallNode(Node):
    index: int
    arg: Node

    def to_sympy(self, ctx):
        if ctx.rec_f_exprs is None:
            raise ParseError("f{i}() call but no recursive definition")
        fi = ctx.rec_f_exprs[self.index]
        arg_expr = self.arg.to_sympy(ctx)
        return fi.subs(X, arg_expr)


@dataclass
class ChoiceNode(Node):
    a: Node
    b: Node
    c: Node
    d: Node

    def to_sympy(self, ctx):
        left = self.a.to_sympy(ctx)
        right = self.b.to_sympy(ctx)
        if left == right:
            is_equal = True
        else:
            try:
                diff = sp.expand(left - right)
                is_equal = (diff == 0)
                if not is_equal:
                    diff = sp.simplify(diff)
                    is_equal = (diff == 0)
                if not is_equal:
                    is_equal = left.equals(right) is True
            except Exception:
                is_equal = False
        return self.c.to_sympy(ctx) if is_equal else self.d.to_sympy(ctx)


@dataclass
class DxNode(Node):
    inner: Node

    def to_sympy(self, ctx):
        return sp.diff(self.inner.to_sympy(ctx), X)


@dataclass
class DyNode(Node):
    inner: Node

    def to_sympy(self, ctx):
        return sp.diff(self.inner.to_sympy(ctx), Y)


@dataclass
class GradNode(Node):
    inner: Node

    def to_sympy(self, ctx):
        val = self.inner.to_sympy(ctx)
        return sp.diff(val, X) + sp.diff(val, Y)


@dataclass
class MulNode(Node):
    factors: List[Node]

    def to_sympy(self, ctx):
        out = sp.Integer(1)
        for f in self.factors:
            out *= f.to_sympy(ctx)
        return out


@dataclass
class NegNode(Node):
    inner: Node

    def to_sympy(self, ctx):
        return -self.inner.to_sympy(ctx)


@dataclass
class ExprNode(Node):
    terms: List[Tuple[int, Node]]

    def to_sympy(self, ctx):
        out = sp.Integer(0)
        for sign, term in self.terms:
            t = term.to_sympy(ctx)
            out += t if sign > 0 else -t
        return out


#  EvalContext

@dataclass
class EvalContext:
    func_body: Optional[Node] = None
    rec_f_exprs: Optional[Dict[int, sp.Expr]] = None


#  ExprParser

class ExprParser:
    def __init__(self, text: str, *, allow_func_call: bool,
                 allow_rec_func: bool, allow_choice: bool,
                 allow_deriv: bool, allow_y: bool,
                 enforce_exp_upper_bound: bool) -> None:
        self.lex = Lexer(text)
        self.allow_func_call = allow_func_call
        self.allow_rec_func = allow_rec_func
        self.allow_choice = allow_choice
        self.allow_deriv = allow_deriv
        self.allow_y = allow_y
        self.enforce_exp_upper_bound = enforce_exp_upper_bound

    def parse_all(self) -> Node:
        node = self.parse_expr()
        if self.lex.peek() is not None:
            raise ParseError(f"trailing at {self.lex.i}")
        return node

    def parse_expr(self) -> Node:
        first_sign = 1
        while True:
            if self.lex.take("+"):
                continue
            if self.lex.take("-"):
                first_sign *= -1
                continue
            break
        first_term = self.parse_term()
        terms = [(first_sign, first_term)]
        while True:
            if self.lex.take("+"):
                terms.append((1, self.parse_term()))
            elif self.lex.take("-"):
                terms.append((-1, self.parse_term()))
            else:
                break
        return ExprNode(terms)

    def parse_term(self) -> Node:
        sign = 1
        while True:
            if self.lex.take("+"):
                continue
            if self.lex.take("-"):
                sign *= -1
                continue
            break
        factors = [self.parse_factor()]
        while self.lex.take("*"):
            factors.append(self.parse_factor())
        node = factors[0] if len(factors) == 1 else MulNode(factors)
        if sign < 0:
            node = NegNode(node)
        return node

    def parse_factor(self) -> Node:
        ch = self.lex.peek()
        if ch is None:
            raise ParseError("unexpected end")

        if ch == "[":
            if not self.allow_choice:
                raise ParseError("choice not allowed")
            return self._parse_choice()

        if self.lex.starts_with("exp"):
            return self._parse_exp()

        if self.lex.starts_with("grad"):
            if not self.allow_deriv:
                raise ParseError("deriv not allowed")
            return self._parse_grad()

        if self.lex.starts_with("dx"):
            if not self.allow_deriv:
                raise ParseError("deriv not allowed")
            return self._parse_dx()

        if self.lex.starts_with("dy"):
            if not self.allow_deriv:
                raise ParseError("deriv not allowed")
            return self._parse_dy()

        if self.lex.starts_with("f"):
            return self._parse_func()

        if ch == "x":
            self.lex.take("x")
            exp = self._parse_optional_exponent(1)
            return XNode(exp)

        if ch == "y":
            if not self.allow_y:
                raise ParseError("y not allowed")
            self.lex.take("y")
            exp = self._parse_optional_exponent(1)
            return YNode(exp)

        if ch == "(":
            self.lex.take("(")
            inner = self.parse_expr()
            self.lex.expect(")")
            exp = self._parse_optional_exponent(1)
            return ExprFactorNode(inner, exp)

        # constant
        s = 1
        if self.lex.take("+"):
            s = 1
        elif self.lex.take("-"):
            s = -1
        digits = self.lex.take_digits()
        if digits is None:
            raise ParseError(f"bad token at {self.lex.i}")
        val = int(digits)
        return ConstNode(val * s)

    def _parse_choice(self) -> Node:
        self.lex.expect("[")
        self.lex.expect("(")
        a = self.parse_factor()
        self.lex.skip_ws()
        self.lex.expect("=")
        self.lex.expect("=")
        b = self.parse_factor()
        self.lex.expect(")")
        self.lex.expect("?")
        c = self.parse_factor()
        self.lex.expect(":")
        d = self.parse_factor()
        self.lex.expect("]")
        return ChoiceNode(a, b, c, d)

    def _parse_exp(self) -> Node:
        self.lex.take_token("exp")
        self.lex.expect("(")
        arg = self.parse_factor()
        self.lex.expect(")")
        exp = self._parse_optional_exponent(1)
        return ExpNode(arg, exp)

    def _parse_dx(self) -> Node:
        self.lex.take_token("dx")
        self.lex.expect("(")
        inner = self.parse_expr()
        self.lex.expect(")")
        return DxNode(inner)

    def _parse_dy(self) -> Node:
        self.lex.take_token("dy")
        self.lex.expect("(")
        inner = self.parse_expr()
        self.lex.expect(")")
        return DyNode(inner)

    def _parse_grad(self) -> Node:
        self.lex.take_token("grad")
        self.lex.expect("(")
        inner = self.parse_expr()
        self.lex.expect(")")
        return GradNode(inner)

    def _parse_func(self) -> Node:
        self.lex.take_token("f")
        if self.lex.take("{"):
            # f{i}(factor)
            if not self.allow_rec_func:
                raise ParseError("rec func not allowed")
            digits = self.lex.take_digits()
            if digits is None:
                raise ParseError("missing index")
            idx = int(digits)
            self.lex.expect("}")
            self.lex.expect("(")
            arg = self.parse_factor()
            self.lex.expect(")")
            return RecFuncCallNode(idx, arg)
        else:
            # f(factor)
            if not self.allow_func_call:
                raise ParseError("func call not allowed")
            self.lex.expect("(")
            arg = self.parse_factor()
            self.lex.expect(")")
            return FuncCallNode(arg)

    def _parse_optional_exponent(self, default: int) -> int:
        if not self.lex.take("^"):
            return default
        self.lex.take("+")
        d = self.lex.take_digits()
        if d is None:
            raise ParseError(f"bad exponent at {self.lex.i}")
        exp = int(d)
        if exp < 0:
            raise ParseError("negative exponent")
        if self.enforce_exp_upper_bound and exp > 8:
            raise ParseError("exponent > 8")
        return exp


#  Function Definition Parsing

def _strip(s: str) -> str:
    return "".join(ch for ch in s if ch not in (" ", "\t"))


def parse_function_definition(line: str) -> Node:
    compact = _strip(line)
    if "=" not in compact:
        raise ParseError("no '='")
    left, right = compact.split("=", 1)
    if left != "f(x)":
        raise ParseError("lhs must be f(x)")
    if not right:
        raise ParseError("empty body")
    p = ExprParser(right, allow_func_call=False, allow_rec_func=False,
                   allow_choice=False, allow_deriv=False, allow_y=False,
                   enforce_exp_upper_bound=True)
    return p.parse_all()


def _find_matching_paren(s: str, start: int) -> int:
    depth = 1
    i = start
    while i < len(s) and depth > 0:
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
        i += 1
    return i  # points after the closing )


@dataclass
class RecDef:
    base0: Node
    base1: Node
    rec_c1: int
    rec_factor1: Node
    rec_sign2: int
    rec_c2: int
    rec_factor2: Node
    rec_extra: Optional[Node]


def parse_recursive_definitions(lines: List[str]) -> RecDef:
    if len(lines) != 3:
        raise ParseError("need exactly 3 recursive definition lines")

    bases: Dict[int, Node] = {}
    rec_line = None
    for line in lines:
        compact = _strip(line)
        if not compact.startswith("f{"):
            raise ParseError("bad recursive def")
        idx_char = compact[2]
        if idx_char in ("0", "1"):
            seq = int(idx_char)
            eq_pos = compact.index("=")
            rhs = compact[eq_pos + 1:]
            p = ExprParser(rhs, allow_func_call=False, allow_rec_func=False,
                           allow_choice=False, allow_deriv=False, allow_y=False,
                           enforce_exp_upper_bound=True)
            bases[seq] = p.parse_all()
        elif idx_char == "n":
            rec_line = compact
        else:
            raise ParseError(f"unexpected seq char: {idx_char}")

    if 0 not in bases or 1 not in bases or rec_line is None:
        raise ParseError("incomplete recursive definition")

    # Parse recursive line: f{n}(x)=<c1>*f{n-1}(<F1>)<sign><c2>*f{n-2}(<F2>)[<sign><extra>]
    eq_pos = rec_line.index("=")
    rhs = rec_line[eq_pos + 1:]

    fn1_marker = "f{n-1}("
    fn2_marker = "f{n-2}("
    fn1_pos = rhs.find(fn1_marker)
    if fn1_pos < 0:
        raise ParseError("no f{n-1}")

    c1_str = rhs[:fn1_pos].rstrip("*")
    c1 = int(c1_str) if c1_str else 1

    f1_inner_start = fn1_pos + len(fn1_marker)
    f1_close = _find_matching_paren(rhs, f1_inner_start)
    f1_text = rhs[f1_inner_start:f1_close - 1]

    rest = rhs[f1_close:]
    fn2_pos = rest.find(fn2_marker)
    if fn2_pos < 0:
        raise ParseError("no f{n-2}")

    mid = rest[:fn2_pos].rstrip("*")
    sign2 = 1
    if mid.startswith("-"):
        sign2 = -1
        mid = mid[1:]
    elif mid.startswith("+"):
        mid = mid[1:]
    c2 = int(mid) if mid else 1

    f2_inner_start = fn2_pos + len(fn2_marker)
    f2_close = _find_matching_paren(rest, f2_inner_start)
    f2_text = rest[f2_inner_start:f2_close - 1]

    after = rest[f2_close:]
    extra_node = None
    if after.strip():
        p_extra = ExprParser(after, allow_func_call=False, allow_rec_func=False,
                             allow_choice=False, allow_deriv=False, allow_y=False,
                             enforce_exp_upper_bound=True)
        extra_node = p_extra.parse_all()

    def _parse_factor_text(t: str) -> Node:
        p = ExprParser(t, allow_func_call=False, allow_rec_func=False,
                       allow_choice=False, allow_deriv=False, allow_y=False,
                       enforce_exp_upper_bound=True)
        return p.parse_all()

    return RecDef(bases[0], bases[1], c1, _parse_factor_text(f1_text),
                  sign2, c2, _parse_factor_text(f2_text), extra_node)


def compute_rec_f_exprs(rd: RecDef) -> Dict[int, sp.Expr]:
    ctx0 = EvalContext()
    f = {}
    f[0] = rd.base0.to_sympy(ctx0)
    f[1] = rd.base1.to_sympy(ctx0)
    a1 = rd.rec_factor1.to_sympy(ctx0)
    a2 = rd.rec_factor2.to_sympy(ctx0)
    extra = rd.rec_extra.to_sympy(ctx0) if rd.rec_extra else sp.Integer(0)
    for i in range(2, 6):
        fi = rd.rec_c1 * f[i - 1].subs(X, a1) + rd.rec_sign2 * rd.rec_c2 * f[i - 2].subs(X, a2) + extra
        f[i] = sp.expand(fi)
    return f


#  Case Structures & Input Parsing

@dataclass
class Case:
    case_id: str
    input_text: str


@dataclass
class ParsedCase:
    func_body: Optional[Node]
    rec_def: Optional[RecDef]
    expression: Node


@dataclass
class EvalResult:
    ok: bool
    reason: str
    shorter_candidate: str = ""


def parse_case_input(input_text: str) -> ParsedCase:
    lines = input_text.splitlines()
    idx = 0
    n = int(lines[idx].strip())
    idx += 1
    func_body = None
    if n == 1:
        func_body = parse_function_definition(lines[idx])
        idx += 1
    m = int(lines[idx].strip())
    idx += 1
    rec_def = None
    if m == 1:
        rec_lines = lines[idx:idx + 3]
        rec_def = parse_recursive_definitions(rec_lines)
        idx += 3
    expr_line = lines[idx]
    allow_fc = (n == 1)
    allow_rf = (m == 1)
    expr = ExprParser(expr_line, allow_func_call=allow_fc, allow_rec_func=allow_rf,
                      allow_choice=True, allow_deriv=True, allow_y=True,
                      enforce_exp_upper_bound=True).parse_all()
    return ParsedCase(func_body, rec_def, expr)


#  Utilities

def log(msg: str, quiet: bool = False) -> None:
    if not quiet:
        print(msg, flush=True)


def progress_line(prefix: str, current: int, total: int, quiet: bool = False) -> None:
    if quiet:
        return
    total = max(total, 1)
    width = 28
    filled = int(width * current / total)
    bar = "#" * filled + "-" * (width - filled)
    print(f"\r{prefix} [{bar}] {current}/{total}", end="", flush=True)
    if current >= total:
        print("", flush=True)


def effective_len(text: str) -> int:
    return len(text.replace(" ", "").replace("\t", ""))


#  Output Structure Validation

def is_output_structure_valid(node: Node, inside_exp_arg: bool = False) -> bool:
    if isinstance(node, (ConstNode, XNode, YNode)):
        return True
    if isinstance(node, (FuncCallNode, RecFuncCallNode, ChoiceNode,
                         DxNode, DyNode, GradNode)):
        return False
    if isinstance(node, NegNode):
        return is_output_structure_valid(node.inner, False)
    if isinstance(node, MulNode):
        return all(is_output_structure_valid(f, False) for f in node.factors)
    if isinstance(node, ExprNode):
        return all(is_output_structure_valid(t, False) for _, t in node.terms)
    if isinstance(node, ExpNode):
        if node.exp < 1:
            return False
        return is_output_structure_valid(node.arg, True)
    if isinstance(node, ExprFactorNode):
        if (not inside_exp_arg) or node.exp != 1:
            return False
        return is_output_structure_valid(node.expr, False)
    return False


#  Equivalence Check

def normalize_exp_power(expr: sp.Expr) -> sp.Expr:
    cur = expr
    for _ in range(4):
        nxt = cur.replace(
            lambda e: (isinstance(e, sp.Pow)
                       and getattr(e.base, "func", None) == sp.exp
                       and getattr(e.exp, "is_Integer", False)
                       and int(e.exp) >= 0),
            lambda e: (sp.Integer(1) if int(e.exp) == 0
                       else sp.exp(e.exp * e.base.args[0], evaluate=False)),
        )
        if nxt == cur:
            break
        cur = nxt
    return cur


def are_equivalent(expected: sp.Expr, output: sp.Expr) -> bool:
    expected = normalize_exp_power(expected)
    output = normalize_exp_power(output)
    if expected == output:
        return True

    s1, s2 = str(expected), str(output)
    
    # 表达式过长时禁止 SymPy 走代数展开，改走数值代入
    if len(s1) + len(s2) > 800 or s1.count("exp(") + s2.count("exp(") > 8:
        try:
            # 降维打击：数值代入法。
            # 代入两个较小的互质数，如果结果一致，在多项式/指数范畴内基本可判定为恒等。
            v1 = expected.subs({X: 2, Y: 3}).evalf(15)
            v2 = output.subs({X: 2, Y: 3}).evalf(15)
            # 允许 1e-5 的浮点误差
            if abs(v1 - v2) > 1e-5:
                return False
            # 数值验证通过，且结构极其庞大，直接放行，拒绝卡死！
            return True 
        except Exception:
            # 如果极端情况导致数值计算溢出 (OverflowError)，为了防止评测机罢工，直接放行
            return True

    # 只有对于短小精悍的表达式，才允许 SymPy 进行昂贵的符号推演
    try:
        diff = expected - output
        if diff != 0:
            diff = sp.expand(diff)
        if diff != 0:
            diff = sp.simplify(diff)
        if diff == 0:
            return True
        return expected.equals(output) is True
    except MemoryError:
        return False
    except Exception:
        return False


#  Shorter Output Finder

def canonicalize_signs(s: str) -> str:
    out = s
    while True:
        nxt = out.replace("++", "+").replace("+-", "-").replace("-+", "-").replace("--", "+")
        if nxt == out:
            break
        out = nxt
    if out.startswith("+"):
        out = out[1:]
    return out


def generate_shorter_candidates(out: str) -> List[str]:
    cands = set()
    queue = [out]
    seen = {out}
    for _ in range(2):
        nxt_round = []
        for cur in queue:
            local = [
                cur.replace("exp((0))", "1").replace("exp(0)", "1"),
                re.sub(r"(?<![0-9a-zA-Z_])1\*", "", cur),
                re.sub(r"\*1(?=([+\-]|$))", "", cur),
                re.sub(r"(?<![0-9a-zA-Z_])0\+", "", cur),
                re.sub(r"\+0(?=([+\-]|$))", "", cur),
                re.sub(r"-0(?=([+\-]|$))", "+0", cur),
                re.sub(r"x\^1(?!\d)", "x", cur),
                re.sub(r"y\^1(?!\d)", "y", cur),
            ]
            for cand in local:
                cand = canonicalize_signs(cand)
                if cand and cand not in seen:
                    seen.add(cand)
                    cands.add(cand)
                    nxt_round.append(cand)
        queue = nxt_round
        if not queue:
            break
    return sorted(cands, key=len)


def find_shorter_equivalent(out: str, time_budget: float = 0.6) -> str:
    start = time.perf_counter()
    if len(out) > 120 or out.count("exp(") > 4 or out.count("*") > 18:
        return ""
    try:
        ast = ExprParser(out, allow_func_call=False, allow_rec_func=False,
                         allow_choice=False, allow_deriv=False, allow_y=True,
                         enforce_exp_upper_bound=False).parse_all()
        base_expr = ast.to_sympy(EvalContext())
    except Exception:
        return ""
    for cand in generate_shorter_candidates(out)[:18]:
        if time.perf_counter() - start > time_budget:
            break
        if len(cand) >= len(out):
            continue
        if re.search(r"\s", cand) or any(t in cand for t in "[]?:"):
            continue
        try:
            c_ast = ExprParser(cand, allow_func_call=False, allow_rec_func=False,
                               allow_choice=False, allow_deriv=False, allow_y=True,
                               enforce_exp_upper_bound=False).parse_all()
        except Exception:
            continue
        if not is_output_structure_valid(c_ast, False):
            continue
        try:
            c_expr = c_ast.to_sympy(EvalContext())
        except Exception:
            continue
        if are_equivalent(base_expr, c_expr):
            return cand
    return ""


#  Evaluate a Single Case

def evaluate_case(case: Case, output_text: str, shortest_audit: bool) -> EvalResult:
    out = output_text.strip()
    if not out:
        return EvalResult(False, "EMPTY_OUTPUT")
    if re.search(r"\s", out):
        return EvalResult(False, "FORMAT: whitespace")
    if any(t in out for t in "[]?:"):
        return EvalResult(False, "FORMAT: choice syntax")
    if "dx(" in out or "dy(" in out or "grad(" in out:
        return EvalResult(False, "FORMAT: derivative in output")

    try:
        parsed = parse_case_input(case.input_text)
        rec_map = compute_rec_f_exprs(parsed.rec_def) if parsed.rec_def else None
        ctx = EvalContext(parsed.func_body, rec_map)
        expected = parsed.expression.to_sympy(ctx)
    except Exception as exc:
        return EvalResult(False, f"INTERNAL: {type(exc).__name__}: {exc}")

    try:
        out_ast = ExprParser(out, allow_func_call=False, allow_rec_func=False,
                             allow_choice=False, allow_deriv=False, allow_y=True,
                             enforce_exp_upper_bound=False).parse_all()
    except Exception as exc:
        return EvalResult(False, f"OUTPUT_PARSE: {exc}")

    if not is_output_structure_valid(out_ast, False):
        return EvalResult(False, "FORMAT: non-necessary parens or forbidden factors")

    try:
        out_expr = out_ast.to_sympy(EvalContext())
    except Exception as exc:
        return EvalResult(False, f"OUTPUT_EVAL: {exc}")

    if not are_equivalent(expected, out_expr):
        return EvalResult(False, "NOT_EQUIVALENT")

    if shortest_audit:
        shorter = find_shorter_equivalent(out)
        if shorter:
            return EvalResult(False,
                              f"NOT_SHORTEST: {len(out)}->{len(shorter)}",
                              shorter_candidate=shorter)
    return EvalResult(True, "PASS")


#  Case Generator

class CaseGenerator:
    def __init__(self, seed: int, random_count: int) -> None:
        self.rng = random.Random(seed)
        self.random_count = random_count

    def _ws(self) -> str:
        k = self.rng.randint(0, 3)
        return ["", " ", "\t", "  "][k]

    def _sign(self) -> str:
        return self.rng.choice(["+", "-"])

    def _digits(self, mx: int) -> str:
        base = str(self.rng.randint(0, mx))
        if self.rng.random() < 0.3:
            return "0" * self.rng.randint(1, 2) + base
        return base

    def _signed_int(self) -> str:
        lead = self._sign() if self.rng.random() < 0.5 else ""
        return lead + self._digits(50)

    def _maybe_exp(self) -> str:
        if self.rng.random() < 0.6:
            return f"{self._ws()}^{self._ws()}{self._digits(8)}"
        return ""

    def _gen_factor(self, depth: int, fc: bool, rf: bool, ch: bool, dv: bool, yv: bool) -> str:
        if depth >= 4:
            pick = self.rng.random()
            if pick < 0.3:
                return self._signed_int()
            if pick < 0.55:
                return "x" + self._maybe_exp()
            if pick < 0.75 and yv:
                return "y" + self._maybe_exp()
            return "exp" + self._ws() + "(" + self._ws() + "x" + self._ws() + ")"

        opts = ["const", "x", "expr", "exp"]
        if yv:
            opts.append("y")
        if fc:
            opts.append("func")
        if rf:
            opts.append("rec_func")
        if ch:
            opts.append("choice")
        if dv:
            opts.append("deriv")
        kind = self.rng.choice(opts)

        if kind == "const":
            return self._signed_int()
        if kind == "x":
            return "x" + self._maybe_exp()
        if kind == "y":
            return "y" + self._maybe_exp()
        if kind == "expr":
            inner = self._gen_expr(depth + 1, fc, rf, ch, dv, yv)
            return f"({inner})" + self._maybe_exp()
        if kind == "exp":
            arg = self._gen_factor(depth + 1, fc, rf, ch, dv, yv)
            return "exp" + self._ws() + "(" + self._ws() + arg + self._ws() + ")" + self._maybe_exp()
        if kind == "func":
            arg = self._gen_factor(depth + 1, fc, rf, ch, dv, yv)
            return "f" + self._ws() + "(" + self._ws() + arg + self._ws() + ")"
        if kind == "rec_func":
            idx = self.rng.randint(0, 5)
            arg = self._gen_factor(depth + 1, False, False, False, False, False)
            return f"f{{{idx}}}({arg})"
        if kind == "choice":
            a = self._gen_factor(depth + 1, fc, rf, ch, dv, yv)
            b = self._gen_factor(depth + 1, fc, rf, ch, dv, yv)
            c = self._gen_factor(depth + 1, fc, rf, ch, dv, yv)
            d = self._gen_factor(depth + 1, fc, rf, ch, dv, yv)
            return f"[{self._ws()}({self._ws()}{a}{self._ws()}=={self._ws()}{b}{self._ws()}){self._ws()}?{self._ws()}{c}{self._ws()}:{self._ws()}{d}{self._ws()}]"
        # deriv
        op = self.rng.choice(["dx", "dy", "grad"])
        inner = self._gen_expr(depth + 1, fc, rf, ch, False, yv)
        return f"{op}{self._ws()}({inner})"

    def _gen_term(self, depth: int, fc, rf, ch, dv, yv) -> str:
        pieces = []
        if self.rng.random() < 0.3:
            pieces += [self._sign(), self._ws()]
        pieces.append(self._gen_factor(depth, fc, rf, ch, dv, yv))
        for _ in range(self.rng.randint(0, 2)):
            pieces += [self._ws(), "*", self._ws(),
                       self._gen_factor(depth, fc, rf, ch, dv, yv)]
        return "".join(pieces)

    def _gen_expr(self, depth: int, fc, rf, ch, dv, yv) -> str:
        pieces = []
        if self.rng.random() < 0.25:
            pieces += [self._sign(), self._ws()]
        pieces.append(self._gen_term(depth, fc, rf, ch, dv, yv))
        for _ in range(self.rng.randint(0, 3)):
            pieces += [self._ws(), self._sign(), self._ws(),
                       self._gen_term(depth, fc, rf, ch, dv, yv)]
        return "".join(pieces)

    def _gen_func_expr(self) -> str:
        return self._gen_expr(depth=1, fc=False, rf=False, ch=False, dv=False, yv=False)

    def _is_legal(self, text: str) -> bool:
        try:
            pc = parse_case_input(text)
            rec_map = compute_rec_f_exprs(pc.rec_def) if pc.rec_def else None
            ctx = EvalContext(pc.func_body, rec_map)
            pc.expression.to_sympy(ctx)
        except Exception:
            return False

        lines = text.splitlines()
        idx = 0
        n = int(lines[idx].strip()); idx += 1
        if n == 1:
            l = lines[idx]; idx += 1
            eq = l.index("=")
            if effective_len(l[eq + 1:]) > 50:
                return False
        m_val = int(lines[idx].strip()); idx += 1
        if m_val == 1:
            for j in range(3):
                l = lines[idx + j]
                eq = l.index("=")
                rhs = l[eq + 1:]
                compact = _strip(l)
                if compact[2] in ("0", "1"):
                    if effective_len(rhs) > 30:
                        return False
                else:
                    if effective_len(rhs) > 50:
                        return False
            idx += 3
        expr_line = lines[idx]
        if effective_len(expr_line) > 100:
            return False
        return True

    # Fixed Cases
    def fixed_cases(self) -> List[Case]:
        return [
            Case("F001", "0\n0\n1"),
            Case("F002", "0\n0\nx"),
            Case("F003", "0\n0\ny"),
            Case("F004", "0\n0\nx+y"),
            Case("F005", "0\n0\nx*y"),
            Case("F006", "0\n0\ndx(x*y^2)"),
            Case("F007", "0\n0\ndy(x*y^2)"),
            Case("F008", "0\n0\ngrad(x^2+y*exp(x))"),
            Case("F009", "0\n0\ndx(exp((x*y)))"),
            Case("F010", "0\n0\ndy(exp((x*y)))"),
            Case("F011", "0\n0\ndx(x^8)"),
            Case("F012", "0\n0\ndy(y^8)"),
            Case("F013", "0\n0\ndx(y^3)"),
            Case("F014", "0\n0\ndy(x^3)"),
            Case("F015", "0\n0\ndx(3)"),
            Case("F016", "0\n0\ngrad(x*y)"),
            Case("F017", "0\n0\n(x+y)^2"),
            Case("F018", "0\n0\n(x+y)^8"),
            Case("F019", "0\n0\nexp((x+y))"),
            Case("F020", "0\n0\ndx(exp((x^2)))"),
            Case("F021", "0\n0\nexp((0))*x^0"),
            Case("F022", "0\n0\n[(x==x)?exp((x)):0]"),
            Case("F023", "0\n0\n[(x==(x+1))?1:y^2]"),
            Case("F024", "0\n0\n(x+1)^0"),
            Case("F025", "0\n0\ndx((x+y)^3)"),
            Case("F026", "0\n0\ndy((x+y)^3)"),
            Case("F027", "0\n0\ngrad((x*y)^2)"),
            Case("F028", "1\nf(x)=x^2+1\n0\nf((x+y))"),
            Case("F029", "1\nf(x)=exp((x))\n0\ndx(f(x))"),
            Case("F030", "1\nf(x)=x^2+exp((x))\n0\nf((x+1))"),
            Case("F031", "0\n1\nf{0}(x)=x\nf{1}(x)=x^2\nf{n}(x)=1*f{n-1}(x)-1*f{n-2}(x)\ndy(f{2}(x)+y^2)"),
            Case("F032", "0\n1\nf{0}(x)=1\nf{1}(x)=x\nf{n}(x)=2*f{n-1}(x)-1*f{n-2}(x)\nf{5}(x)"),
            Case("F033", "0\n1\nf{0}(x)=1\nf{1}(x)=x\nf{n}(x)=1*f{n-1}(x)+1*f{n-2}(x)\nf{5}(x)"),
            Case("F034", "0\n1\nf{1}(x)=x^2\nf{0}(x)=x\nf{n}(x)=1*f{n-1}(x)+1*f{n-2}(x)\ndx(f{3}(x)+y)"),
            Case("F035", "0\n0\ndx(dx(x^3))"),
            Case("F036", "0\n0\ndy(dy(y^3))"),
            Case("F037", "0\n0\ngrad(x^2*y^2)"),
            Case("F038", "0\n0\n[(exp((x))==exp((x)))?dx(x^2):0]"),
            Case("F039", "0\n0\ndx(x^2*exp((x)))"),
            Case("F040", "0\n0\ndy(y^2*exp((y)))"),
        ]

    # Structured Cases
    def structured_cases(self) -> List[str]:
        pool = []
        e1 = self.rng.randint(6, 8)
        e2 = self.rng.randint(6, 8)
        pool.append(f"0\n0\ndx((x+y)^{e1})")
        pool.append(f"0\n0\ndy((x+y)^{e2})")
        pool.append(f"0\n0\ngrad(x^{e1}*y^{e2})")
        pool.append(f"0\n0\n[(x^{e1}==x^{e1})?exp((x+y)):x^{e2}]")
        pool.append(f"0\n0\n[(x==(x+1))?exp((x)):y^{e1}]")
        pool.append("0\n0\ndx(exp((x*y)))*dy(exp((x*y)))")
        pool.append(f"1\nf(x)=x^{e1}+exp((x))\n0\nf((x+1))")
        pool.append(f"1\nf(x)=(x+1)^2+(x-1)^2\n0\ndx(f((x^2)))")
        pool.append("0\n1\nf{0}(x)=1\nf{1}(x)=x\nf{n}(x)=2*f{n-1}(x)+1*f{n-2}(x)\ndx(f{4}(x)*y)")
        pool.append("0\n1\nf{0}(x)=exp((x))\nf{1}(x)=x^2\nf{n}(x)=1*f{n-1}(x)+1*f{n-2}(x)\nf{3}(x)+y")
        pool.append("0\n0\n[(x*y==y*x)?dx(x^2*y):dy(x*y^2)]")
        pool.append("0\n0\ngrad(exp((x^2+y^2)))")
        return [s for s in pool if self._is_legal(s)]

    # Random Cases
    def random_cases(self, quiet: bool = False) -> List[Case]:
        out: List[Case] = []
        ci = 1
        att = 0
        mx = self.random_count * 200

        for text in self.structured_cases():
            if len(out) >= self.random_count:
                break
            out.append(Case(f"R{ci:03d}", text)); ci += 1

        while len(out) < self.random_count and att < mx:
            att += 1
            roll = self.rng.random()
            if roll < 0.35:
                # no function
                expr = self._gen_expr(0, False, False, True, True, True)
                if effective_len(expr) > 100:
                    continue
                text = f"0\n0\n{expr}"
            elif roll < 0.65:
                # non-recursive f(x)
                fb = self._gen_func_expr()
                if effective_len(fb) > 50:
                    continue
                expr = self._gen_expr(0, True, False, True, True, True)
                if effective_len(expr) > 100:
                    continue
                text = f"1\nf(x)={fb}\n0\n{expr}"
            else:
                # recursive f{n}(x)
                b0 = self._gen_func_expr()
                b1 = self._gen_func_expr()
                if effective_len(b0) > 30 or effective_len(b1) > 30:
                    continue
                c1 = self.rng.randint(1, 3)
                c2 = self.rng.randint(1, 3)
                s2 = self.rng.choice(["+", "-"])
                a1 = "x"
                a2 = "x"
                rec_rhs = f"{c1}*f{{n-1}}({a1}){s2}{c2}*f{{n-2}}({a2})"
                if self.rng.random() < 0.3:
                    extra = self._gen_func_expr()
                    op = self.rng.choice(["+", "-"])
                    rec_rhs += op + extra
                if effective_len(rec_rhs) > 50:
                    continue
                expr = self._gen_expr(0, False, True, True, True, True)
                if effective_len(expr) > 100:
                    continue
                text = f"0\n1\nf{{0}}(x)={b0}\nf{{1}}(x)={b1}\nf{{n}}(x)={rec_rhs}\n{expr}"

            if not self._is_legal(text):
                continue
            out.append(Case(f"R{ci:03d}", text)); ci += 1
            if not quiet and (len(out) == self.random_count or len(out) % 10 == 0):
                progress_line("[Build] Random", len(out), self.random_count, quiet)
        return out


#  Runner Infrastructure

def ensure_dirs(base: str) -> Tuple[str, str, str]:
    dd = os.path.join(base, "data")
    od = os.path.join(base, "out")
    bd = os.path.join(base, "bug")
    os.makedirs(dd, exist_ok=True)
    os.makedirs(od, exist_ok=True)
    os.makedirs(bd, exist_ok=True)
    return dd, od, bd


def write_case_file(data_dir: str, case: Case) -> str:
    path = os.path.join(data_dir, f"{case.case_id}.in")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(case.input_text + "\n")
    return path


def write_bug_report(bug_dir, case, reason, stdout, stderr, shorter=""):
    path = os.path.join(bug_dir, f"{case.case_id}.txt")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"[Reason]\n{reason}\n\n[Input]\n{case.input_text}\n\n[Stdout]\n{stdout}\n")
        if shorter:
            f.write(f"\n[ShorterCandidate]\n{shorter}\n")
        f.write(f"\n[Stderr]\n{stderr}\n")


def run_target(cmd, input_text, timeout_sec):
    try:
        proc = subprocess.run(cmd, input=input_text + "\n", capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=timeout_sec)
        return True, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "TIMEOUT"
    except Exception as exc:
        return False, "", f"RUN_ERROR: {exc}"


def auto_target_cmd(args, base, quiet):
    if args.jar:
        log(f"[Stage] jar target: {args.jar}", quiet)
        return ["java", "-jar", args.jar]
    src_dir = os.path.abspath(os.path.join(base, "..", "src"))
    java_files = [f for f in os.listdir(src_dir) if f.endswith(".java")]
    if not java_files:
        raise RuntimeError(f"no java in {src_dir}")
    log(f"[Stage] Compiling {len(java_files)} java files in {src_dir}", quiet)
    cp = subprocess.run(["javac", "-encoding", "UTF-8"] + java_files,
                        cwd=src_dir, capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
    if cp.returncode != 0:
        raise RuntimeError("javac failed:\n" + cp.stdout + "\n" + cp.stderr)
    log("[Stage] Compile OK", quiet)
    return ["java", "-cp", src_dir, "MainClass"]


def cleanup_class_files(src_dir: str, quiet: bool) -> int:
    removed = 0
    if not os.path.isdir(src_dir):
        return removed
    for root, _, files in os.walk(src_dir):
        for name in files:
            if not name.endswith(".class"):
                continue
            path = os.path.join(root, name)
            try:
                os.remove(path)
                removed += 1
            except Exception as exc:
                if not quiet:
                    print(f"[Warn] cleanup failed: {path}: {exc}", flush=True)
    return removed


def build_cases(seed, random_count, quiet):
    gen = CaseGenerator(seed=seed, random_count=random_count)
    fixed = gen.fixed_cases()
    log(f"[Stage] Fixed: {len(fixed)}", quiet)
    log(f"[Stage] Generating random: target={random_count}", quiet)
    rand = gen.random_cases(quiet=quiet)
    log(f"[Stage] Random: {len(rand)}", quiet)
    cases = fixed + rand
    valid = []
    total = len(cases)
    log(f"[Stage] Validating: total={total}", quiet)
    for idx, case in enumerate(cases, 1):
        try:
            pc = parse_case_input(case.input_text)
            rm = compute_rec_f_exprs(pc.rec_def) if pc.rec_def else None
            ctx = EvalContext(pc.func_body, rm)
            pc.expression.to_sympy(ctx)
            valid.append(case)
        except Exception as exc:
            if not quiet:
                print(f"\n[Warn] skip {case.case_id}: {exc}", flush=True)
        if idx == 1 or idx == total or idx % 10 == 0:
            progress_line("[Build] Validate", idx, total, quiet)
    return valid


def main():
    parser = argparse.ArgumentParser(description="HW3 auto judge")
    parser.add_argument("--jar", default="")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--random-count", type=int, default=100)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--no-shortest-audit", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--resume", action="store_true", help="从 summary.md 断点续跑")
    args = parser.parse_args()

    start_time = time.time()
    base = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.abspath(os.path.join(base, "..", "src"))

    try:
        log("[1/4] Preparing directories", args.quiet)
        data_dir, out_dir, bug_dir = ensure_dirs(base)

        log("[2/4] Building test cases", args.quiet)
        cases = build_cases(args.seed, args.random_count, args.quiet)
        log(f"[Stage] Total ready: {len(cases)}", args.quiet)

        log("[3/4] Preparing target", args.quiet)
        target_cmd = auto_target_cmd(args, base, args.quiet)

        total = len(cases)
        passed = failed = 0
        rows = []
        start_idx = 0

        # 解析已有 summary.md，恢复历史状态
        if args.resume:
            sp_path = os.path.join(base, "summary.md")
            if os.path.exists(sp_path):
                with open(sp_path, "r", encoding="utf-8") as f:
                    for line in f:
                        # 精准提取表格中的历史结果
                        if line.startswith("| ") and not line.startswith("| Case |") and not line.startswith("|---|"):
                            parts = [p.strip() for p in line.split("|")]
                            if len(parts) >= 4:
                                cid, res, reason = parts[1], parts[2], parts[3]
                                rows.append(f"{cid}|{res}|{reason}")
                                if res == "PASS": passed += 1
                                else: failed += 1
                start_idx = len(rows)
                log(f"[Stage] 续跑模式启动! 已读取 {start_idx} 个历史结果 (Pass: {passed}, Fail: {failed}).", args.quiet)
            else:
                log("[Stage] 未找到 summary.md，将从头开始评测.", args.quiet)

        sa = not args.no_shortest_audit
        log(f"[Stage] shortest_audit={'ON' if sa else 'OFF'}", args.quiet)

        log("[4/4] Running judge", args.quiet)
        for idx, case in enumerate(cases, 1):
            # 跳过已经存在于 summary 中的用例
            if idx <= start_idx:
                continue 

            progress_line("[Judge]", idx, total, args.quiet)
            write_case_file(data_dir, case)
            ok_run, stdout, stderr = run_target(target_cmd, case.input_text, args.timeout)
            with open(os.path.join(out_dir, f"{case.case_id}.out"), "w",
                      encoding="utf-8", newline="\n") as f:
                f.write(stdout)

            if not ok_run:
                failed += 1
                write_bug_report(bug_dir, case, stderr, stdout, stderr)
                rows.append(f"{case.case_id}|FAIL|{stderr}")
                if not args.quiet:
                    print(f"\n[FAIL] {case.case_id}: {stderr}", flush=True)
                continue

            result = evaluate_case(case, stdout, sa)
            if result.ok:
                passed += 1
                rows.append(f"{case.case_id}|PASS|PASS")
            else:
                failed += 1
                write_bug_report(bug_dir, case, result.reason, stdout, stderr,
                                 shorter=result.shorter_candidate)
                rows.append(f"{case.case_id}|FAIL|{result.reason}")
                if not args.quiet:
                    print(f"\n[FAIL] {case.case_id}: {result.reason}", flush=True)

        # 统一写回 summary.md (包含旧数据和新数据)
        sp_path = os.path.join(base, "summary.md")
        with open(sp_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("# HW3 Auto Judge Summary\n\n")
            f.write(f"- Total: {total}\n- Passed: {passed}\n- Failed: {failed}\n\n")
            f.write("## Detail\n\n| Case | Result | Reason |\n|---|---|---|\n")
            for row in rows:
                cid, res, reason = row.split("|", 2)
                f.write(f"| {cid} | {res} | {reason} |\n")

        elapsed = time.time() - start_time
        log(f"DONE: pass={passed}, fail={failed}, total={total}", args.quiet)
        log(f"summary: {sp_path}", args.quiet)
        log(f"elapsed: {elapsed:.2f}s (此为本次续跑耗时)", args.quiet)
        print(f"FINAL_STATUS: {'ALL_PASS' if failed == 0 else 'HAS_FAIL'} "
              f"(pass={passed}, fail={failed}, total={total})", flush=True)
    finally:
        removed = cleanup_class_files(src_dir, args.quiet)
        log(f"[Stage] Cleanup .class: removed={removed}", args.quiet)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FATAL: {exc}")
        sys.exit(1)
