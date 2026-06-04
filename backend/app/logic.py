from __future__ import annotations

import heapq
from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

from app.models import Draw
from app.schemas import CandidateOut, FilterConfig


RED_RANGE = range(1, 34)
BLUE_RANGE = range(1, 17)


@dataclass(frozen=True)
class RedCandidate:
    score: float
    reds: tuple[int, ...]


def ac_value(reds: tuple[int, ...] | list[int]) -> int:
    ordered = sorted(reds)
    diffs = {
        ordered[j] - ordered[i]
        for i in range(len(ordered))
        for j in range(i + 1, len(ordered))
    }
    return len(diffs) - (len(ordered) - 1)


def consecutive_summary(reds: Iterable[int]) -> dict[str, object]:
    ordered = sorted(reds)
    runs: list[list[int]] = []
    current = [ordered[0]]
    for number in ordered[1:]:
        if number == current[-1] + 1:
            current.append(number)
        else:
            if len(current) > 1:
                runs.append(current)
            current = [number]
    if len(current) > 1:
        runs.append(current)

    if not runs:
        return {"max_run": 1, "pair_count": 0, "text": "无"}

    return {
        "max_run": max(len(run) for run in runs),
        "pair_count": sum(len(run) - 1 for run in runs),
        "text": "、".join("-".join(f"{number:02d}" for number in run) for run in runs),
    }


def max_consecutive_run(reds: tuple[int, ...]) -> int:
    max_run = 1
    current = 1
    previous = reds[0]
    for number in reds[1:]:
        if number == previous + 1:
            current += 1
            if current > max_run:
                max_run = current
        else:
            current = 1
        previous = number
    return max_run


def same_tail_text(reds: Iterable[int]) -> str:
    tails = Counter(number % 10 for number in reds)
    repeated = [f"{tail}尾x{count}" for tail, count in sorted(tails.items()) if count >= 2]
    return "、".join(repeated) if repeated else "无"


def zone_counts(reds: Iterable[int]) -> tuple[int, int, int]:
    first = second = third = 0
    for number in reds:
        if number <= 11:
            first += 1
        elif number <= 22:
            second += 1
        else:
            third += 1
    return first, second, third


def red_mask(reds: Iterable[int]) -> int:
    mask = 0
    for number in reds:
        mask |= 1 << int(number)
    return mask


def draw_key(reds: Iterable[int], blue: int) -> str:
    return "-".join(f"{number:02d}" for number in sorted(reds)) + f"+{blue:02d}"


def build_history(draws: list[Draw]) -> dict[str, object]:
    recent30 = draws[:30]
    recent100 = draws[:100]
    all_red_masks = {red_mask(draw.reds) for draw in draws}
    all_ticket_keys = {draw_key(draw.reds, draw.blue) for draw in draws}
    latest = draws[0] if draws else None
    latest_red_mask = red_mask(latest.reds) if latest else 0

    return {
        "recent30": recent30,
        "recent100": recent100,
        "all_draws": draws,
        "red30": _red_counter(recent30),
        "red100": _red_counter(recent100),
        "blue30": _blue_counter(recent30),
        "blue100": _blue_counter(recent100),
        "all_red_masks": all_red_masks,
        "all_ticket_keys": all_ticket_keys,
        "latest_reds": set(latest.reds) if latest else set(),
        "latest_red_mask": latest_red_mask,
        "latest_blue": latest.blue if latest else None,
    }


