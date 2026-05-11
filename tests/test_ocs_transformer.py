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

    units = transformer._parse_ocu_table_units(table)

    assert len(units) == 1
    ocu = units[0]
    assert ocu.ocu_code == "AIOT-01"
    assert ocu.ocu_name == "感測資料蒐集"
    assert len(ocu.tasks) == 1

    task = ocu.tasks[0]
    assert task.task_code == "T1"
    assert task.task_name == "佈建感測端到資料平台"
    assert len(task.competency_blocks) == 1
    block = task.competency_blocks[0]
    assert [k.code for k in block.knowledge_k] == ["K01", "K02"]
    assert [s.code for s in block.skills_s] == ["S01", "S02"]
    assert [o.output_code for o in block.outputs] == ["O01"]
    assert [p.indicator_code for p in block.indicators] == ["P01"]


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


def test_detect_table_type_for_fixed_templates() -> None:
    transformer = OCSTransformer()

    content_table = [
        ["主要職責", "工作任務", "工作產出", "行為指標", "職能級別", "職能內涵（K=knowledge知識）", "職能內涵（S=skills技能）"],
        ["T1", "T1.1測試", "O1.1.1產出", "P1.1.1指標", "4", "K01知識", "S01技能"],
    ]
    attitude_table = [
        ["職能內涵（A=attitude態度）"],
        ["A01主動積極。"],
    ]

    assert transformer._detect_table_type(content_table) == "ocs_content"
    assert transformer._detect_table_type(attitude_table) == "ocs_attitude"


def test_parse_ocu_table_keeps_multiple_p_codes_in_one_block() -> None:
    transformer = OCSTransformer()

    table = [
        ["主要職責", "工作任務", "工作產出", "行為指標", "職能級別", "職能內涵（K=knowledge知識）", "職能內涵（S=skills技能）"],
        [
            "T5系統更新與維護",
            "T5.1AiOT系統更新與維護",
            "O5.1.2系統導入與升級建置計畫書",
            "P5.1.2有效規劃 AiOT 系統導入與升級步驟，確保新舊系統能無縫接軌。\nP5.1.3評估與採用各式備援與高可靠性（HA）機制，定義系統服務層級協議（SLA）。",
            "5",
            "K15專案風險評估概念\nK16專案管理知識\nK38雲端備援與HA機制\nK39雲端彈性擴展知識",
            "S11專案提案簡報及計畫書撰寫能力\nS28系統備援方案評估與導入策略\nS37操作手冊撰寫能力",
        ],
    ]

    units = transformer._parse_ocu_table_units(table)

    assert len(units) == 1
    task = units[0].tasks[0]
    assert len(task.competency_blocks) == 1
    assert [p.indicator_code for p in task.competency_blocks[0].indicators] == ["P5.1.2", "P5.1.3"]
    assert task.competency_blocks[0].competency_level == 5
def test_parse_ocu_table_continuation_row_without_task_code() -> None:
    transformer = OCSTransformer()

    merged_table = [
        ["主要職責", "工作任務", "工作產出", "行為指標", "職能級別", "職能內涵（K=knowledge知識）", "職能內涵（S=skills技能）"],
        [
            "T1參與規劃",
            "T1.1需求分析",
            "O1.1.1需求分析表",
            "P1.1.1完成需求盤點",
            "4",
            "K01演出需求知識",
            "S01合作協調",
        ],
        [
            "",
            "",
            "",
            "",
            "4",
            "K02製作組織知識",
            "S02時間管理",
        ],
    ]

    units = transformer._parse_ocu_table_units(merged_table)

    assert len(units) == 1
    assert units[0].ocu_code == "T1"
    assert len(units[0].tasks) == 1
    task = units[0].tasks[0]
    assert task.task_code == "T1.1"
    assert len(task.competency_blocks) == 1
    assert [k.code for k in task.competency_blocks[0].knowledge_k] == ["K01", "K02"]
    assert [s.code for s in task.competency_blocks[0].skills_s] == ["S01", "S02"]


def test_parse_ocu_table_continuation_tail_text_without_codes() -> None:
    transformer = OCSTransformer()

    merged_table = [
        ["主要職責", "工作任務", "工作產出", "行為指標", "職能級別", "職能內涵（K=knowledge知識）", "職能內涵（S=skills技能）"],
        [
            "T1參與規劃",
            "T1.2對潛在資安問題進行發掘及",
            "O1.2.1總行資訊安全評估報告",
            "P1.2.1評估現有資訊安全執行方式之合理",
            "4",
            "K04金融市場",
            "S24資訊科技應用能力",
        ],
        [
            "",
            "影響評估",
            "",
            "性、有效性及必要性。",
            "4",
            "",
            "",
        ],
    ]

    units = transformer._parse_ocu_table_units(merged_table)

    assert len(units) == 1
    assert len(units[0].tasks) == 1
    task = units[0].tasks[0]
    assert task.task_name == "對潛在資安問題進行發掘及影響評估"
    assert task.competency_blocks[0].indicators[0].indicator_text == "評估現有資訊安全執行方式之合理性、有效性及必要性。"
