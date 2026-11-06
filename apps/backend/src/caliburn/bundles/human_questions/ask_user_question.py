"""模型提問介面、欄位提示及原生等待接線。"""

import asyncio
import json
from types import GenericAlias
from typing import Annotated, Any, TypedDict, get_origin
from uuid import UUID

from langchain_core.tools import StructuredTool
from langgraph.func import task
from langgraph.prebuilt import ToolRuntime
from langgraph.types import interrupt
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    create_model,
)
from pydantic.v1 import ValidationError as ValidationErrorV1

from caliburn.bundles.interview.references import message_refs
from caliburn.bundles.interview.services import INTERVIEW_UOW_FACTORY, MODEL_REFERENCES
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.human_questions.questions import (
    AnswerBatch,
    AnsweredQuestion,
    PendingQuestions,
    QuestionBatch,
    QuestionToolResult,
    SavedQuestion,
)
from caliburn.modules.interview.application.recording import (
    record_answers,
    record_questions,
)
from caliburn.modules.interview.domain.models.message_content import (
    Answer,
    AnswerInput,
    Question,
    QuestionOption,
)


def _model_text_schema(schema: dict[str, Any]) -> None:
    """只投影文字欄位；儲存字元驗證仍由原 AfterValidator 執行。"""
    for branch in (schema, *schema.get("anyOf", ())):
        if branch.get("pattern") == r"^[^\u0000\uD800-\uDFFF]*$":
            del branch["pattern"]


def _described_field(
    model: type[BaseModel],
    name: str,
    description: str,
    *,
    item_model: type[BaseModel] | None = None,
    model_text: bool = False,
) -> Any:
    """按 Pydantic 官方派生方式保留原驗證與預設值，產生模型欄位介面。"""
    field = model.model_fields[name].asdict()
    attributes = field["attributes"] | {"description": description}
    if model_text:
        # 替換此欄位的 export 設定，不疊加 dict/callable metadata。
        attributes["json_schema_extra"] = _model_text_schema
    # 動態型別只留在 Pydantic Schema 邊界，業務函式仍使用具名模型。
    annotation: Any = field["annotation"]
    if item_model is not None:
        annotation = (
            Annotated[
                GenericAlias(tuple, (item_model, Ellipsis)),
                Field(strict=False),
            ]
            if get_origin(annotation) is tuple
            else GenericAlias(list, item_model)
        )
    return Annotated[
        (
            annotation,
            *field["metadata"],
            Field(**attributes),
        )
    ]


_OptionInput = create_model(
    "QuestionOptionInput",
    __base__=QuestionOption,
    label=_described_field(
        QuestionOption, "label", "供使用者選擇的名稱；同題不可重複。", model_text=True
    ),
    description=_described_field(
        QuestionOption,
        "description",
        "選項的簡短補充說明；不使用時傳 null。",
        model_text=True,
    ),
)
_QuestionInput = create_model(
    "QuestionInput",
    __base__=Question,
    question=_described_field(
        Question, "question", "要詢問使用者的具體問題。", model_text=True
    ),
    header=_described_field(
        Question, "header", "題目的簡短標題；不使用時傳 null。", model_text=True
    ),
    options=_described_field(
        Question,
        "options",
        "可供選擇的選項；空陣列表示只需自填文字。",
        item_model=_OptionInput,
    ),
    multi_select=_described_field(
        Question, "multi_select", "是否可複選；預設為 false，最多選一項。"
    ),
)
_QuestionsInput = create_model(
    "QuestionsInput",
    __base__=QuestionBatch,
    # StructuredTool 另將簽章上的可信 runtime 注入，不屬於問題資料。
    __config__=ConfigDict(extra="ignore"),
    questions=_described_field(
        QuestionBatch,
        "questions",
        "一次提出的相關問題，至少一題。",
        item_model=_QuestionInput,
    ),
)


class QuestionToolState(TypedDict):
    workspace_id: UUID
    turn_id: UUID
    model_step: int


class _QuestionRecord(Question):
    """保存 task 回傳的正式題目；短碼配置不納入業務保存。"""

    message_id: UUID


class _AnswerRecord(AnswerInput):
    """保留真實答案 UUID，供配置失敗後沿原 task 結果重試。"""

    message_id: UUID


_question_records = TypeAdapter(list[_QuestionRecord])
_answer_records = TypeAdapter(list[_AnswerRecord])


