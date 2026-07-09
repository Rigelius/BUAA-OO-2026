import argparse
import os
import random
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

try:
    import sympy as sp
except Exception as exc:  # pragma: no cover
    print(f"FATAL: sympy is required: {exc}")
    sys.exit(1)


X = sp.Symbol("x")


class ParseError(Exception):
    pass


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


class Node:
    def to_sympy(self, ctx: "EvalContext") -> sp.Expr:
        raise NotImplementedError


@dataclass
class ConstNode(Node):
    value: int

    def to_sympy(self, ctx: "EvalContext") -> sp.Expr:
        return sp.Integer(self.value)


@dataclass
class XNode(Node):
    exp: int

    def to_sympy(self, ctx: "EvalContext") -> sp.Expr:
        return X ** self.exp


@dataclass
class ExprFactorNode(Node):
    expr: Node
    exp: int

    def to_sympy(self, ctx: "EvalContext") -> sp.Expr:
        return self.expr.to_sympy(ctx) ** self.exp


@dataclass
class ExpNode(Node):
    arg: Node
    exp: int

    def to_sympy(self, ctx: "EvalContext") -> sp.Expr:
        # Keep exp construction unevaluated to prevent SymPy from exploding on
        # deeply nested exponentials during object construction.
        arg_expr = self.arg.to_sympy(ctx)
        base = sp.exp(arg_expr, evaluate=False)
        if self.exp == 1:
            return base
        return sp.Pow(base, sp.Integer(self.exp), evaluate=False)


@dataclass
class FuncCallNode(Node):
    arg: Node

    def to_sympy(self, ctx: "EvalContext") -> sp.Expr:
        if ctx.func_body is None:
            raise ParseError("function call appears but no function definition is provided")
        arg_expr = self.arg.to_sympy(ctx)
        body_expr = ctx.func_body.to_sympy(ctx)
        return body_expr.subs(X, arg_expr)


@dataclass
class ChoiceNode(Node):
    a: Node
    b: Node
    c: Node
    d: Node

    def to_sympy(self, ctx: "EvalContext") -> sp.Expr:
        left = self.a.to_sympy(ctx)
        right = self.b.to_sympy(ctx)
        if left == right:
            is_equal = True
        else:
            # Lightweight identity check to avoid symbolic blow-ups on deep exp chains.
            try:
                eq2 = left.equals(right)
                is_equal = (eq2 is True)
            except Exception:
                is_equal = False
        if is_equal:
            return self.c.to_sympy(ctx)
        return self.d.to_sympy(ctx)


@dataclass
class MulNode(Node):
    factors: List[Node]

    def to_sympy(self, ctx: "EvalContext") -> sp.Expr:
        out = sp.Integer(1)
        for fac in self.factors:
            out *= fac.to_sympy(ctx)
        return out


@dataclass
class NegNode(Node):
    inner: Node

    def to_sympy(self, ctx: "EvalContext") -> sp.Expr:
        return -self.inner.to_sympy(ctx)


@dataclass
class ExprNode(Node):
    terms: List[Tuple[int, Node]]

    def to_sympy(self, ctx: "EvalContext") -> sp.Expr:
        out = sp.Integer(0)
        for sign, term in self.terms:
            term_expr = term.to_sympy(ctx)
            out += term_expr if sign > 0 else -term_expr
        return out


@dataclass
class EvalContext:
    func_body: Optional[Node]


