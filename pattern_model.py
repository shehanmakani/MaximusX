from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any


class PatternModel:
    def __init__(self, activities: list[dict[str, Any]]):
        self.activities = activities

    def fit(self) -> dict[str, Any]:
        event_counter: Counter[str] = Counter()
        hour_counter: dict[str, Counter[int]] = defaultdict(Counter)
        repo_dirty_frequency: Counter[str] = Counter()
        keywords: Counter[str] = Counter()

        for item in self.activities:
            event_type = item.get("event_type", "unknown")
            event_counter[event_type] += 1
            timestamp = item.get("timestamp")
            hour = _safe_hour(timestamp)
            hour_counter[event_type][hour] += 1

            metadata = item.get("metadata", {})
            repo = metadata.get("repo")
            status = metadata.get("status", [])
            if repo and status:
                repo_dirty_frequency[repo] += 1

            for token in _tokenize(item.get("summary", "")):
                keywords[token] += 1

        dominant_hours = {
            event_type: counter.most_common(2)
            for event_type, counter in hour_counter.items()
        }
        return {
            "event_counter": dict(event_counter),
            "dominant_hours": dominant_hours,
            "repo_dirty_frequency": dict(repo_dirty_frequency),
            "top_keywords": [word for word, _ in keywords.most_common(15)],
        }

    def score_candidate(self, candidate: dict[str, Any]) -> float:
        patterns = self.fit()
        score = 0.0
        source = candidate.get("source", "")
        if source in {"repo", "code"} and patterns["event_counter"].get("repo_snapshot", 0):
            score += 0.12
        if source == "calendar" and patterns["event_counter"].get("meeting_prep", 0):
            score += 0.12
        repo_path = ((candidate.get("execution") or {}).get("command") or ["", "", ""])[2:3]
        if repo_path:
            dirty = patterns["repo_dirty_frequency"].get(repo_path[0], 0)
            score += min(0.18, dirty * 0.03)
        title = (candidate.get("title") or "").lower()
        if any(word in title for word in patterns["top_keywords"][:5]):
            score += 0.08
        return round(score, 3)


def _safe_hour(timestamp: str | None) -> int:
    if not timestamp:
        return datetime.now().hour
    try:
        return datetime.fromisoformat(timestamp).hour
    except ValueError:
        return datetime.now().hour


def _tokenize(text: str) -> list[str]:
    tokens = []
    for raw in text.lower().split():
        token = "".join(ch for ch in raw if ch.isalnum() or ch in {"-", "_"})
        if len(token) >= 4:
            tokens.append(token)
    return tokens
