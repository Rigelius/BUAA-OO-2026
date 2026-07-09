#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HW15 flexible legality judge for the OO U4 library task."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from judge.core.target_matching import direct_target_entry, matching_target_entries

from .generator import generate_all


RE_MAIN_METHOD = re.compile(r"\bpublic\s+static\s+void\s+main\s*\(")
ROOT = Path(__file__).resolve().parents[1]
JUDGE_DIR = Path(__file__).resolve().parent
DEFAULT_OFFICIAL = JUDGE_DIR / "lib" / "library3.jar"
LOCS = {"bs", "tbs", "bro", "ao", "rr", "user"}
MOVABLE = {"bs", "tbs", "bro", "ao", "rr"}


def _fallback_search_roots() -> List[Path]:
    roots: List[Path] = [ROOT]
    cur = ROOT
    for _ in range(4):
        parent = cur.parent
        if parent == cur:
            break
        roots.append(parent)
        u4 = parent / "U4"
        if u4.is_dir():
            roots.append(u4)
        cur = parent
    seen: List[Path] = []
    for r in roots:
        try:
            resolved = r.resolve()
        except OSError:
            continue
        if resolved.is_dir() and resolved not in seen:
            seen.append(resolved)
    return seen


@dataclass
class TargetProject:
    key: str
    display_name: str
    source_dir: Path
    build_dir: Path
    command: List[str]


@dataclass
class RunResult:
    status: str
    stdout: str
    stderr: str
    elapsed: float
    errors: List[str]
    raw_output_path: str


@dataclass
class Order:
    isbn: str
    copy_id: Optional[str] = None
    start: Optional[date] = None
    expire_close: Optional[date] = None


def clear_directory(path: Path) -> None:
    if not path.exists():
        return
    for item in path.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def sanitize_key(name: str, idx: int) -> str:
    key = re.sub(r"[^0-9A-Za-z_.-]+", "_", name).strip("._")
    return key or f"target_{idx}"


def find_official_src(path_text: str = "") -> Path:
    if path_text:
        path = Path(path_text)
        if path.is_file() and path.suffix.lower() == ".jar":
            return path.resolve()
        jars = sorted(path.rglob("library3.jar")) if path.is_dir() else []
        if jars:
            return jars[0].resolve()
    if DEFAULT_OFFICIAL.is_file():
        return DEFAULT_OFFICIAL.resolve()
    for base in _fallback_search_roots():
        jars = sorted(base.rglob("library3.jar"))
        if jars:
            return jars[0].resolve()
    raise RuntimeError("cannot locate library3.jar")


def contains_main(java_file: Path) -> bool:
    try:
        return RE_MAIN_METHOD.search(
            java_file.read_text(encoding="utf-8", errors="replace")
        ) is not None
    except OSError:
        return False


def parse_main_class(java_file: Path) -> str:
    text = java_file.read_text(encoding="utf-8", errors="replace")
    cls = java_file.stem
    pkg = ""
    m = re.search(r"^\s*package\s+([A-Za-z_][\w.]*)\s*;", text, re.MULTILINE)
    if m:
        pkg = m.group(1)
    m = re.search(r"\bpublic\s+class\s+([A-Za-z_]\w*)", text)
    if m:
        cls = m.group(1)
    return f"{pkg}.{cls}" if pkg else cls


def choose_source_dir(project_dir: Path) -> Tuple[Path, Path]:
    candidates = sorted(project_dir.rglob("MainClass.java"))
    if not candidates:
        candidates = sorted(project_dir.rglob("Main.java"))
    if not candidates:
        candidates = sorted(p for p in project_dir.rglob("*.java") if contains_main(p))
    if not candidates:
        raise RuntimeError(f"no Java main class under {project_dir}")
    main_file = candidates[0]
    source_dir = main_file.parent
    rel = main_file.relative_to(project_dir).parts
    for idx, part in enumerate(rel):
        if part.lower() == "src":
            source_dir = project_dir.joinpath(*rel[:idx + 1])
            break
    return source_dir, main_file


def compile_project(source_dir: Path, official_src: Path, build_dir: Path,
                    timeout: float) -> Tuple[bool, str]:
    jar = find_official_src(str(official_src))
    java_files = [str(p) for p in source_dir.rglob("*.java")]
    if not java_files:
        return False, "no java files"
    build_dir.mkdir(parents=True, exist_ok=True)
    clear_directory(build_dir)
    cmd = ["javac", "-encoding", "UTF-8", "-cp", str(jar),
           "-d", str(build_dir)] + java_files
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
    except FileNotFoundError:
        return False, "javac not found"
    except subprocess.TimeoutExpired:
        return False, f"javac timeout after {timeout}s"
    if proc.returncode != 0:
        return False, ((proc.stdout or "") + (proc.stderr or "")).strip()
    return True, "ok"


