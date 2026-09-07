"""Sync Responses request contract with opt-in exact preflight, without mutation.

HTTPX public request hooks run before transport. The independent SDK counter
owns its normal transport retry when enabled; native mode never calls it.
This adapter adds no retry/cache/state store or approximate token guarantee.
Count cannot predict new inline compaction produced by the pending response.
"""
from dataclasses import dataclass, field
import json

import httpx
from langchain_core.exceptions import ContextOverflowError, ModelInvalidRequestError
from openai import OpenAI, OpenAIError


class RequestBudgetExceeded(OpenAIError, ContextOverflowError):
    """Public SDK base propagates through send unchanged; LC marks nonretryable."""


class RequestBudgetConfigurationError(OpenAIError, ModelInvalidRequestError):
    """An uncountable request/configuration must not masquerade as connection loss."""


# SDK3.8 responses.input_tokens.count public parameters, not create's extra_body.
# Keep nested input/tools/text/reasoning objects intact, including opaque items.
_COUNT_FIELDS = frozenset({
    'conversation', 'input', 'instructions', 'model', 'parallel_tool_calls',
    'personality', 'previous_response_id', 'reasoning', 'text', 'tool_choice',
    'tools', 'truncation',
})
# Explicit create-only controls that do not add hidden input. Unknown content
# paths (notably remote prompt templates) fail closed instead of approximating.
_CREATE_ONLY = frozenset({
    'max_output_tokens', 'context_management', 'include', 'store', 'stream',
    'stream_options', 'background', 'metadata', 'max_tool_calls', 'temperature',
    'top_p', 'top_logprobs', 'service_tier', 'safety_identifier', 'user',
    'prompt_cache_key', 'prompt_cache_retention',
})


def validate_context_budget(capacity: int, output: int, compact_threshold: int) -> None:
    """Deployment supplies model capacity; leave room for the output at compaction."""
    if any(type(v) is not int or v <= 0 for v in (capacity, output, compact_threshold)):
        raise ValueError('Context capacity/output/compaction must be positive integers')
    if output >= capacity or compact_threshold + output > capacity:
        raise ValueError('Context capacity must cover compaction threshold plus output reserve')


@dataclass(frozen=True)
class ResponsesBudget:
    counter: OpenAI
    model: str
    context_window_tokens: int
    exact_count: bool = False
    endpoint: httpx.URL = field(init=False)

    def __post_init__(self):
        if type(self.exact_count) is not bool:
            raise RequestBudgetConfigurationError('exact_count must be a boolean')
        if type(self.context_window_tokens) is not int or self.context_window_tokens <= 0:
            raise RequestBudgetConfigurationError('Context capacity must be a positive integer')
        if not isinstance(self.model, str) or not self.model.strip():
            raise RequestBudgetConfigurationError('A configured model is required')
        # SDK3.8 exposes httpx2.URL even with an HTTPX0.28 transport. Normalize
        # via public string form; cross-library URL equality is always false.
        base_url = httpx.URL(str(self.counter.base_url))
        if base_url.query or base_url.fragment:
            raise RequestBudgetConfigurationError('Responses base URL cannot contain query or fragment')
        object.__setattr__(self, 'endpoint', base_url.join('responses'))

    def __call__(self, request: httpx.Request) -> None:
        if request.method != 'POST' or request.url.copy_with(query=None, fragment=None) != self.endpoint:
            return
        if request.url.query or request.url.fragment:
            raise RequestBudgetConfigurationError('Responses query/fragment is not supported by this counter')
        try:
            body = json.loads(request.content)
        except (ValueError, UnicodeError):
            raise RequestBudgetConfigurationError('Responses body must be valid JSON') from None
        if not isinstance(body, dict) or body.get('model') != self.model:
            raise RequestBudgetConfigurationError('Responses model must match configured capacity')
        output = body.get('max_output_tokens')
        if type(output) is not int or not 0 < output <= self.context_window_tokens:
            raise RequestBudgetConfigurationError('A valid final max_output_tokens is required')
        if body.get('truncation') != 'disabled':
            raise RequestBudgetConfigurationError('Responses truncation must be disabled')
        if not self.exact_count:
            return
        # Count has a narrower schema than create. Only exact preflight needs
        # this whitelist; native create remains governed by the SDK/provider.
        if body.keys() - _COUNT_FIELDS - _CREATE_ONLY:
            raise RequestBudgetConfigurationError('Unsupported Responses input/count schema')
        try:
            result = self.counter.responses.input_tokens.count(
                **{key: value for key, value in body.items() if key in _COUNT_FIELDS})
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise RequestBudgetConfigurationError('Counter response must be valid JSON') from None
        tokens = getattr(result, 'input_tokens', None)
        if type(tokens) is not int or tokens < 0:
            raise RequestBudgetConfigurationError('Counter must return nonnegative integer input_tokens')
        if tokens == 0 and any(body.get(k) for k in (
            'input', 'instructions', 'tools', 'text', 'conversation', 'previous_response_id', 'personality',
        )):
            raise RequestBudgetConfigurationError('Counter returned zero for nonempty input')
        if tokens + output > self.context_window_tokens:
            raise RequestBudgetExceeded('Responses input plus output reserve exceeds configured context capacity')