class ExprParser:
    def __init__(
        self,
        text: str,
        *,
        allow_func_call: bool,
        allow_choice: bool,
        enforce_exp_upper_bound: bool,
    ) -> None:
        self.lex = Lexer(text)
        self.allow_func_call = allow_func_call
        self.allow_choice = allow_choice
        self.enforce_exp_upper_bound = enforce_exp_upper_bound

    def parse_all(self) -> Node:
        node = self.parse_expr()
        if self.lex.peek() is not None:
            raise ParseError(f"trailing token at index {self.lex.i}")
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
        terms: List[Tuple[int, Node]] = [(first_sign, first_term)]

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

        factors: List[Node] = [self.parse_factor()]
        while self.lex.take("*"):
            factors.append(self.parse_factor())

        node: Node = factors[0] if len(factors) == 1 else MulNode(factors)
        if sign < 0:
            node = NegNode(node)
        return node

    def parse_factor(self) -> Node:
        ch = self.lex.peek()
        if ch is None:
            raise ParseError("unexpected end while parsing factor")

        if ch == "[":
            if not self.allow_choice:
                raise ParseError("choice factor is not allowed in this context")
            return self.parse_choice_factor()

        if self.lex.starts_with("exp"):
            return self.parse_exp_factor()

        if self.lex.starts_with("f"):
            if not self.allow_func_call:
                raise ParseError("function call is not allowed in this context")
            return self.parse_func_call()

        if ch == "x":
            self.lex.take("x")
            exp = self.parse_optional_exponent(default=1)
            return XNode(exp)

        if ch == "(":
            self.lex.take("(")
            inner = self.parse_expr()
            self.lex.expect(")")
            exp = self.parse_optional_exponent(default=1)
            return ExprFactorNode(inner, exp)

        sign = 1
        if self.lex.take("+"):
            sign = 1
        elif self.lex.take("-"):
            sign = -1

        digits = self.lex.take_digits()
        if digits is None:
            raise ParseError(f"invalid number token at index {self.lex.i}")
        value = int(digits)
        if sign < 0:
            value = -value
        return ConstNode(value)

    def parse_choice_factor(self) -> Node:
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

    def parse_exp_factor(self) -> Node:
        self.lex.take_token("exp")
        self.lex.expect("(")
        arg = self.parse_factor()
        self.lex.expect(")")
        exp = self.parse_optional_exponent(default=1)
        return ExpNode(arg, exp)

    def parse_func_call(self) -> Node:
        self.lex.take_token("f")
        self.lex.expect("(")
        arg = self.parse_factor()
        self.lex.expect(")")
        return FuncCallNode(arg)

    def parse_optional_exponent(self, default: int) -> int:
        if not self.lex.take("^"):
            return default
        self.lex.take("+")
        digits = self.lex.take_digits()
        if digits is None:
            raise ParseError(f"invalid exponent at index {self.lex.i}")
        exp = int(digits)
        if exp < 0:
            raise ParseError("negative exponent not allowed")
        if self.enforce_exp_upper_bound and exp > 8:
            raise ParseError("exponent exceeds guidebook limit")
        return exp


def parse_function_definition(line: str) -> Node:
    compact = "".join(ch for ch in line if ch not in (" ", "\t"))
    if "=" not in compact:
        raise ParseError("function definition has no '='")
    left, right = compact.split("=", 1)
    if left != "f(x)":
        raise ParseError("function definition must be exactly f(x)=Expr")
    if not right:
        raise ParseError("function body is empty")
    parser = ExprParser(
        right,
        allow_func_call=False,
        allow_choice=False,
        enforce_exp_upper_bound=True,
    )
    return parser.parse_all()


@dataclass
class Case:
    case_id: str
    input_text: str


@dataclass
class ParsedCase:
    function_body: Optional[Node]
    expression: Node


@dataclass
class EvalResult:
    ok: bool
    reason: str
    shorter_candidate: str = ""


def parse_case_input(input_text: str) -> ParsedCase:
    lines = input_text.splitlines()
    if not lines:
        raise ParseError("empty input")

    n = int(lines[0].strip())
    if n == 0:
        if len(lines) < 2:
            raise ParseError("missing expression line")
        expr_line = lines[1]
        expr = ExprParser(
            expr_line,
            allow_func_call=False,
            allow_choice=True,
            enforce_exp_upper_bound=True,
        ).parse_all()
        return ParsedCase(None, expr)

    if n == 1:
        if len(lines) < 3:
            raise ParseError("missing function or expression line")
        func_line = lines[1]
        expr_line = lines[2]
        func_body = parse_function_definition(func_line)
        expr = ExprParser(
            expr_line,
            allow_func_call=True,
            allow_choice=True,
            enforce_exp_upper_bound=True,
        ).parse_all()
        return ParsedCase(func_body, expr)

    raise ParseError("the first line n must be 0 or 1")


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


