#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HW11 reference-output judge for OO U3 spec3."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from collections import Counter, deque
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from judge.core.target_matching import direct_target_entry, matching_target_entries

from .generator import TYPES, generate_all


RE_MAIN_METHOD = re.compile(r"\bpublic\s+static\s+void\s+main\s*\(")
ROOT = Path(__file__).resolve().parents[1]
JUDGE_DIR = Path(__file__).resolve().parent
DEFAULT_OFFICIAL_SRC = JUDGE_DIR / "lib"


def _fallback_search_roots() -> List[Path]:
    roots: List[Path] = []
    cur = JUDGE_DIR
    for _ in range(6):
        cur = cur.parent
        roots.append(cur)
        u3 = cur / "U3"
        if u3.is_dir():
            roots.append(u3)
    return roots


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
        if path.is_dir():
            return path.resolve()
    if DEFAULT_OFFICIAL_SRC.is_dir() and any(DEFAULT_OFFICIAL_SRC.rglob("*.java")):
        return DEFAULT_OFFICIAL_SRC.resolve()
    for base in _fallback_search_roots():
        try:
            candidates = list(base.rglob("面向对象第三单元第三次作业官方包"))
        except OSError:
            continue
        for cand in candidates:
            if cand.is_dir() and any(cand.rglob("*.java")):
                return cand.resolve()
        try:
            for candidate in base.rglob("NetworkInterface.java"):
                try:
                    if "spec3" in candidate.read_text(encoding="utf-8", errors="replace"):
                        return candidate.parents[3].resolve()
                except OSError:
                    continue
        except OSError:
            continue
    raise RuntimeError("cannot locate official spec3 source directory")


def contains_main(java_file: Path) -> bool:
    try:
        return RE_MAIN_METHOD.search(java_file.read_text(encoding="utf-8", errors="replace")) is not None
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


