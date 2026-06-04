from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from itertools import combinations

from app.models import Draw
from app.schemas import CandidateOut, FilterConfig


@dataclass(frozen=True)
class Candidate:
    reds: tuple[int, ...]
    blue: int

    @property
    def key(self) -> str:
        return "-".join(f"{n:02d}" for n in self.reds) + f"+{self.blue:02d}"


def ac_value(reds: tuple[int, ...] | list[int]) -> int:
    diffs = {abs(a - b) for a, b in combinations(sorted(reds), 2)}
    return len(diffs) - (len(reds) - 1)


def max_consecutive_run(reds: tuple[int, ...] | list[int]) -> int:
    ordered = sorted(reds)
    best = current = 1
    for previous, value in zip(ordered, ordered[1:]):
        if value == previous + 1:
            current += 1
            best = max(best, current)
        else:
            current = 1
    return best


def draw_key(reds: list[int], blue: int) -> str:
    return "-".join(f"{n:02d}" for n in sorted(reds)) + f"+{blue:02d}"


def build_history(draws: list[Draw]) -> dict[str, object]:
    red_frequency: Counter[int] = Counter()
    blue_frequency: Counter[int] = Counter()
    history_keys: set[str] = set()

    for draw in draws:
        red_frequency.update(draw.reds)
        blue_frequency.update([draw.blue])
        history_keys.add(draw_key(draw.reds, draw.blue))

    latest = draws[0] if draws else None
    return {
        "red_frequency": red_frequency,
        "blue_frequency": blue_frequency,
        "history_keys": history_keys,
        "latest_reds": set(latest.reds) if latest else set(),
        "latest_blue": latest.blue if latest else None,
        "total": len(draws),
    }


def passes_filters(candidate: Candidate, filters: FilterConfig, history: dict[str, object]) -> tuple[bool, dict[str, object]]:
    red_sum = sum(candidate.reds)
    ac = ac_value(candidate.reds)
    run = max_consecutive_run(candidate.reds)
    latest_reds = history["latest_reds"]
    latest_blue = history["latest_blue"]
    red_repeat = len(set(candidate.reds) & latest_reds)
    blue_repeat = latest_blue == candidate.blue

    if filters.exclude_history and candidate.key in history["history_keys"]:
        return False, {}
    if filters.reject_four_consecutive and run >= 4:
        return False, {}
    if filters.reject_three_consecutive and run == 3:
        return False, {}
    if not filters.sum_min <= red_sum <= filters.sum_max:
        return False, {}
    if not filters.ac_min <= ac <= filters.ac_max:
        return False, {}
    if red_repeat > filters.max_red_repeat:
        return False, {}
    if filters.reject_blue_repeat and blue_repeat:
        return False, {}

    return True, {
        "sum_value": red_sum,
        "ac_value": ac,
        "red_repeat": red_repeat,
        "blue_repeat": blue_repeat,
        "run": run,
    }


def _frequency_score(values: tuple[int, ...], frequency: Counter[int], total_draws: int, expected: float) -> float:
    if total_draws == 0:
        return 50.0
    scores = []
    for value in values:
        ratio = frequency[value] / max(total_draws, 1)
        distance = abs(ratio - expected)
        scores.append(max(0.0, 100.0 - distance * 480.0))
    return sum(scores) / len(scores)


def score_candidate(candidate: Candidate, history: dict[str, object], metrics: dict[str, object]) -> tuple[float, list[str]]:
    reds = candidate.reds
    red_frequency = history["red_frequency"]
    blue_frequency = history["blue_frequency"]
    total = int(history["total"])

    freq = _frequency_score(reds, red_frequency, total, expected=6 / 33)
    blue_freq = _frequency_score((candidate.blue,), blue_frequency, total, expected=1 / 16)

    odd_count = sum(n % 2 for n in reds)
    odd_even = max(0.0, 100.0 - abs(odd_count - 3) * 18.0)

    zones = [sum(1 for n in reds if 1 <= n <= 11), sum(1 for n in reds if 12 <= n <= 22), sum(1 for n in reds if 23 <= n <= 33)]
    zone_score = max(0.0, 100.0 - sum(abs(v - 2) for v in zones) * 14.0)

    sum_score = max(0.0, 100.0 - abs(int(metrics["sum_value"]) - 100) * 1.4)
    ac_score = max(0.0, 100.0 - abs(int(metrics["ac_value"]) - 9) * 9.0)
    repeat_score = max(0.0, 100.0 - int(metrics["red_repeat"]) * 18.0 - (12.0 if metrics["blue_repeat"] else 0.0))
    consecutive_score = max(0.0, 100.0 - max(0, int(metrics["run"]) - 1) * 16.0)

    score = (
        freq * 0.24
        + blue_freq * 0.08
        + odd_even * 0.12
        + zone_score * 0.14
        + sum_score * 0.16
        + ac_score * 0.14
        + repeat_score * 0.08
        + consecutive_score * 0.04
    )

    reasons = [
        f"红球频率{freq:.1f}",
        f"奇偶{odd_count}:{6 - odd_count}",
        f"三区分布{zones[0]}-{zones[1]}-{zones[2]}",
        f"和值{metrics['sum_value']}",
        f"AC{metrics['ac_value']}",
    ]
    return round(score, 2), reasons


def generate_candidates(draws: list[Draw], filters: FilterConfig, top_n: int, candidate_pool: int) -> list[CandidateOut]:
    history = build_history(draws)
    rng = random.SystemRandom()
    seen: set[str] = set()
    scored: list[tuple[float, Candidate, dict[str, object], list[str]]] = []
    attempts = 0
    max_attempts = candidate_pool * 8

    while len(seen) < candidate_pool and attempts < max_attempts:
        attempts += 1
        candidate = Candidate(tuple(sorted(rng.sample(range(1, 34), 6))), rng.randint(1, 16))
        if candidate.key in seen:
            continue
        passed, metrics = passes_filters(candidate, filters, history)
        if not passed:
            continue
        seen.add(candidate.key)
        score, reasons = score_candidate(candidate, history, metrics)
        scored.append((score, candidate, metrics, reasons))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        CandidateOut(
            rank=index + 1,
            reds=list(candidate.reds),
            blue=candidate.blue,
            score=score,
            sum_value=int(metrics["sum_value"]),
            ac_value=int(metrics["ac_value"]),
            red_repeat=int(metrics["red_repeat"]),
            blue_repeat=bool(metrics["blue_repeat"]),
            reasons=reasons,
        )
        for index, (score, candidate, metrics, reasons) in enumerate(scored[:top_n])
    ]
