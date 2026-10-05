"""Isolated experimental storage; reuse wire schemas and the production body editor."""

import json
from copy import deepcopy
from functools import lru_cache

from caliburn.features.work_memory.body_edits import apply_body_diff
from caliburn.features.work_memory.body_matching import BodyEditError
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.transport.model_tools.memory_analysis import (
    memory_analysis_tool_definitions,
)
from jsonschema import Draft202012Validator, ValidationError

SITUATION = "work_situation"
UNDERSTANDING = "work_understanding"


@lru_cache
def _definitions(arm: str, role: str) -> list[dict]:
    if arm not in ("two_layer", "one_collection"):
        raise ValueError("Unknown experimental arm")
    allowed = {
        "two_layer": {"b1", "b2", "reader"},
        "one_collection": {"single", "reader"},
    }
    if role not in allowed[arm]:
        return []
    layer = (
        MemoryLayer.WORK_UNDERSTANDING
        if arm == "two_layer" and role != "b1"
        else MemoryLayer.WORK_SITUATION
    )
    definitions = deepcopy(memory_analysis_tool_definitions(layer))
    if arm == "one_collection":
        # Same direct-interview contract as B1, exposed as an understanding collection.
        encoded = json.dumps(definitions, ensure_ascii=False)
        definitions = json.loads(
            encoded.replace("work_situation", "work_understanding")
            .replace("WorkSituation", "WorkUnderstanding")
            .replace("work situation", "work understanding")
            .replace("情境", "理解")
        )
    if role == "reader":
        definitions = [tool for tool in definitions if tool["name"].startswith("read_")]
    for tool in definitions:
        name = tool["name"]
        if name.endswith("_map"):
            tool["description"] += " 已提供且仍適用的導覽不用重讀；需重新定位才用。"
        elif name in ("read_work_understanding", "read_work_situation"):
            tool["description"] += (
                " 按需讀正文；足以回答時停止，不把來源導覽當必讀清單。"
            )
        elif name == "read_interview":
            tool["description"] += (
                " 只有具體事實、指涉或來源缺口才回查；已知尚未確認且沒有新線索時，向下讀不會補出答案。"
            )
    return definitions


def tool_definitions(arm: str, role: str) -> list[dict]:
    return deepcopy(_definitions(arm, role))


