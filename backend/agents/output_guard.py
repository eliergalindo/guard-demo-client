"""
Output Guard Node — Lakera post-check on assistant responses.

This is the final node in the graph. It screens all LLM output before
returning to the user. Demonstrates Lakera's ability to catch:
- Content moderation violations in generated text
- PII leakage in assistant responses
- Harmful or inappropriate content generation
- Data exfiltration in outputs
"""
from typing import Dict, Any, Optional
from .. import lakera

BLOCKED_RESPONSE = (
    "This content has been moderated by Lakera and found to be in "
    "breach of our security policies. Please contact support if you "
    "believe this is an error."
)


async def run_output_guard(
    user_message: str,
    assistant_response: str,
    session_id: Optional[str],
    lakera_api_key: Optional[str],
    lakera_project_id: Optional[str],
    lakera_blocking_mode: bool,
    system_prompt: Optional[str],
) -> Dict[str, Any]:
    """
    Screen assistant output with Lakera Guard.

    Returns:
        {
            "passed": bool,
            "blocked": bool,
            "flagged": bool,
            "lakera_result": ...,
            "final_response": str,  # may be replaced with blocked message
        }
    """
    if not lakera_api_key:
        return {
            "passed": True,
            "blocked": False,
            "flagged": False,
            "lakera_result": None,
            "final_response": assistant_response,
        }

    lakera_messages = [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": assistant_response},
    ]

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
            "final_response": BLOCKED_RESPONSE,
        }

    return {
        "passed": True,
        "blocked": False,
        "flagged": flagged,
        "lakera_result": lakera_result,
        "final_response": assistant_response,
    }
