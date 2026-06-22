"""OCS document-of-record contract helpers (D27 T2).

Pure functions over the OCS JSON contract using plain dicts only.
NO pydantic, NO langgraph, and NOT the legacy ``app/schemas/ocs.py`` models
(those are LLM-era with divergent defaults). Authoritative contract:
``jd-pdf-to-json`` README section 6.

Three functions:
- ``skeleton(profile, units_tasks)`` -> empty contract-shaped shell
- ``assemble_final(draft)`` -> contract-complete copy that passes ``validate``
- ``validate(doc)`` -> list of human-readable error strings ([] == valid)
"""

from __future__ import annotations

import copy
from typing import Any


def _empty_category() -> dict[str, Any]:
    return {"job_categories": [], "occupations": [], "industries": []}


def _empty_block() -> dict[str, Any]:
    return {
        "competency_level": None,
        "indicators": [],
        "outputs": [],
        "knowledge": [],
        "skills": [],
    }


def _task_prov(task: dict) -> dict:
    ref = task.get("indexer_ref") or {}
    return {"ocs_code": ref.get("ocs_code") or "", "task_id": ref.get("task_id") or "", "id": ref.get("id") or ""}


def skeleton(profile: dict, units_tasks: list[dict]) -> dict:
    """Produce the empty OCS shell: profile/units/tasks present, cells empty.

    Units are grouped by (ocs_code, unit_id) so different occupations never merge
    even when both number their units "T1". Units and tasks are RENUMBERED
    sequentially across the whole document (職責 T1,T2…; 任務 T{u}.{t}) for a
    curated multi-OCS instance; the source occupation/task is kept under
    ``unit["source"]`` / ``task["provenance"]`` for display + merge-on-recurate.
    """
    profile = profile or {}

    ocs_code = profile.get("ocs_code") or profile.get("selected_ocs_code") or ""
    occupation = profile.get("occupation_name") or profile.get("job_title") or ""
    description = profile.get("job_description") or profile.get("job_summary") or ""
    category = profile.get("category")
    if not isinstance(category, dict):
        category = _empty_category()
    ocs_level = profile.get("ocs_level")

    # Group by (ocs_code, unit_id), preserving first-seen order.
    order: list[Any] = []
    groups: dict[Any, list[dict]] = {}
    for task in units_tasks or []:
        ref = task.get("indexer_ref") or {}
        key = (ref.get("ocs_code") or "", task.get("unit_id") or "")
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(task)

    ocu_units: list[dict[str, Any]] = []
    for u, key in enumerate(order, start=1):
        tasks = groups[key]
        first = tasks[0]
        ocu_tasks: list[dict[str, Any]] = []
        for t, task in enumerate(tasks, start=1):
            ocu_tasks.append(
                {
                    "task_codes": [{"code": f"T{u}.{t}", "name": task.get("task_name", "")}],
                    "competency_blocks": [_empty_block()],
                    "provenance": _task_prov(task),
                }
            )
        ocu_units.append(
            {
                "ocu_code": f"T{u}",
                # blank when 職責 not adopted (cherry-picked task) → user names it.
                "ocu_name": first.get("unit_title") or "",
                "source": {
                    "ocs_code": key[0],
                    "unit_id": key[1],
                    "occupation_name": first.get("occupation_name") or "",
                },
                "tasks": ocu_tasks,
            }
        )

    return {
        "version_info": {"versions": []},
        "ocs_profile": {
            "ocs_code": ocs_code,
            "ocs_name": {"job_category_name": None, "occupation_name": occupation},
            "category": category,
            "job_description": description,
            "ocs_level": ocs_level,
        },
        "ocs_content": {"ocu_units": ocu_units},
        "ocs_attitude": {"attitudes": []},
        "notes": {"prerequisites": [], "supplements": []},
    }


def _renumber(doc: dict) -> dict:
    """Resequence 職責 T1,T2… and 任務 T{u}.{t}; names/blocks/provenance untouched."""
    for u, unit in enumerate(doc["ocs_content"]["ocu_units"], start=1):
        unit["ocu_code"] = f"T{u}"
        for t, task in enumerate(unit.get("tasks") or [], start=1):
            tcs = task.get("task_codes") or [{"code": "", "name": ""}]
            tcs[0]["code"] = f"T{u}.{t}"
            task["task_codes"] = tcs
    return doc


