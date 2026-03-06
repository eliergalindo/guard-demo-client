"""
Tool Agent Node — MCP tool execution with tool-output scanning.

Handles requests that require external tool calls via MCP/ToolHive.
Demonstrates Lakera's ability to detect:
- Malicious content in tool responses (tool output poisoning)
- Data exfiltration attempts via tool calls
- Indirect prompt injection through tool results
"""
import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from .. import rag, toolhive
from ..openai_client import openai_client


async def run_tool_agent(
    message: str,
    system_prompt: Optional[str],
    model: str = "gpt-4o",
    temperature: float = 0.7,
    db: Session = None,
    lakera_api_key: Optional[str] = None,
    lakera_project_id: Optional[str] = None,
    lakera_blocking_mode: bool = False,
) -> Dict[str, Any]:
    """
    Execute tool calls via OpenAI function calling + MCP.

    Returns:
        {
            "response": str,
            "tool_traces": [...],
            "citations": [...],
        }
    """
    # Get RAG context (tools may need document context too)
    context = await rag.retrieve(message)
    citations = []
    if context:
        citations = [
            {"source": doc.get("metadata", {}).get("source")}
            for doc in context
            if doc.get("metadata", {}).get("source")
            and doc.get("metadata", {}).get("source") != "unknown"
        ]

    # Build tools manifest
    tools_manifest = toolhive.openai_tools_manifest(db)

    # Build messages
    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if context:
        context_text = "\n\n".join([doc["text"] for doc in context])
        messages.append({"role": "system", "content": f"Context information:\n{context_text}"})
    messages.append({"role": "user", "content": message})

    tool_traces: List[Dict[str, Any]] = []

    try:
        openai_client._load_config()

        # First LLM call with tools
        response = openai_client.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            tools=tools_manifest if tools_manifest else None,
        )

        assistant_message = response["choices"][0]["message"]
        messages.append(assistant_message)

        # Handle tool calls
        if assistant_message.get("tool_calls"):
            for tool_call in assistant_message["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                tool_args_str = tool_call["function"]["arguments"]
                tool_call_id = tool_call["id"]

                try:
                    parsed_args = json.loads(tool_args_str)
                except json.JSONDecodeError:
                    parsed_args = {}

                # Find tool metadata
                tool_metadata = None
                for tool_def in tools_manifest:
                    if tool_def["function"]["name"] == tool_name:
                        tool_metadata = tool_def.get("_tool_metadata")
                        break

                if not tool_metadata:
                    tool_result = {
                        "status": "error",
                        "content_string": f"Tool metadata not found for: {tool_name}",
                        "raw_result": None,
                    }
                else:
                    tool_result = await toolhive.execute(
                        tool_name=tool_name,
                        args=parsed_args,
                        tool_metadata=tool_metadata,
                        db=db,
                        lakera_api_key=lakera_api_key,
                        lakera_project_id=lakera_project_id,
                        lakera_blocking_mode=lakera_blocking_mode,
                    )

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": tool_name,
                    "content": tool_result["content_string"],
                })

                tool_traces.append({
                    "id": tool_call_id,
                    "name": tool_name,
                    "args": parsed_args,
                    "result": tool_result,
                })

            # Second LLM call with tool results
            final_response = openai_client.chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
            )
            response_text = final_response["choices"][0]["message"]["content"]
        else:
            response_text = assistant_message["content"]

    except Exception as e:
        response_text = f"I apologize, but I encountered an error executing tools: {str(e)}"

    return {
        "response": response_text,
        "tool_traces": tool_traces,
        "citations": citations,
    }
