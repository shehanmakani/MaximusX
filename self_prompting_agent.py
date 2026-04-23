from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from future_self_bridge import FutureSelfBridge


@dataclass
class CandidateTask:
    id: str
    title: str
    description: str
    source: str
    urgency: float
    impact: float
    effort: float
    risk: float
    deadline: str | None = None
    execution: dict[str, Any] | None = None


class SelfPromptingAgent:
    def __init__(self, profile: str, workspace_root: str | None = None):
        self.profile = profile
        self.workspace_root = Path(workspace_root or Path(__file__).resolve().parent)
        self.outputs_dir = self.workspace_root / "autonomous_outputs"
        self.outputs_dir.mkdir(exist_ok=True)
        self.bridge = FutureSelfBridge()

    def build_context(
        self,
        calendar_path: str | None,
        repo_paths: list[str],
        additional_candidates: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        tasks = []
        if calendar_path:
            tasks.extend(self._calendar_candidates(Path(calendar_path)))
        for repo_path in repo_paths:
            tasks.extend(self._repo_candidates(Path(repo_path)))
        for candidate in additional_candidates or []:
            if isinstance(candidate, dict):
                tasks.append(
                    CandidateTask(
                        id=candidate.get("id", f"candidate-{len(tasks)+1}"),
                        title=candidate.get("title", "Untitled candidate"),
                        description=candidate.get("description", ""),
                        source=candidate.get("source", "planner"),
                        urgency=float(candidate.get("urgency", 0.5)),
                        impact=float(candidate.get("impact", 0.5)),
                        effort=float(candidate.get("effort", 0.5)),
                        risk=float(candidate.get("risk", 0.5)),
                        deadline=candidate.get("deadline"),
                        execution=candidate.get("execution"),
                    )
                )

        context = {
            "current_time": datetime.now().isoformat(timespec="seconds"),
            "candidate_tasks": [asdict(task) for task in tasks],
        }
        return context

    def predict_and_stage(
        self,
        calendar_path: str | None,
        repo_paths: list[str],
        additional_candidates: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        context = self.build_context(calendar_path, repo_paths, additional_candidates=additional_candidates)
        recommendation = self.bridge.recommend_next_action(self.profile, context)
        staged = self.stage_recommendation(recommendation, context)
        return staged

    def stage_recommendation(self, recommendation: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        task = recommendation.get("recommended_task")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        payload = {
            "id": timestamp,
            "created_at": context["current_time"],
            "profile": self.profile,
            "status": "pending_approval",
            "confidence": recommendation.get("confidence", 0.0),
            "summary": recommendation.get("summary", ""),
            "recommended_task": task,
            "execution": (task or {}).get("execution"),
            "futures": recommendation.get("futures", []),
            "candidate_count": len(context.get("candidate_tasks", [])),
        }
        output_path = self.outputs_dir / f"task_{timestamp}.json"
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        payload["path"] = str(output_path)
        return payload

    def _calendar_candidates(self, calendar_path: Path) -> list[CandidateTask]:
        if not calendar_path.exists():
            return []
        events = json.loads(calendar_path.read_text(encoding="utf-8"))
        candidates = []
        now = datetime.now()
        for index, event in enumerate(events, start=1):
            start = _safe_parse_datetime(event.get("start"))
            hours_until = max(0.0, (start - now).total_seconds() / 3600) if start else 48.0
            urgency = 1.0 if hours_until <= 6 else 0.8 if hours_until <= 24 else 0.55
            title = event.get("title", f"Event {index}")
            prep = event.get("prep_task") or f"Prepare materials for {title}"
            candidates.append(
                CandidateTask(
                    id=f"calendar-{index}",
                    title=prep,
                    description=event.get("description", f"Upcoming event: {title}"),
                    source="calendar",
                    urgency=urgency,
                    impact=float(event.get("impact", 0.8)),
                    effort=float(event.get("effort", 0.5)),
                    risk=float(event.get("risk", 0.3)),
                    deadline=event.get("start"),
                    execution={
                        "type": "write_file",
                        "path": str(self.outputs_dir / f"{title.lower().replace(' ', '_')}_brief.md"),
                        "content": f"# {prep}\n\n- Event: {title}\n- Start: {event.get('start')}\n",
                    },
                )
            )
        return candidates

    def _repo_candidates(self, repo_path: Path) -> list[CandidateTask]:
        if not repo_path.exists():
            return []
        candidates = []
        git_dir = repo_path / ".git"
        if git_dir.exists():
            status = _run_command(["git", "-C", str(repo_path), "status", "--porcelain"])
            if status:
                candidates.append(
                    CandidateTask(
                        id=f"repo-{repo_path.name}-review",
                        title=f"Review and summarize pending changes in {repo_path.name}",
                        description="Uncommitted work exists and should be turned into a clear summary or next-step plan.",
                        source="repo",
                        urgency=0.72,
                        impact=0.78,
                        effort=0.35,
                        risk=0.2,
                        execution={
                            "type": "command",
                            "command": ["git", "-C", str(repo_path), "status", "--short"],
                        },
                    )
                )

            recent = _run_command(["git", "-C", str(repo_path), "log", "--oneline", "-n", "1"])
            if recent:
                candidates.append(
                    CandidateTask(
                        id=f"repo-{repo_path.name}-next-step",
                        title=f"Decide the next high-leverage step for {repo_path.name}",
                        description=f"Latest commit: {recent.splitlines()[0]}",
                        source="code",
                        urgency=0.6,
                        impact=0.85,
                        effort=0.4,
                        risk=0.25,
                        execution={
                            "type": "command",
                            "command": ["git", "-C", str(repo_path), "log", "--oneline", "-n", "5"],
                        },
                    )
                )
        return candidates


def _safe_parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _run_command(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description="Predict and stage the next autonomous task.")
    parser.add_argument("--profile", default="Shehan: founder, engineer, builder")
    parser.add_argument("--calendar", help="Path to a JSON file of upcoming events")
    parser.add_argument("--repo", action="append", default=[], help="Repository path to scan; may be repeated")
    parser.add_argument("--workspace-root", help="Override MaximusX workspace root")
    args = parser.parse_args()

    agent = SelfPromptingAgent(profile=args.profile, workspace_root=args.workspace_root)
    staged = agent.predict_and_stage(args.calendar, args.repo)
    print(json.dumps(staged, indent=2))


if __name__ == "__main__":
    main()
