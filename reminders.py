"""
Maximus-X Sentinel — Reminders Module
=======================================
Stores reminders as Qdrant points with a scheduled_at payload.
A background cron worker polls every minute and fires due reminders
back through OpenClaw to the user's preferred channel.
"""

import os
import time
import logging
import threading
from datetime import datetime, timedelta
from dateutil import parser as dateparser
import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, Range
from langchain_ollama import OllamaEmbeddings

logger = logging.getLogger("reminders")

QDRANT_URL = os.getenv("VECTOR_DB_URL", "http://localhost:6333")
OLLAMA_HOST = os.getenv("MODEL_HOST", "http://localhost:11434")
OPENCLAW_URL = os.getenv("OPENCLAW_URL", "http://host.docker.internal:3001")
REMINDER_COLLECTION = "maximus_reminders"

# ── Setup ────────────────────────────────────────────────────────────────────

def get_qdrant():
    return QdrantClient(url=QDRANT_URL)

def ensure_reminder_collection():
    from qdrant_client.models import VectorParams, Distance
    client = get_qdrant()
    existing = [c.name for c in client.get_collections().collections]
    if REMINDER_COLLECTION not in existing:
        client.create_collection(
            collection_name=REMINDER_COLLECTION,
            vectors_config=VectorParams(size=1, distance=Distance.COSINE),  # dummy vector
        )

# ── Parse natural language time ───────────────────────────────────────────────

def parse_when(when_str: str) -> datetime:
    """
    Parse natural language time strings.
    Examples: 'in 2 hours', 'tomorrow 9am', '2026-04-01 10:00', 'friday 3pm'
    """
    now = datetime.now()
    when_lower = when_str.lower().strip()

    # Handle relative times
    if when_lower.startswith("in "):
        parts = when_lower[3:].split()
        if len(parts) >= 2:
            try:
                amount = int(parts[0])
                unit = parts[1].rstrip("s")
                if unit in ("minute", "min"):
                    return now + timedelta(minutes=amount)
                elif unit in ("hour", "hr"):
                    return now + timedelta(hours=amount)
                elif unit == "day":
                    return now + timedelta(days=amount)
                elif unit == "week":
                    return now + timedelta(weeks=amount)
            except ValueError:
                pass

    # Fallback to dateutil
    try:
        return dateparser.parse(when_str, fuzzy=True)
    except Exception:
        return now + timedelta(hours=1)  # default: 1 hour from now

# ── Store reminder ────────────────────────────────────────────────────────────

def schedule_reminder(message: str, when: str, user_id: str = "default", channel: str = "telegram") -> str:
    """Schedule a reminder. Called by the Schedule sub-agent tool."""
    ensure_reminder_collection()
    client = get_qdrant()

    fire_at = parse_when(when)
    reminder_id = abs(hash(f"{message}{fire_at.isoformat()}")) % (2**63)

    client.upsert(
        collection_name=REMINDER_COLLECTION,
        points=[
            PointStruct(
                id=reminder_id,
                vector=[0.0],              # dummy — we don't do semantic search on reminders
                payload={
                    "message": message,
                    "fire_at": fire_at.isoformat(),
                    "user_id": user_id,
                    "channel": channel,
                    "fired": False,
                },
            )
        ],
    )

    time_str = fire_at.strftime("%A %b %d at %-I:%M %p")
    logger.info(f"Reminder scheduled: '{message}' at {time_str}")
    return f"Reminder set for {time_str}: {message}"

# ── Poll and fire ─────────────────────────────────────────────────────────────

def fire_reminder(reminder_id: int, message: str, user_id: str, channel: str):
    """Send the reminder via OpenClaw."""
    try:
        resp = httpx.post(
            f"{OPENCLAW_URL}/send",
            json={
                "channel": channel,
                "user_id": user_id,
                "text": f"⏰ Reminder: {message}",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info(f"Reminder fired: {message}")
        else:
            logger.warning(f"OpenClaw send failed: {resp.status_code}")
    except Exception as e:
        logger.error(f"Failed to fire reminder: {e}")

def poll_reminders():
    """Check for due reminders every 60 seconds."""
    ensure_reminder_collection()
    client = get_qdrant()

    while True:
        try:
            now_iso = datetime.now().isoformat()
            results, _ = client.scroll(
                collection_name=REMINDER_COLLECTION,
                scroll_filter=Filter(
                    must=[FieldCondition(key="fired", match={"value": False})]
                ),
                limit=50,
                with_payload=True,
            )

            for point in results:
                payload = point.payload
                fire_at_str = payload.get("fire_at", "")
                if fire_at_str and fire_at_str <= now_iso:
                    fire_reminder(
                        point.id,
                        payload.get("message", "Reminder"),
                        payload.get("user_id", "default"),
                        payload.get("channel", "telegram"),
                    )
                    # Mark as fired
                    client.set_payload(
                        collection_name=REMINDER_COLLECTION,
                        payload={"fired": True},
                        points=[point.id],
                    )
        except Exception as e:
            logger.error(f"Reminder poll error: {e}")

        time.sleep(60)

# ── Start background thread ───────────────────────────────────────────────────

def start_reminder_worker():
    """Start the reminder polling thread. Call from app startup."""
    t = threading.Thread(target=poll_reminders, daemon=True)
    t.start()
    logger.info("Reminder worker started.")
