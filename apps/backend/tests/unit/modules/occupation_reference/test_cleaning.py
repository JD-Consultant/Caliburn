"""Cleaning retains source relationships while removing retrieval noise."""

import pytest
from ocs_contract.models import OCSDocument

from caliburn.modules.occupation_reference.domain.cleaning import (
    clean_document,
    clean_text,
)


@pytest.mark.parametrize(
    "source,expected",
    [
        (
            "T1.1 評選與建置\n3D列印設\n備、環境\n及安全",
            "評選與建置3D列印設備、環境及安全",
        ),
        ("quality\ncontrol", "quality control"),
        ("架設系統(boardbring\nup）", "架設系統(boardbring up）"),
        (
            "不得低於3.5 mm，至少10件，依據客戶需求",
            "不得低於3.5 mm，至少10件，依據客戶需求",
        ),
        ("1. 檢查設備\n2. 記錄結果", "1. 檢查設備\n2. 記錄結果"),
        ("第一段。\n\n第二段。", "第一段。\n\n第二段。"),
        ("珠寶屬性相關知識【註1】", "珠寶屬性相關知識【註1】"),
        ("【註1】知識說明\n【註2】技能說明", "【註1】知識說明\n【註2】技能說明"),
        ("工作內容\n知識\n技能", "工作內容知識技能"),
        ("操作\u00a0 ISO  9001\u200b", "操作 ISO 9001"),
        ("T2.2.1信用卡相關法令彙整及遵循情況", "信用卡相關法令彙整及遵循情況"),
        ("3D列印原理與ME及VP設備", "3D列印原理與ME及VP設備"),
        ("A320型飛機檢修", "A320型飛機檢修"),
        ("S45C碳鋼加工", "S45C碳鋼加工"),
        ("K10硬質合金刀具", "K10硬質合金刀具"),
        ("T1.12A型模組", "T1.12A型模組"),
        (
            "職業別（職業代碼）：研究發展經理人員（1223） 機械工程師（2144）",
            "職業別：研究發展經理人員、機械工程師",
        ),
        ("材料（至少10件），依註1執行", "材料（至少10件），依註1執行"),
    ],
)
def test_clean_text_preserves_words_numbers_and_note_boundaries(
    source: str, expected: str
) -> None:
    assert clean_text(source) == expected


def test_clean_document_keeps_shared_groups_blocks_notes_and_source() -> None:
    document = OCSDocument.model_validate(
        {
            "version_info": {"versions": [{"version": "V1"}]},
            "ocs_profile": {
                "ocs_code": "APP1",
                "ocs_name": {"occupation_name": "3D工程師"},
                "category": {"occupations": [{"code": "2144", "name": "機械工程師"}]},
                "ocs_level": 4,
            },
            "ocs_content": {
                "ocu_units": [
                    {
                        "ocu_code": "T1",
                        "ocu_name": "設備維護",
                        "tasks": [
                            {
                                "task_codes": [
                                    {"code": "T1.1", "name": "檢查設備"},
                                    {"code": "T1.2", "name": "修理設備"},
                                ],
                                "competency_blocks": [
                                    {
                                        "competency_level": 3,
                                        "outputs": [{"code": "O1.1.1", "name": "產品"}],
                                        "knowledge": [
                                            {"code": "K01", "name": "原理【註1】"}
                                        ],
                                    },
                                    {
                                        "competency_level": None,
                                        "outputs": [{"code": None, "name": "產品"}],
                                        "skills": [{"code": "S01", "name": "S01 檢修"}],
                                    },
                                ],
                            }
                        ],
                    }
                ]
            },
            "notes": {"supplements": ["【註1】設備原理及其限制。"]},
        }
    )
    before = document.model_dump_json()

    cleaned = clean_document(document)

    assert "version_info" not in cleaned
    assert cleaned["ocs_profile"] == {
        "ocs_name": {"occupation_name": "3D工程師"},
        "category": {
            "job_categories": [],
            "occupations": [{"name": "機械工程師"}],
            "industries": [],
        },
        "ocs_level": 4,
    }
    assert cleaned["ocs_content"] == {
        "ocu_units": [
            {
                "ocu_name": "設備維護",
                "tasks": [
                    {
                        "task_codes": [{"name": "檢查設備"}, {"name": "修理設備"}],
                        "competency_blocks": [
                            {
                                "competency_level": 3,
                                "indicators": [],
                                "outputs": [{"name": "產品"}],
                                "knowledge": [{"name": "原理【註1】"}],
                                "skills": [],
                            },
                            {
                                "competency_level": None,
                                "indicators": [],
                                "outputs": [{"name": "產品"}],
                                "knowledge": [],
                                "skills": [{"name": "檢修"}],
                            },
                        ],
                    }
                ],
            }
        ]
    }
    assert cleaned["notes"] == {
        "prerequisites": [],
        "supplements": ["【註1】設備原理及其限制。"],
    }
    assert document.model_dump_json() == before


@pytest.mark.parametrize(
    "source,expected",
    [
        (
            "陶瓷製土-T2.1.1陶瓷配土－T2.1.2\n陶瓷練土",
            "陶瓷製土\n\n陶瓷配土\n\n陶瓷練土",
        ),
        ("財務控管T4.3.\n成本控管", "財務控管\n\n成本控管"),
        ("樣品組裝T2.2.樣品\n測試及調\n校", "樣品組裝\n\n樣品測試及調校"),
        ("確認【T1.1】及（T2.2）程序", "確認【T1.1】及（T2.2）程序"),
        ("測試T1.1A型模組", "測試T1.1A型模組"),
    ],
)
def test_clean_document_retains_embedded_tasks_as_text_paragraphs(
    source: str, expected: str
) -> None:
    document = OCSDocument.model_validate(
        {
            "ocs_profile": {"ocs_code": "TEST"},
            "ocs_content": {
                "ocu_units": [
                    {"tasks": [{"task_codes": [{"code": "T2.1", "name": source}]}]}
                ]
            },
        }
    )

    cleaned = clean_document(document)

    assert cleaned["ocs_content"] == {
        "ocu_units": [
            {
                "tasks": [
                    {
                        "task_codes": [{"name": expected}],
                        "competency_blocks": [],
                    }
                ]
            }
        ]
    }