def is_output_structure_valid(node: Node, inside_exp_arg: bool = False) -> bool:
    if isinstance(node, (ConstNode, XNode)):
        return True

    if isinstance(node, FuncCallNode):
        return False

    if isinstance(node, ChoiceNode):
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
        # In HW2 output, expression-factor parentheses should remain only when
        # they are necessary as exp's direct argument and without an exponent.
        if (not inside_exp_arg) or node.exp != 1:
            return False
        return is_output_structure_valid(node.expr, False)

    return False


class CaseGenerator:
    def __init__(self, seed: int, random_count: int) -> None:
        self.rng = random.Random(seed)
        self.random_count = random_count

    def maybe_ws(self) -> str:
        k = self.rng.randint(0, 3)
        if k == 0:
            return ""
        if k == 1:
            return " " * self.rng.randint(1, 2)
        if k == 2:
            return "\t"
        return "\t" * self.rng.randint(1, 2)

    def sign(self) -> str:
        return self.rng.choice(["+", "-"])

    def digits(self, max_val: int) -> str:
        base = str(self.rng.randint(0, max_val))
        if self.rng.random() < 0.35:
            return "0" * self.rng.randint(1, 2) + base
        return base

    def signed_integer(self) -> str:
        lead = self.sign() if self.rng.random() < 0.5 else ""
        return lead + self.digits(50)

    def maybe_exponent(self) -> str:
        if self.rng.random() < 0.65:
            return f"{self.maybe_ws()}^{self.maybe_ws()}{self.digits(8)}"
        return ""

    def gen_factor(self, depth: int, allow_func: bool, allow_choice: bool) -> str:
        if depth >= 4:
            base_pick = self.rng.random()
            if base_pick < 0.4:
                return self.signed_integer()
            if base_pick < 0.75:
                return "x" + self.maybe_exponent()
            return "exp" + self.maybe_ws() + "(" + self.maybe_ws() + "x" + self.maybe_ws() + ")"

        options: List[str] = ["const", "x", "expr", "exp"]
        if allow_func:
            options.append("func")
        if allow_choice:
            options.append("choice")
        kind = self.rng.choice(options)

        if kind == "const":
            return self.signed_integer()

        if kind == "x":
            return "x" + self.maybe_exponent()

        if kind == "expr":
            inner = self.gen_expr(depth + 1, allow_func, allow_choice)
            return f"({inner})" + self.maybe_exponent()

        if kind == "exp":
            arg = self.gen_factor(depth + 1, allow_func, allow_choice)
            return (
                "exp"
                + self.maybe_ws()
                + "("
                + self.maybe_ws()
                + arg
                + self.maybe_ws()
                + ")"
                + self.maybe_exponent()
            )

        if kind == "func":
            arg = self.gen_factor(depth + 1, allow_func, allow_choice)
            return "f" + self.maybe_ws() + "(" + self.maybe_ws() + arg + self.maybe_ws() + ")"

        a = self.gen_factor(depth + 1, allow_func, allow_choice)
        b = self.gen_factor(depth + 1, allow_func, allow_choice)
        c = self.gen_factor(depth + 1, allow_func, allow_choice)
        d = self.gen_factor(depth + 1, allow_func, allow_choice)
        return (
            "["
            + self.maybe_ws()
            + "("
            + self.maybe_ws()
            + a
            + self.maybe_ws()
            + "=="
            + self.maybe_ws()
            + b
            + self.maybe_ws()
            + ")"
            + self.maybe_ws()
            + "?"
            + self.maybe_ws()
            + c
            + self.maybe_ws()
            + ":"
            + self.maybe_ws()
            + d
            + self.maybe_ws()
            + "]"
        )

    def gen_term(self, depth: int, allow_func: bool, allow_choice: bool) -> str:
        pieces: List[str] = []
        if self.rng.random() < 0.35:
            pieces.append(self.sign())
            pieces.append(self.maybe_ws())

        pieces.append(self.gen_factor(depth, allow_func, allow_choice))
        count = self.rng.randint(1, 3)
        for _ in range(1, count):
            pieces.append(self.maybe_ws())
            pieces.append("*")
            pieces.append(self.maybe_ws())
            pieces.append(self.gen_factor(depth, allow_func, allow_choice))
        return "".join(pieces)

    def gen_expr(self, depth: int, allow_func: bool, allow_choice: bool) -> str:
        pieces: List[str] = []
        if self.rng.random() < 0.3:
            pieces.append(self.sign())
            pieces.append(self.maybe_ws())

        pieces.append(self.gen_term(depth, allow_func, allow_choice))
        count = self.rng.randint(1, 4)
        for _ in range(1, count):
            pieces.append(self.maybe_ws())
            pieces.append(self.sign())
            pieces.append(self.maybe_ws())
            pieces.append(self.gen_term(depth, allow_func, allow_choice))
        return "".join(pieces)

    def effective_len(self, text: str) -> int:
        return len(text.replace(" ", "").replace("\t", ""))

    def _is_case_text_legal(self, input_text: str) -> bool:
        try:
            parsed = parse_case_input(input_text)
        except Exception:
            return False

        lines = input_text.splitlines()
        if not lines:
            return False
        n = int(lines[0].strip())
        if n == 0:
            if len(lines) < 2:
                return False
            return self.effective_len(lines[1]) <= 100
        if n == 1:
            if len(lines) < 3:
                return False
            if self.effective_len(lines[1].split("=", 1)[1] if "=" in lines[1] else "") > 50:
                return False
            if self.effective_len(lines[2]) > 100:
                return False

            # sanity: f-call should be legal in expression with this function body
            _ = parsed.expression
            return True
        return False

    def fixed_cases(self) -> List[Case]:
        return [
            Case("F001", "0\n1"),
            Case("F002", "0\nexp(((x+1)^2))"),
            Case("F003", "0\nexp(x)*exp((2*x))"),
            Case("F004", "0\n[( ((x-1)^2) == (x^2-2*x+1) ) ? exp(x) : x]"),
            Case("F005", "0\n[(x == (x+1)) ? 1 : exp(0)]"),
            Case("F006", "1\nf(x)=x^2+exp(0)\nf((x+1))"),
            Case("F007", "1\nf(x)=((x+1)^2)+x\n[(f((x-1)) == (x^2+x)) ? exp((x)) : x]"),
            Case("F008", "0\n[((( [(x==x)?1:0] ))==1)?exp(x):0]"),
            Case("F009", "0\n(exp((x+1))^2)*(exp((x+1))^2)"),
            Case("F010", "0\nexp((0))*x^0"),
            Case("F011", "0\n(x+1)^8-(x-1)^8"),
            Case("F012", "0\n[(x^8==x^8)?(x+1)^8:(x-1)^8]"),
            Case("F013", "0\n[(x^8==(x^8+1))?exp((x)):exp((0))]"),
            Case("F014", "0\nexp(exp(exp(exp((x)))))"),
            Case("F015", "0\nexp(exp(exp(exp(0013)^3)^5))"),
            Case("F016", "0\n[(exp((x))==exp((x)))?exp((x^8)):x^8]"),
            Case("F017", "0\n[(x==x)?[(x==x)?1:0]:[(x==x)?0:1]]"),
            Case("F018", "0\n[(x==x)?(x+1)^2:(x-1)^2]"),
            Case("F019", "0\n\t[\t(\tx\t==\t x\t)\t?\texp\t(\t(x)\t)\t:\t0\t]\t"),
            Case("F020", "0\n+00012*x^08-00012*x^8+exp((0))"),
            Case("F021", "1\nf(x)=x^8+exp((x))\nf((x+1))"),
            Case("F022", "1\nf(x)=(x+1)^2+(x-1)^2\nf((x^2))"),
            Case("F023", "1\nf(x)=exp((x))+x^2\n[(f((x))==f((x)))?f((x+1)):f((x-1))]"),
            Case("F024", "1\nf(x)=x^2+2*x+1\n[(f((x-1))==x^2)?exp((x)):0]"),
            Case("F025", "1\nf(x)=x^8\nexp((f((x))))"),
            Case("F026", "1\nf(x)=exp((x))^8\nexp((f((x^2))))"),
            Case("F027", "1\nf(x)=x^2+exp((0))\n[(f((x))==(x^2+1))?1:0]"),
            Case("F028", "1\nf(x)=((x+1)^2)\nf((x-1)^2)"),
            Case("F029", "1\nf(x)=x+1\n[(f((x))==(x+1))?(f((x+1))):(f((x-1)))]"),
            Case("F030", "0\n[(exp((0))==1)?(x^8+x^7+x^6+x^5):(x^4+x^3+x^2+x)]"),
        ]

    def structured_cases(self) -> List[str]:
        # High-strength templates: boundary exponents, deep exp nesting,
        # true/false choices, and function substitution stress.
        pool: List[str] = []

        e1 = self.rng.randint(6, 8)
        e2 = self.rng.randint(6, 8)
        pool.append(f"0\n[(x^{e1}==x^{e1})?exp((x^{e2})):(x+1)^{e2}]")
        pool.append(f"0\n[(x^{e1}==(x^{e1}+1))?exp((x^{e2})):(x-1)^{e2}]")

        c = self.digits(30)
        pool.append(f"0\nexp(exp(exp(exp({c})^{self.rng.randint(2,8)})^{self.rng.randint(2,8)}))")
        pool.append(
            "0\n[(x==x)?[(exp((x))==exp((x)))?exp((x^8)):x^8]:[(x==x)?0:1]]"
        )

        f_body1 = f"x^{self.rng.randint(6,8)}+exp((x))"
        pool.append(f"1\nf(x)={f_body1}\nf((x+1))")
        pool.append(f"1\nf(x)={f_body1}\n[(f((x))==f((x)))?f((x^2)):f((x))]")

        f_body2 = "(x+1)^2+(x-1)^2"
        pool.append(f"1\nf(x)={f_body2}\nf((x^{self.rng.randint(2,8)}))")
        pool.append(f"1\nf(x)={f_body2}\nexp((f((x))))")

        pool.append(
            "0\n\t[(\t(x\t==\t x)\t?\t(exp\t(\t(x)\t)^8)\t:\t((x-1)^8)\t]\t"
        )
        pool.append(
            "0\n[(x==x)?((x+1)^2*(x-1)^2):((x+1)^8-(x-1)^8)]"
        )

        valid_pool = [s for s in pool if self._is_case_text_legal(s)]
        self.rng.shuffle(valid_pool)
        return valid_pool

    def random_cases(self, quiet: bool = False) -> List[Case]:
        out: List[Case] = []
        case_index = 1
        attempts = 0
        max_attempts = self.random_count * 200

        structured = self.structured_cases()
        for text in structured:
            if len(out) >= self.random_count:
                break
            out.append(Case(f"R{case_index:03d}", text))
            case_index += 1
        if not quiet and out:
            progress_line("[Build] Structured", len(out), self.random_count, quiet)

        while len(out) < self.random_count and attempts < max_attempts:
            attempts += 1
            # Bias toward harder cases for robustness (not pure random).
            with_func = self.rng.random() < 0.6

            if with_func:
                func_body = self.gen_expr(depth=0, allow_func=False, allow_choice=False)
                expr = self.gen_expr(depth=0, allow_func=True, allow_choice=True)
                if self.effective_len(func_body) > 50:
                    continue
                if self.effective_len(expr) > 100:
                    continue
                input_text = f"1\nf(x)={func_body}\n{expr}"
            else:
                expr = self.gen_expr(depth=0, allow_func=False, allow_choice=True)
                if self.effective_len(expr) > 100:
                    continue
                input_text = f"0\n{expr}"

            if not self._is_case_text_legal(input_text):
                continue

            out.append(Case(f"R{case_index:03d}", input_text))
            case_index += 1

            if not quiet and (len(out) == self.random_count or len(out) % 10 == 0):
                progress_line("[Build] Random", len(out), self.random_count, quiet)

            if not quiet and attempts % 500 == 0:
                print(
                    f"\n[Build] tried={attempts}/{max_attempts}, accepted={len(out)}/{self.random_count}",
                    flush=True,
                )

        return out


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
        f.write(case.input_text + "\n")
    return path


