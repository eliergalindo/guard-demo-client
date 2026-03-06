"""
LangGraph StateGraph for multi-agent orchestration with Lakera Guard.

This graph implements the following flow:

    ┌──────────────┐
    │ Input Guard   │  ← Lakera: prompt injection, jailbreak
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │   Router      │  ← LLM intent classification
    └──┬───┬───┬───┘
       │   │   │   └─────────────┐
       ▼   ▼   ▼                 ▼
     RAG  Tool  PII           General
     Agent Agent Agent         Agent
       │   │   │                 │
       └───┴───┴─────────┬──────┘
                          ▼
                  ┌───────────────┐
                  │ Output Guard   │  ← Lakera: content mod, PII leak
                  └───────┬───────┘
                          ▼
                       Response
"""
import time
from typing import TypedDict, Literal, List, Dict, Any, Optional, Annotated
from langgraph.graph import StateGraph, END

from .agents.input_guard import run_input_guard
from .agents.router import classify_intent
from .agents.rag_agent import run_rag_agent
from .agents.tool_agent import run_tool_agent
from .agents.pii_agent import run_pii_agent
from .agents.general_agent import run_general_agent
from .agents.output_guard import run_output_guard
from . import rag, toolhive


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class GraphState(TypedDict, total=False):
    """Shared state flowing through the graph."""
    # --- Inputs (set once at start) ---
    message: str
    session_id: Optional[str]
    system_prompt: Optional[str]
    model: str
    temperature: float
    lakera_api_key: Optional[str]
    lakera_project_id: Optional[str]
    lakera_blocking_mode: bool
    db: Any  # SQLAlchemy Session (not serialisable, passed by ref)

    # --- Intermediate ---
    route: str  # "rag" | "tool" | "pii" | "general"
    agent_response: str
    citations: List[Dict[str, Any]]
    tool_traces: List[Dict[str, Any]]

    # --- Lakera results ---
    input_guard_result: Dict[str, Any]
    output_guard_result: Dict[str, Any]

    # --- Graph trace (for frontend) ---
    graph_trace: List[Dict[str, Any]]

    # --- Final ---
    final_response: str
    blocked: bool


# ---------------------------------------------------------------------------
# Helper to append trace entries
# ---------------------------------------------------------------------------

def _append_trace(state: dict, node: str, status: str, detail: Optional[str] = None, lakera_flagged: Optional[bool] = None) -> List[Dict[str, Any]]:
    """Return a new graph_trace list with the appended entry."""
    trace = list(state.get("graph_trace", []))
    entry: Dict[str, Any] = {
        "node": node,
        "status": status,
        "timestamp": time.time(),
    }
    if detail is not None:
        entry["detail"] = detail
    if lakera_flagged is not None:
        entry["lakera_flagged"] = lakera_flagged
    trace.append(entry)
    return trace


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

async def input_guard_node(state: dict) -> dict:
    """Screen user input with Lakera Guard."""
    result = await run_input_guard(
        message=state["message"],
        session_id=state.get("session_id"),
        lakera_api_key=state.get("lakera_api_key"),
        lakera_project_id=state.get("lakera_project_id"),
        lakera_blocking_mode=state.get("lakera_blocking_mode", False),
        system_prompt=state.get("system_prompt"),
    )

    flagged = result.get("flagged", False)
    status = "blocked" if result.get("blocked") else ("flagged" if flagged else "passed")

    return {
        "input_guard_result": result,
        "blocked": result.get("blocked", False),
        "final_response": result.get("blocked_response") or "",
        "graph_trace": _append_trace(state, "input_guard", status, lakera_flagged=flagged),
    }


async def router_node(state: dict) -> dict:
    """Classify intent and pick agent route."""
    db = state.get("db")
    has_tools = bool(toolhive.openai_tools_manifest(db)) if db else False

    # Quick check if there's RAG content
    try:
        test_results = await rag.retrieve(state["message"], top_k=1)
        has_rag = bool(test_results)
    except Exception:
        has_rag = False

    route = await classify_intent(
        message=state["message"],
        has_rag_content=has_rag,
        has_tools=has_tools,
        model=state.get("model", "gpt-4o-mini"),
    )

    return {
        "route": route,
        "graph_trace": _append_trace(state, "router", "routed", detail=route),
    }


async def rag_agent_node(state: dict) -> dict:
    """RAG-based knowledge Q&A."""
    result = await run_rag_agent(
        message=state["message"],
        system_prompt=state.get("system_prompt"),
        model=state.get("model", "gpt-4o"),
        temperature=state.get("temperature", 0.7),
    )
    return {
        "agent_response": result["response"],
        "citations": result.get("citations", []),
        "tool_traces": [],
        "graph_trace": _append_trace(
            state, "rag_agent", "completed",
            detail=f"{result.get('rag_chunks_used', 0)} chunks used",
        ),
    }


