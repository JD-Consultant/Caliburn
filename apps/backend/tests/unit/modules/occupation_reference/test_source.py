"""Source identity and lossless task projection through the public constructor."""

import hashlib
import json
from uuid import NAMESPACE_URL, uuid5

import pytest

from caliburn.modules.occupation_reference.domain.source import (
    PREPROCESSING,
    build_reference,
)
from tests.unit.modules.occupation_reference.source_support import source_document


def test_source_embeds_cleaned_groups_and_keeps_raw_tasks() -> None:
    doc = source_document()
    assert [task.task_id for task in doc.tasks] == ["u1-t1", "u1-t2", "u1-t3"]
    group = doc.tasks[0].group
    assert group.task_codes is not None
    assert [(task.code, task.name) for task in group.task_codes] == [
        ("T1", "介面製作"),
        ("T2", "流程整合"),
        (None, "資料串接"),
    ]
    assert group.competency_blocks is not None
    assert len(group.competency_blocks) == 2
    block = group.competency_blocks[0]
    assert block.knowledge is not None
    assert block.knowledge[0].name == "工程識圖"
    assert block.skills is not None
    assert block.skills[0].name == "資料閱讀"
    assert "職位標題" in doc.document_text
    cleaned = json.loads(doc.document_text)
    groups = cleaned["ocs_content"]["ocu_units"][0]["tasks"]
    assert groups[0] == {
        "task_codes": [
            {"name": "介面製作"},
            {"name": "流程整合"},
            {"name": "資料串接"},
        ],
        "competency_blocks": [
            {
                "competency_level": None,
                "outputs": [{"name": "網頁"}],
                "indicators": [{"text": "顯示資料"}],
                "knowledge": [{"name": "工程識圖"}],
                "skills": [{"name": "資料閱讀"}],
            },
            {
                "competency_level": None,
                "outputs": [{"name": "無碼產出"}],
                "indicators": [],
                "knowledge": [],
                "skills": [],
            },
        ],
    }
    assert [chunk.chunk_id for chunk in doc.chunks] == [
        "overview",
        "u1-t1",
        "u1-t2",
        "u1-t3",
    ]
    assert json.loads(doc.chunks[0].text) == {
        "ocs_profile": cleaned["ocs_profile"],
        "ocs_attitude": {"attitudes": []},
        "notes": {"prerequisites": [], "supplements": []},
    }
    for chunk, group_json in zip(doc.chunks[1:], groups, strict=True):
        assert json.loads(chunk.text) == {
            "ocs_profile": cleaned["ocs_profile"],
            "ocu_name": "開發",
            "task_group": group_json,
            "notes": cleaned["notes"],
        }
        assert chunk.task_id == chunk.chunk_id


