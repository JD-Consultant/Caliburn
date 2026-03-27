"""Tests for header-driven OCU table parsing."""

from jd_pdf_to_json.transformers.ocs_transformer import OCSTransformer


def test_normalize_text_handles_spaces_and_fullwidth() -> None:
    transformer = OCSTransformer()

    assert transformer._normalize_text(" 知識（ K ）\n") == "知識k"
    assert transformer._normalize_text("工作 任務 代碼") == "工作任務代碼"


def test_parse_ocu_table_with_header_mapping() -> None:
    transformer = OCSTransformer()

    table = [
        ["職能單元代碼", "AIOT-01", "職能單元名稱", "感測資料蒐集"],
        ["技能(S)", "工作任務", "工作產出", "工作任務代碼", "知識(K)", "行為指標"],
        [
            "S01 設備安裝\nS02 系統設定",
            "佈建感測端到資料平台",
            "O01 佈建完成",
            "T1",
            "K01 網路基礎\nK02 通訊協定",
            "P01 遵循流程",
        ],
    ]

    ocu = transformer._parse_ocu_table(table)

    assert ocu is not None
    assert ocu.ocu_code == "AIOT-01"
    assert ocu.ocu_name == "感測資料蒐集"
    assert len(ocu.tasks) == 1

    task = ocu.tasks[0]
    assert task.task_code == "T1"
    assert task.task_name == "佈建感測端到資料平台"
    assert [k.code for k in task.knowledge_k] == ["K01", "K02"]
    assert [s.code for s in task.skills_s] == ["S01", "S02"]
    assert [o.output_code for o in task.outputs] == ["O01"]
    assert [p.indicator_code for p in task.behavioral_indicators] == ["P01"]


def test_extract_competency_items_preserves_leading_digit_in_name() -> None:
    transformer = OCSTransformer()

    items = transformer._extract_competency_items(
        "S01 3D列印技術類型辨識能力\nS02 3D列印設備組裝與拆解能力",
        "S",
    )

    assert [item.code for item in items] == ["S01", "S02"]
    assert [item.name for item in items] == [
        "3D列印技術類型辨識能力",
        "3D列印設備組裝與拆解能力",
    ]
