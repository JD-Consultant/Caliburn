"""PDF profiles keep occupation categories separate from the reference title."""

from pathlib import Path

import pytest

from caliburn.modules.occupation_reference.infrastructure.pdf.parsers import (
    PDFPlumberParser,
    models,
)
from caliburn.modules.occupation_reference.infrastructure.pdf.transformers import (
    ocs_transformer,
)

PDFS = Path(__file__).parent / "fixtures" / "sample_pdfs"
PROFILE_PDFS = Path(__file__).parent / "fixtures" / "profile_pdfs"


def profile_source(category_row: list[str | None] | None) -> models.PDFDocument:
    rows: list[list[str | None]] = [
        ["職能基準代碼", "APP7322-001v4"],
        ["職業", "3D列印積層製造工程師"],
    ]
    if category_row is not None:
        rows.append(category_row)
    return models.PDFDocument(
        Path("profile.pdf"),
        "snapshot",
        [
            models.PDFPage(
                1,
                "",
                [models.PDFTable(rows, [], (0, 0, 400, 100), 1, 1)],
                [],
                400,
                800,
            )
        ],
    )


@pytest.mark.parametrize(
    ("title", "occupations"),
    [
        (
            "3D列印積層製造工程師",
            [("C2149", "其他工程專業人員"), ("C2144", "機械工程師")],
        ),
        ("3D列印設備配修人員", [("8201", "機械組裝人員")]),
        ("3D珠寶設計人員", [("2173", "產品及服裝設計師")]),
    ],
)
def test_pdf_preserves_occupation_categories_separately_from_title(
    title: str, occupations: list[tuple[str, str]]
) -> None:
    source = PDFPlumberParser().parse(PDFS / f"{title}-職能基準.pdf")
    profile = ocs_transformer.transform_document(source).ocs_profile

    assert profile.ocs_name is not None
    assert profile.ocs_name.occupation_name == title
    assert profile.category is not None and profile.category.occupations
    assert [
        (item.code, item.name) for item in profile.category.occupations
    ] == occupations


@pytest.mark.parametrize(
    ("names", "codes"),
    [
        ("其他工程專業人\n員、機械工程師", "C2149、C2144"),
        ("其他工程專業人員\n機械工程師", "C2149\nC2144"),
    ],
)
def test_profile_preserves_category_names_across_layout_breaks(
    names: str, codes: str
) -> None:
    source = profile_source(["職業別", names, "職業別代碼", codes])
    profile = ocs_transformer.transform_document(source).ocs_profile
    assert profile.category is not None and profile.category.occupations
    assert [(item.code, item.name) for item in profile.category.occupations] == [
        ("C2149", "其他工程專業人員"),
        ("C2144", "機械工程師"),
    ]


@pytest.mark.parametrize("codes", [None, "C2149、C2144、C2145"])
def test_unpaired_categories_keep_the_whole_source_cell(codes: str | None) -> None:
    source = profile_source(
        ["職業別", "其他工程專業人員、機械工程師", "職業別代碼", codes]
    )
    profile = ocs_transformer.transform_document(source).ocs_profile
    assert profile.category is not None and profile.category.occupations
    assert [(item.code, item.name) for item in profile.category.occupations] == [
        ("Unknown", "其他工程專業人員、機械工程師"),
    ]


def test_absent_categories_are_not_replaced_by_reference_title() -> None:
    profile = ocs_transformer.transform_document(profile_source(None)).ocs_profile
    assert profile.ocs_name is not None
    assert profile.ocs_name.occupation_name == "3D列印積層製造工程師"
    assert profile.category is not None
    assert profile.category.occupations == []


@pytest.mark.parametrize(
    ("title", "occupations"),
    [
        (
            "AIoT應用工程師",
            [
                ("21", "科學及工程專業人員"),
                ("2144", "機械工程師"),
                ("2152", "電子工程師"),
                ("2519", "其他軟體、應用程式開發人員及分析師"),
                ("252", "資料庫及網路專業人員"),
                ("2523", "電腦網路專業人員"),
                ("3513", "電腦網路及系統技術員"),
            ],
        ),
        ("供應鏈管理人員", [("1324", "供給、配送及倉儲經理人員")]),
    ],
)
def test_pdf_keeps_punctuation_inside_occupation_category_names(
    title: str, occupations: list[tuple[str, str]]
) -> None:
    source = PDFPlumberParser().parse(PROFILE_PDFS / f"{title}-職能基準.pdf")
    profile = ocs_transformer.transform_document(source).ocs_profile
    assert profile.ocs_name is not None
    assert profile.ocs_name.occupation_name == title
    assert profile.category is not None and profile.category.occupations
    assert [
        (item.code, item.name) for item in profile.category.occupations
    ] == occupations
