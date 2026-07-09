#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HW10 testcase generator for the spec2 video-network judge."""

from __future__ import annotations

import argparse
import os
import random
import string
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


TYPES = ["tech", "music", "sport", "game", "food", "travel", "comedy"]
MAX_COMMANDS = 3000
FIXED_CASES_DIR = Path(__file__).resolve().parent / "fixed_cases_hw10"


def _normalize_lines(text: str) -> List[str]:
    return [line.strip() for line in text.strip().splitlines() if line.strip()]


def _write_case(out_dir: str, filename: str, lines: List[str]) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, filename), "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip())
        f.write("\n")


def _load_fixed_cases_from_dir() -> List[Tuple[str, List[str]]]:
    cases: List[Tuple[str, List[str]]] = []
    if not FIXED_CASES_DIR.is_dir():
        return cases
    for path in sorted(FIXED_CASES_DIR.glob("*.txt")):
        lines = _normalize_lines(path.read_text(encoding="utf-8", errors="replace"))
        if lines:
            cases.append((path.name, lines[:MAX_COMMANDS]))
    return cases


def _builtin_fixed_cases() -> List[Tuple[str, List[str]]]:
    return [
        (
            "h10_fixed_01_sample.txt",
            _normalize_lines(
                """
                add_user 1 20 Alice
                add_user 2 22 Bob
                add_user_coins 2 10
                upload_video 1 101 tech
                watch_video 2 101
                like_video 2 101
                coin_video 2 101 2
                send_comment 2 101 1 Awesome!
                send_comment 2 101 2 Bad_Spam
                clean_spam_comments 101 Spam
                query_most_popular_video tech
                purchase_medal 2 101 5
                """
            ),
        ),
        (
            "h10_fixed_02_exception_priority.txt",
            _normalize_lines(
                """
                add_user 1 20 A
                add_user 1 21 B
                add_user 2 110 Old
                add_user 2 30 B
                add_user_coins 9 5
                upload_video 9 100 tech
                upload_video 9 101 tech
                upload_video 1 100 tech
                upload_video 1 100 music
                like_video 9 100
                like_video 2 999
                like_video 1 100
                like_video 2 100
                coin_video 2 100 3
                add_user_coins 2 1
                watch_video 2 100
                coin_video 2 100 3
                coin_video 2 100 2
                query_best_contributor 1
                purchase_medal 1 100 1
                purchase_medal 2 999 1
                purchase_medal 2 100 2
                purchase_medal 2 100 1
                clean_spam_comments 999 spam
                query_most_popular_video tech
                """
            ),
        ),
        (
            "h10_fixed_03_comments.txt",
            _normalize_lines(
                """
                add_user 1 20 Up
                add_user 2 21 Fan
                upload_video 1 200 tech
                upload_video 1 201 music
                send_comment 2 200 1 aaaa
                send_comment 2 200 2 baaa
                send_comment 2 200 3 keep
                send_comment 2 200 1 duplicate
                send_comment 9 200 4 bad
                clean_spam_comments 200 aa
                send_comment 2 201 5 abc
                send_comment 2 201 6 a
                clean_spam_comments 201 a
                clean_spam_comments 200 zz
                """
            ),
        ),
        (
            "h10_fixed_04_forward_received_heat.txt",
            _normalize_lines(
                """
                add_user 1 40 Up
                add_user 2 30 Mid
                add_user 3 20 Fan
                follow_user 2 1
                follow_user 3 2
                upload_video 1 301 tech
                upload_video 1 302 tech
                query_received_unwatched_videos 2
                watch_video 2 301
                forward_video 2 301 3
                query_received_unwatched_videos 3
                watch_video 3 301
                like_video 3 301
                query_most_popular_video tech
                query_most_popular_video food
                forward_video 1 301 2
                """
            ),
        ),
        (
            "h10_fixed_05_contributor_medal.txt",
            _normalize_lines(
                """
                add_user 1 30 Up
                add_user 2 25 A
                add_user 3 26 B
                add_user_coins 2 10
                add_user_coins 3 10
                upload_video 1 401 game
                watch_video 2 401
                watch_video 3 401
                coin_video 2 401 1
                coin_video 3 401 2
                coin_video 2 401 2
                query_best_contributor 1
                purchase_medal 2 401 3
                purchase_medal 2 401 1
                query_most_popular_video game
                """
            ),
        ),
        (
            "h10_fixed_06_longest_and_path.txt",
            _normalize_lines(
                """
                add_user 1 60 U1
                add_user 2 50 U2
                add_user 3 50 U3
                add_user 4 40 U4
                add_user 5 30 U5
                add_user 6 20 U6
                follow_user 1 2
                follow_user 2 4
                follow_user 3 4
                follow_user 4 5
                follow_user 5 6
                follow_user 6 1
                queryLongestDecSeq
                query_shortest_path 6 5
                unfollow_user 4 5
                queryLongestDecSeq
                query_mutual_following_sum
                follow_user 2 1
                query_mutual_following_sum
                """
            ),
        ),
        ("h10_fixed_07_stress_lis.txt", _stress_lis_case(1200)),
        ("h10_fixed_08_stress_comments.txt", _stress_comments_case(1200)),
    ]


