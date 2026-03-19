"""
Maximus-X Sentinel — FastAPI Server
=====================================
Exposes /chat endpoint consumed by OpenClaw webhook.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from app.agent import run_agent
from app.reminders import start_reminder_worker
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("maximus-x")

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_reminder_worker()
    logger.info("Maximus-X Sentinel online.")
    yield

app = FastAPI(
    title="Maximus-X Sentinel",
    description="Private GPU-accelerated multi-agent AI assistant",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to your Mac IP in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request/Response models ────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    user_id: str = "default"
    channel: str = "api"          # telegram, whatsapp, signal, discord, api

class ChatResponse(BaseModel):
    reply: str
    agent_used: str = "supervisor"
    channel: str

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "online", "model": "llama3.2:3b", "version": "2.0.0"}

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Main endpoint — receives messages from OpenClaw, returns agent reply."""
    try:
        logger.info(f"[{req.channel}] user={req.user_id} msg={req.message[:80]}...")
        reply = run_agent(req.message, user_id=req.user_id, channel=req.channel)
        return ChatResponse(reply=reply, channel=req.channel)
    except Exception as e:
        logger.error(f"Agent error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents")
def list_agents():
    return {
        "agents": {
            "research":  ["find", "search", "what is", "explain", "summarize"],
            "chembiz":   ["chemrich", "intelliform", "formulation", "lead", "pricing"],
            "home":      ["lights", "temperature", "lock", "sensor", "scene"],
            "schedule":  ["remind", "calendar", "meeting", "when", "schedule"],
        }
    }

@app.get("/reminders")
def list_reminders():
    from app.reminders import get_qdrant, REMINDER_COLLECTION
    from qdrant_client.models import Filter, FieldCondition
    client = get_qdrant()
    results, _ = client.scroll(
        collection_name=REMINDER_COLLECTION,
        scroll_filter=Filter(must=[FieldCondition(key="fired", match={"value": False})]),
        limit=50, with_payload=True,
    )
    return {"pending": [p.payload for p in results]}