async def tool_agent_node(state: dict) -> dict:
    """MCP tool execution."""
    result = await run_tool_agent(
        message=state["message"],
        system_prompt=state.get("system_prompt"),
        model=state.get("model", "gpt-4o"),
        temperature=state.get("temperature", 0.7),
        db=state.get("db"),
        lakera_api_key=state.get("lakera_api_key"),
        lakera_project_id=state.get("lakera_project_id"),
        lakera_blocking_mode=state.get("lakera_blocking_mode", False),
    )
    return {
        "agent_response": result["response"],
        "citations": result.get("citations", []),
        "tool_traces": result.get("tool_traces", []),
        "graph_trace": _append_trace(
            state, "tool_agent", "completed",
            detail=f"{len(result.get('tool_traces', []))} tools called",
        ),
    }


async def pii_agent_node(state: dict) -> dict:
    """PII-aware response generation."""
    result = await run_pii_agent(
        message=state["message"],
        system_prompt=state.get("system_prompt"),
        model=state.get("model", "gpt-4o"),
        temperature=state.get("temperature", 0.7),
    )
    return {
        "agent_response": result["response"],
        "citations": result.get("citations", []),
        "tool_traces": [],
        "graph_trace": _append_trace(state, "pii_agent", "completed", detail=result.get("pii_context")),
    }


async def general_agent_node(state: dict) -> dict:
    """General conversational response."""
    result = await run_general_agent(
        message=state["message"],
        system_prompt=state.get("system_prompt"),
        model=state.get("model", "gpt-4o"),
        temperature=state.get("temperature", 0.7),
    )
    return {
        "agent_response": result["response"],
        "citations": result.get("citations", []),
        "tool_traces": [],
        "graph_trace": _append_trace(state, "general_agent", "completed"),
    }


async def output_guard_node(state: dict) -> dict:
    """Screen assistant output with Lakera Guard."""
    result = await run_output_guard(
        user_message=state["message"],
        assistant_response=state.get("agent_response", ""),
        session_id=state.get("session_id"),
        lakera_api_key=state.get("lakera_api_key"),
        lakera_project_id=state.get("lakera_project_id"),
        lakera_blocking_mode=state.get("lakera_blocking_mode", False),
        system_prompt=state.get("system_prompt"),
    )

    flagged = result.get("flagged", False)
    status = "blocked" if result.get("blocked") else ("flagged" if flagged else "passed")

    return {
        "output_guard_result": result,
        "final_response": result["final_response"],
        "blocked": result.get("blocked", False),
        "graph_trace": _append_trace(state, "output_guard", status, lakera_flagged=flagged),
    }


# ---------------------------------------------------------------------------
# Conditional edges
# ---------------------------------------------------------------------------

def should_continue_after_input_guard(state: dict) -> str:
    """If input was blocked, skip to END. Otherwise route."""
    if state.get("blocked"):
        return "end"
    return "router"


def route_to_agent(state: dict) -> str:
    """Pick agent based on router classification."""
    route = state.get("route", "general")
    return {
        "rag": "rag_agent",
        "tool": "tool_agent",
        "pii": "pii_agent",
        "general": "general_agent",
    }.get(route, "general_agent")


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """Construct and compile the LangGraph StateGraph."""
    graph = StateGraph(GraphState)

    # Add nodes
    graph.add_node("input_guard", input_guard_node)
    graph.add_node("router", router_node)
    graph.add_node("rag_agent", rag_agent_node)
    graph.add_node("tool_agent", tool_agent_node)
    graph.add_node("pii_agent", pii_agent_node)
    graph.add_node("general_agent", general_agent_node)
    graph.add_node("output_guard", output_guard_node)

    # Entry point
    graph.set_entry_point("input_guard")

    # Conditional: input_guard → router or END
    graph.add_conditional_edges(
        "input_guard",
        should_continue_after_input_guard,
        {"router": "router", "end": END},
    )

    # Conditional: router → one of the agents
    graph.add_conditional_edges(
        "router",
        route_to_agent,
        {
            "rag_agent": "rag_agent",
            "tool_agent": "tool_agent",
            "pii_agent": "pii_agent",
            "general_agent": "general_agent",
        },
    )

    # All agents → output_guard
    graph.add_edge("rag_agent", "output_guard")
    graph.add_edge("tool_agent", "output_guard")
    graph.add_edge("pii_agent", "output_guard")
    graph.add_edge("general_agent", "output_guard")

    # output_guard → END
    graph.add_edge("output_guard", END)

    return graph.compile()


# Module-level compiled graph (singleton)
agent_graph = build_graph()
