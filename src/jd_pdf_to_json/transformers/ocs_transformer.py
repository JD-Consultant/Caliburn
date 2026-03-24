"""OCS PDF → OCSDocument transformer implementation."""

import re
from typing import Optional, Dict, List, Any
from datetime import datetime

import pdfplumber

from jd_pdf_to_json.core.models import (
    OCSDocument,
    VersionInfo,
    VersionEntry,
    OCSProfile,
    OCSName,
    OCSCategory,
    CategoryItem,
    OCSUnit,
    Task,
    OutputItem,
    BehavioralIndicator,
    CompetencyItem,
    Attitude,
    Requirement,
    OCSContent,
    OCSAttitude,
    NotesAndAppendix,
)
from jd_pdf_to_json.transformers.base import BaseOCSTransformer
from jd_pdf_to_json.utils.exceptions import TransformationError
from jd_pdf_to_json.utils.logger import logger


class OCSTransformer(BaseOCSTransformer):
    """Transform PDF raw data into OCSDocument model."""

    def __init__(self):
        """Initialize transformer."""
        self.logger = logger

    def transform(self, raw_data: dict) -> OCSDocument:
        """
        Transform raw PDF data into structured OCS model.

        Args:
            raw_data: Dict with keys:
                - 'file_path': str (path to PDF)
                - 'metadata': dict (from parser)
                - 'pages': list (from parser)

        Returns:
            Validated OCSDocument model

        Raises:
            TransformationError: If transformation fails
        """
        try:
            file_path = raw_data.get("file_path", "")
            metadata = raw_data.get("metadata", {})

            self.logger.info(f"開始轉換: {file_path}")

            with pdfplumber.open(file_path) as pdf:
                # 1. 提取版本信息（通常在第一頁）
                version_info = self._extract_version_info(pdf)
                self.logger.debug(f"✓ 版本信息: {len(version_info.versions)} 筆紀錄")

                # 2. 提取 OCS Profile 信息
                ocs_profile = self._extract_profile(pdf, version_info)
                self.logger.debug(f"✓ Profile: {ocs_profile.ocs_code}")

                # 3. 提取 OCU 內容（任務、產出、知識、技能等）
                ocs_content = self._extract_content(pdf, ocs_profile)
                self.logger.debug(
                    f"✓ 內容: {len(ocs_content.ocu_units)} 個職能單元"
                )

                # 4. 提取態度信息
                ocs_attitude = self._extract_attitude(pdf)
                self.logger.debug(f"✓ 態度: {len(ocs_attitude.attitudes)} 個態度")

                # 5. 提取說明與補充
                notes_appendix = self._extract_notes_and_appendix(pdf)
                self.logger.debug(
                    f"✓ 補充: {len(notes_appendix.requirements)} 項建議"
                )

                # 組合成完整的 OCSDocument
                doc = OCSDocument(
                    version_info=version_info,
                    ocs_profile=ocs_profile,
                    ocs_content=ocs_content,
                    ocs_attitude=ocs_attitude,
                    notes_and_appendix=notes_appendix,
                )

                self.logger.info(f"✓ 轉換完成: {ocs_profile.ocs_code}")
                return doc

        except Exception as e:
            self.logger.error(f"✗ 轉換失敗: {str(e)}")
            raise TransformationError(f"Failed to transform PDF: {str(e)}") from e

    def _extract_version_info(self, pdf) -> VersionInfo:
        """提取版本歷史信息（通常在第一頁表格）。"""
        versions = []

        try:
            first_page = pdf.pages[0]
            tables = first_page.extract_tables()

            if not tables:
                self.logger.warning("未找到版本表格，version_info.versions 將為空")
                return VersionInfo(versions=versions)

            # 遍歷表格尋找版本信息
            for table in tables:
                # 版本表格通常有欄位: 版本, 職能基準代碼, 職能基準名稱, 狀態, 更新說明, 發展更新日期
                for row in table:
                    if len(row) >= 4 and row[0] and "V" in str(row[0]):
                        version_record = VersionEntry(
                            version=str(row[0]).strip(),
                            ocs_code=str(row[1]).strip() if row[1] else "Unknown",
                            ocs_name=str(row[2]).strip() if row[2] else "Unknown",
                            status=str(row[3]).strip() if row[3] else "Unknown",
                            update_note=str(row[4]).strip() if len(row) > 4 and row[4] else None,
                            update_date=str(row[5]).strip() if len(row) > 5 and row[5] else "Unknown",
                        )
                        versions.append(version_record)

        except Exception as e:
            self.logger.warning(f"版本提取失敗: {str(e)}")

        return VersionInfo(versions=versions)

    def _extract_first_code(self, text: str) -> Optional[str]:
        """從文本中提取第一個職能代碼（格式：ABC123-001v1）。"""
        match = re.search(r"[A-Z]{2,}[\d]+-\d+[vV]\d+", text)
        return match.group(0) if match else None

    def _extract_profile(self, pdf, version_info: VersionInfo) -> OCSProfile:
        """提取 OCS Profile 信息（職能代碼、名稱、職類別等）。"""
        try:
            first_page = pdf.pages[0]
            text = first_page.extract_text() or ""
            tables = first_page.extract_tables() or []

            # 取第一個版本的代碼和名稱
            ocs_code = (
                version_info.versions[0].ocs_code
                if version_info.versions
                else "Unknown"
            )
            ocs_name_str = (
                version_info.versions[0].ocs_name
                if version_info.versions
                else "Unknown"
            )

            # 尋找職類別、職業等信息
            job_categories = []
            occupations = []
            industries = []

            # 簡單的提取邏輯：尋找 Profile 表格
            for table in tables:
                for row in table:
                    row_str = " ".join(
                        [str(cell).strip() for cell in row if cell]
                    )

                    # 提取職類別
                    if "職類別" in row_str and len(row) >= 2:
                        for i, cell in enumerate(row):
                            if cell and "職類別" in str(cell):
                                if i + 1 < len(row) and row[i + 1]:
                                    cat_name = str(row[i + 1]).strip()
                                    cat_code = self._extract_category_code(
                                        cat_name
                                    )
                                    if cat_name and cat_name not in [
                                        c.name for c in job_categories
                                    ]:
                                        job_categories.append(
                                            CategoryItem(
                                                name=cat_name, code=cat_code
                                            )
                                        )

                    # 提取職業
                    if "職業" in row_str and len(row) >= 2:
                        for i, cell in enumerate(row):
                            if (
                                cell
                                and "職業" in str(cell)
                                and "職業別代碼" not in str(cell)
                            ):
                                if i + 1 < len(row) and row[i + 1]:
                                    occ_name = str(row[i + 1]).strip()
                                    occ_code = self._extract_occupation_code(
                                        text, occ_name
                                    )
                                    if occ_name and occ_name not in [
                                        o.name for o in occupations
                                    ]:
                                        occupations.append(
                                            CategoryItem(
                                                name=occ_name, code=occ_code
                                            )
                                        )

            # 若未提取到職業，使用版本名稱
            if not occupations:
                occupations.append(
                    CategoryItem(name=ocs_name_str, code=ocs_code.split("-")[0])
                )

            profile = OCSProfile(
                ocs_code=ocs_code,
                ocs_name=OCSName(
                    job_category_name=job_categories[0].name
                    if job_categories
                    else None,
                    occupation_name=occupations[0].name if occupations else None,
                ),
                category=OCSCategory(
                    job_categories=job_categories,
                    occupations=occupations,
                    industries=industries,
                ),
                job_description="",  # 通常需要手動從文本中提取
                ocs_level=3,  # 預設級別
            )

            return profile

        except Exception as e:
            self.logger.warning(f"Profile 提取失敗: {str(e)}")
            return OCSProfile(
                ocs_code="Unknown",
                ocs_name=OCSName(
                    job_category_name=None, occupation_name="Unknown"
                ),
                category=OCSCategory(
                    job_categories=[], occupations=[], industries=[]
                ),
                job_description="",
                ocs_level=3,
            )

    def _extract_category_code(self, cat_name: str) -> str:
        """從職類別名稱或文本中提取代碼。"""
        # 簡單的啟發式方法：如果名稱包含代碼格式，提取出來
        match = re.search(r"[A-Z]{2,}", cat_name)
        return match.group(0) if match else "Unknown"

    def _extract_occupation_code(self, text: str, occ_name: str) -> str:
        """From text extract occupation code related to occupation name."""
        # 簡單方法：尋找職業別代碼
        pattern = r"職業別代碼\s*(\d+)"
        match = re.search(pattern, text)
        return match.group(1) if match else "Unknown"

    def _extract_content(
        self, pdf, ocs_profile: OCSProfile
    ) -> OCSContent:
        """提取 OCU 內容（任務、產出、行為指標、知識、技能等）。"""
        ocu_units = []

        try:
            # OCU 內容通常從第二頁開始（跳過第一頁的 Profile）
            # 每個 OCU 單元通常是一個表格，包含: 職能單元代碼、職能單元名稱、任務列表

            for page_idx in range(
                1, len(pdf.pages)
            ):  # 從第二頁開始
                page = pdf.pages[page_idx]

                # 檢查是否為態度或補充部分（通常不再有 OCU 內容）
                text = page.extract_text() or ""
                if "態度" in text or "說明與補充" in text:
                    break

                tables = page.extract_tables() or []
                for table in tables:
                    ocu = self._parse_ocu_table(table)
                    if ocu:
                        ocu_units.append(ocu)

        except Exception as e:
            self.logger.warning(f"OCU 內容提取失敗: {str(e)}")

        return OCSContent(ocu_units=ocu_units)

    def _parse_ocu_table(self, table: List[List[Any]]) -> Optional[OCSUnit]:
        """解析單個 OCU 表格。"""
        if not table or len(table) < 2:
            return None

        try:
            # 表通常有: OCU代碼, OCU名稱, 任務代碼, 任務名稱, 產出, 行為指標, 知識(K), 技能(S)
            # 簡化版本：提取第一行作為 OCU 頭部

            header = table[0]
            ocu_code = str(header[0]).strip() if header[0] else "T0"
            ocu_name = str(header[1]).strip() if len(header) > 1 else "Unknown"

            # 提取任務列表
            tasks = []
            for row in table[1:]:
                if not row or not row[0]:
                    continue

                task_code = str(row[0]).strip()
                task_name = str(row[1]).strip() if len(row) > 1 else ""

                # 提取產出 (O開頭)
                outputs = []
                for col in row:
                    if col and isinstance(col, str) and col.strip().startswith(
                        "O"
                    ):
                        outputs.append(
                            OutputItem(
                                output_code=col.strip(),
                                output_name="",
                            )
                        )

                # 提取知識 (K開頭)
                knowledge = []
                for col in row:
                    if col and isinstance(col, str) and col.strip().startswith(
                        "K"
                    ):
                        knowledge.append(
                            CompetencyItem(code=col.strip(), name=col.strip())
                        )

                # 提取技能 (S開頭)
                skills = []
                for col in row:
                    if col and isinstance(col, str) and col.strip().startswith(
                        "S"
                    ):
                        skills.append(
                            CompetencyItem(code=col.strip(), name=col.strip())
                        )

                if task_code:
                    task = Task(
                        task_code=task_code,
                        task_name=task_name,
                        outputs=outputs,
                        behavioral_indicators=[],  # 通常需要單獨提取
                        competency_level=3,  # 預設級別
                        knowledge_k=knowledge,
                        skills_s=skills,
                    )
                    tasks.append(task)

            if tasks:
                return OCSUnit(
                    ocu_code=ocu_code,
                    ocu_name=ocu_name,
                    tasks=tasks,
                )

        except Exception as e:
            self.logger.warning(f"OCU 表解析失敗: {str(e)}")

        return None

    def _extract_attitude(self, pdf) -> OCSAttitude:
        """提取態度信息。"""
        attitudes = []

        try:
            full_text = "".join(
                [page.extract_text() or "" for page in pdf.pages]
            )

            # 尋找態度部分（A01, A02, ...）
            attitude_pattern = (
                r"A(\d+)\s*([^A\n]*?)(?=A\d+|說明與補充|$)"
            )
            matches = re.finditer(attitude_pattern, full_text, re.DOTALL)

            for match in matches:
                att_code = "A" + match.group(1)
                att_text = match.group(2).strip()

                # 分離名稱和描述
                lines = att_text.split("\n")
                att_name = lines[0] if lines else att_code
                att_description = "\n".join(
                    lines[1:]
                ) if len(lines) > 1 else None

                attitudes.append(
                    Attitude(
                        attitude_code=att_code,
                        attitude_name=att_name,
                        attitude_description=att_description,
                    )
                )

        except Exception as e:
            self.logger.warning(f"態度提取失敗: {str(e)}")

        return OCSAttitude(attitudes=attitudes)

    def _extract_notes_and_appendix(self, pdf) -> NotesAndAppendix:
        """提取說明與補充部分。"""
        requirements = []

        try:
            # 在最後幾頁尋找說明與補充
            full_text = "".join(
                [page.extract_text() or "" for page in pdf.pages]
            )

            # 尋找 "說明與補充事項" 之後的內容
            notes_start = full_text.find("說明與補充")
            if notes_start != -1:
                notes_text = full_text[notes_start:]

                # 簡單地將 bullets 分離為建議
                lines = notes_text.split("\n")
                for line in lines[1:]:  # 跳過標題
                    line = line.strip()
                    if line and not line.startswith("第"):
                        # 這是一項建議
                        requirements.append(
                            Requirement(
                                category="建議",
                                content=line,
                                notes=None,
                            )
                        )

        except Exception as e:
            self.logger.warning(f"補充信息提取失敗: {str(e)}")

        return NotesAndAppendix(requirements=requirements)
