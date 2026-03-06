"""
PII Agent Node — Data handling with PII detection.

Handles requests involving personally identifiable information.
Demonstrates Lakera's ability to detect:
- SSNs, credit card numbers, IBANs
- Email addresses, phone numbers, physical addresses
- IP addresses and other sensitive data patterns
- Data leak prevention in LLM outputs
"""
from typing import List, Dict, Any, Optional
from .. import rag
from ..openai_client import openai_client

PII_SYSTEM_ADDENDUM = """
IMPORTANT: You are a helpful assistant. When users share personal information or
ask about data handling, respond helpfully. Do NOT refuse to answer or add
excessive warnings — the security layer (Lakera Guard) handles PII detection
separately. Just respond naturally to the user's request.
"""


async def run_pii_agent(
    message: str,
    system_prompt: Optional[str],
    model: str = "gpt-4o",
    temperature: float = 0.7,
) -> Dict[str, Any]:
    """
    Handle PII-related requests. The LLM processes normally — Lakera's
    output guard will detect any PII in the response.

    Returns:
        {
            "response": str,
            "citations": [...],
            "pii_context": str,  # explanation of what PII scenario was detected
        }
    """
    # Get RAG context (may contain customer data)
    context = await rag.retrieve(message)
    citations = []
    if context:
        citations = [
            {"source": doc.get("metadata", {}).get("source")}
            for doc in context
            if doc.get("metadata", {}).get("source")
            and doc.get("metadata", {}).get("source") != "unknown"
        ]

    # Build messages
    messages: List[Dict[str, str]] = []
    base_prompt = (system_prompt or "") + "\n\n" + PII_SYSTEM_ADDENDUM
    messages.append({"role": "system", "content": base_prompt.strip()})

    if context:
        context_text = "\n\n".join([doc["text"] for doc in context])
        messages.append({
            "role": "system",
            "content": f"Context information:\n{context_text}",
        })

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
        "pii_context": "PII-related request processed. Lakera Guard will scan the output for sensitive data patterns.",
    }
