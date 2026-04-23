from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from activity_logger import log_activity
from morning_digest import build_morning_digest


WORKSPACE_ROOT = Path(__file__).resolve().parent
SLEEP_STATE_PATH = WORKSPACE_ROOT / "memory" / "sleep_state.json"


def exit_sleep_mode() -> dict:
    session = {}
    if SLEEP_STATE_PATH.exists():
        session = json.loads(SLEEP_STATE_PATH.read_text(encoding="utf-8"))
        session["status"] = "awake"
        session["woken_at"] = datetime.now().isoformat(timespec="seconds")
        SLEEP_STATE_PATH.write_text(json.dumps(session, indent=2), encoding="utf-8")

    digest = build_morning_digest()
    log_activity(
        "wake_mode",
        "Exited overnight autonomous mode and generated morning digest",
        {"pending_count": digest["pending_count"], "executed_count": digest["executed_count"]},
    )
    return {"session": session, "digest": digest}


def main() -> None:
    parser = argparse.ArgumentParser(description="Exit sleep mode and print the morning digest.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = exit_sleep_mode()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result["digest"]["digest"])


if __name__ == "__main__":
    main()
