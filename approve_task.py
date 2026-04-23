import sys
import json
import os

def execute_staged_task(task_id):
    path = f"./autonomous_outputs/task_{task_id}.json"
    
    if not os.path.exists(path):
        print("Task not found.")
        return

    with open(path, 'r') as f:
        task = json.load(f)

    print(f"Executing: {task['action']}")
    
    # Logic for specific actions
    if task['action'] == "git_push":
        subprocess.run(["git", "add", "."])
        subprocess.run(["git", "commit", "-m", f"Auto-update: {task['summary']}"])
        subprocess.run(["git", "push"])
    
    elif task['action'] == "email":
        # Call your existing MaximusX email module
        pass

    # Mark as completed
    os.rename(path, path.replace("pending", "completed"))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        execute_staged_task(sys.argv[1])
