import time
from twilio.rest import Client # Or use OpenClaw/Bark bridge

def notify_shehan(task_data):
    message = f"Clone Update: I've drafted the {task_data['summary']}. Reply 'GO' to execute."
    # Use your WhatsApp/iMessage API here
    print(f"SENT TO MOBILE: {message}")

while True:
    # Check Jetson's staging folder every hour
    new_tasks = check_staging_folder() # Use SSH or shared NFS mount
    for task in new_tasks:
        notify_shehan(task)
    time.sleep(3600)
