from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from activity_logger import read_recent_activity
from pattern_model import PatternModel
from reasoning_loop import ReasoningLoop
from self_prompting_agent import SelfPromptingAgent


class OvernightPlanner:
    def __init__(self, profile: str, workspace_root: str | None = None):
        self.agent = SelfPromptingAgent(profile=profile, workspace_root=workspace_root)
        self.reasoner = ReasoningLoop(profile=profile)

    def build_candidates(
        self,
        calendar_path: str | None,
        repo_paths: list[str],
        max_candidates: int = 6,
    ) -> dict[str, Any]:
        recent_activity = read_recent_activity()
        model = PatternModel(recent_activity)
        learned = model.fit()
        base_context = self.agent.build_context(calendar_path, repo_paths)
        ranked_candidates = []
        for candidate in base_context["candidate_tasks"]:
            learned_bonus = model.score_candidate(candidate)
            candidate["learned_bonus"] = learned_bonus
            candidate["impact"] = min(1.0, float(candidate.get("impact", 0.5)) + learned_bonus)
            ranked_candidates.append(candidate)

        ranked_candidates.sort(
            key=lambda item: (
                float(item.get("urgency", 0.0)) + float(item.get("impact", 0.0)) - float(item.get("risk", 0.0))
            ),
            reverse=True,
        )

        generated = self._generate_learned_candidates(learned, repo_paths)
        final_candidates = (generated + ranked_candidates)[:max_candidates]
        return {
            "current_time": base_context["current_time"],
            "candidate_tasks": final_candidates,
            "learned_patterns": learned,
        }

    def stage_best_task(self, calendar_path: str | None, repo_paths: list[str]) -> dict[str, Any]:
        context = self.build_candidates(calendar_path, repo_paths)
        deliberation = self.reasoner.deliberate(
            context["candidate_tasks"],
            learned_patterns=context.get("learned_patterns"),
        )
        recommendation = self._build_reasoned_recommendation(deliberation, context)
        staged = self.agent.stage_recommendation(recommendation, context)
        staged["learned_patterns"] = context["learned_patterns"]
        staged["reasoning"] = deliberation
        path = Path(staged["path"])
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["learned_patterns"] = context["learned_patterns"]
        payload["reasoning"] = deliberation
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return staged

    def _generate_learned_candidates(self, learned: dict[str, Any], repo_paths: list[str]) -> list[dict[str, Any]]:
        candidates = []
        top_keywords = learned.get("top_keywords", [])
        if "meeting" in top_keywords or "brief" in top_keywords:
            candidates.append(
                {
                    "id": "learned-night-brief",
                    "title": "Prepare tomorrow's high-priority briefing packet",
                    "description": "Learned from past behavior that meeting prep is a recurring nighttime task.",
                    "source": "planner",
                    "urgency": 0.78,
                    "impact": 0.88,
                    "effort": 0.4,
                    "risk": 0.18,
                    "execution": None,
                }
            )
        for repo in repo_paths[:2]:
            repo_name = Path(repo).name
            candidates.append(
                {
                    "id": f"learned-{repo_name}-summary",
                    "title": f"Draft an overnight summary and next-step memo for {repo_name}",
                    "description": "Recurring pattern indicates unfinished repo work should be summarized before morning.",
                    "source": "planner",
                    "urgency": 0.68,
                    "impact": 0.8,
                    "effort": 0.32,
                    "risk": 0.12,
                    "execution": {
                        "type": "write_file",
                        "path": str(Path(self.agent.outputs_dir) / f"{repo_name}_overnight_memo.md"),
                        "content": f"# Overnight memo for {repo_name}\n\n- Review today's changes\n- List next actions\n- Flag anything needing approval\n",
                    },
                }
            )
        return candidates

    def _build_reasoned_recommendation(self, deliberation: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        winner = deliberation.get("winner")
        if not winner:
            return self.agent.bridge.recommend_next_action(self.agent.profile, context)

        candidate = winner["candidate"]
        confidence = min(0.99, round(0.55 + winner["composite_score"] * 0.35, 2))
        summary = (
            f"{candidate['title']} was selected after strategic, practical, protective, "
            f"and identity-based reasoning because it best fits current context and your operating style."
        )
        return {
            "recommended_task": candidate,
            "confidence": confidence,
            "summary": summary,
            "futures": [
                {
                    "persona": "Reasoning Loop",
                    "bias": "self-critique + identity alignment",
                    "top_tasks": [
                        {
                            "id": item["candidate"]["id"],
                            "title": item["candidate"]["title"],
                            "score": item["composite_score"],
                            "reason": "; ".join(item["reasons"][:2]),
                        }
                        for item in deliberation["ranked_options"][:3]
                    ],
                }
            ],
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an overnight task queue from learned patterns.")
    parser.add_argument("--profile", default="Shehan: founder, engineer, builder")
    parser.add_argument("--calendar")
    parser.add_argument("--repo", action="append", default=[])
    parser.add_argument("--stage", action="store_true")
    args = parser.parse_args()

    planner = OvernightPlanner(profile=args.profile)
    if args.stage:
        print(json.dumps(planner.stage_best_task(args.calendar, args.repo), indent=2))
        return
    print(json.dumps(planner.build_candidates(args.calendar, args.repo), indent=2))


if __name__ == "__main__":
    main()
