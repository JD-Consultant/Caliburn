"""Memory 離線模型只複製實際 request 已提供的訪談 ref。"""

import json
from typing import Any


def interview_ref(request: dict[str, Any], text: str) -> str:
    for item in request["input"]:
        if item.get("role") != "user" or not isinstance(item.get("content"), str):
            continue
        try:
            material = json.loads(item["content"])
        except json.JSONDecodeError:
            continue
        if not isinstance(material, dict):
            continue
        if material.get("source") == "interview":
            for message in material["messages"]:
                if message["text"] == text:
                    return str(message["ref"])
        if (
            material.get("data_kind") == "employee_input"
            and material.get("text") == text
        ):
            return str(material["ref"])
    raise AssertionError(f"模型沒有收到原話的 ref：{text!r}")


def interview_material(request: dict[str, Any]) -> dict[str, Any]:
    for item in request["input"]:
        if item.get("role") == "user" and isinstance(item.get("content"), str):
            try:
                material = json.loads(item["content"])
            except json.JSONDecodeError:
                continue
            if isinstance(material, dict) and material.get("source") == "interview":
                return material
    raise AssertionError("模型 request 沒有訪談材料")