def test_retrieval_json_preserves_profile_notes_models_and_repeated_groups() -> None:
    shared_group = {
        "task_codes": [{"code": "T1.1", "name": "T1.1 檢修A320型飛機"}],
        "competency_blocks": [
            {
                "competency_level": 3,
                "indicators": [
                    {"code": "P1.1.1", "text": "P1.1.1 不得低於3.5 mm，至少10件"}
                ],
                "knowledge": [{"code": "K01", "name": "K01 K10硬質合金刀具【註1】"}],
                "skills": [{"code": "S01", "name": "S01 S45C碳鋼加工"}],
            }
        ],
    }
    source_utf8 = (
        json.dumps(
            {
                "version_info": {"versions": [{"version": "V1"}]},
                "ocs_profile": {
                    "ocs_code": "APP1",
                    "ocs_name": {"occupation_name": "3D列印工程師"},
                    "category": {
                        "occupations": [{"code": "2144", "name": "機械工程師"}]
                    },
                    "job_description": "依據客戶需求\n操作T1.12A型模組",
                    "ocs_level": 4,
                    "specialization": "機械\n設計",
                },
                "ocs_content": {
                    "ocu_units": [
                        {
                            "ocu_code": "T1",
                            "ocu_name": "T1 設備\n維護",
                            "tasks": [shared_group, shared_group],
                        },
                        {"tasks": []},
                        {"ocu_name": "檢查", "tasks": [shared_group]},
                    ]
                },
                "ocs_attitude": {"attitudes": [{"code": "A01", "name": "謹慎負責"}]},
                "notes": {
                    "prerequisites": ["須熟悉3D列印"],
                    "supplements": ["【註1】材料不得\n低於3.5 mm。"],
                },
                "scope": "僅適用本規範",
            },
            ensure_ascii=False,
        )
        + "\r\n"
    )

    document = build_reference(source_utf8, source_file="technical.json")

    assert "機械工程師" in document.document_text
    cleaned = json.loads(document.document_text)
    expected_profile = {
        "ocs_name": {"occupation_name": "3D列印工程師"},
        "category": {
            "job_categories": [],
            "occupations": [{"name": "機械工程師"}],
            "industries": [],
        },
        "job_description": "依據客戶需求操作T1.12A型模組",
        "ocs_level": 4,
        "specialization": "機械設計",
    }
    assert cleaned["ocs_profile"] == expected_profile
    assert cleaned["notes"] == {
        "prerequisites": ["須熟悉3D列印"],
        "supplements": ["【註1】材料不得低於3.5 mm。"],
    }
    assert cleaned["ocs_attitude"] == {"attitudes": [{"name": "謹慎負責"}]}
    assert "version_info" not in cleaned
    units = cleaned["ocs_content"]["ocu_units"]
    assert units[0]["ocu_name"] == "設備維護"
    assert units[0]["tasks"][0] == units[0]["tasks"][1] == units[2]["tasks"][0]
    assert [task.task_id for task in document.tasks] == ["u1-t1", "u1-t2", "u3-t1"]
    assert json.loads(document.chunks[0].text) == {
        "ocs_profile": expected_profile,
        "ocs_attitude": {"attitudes": [{"name": "謹慎負責"}]},
        "notes": cleaned["notes"],
        "scope": "僅適用本規範",
    }
    for chunk in document.chunks[1:]:
        payload = json.loads(chunk.text)
        assert payload["ocs_profile"] == expected_profile
        assert payload["notes"] == cleaned["notes"]
        assert payload["task_group"]["task_codes"] == [{"name": "檢修A320型飛機"}]
        assert payload["task_group"]["competency_blocks"] == [
            {
                "competency_level": 3,
                "outputs": [],
                "indicators": [{"text": "不得低於3.5 mm，至少10件"}],
                "knowledge": [{"name": "K10硬質合金刀具【註1】"}],
                "skills": [{"name": "S45C碳鋼加工"}],
            }
        ]
        assert '"code"' not in chunk.text
    assert '"ocs_code"' not in document.document_text
    assert '"ocu_code"' not in document.document_text
    assert '"code"' not in document.document_text
    assert document.source_utf8 == source_utf8
    assert document.tasks[0].group.task_codes is not None
    assert document.tasks[0].group.task_codes[0].name == "T1.1 檢修A320型飛機"
    assert PREPROCESSING == "ocs_clean_document_v1"


def test_identity_preserves_source_bytes_and_changes_with_source_content() -> None:
    doc = source_document()
    same = build_reference(doc.source_utf8, source_file="renamed.json")
    original_bytes = (doc.source_utf8 + "\r\n").encode("utf-8")
    changed = build_reference(
        original_bytes.decode("utf-8"), source_file=doc.source_file
    )
    assert same.reference_id == doc.reference_id
    assert doc.reference_id == str(
        uuid5(NAMESPACE_URL, f"caliburn:ocs:OC1:{doc.source_sha256}")
    )
    assert changed.reference_id != doc.reference_id
    assert changed.source_utf8.encode("utf-8") == original_bytes
    assert changed.source_sha256 == hashlib.sha256(original_bytes).hexdigest()


@pytest.mark.parametrize(
    "wrapped,expected",
    [
        ("quality\ncontrol", "quality control"),
        ("品質\n管理", "品質管理"),
        ("操作CNC\nmachine", "操作CNC machine"),
        ("CAD\n設計", "CAD設計"),
        ("heat-\ntreatment", "heat-treatment"),
        ("ISO\n9001", "ISO 9001"),
    ],
)
def test_overview_wrapping_keeps_word_boundaries_without_changing_source(
    wrapped: str, expected: str
) -> None:
    source_utf8 = (
        json.dumps(
            {"ocs_profile": {"ocs_code": "OC1", "job_description": wrapped}},
            ensure_ascii=False,
        )
        + "\r\n"
    )
    document = build_reference(source_utf8, source_file="wrapped.json")

    assert (
        json.loads(document.document_text)["ocs_profile"]["job_description"] == expected
    )
    assert (
        json.loads(document.chunks[0].text)["ocs_profile"]["job_description"]
        == expected
    )
    assert document.source.ocs_profile.job_description == wrapped
    assert document.source_utf8 == source_utf8
    assert document.source_sha256 == hashlib.sha256(source_utf8.encode()).hexdigest()


@pytest.mark.parametrize("code", ["", " ", "Unknown"])
def test_source_requires_a_usable_ocs_code(code: str) -> None:
    with pytest.raises(ValueError, match="OCS code"):
        source_document(code)
