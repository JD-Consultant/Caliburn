"""JD 模型編修意圖；正式 UUID、版本與交易資料不出現在工具參數。"""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field


def _require_text(value: str) -> str:
    if (
        not value.strip()
        or "\x00" in value
        or any(0xD800 <= ord(char) <= 0xDFFF for char in value)
    ):
        raise ValueError("文字須含非空白內容且可保存為 UTF-8")
    return value


def _mathematical_integer(value: object) -> int:
    if type(value) is int:
        return value
    if type(value) is float and value.is_integer():
        return int(value)
    raise ValueError("級別須為 JSON 數學整數，不接受布林或字串")


type ReadRef = Annotated[
    str,
    Field(
        strict=True,
        pattern=r"^(duty|task|outcome|requirement|knowledge|skill|collaboration|condition)_[1-9][0-9]*$",
        description="原樣使用已提供的 JD 短碼，不自行編號或使用 UUID。",
    ),
]
type Text = Annotated[
    str, Field(strict=True, min_length=1), AfterValidator(_require_text)
]
type Level = Annotated[
    int, Field(strict=True, ge=1, le=6), BeforeValidator(_mathematical_integer)
]
type ConditionKind = Annotated[
    Literal[
        "work_environment",
        "schedule_travel",
        "shared_authority",
        "shared_collaboration",
        "qualification",
    ],
    Field(
        description="work_environment 工作環境；schedule_travel 時程／出差；"
        "shared_authority 共通權限；shared_collaboration 共通協作；"
        "qualification 必要資格。"
    ),
]


class WriteInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InterviewSource(WriteInput):
    kind: Literal["interview"]
    message_ref: Annotated[
        str,
        Field(
            strict=True,
            pattern=r"^message_[1-9][0-9]*$",
            description="原樣使用已讀訪談或本輪原話提供的 ref（message_N）；"
            "正文須直接支持本項。",
        ),
    ]


class MemorySource(WriteInput):
    kind: Literal["work_situation", "work_understanding"]
    target_title: Annotated[
        Text,
        Field(
            description="本輪固定發布版已讀正文的完整標題；按所選類別精確定位，不改寫或摘要。"
        ),
    ]


type Source = InterviewSource | MemorySource
type CitationRef = Annotated[
    str,
    Field(
        strict=True,
        pattern=r"^citation_[1-9][0-9]*$",
        description="目前目標讀回 supporting_sources 中的既有 citation_ref；"
        "用於移除或核對該引用。",
    ),
]


class SourceInput(WriteInput):
    supporting_sources: Annotated[
        tuple[Source, ...],
        Field(
            max_length=64,
            description=("只支持本項自身，不自動繼承給其他項目；無來源填 []，不猜造。"),
        ),
    ] = ()


class AddSource(WriteInput):
    action: Literal["add_source"]
    source: Source


class RemoveSource(WriteInput):
    action: Literal["remove_source"]
    citation_ref: CitationRef


class ConfirmSource(WriteInput):
    action: Literal["confirm_reference_alignment"]
    citation_ref: CitationRef


type SourceChange = AddSource | RemoveSource | ConfirmSource


class TaskDetail(WriteInput):
    text: Text


class ExistingCapability(WriteInput):
    kind: Literal["existing"]
    capability_read_ref: ReadRef


class NewCapability(WriteInput):
    kind: Literal["new"]
    name: Text
    description: Annotated[
        Text | None,
        Field(description="所需專業內容、用途及適用範圍；不需補述時填 null。"),
    ] = None


type Capability = ExistingCapability | NewCapability


class DutyItem(SourceInput):
    kind: Literal["duty"]
    name: Text
    scope: Annotated[
        Text | None,
        Field(description="依共同目的組成的工作範圍與責任界線；名稱已足夠時填 null。"),
    ] = None


class CapabilityItem(SourceInput):
    kind: Annotated[
        Literal["knowledge", "skill"],
        Field(
            description="knowledge 是工作須理解的內容；"
            "skill 是運用方法完成工作與判斷的能力。"
        ),
    ]
    name: Text
    description: Annotated[
        Text | None,
        Field(description="所需專業內容、用途及適用範圍；不需補述時填 null。"),
    ] = None


class CollaborationItem(SourceInput):
    kind: Literal["collaboration"]
    collaborator_name: Annotated[
        Text,
        Field(description="已知且與工作有關的協作角色、單位或對象；不自動視為主管。"),
    ]
    scope: Annotated[
        Text | None,
        Field(
            description="協作事項、本人分工及必要交接／核准界線；不需補述時填 null。"
        ),
    ] = None


