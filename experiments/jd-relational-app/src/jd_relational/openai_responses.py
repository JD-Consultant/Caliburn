"""Terminal evidence for one OpenAI Responses reply, shared by every role.

The consultant, the extraction stage and the consolidation stage all talk to
the same provider through the same adapter, so they judge a reply complete the
same way, in one place. A second copy of this rule is how two roles start
disagreeing about what "finished" means.

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
