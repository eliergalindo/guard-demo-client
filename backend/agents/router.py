"""
Router Node — LLM-based intent classification.

Classifies the user message into one of the available agent types so the
graph can route to the correct specialized node. This enables the demo to
show how different Lakera protections apply to different interaction types.

Routes:
- "rag"  → RAG Agent (knowledge Q&A, indirect injection demo)
- "tool" → Tool Agent (MCP tool execution, tool-output scanning demo)
- "pii"  → PII Agent (data handling, PII detection demo)
- "general" → General chat (default, still guarded by output check)
"""
from typing import List, Dict, Any, Optional
from ..openai_client import openai_client

ROUTER_SYSTEM_PROMPT = """You are a routing classifier. Given a user message, classify it into exactly ONE category.

Categories:
- "rag": The user is asking a knowledge question that requires searching documents or data. Examples: "What does our policy say about...", "Find information about...", "How many customers..."
- "tool": The user is explicitly requesting an action that requires an external tool, file operation, or API call. Examples: "List the files in...", "Create a file...", "Run a search on..."
- "pii": The user message contains, requests, or asks about personally identifiable information (names, emails, SSNs, credit cards, addresses, phone numbers). Examples: "My SSN is...", "Send this to john@example.com", "What's the customer's credit card?"
- "general": General conversation, greetings, or anything that doesn't fit the above.

Respond with ONLY the category name, nothing else. One word."""


async def classify_intent(
    message: str,
    has_rag_content: bool,
    has_tools: bool,
    model: str = "gpt-4o-mini",
    temperature: float = 0,
) -> str:
    """
    Classify user intent and return one of: "rag", "tool", "pii", "general".
    Falls back to "general" on any error.
    """
    try:
        messages = [
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ]

        response = openai_client.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
        )

        classification = response["choices"][0]["message"]["content"].strip().lower()

        # Validate the classification
        valid_routes = {"rag", "tool", "pii", "general"}
        if classification not in valid_routes:
            print(f"⚠️ Router returned invalid classification '{classification}', defaulting to 'general'")
            return "general"

        # Downgrade if capabilities aren't available
        if classification == "rag" and not has_rag_content:
            print("📝 Router selected 'rag' but no RAG content available, falling back to 'general'")
            return "general"
        if classification == "tool" and not has_tools:
            print("📝 Router selected 'tool' but no tools configured, falling back to 'general'")
            return "general"

        return classification

    except Exception as e:
        print(f"⚠️ Router classification error: {e}, defaulting to 'general'")
        return "general"
