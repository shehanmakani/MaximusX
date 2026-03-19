"""
Maximus-X Sentinel — LangGraph Supervisor Agent
================================================
Routes incoming messages to specialized sub-agents based on intent.

Sub-agents:
  research   → web search + RAG over Context Membrane
  chembiz    → ChemRich/ChemeNova domain knowledge + business context
  home       → Home Assistant REST API
  schedule   → Google Calendar + cron reminders
"""

from typing import Literal, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import tool
from pydantic import BaseModel
import httpx
import os

# ── Model setup ───────────────────────────────────────────────────────────────

OLLAMA_HOST = os.getenv("MODEL_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

def get_llm(temperature: float = 0.1):
    return ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_HOST,
        temperature=temperature,
    )

# ── State ─────────────────────────────────────────────────────────────────────

class AgentState(BaseModel):
    messages: list
    next_agent: str = "supervisor"
    user_id: str = "default"
    channel: str = "api"           # telegram, whatsapp, signal, discord, api

# ── Routing classifier ────────────────────────────────────────────────────────

ROUTE_PROMPT = """You are a routing classifier for a personal AI assistant.
Classify the user's message into exactly ONE of these routes:

- research   : general questions, web search, "find", "what is", "explain", "summarize"
- chembiz    : anything about ChemRich, ChemeNova, IntelliForm, chemical formulation, leads, pricing, business
- home       : smart home, lights, temperature, locks, sensors, Home Assistant
- schedule   : calendar, reminders, meetings, "when is", "remind me", scheduling

Respond with ONLY the route name. No explanation."""

def classify_route(state: AgentState) -> Literal["research", "chembiz", "home", "schedule"]:
    """Supervisor: classifies intent and routes to the right sub-agent."""
    llm = get_llm(temperature=0.0)
    last_message = state.messages[-1]
    content = last_message.content if hasattr(last_message, "content") else str(last_message)

    response = llm.invoke([
        SystemMessage(content=ROUTE_PROMPT),
        HumanMessage(content=content),
    ])
    route = response.content.strip().lower()

    # Fallback to research if unrecognized
    if route not in ("research", "chembiz", "home", "schedule"):
        route = "research"

    return route

# ── Sub-agent tools ───────────────────────────────────────────────────────────

@tool
def rag_search(query: str) -> str:
    """Search the Context Membrane (personal document RAG) for relevant information."""
    from app.rag import search_context_membrane
    return search_context_membrane(query)

@tool
def home_assistant_action(entity_id: str, action: str, value: str = "") -> str:
    """Control a Home Assistant entity. Actions: turn_on, turn_off, set_temperature."""
    ha_url = os.getenv("HOME_ASSISTANT_URL")
    ha_token = os.getenv("HOME_ASSISTANT_TOKEN")
    if not ha_url or not ha_token:
        return "Home Assistant not configured. Set HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN in .env"

    domain = entity_id.split(".")[0]
    service = action
    payload = {"entity_id": entity_id}
    if value:
        payload["value"] = value

    try:
        resp = httpx.post(
            f"{ha_url}/api/services/{domain}/{service}",
            headers={"Authorization": f"Bearer {ha_token}"},
            json=payload,
            timeout=10,
        )
        return f"✓ {entity_id} → {action}" if resp.status_code == 200 else f"Error: {resp.text}"
    except Exception as e:
        return f"Home Assistant unreachable: {e}"

@tool
def chembiz_context_lookup(query: str) -> str:
    """Look up ChemRich/ChemeNova specific business and product context from RAG."""
    from app.rag import search_context_membrane
    return search_context_membrane(query, collection="chembiz")

@tool
def get_calendar_events(days_ahead: int = 7) -> str:
    """Get upcoming calendar events for the next N days."""
    # Placeholder — connect to Google Calendar API via langchain-google-calendar
    return f"[Calendar integration — set GOOGLE_CALENDAR_CREDS in .env to activate]"

