"""App-owned execution limits for the formal B1/B2 background roles.

These values are product assembly policy, not package defaults and not model
choices.  Keeping them together prevents the dispatcher, role factory and
durable workflows from drifting onto different budgets.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BackgroundMemoryLimits:
    request_timeout_seconds: float
    compaction_trigger_input_tokens: int
    compaction_keep_messages: int
    case_max_output_tokens: int
    case_summary_max_output_tokens: int
    case_max_model_steps: int
    case_max_tool_calls: int
    case_max_chars: int
    case_context_chars: int
    case_max_windows: int
    case_max_completion_corrections: int
    understanding_max_output_tokens: int
    understanding_summary_max_output_tokens: int
    understanding_max_model_steps: int
    understanding_max_tool_calls: int
    understanding_max_completion_corrections: int
    max_stale_retries: int


FORMAL_BACKGROUND_MEMORY_LIMITS = BackgroundMemoryLimits(
    request_timeout_seconds=300.0,
    compaction_trigger_input_tokens=16000,
    compaction_keep_messages=8,
    case_max_output_tokens=32768,
    case_summary_max_output_tokens=8192,
    case_max_model_steps=256,
    case_max_tool_calls=240,
    case_max_chars=24000,
    case_context_chars=6000,
    case_max_windows=16,
    case_max_completion_corrections=3,
    understanding_max_output_tokens=32768,
    understanding_summary_max_output_tokens=8192,
    understanding_max_model_steps=128,
    understanding_max_tool_calls=120,
    understanding_max_completion_corrections=3,
    max_stale_retries=5,
)
