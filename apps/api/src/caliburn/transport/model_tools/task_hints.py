"""Anonymized task-hint search: task content only, no occupation identity leaves this module."""

from dataclasses import asdict

from openai.types.responses import FunctionToolParam
from pydantic import ValidationError

from caliburn.adapters.occupation_references import OccupationReferenceClient, ReferenceClientError
from caliburn.contracts.generated.tools.search_task_hints_arguments import (
    SearchTaskHintsArguments,
)
from caliburn.contracts.generated.tools.task_hint_search_result import TaskHintSearchResult
from caliburn.contracts.validation import parse_contract
from caliburn.transport.model_tools.contracts import function_definition, reject_tool_call

_MAX_HITS = 5
_EXPECTED_FAILURES = (ReferenceClientError,)

_DESCRIPTION = (
    "用一段具體工作任務或職責描述，查公版對這類任務的知識/技能/產出/行為指標，"
    "純粹幫員工回想這類任務通常涉及什麼，不是認定員工的職位、已完成的工作，"
    "也不能直接寫進 JD。結果刻意不含任何職位名稱或代碼；query 保留動作、對象與情境。"
)


def search_task_hints_definition() -> FunctionToolParam:
    """Make the definition inspectable without a network client."""
    return function_definition("search_task_hints", _DESCRIPTION, "search-task-hints-arguments")


class TaskHintTools:
    """Stateless anonymized read; no execution scope, no persisted state, nothing to confirm."""

    names = ("search_task_hints",)
    read_names = names

    def __init__(self, client: OccupationReferenceClient) -> None:
        self.client = client

    def definitions(self) -> list[FunctionToolParam]:
        return [search_task_hints_definition()]

    async def invoke(self, name: str, arguments: str) -> str:
        if name not in self.names:
            return reject_tool_call(
                "scope_not_allowed",
                "目前執行或讀寫入口不允許這項操作。",
                "使用 App 提供的工具，不猜範圍或版本。",
            )
        try:
            parsed = parse_contract(SearchTaskHintsArguments, arguments)
        except ValidationError:
            return reject_tool_call(
                "invalid_arguments",
                "query 不合法，本次未執行搜尋。",
                "只填非空 query，最多 12,000 字元，描述具體任務內容。",
            )
        try:
            found = await self.client.search(parsed.query, limit=_MAX_HITS)
        except _EXPECTED_FAILURES as error:
            return _rejection(error)
        hints = []
        for hit in found.references:
            matched = hit.retrieval_evidence.matched_task_ids
            if not matched:
                continue
            try:
                detail = await self.client.read_task(hit.reference.reference_id, matched[0])
            except _EXPECTED_FAILURES as error:
                return _rejection(error)
            hints.append(
                {
                    "names": [asdict(name) for name in detail.names],
                    "competency_blocks": [asdict(block) for block in detail.competency_blocks],
                }
            )
        return TaskHintSearchResult.model_validate({"hints": hints}).model_dump_json()


_CLIENT_FAILURE_FEEDBACK = {
    "timeout": (
        "公版服務讀取逾時，未取得完整結果。",
        "由 App 處理服務及有限重試；不視為沒有相關任務，也不盲目重試。",
    ),
    "reference_service_unavailable": (
        "公版服務目前不可用，未取得完整結果。",
        "由 App 處理服務連線；不視為沒有相關任務。",
    ),
    "reference_index_incompatible": (
        "公版索引未就緒或與目前服務不相容。",
        "由 App 核對索引及模型版本；不改用同名來源或把故障當空候選。",
    ),
    "reference_query_invalid": (
        "公版服務拒絕本次查詢。",
        "核對 query 的非空、長度與服務限制。",
    ),
    "reference_provider_invalid_response": (
        "公版服務的上游結果不符合契約。",
        "由 App 核對上游資料；本次沒有可用完整結果，不視為沒有相關任務。",
    ),
}


def _rejection(error: Exception) -> str:
    assert isinstance(error, ReferenceClientError)
    if error.code == "invalid_arguments":
        return reject_tool_call(
            "invalid_arguments",
            "query 不合法，本次未執行搜尋。",
            "只填非空 query，最多 12,000 字元。",
        )
    code = error.code if error.code in _CLIENT_FAILURE_FEEDBACK else "reference_service_unavailable"
    message, next_action = _CLIENT_FAILURE_FEEDBACK.get(
        code, _CLIENT_FAILURE_FEEDBACK["reference_service_unavailable"]
    )
    return reject_tool_call(code, message, next_action)
