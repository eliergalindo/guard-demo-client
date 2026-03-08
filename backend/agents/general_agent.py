"""
General Agent Node — Default conversational agent.

Handles general chat messages that don't require specialized routing.
Still protected by input and output Lakera guards, demonstrating
baseline content moderation on all interactions.
"""
from typing import List, Dict, Any, Optional
from .. import rag
from ..openai_client import openai_client


async def run_general_agent(
    message: str,
    system_prompt: Optional[str],
    model: str = "gpt-4o",
    temperature: float = 0.7,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Handle general conversation with RAG context if available.

    Returns:
        {
            "response": str,
            "citations": [...],
        }
    """
    context = await rag.retrieve(message)
    citations = []
    if context:
        citations = [
            {"source": doc.get("metadata", {}).get("source")}
            for doc in context
            if doc.get("metadata", {}).get("source")
            and doc.get("metadata", {}).get("source") != "unknown"
        ]

    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if context:
        context_text = "\n\n".join([doc["text"] for doc in context])
        messages.append({"role": "system", "content": f"Context information:\n{context_text}"})
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": message})

    try:
        openai_client._load_config()
        response = openai_client.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
        )
        response_text = response["choices"][0]["message"]["content"]
    except Exception as e:
        response_text = f"I apologize, but I encountered an error: {str(e)}"

    return {
        "response": response_text,
        "citations": citations,
    }