def generate_candidates(
    draws: list[Draw], filters: FilterConfig, top_n: int, candidate_pool: int
) -> list[CandidateOut]:
    history = build_history(draws)
    required = sorted(set(filters.dan_numbers or []))
    excluded = set(filters.exclude_numbers or [])
    kill_tails = set(filters.kill_tails or [])

    if len(required) > 6:
        return []
    if any(number not in RED_RANGE for number in required):
        return []
    if required and (set(required) & excluded):
        return []
    if any(number % 10 in kill_tails for number in required):
        return []

    allowed_reds = [
        number
        for number in RED_RANGE
        if number not in excluded and number % 10 not in kill_tails
    ]
    if any(number not in allowed_reds for number in required):
        return []

    forbidden_masks = _build_history_forbidden_masks(draws, filters.history_overlap)
    heap_size = max(top_n * 8, min(candidate_pool, 2000), 200)
    red_heap: list[tuple[float, tuple[int, ...]]] = []

    need = 6 - len(required)
    for search_reds in _red_search_sets(allowed_reds, required, history, top_n, candidate_pool):
        red_heap.clear()
        optional = [number for number in search_reds if number not in required]
        for rest in combinations(optional, need):
            reds = tuple(sorted(required + list(rest)))
            if not _passes_filters(reds, filters, history, forbidden_masks):
                continue
            score = _score_red_only(reds, history)
            entry = (score, reds)
            if len(red_heap) < heap_size:
                heapq.heappush(red_heap, entry)
            elif entry > red_heap[0]:
                heapq.heapreplace(red_heap, entry)
        if len(red_heap) >= min(heap_size, max(top_n * 3, 80)):
            break

    blue_numbers = [
        number for number in BLUE_RANGE if number not in set(filters.exclude_blues or [])
    ]
    scored: list[tuple[float, tuple[int, ...], int]] = []
    for red_score, reds in red_heap:
        for blue in blue_numbers:
            if filters.reject_blue_repeat and blue == history["latest_blue"]:
                continue
            if filters.exclude_history and draw_key(reds, blue) in history["all_ticket_keys"]:
                continue
            scored.append((red_score + _score_blue_only(blue, history), reds, blue))

    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [
        _candidate_out(index, reds, blue, score, history)
        for index, (score, reds, blue) in enumerate(scored[:top_n], start=1)
    ]


def _passes_filters(
    reds: tuple[int, ...],
    filters: FilterConfig,
    history: dict[str, object],
    forbidden_masks: set[int],
) -> bool:
    red_sum = sum(reds)
    span = reds[-1] - reds[0]
    odd_count = sum(1 for number in reds if number % 2)
    even_count = 6 - odd_count

    if not filters.sum_min <= red_sum <= filters.sum_max:
        return False
    if not filters.span_min <= span <= filters.span_max:
        return False
    if filters.odd_even != "any":
        try:
            odd, even = [int(part) for part in filters.odd_even.split(":", 1)]
        except ValueError:
            return False
        if (odd_count, even_count) != (odd, even):
            return False

    mask = red_mask(reds)
    if (mask & int(history["latest_red_mask"])).bit_count() > filters.max_red_repeat:
        return False

    run = max_consecutive_run(reds)
    if filters.reject_four_consecutive and run >= 4:
        return False
    if filters.reject_three_consecutive and run >= 3:
        return False
    if not filters.allow_two_consecutive and run >= 2:
        return False
    if forbidden_masks and mask in forbidden_masks:
        return False
    if not filters.ac_min <= ac_value(reds) <= filters.ac_max:
        return False
    return True


def _red_search_sets(
    allowed_reds: list[int],
    required: list[int],
    history: dict[str, object],
    top_n: int,
    candidate_pool: int,
) -> list[list[int]]:
    required_set = set(required)
    allowed_set = set(allowed_reds)
    if len(allowed_reds) <= 24:
        return [allowed_reds]

    width = 24
    if top_n >= 50 or candidate_pool >= 5000:
        width = 27
    if top_n >= 100 or candidate_pool >= 50000:
        width = 29
    width = min(len(allowed_reds), max(width, len(required_set) + 16))

    prioritized = sorted(
        allowed_reds,
        key=lambda number: (
            number in required_set,
            _single_red_priority(number, history),
            -number,
        ),
        reverse=True,
    )
    first_pass = sorted((set(prioritized[:width]) | required_set) & allowed_set)
    if len(first_pass) == len(allowed_reds):
        return [first_pass]
    return [first_pass, allowed_reds]


def _single_red_priority(number: int, history: dict[str, object]) -> float:
    red30: Counter[int] = history["red30"]
    red100: Counter[int] = history["red100"]
    max30 = max(red30.values(), default=1)
    max100 = max(red100.values(), default=1)
    hot30 = red30[number] / max30 if max30 else 0
    hot100 = red100[number] / max100 if max100 else 0
    cold = 1 - hot30
    latest = 1 if number in history["latest_reds"] else 0
    return hot30 * 14.0 + hot100 * 10.5 + cold * 7.0 + latest * 7.0