@tool
def set_reminder(message: str, when: str) -> str:
    """Set a reminder. when format: 'in 2 hours', 'tomorrow 9am', '2026-04-01 10:00'"""
    # Stores to Qdrant with a scheduled_at timestamp; retrieved by cron worker
    from app.reminders import schedule_reminder
    return schedule_reminder(message, when)

# ── Sub-agents ────────────────────────────────────────────────────────────────

RESEARCH_SYSTEM = """You are the Research agent for Maximus-X, a private personal AI assistant.
You have access to the user's personal Context Membrane (RAG over their notes/docs) and can search it.
Be concise, accurate, and cite sources when available. Prefer RAG results over generic answers."""

CHEMBIZ_SYSTEM = """You are the ChemBiz agent for Maximus-X, personal assistant to Shehan — 
a chemical engineer, founder of ChemRich Global and ChemeNova LLC.
You have deep context on: ChemRich product catalog (Calcium Chloride, D-Limonene, IPA 99%, etc.),
IntelliForm™ AI formulation co-pilot, NSF I-Corps, specialty chemical industry.
Answer business and technical questions with domain precision."""

HOME_SYSTEM = """You are the Home agent for Maximus-X. You control smart home devices via Home Assistant.
Always confirm actions before executing. Report entity states clearly."""

SCHEDULE_SYSTEM = """You are the Schedule agent for Maximus-X. You manage calendar events and reminders.
Parse natural language times correctly. Confirm before creating events."""

def build_research_agent():
    return create_react_agent(get_llm(), tools=[rag_search], state_modifier=RESEARCH_SYSTEM)

def build_chembiz_agent():
    return create_react_agent(get_llm(), tools=[chembiz_context_lookup], state_modifier=CHEMBIZ_SYSTEM)

def build_home_agent():
    return create_react_agent(get_llm(), tools=[home_assistant_action], state_modifier=HOME_SYSTEM)

def build_schedule_agent():
    return create_react_agent(get_llm(), tools=[get_calendar_events, set_reminder], state_modifier=SCHEDULE_SYSTEM)

# ── Graph assembly ─────────────────────────────────────────────────────────────

def build_supervisor_graph():
    """Assemble the full LangGraph supervisor → sub-agent routing graph."""

    research_agent = build_research_agent()
    chembiz_agent = build_chembiz_agent()
    home_agent = build_home_agent()
    schedule_agent = build_schedule_agent()

    def run_research(state: dict):
        result = research_agent.invoke(state)
        return result

    def run_chembiz(state: dict):
        result = chembiz_agent.invoke(state)
        return result

    def run_home(state: dict):
        result = home_agent.invoke(state)
        return result

    def run_schedule(state: dict):
        result = schedule_agent.invoke(state)
        return result

    def supervisor_route(state: dict) -> str:
        # Wrap dict state into AgentState for typing
        agent_state = AgentState(
            messages=state["messages"],
            user_id=state.get("user_id", "default"),
            channel=state.get("channel", "api"),
        )
        return classify_route(agent_state)

    builder = StateGraph(dict)
    builder.add_node("research", run_research)
    builder.add_node("chembiz", run_chembiz)
    builder.add_node("home", run_home)
    builder.add_node("schedule", run_schedule)

    builder.add_conditional_edges(
        START,
        supervisor_route,
        {
            "research": "research",
            "chembiz": "chembiz",
            "home": "home",
            "schedule": "schedule",
        },
    )

    builder.add_edge("research", END)
    builder.add_edge("chembiz", END)
    builder.add_edge("home", END)
    builder.add_edge("schedule", END)

    return builder.compile()

# ── Singleton graph ────────────────────────────────────────────────────────────
graph = build_supervisor_graph()

def run_agent(message: str, user_id: str = "default", channel: str = "api") -> str:
    """Main entry point — invoke the supervisor graph."""
    result = graph.invoke({
        "messages": [HumanMessage(content=message)],
        "user_id": user_id,
        "channel": channel,
    })
    last = result["messages"][-1]
    return last.content if hasattr(last, "content") else str(last)
