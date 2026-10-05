"""Experimental final-output constraint; production requests stay unchanged."""

from copy import deepcopy
from typing import Any

from caliburn.adapters.openai_responses import ResponseRequest


def object_schema(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def completion_schema(role: str) -> dict[str, Any]:
    if role == "single":
        return object_schema({"status": {"type": "string", "enum": ["complete"]}})
    if role != "reader":
        raise ValueError("Unsupported experiment role")
    return object_schema(
        {
            "task": object_schema(
                {"title": {"type": "string"}, "work": {"type": "string"}}
            ),
            "unknowns": {"type": "array", "items": {"type": "string"}},
            "references": {
                "type": "array",
                "items": {
                    "anyOf": [
                        object_schema(
                            {
                                "kind": {
                                    "type": "string",
                                    "enum": ["work_understanding", "work_situation"],
                                },
                                "target_title": {"type": "string"},
                            }
                        ),
                        object_schema(
                            {
                                "kind": {"type": "string", "enum": ["interview"]},
                                "sequences": {
                                    "type": "array",
                                    "items": {"type": "integer"},
                                },
                            }
                        ),
                    ]
                },
            },
        }
    )


class StructuredRequest:
    """Compose only the experiment's text constraint into both public payloads."""

    def __init__(self, request: ResponseRequest, role: str) -> None:
        self._count = request.count_payload()
        self._create = request.create_payload()
        text = {
            "format": {
                "type": "json_schema",
                "name": f"memory_study_{role}",
                "strict": True,
                "schema": completion_schema(role),
            }
        }
        self._count["text"] = deepcopy(text)
        self._create["text"] = deepcopy(text)

    def count_payload(self) -> dict[str, Any]:
        return deepcopy(self._count)

    def create_payload(self) -> dict[str, Any]:
        return deepcopy(self._create)


def structured_request(request: ResponseRequest, role: str) -> StructuredRequest:
    return StructuredRequest(request, role)