def _build_history_forbidden_masks(draws: list[Draw], mode: str) -> set[int]:
    if mode == "none" or not draws:
        return set()

    exact = {red_mask(draw.reds) for draw in draws}
    if mode == "exact":
        return exact
    if mode != "similar5":
        return exact

    forbidden = set(exact)
    all_reds = set(RED_RANGE)
    for draw in draws:
        draw_reds = tuple(draw.reds)
        replacements = all_reds - set(draw_reds)
        for five_numbers in combinations(draw_reds, 5):
            five_mask = red_mask(five_numbers)
            for replacement in replacements:
                forbidden.add(five_mask | (1 << replacement))
    return forbidden


def _candidate_out(
    rank: int,
    reds: tuple[int, ...],
    blue: int,
    score: float,
    history: dict[str, object],
) -> CandidateOut:
    zones = zone_counts(reds)
    consecutive = consecutive_summary(reds)
    red_repeat = len(set(reds) & history["latest_reds"])
    blue_repeat = history["latest_blue"] == blue
    odd_count = sum(number % 2 for number in reds)
    reasons = [
        f"和值{sum(reds)}",
        f"跨度{reds[-1] - reds[0]}",
        f"奇偶{odd_count}:{6 - odd_count}",
        f"三区{zones[0]}:{zones[1]}:{zones[2]}",
        f"AC{ac_value(reds)}",
    ]
    return CandidateOut(
        rank=rank,
        reds=list(reds),
        blue=blue,
        score=round(score, 2),
        sum_value=sum(reds),
        span=reds[-1] - reds[0],
        odd_even=f"{odd_count}:{6 - odd_count}",
        zone_ratio=f"{zones[0]}:{zones[1]}:{zones[2]}",
        ac_value=ac_value(reds),
        red_repeat=red_repeat,
        blue_repeat=blue_repeat,
        consecutive=str(consecutive["text"]),
        same_tail=same_tail_text(reds),
        reasons=reasons,
    )


def _red_counter(draws: list[Draw]) -> Counter[int]:
    counter: Counter[int] = Counter()
    for draw in draws:
        counter.update(draw.reds)
    return counter


def _blue_counter(draws: list[Draw]) -> Counter[int]:
    counter: Counter[int] = Counter()
    for draw in draws:
        counter.update([draw.blue])
    return counter


def _score_red_only(reds: tuple[int, ...], history: dict[str, object]) -> float:
    return round(
        _hot_score(reds, history["red30"], len(history["recent30"]), 14.0)
        + _hot_score(reds, history["red100"], len(history["recent100"]), 10.5)
        + _cold_red_score(reds, history["red30"], 7.0)
        + _odd_even_score(reds, 8.0)
        + _zone_score(reds, 8.0)
        + _sum_score(reds, 12.0)
        + _span_score(reds, 8.0)
        + _consecutive_score(reds, 7.0)
        + _ac_score(reds, 8.0)
        + _same_tail_score(reds, 5.0)
        + _last_red_score(reds, history["latest_reds"], 7.0),
        6,
    )


def _score_blue_only(blue: int, history: dict[str, object]) -> float:
    return round(
        _single_hot_score(blue, history["blue30"], len(history["recent30"]), 2.0)
        + _single_hot_score(blue, history["blue100"], len(history["recent100"]), 1.5)
        + _cold_blue_score(blue, history["blue30"], 1.0)
        + _last_blue_score(blue, history["latest_blue"], 1.0),
        6,
    )


def _hot_score(
    numbers: Iterable[int], counter: Counter[int], draw_count: int, weight: float
) -> float:
    if draw_count == 0:
        return weight * 0.62
    max_count = max(counter.values(), default=0)
    if max_count == 0:
        return weight * 0.62
    normalized = sum(counter[number] / max_count for number in numbers) / 6
    return weight * normalized


def _single_hot_score(
    number: int, counter: Counter[int], draw_count: int, weight: float
) -> float:
    if draw_count == 0:
        return weight * 0.62
    max_count = max(counter.values(), default=0)
    if max_count == 0:
        return weight * 0.62
    return weight * (counter[number] / max_count)


