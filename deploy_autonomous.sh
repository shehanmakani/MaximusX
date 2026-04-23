#!/bin/bash

# 1. Start the Maximus-X services
docker compose up -d

# 2. Start the Autonomous Predictor on the Jetson
# (Runs in the background)
python3 autonomous_agent.py &

# 3. Start the WhatsApp Bridge on the Pi
# (Make sure ngrok is also running)
python3 whatsapp_bridge.py &

echo "Maximus-X Clone is now operating 24/7."