def build_from_picked(profile: dict, picked: list[dict], prev: dict | None = None) -> dict:
    """ADDITIVE 選任務：保留 prev 全部任務（含已填/自訂/使用者編輯），只「加」picked
    中尚未存在（依 provenance ocs_code+task_id）的任務。新任務若來源職責
    (ocs_code+unit_id) 已在文件 → 併入該職責；否則新增職責（名稱依 adopt：
    picked.unit_title 有值＝採用整組保留名，留白＝cherry-pick）。"""
    if not prev or not ((prev.get("ocs_content") or {}).get("ocu_units")):
        return skeleton(profile, picked)

    doc = copy.deepcopy(prev)
    units = doc["ocs_content"]["ocu_units"]

    existing: set[tuple] = set()
    for unit in units:
        for task in unit.get("tasks") or []:
            p = task.get("provenance") or {}
            existing.add((p.get("ocs_code") or "", p.get("task_id") or ""))

    for it in picked:
        ref = it.get("indexer_ref") or {}
        oc = ref.get("ocs_code") or ""
        tid = ref.get("task_id") or ""
        key = (oc, tid)
        if key in existing:
            continue
        existing.add(key)
        uid = it.get("unit_id") or ""
        target = None
        for unit in units:
            src = unit.get("source") or {}
            if uid and src.get("ocs_code") == oc and src.get("unit_id") == uid:
                target = unit
                break
        if target is None:
            target = {
                "ocu_code": "",
                "ocu_name": it.get("unit_title") or "",  # blank = cherry-pick
                "source": {"ocs_code": oc, "unit_id": uid,
                           "occupation_name": it.get("occupation_name") or ""},
                "tasks": [],
            }
            units.append(target)
        target["tasks"].append({
            "task_codes": [{"code": "", "name": it.get("task_name", "")}],
            "competency_blocks": [_empty_block()],
            "provenance": {"ocs_code": oc, "task_id": tid, "id": ref.get("id") or ""},
        })

    return _renumber(doc)


def assemble_final(draft: dict) -> dict:
    """Return a contract-complete deep copy of ``draft`` that passes validate."""
    doc = copy.deepcopy(draft or {})

    # Ensure all 5 top-level keys exist.
    doc.setdefault("version_info", {"versions": []})
    doc.setdefault("ocs_profile", {})
    doc.setdefault("ocs_content", {})
    doc.setdefault("ocs_attitude", {"attitudes": []})
    doc.setdefault("notes", {"prerequisites": [], "supplements": []})

    if not isinstance(doc["version_info"], dict):
        doc["version_info"] = {"versions": []}
    doc["version_info"].setdefault("versions", [])

    if not isinstance(doc["ocs_attitude"], dict):
        doc["ocs_attitude"] = {"attitudes": []}
    doc["ocs_attitude"].setdefault("attitudes", [])

    if not isinstance(doc["notes"], dict):
        doc["notes"] = {"prerequisites": [], "supplements": []}
    doc["notes"].setdefault("prerequisites", [])
    doc["notes"].setdefault("supplements", [])

    profile = doc["ocs_profile"] if isinstance(doc["ocs_profile"], dict) else {}
    doc["ocs_profile"] = profile
    name = profile.get("ocs_name")
    if not isinstance(name, dict):
        name = {}
        profile["ocs_name"] = name
    name.setdefault("job_category_name", None)
    name.setdefault("occupation_name", "")

    content = doc["ocs_content"] if isinstance(doc["ocs_content"], dict) else {}
    doc["ocs_content"] = content
    units = content.get("ocu_units")
    if not isinstance(units, list):
        units = []
        content["ocu_units"] = units

    for unit in units:
        if not isinstance(unit, dict):
            continue
        tasks = unit.get("tasks")
        if not isinstance(tasks, list):
            continue
        for task in tasks:
            if not isinstance(task, dict):
                continue
            task.setdefault("task_codes", [])
            blocks = task.get("competency_blocks")
            if not isinstance(blocks, list) or not blocks:
                blocks = [_empty_block()]
                task["competency_blocks"] = blocks
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                block.setdefault("competency_level", None)
                for key in ("indicators", "outputs", "knowledge", "skills"):
                    if not isinstance(block.get(key), list):
                        block[key] = []

    # Populate our own version record if none exists.
    versions = doc["version_info"]["versions"]
    if not versions:
        versions.append(
            {
                "version": "v1",
                "ocs_code": profile.get("ocs_code", ""),
                "ocs_name": name.get("occupation_name", ""),
                "status": "最新版本",
                "update_date": None,
            }
        )

    # Strip front-end-only keys (_uid/_tid/_pool) → contract-pure final JSON.
    doc.pop("_pool", None)
    for unit in units:
        if not isinstance(unit, dict):
            continue
        unit.pop("_uid", None)
        for task in unit.get("tasks") or []:
            if isinstance(task, dict):
                task.pop("_tid", None)

    return doc


