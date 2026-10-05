"""Research-only source projection and bounded outbound accounting."""

import hashlib
import json
import time
from copy import deepcopy
from decimal import Decimal
from typing import Any

from caliburn.adapters.openai_models import model_profile
from caliburn.adapters.openai_responses import ResponseRequest
from preparation import ARMS, MEMORY_READ_NAMES


class StudyStop(BaseException):
    """Stop the experiment without triggering product provider retries."""


def project_request(
    payload: dict[str, Any], *, arm: str, covered: int, summary: str
) -> dict[str, Any]:
    if arm not in ARMS:
        raise ValueError("Unknown comparison arm")
    projected = deepcopy(payload)
    app = json.loads(projected["input"][-2]["content"])
    if app["data_kind"] != "consultant_turn_reference":
        raise ValueError("Project only the initial App reference message")
    messages = app["historical_interview"]["messages"]
    through = app["interview_read_boundary"]["through_sequence"]
    if type(covered) is not int or not 0 <= covered <= through:
        raise ValueError("Recent-window boundary is outside this Turn")
    recent = [message for message in messages if message["interview_sequence"] > covered]
    context_sequences = []
    if not recent or recent[0]["speaker"] == "employee":
        before = recent[0]["interview_sequence"] if recent else through + 1
        guidance = [
            m for m in messages if m["interview_sequence"] < before and m["speaker"] != "employee"
        ]
        if guidance:
            recent = [guidance[-1], *recent]
            context_sequences = [guidance[-1]["interview_sequence"]]
    app["historical_interview"]["messages"] = recent
    app["interview_read_boundary"]["context_sequences"] = context_sequences
    # Keep product Memory coverage truthful: the study's shared recent boundary is
    # not a claim that raw/recent arms have organized or published those messages.
    app["interview_read_boundary"]["recent_window_after_sequence"] = covered
    if arm != "compaction_hierarchical_memory":
        app.pop("work_situation_map", None)
        app.pop("work_understanding_map", None)
        app.pop("memory_consolidation", None)
    if arm == "compaction_flat_summary":
        app["work_summary"] = summary or "尚無已整理摘要。"
        app["summary_through_sequence"] = covered
    projected["input"][-2]["content"] = json.dumps(app, ensure_ascii=False)
    return projected


def selected_tools(tools: list[Any], arm: str) -> list[Any]:
    if arm not in ARMS:
        raise ValueError("Unknown comparison arm")
    excluded = {"request_memory_consolidation"}
    if arm != "compaction_hierarchical_memory":
        excluded.update(MEMORY_READ_NAMES)
    if arm == "compaction_recent_history":
        excluded.add("read_interview")
    return [deepcopy(tool) for tool in tools if tool["name"] not in excluded]


def fingerprint(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def window_fingerprint(payload: dict[str, Any]) -> str:
    return fingerprint({"model": payload["model"], "input": payload["input"]})


class StudyAllowance:
    def __init__(
        self, *, max_compactions: int = 16, max_estimated_usd: Decimal = Decimal("2.00")
    ) -> None:
        self.outbound_calls = 0
        self.generation_calls = 0
        self.compaction_calls = 0
        self.input_tokens = 0
        self.occupied_usd = Decimal(0)
        self.max_compactions = max_compactions
        self.max_estimated_usd = max_estimated_usd
        self.started = time.monotonic()
        self.counts: dict[str, int] = {}
        self.window_counts: dict[str, int] = {}
        self.pending: dict[str, Decimal] = {}

    def record_count(self, payload: dict[str, Any], input_tokens: object) -> None:
        if type(input_tokens) is not int or input_tokens <= 0:
            raise StudyStop("invalid_remote_count")
        self.counts[fingerprint(payload)] = input_tokens
        self.window_counts[window_fingerprint(payload)] = input_tokens

    def admit(self, path: str, payload: dict[str, Any]) -> None:
        if time.monotonic() - self.started >= 14_400 or self.outbound_calls >= 2200:
            raise StudyStop("outbound_or_time_limit")
        if payload.get("model") != "gpt-6-luna":
            raise StudyStop("unapproved_model")
        tokens = 0
        reserve = Decimal("0.0001")
        if path == "/v1/responses":
            request = ResponseRequest.from_snapshot(payload)
            tokens = self.counts.get(fingerprint(request.count_payload()), 0)
            if not tokens:
                raise StudyStop("missing_count")
            if self.generation_calls >= 900 or payload["max_output_tokens"] != 16_384:
                raise StudyStop("generation_limit")
            reserve = model_profile("gpt-6-luna").pricing.reserve_response_cost(
                input_tokens=tokens, max_output_tokens=16_384
            )
        elif path == "/v1/responses/compact":
            tokens = self.window_counts.get(window_fingerprint(payload), 0)
            if not tokens:
                raise StudyStop("missing_count")
            if self.compaction_calls >= self.max_compactions:
                raise StudyStop("compaction_limit")
            # Compact has no request output limit. This is a disclosed reservation,
            # not a guarantee about the provider's eventual bill.
            reserve = model_profile("gpt-6-luna").pricing.reserve_response_cost(
                input_tokens=tokens, max_output_tokens=128_000
            )
        elif path != "/v1/responses/input_tokens":
            raise StudyStop("unapproved_endpoint")
        if self.input_tokens + tokens > 35_000_000:
            raise StudyStop("cumulative_input_limit")
        if self.occupied_usd + reserve > self.max_estimated_usd:
            raise StudyStop("estimated_budget_limit")
        key = path + fingerprint(payload)
        if path != "/v1/responses/input_tokens" and key in self.pending:
            raise StudyStop("unsettled_prior_request")
        self.outbound_calls += 1
        self.occupied_usd += reserve
        self.input_tokens += tokens
        if path == "/v1/responses":
            self.generation_calls += 1
        elif path.endswith("/compact"):
            self.compaction_calls += 1
        if tokens:
            self.pending[key] = reserve

    def settle(self, path: str, payload: dict[str, Any], estimated_usd: object) -> None:
        if (
            not isinstance(estimated_usd, Decimal)
            or not estimated_usd.is_finite()
            or estimated_usd < 0
        ):
            raise StudyStop("unknown_usage")
        key = path + fingerprint(payload)
        if key not in self.pending:
            raise StudyStop("unadmitted_settlement")
        self.occupied_usd += estimated_usd - self.pending.pop(key)
        if self.occupied_usd > self.max_estimated_usd:
            raise StudyStop("estimated_budget_limit_after_settlement")
