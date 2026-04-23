from __future__ import annotations

import argparse
import json
from pathlib import Path


OUTPUT_DIR = Path(__file__).resolve().parent / "autonomous_outputs"


def build_morning_digest() -> dict:
    tasks = []
    for path in sorted(OUTPUT_DIR.glob("task_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        tasks.append(payload)

    pending = [task for task in tasks if task.get("status") == "pending_approval"]
    executed = [task for task in tasks if task.get("status") == "approved_executed"]

    summary_lines = []
    for task in pending:
        task_title = ((task.get("recommended_task") or {}).get("title")) or task.get("summary", "Pending task")
        reasoning = ((task.get("reasoning") or {}).get("winner") or {}).get("reasons", [])
        reason_text = reasoning[0] if reasoning else "awaiting review"
        summary_lines.append(
            f"PENDING [{task.get('id')}]: {task_title} (confidence {task.get('confidence')}) | {reason_text}"
        )
    for task in executed:
        task_title = ((task.get("recommended_task") or {}).get("title")) or task.get("summary", "Executed task")
        summary_lines.append(f"READY [{task.get('id')}]: {task_title}")

    return {
        "pending_count": len(pending),
        "executed_count": len(executed),
        "tasks": tasks,
        "digest": "\n".join(summary_lines) if summary_lines else "No overnight tasks available.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Show the overnight approval digest.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    digest = build_morning_digest()
    if args.json:
        print(json.dumps(digest, indent=2))
    else:
        print(digest["digest"])


if __name__ == "__main__":
    main()