class ConditionItem(SourceInput):
    kind: Literal["condition"]
    condition_kind: ConditionKind
    text: Annotated[
        Text,
        Field(
            description="有依據的共通工作條件及適用範圍；任務特有條件留在任務。"
            "資格須是職位確實必要，不由個人持證推定；未知不寫成不需要。"
        ),
    ]


type NewItem = DutyItem | CapabilityItem | CollaborationItem | ConditionItem


class SetField(WriteInput):
    action: Literal["set_field"]
    field: Literal["name", "description", "scope", "collaborator_name", "text"]
    value: Text


class ClearField(WriteInput):
    action: Literal["clear_field"]
    field: Literal["description", "scope"]


class SetCompetencyLevel(WriteInput):
    action: Literal["set_competency_level"]
    value: Annotated[
        Level | None,
        Field(
            description="有已確認定級依據才設定任務級別；"
            "null 清空，未取得新依據時不送此動作。"
        ),
    ]


class SetConditionKind(WriteInput):
    action: Literal["set_condition_kind"]
    value: ConditionKind


class AddDetail(WriteInput):
    action: Literal["add_detail"]
    kind: Annotated[
        Literal["outcome", "requirement"],
        Field(
            description="outcome 是形成、交付或維持的結果；"
            "requirement 是已確認的執行／完成要求，"
            "不可把單次做法升為固定要求。"
        ),
    ]
    text: Text


class ReviseDetail(WriteInput):
    action: Literal["revise_detail"]
    detail_read_ref: ReadRef
    text: Text


class RemoveDetail(WriteInput):
    action: Literal["remove_detail"]
    detail_read_ref: ReadRef


class SetCapability(WriteInput):
    action: Literal["set_capability"]
    capability_read_ref: ReadRef
    relationship: Literal["link", "unlink"]


class CreateCapability(WriteInput):
    action: Literal["create_capability"]
    kind: Annotated[
        Literal["knowledge", "skill"],
        Field(
            description="knowledge 是工作須理解的內容；"
            "skill 是運用方法完成工作與判斷的能力。"
        ),
    ]
    name: Text
    description: Annotated[
        Text | None,
        Field(description="所需專業內容、用途及適用範圍；不需補述時填 null。"),
    ] = None


class ReorderCapability(WriteInput):
    action: Literal["reorder_capability"]
    capability_read_ref: ReadRef
    before_read_ref: ReadRef | None = Field(
        description="放在同任務已連結的同類能力前；null 表示組末。"
    )


type ItemChange = (
    SetField
    | ClearField
    | SetCompetencyLevel
    | SetConditionKind
    | AddDetail
    | ReviseDetail
    | RemoveDetail
    | SetCapability
    | CreateCapability
    | ReorderCapability
    | AddSource
    | RemoveSource
    | ConfirmSource
)
type ItemChanges = Annotated[list[ItemChange], Field(min_length=1, max_length=64)]


class SetProfileField(WriteInput):
    action: Literal["set_field"]
    field: Annotated[
        Literal["job_title", "organization_unit", "reports_to", "purpose"],
        Field(
            description="job_title 真實職稱；organization_unit 已知單位；"
            "reports_to 已確認匯報角色；"
            "purpose 概括服務對象、主要工作及持續價值，不另造組織關係或績效目標。"
        ),
    ]
    value: Text


class ClearProfileField(WriteInput):
    action: Literal["clear_field"]
    field: Literal["job_title", "organization_unit", "reports_to", "purpose"]


class SetBaselineLevel(WriteInput):
    action: Literal["set_baseline_competency_level"]
    value: Annotated[
        Level | None,
        Field(
            description="有已確認定級依據才設定職務共同基準級別；"
            "null 清空，未取得新依據時不送此動作。"
        ),
    ]


type ProfileChange = (
    SetProfileField
    | ClearProfileField
    | SetBaselineLevel
    | AddSource
    | RemoveSource
    | ConfirmSource
)
type ProfileChanges = Annotated[list[ProfileChange], Field(min_length=1, max_length=64)]


class CurrentContainer(WriteInput):
    kind: Literal["current_container"]


class TaskParent(WriteInput):
    kind: Literal["task_parent"]
    parent_read_ref: ReadRef | None


type Destination = CurrentContainer | TaskParent


class SetDutyScope(WriteInput):
    action: Literal["set_duty_scope"]
    duty_read_ref: ReadRef
    scope: Annotated[
        Text | None, Field(description="職責涵蓋的工作範圍與責任界線；null 清空。")
    ]


type MovementChange = (
    SetField | ClearField | SetCompetencyLevel | AddDetail | ReviseDetail | SetDutyScope
)
