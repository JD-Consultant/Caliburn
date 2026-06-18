"""Deterministic eval checks（D20）：能用規則判的全 deterministic，judge 延後。"""
import re

from app.utils import safe_parse_json

_MISSING = object()
_CJK = re.compile(r"[一-鿿]")
_ASCII_ALPHA = re.compile(r"[A-Za-z]")
_CODE_OCU = re.compile(r"^T\d+$")
_CODE_TASK = re.compile(r"^T\d+\.\d+$")
_CODE_IND = re.compile(r"^P\d+\.\d+\.\d+$")
_CODE_OUT = re.compile(r"^O\d+\.\d+\.\d+$")


def is_valid_json(text: str) -> bool:
    return safe_parse_json(text, default=_MISSING) is not _MISSING


def has_keys(obj: dict, keys: list[str]) -> bool:
    return isinstance(obj, dict) and all(k in obj for k in keys)


def is_zh_tw(text: str) -> bool:
    if not text or not _CJK.search(text):
        return False
    cjk = len(_CJK.findall(text))
    ascii_alpha = len(_ASCII_ALPHA.findall(text))
    return cjk >= ascii_alpha  # CJK 為主、容許少量英文（縮寫/系統名）


def doc_structure_ok(doc: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    units = (doc.get("ocs_content") or {}).get("ocu_units") or []
    if not units:
        reasons.append("no ocu_units")
    for u in units:
        if not _CODE_OCU.match(u.get("ocu_code", "")):
            reasons.append(f"bad ocu_code {u.get('ocu_code')!r}")
        for t in u.get("tasks", []):
            if not _CODE_TASK.match(t.get("task_code", "")):
                reasons.append(f"bad task_code {t.get('task_code')!r}")
            for ind in t.get("indicators", []):
                if not _CODE_IND.match(ind.get("code", "")):
                    reasons.append(f"bad indicator code {ind.get('code')!r}")
            for o in t.get("outputs", []):
                if not _CODE_OUT.match(o.get("code", "")):
                    reasons.append(f"bad output code {o.get('code')!r}")
    if "ocs_ksa" not in doc or "attitudes" not in (doc.get("ocs_ksa") or {}):
        reasons.append("ocs_ksa missing attitudes bucket")
    return (not reasons, reasons)


_REQUIRED_5W2H = ("situation", "purpose", "workflow_steps", "outputs")


def deep_quality_ok(task: dict, threshold: float = 0.60) -> bool:
    inds = task.get("behavior_indicators") or []
    if not inds:
        return False
    if not all(task.get(f) for f in _REQUIRED_5W2H):  # 必填 5W2H 欄非空
        return False
    return all((i.get("quality_score") or 0) >= threshold for i in inds)