def _isbn_of(book_id: str) -> str:
    return book_id[:6]


def _copy_no(book_id: str) -> int:
    return int(book_id[-2:])


def _typ(isbn: str) -> str:
    return isbn[0]


def _parse_date(text: str) -> date:
    return date.fromisoformat(text)


class FlexibleValidator:
    def __init__(self, input_text: str, output_text: str) -> None:
        self.input_lines = [x.strip() for x in input_text.splitlines() if x.strip()]
        self.out_lines = [x.strip() for x in output_text.splitlines() if x.strip()]
        self.pos = 0
        self.errors: List[str] = []
        self.counts: Dict[str, int] = {}
        self.loc: Dict[str, str] = {}
        self.owner: Dict[str, str] = {}
        self.reader: Dict[str, str] = {}
        self.holdings: Dict[str, Set[str]] = {}
        self.reading: Dict[str, str] = {}
        self.orders: Dict[str, Order] = {}
        self.reserved_for: Dict[str, str] = {}
        self.history: Dict[str, List[Tuple[str, str, str]]] = {}
        self.ratings: Dict[str, List[int]] = {}
        # hw15: credit-score system
        # 初始 100, 范围 [0, 180]. gate: 借 B/C > 80, 读 A > 40, 读 B/C > 0.
        # 增减: 按时归还 +10, 逾期归还 -15 (在到期当日 close 触发一次),
        # 阅读未同日归还 -10 (在 close 触发), 预约到期未取 -15 (在 close 触发),
        # 同日主动 restore +10.
        self.credit: Dict[str, int] = {}
        # copy_id -> deadline (last legal return day, close of this day counts as overdue)
        self.borrow_deadline: Dict[str, date] = {}
        # copy_id -> borrower (mirrors self.owner but survives after return for scoring)
        self.borrow_user: Dict[str, str] = {}
        # (day_s, user) 表示当天该用户执行过 read
        self.read_today: Set[Tuple[str, str]] = set()
        # 当天已 restore 的用户 (day_s, user) 用于 restore 同日奖励防重复
        self.restored_today: Set[Tuple[str, str]] = set()
        # 已扣过逾期分的 copy_id (避免同一册再触发)
        self.overdue_scored: Set[str] = set()
        # 已扣过预约过期分的具体预约记录
        self.order_expire_scored: Set[Tuple[str, str, str, str]] = set()

    def credit_of(self, user: str) -> int:
        return self.credit.get(user, 100)

    def credit_delta(self, user: str, delta: int) -> None:
        new_val = self.credit_of(user) + delta
        self.credit[user] = max(0, min(180, new_val))

    def error(self, msg: str) -> None:
        if len(self.errors) < 80:
            self.errors.append(msg)

    def next_out(self, context: str) -> Optional[str]:
        if self.pos >= len(self.out_lines):
            self.error(f"{context}: missing output")
            return None
        line = self.out_lines[self.pos]
        self.pos += 1
        return line

    def add_move(self, day: str, copy_id: str, to: str) -> None:
        frm = self.loc[copy_id]
        self.history[copy_id].append((day, frm, to))
        self.loc[copy_id] = to

    def score(self, isbn: str) -> int:
        values = self.ratings.get(isbn, [])
        return sum(values) // len(values) if values else 0

    def shelf_for(self, isbn: str) -> str:
        return "tbs" if self.score(isbn) >= 4 else "bs"

    def shelf_copies(self, isbn: str) -> List[str]:
        return [c for c, loc in self.loc.items()
                if _isbn_of(c) == isbn and loc in {"bs", "tbs"}]

    def can_hold(self, user: str, isbn: str) -> bool:
        held = self.holdings.setdefault(user, set())
        if _typ(isbn) == "A":
            return False
        if _typ(isbn) == "B":
            return all(_typ(_isbn_of(c)) != "B" for c in held)
        return all(_isbn_of(c) != isbn for c in held)

    def _order_expire_key(self, user: str, order: Order) -> Tuple[str, str, str, str]:
        copy_id = order.copy_id or ""
        expire_day = order.expire_close.isoformat() if order.expire_close else ""
        return user, order.isbn, copy_id, expire_day

    def _penalize_expired_order(self, user: str, order: Order) -> None:
        key = self._order_expire_key(user, order)
        if key not in self.order_expire_scored:
            self.credit_delta(user, -15)
            self.order_expire_scored.add(key)

    def _apply_overdue_penalties(self, day: date, phase: str) -> None:
        for cid, dl in list(self.borrow_deadline.items()):
            if cid not in self.owner or cid in self.overdue_scored:
                continue
            expired = day >= dl if phase == "close" else day > dl
            if expired:
                self.credit_delta(self.borrow_user.get(cid, self.owner[cid]), -15)
                self.overdue_scored.add(cid)

    def expire_orders(self, current: date, phase: str) -> None:
        expired: List[str] = []
        for user, order in self.orders.items():
            if order.expire_close is None:
                continue
            if (phase == "close" and current >= order.expire_close) or (
                    phase != "close" and current > order.expire_close):
                expired.append(user)
        for user in expired:
            order = self.orders.pop(user)
            self._penalize_expired_order(user, order)
            if order.copy_id:
                self.reserved_for.pop(order.copy_id, None)

    def parse_input(self) -> bool:
        if not self.input_lines:
            self.error("empty input")
            return False
        try:
            n = int(self.input_lines[0])
        except ValueError:
            self.error("first input line is not inventory count")
            return False
        if len(self.input_lines) < n + 1:
            self.error("inventory is truncated")
            return False
        for line in self.input_lines[1:n + 1]:
            try:
                isbn, count_text = line.split()
                count = int(count_text)
            except ValueError:
                self.error(f"bad inventory line: {line}")
                continue
            self.counts[isbn] = count
            self.ratings[isbn] = []
            for idx in range(1, count + 1):
                copy_id = f"{isbn}-{idx:02d}"
                self.loc[copy_id] = "bs"
                self.history[copy_id] = []
        self.commands = self.input_lines[n + 1:]
        return not self.errors

    def validate(self) -> List[str]:
        if not self.parse_input():
            return self.errors
        for idx, raw in enumerate(self.commands, start=1):
            self.handle_command(idx, raw)
            if len(self.errors) >= 80:
                break
        if self.pos != len(self.out_lines):
            self.error(f"extra output at line {self.pos + 1}: {self.out_lines[self.pos]}")
        return self.errors

    def handle_command(self, idx: int, raw: str) -> None:
        m = re.match(r"^\[(\d{4}-\d{2}-\d{2})\]\s+(.+)$", raw)
        if not m:
            self.error(f"input command {idx}: bad date format: {raw}")
            return
        day_s, body = m.group(1), m.group(2)
        day = _parse_date(day_s)
        if body == "OPEN":
            self._apply_overdue_penalties(day, "open")
            self.expire_orders(day, "open")
            self.handle_arrange(day_s, before_open=True)
            self.check_after_open(day_s)
            return
        if body == "CLOSE":
            self._close_of_day_credit(day, day_s)
            self.expire_orders(day, "close")
            self.handle_arrange(day_s, before_open=False)
            return
        p = body.split()
        if len(p) < 3:
            self.error(f"input command {idx}: bad request: {raw}")
            return
        user, op, book = p[0], p[1], p[2]
        if op == "queried":
            if book == "credit" and len(p) >= 4 and p[3] == "score":
                self.handle_credit_query(day_s, user)
            else:
                self.handle_query(day_s, book)
        elif op == "borrowed":
            self.handle_borrow(day_s, user, book)
        elif op == "ordered":
            self.handle_order(day_s, user, book)
        elif op == "picked":
            self.handle_pick(day_s, user, book)
        elif op == "returned":
            self.handle_return(day_s, user, book)
        elif op == "read":
            self.handle_read(day_s, user, book)
        elif op == "restored":
            self.handle_restore(day_s, user, book)
        elif op == "renewed":
            self.handle_renew(day_s, user, book)
        elif op == "graded" and len(p) == 4:
            self.handle_grade(day_s, user, book, p[3])
        else:
            self.error(f"input command {idx}: unknown request: {raw}")

    def _close_of_day_credit(self, day: date, day_s: str) -> None:
        # 预约到期未取 -15 (针对本 close 触发过期的订单)
        for u, order in list(self.orders.items()):
            if order.expire_close is not None and day >= order.expire_close:
                self._penalize_expired_order(u, order)
        # 借书逾期未还 -15 (今天恰为归还截止, 且尚未归还)
        self._apply_overdue_penalties(day, "close")
        # 阅读未同日归还 -10
        for (d, u) in list(self.read_today):
            if d == day_s:
                self.credit_delta(u, -10)
                self.read_today.discard((d, u))

    def handle_arrange(self, day_s: str, before_open: bool) -> None:
        first = self.next_out(f"{day_s} arrange")
        if first is None:
            return
        if not re.fullmatch(r"\d+", first):
            self.error(f"{day_s} arrange: first line should be move count, got '{first}'")
            return
        moved_counted: Set[str] = set()
        for i in range(int(first)):
            line = self.next_out(f"{day_s} arrange move {i + 1}")
            if line is None:
                return
            m = re.match(
                r"^\[(\d{4}-\d{2}-\d{2})\] move ([ABC]-\d{4}-\d{2}) "
                r"from (bs|tbs|bro|ao|rr) to (bs|tbs|bro|ao|rr)"
                r"(?: for ([0-9A-Za-z_]+))?$", line)
            if not m:
                self.error(f"{day_s} arrange: bad move line: {line}")
                continue
            out_day, copy_id, frm, to, reserve_user = m.groups()
            if out_day != day_s:
                self.error(f"{day_s} arrange: move date mismatch: {line}")
            if copy_id not in self.loc:
                self.error(f"{day_s} arrange: unknown book copy {copy_id}")
                continue
            if frm == to:
                self.error(f"{day_s} arrange: from and to are same for {copy_id}")
            if self.loc[copy_id] != frm:
                self.error(f"{day_s} arrange: {copy_id} is at {self.loc[copy_id]}, not {frm}")
            if to != "ao" and reserve_user:
                self.error(f"{day_s} arrange: 'for user' only allowed when moving to ao")
            if to == "ao" and not reserve_user:
                self.error(f"{day_s} arrange: moving to ao must specify reserved user")
            if copy_id in self.reserved_for and to != "user":
                self.error(f"{day_s} arrange: active reserved copy {copy_id} was moved")
            if frm == "rr":
                reading_user = self.reader.pop(copy_id, None)
                if reading_user is not None and self.reading.get(reading_user) == copy_id:
                    self.reading.pop(reading_user, None)
            if to != "ao":
                if copy_id in moved_counted:
                    self.error(f"{day_s} arrange: {copy_id} moved more than once")
                moved_counted.add(copy_id)
                self.reserved_for.pop(copy_id, None)
            else:
                order = self.orders.get(reserve_user or "")
                if order is None or order.isbn != _isbn_of(copy_id) or order.copy_id is not None:
                    self.error(f"{day_s} arrange: no matching pending order for {reserve_user}")
                else:
                    order.copy_id = copy_id
                    start = _parse_date(day_s) if before_open else _parse_date(day_s) + timedelta(days=1)
                    order.start = start
                    order.expire_close = start + timedelta(days=4)
                    self.reserved_for[copy_id] = reserve_user or ""
            self.add_move(day_s, copy_id, to)

    def check_after_open(self, day_s: str) -> None:
        for copy_id, loc in self.loc.items():
            if loc in {"bro", "rr"}:
                self.error(f"{day_s} open: {copy_id} remains at {loc} after opening arrange")
            if loc in {"bs", "tbs"}:
                expected = self.shelf_for(_isbn_of(copy_id))
                if loc != expected:
                    self.error(f"{day_s} open: {copy_id} should be on {expected}, got {loc}")

    def consume_accept_reject(self, day_s: str, user: str, op: str) -> Optional[Tuple[str, str]]:
        line = self.next_out(f"{day_s} {user} {op}")
        if line is None:
            return None
        m = re.match(
            r"^\[(\d{4}-\d{2}-\d{2})\] \[(accept|reject)\] "
            r"([0-9A-Za-z_]+) ([a-z]+) (.+)$", line)
        if not m:
            self.error(f"{day_s} {op}: bad response line: {line}")
            return None
        out_day, verdict, out_user, out_op, rest = m.groups()
        if out_day != day_s or out_user != user or out_op != op:
            self.error(f"{day_s} {op}: response does not match request: {line}")
        return verdict, rest

    def handle_borrow(self, day_s: str, user: str, isbn: str) -> None:
        # hw15: 借 B/C 类要求信用 > 80
        credit_ok = self.credit.get(user, 100) > 80
        can = (self.can_hold(user, isbn) and bool(self.shelf_copies(isbn))
               and credit_ok)
        resp = self.consume_accept_reject(day_s, user, "borrowed")
        if not resp:
            return
        verdict, rest = resp
        if verdict == "reject":
            if can:
                self.error(f"{day_s} borrowed: rejected although {isbn} can be borrowed")
            if rest != isbn:
                self.error(f"{day_s} borrowed: reject target mismatch: {rest}")
            return
        copy_id = rest
        if not can:
            self.error(f"{day_s} borrowed: accepted invalid borrow of {isbn}")
        if _isbn_of(copy_id) != isbn or self.loc.get(copy_id) not in {"bs", "tbs"}:
            self.error(f"{day_s} borrowed: invalid accepted copy {copy_id}")
            return
        self.add_move(day_s, copy_id, "user")
        self.owner[copy_id] = user
        self.holdings.setdefault(user, set()).add(copy_id)
        # hw15: 记录归还截止日 (B=15 天, C=30 天)
        days = 15 if _typ(isbn) == "B" else 30
        self.borrow_deadline[copy_id] = _parse_date(day_s) + timedelta(days=days)
        self.borrow_user[copy_id] = user

    def handle_read(self, day_s: str, user: str, isbn: str) -> None:
        # hw15: 读 A 类要求信用 > 40, 读 B/C 类要求信用 > 0
        credit = self.credit.get(user, 100)
        min_credit = 40 if _typ(isbn) == "A" else 0
        credit_ok = credit > min_credit
        can = (user not in self.reading and bool(self.shelf_copies(isbn))
               and credit_ok)
        resp = self.consume_accept_reject(day_s, user, "read")
        if not resp:
            return
        verdict, rest = resp
        if verdict == "reject":
            if can:
                self.error(f"{day_s} read: rejected although {isbn} is readable")
            if rest != isbn:
                self.error(f"{day_s} read: reject target mismatch: {rest}")
            return
        copy_id = rest
        if not can:
            self.error(f"{day_s} read: accepted invalid read of {isbn}")
        if _isbn_of(copy_id) != isbn or self.loc.get(copy_id) not in {"bs", "tbs"}:
            self.error(f"{day_s} read: invalid accepted copy {copy_id}")
            return
        self.add_move(day_s, copy_id, "rr")
        self.reader[copy_id] = user
        self.reading[user] = copy_id
        # hw15: 标记本日阅读者, 若不 restore 则 close 时扣 10
        self.read_today.add((day_s, user))

    def handle_order(self, day_s: str, user: str, isbn: str) -> None:
        # hw15: 预定 B/C 类同样要求信用 > 80
        credit_ok = self.credit.get(user, 100) > 80
        can = (self.can_hold(user, isbn) and user not in self.orders
               and credit_ok)
        resp = self.consume_accept_reject(day_s, user, "ordered")
        if not resp:
            return
        verdict, rest = resp
        if rest != isbn:
            self.error(f"{day_s} ordered: target mismatch: {rest}")
        if verdict == "accept":
            if not can:
                self.error(f"{day_s} ordered: accepted invalid order of {isbn}")
            self.orders[user] = Order(isbn)
        elif can:
            self.error(f"{day_s} ordered: rejected valid order of {isbn}")

    def handle_pick(self, day_s: str, user: str, isbn: str) -> None:
        order = self.orders.get(user)
        can = (order is not None and order.isbn == isbn and order.copy_id is not None
               and self.loc.get(order.copy_id) == "ao" and self.can_hold(user, isbn))
        resp = self.consume_accept_reject(day_s, user, "picked")
        if not resp:
            return
        verdict, rest = resp
        if verdict == "reject":
            if can:
                self.error(f"{day_s} picked: rejected although reserved copy is available")
            if rest != isbn:
                self.error(f"{day_s} picked: reject target mismatch: {rest}")
            return
        copy_id = rest
        if not can or order is None or order.copy_id != copy_id:
            self.error(f"{day_s} picked: accepted invalid picked copy {copy_id}")
            return
        self.add_move(day_s, copy_id, "user")
        self.owner[copy_id] = user
        self.holdings.setdefault(user, set()).add(copy_id)
        self.reserved_for.pop(copy_id, None)
        self.orders.pop(user, None)

    def handle_return(self, day_s: str, user: str, copy_id: str) -> None:
        can = self.owner.get(copy_id) == user
        resp = self.consume_accept_reject(day_s, user, "returned")
        if not resp:
            return
        verdict, rest = resp
        # hw15: return 行末带 " overdue" / " not overdue"
        m = re.match(r"^([ABC]-\d{4}-\d{2})(?:\s+(overdue|not overdue))?$", rest)
        if not m:
            self.error(f"{day_s} returned: bad tail: {rest}")
            return
        out_copy, overdue_tag = m.group(1), m.group(2)
        if out_copy != copy_id:
            self.error(f"{day_s} returned: target mismatch: {out_copy}")
        if verdict == "reject":
            if can:
                self.error(f"{day_s} returned: rejected valid return {copy_id}")
            return
        if not can:
            self.error(f"{day_s} returned: accepted invalid return {copy_id}")
            return
        # hw15: 校验 overdue 标记, 结算信用
        deadline = self.borrow_deadline.get(copy_id)
        return_day = _parse_date(day_s)
        actually_overdue = deadline is not None and return_day > deadline
        if overdue_tag is None:
            self.error(f"{day_s} returned: missing overdue/not-overdue tag")
        elif actually_overdue and overdue_tag != "overdue":
            self.error(f"{day_s} returned: {copy_id} should be overdue")
        elif not actually_overdue and overdue_tag == "overdue":
            self.error(f"{day_s} returned: {copy_id} should be not overdue")
        if not actually_overdue:
            self.credit_delta(user, 10)
        self.add_move(day_s, copy_id, "bro")
        self.owner.pop(copy_id, None)
        self.holdings.setdefault(user, set()).discard(copy_id)
        self.borrow_deadline.pop(copy_id, None)
        self.borrow_user.pop(copy_id, None)
        self.overdue_scored.discard(copy_id)

    def handle_restore(self, day_s: str, user: str, copy_id: str) -> None:
        can = self.reader.get(copy_id) == user and self.reading.get(user) == copy_id
        resp = self.consume_accept_reject(day_s, user, "restored")
        if not resp:
            return
        verdict, rest = resp
        if rest != copy_id:
            self.error(f"{day_s} restored: target mismatch: {rest}")
        if verdict == "reject":
            if can:
                self.error(f"{day_s} restored: rejected valid restore {copy_id}")
            return
        if not can:
            self.error(f"{day_s} restored: accepted invalid restore {copy_id}")
            return
        self.add_move(day_s, copy_id, "bro")
        self.reader.pop(copy_id, None)
        self.reading.pop(user, None)
        # hw15: 同日主动 restore +10 (每用户每天最多一次)
        key = (day_s, user)
        if key not in self.restored_today:
            self.restored_today.add(key)
            self.credit_delta(user, 10)
        # 该用户当天的 read 已经归还, 移除未归还标记
        self.read_today.discard((day_s, user))

    def handle_grade(self, day_s: str, user: str, isbn: str, score_text: str) -> None:
        resp = self.consume_accept_reject(day_s, user, "graded")
        if not resp:
            return
        verdict, rest = resp
        if verdict != "accept":
            self.error(f"{day_s} graded: grading should always be accepted")
            return
        if rest != f"{isbn} {score_text}":
            self.error(f"{day_s} graded: response mismatch: {rest}")
        try:
            value = int(score_text)
        except ValueError:
            self.error(f"{day_s} graded: bad score {score_text}")
            return
        if value < 0 or value > 5:
            self.error(f"{day_s} graded: score out of range {value}")
        self.ratings.setdefault(isbn, []).append(value)

    def handle_query(self, day_s: str, copy_id: str) -> None:
        header = self.next_out(f"{day_s} queried")
        if header is None:
            return
        m = re.match(
            r"^\[(\d{4}-\d{2}-\d{2})\]\s+([ABC]-\d{4}-\d{2})\s+moving trace: (\d+)$",
            header)
        if not m:
            self.error(f"{day_s} queried: bad query header: {header}")
            return
        out_day, out_copy, count_text = m.groups()
        if out_day != day_s or out_copy != copy_id:
            self.error(f"{day_s} queried: header mismatch: {header}")
        expected = self.history.get(copy_id, [])
        count = int(count_text)
        if count != len(expected):
            self.error(f"{day_s} queried: expected {len(expected)} traces, got {count}")
        for i in range(count):
            line = self.next_out(f"{day_s} queried trace {i + 1}")
            if line is None:
                return
            m2 = re.match(
                r"^(\d+) \[(\d{4}-\d{2}-\d{2})\] from "
                r"(bs|tbs|bro|ao|rr|user) to (bs|tbs|bro|ao|rr|user)$", line)
            if not m2:
                self.error(f"{day_s} queried: bad trace line: {line}")
                continue
            idx, t_day, frm, to = m2.groups()
            if int(idx) != i + 1:
                self.error(f"{day_s} queried: trace index mismatch in {line}")
            if i < len(expected) and (t_day, frm, to) != expected[i]:
                self.error(
                    f"{day_s} queried: trace {i + 1} expected {expected[i]}, "
                    f"got {(t_day, frm, to)}")

    def handle_renew(self, day_s: str, user: str, copy_id: str) -> None:
        # hw15: renewed <ISBN-copy> — 未逾期时 +7 天; 每册最多一次即可, 判官只校验 accept/reject
        deadline = self.borrow_deadline.get(copy_id)
        return_day = _parse_date(day_s)
        can = (self.owner.get(copy_id) == user and deadline is not None
               and return_day <= deadline)
        resp = self.consume_accept_reject(day_s, user, "renewed")
        if not resp:
            return
        verdict, rest = resp
        if rest != copy_id:
            self.error(f"{day_s} renewed: target mismatch: {rest}")
        if verdict == "reject":
            if can:
                self.error(f"{day_s} renewed: rejected valid renew {copy_id}")
            return
        if not can:
            self.error(f"{day_s} renewed: accepted invalid renew {copy_id}")
            return
        self.borrow_deadline[copy_id] = deadline + timedelta(days=7)

    def handle_credit_query(self, day_s: str, user: str) -> None:
        line = self.next_out(f"{day_s} credit query {user}")
        if line is None:
            return
        m = re.match(r"^\[(\d{4}-\d{2}-\d{2})\]\s+([0-9A-Za-z_]+)\s+(-?\d+)$", line)
        if not m:
            self.error(f"{day_s} credit: bad response line: {line}")
            return
        out_day, out_user, out_val = m.groups()
        if out_day != day_s or out_user != user:
            self.error(f"{day_s} credit: response header mismatch: {line}")
        try:
            got = int(out_val)
        except ValueError:
            self.error(f"{day_s} credit: bad score value: {out_val}")
            return
        if got != self.credit_of(user):
            self.error(
                f"{day_s} credit: {user} expected {self.credit_of(user)}, got {got}")


