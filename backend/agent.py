"""
Agent orchestrator — delegates to LangGraph multi-agent pipeline.

The graph runs: input_guard → router → [rag|tool|pii|general] → output_guard
Each node demonstrates a different Lakera Guard security protection.
"""
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from .models import AppConfig, ChatMessageRecord
from .graph import agent_graph


class AgentRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class AgentResult(BaseModel):
    response: str
    citations: List[Dict[str, Any]] = []
    tool_traces: List[Dict[str, Any]] = []
    lakera_status: Optional[Dict[str, Any]] = None
    graph_trace: List[Dict[str, Any]] = []


async def run_agent(req: AgentRequest, cfg: AppConfig, db: Session) -> AgentResult:
    """
    Run the LangGraph multi-agent pipeline.

    The graph handles:
    1. Input Guard   — Lakera pre-check (prompt injection, jailbreak)
    2. Router        — LLM intent classification
    3. Agent         — One of: RAG, Tool, PII, or General
    4. Output Guard  — Lakera post-check (content mod, PII leak)
    """
    lakera_api_key = cfg.lakera_api_key if cfg.lakera_enabled else None
    lakera_project_id = cfg.lakera_project_id if cfg.lakera_enabled else None
    lakera_blocking_mode = cfg.lakera_blocking_mode if cfg.lakera_enabled else False

    # Load conversation history from DB for multi-turn context
    conversation_history: List[Dict[str, str]] = []
    if req.session_id:
        past_messages = (
            db.query(ChatMessageRecord)
            .filter(ChatMessageRecord.session_id == req.session_id)
            .order_by(ChatMessageRecord.id.asc())
            .all()
        )
        conversation_history = [
            {"role": msg.role, "content": msg.content}
            for msg in past_messages
        ]

    initial_state = {
        "message": req.message,
        "session_id": req.session_id,
        "conversation_history": conversation_history,
        "system_prompt": cfg.system_prompt,
        "model": cfg.openai_model or "gpt-4o",
        "temperature": cfg.temperature,
        "lakera_api_key": lakera_api_key,
        "lakera_project_id": lakera_project_id,
        "lakera_blocking_mode": lakera_blocking_mode,
        "db": db,
        # Defaults for intermediate state
        "route": "general",
        "agent_response": "",
        "citations": [],
        "tool_traces": [],
        "input_guard_result": {},
        "output_guard_result": {},
        "graph_trace": [],
        "final_response": "",
        "blocked": False,
    }

    try:
        # Run the compiled graph
        final_state = await agent_graph.ainvoke(initial_state)

        # Determine which lakera_status to surface (prefer output guard, fall back to input)
        lakera_status = None
        output_guard = final_state.get("output_guard_result", {})
        input_guard = final_state.get("input_guard_result", {})

        if output_guard.get("lakera_result"):
            lakera_status = output_guard["lakera_result"]
        elif input_guard.get("lakera_result"):
            lakera_status = input_guard["lakera_result"]

        return AgentResult(
            response=final_state.get("final_response", ""),
            citations=final_state.get("citations", []),
            tool_traces=final_state.get("tool_traces", []),
            lakera_status=lakera_status,
            graph_trace=final_state.get("graph_trace", []),
        )

    except Exception as e:
        print(f"Graph execution error: {e}")
        return AgentResult(
            response=f"I apologize, but I encountered an error: {str(e)}",
            citations=[],
            tool_traces=[],
            lakera_status=None,
            graph_trace=[{"node": "error", "status": "failed", "detail": str(e)}],
        )
