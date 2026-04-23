from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from activity_logger import capture_repo_activity, log_activity
from overnight_planner import OvernightPlanner


WORKSPACE_ROOT = Path(__file__).resolve().parent
MEMORY_DIR = WORKSPACE_ROOT / "memory"
SLEEP_STATE_PATH = MEMORY_DIR / "sleep_state.json"


def enter_sleep_mode(
    profile: str,
    calendar_path: str | None,
    repo_paths: list[str],
    cycles: int,
    interval_seconds: int,
) -> dict:
    MEMORY_DIR.mkdir(exist_ok=True)
    session = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "status": "sleeping",
        "profile": profile,
        "calendar_path": calendar_path,
        "repo_paths": repo_paths,
        "cycles": [],
    }
    SLEEP_STATE_PATH.write_text(json.dumps(session, indent=2), encoding="utf-8")
    log_activity("sleep_mode_entered", "Entered overnight autonomous mode", {"repo_paths": repo_paths})
    capture_repo_activity(repo_paths)

    planner = OvernightPlanner(profile=profile, workspace_root=str(WORKSPACE_ROOT))
    for cycle in range(1, cycles + 1):
        staged = planner.stage_best_task(calendar_path, repo_paths)
        cycle_record = {
            "cycle": cycle,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "staged_task_id": staged["id"],
            "summary": staged["summary"],
        }
        session["cycles"].append(cycle_record)
        SLEEP_STATE_PATH.write_text(json.dumps(session, indent=2), encoding="utf-8")
        log_activity("sleep_cycle", staged["summary"], {"task_id": staged["id"], "cycle": cycle})
        if cycle < cycles and interval_seconds > 0:
            time.sleep(interval_seconds)

    session["status"] = "awaiting_wake"
    session["finished_at"] = datetime.now().isoformat(timespec="seconds")
    SLEEP_STATE_PATH.write_text(json.dumps(session, indent=2), encoding="utf-8")
    return session


def main() -> None:
    parser = argparse.ArgumentParser(description="Put MaximusX into overnight sleep mode.")
    parser.add_argument("--profile", default="Shehan: founder, engineer, builder")
    parser.add_argument("--calendar")
    parser.add_argument("--repo", action="append", default=[])
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--interval-seconds", type=int, default=0)
    args = parser.parse_args()

    result = enter_sleep_mode(
        profile=args.profile,
        calendar_path=args.calendar,
        repo_paths=args.repo,
        cycles=args.cycles,
        interval_seconds=args.interval_seconds,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
