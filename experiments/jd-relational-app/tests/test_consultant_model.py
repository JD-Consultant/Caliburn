"""The consultant's model assembly, on this product's one provider.

Real SDK and adapter against an in-process transport; zero provider calls. What
is pinned here is what the role was decided to be: OpenAI Responses, reasoning
effort high, an explicit output ceiling, inline compaction, no parallel tool
calls and no server-side conversation storage.
"""

import httpx
import pytest
from langchain_openai import ChatOpenAI

from jd_relational.consultant_model import (
    COMPACT_THRESHOLD, MAX_OUTPUT_TOKENS, ConsultantModelError, create_consultant_model,
)
from jd_relational.openai_responses import accepted

from support.openai_replies import MODEL, refused, reply, truncated

KEY = "synthetic-consultant-not-a-key"


def answering(body):
    return httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)),
                        trust_env=False, timeout=5)


def built(client, **options):
    return create_consultant_model(model=MODEL, api_key=KEY, http_client=client, **options)


def test_the_role_profile_is_what_was_decided():
    with answering(reply("a1")) as client:
        model = built(client)
    assert isinstance(model, ChatOpenAI)
    assert model.use_responses_api is True and model.output_version == "responses/v1"
    assert model.store is False, "the durable record is this App's, never the provider's"
    assert model.max_tokens == MAX_OUTPUT_TOKENS == 8192
    assert model.reasoning == {"effort": "high", "context": "all_turns"}
    assert model.model_kwargs["parallel_tool_calls"] is False
    assert model.max_retries == 0, "a retry is the App's decision, not the adapter's"
    assert model.context_management == [
        {"type": "compaction", "compact_threshold": COMPACT_THRESHOLD}]


def test_no_truncation_parameter_is_sent_so_an_oversize_input_fails_loudly():
    sent = []

    def receive(request):
        import json
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=reply("a1"))

    with httpx.Client(transport=httpx.MockTransport(receive), trust_env=False, timeout=5) as client:
        built(client).invoke("合成輸入")
    assert "truncation" not in sent[0]
    assert sent[0]["store"] is False and sent[0]["parallel_tool_calls"] is False


def test_a_completed_reply_is_accepted_and_carries_its_text():
    with answering(reply("a1", text="合成顧問回覆")) as client:
        message = built(client).invoke("合成輸入")
    assert accepted(message)
    assert "合成顧問回覆" in str(message.content)


def test_one_tool_call_arrives_as_one_tool_call():
    with answering(reply("a2", "jd_read", {"view": "current"})) as client:
        message = built(client).invoke("合成輸入")
    assert accepted(message)
    assert [call["name"] for call in message.tool_calls] == ["jd_read"]
    assert message.tool_calls[0]["args"] == {"view": "current"}


def test_a_reply_cut_off_at_the_ceiling_is_not_a_short_success():
    with answering(truncated("a3")) as client:
        message = built(client).invoke("合成輸入")
    assert message.response_metadata.get("status") == "incomplete"
    assert not accepted(message), "truncation was accepted as an answer"


def test_a_refusal_is_not_an_answer():
    with answering(refused("a4")) as client:
        message = built(client).invoke("合成輸入")
    assert not accepted(message)


@pytest.mark.parametrize("options", [
    {"model": ""}, {"model": "   "}, {"api_key": ""}, {"model": "with\0null"},
    {"max_output_tokens": 0}, {"max_output_tokens": -1}, {"reasoning_effort": " "},
    {"compact_threshold": 0}, {"request_timeout": 0}, {"request_timeout": float("inf")},
])
def test_an_unusable_configuration_is_refused_before_any_client_is_bound(options):
    with answering(reply("a1")) as client:
        arguments = {"model": MODEL, "api_key": KEY, "http_client": client, **options}
        with pytest.raises(ConsultantModelError) as error:
            create_consultant_model(**arguments)
    assert error.value.code == "invalid_model_configuration"


def test_the_product_has_no_anthropic_consultant_path():
    """One provider. A framework that can speak to two is not a product that does."""
    import pathlib
    source = pathlib.Path(__file__).resolve().parents[1] / "src" / "jd_relational"
    offenders = [path.name for path in source.rglob("*.py")
                 if "langchain_anthropic" in path.read_text(encoding="utf-8")
                 or "ChatAnthropic" in path.read_text(encoding="utf-8")]
    assert offenders == [], offenders
