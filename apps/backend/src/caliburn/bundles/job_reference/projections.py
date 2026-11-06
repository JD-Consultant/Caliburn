"""模型結果沿模組規則清洗正文，定位原樣保留；HTTP 仍提供原始來源投影。"""

from pydantic import JsonValue

from caliburn.modules.occupation_reference.application.search import ReferenceTask
from caliburn.modules.occupation_reference.domain.cleaning import clean_source_fields
from caliburn.modules.occupation_reference.domain.source import ReferenceDocument


def project_reference(
    document: ReferenceDocument, *, reference_id: str
) -> dict[str, object]:
    profile = document.source.ocs_profile
    names = profile.ocs_name
    source_units = (
        document.source.ocs_content.ocu_units if document.source.ocs_content else []
    )
    units: list[JsonValue] = []
    for index, unit in enumerate(source_units or [], 1):
        unit_id = f"u{index}"
        units.append(
            {
                "unit_id": unit_id,
                "code": unit.ocu_code,
                "name": unit.ocu_name,
                "tasks": [
                    {
                        "task_id": entry.task_id,
                        "names": [
                            {"code": item.code, "name": item.name}
                            for item in entry.group.task_codes or []
                        ],
                        "competency_block_count": len(
                            entry.group.competency_blocks or []
                        ),
                    }
                    for entry in document.tasks
                    if entry.unit_id == unit_id
                ],
            }
        )
    content: dict[str, JsonValue] = {
        "title": ((names.occupation_name or names.job_category_name) if names else None)
        or document.ocs_code,
        "overview": profile.job_description or "",
        "category": profile.category.model_dump(mode="json")
        if profile.category
        else {},
        "ocs_level": profile.ocs_level,
        "attitudes": [
            item.model_dump(mode="json")
            for item in (document.source.ocs_attitude.attitudes or [])
        ]
        if document.source.ocs_attitude
        else [],
        "notes": document.source.notes.model_dump(mode="json")
        if document.source.notes
        else {},
        "catalog_scope": "all_parsed_task_groups",
        "units": units,
    }
    return {
        "reference_id": reference_id,
        "source_sha256": document.source_sha256,
        "source_file": document.source_file,
        "ocs_code": document.ocs_code,
        **clean_source_fields(content),
    }


def project_task(result: ReferenceTask, *, reference_id: str) -> dict[str, object]:
    entry = result.entry
    content: dict[str, JsonValue] = {
        "names": [
            {"code": item.code, "name": item.name}
            for item in entry.group.task_codes or []
        ],
        "competency_blocks": [
            {
                "competency_level": block.competency_level,
                "outputs": [
                    {"code": item.code, "name": item.name}
                    for item in block.outputs or []
                ],
                "indicators": [
                    {"code": item.code, "text": item.text}
                    for item in block.indicators or []
                ],
                "knowledge": [
                    {"code": item.code, "name": item.name}
                    for item in block.knowledge or []
                ],
                "skills": [
                    {"code": item.code, "name": item.name}
                    for item in block.skills or []
                ],
            }
            for block in entry.group.competency_blocks or []
        ],
        "notes": result.notes.model_dump(mode="json") if result.notes else {},
    }
    return {
        "reference_id": reference_id,
        "source_sha256": result.source_sha256,
        "task_id": entry.task_id,
        "unit_id": entry.unit_id,
        **clean_source_fields(content),
    }
