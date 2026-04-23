from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ReasoningLens:
    name: str
    question: str
    weight: float


LENSES = (
    ReasoningLens("strategic", "Which option creates the most long-term leverage?", 1.0),
    ReasoningLens("practical", "Which option is most executable tonight with low friction?", 0.9),
    ReasoningLens("protective", "Which option avoids costly mistakes or premature execution?", 0.8),
    ReasoningLens("identity", "Which option best matches how the user would want to operate?", 1.0),
)


class ReasoningLoop:
    def __init__(self, profile: str, principles: list[str] | None = None):
        self.profile = profile
        self.principles = principles or [
            "Prefer high-leverage work over busywork.",
            "Do preparation, drafting, research, and organization overnight.",
            "Do not finalize irreversible external actions without approval.",
            "Adapt to current goals instead of copying yesterday literally.",
        ]

    def deliberate(self, candidates: list[dict[str, Any]], learned_patterns: dict[str, Any] | None = None) -> dict[str, Any]:
        learned_patterns = learned_patterns or {}
        critiques = []
        scored = []

        for candidate in candidates:
            lens_scores = {}
            reasons = []
            total = 0.0
            for lens in LENSES:
                score, reason = self._score_candidate(candidate, lens, learned_patterns)
                lens_scores[lens.name] = score
                reasons.append(f"{lens.name}: {reason}")
                total += score * lens.weight

            critique = self._critique(candidate)
            if critique:
                reasons.append(f"critique: {critique}")
                total -= 0.12

            scored.append(
                {
                    "candidate": candidate,
                    "composite_score": round(total, 3),
                    "lens_scores": lens_scores,
                    "reasons": reasons,
                }
            )
            if critique:
                critiques.append({"id": candidate.get("id"), "critique": critique})

        scored.sort(key=lambda item: item["composite_score"], reverse=True)
        winner = scored[0] if scored else None
        return {
            "winner": winner,
            "ranked_options": scored,
            "critiques": critiques,
            "principles": self.principles,
        }

    def _score_candidate(
        self,
        candidate: dict[str, Any],
        lens: ReasoningLens,
        learned_patterns: dict[str, Any],
    ) -> tuple[float, str]:
        urgency = float(candidate.get("urgency", 0.5))
        impact = float(candidate.get("impact", 0.5))
        effort = float(candidate.get("effort", 0.5))
        risk = float(candidate.get("risk", 0.5))
        source = candidate.get("source", "")
        title = (candidate.get("title") or "").lower()
        top_keywords = learned_patterns.get("top_keywords", [])

        if lens.name == "strategic":
            score = impact * 0.7 + urgency * 0.2 + (1 - effort) * 0.1
            return round(score, 3), "prioritizes leverage and future payoff"
        if lens.name == "practical":
            score = (1 - effort) * 0.45 + urgency * 0.35 + (1 - risk) * 0.2
            return round(score, 3), "favors work that can actually get done overnight"
        if lens.name == "protective":
            score = (1 - risk) * 0.65 + (0.2 if candidate.get("execution") is None else 0.0)
            return round(score, 3), "rewards reversible and lower-risk actions"

        identity_bonus = 0.0
        if source in {"calendar", "planner", "repo", "code"}:
            identity_bonus += 0.15
        if any(keyword in title for keyword in top_keywords[:6]):
            identity_bonus += 0.15
        score = impact * 0.35 + urgency * 0.2 + identity_bonus + (1 - risk) * 0.2
        return round(score, 3), "matches the user's recurring style and priorities"

    def _critique(self, candidate: dict[str, Any]) -> str | None:
        execution = candidate.get("execution")
        source = candidate.get("source", "")
        if execution and execution.get("type") == "command":
            return "requires command execution, so approval and tighter policy checks are needed"
        if source == "planner" and not execution:
            return "planner-generated work is useful, but still abstract until grounded in current artifacts"
        if float(candidate.get("risk", 0.0)) > 0.7:
            return "risk is too high for unattended autonomous execution"
        return None