def _stress_lis_case(size: int) -> List[str]:
    lines: List[str] = []
    for i in range(1, size + 1):
        lines.append(f"add_user {i} {110 - (i % 100)} U{i}")
    for i in range(1, size):
        lines.append(f"follow_user {i} {i + 1}")
    lines.extend(["queryLongestDecSeq"] * 12)
    return lines[:MAX_COMMANDS]


def _stress_comments_case(size: int) -> List[str]:
    lines = ["add_user 1 30 Up", "add_user 2 20 Fan", "upload_video 1 900 tech"]
    for i in range(1, size + 1):
        body = f"spamspam_{i}" if i % 2 == 0 else f"clean_{i}"
        lines.append(f"send_comment 2 900 {i} {body}")
    lines.append("clean_spam_comments 900 spam")
    lines.append("clean_spam_comments 900 clean")
    return lines[:MAX_COMMANDS]


class CaseBuilder:
    def __init__(self, seed: Optional[int], max_lines: int) -> None:
        self.rng = random.Random(seed)
        self.max_lines = max_lines
        self.lines: List[str] = []
        self.users: Dict[int, int] = {}
        self.coins: Dict[int, int] = {}
        self.following: Dict[int, Set[int]] = {}
        self.followers: Dict[int, Set[int]] = {}
        self.videos: Dict[int, Tuple[int, str]] = {}
        self.watched: Dict[int, Set[int]] = {}
        self.comments: Dict[int, Set[int]] = {}
        self.next_user = 1
        self.next_video = 1000
        self.next_comment = 1

    def emit(self, line: str) -> bool:
        if len(self.lines) >= self.max_lines:
            return False
        self.lines.append(line)
        return True

    def existing_user(self) -> Optional[int]:
        return self.rng.choice(list(self.users)) if self.users else None

    def two_users(self) -> Tuple[Optional[int], Optional[int]]:
        if len(self.users) < 2:
            return None, None
        return tuple(self.rng.sample(list(self.users), 2))  # type: ignore

    def existing_video(self) -> Optional[int]:
        return self.rng.choice(list(self.videos)) if self.videos else None

    def non_user(self) -> int:
        value = self.rng.randint(1_000_000, 2_000_000)
        while value in self.users:
            value = self.rng.randint(1_000_000, 2_000_000)
        return value

    def non_video(self) -> int:
        value = self.rng.randint(1_000_000, 2_000_000)
        while value in self.videos:
            value = self.rng.randint(1_000_000, 2_000_000)
        return value

    def random_name(self) -> str:
        return "".join(self.rng.choice(string.ascii_letters) for _ in range(self.rng.randint(1, 12)))

    def add_user(self, valid: bool = True) -> None:
        uid = self.next_user
        age = self.rng.randint(1, 110)
        if not valid:
            mode = self.rng.random()
            if mode < 0.5 and self.users:
                uid = self.existing_user() or uid
            else:
                uid = self.existing_user() if self.users else uid
        else:
            self.next_user += 1
        if self.emit(f"add_user {uid} {age} {self.random_name()}") and valid and uid not in self.users:
            self.users[uid] = age
            self.coins[uid] = 0
            self.following[uid] = set()
            self.followers[uid] = set()
            self.watched[uid] = set()

    def add_user_coins(self, valid: bool = True) -> None:
        uid = self.existing_user() if valid or self.rng.random() > 0.25 else self.non_user()
        if uid is None:
            self.add_user(True)
            return
        amount = self.rng.randint(1, 9999)
        if self.emit(f"add_user_coins {uid} {amount}") and uid in self.users:
            self.coins[uid] += amount

    def follow(self, valid: bool = True) -> None:
        a, b = self.two_users()
        if a is None or b is None:
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
            else:
                self.following[a].add(b)
                self.followers[b].add(a)
        if self.emit(f"follow_user {a} {b}") and a in self.users and b in self.users and a != b and b not in self.following[a]:
            self.following[a].add(b)
            self.followers[b].add(a)

    def unfollow(self, valid: bool = True) -> None:
        pairs = [(a, b) for a, s in self.following.items() for b in s]
        if valid and pairs:
            a, b = self.rng.choice(pairs)
        else:
            a, b = self.two_users()
            if a is None or b is None:
                self.add_user(True)
                return
            if not valid and self.rng.random() < 0.3:
                a = self.non_user()
            elif not valid and self.rng.random() < 0.55:
                b = self.non_user()
            elif b in self.following.get(a, set()):
                self.following[a].remove(b)
                self.followers[b].remove(a)
        if self.emit(f"unfollow_user {a} {b}") and a in self.users and b in self.following.get(a, set()):
            self.following[a].remove(b)
            self.followers[b].remove(a)

    def upload(self, valid: bool = True) -> None:
        uid = self.existing_user()
        if uid is None:
            self.add_user(True)
            return
        vid = self.next_video
        self.next_video += 1
        typ = self.rng.choice(TYPES)
        if not valid:
            pick = self.rng.random()
            if pick < 0.35:
                uid = self.non_user()
            elif pick < 0.7 and self.videos:
                vid = self.rng.choice(list(self.videos))
            else:
                uid = self.non_user()
        if self.emit(f"upload_video {uid} {vid} {typ}") and uid in self.users and vid not in self.videos and typ in TYPES:
            self.videos[vid] = (uid, typ)
            self.comments[vid] = set()

    def watch(self, valid: bool = True) -> None:
        uid = self.existing_user()
        vid = self.existing_video()
        if uid is None or vid is None:
            self.upload(True)
            return
        if not valid:
            if self.rng.random() < 0.45:
                uid = self.non_user()
            else:
                vid = self.non_video()
        if self.emit(f"watch_video {uid} {vid}") and uid in self.users and vid in self.videos:
            self.watched[uid].add(vid)

    def like(self, valid: bool = True) -> None:
        uid = self.existing_user()
        vid = self.existing_video()
        if uid is None or vid is None:
            self.upload(True)
            return
        if valid:
            uploader = self.videos[vid][0]
            candidates = [u for u in self.users if u != uploader]
            if not candidates:
                return
            uid = self.rng.choice(candidates)
            self.watched[uid].add(vid)
        elif self.rng.random() < 0.25:
            uid = self.non_user()
        elif self.rng.random() < 0.5:
            vid = self.non_video()
        self.emit(f"like_video {uid} {vid}")

    def coin(self, valid: bool = True) -> None:
        uid, vid = self._watched_non_uploader_pair()
        if uid is None or vid is None:
            self.watch(True)
            return
        amount = self.rng.choice([1, 2])
        if valid:
            if self.coins[uid] < amount:
                self.emit(f"add_user_coins {uid} {amount + 2}")
                self.coins[uid] += amount + 2
        else:
            pick = self.rng.random()
            if pick < 0.2:
                uid = self.non_user()
            elif pick < 0.4:
                vid = self.non_video()
            elif pick < 0.6:
                uid = self.videos[vid][0]
            elif pick < 0.8:
                amount = 3
            else:
                self.coins[uid] = 0
        if self.emit(f"coin_video {uid} {vid} {amount}") and uid in self.users and vid in self.videos and self.videos[vid][0] != uid and vid in self.watched[uid] and amount in (1, 2) and self.coins[uid] >= amount:
            self.coins[uid] -= amount
            self.coins[self.videos[vid][0]] += amount

    def forward(self, valid: bool = True) -> None:
        uid, vid = self._watched_non_uploader_pair()
        if uid is None or vid is None:
            self.watch(True)
            return
        if self.followers[uid]:
            follower = self.rng.choice(list(self.followers[uid]))
        else:
            follower = self.existing_user() or uid
            if follower != uid:
                self.following[follower].add(uid)
                self.followers[uid].add(follower)
        if not valid:
            pick = self.rng.random()
            if pick < 0.2:
                uid = self.non_user()
            elif pick < 0.4:
                follower = self.non_user()
            elif pick < 0.6:
                vid = self.non_video()
            elif pick < 0.8 and uid in self.watched:
                self.watched[uid].discard(vid)
            else:
                candidates = [u for u in self.users if u not in self.followers.get(uid, set())]
                if candidates:
                    follower = self.rng.choice(candidates)
        self.emit(f"forward_video {uid} {vid} {follower}")

    def comment(self, valid: bool = True) -> None:
        uid = self.existing_user()
        vid = self.existing_video()
        if uid is None or vid is None:
            self.upload(True)
            return
        cid = self.next_comment
        self.next_comment += 1
        body = self.rng.choice(["great", "spam", "aaaa", "clean", "x_y_z"])
        if not valid:
            pick = self.rng.random()
            if pick < 0.2:
                uid = self.non_user()
            elif pick < 0.4:
                vid = self.non_video()
            elif pick < 0.7 and self.comments.get(vid):
                cid = self.rng.choice(list(self.comments[vid]))
            else:
                uid = self.non_user()
        if self.emit(f"send_comment {uid} {vid} {cid} {body}") and uid in self.users and vid in self.videos and cid not in self.comments[vid]:
            self.comments[vid].add(cid)

    def clean(self, valid: bool = True) -> None:
        vid = self.existing_video()
        if vid is None:
            self.upload(True)
            return
        if not valid:
            vid = self.non_video()
        keyword = self.rng.choice(["spam", "aa", "clean"])
        self.emit(f"clean_spam_comments {vid} {keyword}")

    def purchase(self, valid: bool = True) -> None:
        uid, vid = self._non_uploader_pair()
        if uid is None or vid is None:
            self.upload(True)
            return
        amount = self.rng.randint(1, 8)
        if valid and self.coins[uid] < amount:
            self.emit(f"add_user_coins {uid} {amount + 5}")
            self.coins[uid] += amount + 5
        elif not valid:
            pick = self.rng.random()
            if pick < 0.2:
                uid = self.non_user()
            elif pick < 0.4:
                vid = self.non_video()
            elif pick < 0.6:
                uid = self.videos[vid][0]
            elif pick < 0.8:
                self.coins[uid] = 0
        if self.emit(f"purchase_medal {uid} {vid} {amount}") and uid in self.users and vid in self.videos and uid != self.videos[vid][0] and self.coins[uid] >= amount:
            self.coins[uid] -= amount
            self.coins[self.videos[vid][0]] += amount

    def query(self) -> None:
        op = self.rng.choice([
            "query_received_unwatched_videos", "query_up_followers_age_ratio",
            "query_mutual_following_sum", "query_shortest_path",
            "query_best_contributor", "query_most_popular_video", "queryLongestDecSeq",
        ])
        if op in {"query_mutual_following_sum", "queryLongestDecSeq"}:
            self.emit(op)
        elif op == "query_shortest_path":
            a = self.existing_user() if self.rng.random() > 0.1 else self.non_user()
            b = self.existing_user() if self.rng.random() > 0.1 else self.non_user()
            if a is not None and b is not None:
                self.emit(f"{op} {a} {b}")
        elif op == "query_most_popular_video":
            typ = self.rng.choice(TYPES)
            self.emit(f"{op} {typ}")
        else:
            uid = self.existing_user() if self.rng.random() > 0.1 else self.non_user()
            if uid is not None:
                self.emit(f"{op} {uid}")

    def _non_uploader_pair(self) -> Tuple[Optional[int], Optional[int]]:
        if not self.users or not self.videos:
            return None, None
        vid = self.existing_video()
        assert vid is not None
        candidates = [u for u in self.users if u != self.videos[vid][0]]
        if not candidates:
            return None, None
        return self.rng.choice(candidates), vid

    def _watched_non_uploader_pair(self) -> Tuple[Optional[int], Optional[int]]:
        uid, vid = self._non_uploader_pair()
        if uid is None or vid is None:
            return None, None
        self.watched[uid].add(vid)
        return uid, vid

    def build(self) -> List[str]:
        for _ in range(self.rng.randint(8, 30)):
            self.add_user(True)
        for _ in range(self.rng.randint(3, 10)):
            self.upload(True)
        while len(self.lines) < self.max_lines:
            pick = self.rng.random()
            valid = self.rng.random() > 0.20
            if pick < 0.08:
                self.add_user(valid)
            elif pick < 0.14:
                self.add_user_coins(valid)
            elif pick < 0.26:
                self.follow(valid)
            elif pick < 0.32:
                self.unfollow(valid)
            elif pick < 0.42:
                self.upload(valid)
            elif pick < 0.52:
                self.watch(valid)
            elif pick < 0.61:
                self.like(valid)
            elif pick < 0.70:
                self.coin(valid)
            elif pick < 0.78:
                self.forward(valid)
            elif pick < 0.86:
                self.comment(valid)
            elif pick < 0.91:
                self.clean(valid)
            elif pick < 0.95:
                self.purchase(valid)
            else:
                self.query()
        return self.lines[: self.max_lines]


def generate_all(out_dir: str, random_count: int, base_seed: Optional[int] = None, max_lines: int = 3000) -> List[str]:
    files: List[str] = []
    seen = set()
    for name, lines in _load_fixed_cases_from_dir() + _builtin_fixed_cases():
        if name in seen:
            continue
        seen.add(name)
        _write_case(out_dir, name, lines[:MAX_COMMANDS])
        files.append(name)
    for i in range(max(0, random_count)):
        seed = (base_seed + i) if base_seed is not None else None
        builder = CaseBuilder(seed, max_lines=max(1, min(MAX_COMMANDS, max_lines)))
        filename = f"h10_random_{i + 1:02d}.txt"
        _write_case(out_dir, filename, builder.build())
        files.append(filename)
    return files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate HW10 testcases")
    parser.add_argument("--out", default="data_hw10")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260515)
    parser.add_argument("--max-lines", type=int, default=3000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    files = generate_all(args.out, args.count, args.seed, args.max_lines)
    print(f"Generated {len(files)} files in '{args.out}':")
    for name in files:
        print(f"  - {name}")


if __name__ == "__main__":
    main()