def expected_output(input_text: str) -> Tuple[List[str], List[str]]:
    validator = FlexibleValidator(input_text, "")
    validator.parse_input()
    return [], validator.errors


def validate_output(input_text: str, output_text: str) -> List[str]:
    return FlexibleValidator(input_text, output_text).validate()


def discover_targets(args: argparse.Namespace, official_src: Path) -> List[TargetProject]:
    build_root = (JUDGE_DIR / args.build_dir).resolve()
    targets: List[Tuple[str, Path]] = []
    if args.mode in {"self", "both"}:
        targets.append(("self", ROOT))
    if args.mode in {"mutual", "both"}:
        base = (JUDGE_DIR / args.co_judge_dir).resolve()
        direct = direct_target_entry(args.target_pattern)
        if direct:
            targets.append((direct.name, direct))
        else:
            for entry in matching_target_entries(sorted(base.iterdir(), key=lambda p: p.name.lower()), args.target_pattern):
                targets.append((entry.name, entry))
    projects: List[TargetProject] = []
    skipped: List[str] = []
    for idx, (name, project_dir) in enumerate(targets, start=1):
        try:
            if project_dir.is_file() and project_dir.suffix.lower() == ".jar":
                key = sanitize_key(f"{project_dir.stem}_jar", idx)
                projects.append(TargetProject(
                    key=key,
                    display_name=project_dir.name,
                    source_dir=project_dir.parent,
                    build_dir=build_root / key,
                    command=["java", "-jar", str(project_dir.resolve())],
                ))
                continue
            source_dir, main_file = choose_source_dir(project_dir)
            key = sanitize_key(name, idx)
            build_dir = build_root / key
            ok, msg = compile_project(source_dir, official_src, build_dir, args.compile_timeout)
            if not ok:
                raise RuntimeError(msg)
            jar = find_official_src(str(official_src))
            cp = f"{build_dir}{';' if sys.platform == 'win32' else ':'}{jar}"
            projects.append(TargetProject(
                key=key,
                display_name=name,
                source_dir=source_dir,
                build_dir=build_dir,
                command=["java", "-cp", cp, parse_main_class(main_file)],
            ))
        except Exception as exc:
            skipped.append(f"{name}: {exc}")
    if skipped:
        print("[WARN] skipped targets:", file=sys.stderr)
        for item in skipped:
            print("  - " + item, file=sys.stderr)
    if not projects:
        raise RuntimeError("no compilable target project found")
    return projects