def validate(doc: dict) -> list[str]:
    """Return human-readable error strings; empty list means valid."""
    errors: list[str] = []

    if not isinstance(doc, dict):
        return ["doc: must be a dict"]

    for key in ("version_info", "ocs_profile", "ocs_content", "ocs_attitude", "notes"):
        if key not in doc:
            errors.append(f"doc: missing top-level key '{key}'")

    # ocs_profile checks
    profile = doc.get("ocs_profile")
    if isinstance(profile, dict):
        if not isinstance(profile.get("ocs_code"), str):
            errors.append("ocs_profile.ocs_code: must be a str")
        name = profile.get("ocs_name")
        if not isinstance(name, dict):
            errors.append("ocs_profile.ocs_name: must be a dict")
        else:
            if "job_category_name" not in name:
                errors.append("ocs_profile.ocs_name: missing key 'job_category_name'")
            if "occupation_name" not in name:
                errors.append("ocs_profile.ocs_name: missing key 'occupation_name'")
    elif "ocs_profile" in doc:
        errors.append("ocs_profile: must be a dict")

    # ocs_content / ocu_units checks
    content = doc.get("ocs_content")
    if isinstance(content, dict):
        units = content.get("ocu_units")
        if not isinstance(units, list):
            errors.append("ocs_content.ocu_units: must be a list")
        else:
            for i, unit in enumerate(units):
                loc = f"ocu_units[{i}]"
                if not isinstance(unit, dict):
                    errors.append(f"{loc}: must be a dict")
                    continue
                if not isinstance(unit.get("ocu_code"), str):
                    errors.append(f"{loc}: ocu_code must be a str")
                if not isinstance(unit.get("ocu_name"), str):
                    errors.append(f"{loc}: ocu_name must be a str")
                tasks = unit.get("tasks")
                if not isinstance(tasks, list):
                    errors.append(f"{loc}: tasks must be a list")
                    continue
                for j, task in enumerate(tasks):
                    tloc = f"{loc}.tasks[{j}]"
                    if not isinstance(task, dict):
                        errors.append(f"{tloc}: must be a dict")
                        continue
                    task_codes = task.get("task_codes")
                    if not isinstance(task_codes, list) or not task_codes:
                        errors.append(f"{tloc}: task_codes must be a non-empty list")
                    else:
                        for k, tc in enumerate(task_codes):
                            if not isinstance(tc, dict) or "code" not in tc or "name" not in tc:
                                errors.append(
                                    f"{tloc}.task_codes[{k}]: must have 'code' and 'name'"
                                )
                    blocks = task.get("competency_blocks")
                    if not isinstance(blocks, list) or not blocks:
                        errors.append(f"{tloc}: competency_blocks must be a non-empty list")
                    else:
                        for b, block in enumerate(blocks):
                            bloc = f"{tloc}.competency_blocks[{b}]"
                            if not isinstance(block, dict):
                                errors.append(f"{bloc}: must be a dict")
                                continue
                            for lk in ("indicators", "outputs", "knowledge", "skills"):
                                if not isinstance(block.get(lk), list):
                                    errors.append(f"{bloc}: {lk} must be a list")
                            level = block.get("competency_level")
                            if not (level is None or isinstance(level, int)):
                                errors.append(
                                    f"{bloc}: competency_level must be int or None"
                                )
    elif "ocs_content" in doc:
        errors.append("ocs_content: must be a dict")

    # ocs_attitude checks
    attitude = doc.get("ocs_attitude")
    if isinstance(attitude, dict):
        if not isinstance(attitude.get("attitudes"), list):
            errors.append("ocs_attitude.attitudes: must be a list")
    elif "ocs_attitude" in doc:
        errors.append("ocs_attitude: must be a dict")

    # notes checks
    notes = doc.get("notes")
    if isinstance(notes, dict):
        if "prerequisites" not in notes:
            errors.append("notes: missing key 'prerequisites'")
        if "supplements" not in notes:
            errors.append("notes: missing key 'supplements'")
    elif "notes" in doc:
        errors.append("notes: must be a dict")

    return errors
