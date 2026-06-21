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


def skeleton(profile: dict, units_tasks: list[dict]) -> dict:
    """Produce the empty OCS shell: profile/units/tasks present, cells empty."""
    profile = profile or {}

    ocs_code = profile.get("ocs_code") or profile.get("selected_ocs_code") or ""
    occupation = profile.get("occupation_name") or profile.get("job_title") or ""
    description = profile.get("job_description") or profile.get("job_summary") or ""
    category = profile.get("category")
    if not isinstance(category, dict):
        category = _empty_category()
    ocs_level = profile.get("ocs_level")

    # Group tasks by unit_id, preserving first-seen order. Tasks with no
    # unit_id land in a single synthetic bucket (key None).
    order: list[Any] = []
    groups: dict[Any, list[dict]] = {}
    for task in units_tasks or []:
        unit_id = task.get("unit_id")
        key = unit_id if unit_id else None
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(task)

    ocu_units: list[dict[str, Any]] = []
    for u, key in enumerate(order, start=1):
        tasks = groups[key]
        first = tasks[0]
        unit_id = first.get("unit_id")
        unit_title = first.get("unit_title")
        ocu_code = unit_id if unit_id else f"T{u}"
        ocu_name = unit_title if unit_title else "其他工作任務"

        ocu_tasks: list[dict[str, Any]] = []
        for t, task in enumerate(tasks, start=1):
            ref = task.get("indexer_ref") or {}
            task_id = ref.get("task_id")
            code = task_id if task_id else f"{ocu_code}.{t}"
            ocu_tasks.append(
                {
                    "task_codes": [{"code": code, "name": task.get("task_name", "")}],
                    "competency_blocks": [_empty_block()],
                }
            )

        ocu_units.append({"ocu_code": ocu_code, "ocu_name": ocu_name, "tasks": ocu_tasks})

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