def run_target(target: TargetProject, case_name: str, input_text: str,
               out_dir: Path, timeout: float) -> RunResult:
    start = time.monotonic()
    status = "PASSED"
    errors: List[str] = []
    stdout = ""
    stderr = ""
    try:
        proc = subprocess.run(target.command, input=input_text, capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=timeout)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        if proc.returncode != 0:
            status = "RUNTIME_ERROR"
            errors.append(f"exit code {proc.returncode}")
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        status = "TIMEOUT"
        errors.append(f"timeout after {timeout}s")
    except Exception as exc:
        status = "EXEC_ERROR"
        errors.append(str(exc))
    elapsed = time.monotonic() - start
    if status == "PASSED":
        errors.extend(validate_output(input_text, stdout))
        if errors:
            status = "WRONG_ANSWER"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / f"{target.key}__{Path(case_name).stem}.txt"
    raw_path.write_text(stdout, encoding="utf-8", errors="replace")
    return RunResult(status, stdout, stderr, elapsed, errors, str(raw_path))


def write_problem(case_name: str, input_text: str, results: Dict[str, RunResult],
                  problem_dir: Path) -> None:
    problem_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"# Problem Case: {case_name}", "", "## Input", "```text",
             input_text.rstrip(), "```", "", "## Results", ""]
    for name, result in results.items():
        lines.append(f"### {name}: {result.status}")
        lines.append(f"- elapsed: {result.elapsed:.3f}s")
        lines.append(f"- raw output: {result.raw_output_path}")
        for err in result.errors[:30]:
            lines.append(f"- {err}")
        lines.append("")
    (problem_dir / f"{Path(case_name).stem}.md").write_text(
        "\n".join(lines), encoding="utf-8")


