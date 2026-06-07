from __future__ import annotations

import hashlib
import html
import re
from collections import Counter
from urllib.parse import urlparse

import requests

from app.models import ExpertSignal


KEYWORDS = {
    "red_dan": ("红球重点", "红球胆码", "红胆", "独胆", "三胆", "重点关注", "核心红球"),
    "red_kill": ("杀红", "红球杀号", "杀一红", "杀三红", "杀六红", "杀码", "排除红球"),
    "blue_dan": ("蓝球重点", "蓝球胆码", "蓝胆", "一码定蓝", "定蓝", "蓝球看好"),
    "blue_kill": ("杀蓝", "蓝球杀号", "杀一蓝", "杀三蓝", "杀六蓝", "排除蓝球"),
    "kill_tails": ("杀尾", "毒尾", "杀尾号"),
}
ALL_SIGNAL_KEYWORDS = tuple({keyword for keywords in KEYWORDS.values() for keyword in keywords})


def compact_numbers(numbers: list[int]) -> str:
    return ",".join(str(number) for number in sorted(set(numbers)))


def parse_compact_numbers(value: str | None, min_value: int, max_value: int) -> list[int]:
    if not value:
        return []
    numbers = []
    for item in re.split(r"[\s,，、;；|/]+", value):
        if not item:
            continue
        try:
            number = int(item)
        except ValueError:
            continue
        if min_value <= number <= max_value:
            numbers.append(number)
    return sorted(set(numbers))


def content_hash(text: str, source_url: str | None = None) -> str:
    digest = hashlib.sha256()
    digest.update((source_url or "").encode("utf-8"))
    digest.update(text.encode("utf-8", errors="ignore"))
    return digest.hexdigest()


def download_expert_text(url: str) -> str:
    response = requests.get(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
            )
        },
        timeout=20,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return html_to_text(response.text)


def html_to_text(markup: str) -> str:
    markup = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", markup)
    markup = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", markup)
    text = re.sub(r"(?s)<[^>]+>", " ", markup)
    text = html.unescape(text)
    return re.sub(r"[ \t\r\f\v]+", " ", text)


def source_name_from_url(url: str) -> str:
    host = urlparse(url).netloc or url
    return host.replace("www.", "")


def parse_expert_text(text: str) -> dict[str, object]:
    clean = re.sub(r"\s+", " ", text)
    issue_match = re.search(r"20\d{5}", clean)
    return {
        "issue": issue_match.group(0) if issue_match else None,
        "red_dan": _numbers_near_keywords(clean, KEYWORDS["red_dan"], 1, 33),
        "red_kill": _numbers_near_keywords(clean, KEYWORDS["red_kill"], 1, 33),
        "blue_dan": _numbers_near_keywords(clean, KEYWORDS["blue_dan"], 1, 16),
        "blue_kill": _numbers_near_keywords(clean, KEYWORDS["blue_kill"], 1, 16),
        "kill_tails": _numbers_near_keywords(clean, KEYWORDS["kill_tails"], 0, 9),
    }


def _numbers_near_keywords(
    text: str,
    keywords: tuple[str, ...],
    min_value: int,
    max_value: int,
    window: int = 110,
) -> list[int]:
    numbers: list[int] = []
    for keyword in keywords:
        for match in re.finditer(re.escape(keyword), text):
            fragment_end = min(len(text), match.end() + window)
            for boundary in ALL_SIGNAL_KEYWORDS:
                boundary_match = re.search(re.escape(boundary), text[match.end() : fragment_end])
                if boundary_match:
                    fragment_end = min(fragment_end, match.end() + boundary_match.start())
            fragment = text[match.start() : fragment_end]
            for raw in re.findall(r"(?<!\d)(\d{1,2})(?!\d)", fragment):
                number = int(raw)
                if min_value <= number <= max_value:
                    numbers.append(number)
    return sorted(set(numbers))


def signal_to_out(signal: ExpertSignal) -> dict[str, object]:
    return {
        "id": signal.id,
        "issue": signal.issue,
        "source": signal.source,
        "source_url": signal.source_url,
        "red_dan": parse_compact_numbers(signal.red_dan, 1, 33),
        "red_kill": parse_compact_numbers(signal.red_kill, 1, 33),
        "blue_dan": parse_compact_numbers(signal.blue_dan, 1, 16),
        "blue_kill": parse_compact_numbers(signal.blue_kill, 1, 16),
        "kill_tails": parse_compact_numbers(signal.kill_tails, 0, 9),
        "weight": signal.weight,
    }


def build_consensus(signals: list[ExpertSignal]) -> dict[str, object]:
    counters: dict[str, Counter[int]] = {
        "red_dan": Counter(),
        "red_kill": Counter(),
        "blue_dan": Counter(),
        "blue_kill": Counter(),
        "kill_tails": Counter(),
    }
    ranges = {
        "red_dan": (1, 33),
        "red_kill": (1, 33),
        "blue_dan": (1, 16),
        "blue_kill": (1, 16),
        "kill_tails": (0, 9),
    }
    for signal in signals:
        for key, (min_value, max_value) in ranges.items():
            for number in parse_compact_numbers(getattr(signal, key), min_value, max_value):
                counters[key][number] += signal.weight

    def top_items(counter: Counter[int], limit: int = 12) -> list[dict[str, object]]:
        return [
            {"number": number, "weight": round(weight, 2)}
            for number, weight in counter.most_common(limit)
        ]

    return {
        "total_signals": len(signals),
        "red_dan": top_items(counters["red_dan"]),
        "red_kill": top_items(counters["red_kill"]),
        "blue_dan": top_items(counters["blue_dan"]),
        "blue_kill": top_items(counters["blue_kill"]),
        "kill_tails": top_items(counters["kill_tails"]),
    }
