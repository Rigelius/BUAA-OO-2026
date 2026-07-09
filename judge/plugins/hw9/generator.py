#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HW9 testcase generator for the social-network mutual judge."""

from __future__ import annotations

import argparse
import os
import random
import string
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

MAX_MUTUAL_COMMANDS = 3000
FIXED_CASES_DIR = Path(__file__).resolve().parent / "fixed_cases"


def _write_case(out_dir: str, filename: str, lines: List[str]) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, filename), "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip())
        f.write("\n")


def _normalize_lines(text: str) -> List[str]:
    return [line.strip() for line in text.strip().splitlines() if line.strip()]


def _load_fixed_cases_from_dir() -> List[Tuple[str, List[str]]]:
    cases: List[Tuple[str, List[str]]] = []
    if not FIXED_CASES_DIR.is_dir():
        return cases
    for path in sorted(FIXED_CASES_DIR.glob("*.txt")):
        lines = _normalize_lines(path.read_text(encoding="utf-8", errors="replace"))
        if lines:
            cases.append((path.name, lines[:MAX_MUTUAL_COMMANDS]))
    return cases


def _builtin_fixed_cases() -> List[Tuple[str, List[str]]]:
    return [
        (
            "h9_fixed_01_sample.txt",
            _normalize_lines(
                """
                add_user 1 20 Alice
                add_user 2 22 Bob
                add_user 3 25 Charlie
                follow_user 1 2
                follow_user 2 1
                query_mutual_following_sum
                upload_video 1 101
                watch_video 2 101
                query_received_unwatched_videos 2
                follow_user 2 3
                query_shortest_path 1 3
                """
            ),
        ),
        (
            "h9_fixed_02_exceptions.txt",
            _normalize_lines(
                """
                add_user 1 20 A
                add_user 1 21 B
                add_user 2 111 Old
                upload_video 9 100
                upload_video 1 100
                upload_video 1 100
                follow_user 1 1
                follow_user 1 2
                unfollow_user 1 2
                watch_video 2 100
                query_shortest_path 1 2
                query_up_followers_age_ratio 9
                """
            ),
        ),
        (
            "h9_fixed_03_mutual_updates.txt",
            _normalize_lines(
                """
                add_user 1 10 U1
                add_user 2 17 U2
                add_user 3 31 U3
                add_user 4 46 U4
                follow_user 1 2
                follow_user 2 1
                follow_user 3 4
                follow_user 4 3
                query_mutual_following_sum
                unfollow_user 2 1
                query_mutual_following_sum
                follow_user 2 1
                query_up_followers_age_ratio 1
                query_shortest_path 3 1
                follow_user 4 1
                query_shortest_path 3 1
                """
            ),
        ),
        (
            "h9_fixed_04_video_order.txt",
            _normalize_lines(
                """
                add_user 1 20 Up
                add_user 2 20 Fan
                follow_user 2 1
                upload_video 1 101
                upload_video 1 102
                upload_video 1 103
                upload_video 1 104
                upload_video 1 105
                upload_video 1 106
                query_received_unwatched_videos 2
                watch_video 2 104
                query_received_unwatched_videos 2
                watch_video 2 999
                """
            ),
        ),
    ]


