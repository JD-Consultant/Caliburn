"""模型可讀內容保留分類、級別與註解，格式清洗不改固定來源。"""

import asyncio
import json
from pathlib import Path
from unittest.mock import create_autospec
from uuid import UUID

from caliburn.bundles.job_reference.projections import project_task
from caliburn.modules.model_references.contracts import ModelReferences, ReferenceTarget
from caliburn.modules.occupation_reference.application.search import (
    ReferenceSearch,
    ReferenceTask,
)
from caliburn.modules.occupation_reference.domain.source import build_reference
from caliburn.modules.occupation_reference.presentation.api.projection import (
    project_task as project_http_task,
)
from tests.unit.bundles.job_reference.support import SourceStore, invoke
from tests.unit.modules.occupation_reference.source_support import (
    FixedEmbedder,
    FixedReranker,
    source_document,
)


def test_model_reads_keep_clean_content_and_note_context_from_the_same_source() -> None:
    source = source_document().source.model_dump(mode="json")
    source["ocs_profile"].update(
        ocs_name={"occupation_name": "3D列印\n工程師"},
        category={"occupations": [{"code": "2144", "name": "機械工程師"}]},
        ocs_level=4,
        job_description="依據客戶需求建置3D列印\n設備，不得省略安全檢查。",
    )
    source["ocs_attitude"] = {"attitudes": [{"code": "A01", "name": "A01 注意安全"}]}
    source["notes"] = {
        "prerequisites": ["至少2年經驗"],
        "supplements": ["【註1】S45C材料，厚度至少3 mm，不得\n省略檢查。"],
    }
    group = source["ocs_content"]["ocu_units"][0]["tasks"][0]
    group["task_codes"][0] = {"code": "T1.1", "name": "T1.1 建置3D列印\n設備"}
    group["competency_blocks"][0]["knowledge"] = [
        {"code": "K01", "name": "K01 材料相關\n知識【註1】"}
    ]
    raw_source = json.dumps(source, ensure_ascii=False)
    document = build_reference(raw_source, source_file="synthetic.json")
    original_source = document.source.model_dump(mode="json")
    service = ReferenceSearch(SourceStore([document]), FixedEmbedder(), FixedReranker())
    target = ReferenceTarget("occupation", UUID(document.reference_id))
    references = create_autospec(ModelReferences, instance=True)
    references.get_or_create_refs.return_value = {target: "occupation_101"}
    references.resolve_refs.return_value = {"occupation_101": target}

    async def scenario() -> None:
        found = await invoke(
            service,
            "search_occupation_references",
            {"query": "3D列印"},
            references=references,
        )
        catalog = found["references"][0]
        arguments = {"reference_id": catalog["reference_id"], "task_id": None}
        assert (
            await invoke(
                service, "read_occupation_reference", arguments, references=references
            )
            == catalog
        )
        assert catalog["ocs_level"] == 4
        assert catalog["category"]["occupations"] == [{"name": "機械工程師"}]
        assert catalog["attitudes"] == [{"name": "注意安全"}]
        assert catalog["title"] == "3D列印工程師"
        assert catalog["overview"] == "依據客戶需求建置3D列印設備，不得省略安全檢查。"
        task = await invoke(
            service,
            "read_occupation_reference",
            {**arguments, "task_id": "u1-t1"},
            references=references,
        )
        assert task["names"][0] == {"name": "建置3D列印設備"}
        assert task["competency_blocks"][0]["knowledge"] == [
            {"name": "材料相關知識【註1】"}
        ]
        assert len(task["competency_blocks"]) == 2
        assert task["competency_blocks"][1]["competency_level"] is None
        assert (
            task["notes"]
            == catalog["notes"]
            == {
                "prerequisites": ["至少2年經驗"],
                "supplements": ["【註1】S45C材料，厚度至少3 mm，不得省略檢查。"],
            }
        )
        assert (
            task["source_sha256"] == catalog["source_sha256"] == document.source_sha256
        )
        assert document.source_utf8 == raw_source
        assert document.source.model_dump(mode="json") == original_source
        raw_task = project_http_task(
            await asyncio.to_thread(service.read_task, document.reference_id, "u1-t1")
        )
        assert raw_task.names[0].code == "T1.1"
        assert raw_task.names[0].name == "T1.1 建置3D列印\n設備"
        assert raw_task.competency_blocks[0].knowledge[0].code == "K01"

    asyncio.run(scenario())


def test_jewelry_knowledge_note_is_returned_with_its_explanation() -> None:
    fixture = (
        Path(__file__).parents[2]
        / "modules/occupation_reference/pdf/fixtures/golden"
        / "3D珠寶設計人員-職能基準.json"
    )
    document = build_reference(
        fixture.read_bytes().decode("utf-8"), source_file=fixture.name
    )
    result = ReferenceTask(
        document.reference_id,
        document.source_sha256,
        document.tasks[0],
        document.source.notes,
    )
    task = project_task(result, reference_id="occupation_101")
    assert "珠寶屬性相關知識【註1】" in json.dumps(
        task["competency_blocks"], ensure_ascii=False
    )
    assert "【註1】珠寶屬性相關知識：" in json.dumps(task["notes"], ensure_ascii=False)
    assert "材料品質產業標準" in json.dumps(task["notes"], ensure_ascii=False)
