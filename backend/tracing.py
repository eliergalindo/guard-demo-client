"""
LangSmith observability integration for the Agentic Demo.

Provides tracing for:
- Agent orchestration (run_agent)
- RAG retrieval
- OpenAI LLM calls
- Lakera Guard checks
- Tool executions
"""
import os
import functools
from typing import Optional, Callable, Any

# Try to import langsmith; gracefully degrade if not installed
try:
    from langsmith import traceable, Client
    from langsmith.run_trees import RunTree
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False

_client: Optional[Any] = None
_enabled: bool = False


def configure(api_key: Optional[str], project: Optional[str], enabled: bool = False):
    """
    Configure LangSmith tracing at runtime.
    Called whenever the app config is loaded/updated.
    """
    global _client, _enabled

    if not LANGSMITH_AVAILABLE:
        _enabled = False
        return

    _enabled = enabled and bool(api_key)

    if _enabled:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = api_key or ""
        os.environ["LANGCHAIN_PROJECT"] = project or "guard-demo"
        try:
            _client = Client(api_key=api_key)
        except Exception as e:
            print(f"LangSmith client init error: {e}")
            _enabled = False
    else:
        os.environ.pop("LANGCHAIN_TRACING_V2", None)
        os.environ.pop("LANGCHAIN_API_KEY", None)
        os.environ.pop("LANGCHAIN_PROJECT", None)
        _client = None


def is_enabled() -> bool:
    return _enabled and LANGSMITH_AVAILABLE


def trace(name: str, run_type: str = "chain", metadata: Optional[dict] = None):
    """
    Decorator that wraps a function with LangSmith tracing when enabled.
    Falls back to a no-op when tracing is disabled or langsmith is unavailable.

    Args:
        name: The name for the trace span.
        run_type: One of "chain", "llm", "tool", "retriever".
        metadata: Optional metadata dict attached to the trace.
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            if is_enabled():
                traced_fn = traceable(name=name, run_type=run_type, metadata=metadata or {})(fn)
                return await traced_fn(*args, **kwargs)
            return await fn(*args, **kwargs)

        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):
            if is_enabled():
                traced_fn = traceable(name=name, run_type=run_type, metadata=metadata or {})(fn)
                return traced_fn(*args, **kwargs)
            return fn(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(fn):
            return async_wrapper
        return sync_wrapper

    return decorator
