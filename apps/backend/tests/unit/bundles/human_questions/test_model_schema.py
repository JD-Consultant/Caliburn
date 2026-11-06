"""模型 Schema 不帶儲存字元 regex，正式驗證仍在原生工具入口執行。"""

import asyncio
import json
from typing import Any, cast

import pytest
from pydantic import BaseModel

from caliburn.bundles.human_questions.ask_user_question import create_question_tool
from caliburn.modules.agent.infrastructure.openai.request_initialization import (
    OpenAIRequestInitializer,
)
from caliburn.modules.human_questions.questions import QuestionBatch
from caliburn.modules.interview.domain.models.message_content import (
    Question,
    QuestionOption,
)
from tests.unit.modules.agent.offline_openai import MODEL_REQUEST


def initialized_tool() -> OpenAIRequestInitializer:
    return OpenAIRequestInitializer(MODEL_REQUEST, (create_question_tool(),))


def test_model_schema_omits_storage_pattern_and_retains_field_contract() -> None:
    request = initialized_tool().initialize({"turn_input": "原話"})["model_request"]
    (tool,) = request["tools"]
    assert tool["type"] == "function" and tool["strict"] is True
    schema = cast(dict[str, Any], tool["parameters"])
    assert '"pattern"' not in json.dumps(schema)
    assert set(schema["properties"]) == {"questions"}
    questions = schema["properties"]["questions"]
    assert questions["minItems"] == 1
    question = questions["items"]
    assert set(question["required"]) == {
        "question",
        "header",
        "options",
        "multi_select",
    }
    fields = question["properties"]
    assert fields["question"]["minLength"] == 1
    assert fields["header"]["default"] is None
    assert fields["header"]["anyOf"] == [{"type": "string"}, {"type": "null"}]
    option = fields["options"]["items"]["properties"]
    assert option["label"]["minLength"] == 1
    assert option["description"]["anyOf"] == [{"type": "string"}, {"type": "null"}]
    # Domain/HTTP 的字元契約仍由同一正式型別輸出。
    assert "pattern" in Question.model_json_schema()["properties"]["question"]


@pytest.mark.parametrize("field", ["question", "header", "label", "description"])
@pytest.mark.parametrize("invalid", ["\x00", "\ud800", "\udfff"])
def test_native_tool_rejects_unstorable_text_before_runtime(
    field: str, invalid: str
) -> None:
    question: dict[str, Any] = {
        "question": "盤點方式？",
        "header": None,
        "options": [{"label": "逐筆核對", "description": None}],
        "multi_select": False,
    }
    target = question if field in {"question", "header"} else question["options"][0]
    target[field] = invalid

    async def run() -> None:
        # 故意不提供 runtime；原生參數驗證須先拒絕，不能進入保存 coroutine。
        result = await initialized_tool().tools[0].ainvoke({"questions": [question]})
        assert isinstance(result, str) and result.startswith("questions 無效：")
        assert field in result

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("optional", [None, " 原文🙂\n "])
def test_tool_keeps_unicode_null_and_formal_question_types(
    optional: str | None,
) -> None:
    schema = initialized_tool().tools[0].args_schema
    assert isinstance(schema, type) and issubclass(schema, BaseModel)
    value = schema.model_validate(
        {
            "questions": [
                {
                    "question": "盤點📝？",
                    "header": optional,
                    "options": [{"label": "逐筆核對🙂", "description": optional}],
                    "multi_select": False,
                }
            ]
        }
    )
    assert isinstance(value, QuestionBatch)
    (question,) = value.questions
    assert isinstance(question, Question)
    assert isinstance(question.options[0], QuestionOption)
    assert question.header == question.options[0].description == optional