def _cold_red_score(numbers: Iterable[int], counter: Counter[int], weight: float) -> float:
    if not counter:
        return weight * 0.6
    counts = [counter[number] for number in RED_RANGE]
    cutoff = sorted(counts)[min(9, len(counts) - 1)]
    cold_hits = sum(1 for number in numbers if counter[number] <= cutoff)
    score_map = {0: 0.45, 1: 1.0, 2: 0.9, 3: 0.55, 4: 0.25, 5: 0.1, 6: 0.05}
    return weight * score_map.get(cold_hits, 0.1)


def _cold_blue_score(blue: int, counter: Counter[int], weight: float) -> float:
    if not counter:
        return weight * 0.6
    counts = [counter[number] for number in BLUE_RANGE]
    cutoff = sorted(counts)[min(4, len(counts) - 1)]
    return weight if counter[blue] <= cutoff else weight * 0.35


def _odd_even_score(numbers: Iterable[int], weight: float) -> float:
    odd_count = sum(1 for number in numbers if number % 2)
    score_map = {3: 1.0, 2: 0.88, 4: 0.88, 1: 0.48, 5: 0.48, 0: 0.18, 6: 0.18}
    return weight * score_map[odd_count]


def _zone_score(numbers: Iterable[int], weight: float) -> float:
    zones = zone_counts(numbers)
    if zones == (2, 2, 2):
        return weight
    if max(zones) <= 3 and min(zones) >= 1:
        return weight * 0.86
    if max(zones) == 4:
        return weight * 0.48
    return weight * 0.22


def _sum_score(numbers: Iterable[int], weight: float) -> float:
    return _band_score(sum(numbers), low=60, ideal_low=86, ideal_high=115, high=140) * weight


def _span_score(numbers: Iterable[int], weight: float) -> float:
    ordered = sorted(numbers)
    return _band_score(ordered[-1] - ordered[0], low=12, ideal_low=20, ideal_high=29, high=32) * weight


def _consecutive_score(numbers: Iterable[int], weight: float) -> float:
    summary = consecutive_summary(numbers)
    if int(summary["max_run"]) >= 4:
        return weight * 0.08
    if int(summary["max_run"]) == 3:
        return weight * 0.28
    if int(summary["pair_count"]) == 1:
        return weight
    if int(summary["pair_count"]) == 0:
        return weight * 0.78
    return weight * 0.55


def _ac_score(numbers: Iterable[int], weight: float) -> float:
    ac = ac_value(tuple(numbers))
    if ac in (7, 8, 9):
        return weight
    if ac in (6, 10):
        return weight * 0.82
    if ac in (5, 11):
        return weight * 0.56
    return weight * 0.25


def _same_tail_score(numbers: Iterable[int], weight: float) -> float:
    tail_counts = Counter(number % 10 for number in numbers)
    max_tail = max(tail_counts.values())
    repeated_groups = sum(1 for count in tail_counts.values() if count >= 2)
    if max_tail == 1:
        return weight * 0.86
    if max_tail == 2 and repeated_groups <= 2:
        return weight
    if max_tail == 2:
        return weight * 0.72
    if max_tail == 3:
        return weight * 0.32
    return weight * 0.1


def _last_red_score(numbers: Iterable[int], latest_reds: set[int], weight: float) -> float:
    if not latest_reds:
        return weight * 0.62
    overlap = len(set(numbers) & latest_reds)
    score_map = {0: 0.72, 1: 1.0, 2: 0.9, 3: 0.45, 4: 0.15, 5: 0.05, 6: 0.0}
    return weight * score_map[overlap]


def _last_blue_score(blue: int, latest_blue: int | None, weight: float) -> float:
    if latest_blue is None:
        return weight * 0.62
    return weight * (0.25 if blue == latest_blue else 1.0)


def _band_score(value: int, low: int, ideal_low: int, ideal_high: int, high: int) -> float:
    if value < low or value > high:
        return 0.08
    if ideal_low <= value <= ideal_high:
        return 1.0
    if value < ideal_low:
        return 0.08 + 0.92 * ((value - low) / max(1, ideal_low - low))
    return 0.08 + 0.92 * ((high - value) / max(1, high - ideal_high))