class CaseBuilder:
    def __init__(self, seed: Optional[int], max_lines: int) -> None:
        self.rng = random.Random(seed)
        self.max_lines = max_lines
        self.lines: List[str] = []
        self.users: Dict[int, Tuple[str, int]] = {}
        self.videos: Dict[int, int] = {}
        self.following: Dict[int, Set[int]] = {}
        self.next_user = 1
        self.next_video = 1001

    def emit(self, line: str) -> bool:
        if len(self.lines) >= self.max_lines:
            return False
        self.lines.append(line)
        return True

    def name(self) -> str:
        length = self.rng.randint(1, 12)
        return "".join(self.rng.choice(string.ascii_letters) for _ in range(length))

    def existing_user(self) -> Optional[int]:
        if not self.users:
            return None
        return self.rng.choice(list(self.users.keys()))

    def two_users(self) -> Tuple[Optional[int], Optional[int]]:
        if len(self.users) < 2:
            return None, None
        a, b = self.rng.sample(list(self.users.keys()), 2)
        return a, b

    def non_user(self) -> int:
        x = self.rng.randint(-100000, 100000)
        while x in self.users:
            x = self.rng.randint(-100000, 100000)
        return x

    def non_video(self) -> int:
        x = self.rng.randint(-100000, 100000)
        while x in self.videos:
            x = self.rng.randint(-100000, 100000)
        return x

    def add_user(self, valid: bool = True) -> None:
        if not valid and self.users and self.rng.random() < 0.7:
            uid = self.existing_user()
        else:
            uid = self.next_user
            self.next_user += 1
        age = self.rng.randint(1, 110) if valid else self.rng.choice([111, 200])
        self.emit(f"add_user {uid} {age} {self.name()}")
        if valid and uid not in self.users:
            self.users[uid] = (self.name(), age)
            self.following[uid] = set()

    def follow(self, valid: bool = True) -> None:
        a, b = self.two_users()
        if a is None:
            self.add_user(True)
            return
        if not valid:
            pick = self.rng.random()
            if pick < 0.25:
                a = self.non_user()
            elif pick < 0.5:
                b = self.non_user()
            elif pick < 0.75:
                b = a
            elif b not in self.following[a]:
                self.following[a].add(b)
        if self.emit(f"follow_user {a} {b}") and valid and a in self.users and b in self.users and a != b and b not in self.following[a]:
            self.following[a].add(b)

    def unfollow(self, valid: bool = True) -> None:
        pairs = [(a, b) for a, s in self.following.items() for b in s]
        if valid and pairs:
            a, b = self.rng.choice(pairs)
        else:
            a, b = self.two_users()
            if a is None:
                self.add_user(True)
                return
            if not valid and self.rng.random() < 0.35:
                a = self.non_user()
            elif not valid and self.rng.random() < 0.55:
                b = self.non_user()
            elif b in self.following.get(a, set()):
                self.following[a].remove(b)
        if self.emit(f"unfollow_user {a} {b}") and valid and b in self.following.get(a, set()):
            self.following[a].remove(b)

    def upload(self, valid: bool = True) -> None:
        uid = self.existing_user()
        if uid is None:
            self.add_user(True)
            return
        vid = self.next_video
        self.next_video += 1
        if not valid:
            if self.rng.random() < 0.5:
                uid = self.non_user()
            elif self.videos:
                vid = self.rng.choice(list(self.videos.keys()))
        if self.emit(f"upload_video {uid} {vid}") and valid and uid in self.users and vid not in self.videos:
            self.videos[vid] = uid

    def watch(self, valid: bool = True) -> None:
        uid = self.existing_user()
        vid = self.rng.choice(list(self.videos.keys())) if self.videos else self.next_video
        if uid is None:
            self.add_user(True)
            return
        if not valid:
            if self.rng.random() < 0.45:
                uid = self.non_user()
            else:
                vid = self.non_video()
        self.emit(f"watch_video {uid} {vid}")

    def query(self) -> None:
        op = self.rng.choice([
            "query_received_unwatched_videos",
            "query_up_followers_age_ratio",
            "query_mutual_following_sum",
            "query_shortest_path",
        ])
        if op == "query_mutual_following_sum":
            self.emit(op)
        elif op == "query_shortest_path":
            a = self.existing_user() if self.rng.random() > 0.1 else self.non_user()
            b = self.existing_user() if self.rng.random() > 0.1 else self.non_user()
            if a is None or b is None:
                self.add_user(True)
            else:
                self.emit(f"{op} {a} {b}")
        else:
            uid = self.existing_user() if self.rng.random() > 0.12 else self.non_user()
            if uid is None:
                self.add_user(True)
            else:
                self.emit(f"{op} {uid}")

    def build(self) -> List[str]:
        starter = self.rng.randint(8, 25)
        for _ in range(starter):
            self.add_user(True)
        for _ in range(min(self.max_lines - len(self.lines), self.rng.randint(60, self.max_lines))):
            pick = self.rng.random()
            if pick < 0.12:
                self.add_user(valid=self.rng.random() > 0.18)
            elif pick < 0.35:
                self.follow(valid=self.rng.random() > 0.2)
            elif pick < 0.48:
                self.unfollow(valid=self.rng.random() > 0.35)
            elif pick < 0.62:
                self.upload(valid=self.rng.random() > 0.18)
            elif pick < 0.74:
                self.watch(valid=self.rng.random() > 0.2)
            else:
                self.query()
        return self.lines[: self.max_lines]


def generate_all(out_dir: str, random_count: int, base_seed: Optional[int] = None, strict_mutual: bool = False) -> List[str]:
    files: List[str] = []
    seen = set()
    for name, lines in _load_fixed_cases_from_dir() + _builtin_fixed_cases():
        if name in seen:
            continue
        seen.add(name)
        _write_case(out_dir, name, lines[:MAX_MUTUAL_COMMANDS])
        files.append(name)

    for i in range(max(0, random_count)):
        seed = (base_seed + i) if base_seed is not None else None
        max_lines = MAX_MUTUAL_COMMANDS if strict_mutual else 1000
        builder = CaseBuilder(seed, max_lines=max_lines)
        lines = builder.build()
        filename = f"h9_random_{i + 1:02d}.txt"
        _write_case(out_dir, filename, lines)
        files.append(filename)
    return files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate HW9 testcases")
    parser.add_argument("--out", default="data")
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--strict-mutual", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    files = generate_all(args.out, args.count, args.seed, strict_mutual=args.strict_mutual)
    print(f"Generated {len(files)} files in '{args.out}':")
    for name in files:
        print(f"  - {name}")


if __name__ == "__main__":
    main()