class Workspace:
    """One arm owns all mutable objects; snapshots are detached values, not views."""

    def __init__(self, arm: str, messages: list[dict]) -> None:
        _definitions(arm, "reader")
        self.arm = arm
        self.messages = {
            item["interview_sequence"]: deepcopy(item) for item in messages
        }
        self.read_through = 0
        self.objects: dict[str, dict] = {}
        self.next_id = 1

    def snapshot(self) -> dict:
        return deepcopy(
            {
                "arm": self.arm,
                "read_through": self.read_through,
                "next_id": self.next_id,
                "objects": self.objects,
            }
        )

    @classmethod
    def restore(cls, arm: str, messages: list[dict], snapshot: dict) -> "Workspace":
        if snapshot["arm"] != arm:
            raise ValueError("Cross-arm snapshot")
        workspace = cls(arm, messages)
        saved = deepcopy(snapshot)
        workspace.read_through = saved["read_through"]
        workspace.next_id = saved["next_id"]
        workspace.objects = saved["objects"]
        return workspace

    def map(self, layer: str) -> dict:
        return {
            "items": [
                {"target_title": item["title"], "description": item["description"]}
                for item in self.objects.values()
                if item["layer"] == layer
            ]
        }

    def _find(self, layer: str, title: str) -> tuple[str, dict]:
        for identity, item in self.objects.items():
            if item["layer"] == layer and item["title"] == title:
                return identity, item
        raise ValueError("target_not_found")

    def _reference_field(self, layer: str) -> str:
        return (
            "work_situation_references"
            if self.arm == "two_layer" and layer == UNDERSTANDING
            else "interview_references"
        )

    def _resolve(self, layer: str, refs: list) -> list:
        if self._reference_field(layer) == "interview_references":
            if any(
                type(value) is not int
                or value not in self.messages
                or value > self.read_through
                for value in refs
            ):
                raise ValueError("interview_out_of_scope")
            return list(dict.fromkeys(refs))
        return list(dict.fromkeys(self._find(SITUATION, title)[0] for title in refs))

    def _view(self, item: dict) -> dict:
        result = {key: item[key] for key in ("title", "description", "body")}
        field = self._reference_field(item["layer"])
        if field == "interview_references":
            result[field] = list(item["references"])
        else:
            result[field] = [
                {
                    "target_title": self.objects[identity]["title"],
                    "description": self.objects[identity]["description"],
                }
                for identity in item["references"]
            ]
        return result

    def views(self, layer: str) -> dict:
        return {
            identity: self._view(item)
            for identity, item in self.objects.items()
            if item["layer"] == layer
        }

    def read_interview(self, query: dict) -> dict:
        if query["kind"] == "messages":
            sequences = query["sequences"]
        else:
            start, end = query["start_sequence"], query["end_sequence"]
            if start > end or end > self.read_through:
                raise ValueError("interview_out_of_scope")
            sequences = list(range(start, end + 1))
        if any(
            value not in self.messages or value > self.read_through
            for value in sequences
        ):
            raise ValueError("interview_out_of_scope")
        return {
            "messages": [
                deepcopy(self.messages[value]) for value in sorted(set(sequences))
            ]
        }

    def invoke(self, role: str, name: str, arguments: dict) -> dict:
        tool = next(
            (item for item in _definitions(self.arm, role) if item["name"] == name),
            None,
        )
        if tool is None:
            return self._error("scope_not_allowed")
        try:
            Draft202012Validator(tool["parameters"]).validate(arguments)
            return self._execute(name, arguments)
        except ValidationError:
            return self._error("invalid_arguments")
        except BodyEditError as error:
            return self._error(error.code)
        except ValueError as error:
            return self._error(str(error))

    @staticmethod
    def _error(code: str) -> dict:
        return {
            "error": {
                "code": code,
                "message": "本次操作未採用。",
                "next_action": "依工具契約修正；定位或 patch 有誤時按需讀取目前正文及來源，再補足唯一上下文。不要重送相同錯誤。",
            }
        }

    def _validate_content(
        self, layer: str, candidate: dict, identity: str | None = None
    ) -> None:
        if any(not candidate[key].strip() for key in ("title", "description", "body")):
            raise ValueError("blank_content")
        if any(
            key != identity
            and item["layer"] == layer
            and item["title"] == candidate["title"]
            for key, item in self.objects.items()
        ):
            raise ValueError("duplicate_title")

    def _execute(self, name: str, arguments: dict) -> dict:
        if name == "read_interview":
            return self.read_interview(arguments["query"])
        layer = UNDERSTANDING if "work_understanding" in name else SITUATION
        if name.endswith("_map"):
            return self.map(layer)
        if name.startswith("create_"):
            candidate = {
                key: arguments[key] for key in ("title", "description", "body")
            }
            candidate.update(
                layer=layer,
                references=self._resolve(
                    layer, arguments[self._reference_field(layer)]
                ),
            )
            self._validate_content(layer, candidate)
            identity = f"object_{self.next_id}"
            self.objects[identity] = candidate
            self.next_id += 1
            return {"status": "created"}
        identity, item = self._find(layer, arguments["target_title"])
        if name.startswith("read_"):
            return self._view(item)
        if name.startswith("delete_"):
            del self.objects[identity]
            if layer == SITUATION:
                for dependent in self.objects.values():
                    if dependent["layer"] == UNDERSTANDING:
                        dependent["references"] = [
                            ref for ref in dependent["references"] if ref != identity
                        ]
            return {"status": "deleted"}
        candidate = deepcopy(item)
        seen = set()
        for change in arguments["changes"]:
            field = change["field"]
            if field in seen:
                raise ValueError("duplicate_field")
            seen.add(field)
            if field in ("title", "description"):
                candidate[field] = change["value"]
            elif field == "body":
                candidate[field] = apply_body_diff(candidate[field], change["diff"])
            else:
                add = self._resolve(layer, change.get("add", []))
                remove = self._resolve(layer, change.get("remove", []))
                if set(add) & set(remove) or not set(remove) <= set(
                    candidate["references"]
                ):
                    raise ValueError("invalid_reference_change")
                candidate["references"] = list(
                    dict.fromkeys(
                        [ref for ref in candidate["references"] if ref not in remove]
                        + add
                    )
                )
        self._validate_content(layer, candidate, identity)
        self.objects[identity] = candidate
        return {"status": "updated"}
