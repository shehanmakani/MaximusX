# Maximus-X Sentinel 🧠
> *A private, GPU-accelerated personal AI brain. Nobody else has built this.*

A fully local, multi-agent personal AI assistant running on **NVIDIA Jetson Orin Nano** with **Raspberry Pi 5** voice edge and **Mac** dashboard. Combines **OpenClaw** multi-channel messaging gateway, **LangGraph** agent orchestration, **Qdrant** vector memory, and **Ollama** inference — all on-premise, zero cloud, zero subscription.

---

## What Makes This Different

Most "personal AI" setups are either:
- Cloud-dependent (ChatGPT, Claude.ai, etc.) — your data leaves your machine
- Single-model chatbots — no specialization, no memory, no autonomy

**Maximus-X Sentinel** is different:

| Feature | What it does |
|---|---|
| **OpenClaw Gateway** | Talk to Maximus via WhatsApp, Telegram, Signal, Discord, iMessage — all routed to your Jetson |
| **LangGraph Supervisor** | Intelligent routing to specialized sub-agents (Research, ChemBiz, Home, Schedule) |
| **Context Membrane** | Auto-ingesting RAG layer that pulls from your local notes, emails, and docs nightly |
| **Jetson Inference Core** | GPU-accelerated local LLM — no API keys, no token costs, no privacy leaks |
| **Pi 5 Voice Edge** | Wake word + faster-whisper STT + Kokoro TTS, runs on Pi hardware |
| **Self-improving** | OpenClaw can write and install its own new skills when you ask for new capabilities |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     YOUR DEVICES                            │
│  WhatsApp / Telegram / Signal / iMessage / Discord          │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│              Mac / Laptop  (OpenClaw Gateway)               │
│  • openclaw gateway process (Node.js)                       │
│  • Open WebUI dashboard  :3000                              │
│  • Routes all channels → Jetson agent                       │
└────────────────────────┬────────────────────────────────────┘
                         │ LAN / Wi-Fi
┌────────────────────────▼────────────────────────────────────┐
│           NVIDIA Jetson Orin Nano  (AI Brain)               │
│                                                             │
│  ┌─────────────────────────────────────────────────┐        │
│  │         LangGraph Supervisor Agent              │        │
│  │   Routes to: Research | ChemBiz | Home | Sched  │        │
│  └──────────┬──────────────────────┬──────────────┘        │
│             │                      │                        │
│  ┌──────────▼──────┐    ┌──────────▼──────┐                │
│  │  Ollama (LLM)   │    │  Qdrant (RAG)   │                │
│  │  llama3.2:3b    │    │  Context Membrane│               │
│  │  GPU accel.     │    │  Auto-ingestion  │                │
│  └─────────────────┘    └─────────────────┘                │
│                                                             │
│  FastAPI server :8000 ← all agent traffic                   │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│             Raspberry Pi 5  (Voice Edge)                    │
│  • openWakeWord  (wake: "Hey Maximus")                      │
│  • faster-whisper STT (CTranslate2 backend)                 │
│  • Kokoro-82M TTS (HF TTS Arena #1, offline)                │
│  • Home/work presence triggers                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

- **Jetson Orin Nano** running JetPack 6.4+
- **NVMe SSD** strongly recommended (SD card I/O is the bottleneck for model loading)
- **Raspberry Pi 5** (4GB or 8GB)
- **Mac/Linux** laptop for OpenClaw gateway
- **Ollama** model pulled: `ollama pull llama3.2:3b`

---

## Quick Start

### 1. Clone & configure
```bash
git clone https://github.com/shehanmakani/MaximusX
cd MaximusX
cp .env.example .env
# Edit .env — set OPENCLAW_TOKEN, TELEGRAM_BOT_TOKEN, etc.
```

### 2. Start the Jetson stack
```bash
docker compose up -d
```

### 3. Start OpenClaw on Mac
```bash
npm install -g @openclaw/openclaw
openclaw init
openclaw start
```

### 4. Start voice edge on Pi
```bash
cd pi-voice
pip install -r requirements.txt
python3 voice_edge.py
```

---

## Agent Specializations

| Agent | Trigger keywords | Capabilities |
|---|---|---|
| **Research** | "find", "search", "what is", "summarize" | Web search, RAG over your docs |
| **ChemBiz** | "chemrich", "intelliform", "formulation", "lead" | Chemical domain Q&A, business context |
| **Home** | "lights", "temperature", "lock", "scene" | Home Assistant REST API |
| **Schedule** | "remind", "meeting", "calendar", "when" | Google Calendar + cron reminders |

---

## OpenClaw Skills Included

- `chembiz-context` — Loads ChemRich/ChemeNova domain knowledge into every ChemBiz query
- `nightly-ingest` — Cron job: pulls new emails/notes into Qdrant Context Membrane at 2am
- `voice-relay` — Bridges Pi STT output → OpenClaw → Jetson and back to Pi TTS
- `presence-trigger` — Detects home/work arrival via Pi sensor, fires contextual briefing

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM inference | Ollama + llama3.2:3b (Jetson GPU) |
| Agent orchestration | LangGraph + LangChain-core |
| Vector DB | Qdrant v1.13.0 (arm64) |
| Messaging gateway | OpenClaw (self-hosted) |
| Dashboard | Open WebUI |
| Voice STT | faster-whisper (CTranslate2) |
| Wake word | openWakeWord |
| TTS | Kokoro-82M |
| Container runtime | Docker + NVIDIA runtime |
| API server | FastAPI + Uvicorn |

---

## Privacy Guarantee

- Zero cloud inference — all LLM calls stay on Jetson
- OpenClaw stores config/memory as local Markdown on your Mac
- Qdrant vector data stays on Jetson NVMe
- Only outbound: your chosen messaging app (Telegram, etc.) for delivery
