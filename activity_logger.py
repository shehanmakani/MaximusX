from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parent
MEMORY_DIR = WORKSPACE_ROOT / "memory"
ACTIVITY_LOG = MEMORY_DIR / "activity_log.jsonl"


def ensure_memory_dir() -> None:
    MEMORY_DIR.mkdir(exist_ok=True)


def log_activity(event_type: str, summary: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    ensure_memory_dir()
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "event_type": event_type,
        "summary": summary,
        "metadata": metadata or {},
    }
    with ACTIVITY_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
    return entry


def read_recent_activity(limit: int = 200) -> list[dict[str, Any]]:
    if not ACTIVITY_LOG.exists():
        return []
    lines = ACTIVITY_LOG.read_text(encoding="utf-8").splitlines()
    entries = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def capture_repo_activity(repo_paths: list[str]) -> list[dict[str, Any]]:
    captured = []
    for repo in repo_paths:
        repo_path = Path(repo)
        if not (repo_path / ".git").exists():
            continue
        status = _run(["git", "-C", str(repo_path), "status", "--short"])
        latest = _run(["git", "-C", str(repo_path), "log", "--oneline", "-n", "3"])
        summary = f"Observed repo {repo_path.name}: {'dirty' if status else 'clean'} working tree"
        entry = log_activity(
            "repo_snapshot",
            summary,
            metadata={
                "repo": str(repo_path),
                "status": status.splitlines(),
                "recent_commits": latest.splitlines(),
            },
        )
        captured.append(entry)
    return captured


def _run(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Log daytime activity for overnight learning.")
    parser.add_argument("--event-type", default="manual_note")
    parser.add_argument("--summary")
    parser.add_argument("--repo", action="append", default=[])
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    if args.repo:
        captured = capture_repo_activity(args.repo)
        print(json.dumps(captured, indent=2))
        return

    if args.show:
        print(json.dumps(read_recent_activity(), indent=2))
        return

    if not args.summary:
        raise SystemExit("Provide --summary or use --repo/--show.")

    print(json.dumps(log_activity(args.event_type, args.summary), indent=2))


if __name__ == "__main__":
    main()
