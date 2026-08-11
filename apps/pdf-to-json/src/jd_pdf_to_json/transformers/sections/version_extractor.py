"""Version-history extractor (moved verbatim from OCSTransformer, Phase 3b)."""

from typing import Dict, Optional

from jd_pdf_to_json.core.models import VersionEntry, VersionInfo
from jd_pdf_to_json.transformers.support import tables as tbl
from jd_pdf_to_json.utils.logger import logger

VERSION_HEADER_ALIASES: Dict[str, list] = {
    "version": ["版本", "version"],
    "ocs_code": ["職能基準代碼", "職能代碼", "ocscode"],
    "ocs_name": ["職能基準名稱", "職能名稱", "ocsname"],
    "status": ["狀態", "status"],
    "update_note": ["更新說明", "修訂內容", "備註", "note"],
    "update_date": ["發展更新日期", "更新日期", "date"],
}


def extract_version_info(pdf) -> VersionInfo:
    """Extract version history from the first-page table."""
    versions = []
    try:
        tables = pdf.pages[0].extract_tables()
        if not tables:
            logger.warning("未找到版本表格，version_info.versions 將為空")
            return VersionInfo(versions=versions)

        for table in tables:
            header_idx: Optional[int] = None
            header_map: Dict[str, int] = {}
            for row_idx, row in enumerate(table):
                current_map = tbl.build_column_map(row, VERSION_HEADER_ALIASES)
                if all(k in current_map for k in ("version", "ocs_code", "ocs_name", "status")):
                    header_idx = row_idx
                    header_map = current_map
                    break

            if header_idx is None:
                continue

            for row in table[header_idx + 1 :]:
                version_idx = header_map.get("version")
                version_val = (
                    tbl.find_cell_value(row, version_idx) or ""
                    if version_idx is not None
                    else ""
                )
                if not version_val:
                    continue
                versions.append(
                    VersionEntry(
                        version=version_val,
                        ocs_code=tbl.find_cell_value(row, header_map["ocs_code"]) or "Unknown",
                        ocs_name=tbl.find_cell_value(row, header_map["ocs_name"]) or "Unknown",
                        status=tbl.find_cell_value(row, header_map["status"]) or "Unknown",
                        update_note=(
                            tbl.find_cell_value(row, header_map["update_note"])
                            if "update_note" in header_map
                            else None
                        ),
                        update_date=(
                            tbl.find_cell_value(row, header_map["update_date"]) or "Unknown"
                            if "update_date" in header_map
                            else "Unknown"
                        ),
                    )
                )

    except Exception as e:
        logger.warning(f"版本提取失敗: {str(e)}")

    return VersionInfo(versions=versions)
