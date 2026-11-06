"""角色工具的嚴格結構，只接受精確標題及共用訪談 ref。"""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

type Text = Annotated[str, StringConstraints(min_length=1)]
type MessageReference = Annotated[
    str,
    StringConstraints(min_length=1),
    Field(description="材料提供的 message_* ref；不可猜號、改前綴或傳 UUID。"),
]
type InterviewReferences = Annotated[list[MessageReference], Field(min_length=1)]
type SituationReferences = Annotated[
    list[Text],
    Field(
        min_length=1,
        description="情境來源導覽的 target_title 字串清單，不傳整個導覽物件。",
    ),
]


class EmptyArguments(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)


class TargetArguments(EmptyArguments):
    target_title: Text = Field(description="目前導覽上的精確標題，保留大小寫與空白。")


class CreateContent(EmptyArguments):
    title: Text
    description: Text
    body: Text = Field(
        description="完整 Markdown 正文；保留已知適用條件、限制及精確數值。"
    )


class CreateSituation(CreateContent):
    interview_references: list[MessageReference]


class CreateUnderstanding(CreateContent):
    work_situation_references: list[Text] = Field(
        description=(
            "支持本項理解的情境完整標題；取來源導覽的 target_title 字串，不傳整個物件。"
        )
    )


class ChangeText(EmptyArguments):
    field: Literal["title", "description"]
    value: Text


class ChangeBody(EmptyArguments):
    field: Literal["body"]
    diff: Text = Field(
        description=(
            "正文 V4A。每段以獨立一行 @@ 起始。正文行首以 + 新增、- 刪除、"
            "一個空白保留；以實際換行為界，保留完整原行及唯一上下文。"
            "每段至少有一行 + 或 -。*** End of File 限定該段定位至正文結尾，"
            "不是通用結束標記。"
            "不含檔名、行號或 Markdown 圍欄。@@ 及 *** End of File 不帶前綴。"
            "例如：\n@@\n-目前完整行\n+新的完整行"
        )
    )


class AddInterviewReferences(EmptyArguments):
    field: Literal["interview_references"]
    add: InterviewReferences


class RemoveInterviewReferences(EmptyArguments):
    field: Literal["interview_references"]
    remove: InterviewReferences


class ChangeInterviewReferences(AddInterviewReferences, RemoveInterviewReferences):
    pass


class AddSituationReferences(EmptyArguments):
    field: Literal["work_situation_references"]
    add: SituationReferences


class RemoveSituationReferences(EmptyArguments):
    field: Literal["work_situation_references"]
    remove: SituationReferences


class ChangeSituationReferences(AddSituationReferences, RemoveSituationReferences):
    pass


type SituationChange = (
    ChangeText
    | ChangeBody
    | AddInterviewReferences
    | RemoveInterviewReferences
    | ChangeInterviewReferences
)
type UnderstandingChange = (
    ChangeText
    | ChangeBody
    | AddSituationReferences
    | RemoveSituationReferences
    | ChangeSituationReferences
)


def _require_distinct_fields(
    changes: list[SituationChange] | list[UnderstandingChange],
) -> None:
    if len(changes) != len({change.field for change in changes}):
        raise ValueError("Each changed field may be listed once")


class UpdateSituation(TargetArguments):
    changes: Annotated[list[SituationChange], Field(min_length=1, max_length=4)]

    @model_validator(mode="after")
    def _validate_changes(self) -> Self:
        _require_distinct_fields(self.changes)
        return self


class UpdateUnderstanding(TargetArguments):
    changes: Annotated[list[UnderstandingChange], Field(min_length=1, max_length=4)]

    @model_validator(mode="after")
    def _validate_changes(self) -> Self:
        _require_distinct_fields(self.changes)
        return self
