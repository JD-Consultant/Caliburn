"""Common terminal evidence after each role's adapter normalization.

The consultant and B1 OpenRouter adapters and the current B2 OpenAI Responses
adapter use different wire formats, but all must project a completed status
and preserve refusal evidence before this boundary. Keeping the final decision
here prevents roles from disagreeing about what "finished" means.

Checked 2026-09-14 against the official structured-output guidance: an
application must see that the response reached `completed` and that no content
block is a refusal before trusting it (the caller still owns schema or tool
validation). `status` is also what reports truncation -- a reply cut off at the
output ceiling arrives as `incomplete`, never as a short success. HTTP 200
alone, or text that merely parses, is evidence of neither.
"""

from langchain_core.messages import AIMessage


def accepted(raw: AIMessage) -> bool:
    """True only for a normally completed, unrefused response."""
    refused = raw.additional_kwargs.get("refusal") or any(
        isinstance(block, dict) and (block.get("type") == "refusal" or
            (block.get("type") == "non_standard" and "refusal" in block.get("value", {})))
        for block in raw.content_blocks)
    return not refused and raw.response_metadata.get("status") == "completed"