def write_bug_report(
    bug_dir: str,
    case: Case,
    reason: str,
    stdout_text: str,
    stderr_text: str,
    shorter_candidate: str = "",
) -> None:
    path = os.path.join(bug_dir, f"{case.case_id}.txt")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"[Reason]\n{reason}\n\n")
        f.write(f"[Input]\n{case.input_text}\n\n")
        f.write(f"[Stdout]\n{stdout_text}\n\n")
        if shorter_candidate:
            f.write(f"[ShorterCandidate]\n{shorter_candidate}\n\n")
        f.write(f"[Stderr]\n{stderr_text}\n")


def run_target(cmd: List[str], input_text: str, timeout_sec: float) -> Tuple[bool, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            input=input_text + "\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
        )
        return True, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "TIMEOUT"
    except Exception as exc:
        return False, "", f"RUN_ERROR: {exc}"


def auto_target_cmd(args: argparse.Namespace, base: str, quiet: bool) -> List[str]:
    if args.jar:
        log(f"[Stage] Using jar target: {args.jar}", quiet)
        return ["java", "-jar", args.jar]

    src_dir = os.path.abspath(os.path.join(base, "..", "src"))
    java_files = [f for f in os.listdir(src_dir) if f.endswith(".java")]
    if not java_files:
        raise RuntimeError(f"no java files found in {src_dir}")

    log(f"[Stage] Compiling {len(java_files)} java files in {src_dir}", quiet)

    cp = subprocess.run(
        ["javac", "-encoding", "UTF-8"] + java_files,
        cwd=src_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if cp.returncode != 0:
        raise RuntimeError("javac failed:\n" + cp.stdout + "\n" + cp.stderr)

    log("[Stage] Compile success, target=MainClass", quiet)

    return ["java", "-cp", src_dir, "MainClass"]


def normalize_output_text(text: str) -> str:
    return text.strip()


def is_complex_for_symbolic(a: sp.Expr, b: sp.Expr) -> bool:
    sa = str(a)
    sb = str(b)
    total_len = len(sa) + len(sb)
    exp_cnt = sa.count("exp(") + sb.count("exp(")
    return total_len > 900 or exp_cnt > 10


def are_equivalent(expected_expr: sp.Expr, output_expr: sp.Expr) -> bool:
    # Normalize exp(a)^k -> exp(k*a) for non-negative integer k so equivalent
    # forms across algebraic rewrites are easier for SymPy to compare.
    def normalize_exp_power(expr: sp.Expr) -> sp.Expr:
        cur = expr
        for _ in range(4):
            nxt = cur.replace(
                lambda e: (
                    isinstance(e, sp.Pow)
                    and getattr(e.base, "func", None) == sp.exp
                    and getattr(e.exp, "is_Integer", False)
                    and int(e.exp) >= 0
                ),
                lambda e: (
                    sp.Integer(1)
                    if int(e.exp) == 0
                    else sp.exp(e.exp * e.base.args[0], evaluate=False)
                ),
            )
            if nxt == cur:
                break
            cur = nxt
        return cur

    expected_expr = normalize_exp_power(expected_expr)
    output_expr = normalize_exp_power(output_expr)

    if expected_expr == output_expr:
        return True

    if is_complex_for_symbolic(expected_expr, output_expr):
        # Lightweight path for very complex expressions to avoid simplify blow-up.
        try:
            eq = expected_expr.equals(output_expr)
            return eq is True
        except Exception:
            return False

    try:
        diff = expected_expr - output_expr
        if diff != 0:
            diff = sp.expand(diff)
        if diff != 0:
            diff = sp.simplify(diff)
        if diff == 0:
            return True
        eq2 = diff.equals(0)
        if eq2 is True:
            return True
        eq3 = expected_expr.equals(output_expr)
        return eq3 is True
    except MemoryError:
        # Do not attempt another heavy symbolic call after memory blow-up.
        return False
    except Exception:
        return False


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
        nxt_round: List[str] = []
        for cur in queue:
            local = []
            local.append(cur.replace("exp((0))", "1").replace("exp(0)", "1"))
            local.append(re.sub(r"(?<![0-9a-zA-Z_])1\*", "", cur))
            local.append(re.sub(r"\*1(?=([+\-]|$))", "", cur))
            local.append(re.sub(r"(?<![0-9a-zA-Z_])0\+", "", cur))
            local.append(re.sub(r"\+0(?=([+\-]|$))", "", cur))
            local.append(re.sub(r"-0(?=([+\-]|$))", "+0", cur))
            local.append(re.sub(r"x\^1(?!\d)", "x", cur))

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


def should_run_shortest_audit(out: str) -> bool:
    # Heuristic guard: avoid pathological symbolic checks on very complex outputs.
    exp_count = out.count("exp(")
    mul_count = out.count("*")
    if len(out) > 120:
        return False
    if exp_count > 4:
        return False
    if mul_count > 18:
        return False
    return True


def find_shorter_equivalent_output(out: str, time_budget_sec: float = 0.6) -> str:
    start = time.perf_counter()
    base_len = len(out)
    try:
        out_ast = ExprParser(
            out,
            allow_func_call=False,
            allow_choice=False,
            enforce_exp_upper_bound=False,
        ).parse_all()
        out_expr = out_ast.to_sympy(EvalContext(None))
    except Exception:
        return ""

    candidates = generate_shorter_candidates(out)
    checked = 0
    for cand in candidates:
        if time.perf_counter() - start > time_budget_sec:
            break
        if checked >= 18:
            break
        if len(cand) >= base_len:
            continue
        if re.search(r"\\s", cand):
            continue
        if any(tok in cand for tok in ("[", "]", "?", ":")):
            continue
        try:
            cand_ast = ExprParser(
                cand,
                allow_func_call=False,
                allow_choice=False,
                enforce_exp_upper_bound=False,
            ).parse_all()
        except Exception:
            continue

        if not is_output_structure_valid(cand_ast, False):
            continue

        try:
            cand_expr = cand_ast.to_sympy(EvalContext(None))
        except Exception:
            continue

        checked += 1
        if are_equivalent(out_expr, cand_expr):
            return cand

    return ""


def evaluate_case(case: Case, output_text: str, shortest_audit: bool) -> EvalResult:
    out = normalize_output_text(output_text)
    if not out:
        return EvalResult(False, "EMPTY_OUTPUT")

    if re.search(r"\s", out):
        return EvalResult(False, "FORMAT_VIOLATION: output contains whitespace")

    if any(tok in out for tok in ("[", "]", "?", ":")):
        return EvalResult(False, "FORMAT_VIOLATION: output still contains choice syntax")

    try:
        parsed = parse_case_input(case.input_text)
        expected_ctx = EvalContext(parsed.function_body)
        expected_expr = parsed.expression.to_sympy(expected_ctx)
    except Exception as exc:
        return EvalResult(False, f"INTERNAL_CASE_PARSE_ERROR: {type(exc).__name__}: {exc}")

    try:
        output_ast = ExprParser(
            out,
            allow_func_call=False,
            allow_choice=False,
            enforce_exp_upper_bound=False,
        ).parse_all()
    except Exception as exc:
        return EvalResult(False, f"OUTPUT_PARSE_ERROR: {exc}")

    if not is_output_structure_valid(output_ast, False):
        return EvalResult(False, "FORMAT_VIOLATION: output contains non-necessary parentheses or forbidden factors")

    try:
        output_expr = output_ast.to_sympy(EvalContext(None))
    except Exception as exc:
        return EvalResult(False, f"OUTPUT_EVAL_ERROR: {type(exc).__name__}: {exc}")

    if not are_equivalent(expected_expr, output_expr):
        return EvalResult(False, "NOT_EQUIVALENT")

    if shortest_audit:
        if should_run_shortest_audit(out):
            shorter = find_shorter_equivalent_output(out)
            if shorter:
                return EvalResult(
                    False,
                    f"NOT_SHORTEST: found shorter equivalent output (len {len(out)} -> {len(shorter)})",
                    shorter_candidate=shorter,
                )

    return EvalResult(True, "PASS")


def build_cases(seed: int, random_count: int, quiet: bool) -> List[Case]:
    gen = CaseGenerator(seed=seed, random_count=random_count)
    fixed = gen.fixed_cases()
    log(f"[Stage] Fixed cases prepared: {len(fixed)}", quiet)
    log(f"[Stage] Generating random cases: target={random_count}", quiet)
    random_cases = gen.random_cases(quiet=quiet)
    log(f"[Stage] Random cases generated: {len(random_cases)}", quiet)
    if len(random_cases) < random_count:
        log(
            f"[Warn] Requested random-count={random_count}, but only generated {len(random_cases)} legal cases in attempt limit.",
            quiet,
        )
    cases = fixed + random_cases

    valid: List[Case] = []
    total = len(cases)
    log(f"[Stage] Validating generated cases with parser/sympy: total={total}", quiet)
    for idx, case in enumerate(cases, start=1):
        _ = parse_case_input(case.input_text)
        valid.append(case)
        if idx == 1 or idx == total or idx % 10 == 0:
            progress_line("[Build] Validate", idx, total, quiet)
    return valid


def main() -> None:
    parser = argparse.ArgumentParser(description="HW2 guidebook-compliant auto judge")
    parser.add_argument("--jar", default="", help="path to target jar; if empty, compile/run ../src/MainClass")
    parser.add_argument("--seed", type=int, default=20260314, help="random seed")
    parser.add_argument("--random-count", type=int, default=200, help="number of random legal cases")
    parser.add_argument("--timeout", type=float, default=5.0, help="timeout (seconds) for each case")
    parser.add_argument("--no-shortest-audit", action="store_true", help="disable shortest-length disprover")
    parser.add_argument("--quiet", action="store_true", help="disable progress logs")
    args = parser.parse_args()

    start_time = time.time()
    log("[1/4] Preparing workspace directories", args.quiet)
    base = os.path.dirname(os.path.abspath(__file__))
    data_dir, out_dir, bug_dir = ensure_dirs(base)

    log("[2/4] Building test cases", args.quiet)
    cases = build_cases(args.seed, args.random_count, args.quiet)
    log(f"[Stage] Total cases ready: {len(cases)}", args.quiet)

    log("[3/4] Preparing target command", args.quiet)
    target_cmd = auto_target_cmd(args, base, args.quiet)

    total = len(cases)
    passed = 0
    failed = 0
    rows: List[str] = []
    shortest_audit_enabled = not args.no_shortest_audit
    log(f"[Stage] shortest_audit={'ON' if shortest_audit_enabled else 'OFF'}", args.quiet)

    log("[4/4] Running judge", args.quiet)
    for idx, case in enumerate(cases, start=1):
        progress_line("[Judge] Running", idx, total, args.quiet)
        write_case_file(data_dir, case)
        ok_run, stdout_text, stderr_text = run_target(target_cmd, case.input_text, args.timeout)

        out_path = os.path.join(out_dir, f"{case.case_id}.out")
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(stdout_text)

        if not ok_run:
            failed += 1
            reason = stderr_text
            write_bug_report(bug_dir, case, reason, stdout_text, stderr_text)
            rows.append(f"{case.case_id}|FAIL|{reason}")
            if not args.quiet:
                print(f"\n[FAIL] {case.case_id}: {reason}", flush=True)
            continue

        result = evaluate_case(case, stdout_text, shortest_audit_enabled)
        if result.ok:
            passed += 1
            rows.append(f"{case.case_id}|PASS|PASS")
        else:
            failed += 1
            write_bug_report(
                bug_dir,
                case,
                result.reason,
                stdout_text,
                stderr_text,
                shorter_candidate=result.shorter_candidate,
            )
            rows.append(f"{case.case_id}|FAIL|{result.reason}")
            if not args.quiet:
                print(f"\n[FAIL] {case.case_id}: {result.reason}", flush=True)

    summary_path = os.path.join(base, "summary.md")
    with open(summary_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("# HW2 Auto Judge Summary\n\n")
        f.write(f"- Total: {total}\n")
        f.write(f"- Passed: {passed}\n")
        f.write(f"- Failed: {failed}\n\n")
        f.write("## Detail\n\n")
        f.write("| Case | Result | Reason |\n")
        f.write("|---|---|---|\n")
        for row in rows:
            case_id, res, reason = row.split("|", 2)
            f.write(f"| {case_id} | {res} | {reason} |\n")

    elapsed = time.time() - start_time
    log(f"DONE: pass={passed}, fail={failed}, total={total}", args.quiet)
    log(f"summary: {summary_path}", args.quiet)
    log(f"elapsed: {elapsed:.2f}s", args.quiet)

    final_status = "ALL_PASS" if failed == 0 else "HAS_FAIL"
    # Always print final status so users can see the result at a glance.
    print(f"FINAL_STATUS: {final_status} (pass={passed}, fail={failed}, total={total})", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FATAL: {exc}")
        sys.exit(1)