async def ask_user_question(
    questions: list[Question], runtime: ToolRuntime[AgentContext, QuestionToolState]
) -> str:
    """需要補充資訊、確認或選擇時，向使用者提出簡明問題並取得回答。

    使用者可略過任一題：selected 為空且未提供 custom 代表略過，
    不表示同意、拒絕或允許補造答案。不要強迫使用者回答。
    結果的 question_ref 與 answer_ref 可供 read_interview 查讀正式題目與答案。
    """
    call_id = runtime.tool_call_id
    assert call_id is not None
    uow_factory = runtime.context.services.require(INTERVIEW_UOW_FACTORY)
    references = runtime.context.services.require(MODEL_REFERENCES)

    @task
    def save_questions() -> str:
        messages = record_questions(
            workspace_id=runtime.state["workspace_id"],
            turn_id=runtime.state["turn_id"],
            questions=tuple(
                Question.model_validate(question.model_dump()) for question in questions
            ),
            uow_factory=uow_factory,
        )
        saved = []
        for message in messages:
            assert isinstance(message.content, Question)
            saved.append(
                _QuestionRecord(
                    message_id=message.message_id, **message.content.model_dump()
                )
            )
        return _question_records.dump_json(saved, exclude_none=True).decode()

    saved_questions = _question_records.validate_json(await save_questions())
    question_refs = await asyncio.to_thread(
        message_refs,
        workspace_id=runtime.state["workspace_id"],
        message_ids=[question.message_id for question in saved_questions],
        references=references,
    )
    pending = PendingQuestions(
        questions=[
            SavedQuestion(
                **question.model_dump(), question_ref=question_refs[question.message_id]
            )
            for question in saved_questions
        ],
        model_step=runtime.state["model_step"],
        call_id=call_id,
    )
    reply = interrupt(pending.model_dump(mode="json", exclude_none=True))
    answers = pending.validate_answers(
        AnswerBatch.model_validate_json(json.dumps(reply))
    )

    @task
    def save_answers() -> str:
        messages = record_answers(
            workspace_id=runtime.state["workspace_id"],
            turn_id=runtime.state["turn_id"],
            answers=answers.answers,
            uow_factory=uow_factory,
        )
        saved = []
        for message in messages:
            assert isinstance(message.content, Answer)
            assert message.reply_to_message_id is not None
            saved.append(
                _AnswerRecord(
                    message_id=message.message_id,
                    question_message_id=message.reply_to_message_id,
                    selected=message.content.selected,
                    custom=message.content.custom,
                )
            )
        return _answer_records.dump_json(saved, exclude_none=True).decode()

    saved_answers = _answer_records.validate_json(await save_answers())
    answer_refs = await asyncio.to_thread(
        message_refs,
        workspace_id=runtime.state["workspace_id"],
        message_ids=[answer.message_id for answer in saved_answers],
        references=references,
    )
    by_id = {answer.question_message_id: answer for answer in saved_answers}
    return QuestionToolResult(
        answers=[
            AnsweredQuestion(
                question=question.question,
                question_ref=question.question_ref,
                answer_ref=answer_refs[by_id[question.message_id].message_id],
                selected=by_id[question.message_id].selected,
                custom=by_id[question.message_id].custom,
            )
            for question in pending.questions
        ]
    ).model_dump_json(exclude_none=True)


_REPAIRS = {
    "duplicate_option_label": "同題 label 不可重複，請合併重複選項或改名。",
    "string_too_short": "文字不可為空，請補上內容。",
    "too_short": "請提供至少一題。",
    "missing": "請補上此必要欄位。",
    "string_type": "請提供文字；允許 null 的欄位不使用時傳 null。",
    "bool_type": "請使用布林值 true 或 false。",
    "bool_parsing": "請使用布林值 true 或 false。",
    "list_type": "請提供陣列。",
    "tuple_type": "請提供陣列。",
    "model_type": "請提供包含題目或選項欄位的物件。",
    "extra_forbidden": "請移除未定義的欄位。",
}
_INPUT_FIELDS = {
    "questions",
    "question",
    "header",
    "options",
    "label",
    "description",
    "multi_select",
}


def _question_validation_error(error: ValidationError | ValidationErrorV1) -> str:
    """只呈現已知欄位、陣列位置與修正方法，不回顯輸入或未知鍵名。"""
    errors = (
        error.errors(include_input=False, include_url=False)
        if isinstance(error, ValidationError)
        else error.errors()
    )
    repairs = []
    for issue in errors[:5]:
        location = ""
        for part in issue["loc"]:
            if isinstance(part, int):
                location += f"[{part}]"
            else:
                field = part if part in _INPUT_FIELDS else "<extra>"
                location += ("." if location else "") + field
        code = issue["type"]
        if code == "duplicate_option_label":
            index = issue["ctx"]["index"]
            location += f"[{index}].label"
        repair = _REPAIRS.get(code, "請依此欄位的格式修正後重新呼叫。")
        repairs.append(f"{location or 'questions'}：{repair}")
    if len(errors) > 5:
        repairs.append("另有欄位錯誤，請修正以上位置後重試。")
    return "questions 無效：\n" + "\n".join(repairs)


def create_question_tool() -> StructuredTool:
    return StructuredTool.from_function(
        coroutine=ask_user_question,
        args_schema=_QuestionsInput,
        handle_validation_error=_question_validation_error,
    )
