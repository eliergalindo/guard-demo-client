"""
RAG Agent Node — Knowledge Q&A with indirect injection protection.

Handles knowledge questions by retrieving context from ChromaDB and
generating answers. Demonstrates Lakera's ability to detect:
- Indirect prompt injection hidden in retrieved documents
- Content moderation on RAG-sourced material
- Data poisoning in knowledge base
"""
import json
from typing import List, Dict, Any, Optional
from .. import rag
from ..openai_client import openai_client


async def run_rag_agent(
    message: str,
    system_prompt: Optional[str],
    model: str = "gpt-4o",
    temperature: float = 0.7,
) -> Dict[str, Any]:
    """
    Retrieve context from RAG and generate an answer.

    Returns:
        {
            "response": str,
            "citations": [...],
            "rag_chunks_used": int,
        }
    """
    # Step 1: Retrieve relevant context
    context = await rag.retrieve(message)
    citations = []
    if context:
        citations = [
            {"source": doc.get("metadata", {}).get("source")}
            for doc in context
            if doc.get("metadata", {}).get("source")
            and doc.get("metadata", {}).get("source") != "unknown"
        ]

    # Step 2: Build messages
    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    if context:
        context_text = "\n\n".join([doc["text"] for doc in context])
        messages.append({
            "role": "system",
            "content": f"Context information:\n{context_text}",
        })

    messages.append({"role": "user", "content": message})

    # Step 3: Call LLM
    try:
        openai_client._load_config()
        response = openai_client.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
        )
        response_text = response["choices"][0]["message"]["content"]
    except Exception as e:
        response_text = f"I apologize, but I encountered an error retrieving information: {str(e)}"

    return {
        "response": response_text,
        "citations": citations,
        "rag_chunks_used": len(context) if context else 0,
    }
