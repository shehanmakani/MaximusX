from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import subprocess

app = Flask(__name__)

# Replace with your Jetson's local IP and SSH user
JETSON_SSH = "shehan@192.168.1.100" 

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '').lower().strip()
    resp = MessagingResponse()
    msg = resp.message()

    if incoming_msg == 'go':
        # Trigger the execution script on the Jetson
        try:
            cmd = f"ssh {JETSON_SSH} 'python3 ~/MaximusX/execute_staged.py'"
            subprocess.run(cmd, shell=True, check=True)
            msg.body("🚀 Execution started on Jetson. I'll notify you when finished.")
        except Exception as e:
            msg.body(f"⚠️ Error triggering Jetson: {str(e)}")
            
    elif incoming_msg == 'status':
        # Query the Jetson for what it's currently working on
        status = subprocess.check_output(f"ssh {JETSON_SSH} 'cat ~/MaximusX/current_task.txt'", shell=True)
        msg.body(f"Current Task: {status.decode()}")
    else:
        msg.body("I didn't recognize that. Send 'GO' to execute or 'STATUS' to check progress.")

    return str(resp)

if __name__ == "__main__":
    # Use ngrok to expose port 5000 to Twilio's webhook setting
    app.run(port=5000)
