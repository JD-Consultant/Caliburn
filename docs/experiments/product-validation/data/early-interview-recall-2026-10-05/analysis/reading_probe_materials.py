"""Cold-start probes of reading/answers, not JD persistence or native-history replay."""

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from baseline_store import HERE, read_baseline
from caliburn.contracts.generated.tools.historical_interview import HistoricalInterview
from caliburn.contracts.generated.tools.memory_map import MemoryMap
from caliburn.contracts.generated.tools.memory_map_arguments import MemoryMapArguments
from caliburn.contracts.generated.tools.read_interview_arguments import (
    InterviewMessagesQuery,
    ReadInterviewArguments,
)
from caliburn.contracts.generated.tools.read_memory_object_arguments import (
    ReadMemoryObjectArguments,
)
from caliburn.contracts.generated.tools.work_situation_view import WorkSituationView
from caliburn.contracts.generated.tools.work_understanding_view import (
    WorkUnderstandingView,
)
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.transport.model_tools.contracts import reject_tool_call
from memory_fixture import read_memory_fixture
from pydantic import ValidationError
from reading_prompt_candidates import navigation_candidate, precision_candidate
from study_manifest import file_hash

TRACE_HASH = "1ee84b42d289c9f15ce14f6c1f61eb4dec3950e0389a9b720447bfbac783ce6f"
CASES = {
    "map_present": ("navigation", "c01"),
    "map_absent": ("navigation", "c01"),
    "historical": ("navigation", "c04"),
    "detail": ("precision", "c06"),
    "narrow": ("precision", None),
}


def build_materials() -> dict[str, Any]:
    trace = HERE / "live-01/trace.jsonl"
    if file_hash(trace) != TRACE_HASH:
        raise ValueError("Original trace changed")
    with trace.open(encoding="utf-8") as source:
        request = next(
            row["payload"]
            for line in source
            if (row := json.loads(line)).get("event") == "request"
            and row.get("path") == "/v1/responses"
            and row.get("arm") == "memory"
            and row.get("case_id") == "c01"
        )
    if len(request["input"]) != 2 or any(
        set(item) != {"role", "content"} or item["role"] != "user"
        for item in request["input"]
    ):
        raise ValueError("Require a real cold-start input, not redacted native state")
    request["tools"] = [
        tool
        for tool in request["tools"]
        if tool["name"]
        in {
            "read_work_situation_map",
            "read_work_situation",
            "read_work_understanding_map",
            "read_work_understanding",
            "read_interview",
        }
    ]
    request["instructions"] += (
        "\n本次為既有資料的唯讀問答：只回答員工此刻的問題，不編輯或宣稱更新 JD。"
        "若目前沒有預載導覽，可用相應 map 工具取得；App 額外提供的已讀正文可直接沿用。\n"
    )
    baseline, memory = read_baseline(), read_memory_fixture()
    interviews = [
        {
            "interview_sequence": item.message.interview_sequence,
            "speaker": item.message.speaker.value,
            "text": item.message.interview_text,
        }
        for item in baseline.interviews
    ]
    sequences = {
        item.message.source_id: item.message.interview_sequence
        for item in baseline.interviews
    }
    selected = {item.object_id: item for item in memory.objects}
    reference = json.loads(request["input"][0]["content"])
    maps = {
        f"read_{layer}_map": reference[f"{layer}_map"]
        for layer in ("work_situation", "work_understanding")
    }
    views: dict[str, dict[str, Any]] = {
        "read_work_situation": {},
        "read_work_understanding": {},
    }
    for item in memory.objects:
        view = {
            "title": item.content.title,
            "description": item.content.description,
            "body": item.content.body,
        }
        if item.layer == MemoryLayer.WORK_SITUATION:
            view["interview_references"] = sorted(
                sequences[s] for s in item.interview_references
            )
            parsed = WorkSituationView.model_validate(view)
        else:
            names = {
                selected[r.object_id].content.title
                for r in item.work_situation_references
            }
            view["work_situation_references"] = [
                entry
                for entry in maps["read_work_situation_map"]["items"]
                if entry["target_title"] in names
            ]
            parsed = WorkUnderstandingView.model_validate(view)
        views[f"read_{item.layer.value}"][item.content.title] = parsed.model_dump(
            mode="json"
        )
    questions = {
        case["case_id"]: case["employee_input"]
        for case in json.loads(
            (HERE / "continuation.json").read_text(encoding="utf-8")
        )["cases"]
    }
    return {
        "request": request,
        "maps": maps,
        "views": views,
        "interviews": interviews,
        "questions": questions,
    }


def probe_request(materials: dict[str, Any], arm: str, case_id: str) -> dict[str, Any]:
    candidate, question_id = CASES[case_id]
    if arm not in {"control", candidate}:
        raise ValueError("Unapproved case/arm pair")
    request = deepcopy(materials["request"])
    reference = json.loads(request["input"][0]["content"])
    if case_id == "map_absent":
        reference.pop("work_situation_map")
        reference.pop("work_understanding_map")
    request["input"] = [
        {"role": "user", "content": json.dumps(reference, ensure_ascii=False)}
    ]
    if candidate == "precision":
        request["input"].append(
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "data_kind": "app_preloaded_work_understanding",
                        "items": list(
                            materials["views"]["read_work_understanding"].values()
                        ),
                    },
                    ensure_ascii=False,
                ),
            }
        )
    question = (
        materials["questions"][question_id]
        if question_id
        else "只確認一個細節：我每日大約處理多少張進貨單？這次不用整理其他工作。"
    )
    request["input"].append({"role": "user", "content": question})
    if arm == "navigation":
        return navigation_candidate(request)
    if arm == "precision":
        return precision_candidate(request)
    return request


def invoke(materials: dict[str, Any], name: str, arguments: str) -> dict[str, Any]:
    """Read all original data on demand; no keyword answer cache or grading lookup."""
    try:
        if name in materials["maps"]:
            MemoryMapArguments.model_validate_json(arguments)
            return MemoryMap.model_validate(materials["maps"][name]).model_dump(
                mode="json"
            )
        if name in materials["views"]:
            args = ReadMemoryObjectArguments.model_validate_json(arguments)
            if args.target_title not in materials["views"][name]:
                return _reject(
                    "target_not_found", "請依目前導覽選取精確 target_title。"
                )
            return deepcopy(materials["views"][name][args.target_title])
        if name != "read_interview":
            return _reject("scope_not_allowed", "本次只提供已列出的唯讀工具。")
        query = ReadInterviewArguments.model_validate_json(arguments).query
        if isinstance(query, InterviewMessagesQuery):
            sequences = {value.root for value in query.sequences}
        else:
            if query.start_sequence > query.end_sequence:
                return _reject("invalid_arguments", "區間起點不得晚於終點。")
            if query.end_sequence > len(materials["interviews"]):
                return _reject(
                    "source_not_available", "來源超出固定訪談上界，整筆拒絕。"
                )
            sequences = set(range(query.start_sequence, query.end_sequence + 1))
        if not sequences <= set(range(1, len(materials["interviews"]) + 1)):
            return _reject("source_not_available", "來源超出固定訪談上界，整筆拒絕。")
        return HistoricalInterview.model_validate(
            {
                "data_kind": "historical_interview",
                "messages": [
                    row
                    for row in materials["interviews"]
                    if row["interview_sequence"] in sequences
                ],
            }
        ).model_dump(mode="json")
    except ValidationError:
        return _reject("invalid_arguments", "只提交工具宣告的欄位與合法定位。")


def _reject(code: str, message: str) -> dict[str, Any]:
    return json.loads(reject_tool_call(code, message, message))
