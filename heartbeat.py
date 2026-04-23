import time
import requests
import subprocess

# Settings
JETSON_IP = "192.168.1.XX" # Replace with your Jetson's local IP
CHECK_INTERVAL = 3600 # 1 hour

def trigger_jetson_cycle():
    print("Waking up the Brain...")
    # Trigger the orchestrator on the Jetson via SSH
    cmd = f"ssh user@{JETSON_IP} 'python3 ~/MaximusX/autonomous_executive.py'"
    result = subprocess.check_output(cmd, shell=True)
    return result

def send_to_mobile(message):
    # Use your preferred bridge (Twilio, Bark, or simple Telegram bot)
    # Example using a simple webhook:
    print(f"NOTIFYING SHEHAN: {message}")
    # requests.post("https://api.telegram.org/botYOUR_TOKEN/sendMessage", data={"text": message})

while True:
    try:
        output = trigger_jetson_cycle()
        send_to_mobile(f"Clone Update: {output.decode()}")
    except Exception as e:
        print(f"Error in heartbeat: {e}")
    
    time.sleep(CHECK_INTERVAL)
