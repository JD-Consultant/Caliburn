"""目標由內容用例提供；引用動作只能修改該目標的來源。"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, PositiveInt

from caliburn.modules.job_description.domain.models.citation import SourceReference
from caliburn.shared.application.base_dto import BaseDTO

type EditingActor = Literal["human", "consultant"]


class AddCitationInput(BaseDTO):
    action: Literal["add"] = "add"
    source: SourceReference


class RemoveCitationInput(BaseDTO):
    action: Literal["remove"] = "remove"
    citation_id: UUID


class ConfirmCitationInput(BaseDTO):
    action: Literal["confirm"] = "confirm"
    citation_id: UUID
    published_version: PositiveInt | None = None


type CitationChange = Annotated[
    AddCitationInput | RemoveCitationInput | ConfirmCitationInput,
    Field(discriminator="action"),
]