def write_summary(report_dir: Path, summaries: List[dict]) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "consensus_summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# HW14 Judge Report", "", f"- total_cases: {len(summaries)}",
             f"- passed_cases: {sum(1 for s in summaries if s['all_passed'])}", "",
             "| case | all_passed | max_elapsed |", "|---|---:|---:|"]
    for item in summaries:
        lines.append(f"| {item['case']} | {item['all_passed']} | {item['max_elapsed']:.3f}s |")
    (report_dir / "consensus_summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HW14 flexible judge")
    parser.add_argument("--mode", choices=["self", "mutual", "both"], default="self")
    parser.add_argument("--co-judge-dir", default=".")
    parser.add_argument("--target-pattern", default="互测代码_*")
    parser.add_argument("--official-src", default="")
    parser.add_argument("--build-dir", default=".build_targets_hw14")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260607)
    parser.add_argument("--max-lines", type=int, default=260)
    parser.add_argument("--data-dir", default="data_hw14")
    parser.add_argument("--out-dir", default="out_raw_hw14")
    parser.add_argument("--report-dir", default="report_hw14")
    parser.add_argument("--problem-dir", default="problem_cases_hw14")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--compile-timeout", type=float, default=90.0)
    parser.add_argument("--max-cases", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    official_src = find_official_src(args.official_src)
    data_dir = (JUDGE_DIR / args.data_dir).resolve()
    if args.generate:
        data_dir.mkdir(parents=True, exist_ok=True)
        clear_directory(data_dir)
        generate_all(str(data_dir), args.count, args.seed, args.max_lines)
    if not data_dir.is_dir() or not list(data_dir.glob("*.txt")):
        data_dir.mkdir(parents=True, exist_ok=True)
        generate_all(str(data_dir), args.count, args.seed, args.max_lines)
    targets = discover_targets(args, official_src)
    cases = sorted(data_dir.glob("*.txt"))
    if args.max_cases > 0:
        cases = cases[:args.max_cases]
    out_dir = (JUDGE_DIR / args.out_dir).resolve()
    report_dir = (JUDGE_DIR / args.report_dir).resolve()
    problem_dir = (JUDGE_DIR / args.problem_dir).resolve()
    clear_directory(out_dir)
    clear_directory(problem_dir)
    summaries: List[dict] = []
    for idx, case_path in enumerate(cases, start=1):
        input_text = case_path.read_text(encoding="utf-8", errors="replace")
        print(f"[{idx}/{len(cases)}] {case_path.name}")
        results: Dict[str, RunResult] = {}
        for target in targets:
            result = run_target(target, case_path.name, input_text, out_dir, args.timeout)
            results[target.display_name] = result
            print(f"  - {target.display_name}: {result.status} ({result.elapsed:.3f}s)")
        all_passed = all(r.status == "PASSED" for r in results.values())
        if not all_passed:
            write_problem(case_path.name, input_text, results, problem_dir)
        summaries.append({
            "case": case_path.name,
            "all_passed": all_passed,
            "max_elapsed": max((r.elapsed for r in results.values()), default=0.0),
            "targets": {name: {"status": r.status, "elapsed": r.elapsed, "errors": r.errors}
                        for name, r in results.items()},
        })
    write_summary(report_dir, summaries)
    print(f"summary: {report_dir / 'consensus_summary.md'}")
    return 0 if all(item["all_passed"] for item in summaries) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise SystemExit(3)
