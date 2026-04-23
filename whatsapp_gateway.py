from __future__ import annotations

import json
import subprocess
from pathlib import Path

from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

from approve_task import execute_staged_task

app = Flask(__name__)

# Replace with your Jetson's local IP and SSH user
JETSON_SSH = "shehan@192.168.1.100" 
OUTPUT_DIR = Path(__file__).resolve().parent / "autonomous_outputs"


def _latest_pending_task() -> dict | None:
    tasks = sorted(OUTPUT_DIR.glob("task_*.json"))
    for path in reversed(tasks):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("status") == "pending_approval":
            return payload
    return None

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '').lower().strip()
    resp = MessagingResponse()
    msg = resp.message()

    if incoming_msg.startswith('approve'):
        try:
            parts = incoming_msg.split()
            task_id = parts[1] if len(parts) > 1 else None
            if not task_id:
                pending = _latest_pending_task()
                if not pending:
                    msg.body("No pending tasks are waiting for approval.")
                    return str(resp)
                task_id = pending["id"]
            result = execute_staged_task(task_id)
            msg.body(f"Approved {task_id}: {result['status']}")
        except Exception as e:
            msg.body(f"Approval failed: {str(e)}")
            
    elif incoming_msg == 'status':
        pending = _latest_pending_task()
        if pending:
            msg.body(
                f"Pending task {pending['id']}: {pending['recommended_task']['title']} "
                f"(confidence {pending['confidence']})"
            )
        else:
            msg.body("No pending tasks in autonomous_outputs.")
    elif incoming_msg == 'go':
        try:
            cmd = f"ssh {JETSON_SSH} 'python3 ~/MaximusX/self_prompting_agent.py'"
            subprocess.run(cmd, shell=True, check=True)
            msg.body("Prediction loop triggered on Jetson. Reply STATUS to see the latest pending task.")
        except Exception as e:
            msg.body(f"⚠️ Error triggering Jetson: {str(e)}")
    else:
        msg.body("Send GO to predict work, STATUS to see the latest task, or APPROVE <task_id> to execute.")

    return str(resp)

if __name__ == "__main__":
    # Use ngrok to expose port 5000 to Twilio's webhook setting
    app.run(port=5000)