def compile_project(source_dir: Path, official_src: Path, build_dir: Path, timeout: float) -> Tuple[bool, str]:
    java_files = [str(p) for p in official_src.rglob("*.java")]
    java_files.extend(str(p) for p in source_dir.glob("*.java"))
    if not java_files:
        return False, "no java files"
    build_dir.mkdir(parents=True, exist_ok=True)
    clear_directory(build_dir)
    cmd = ["javac", "-encoding", "UTF-8", "-d", str(build_dir)] + java_files
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
            projects.append(TargetProject(
                key=key,
                display_name=name,
                source_dir=source_dir,
                build_dir=build_dir,
                command=["java", "-cp", str(build_dir), parse_main_class(main_file)],
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


class ErrorStats:
    def __init__(self) -> None:
        self.single: Dict[str, Counter] = {
            "eui": Counter(), "evi": Counter(), "uinf": Counter(), "vinf": Counter(),
            "ss": Counter(), "eci": Counter(), "ic": Counter(), "nc": Counter(),
            "csu": Counter(), "csv": Counter(),
        }
        self.pair_ids: Dict[str, Counter] = {
            "ds": Counter(), "flnf": Counter(), "uc": Counter(), "vu": Counter(), "dm": Counter(),
        }
        self.pair_total: Counter = Counter()
        self.invalid_age = 0
        self.invalid_coins = 0
        self.invalid_type = 0
        self.invalid_comment = 0
        self.invalid_rank = 0
        self.no_user = 0
        self.no_video_uploaded = 0

    def one(self, code: str, value: int) -> str:
        self.single[code][value] += 1
        return f"{code}-{sum(self.single[code].values())}, {value}-{self.single[code][value]}"

    def pair(self, code: str, a: int, b: int, sort_ids: bool = False, uncess: bool = False) -> str:
        if sort_ids and a > b:
            a, b = b, a
        self.pair_total[code] += 1
        self.pair_ids[code][a] += 1
        if a != b or not uncess:
            self.pair_ids[code][b] += 1
        return f"{code}-{self.pair_total[code]}, {a}-{self.pair_ids[code][a]}, {b}-{self.pair_ids[code][b]}"

    def age(self, value: int) -> str:
        self.invalid_age += 1
        return f"ia-{self.invalid_age}, {value}"

    def coins(self, value: int) -> str:
        self.invalid_coins += 1
        return f"ivc-{self.invalid_coins}, {value}"

    def typ(self, value: str) -> str:
        self.invalid_type += 1
        return f"it-{self.invalid_type}, {value}"

    def comment(self) -> str:
        self.invalid_comment += 1
        return f"ict-{self.invalid_comment}"

    def rank(self, value: int) -> str:
        self.invalid_rank += 1
        return f"ir-{self.invalid_rank}, {value}"

    def nouser(self) -> str:
        self.no_user += 1
        return f"nu-{self.no_user}"

    def no_video_uploaded_exc(self) -> str:
        self.no_video_uploaded += 1
        return f"nvu-{self.no_video_uploaded}"


class ReferenceModel:
    def __init__(self) -> None:
        self.users: Dict[int, Dict[str, object]] = {}
        self.following: Dict[int, Set[int]] = {}
        self.followers: Dict[int, Set[int]] = {}
        self.received: Dict[int, List[int]] = {}
        self.watched: Dict[int, Set[int]] = {}
        self.liked: Dict[int, Set[int]] = {}
        self.type_counts: Dict[int, Dict[str, int]] = {}
        self.medals: Dict[int, Set[int]] = {}
        self.contributions: Dict[int, Dict[int, int]] = {}
        self.videos: Dict[int, Dict[str, object]] = {}
        self.mutual = 0
        self.err = ErrorStats()
        self.out: List[str] = []

    def valid_type(self, typ: str) -> bool:
        return typ in TYPES

    def add_user(self, uid: int, age: int, name: str) -> None:
        if uid in self.users:
            self.out.append(self.err.one("eui", uid))
        elif age < 0 or age > 110:
            self.out.append(self.err.age(age))
        else:
            self.users[uid] = {"name": name, "age": age, "coins": 0}
            self.following[uid] = set()
            self.followers[uid] = set()
            self.received[uid] = []
            self.watched[uid] = set()
            self.liked[uid] = set()
            self.type_counts[uid] = {typ: 0 for typ in TYPES}
            self.medals[uid] = set()
            self.contributions[uid] = {}
            self.out.append("add_user succeeded")

    def upload_video(self, uid: int, vid: int, typ: str) -> None:
        if uid not in self.users:
            self.out.append(self.err.one("uinf", uid))
        elif vid in self.videos:
            self.out.append(self.err.one("evi", vid))
        elif not self.valid_type(typ):
            self.out.append(self.err.typ(typ))
        else:
            self.videos[vid] = {
                "uploader": uid, "type": typ, "play": 0, "likes": 0,
                "forward": 0, "coins": 0, "comments": [],
            }
            for fan in list(self.followers[uid]):
                self.received[fan].insert(0, vid)
            self.out.append("upload_video succeeded")

    def follow_user(self, a: int, b: int) -> None:
        if a not in self.users:
            self.out.append(self.err.one("uinf", a))
        elif b not in self.users:
            self.out.append(self.err.one("uinf", b))
        elif a == b:
            self.out.append(self.err.one("ss", a))
        elif b in self.following[a]:
            self.out.append(self.err.pair("ds", a, b))
        else:
            self.following[a].add(b)
            self.followers[b].add(a)
            if a in self.following[b]:
                self.mutual += 1
            self.out.append("follow_user succeeded")

    def unfollow_user(self, a: int, b: int) -> None:
        if a not in self.users:
            self.out.append(self.err.one("uinf", a))
        elif b not in self.users:
            self.out.append(self.err.one("uinf", b))
        elif b not in self.following[a]:
            self.out.append(self.err.pair("flnf", a, b, sort_ids=True))
        else:
            if a in self.following[b]:
                self.mutual -= 1
            self.following[a].remove(b)
            self.followers[b].remove(a)
            self.out.append("unfollow_user succeeded")

    def watch_video(self, uid: int, vid: int) -> None:
        if uid not in self.users:
            self.out.append(self.err.one("uinf", uid))
        elif vid not in self.videos:
            self.out.append(self.err.one("vinf", vid))
        else:
            self.received[uid] = [x for x in self.received[uid] if x != vid]
            self.watched[uid].add(vid)
            typ = str(self.videos[vid]["type"])
            self.type_counts[uid][typ] += 1
            self.videos[vid]["play"] = int(self.videos[vid]["play"]) + 1
            self.out.append("watch_video succeeded")

    def query_received(self, uid: int) -> None:
        if uid not in self.users:
            self.out.append(self.err.one("uinf", uid))
            return
        self.out.append("query_received_unwatched_videos succeeded")
        first = self.received[uid][:5]
        self.out.append(" ".join(map(str, first)) if first else "None")

    def query_ratio(self, uid: int) -> None:
        if uid not in self.users:
            self.out.append(self.err.one("uinf", uid))
            return
        counts = [0, 0, 0, 0]
        for fid in self.followers[uid]:
            age = int(self.users[fid]["age"])
            if age <= 16:
                counts[0] += 1
            elif age <= 30:
                counts[1] += 1
            elif age <= 45:
                counts[2] += 1
            else:
                counts[3] += 1
        n = len(self.followers[uid])
        rendered = [
            "0.00" if n == 0 else str((Decimal(c) / Decimal(n)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            for c in counts
        ]
        self.out.append("query_up_followers_age_ratio succeeded")
        self.out.append(f"{self.users[uid]['name']} {' '.join(rendered)}")

    def query_shortest(self, a: int, b: int) -> None:
        if a not in self.users:
            self.out.append(self.err.one("uinf", a))
        elif b not in self.users:
            self.out.append(self.err.one("uinf", b))
        elif a == b:
            self.out.append("0")
        else:
            q = deque([(a, 0)])
            seen = {a}
            while q:
                cur, dist = q.popleft()
                for nxt in self.following[cur]:
                    if nxt == b:
                        self.out.append(str(dist + 1))
                        return
                    if nxt not in seen:
                        seen.add(nxt)
                        q.append((nxt, dist + 1))
            self.out.append(self.err.pair("uc", a, b, sort_ids=True, uncess=True))

    def add_user_coins(self, uid: int, coins: int) -> None:
        if uid not in self.users:
            self.out.append(self.err.one("uinf", uid))
        else:
            self.users[uid]["coins"] = int(self.users[uid]["coins"]) + coins
            self.out.append("add_user_coins succeeded")

    def like_video(self, uid: int, vid: int) -> None:
        if uid not in self.users:
            self.out.append(self.err.one("uinf", uid))
        elif vid not in self.videos:
            self.out.append(self.err.one("vinf", vid))
        elif uid == int(self.videos[vid]["uploader"]):
            self.out.append(self.err.one("eui", uid))
        elif vid not in self.watched[uid]:
            self.out.append(self.err.pair("vu", uid, vid))
        elif vid in self.liked[uid]:
            self.liked[uid].remove(vid)
            self.videos[vid]["likes"] = int(self.videos[vid]["likes"]) - 1
            self.out.append("unlike_video succeeded")
        else:
            self.liked[uid].add(vid)
            self.videos[vid]["likes"] = int(self.videos[vid]["likes"]) + 1
            self.out.append("like_video succeeded")

    def coin_video(self, uid: int, vid: int, amount: int) -> None:
        if uid not in self.users:
            self.out.append(self.err.one("uinf", uid))
        elif vid not in self.videos:
            self.out.append(self.err.one("vinf", vid))
        elif uid == int(self.videos[vid]["uploader"]):
            self.out.append(self.err.one("eui", uid))
        elif vid not in self.watched[uid]:
            self.out.append(self.err.pair("vu", uid, vid))
        elif amount not in (1, 2):
            self.out.append(self.err.coins(amount))
        elif int(self.users[uid]["coins"]) < amount:
            self.out.append(self.err.one("ic", uid))
        else:
            up = int(self.videos[vid]["uploader"])
            self.users[uid]["coins"] = int(self.users[uid]["coins"]) - amount
            self.users[up]["coins"] = int(self.users[up]["coins"]) + amount
            self.videos[vid]["coins"] = int(self.videos[vid]["coins"]) + amount
            self.contributions[up][uid] = self.contributions[up].get(uid, 0) + amount
            self.out.append("coin_video succeeded")

    def query_best_contributor(self, uid: int) -> None:
        if uid not in self.users:
            self.out.append(self.err.one("uinf", uid))
        elif not self.contributions[uid]:
            self.out.append(self.err.one("nc", uid))
        else:
            best_value = max(self.contributions[uid].values())
            best_id = min(k for k, v in self.contributions[uid].items() if v == best_value)
            self.out.append(f"{uid}'s best contributor is {best_id}")

    def forward_video(self, uid: int, vid: int, follower: int) -> None:
        if uid not in self.users:
            self.out.append(self.err.one("uinf", uid))
        elif follower not in self.users:
            self.out.append(self.err.one("uinf", follower))
        elif vid not in self.videos:
            self.out.append(self.err.one("vinf", vid))
        elif vid not in self.watched[uid]:
            self.out.append(self.err.pair("vu", uid, vid))
        elif follower not in self.followers[uid]:
            self.out.append(self.err.pair("flnf", uid, follower, sort_ids=True))
        else:
            self.received[follower].insert(0, vid)
            self.videos[vid]["forward"] = int(self.videos[vid]["forward"]) + 1
            self.out.append("forward_video succeeded")

    def send_comment(self, uid: int, vid: int, cid: int, comment: str) -> None:
        if uid not in self.users:
            self.out.append(self.err.one("uinf", uid))
        elif vid not in self.videos:
            self.out.append(self.err.one("vinf", vid))
        elif any(old_id == cid for old_id, _ in self.videos[vid]["comments"]):  # type: ignore
            self.out.append(self.err.one("eci", cid))
        elif comment == "":
            self.out.append(self.err.comment())
        else:
            self.videos[vid]["comments"].append((cid, comment))  # type: ignore
            self.out.append("send_comment succeeded")

    def clean_spam_comments(self, vid: int, keyword: str) -> None:
        if vid not in self.videos:
            self.out.append(self.err.one("vinf", vid))
            return
        comments: List[Tuple[int, str]] = self.videos[vid]["comments"]  # type: ignore
        removed = 0
        max_count = 0
        kept: List[Tuple[int, str]] = []
        for cid, body in comments:
            if keyword in body:
                removed += 1
                max_count = max(max_count, self.count_keyword(body, keyword))
            else:
                kept.append((cid, body))
        self.videos[vid]["comments"] = kept
        self.out.append(f"{removed} comments have been cleaned.")
        self.out.append(f"The maximum count of the keyword found in removed comments is {max_count}")

    @staticmethod
    def count_keyword(body: str, keyword: str) -> int:
        if keyword == "":
            return len(body) + 1
        return sum(1 for i in range(0, len(body) - len(keyword) + 1) if body[i:i + len(keyword)] == keyword)

    def heat(self, vid: int) -> int:
        video = self.videos[vid]
        return (int(video["play"]) * 2 + int(video["likes"]) * 3
                + int(video["forward"]) * 4 + int(video["coins"]) * 5)

    def query_most_popular_video(self, typ: str) -> None:
        if not self.valid_type(typ):
            self.out.append(self.err.typ(typ))
            return
        candidates = [vid for vid, video in self.videos.items() if video["type"] == typ]
        if not candidates:
            self.out.append(f"The most popular video of {typ} is NULL.")
            return
        best_heat = max(self.heat(vid) for vid in candidates)
        best_id = min(vid for vid in candidates if self.heat(vid) == best_heat)
        self.out.append(f"{typ}'s most popular video is {best_id}")

    def purchase_medal(self, uid: int, vid: int, amount: int) -> None:
        if uid not in self.users:
            self.out.append(self.err.one("uinf", uid))
        elif vid not in self.videos:
            self.out.append(self.err.one("vinf", vid))
        else:
            up = int(self.videos[vid]["uploader"])
            if uid == up:
                self.out.append(self.err.one("eui", uid))
            elif int(self.users[uid]["coins"]) < amount:
                self.out.append(self.err.one("ic", uid))
            elif up in self.medals[uid]:
                self.out.append(self.err.pair("dm", uid, up))
            else:
                self.users[uid]["coins"] = int(self.users[uid]["coins"]) - amount
                self.users[up]["coins"] = int(self.users[up]["coins"]) + amount
                self.medals[uid].add(up)
                self.out.append("purchase_medal succeeded")

    def query_longest_dec_seq(self) -> None:
        order = sorted(self.users, key=lambda uid: int(self.users[uid]["age"]))
        dp: Dict[int, int] = {}
        ans = 0
        for uid in order:
            best = 1
            age = int(self.users[uid]["age"])
            for nxt in self.following[uid]:
                if age > int(self.users[nxt]["age"]):
                    best = max(best, dp[nxt] + 1)
            dp[uid] = best
            ans = max(ans, best)
        self.out.append(str(ans))

    def interest(self, uid: int, typ: str) -> int:
        return self.type_counts[uid][typ] * (len(self.videos) - len(self.watched[uid]) + 1)

    def influence(self, uid: int, typ: str) -> int:
        return sum(
            self.heat(vid)
            for vid, video in self.videos.items()
            if int(video["uploader"]) == uid and video["type"] == typ
        )

    def up_score(self, watcher: int, up: int) -> int:
        return sum(self.interest(watcher, typ) * self.influence(up, typ) for typ in TYPES)

    def video_score(self, uid: int, vid: int) -> int:
        return self.heat(vid) * self.interest(uid, str(self.videos[vid]["type"]))

    def query_global_best_contributor(self) -> None:
        if not self.users:
            self.out.append(self.err.nouser())
            return
        best_counts: Counter = Counter()
        for up, contributors in self.contributions.items():
            if not contributors:
                continue
            best_value = max(contributors.values())
            best_id = min(uid for uid, value in contributors.items() if value == best_value)
            best_counts[best_id] += 1
        if not best_counts:
            self.out.append("Global best contributor is 0 with 0 times.")
            return
        max_times = max(best_counts.values())
        best = min(uid for uid, times in best_counts.items() if times == max_times)
        self.out.append(f"Global best contributor is {best} with {max_times} times.")

    def recommend_video(self, uid: int) -> None:
        if uid not in self.users:
            self.out.append(self.err.one("uinf", uid))
        elif not self.videos:
            self.out.append(self.err.no_video_uploaded_exc())
        elif not self.watched[uid]:
            self.out.append(self.err.one("csv", uid))
        else:
            best_score = max(self.video_score(uid, vid) for vid in self.videos)
            best_id = min(vid for vid in self.videos if self.video_score(uid, vid) == best_score)
            self.out.append(f"We recommended video {best_id} for {uid}")

    def recommend_nth_up(self, uid: int, rank: int) -> None:
        if uid not in self.users:
            self.out.append(self.err.one("uinf", uid))
        elif rank <= 0:
            self.out.append(self.err.rank(rank))
        elif not self.videos:
            self.out.append(self.err.no_video_uploaded_exc())
        else:
            candidates = [
                other for other in self.users
                if other != uid and other not in self.following[uid]
            ]
            if len(candidates) < rank:
                self.out.append(self.err.one("csu", uid))
                return
            ordered = sorted(candidates, key=lambda other: (-self.up_score(uid, other), other))
            ans = ordered[rank - 1]
            self.out.append(f"We recommended up {ans} at rank {rank} for {uid}")

    def query_most_influential_up(self, typ: str) -> None:
        if not self.valid_type(typ):
            self.out.append(self.err.typ(typ))
        elif not self.users:
            self.out.append(self.err.nouser())
        else:
            best_value = max(self.influence(uid, typ) for uid in self.users)
            best_id = min(uid for uid in self.users if self.influence(uid, typ) == best_value)
            self.out.append(f"The most influential up in {typ} is {best_id}")

    def query_user_profile(self, uid: int) -> None:
        if uid not in self.users:
            self.out.append(self.err.one("uinf", uid))
        elif not self.watched[uid]:
            self.out.append(self.err.one("csv", uid))
        else:
            parts: List[str] = []
            for typ in TYPES:
                parts.append(f"{typ} {self.interest(uid, typ)}")
            self.out.append(" ".join(parts))

    def run_line(self, raw: str) -> Optional[str]:
        line = raw.strip()
        if not line:
            return None
        cmd = line.split()[0]
        try:
            if cmd == "send_comment":
                parts = line.split(maxsplit=4)
                comment = parts[4] if len(parts) >= 5 else ""
                self.send_comment(int(parts[1]), int(parts[2]), int(parts[3]), comment)
            elif cmd == "clean_spam_comments":
                parts = line.split(" ", 2)
                keyword = parts[2] if len(parts) >= 3 else ""
                self.clean_spam_comments(int(parts[1]), keyword)
            else:
                p = line.split()
                if cmd == "add_user":
                    self.add_user(int(p[1]), int(p[2]), p[3])
                elif cmd == "upload_video":
                    self.upload_video(int(p[1]), int(p[2]), p[3])
                elif cmd == "follow_user":
                    self.follow_user(int(p[1]), int(p[2]))
                elif cmd == "unfollow_user":
                    self.unfollow_user(int(p[1]), int(p[2]))
                elif cmd == "watch_video":
                    self.watch_video(int(p[1]), int(p[2]))
                elif cmd == "query_received_unwatched_videos":
                    self.query_received(int(p[1]))
                elif cmd == "query_up_followers_age_ratio":
                    self.query_ratio(int(p[1]))
                elif cmd == "query_mutual_following_sum":
                    self.out.append(str(self.mutual))
                elif cmd == "query_shortest_path":
                    self.query_shortest(int(p[1]), int(p[2]))
                elif cmd == "add_user_coins":
                    self.add_user_coins(int(p[1]), int(p[2]))
                elif cmd == "like_video":
                    self.like_video(int(p[1]), int(p[2]))
                elif cmd == "coin_video":
                    self.coin_video(int(p[1]), int(p[2]), int(p[3]))
                elif cmd == "query_best_contributor":
                    self.query_best_contributor(int(p[1]))
                elif cmd == "forward_video":
                    self.forward_video(int(p[1]), int(p[2]), int(p[3]))
                elif cmd == "query_most_popular_video":
                    self.query_most_popular_video(p[1])
                elif cmd == "purchase_medal":
                    self.purchase_medal(int(p[1]), int(p[2]), int(p[3]))
                elif cmd == "queryLongestDecSeq":
                    self.query_longest_dec_seq()
                elif cmd == "queryGlobalBestContributor":
                    self.query_global_best_contributor()
                elif cmd == "recommend_video":
                    self.recommend_video(int(p[1]))
                elif cmd == "recommend_Nth_up":
                    self.recommend_nth_up(int(p[1]), int(p[2]))
                elif cmd == "query_most_influential_up":
                    self.query_most_influential_up(p[1])
                elif cmd == "query_user_profile":
                    self.query_user_profile(int(p[1]))
                elif cmd == "end":
                    return "end"
                else:
                    return f"unknown command: {line}"
        except (IndexError, ValueError) as exc:
            return f"bad command: {line} ({exc})"
        return None


def expected_output(input_text: str) -> Tuple[List[str], List[str]]:
    model = ReferenceModel()
    errors: List[str] = []
    for idx, raw in enumerate(input_text.splitlines(), start=1):
        err = model.run_line(raw)
        if err == "end":
            break
        if err:
            errors.append(f"line {idx}: {err}")
    return model.out, errors


def run_target(target: TargetProject, case_name: str, input_text: str, expected: List[str],
               out_dir: Path, timeout: float) -> RunResult:
    start = time.monotonic()
    status = "PASSED"
    errors: List[str] = []
    stdout = ""
    stderr = ""
    try:
        proc = subprocess.run(target.command, input=input_text, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=timeout)
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
    actual = [line.strip() for line in stdout.splitlines() if line.strip()]
    if status == "PASSED" and actual != expected:
        status = "WRONG_ANSWER"
        n = min(len(actual), len(expected))
        for i in range(n):
            if actual[i] != expected[i]:
                errors.append(f"line {i + 1}: expected '{expected[i]}', got '{actual[i]}'")
                break
        if len(actual) != len(expected):
            errors.append(f"line count mismatch: expected {len(expected)}, got {len(actual)}")
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / f"{target.key}__{Path(case_name).stem}.txt"
    raw_path.write_text(stdout, encoding="utf-8", errors="replace")
    return RunResult(status, stdout, stderr, elapsed, errors, str(raw_path))


def write_problem(case_name: str, input_text: str, expected: List[str], results: Dict[str, RunResult],
                  problem_dir: Path) -> None:
    problem_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"# Problem Case: {case_name}", "", "## Input", "```text", input_text.rstrip(), "```", "",
             "## Expected Output", "```text", "\n".join(expected), "```", "", "## Results", ""]
    for name, result in results.items():
        lines.append(f"### {name}: {result.status}")
        lines.append(f"- elapsed: {result.elapsed:.3f}s")
        lines.append(f"- raw output: {result.raw_output_path}")
        for err in result.errors[:20]:
            lines.append(f"- {err}")
        lines.append("")
    (problem_dir / f"{Path(case_name).stem}.md").write_text("\n".join(lines), encoding="utf-8")


def write_summary(report_dir: Path, summaries: List[dict]) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "consensus_summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# HW11 Judge Report", "", f"- total_cases: {len(summaries)}",
             f"- passed_cases: {sum(1 for s in summaries if s['all_passed'])}", "",
             "| case | all_passed | max_elapsed |", "|---|---:|---:|"]
    for item in summaries:
        lines.append(f"| {item['case']} | {item['all_passed']} | {item['max_elapsed']:.3f}s |")
    (report_dir / "consensus_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HW11 reference-output judge")
    parser.add_argument("--mode", choices=["self", "mutual", "both"], default="self")
    parser.add_argument("--co-judge-dir", default=".")
    parser.add_argument("--target-pattern", default="互测代码_*")
    parser.add_argument("--official-src", default="")
    parser.add_argument("--build-dir", default=".build_targets_hw11")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260515)
    parser.add_argument("--max-lines", type=int, default=3000)
    parser.add_argument("--data-dir", default="data_hw11")
    parser.add_argument("--out-dir", default="out_raw_hw11")
    parser.add_argument("--report-dir", default="report_hw11")
    parser.add_argument("--problem-dir", default="problem_cases_hw11")
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
        expected, input_errors = expected_output(input_text)
        print(f"[{idx}/{len(cases)}] {case_path.name}")
        results: Dict[str, RunResult] = {}
        if input_errors:
            print("  input error: " + "; ".join(input_errors[:3]))
        for target in targets:
            result = run_target(target, case_path.name, input_text, expected, out_dir, args.timeout)
            results[target.display_name] = result
            print(f"  - {target.display_name}: {result.status} ({result.elapsed:.3f}s)")
        all_passed = all(r.status == "PASSED" for r in results.values()) and not input_errors
        if not all_passed:
            write_problem(case_path.name, input_text, expected, results, problem_dir)
        summaries.append({
            "case": case_path.name,
            "all_passed": all_passed,
            "max_elapsed": max((r.elapsed for r in results.values()), default=0.0),
            "targets": {name: {"status": r.status, "elapsed": r.elapsed, "errors": r.errors}
                        for name, r in results.items()},
            "input_errors": input_errors,
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
