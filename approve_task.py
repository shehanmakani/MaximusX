from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path


OUTPUT_DIR = Path(__file__).resolve().parent / "autonomous_outputs"
ALLOWED_COMMAND_PREFIXES = {
    ("git", "status"),
    ("git", "log"),
}


def _task_path(task_id: str) -> Path:
    return OUTPUT_DIR / f"task_{task_id}.json"


def execute_staged_task(task_id: str) -> dict:
    path = _task_path(task_id)
    if not path.exists():
        raise FileNotFoundError(f"Task not found: {task_id}")

    task = json.loads(path.read_text(encoding="utf-8"))
    execution = task.get("execution") or {}
    result = {"task_id": task_id, "status": "approved_noop", "details": "No executable action attached."}

    if execution.get("type") == "command":
        command = execution.get("command") or []
        prefix = tuple(command[:2])
        if prefix not in ALLOWED_COMMAND_PREFIXES:
            raise ValueError(f"Command is not allowlisted: {shlex.join(command)}")
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        result = {
            "task_id": task_id,
            "status": "approved_executed",
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    elif execution.get("type") == "write_file":
        target = Path(execution["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(execution.get("content", ""), encoding="utf-8")
        result = {
            "task_id": task_id,
            "status": "approved_executed",
            "written_to": str(target),
        }

    task["status"] = result["status"]
    task["approval_result"] = result
    path.write_text(json.dumps(task, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python approve_task.py <task_id>")
    print(json.dumps(execute_staged_task(sys.argv[1]), indent=2))
