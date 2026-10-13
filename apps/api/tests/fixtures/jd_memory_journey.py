"""正式 HTTP 旅程的有限 A／B 替身；只證接線，不評內容品質。"""

import json
import re

import httpx2

from tests.fixtures.response_loop import response_at
from tests.fixtures.response_transport import response_http_reply


class JourneyModel:
    """只替換 SDK HTTP；各角色仍執行 create_agent 及正式工具。"""

    def __init__(self, case: str):
        self.case = case
        self.sent: list[dict] = []
        self.counts: list[dict] = []
        self.compactions: list[dict] = []
        self.positions: dict[tuple[str, int], int] = {}
        self.references: dict[str, str] = {}
        self.frontier = 0

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        payload = json.loads(request.content)
        if request.url.path.endswith("/input_tokens"):
            self.counts.append(payload)
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 500}
            )
        if request.url.path.endswith("/compact"):
            self.compactions.append(payload)
            return httpx2.Response(
                200,
                json={
                    "id": f"cmp_{len(self.compactions)}",
                    "object": "response.compaction",
                    "created_at": 1,
                    "output": [
                        {"type": "compaction", "encrypted_content": "synthetic-window"},
                        *payload["input"],
                    ],
                    "usage": {
                        "input_tokens": 500,
                        "output_tokens": 100,
                        "total_tokens": 600,
                        "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                        "output_tokens_details": {"reasoning_tokens": 0},
                    },
                },
            )
        self.sent.append(payload)
        names = {tool["name"] for tool in payload["tools"]}
        role = (
            "A" if "create_jd_task" in names else "B1" if "create_work_situation" in names else "B2"
        )
        data = self._data(payload, role)
        sequence = (
            data["interview_sequence"]
            if role == "A"
            else data["required_interview_range"]["end_sequence"]
            if role == "B1"
            else self.frontier
        )
        if role == "B1":
            self.frontier = sequence
        key = role, sequence
        index = self.positions.get(key, 0)
        self.positions[key] = index + 1
        self._remember_created(payload)
        if role == "A":
            call = self._consultant(index, data, payload)
        elif role == "B1":
            call = self._situation(index, data)
        else:
            call = self._understanding(index, data, payload)
        number = len(self.sent)
        raw = response_at(number, final=call is None).model_dump(mode="json")
        raw["service_tier"] = "default"
        if call is None:
            raw["output"][1]["content"][0]["text"] = (
                "合成顧問本輪已完成。" if role == "A" else '{"status":"complete"}'
            )
        else:
            raw["output"] = [
                {
                    "type": "function_call",
                    "id": f"fc_journey_{number}",
                    "call_id": f"call_journey_{number}",
                    "name": call[0],
                    "arguments": json.dumps(call[1], ensure_ascii=False),
                }
            ]
        return response_http_reply(request, raw)

    @staticmethod
    def _data(payload: dict, role: str) -> dict:
        for item in reversed(payload["input"]):
            if item.get("role") != "user" or not isinstance(item.get("content"), str):
                continue
            try:
                data = json.loads(item["content"])
            except json.JSONDecodeError:
                continue
            if role == "A" and "interview_sequence" in data:
                return data
            if role != "A" and data.get("data_kind") == "memory_analysis_input":
                return data
        raise AssertionError("The product did not supply the role's actual captured input")

    def _remember_created(self, payload: dict) -> None:
        calls = {
            item["call_id"]: item
            for item in payload["input"]
            if item.get("type") == "function_call"
        }
        for item in payload["input"]:
            if item.get("type") != "function_call_output":
                continue
            call = calls.get(item["call_id"])
            match = re.fullmatch(r"created · read_ref: (\S+)", item["output"])
            if call is not None and match is not None:
                arguments = json.loads(call["arguments"])
                if call["name"] == "create_jd_item":
                    self.references[arguments["item"]["kind"]] = match[1]

    def _consultant(self, index: int, data: dict, payload: dict):
        sequence, text = data["interview_sequence"], data["text"]
        source = [{"kind": "interview", "interview_sequence": sequence}]
        for item in payload["input"]:
            if item.get("role") != "user" or not isinstance(item.get("content"), str):
                continue
            try:
                app_data = json.loads(item["content"])
            except json.JSONDecodeError:
                continue
            entries = app_data.get("work_understanding_map", {}).get("items", [])
            if entries:
                source.append(
                    {"kind": "work_understanding", "target_title": entries[-1]["target_title"]}
                )
                break
        first = sequence == 2
        if self.case == "manual_cross_section_changes" and first:
            operations = [
                ("read_jd", {"view": "map", "read_ref": None}),
                (
                    "create_jd_item",
                    {
                        "item": {
                            "kind": "responsibility_area",
                            "title": "設備管理",
                            "scope_text": "異常停用及交接",
                            "supporting_sources": source,
                        }
                    },
                ),
                (
                    "create_jd_item",
                    {
                        "item": {
                            "kind": "skill",
                            "name": "異常描述與追蹤",
                            "description": "描述設備異常並追蹤技師處理",
                            "supporting_sources": source,
                        }
                    },
                ),
                (
                    "create_jd_item",
                    {
                        "item": {
                            "kind": "collaborator",
                            "name": "技師",
                            "scope_text": "維修及安全判斷",
                            "supporting_sources": source,
                        }
                    },
                ),
                (
                    "create_jd_task",
                    {
                        "parent_read_ref": self.references.get("responsibility_area"),
                        "title": "設備異常停用與交接",
                        "description": text,
                        "outcomes": [{"text": "可追蹤的設備異常紀錄"}],
                        "requirements": [{"text": "技師簽認後恢復借用"}],
                        "required_knowledge": [],
                        "required_skills": [
                            {"capability_read_ref": self.references.get("skill", "missing")}
                        ],
                        "supporting_sources": source,
                    },
                ),
                (
                    "edit_interview_plan",
                    {"diff": "@@\n+核對已談設備分工；其他工作待談。\n*** End of File"},
                ),
                ("request_context_compaction", {}),
                ("request_memory_consolidation", {}),
            ]
        else:
            operations = [("read_jd", {"view": "map", "read_ref": None})]
            # 合成任務只證原話進入正式保存，不充作品質 oracle 或自然模型預期。
            if not (self.case == "unanchored_background_and_shared_ks" and first):
                operations.append(
                    (
                        "create_jd_task",
                        {
                            "parent_read_ref": None,
                            "title": f"合成工作 {sequence}",
                            "description": text,
                            "outcomes": [],
                            "requirements": [],
                            "required_knowledge": [],
                            "required_skills": [],
                            "supporting_sources": source,
                        },
                    )
                )
            if first:
                operations.append(
                    ("edit_interview_plan", {"diff": "@@\n+接續尚未談到的工作。\n*** End of File"})
                )
                operations.append(("request_context_compaction", {}))
            if "工作記憶" in text:
                operations.append(("request_memory_consolidation", {}))
            elif not first:
                operations.append(("request_context_compaction", {}))
        return operations[index] if index < len(operations) else None

    @staticmethod
    def _situation(index: int, data: dict):
        messages = data["historical_interview"]["messages"]
        employees = [item for item in messages if item["speaker"] == "employee"]
        last = employees[-1]
        if index == 0:
            return "create_work_situation", {
                "title": f"合成情境 {last['interview_sequence']}",
                "description": "此批正式員工原話",
                "body": "\n\n".join(item["text"] for item in employees),
                "interview_references": [item["interview_sequence"] for item in employees],
            }
        return None

    def _understanding(self, index: int, data: dict, payload: dict):
        title = data["work_situation_map"]["items"][-1]["target_title"]
        if index == 0:
            return "read_work_situation", {"target_title": title}
        if index == 1:
            observed = next(
                item["output"]
                for item in reversed(payload["input"])
                if item.get("type") == "function_call_output"
            )
            return "create_work_understanding", {
                "title": f"合成理解 {self.frontier}",
                "description": "從本批實際情境讀取結果建立",
                "body": observed,
                "work_situation_references": [title],
            }
        return None
