"""
Input Guard Node — Lakera pre-check for prompt injection and jailbreak detection.

This is the first node in the graph. It screens all user input before any
LLM processing occurs. Demonstrates Lakera's ability to catch:
- Direct prompt injection attempts
- Jailbreak attacks
- Malicious instructions hidden in user messages
"""
from typing import Dict, Any, Optional
from .. import lakera


async def run_input_guard(
    message: str,
    session_id: Optional[str],
    lakera_api_key: Optional[str],
    lakera_project_id: Optional[str],
    lakera_blocking_mode: bool,
    system_prompt: Optional[str],
) -> Dict[str, Any]:
    """
    Screen user input with Lakera Guard.

    Returns:
        {
            "passed": bool,          # True if input is allowed through
            "blocked": bool,         # True if blocked in blocking mode
            "flagged": bool,         # True if Lakera flagged the input
            "lakera_result": ...,    # Raw Lakera response
            "blocked_response": str | None  # Canned response if blocked
        }
    """
    if not lakera_api_key:
        return {"passed": True, "blocked": False, "flagged": False, "lakera_result": None, "blocked_response": None}

    lakera_messages = [{"role": "user", "content": message}]

    lakera_result = await lakera.check_interaction(
        messages=lakera_messages,
        meta={"session_id": session_id} if session_id else None,
        api_key=lakera_api_key,
        project_id=lakera_project_id,
        system_prompt=system_prompt,
    )

    flagged = bool(lakera_result and lakera_result.get("flagged"))

    if flagged and lakera_blocking_mode:
        return {
            "passed": False,
            "blocked": True,
            "flagged": True,
            "lakera_result": lakera_result,
            "blocked_response": (
                "This content has been moderated by Lakera and found to be in "
                "breach of our security policies. Please contact support if you "
                "believe this is an error."
            ),
        }

    return {
        "passed": True,
        "blocked": False,
        "flagged": flagged,
        "lakera_result": lakera_result,
        "blocked_response": None,
    }
