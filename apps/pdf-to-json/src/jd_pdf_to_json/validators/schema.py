"""Schema validation."""

import re
import unicodedata

from jd_pdf_to_json.core.models import OCSDocument
from jd_pdf_to_json.parsers.models import PDFDocument
from jd_pdf_to_json.transformers.sections import profile_extractor, version_extractor
from jd_pdf_to_json.transformers.sections.content_extractor import parse_task_codes
from jd_pdf_to_json.transformers.sections.notes_extractor import ITEM_MARKER, PREREQUISITE_HEADER
from jd_pdf_to_json.transformers.support import items as itm
from jd_pdf_to_json.transformers.support import tables as tbl
from jd_pdf_to_json.transformers.support import text as txt
from jd_pdf_to_json.transformers.support.items import extract_task_level
from jd_pdf_to_json.utils.logger import logger


class OCSSchemaValidator:
    """Validate OCS model against schema rules."""

    REQUIRED_KEYS = {
        "version_info",
        "ocs_profile",
        "ocs_content",
        "ocs_attitude",
        "notes",
    }

    def validate(self, model: OCSDocument) -> tuple[bool, list[str]]:
        """Validate model against business rules. Returns (is_valid, error_messages)."""
        errors: list[str] = []
        if not model.ocs_content.ocu_units:
            errors.append("Missing OCS content: no competency units")

        # Rule 1: all top-level keys present
        try:
            missing_keys = self.REQUIRED_KEYS - set(model.model_dump().keys())
            if missing_keys:
                errors.append(f"Missing required keys: {missing_keys}")
        except Exception as e:
            errors.append(f"Failed to check top-level keys: {str(e)}")

        # Rule 2: every competency block must have at least one indicator;
        #         knowledge/skill items must have code and name
        for unit in model.ocs_content.ocu_units:
            if not unit.tasks:
                errors.append(f"OCU {unit.ocu_code}: missing tasks")
            for task in unit.tasks:
                if not task.competency_blocks:
                    errors.append(f"OCU {unit.ocu_code}: missing competency blocks")
                if not task.task_codes:
                    errors.append(f"OCU {unit.ocu_code}: task with empty task_codes")
                    continue
                primary_code = task.task_codes[0].code
                for block_idx, block in enumerate(task.competency_blocks):
                    loc = f"OCU {unit.ocu_code}, Task {primary_code}, Block {block_idx}"
                    if not block.indicators:
                        errors.append(f"{loc}: missing behavioral indicators")
                    for i, item in enumerate(block.knowledge):
                        if not item.code or not item.name:
                            errors.append(f"{loc}: knowledge[{i}] missing code or name")
                    for i, item in enumerate(block.skills):
                        if not item.code or not item.name:
                            errors.append(f"{loc}: skill[{i}] missing code or name")

        # Uncoded source attitude paragraphs legitimately have code=None.
        for i, att in enumerate(model.ocs_attitude.attitudes):
            if not att.name or not att.name.strip():
                errors.append(f"Attitude[{i}]: missing name")

        if errors:
            for error in errors:
                logger.debug(f"  - {error}")

        return len(errors) == 0, errors

    def validate_source(self, source: PDFDocument, model: OCSDocument) -> tuple[bool, list[str]]:
        """Check mapped body cells against the same task and semantic output field.

        Whitespace, punctuation and Unicode width are ignored for this coverage
        check. It cannot certify characters that the PDF extractor itself missed.
        """

        def comparable(text: str) -> str:
            normalized = unicodedata.normalize("NFKC", text).casefold()
            return re.sub(r"[^\w./%+\-]", "", normalized)

        tasks = {
            entry.code: task
            for unit in model.ocs_content.ocu_units
            for task in unit.tasks
            for entry in task.task_codes
        }
        errors = []
        # Use the section owners' interpretation of the fixed extraction data.
        # This checks assembly loss; it is not an independent metadata parser.
        versions = version_extractor.extract_version_info(source)
        if model.version_info != versions:
            errors.append("Version section: parsed source entries missing or changed")
        expected_profile = profile_extractor.extract_profile(source, versions)
        if model.ocs_profile != expected_profile:
            errors.append("Profile section: parsed source fields missing or changed")
        first_text = txt.normalize_text(source.pages[0].text)
        if not versions.versions and all(
            label in first_text for label in ("版本", "職能基準代碼", "職能基準名稱", "狀態")
        ):
            errors.append("Version section: source table signals present but no parsed entries")
        current_codes = []
        for table, rows in tbl.mapped_content_tables(source):
            for row_index, row in enumerate(rows, 1):
                entries = parse_task_codes(row[-1] or "", row[1] or "", row[-1] == row[1])
                if entries:
                    current_codes = [entry.code for entry in entries]
                location = f"page {table.page_number}, table {table.table_number}, body row {row_index}, task {current_codes}"
                missing = [code for code in current_codes if code not in tasks]
                if missing:
                    errors.append(f"{location}: missing source task codes {missing}")
                for entry in entries:
                    if entry.code in tasks:
                        actual_entry = next(
                            item for item in tasks[entry.code].task_codes if item.code == entry.code
                        )
                        if comparable(entry.name or "") not in comparable(actual_entry.name or ""):
                            errors.append(f"{location}: missing task_name text for {entry.code}")
                matching = [tasks[code] for code in current_codes if code in tasks]
                if len({id(task) for task in matching}) > 1:
                    errors.append(
                        f"{location}: source task codes split across unrelated task groups"
                    )
                if not matching:
                    errors.append(f"{location}: missing source task")
                    continue
                unique_tasks = {id(task): task for task in matching}.values()
                blocks = [block for task in unique_tasks for block in task.competency_blocks]
                if (
                    not entries
                    and row[1]
                    and comparable(row[1])
                    not in comparable(
                        "".join(entry.name or "" for task in matching for entry in task.task_codes)
                    )
                ):
                    errors.append(f"{location}: missing task_name continuation")
                level = extract_task_level(row, {"level": 4})
                if level is not None and not any(
                    block.competency_level == level for block in blocks
                ):
                    errors.append(f"{location}: missing source level {level}")
                # Items from one source row belong to the same competency block.
                # The leading fragment of a continuation cell is checked below
                # against the task; its newly coded items bind to this row/block.
                row_items = (
                    ("indicators", "text", itm.extract_behavioral_indicators(row[3])),
                    ("outputs", "name", itm.extract_output_items(row[2])),
                    ("knowledge", "name", itm.extract_competency_items(row[5], "K")),
                    ("skills", "name", itm.extract_competency_items(row[6], "S")),
                )
                for attribute, body, extracted in row_items:
                    field = "behavioral" if attribute == "indicators" else attribute
                    for item in extracted:
                        if item.code is None:
                            continue
                        if not any(
                            item.code == actual.code
                            and comparable(getattr(item, body) or "")
                            in comparable(getattr(actual, body) or "")
                            for block in blocks
                            for actual in getattr(block, attribute)
                        ):
                            errors.append(f"{location}: uncovered {field} item {item.code}")
                candidates = []
                for block in blocks:
                    if level is not None and block.competency_level != level:
                        continue
                    if all(
                        all(
                            any(
                                item.code == actual.code
                                and comparable(getattr(item, body) or "")
                                in comparable(getattr(actual, body) or "")
                                for actual in getattr(block, attribute)
                            )
                            for item in extracted
                            if item.code is not None
                        )
                        for attribute, body, extracted in row_items
                    ):
                        candidates.append(block)
                if not candidates:
                    errors.append(f"{location}: source items do not match one competency block")
                for field, column, attribute, body_attribute in (
                    ("outputs", 2, "outputs", "name"),
                    ("behavioral", 3, "indicators", "text"),
                    ("knowledge", 5, "knowledge", "name"),
                    ("skills", 6, "skills", "name"),
                ):
                    raw = txt.normalize_code_spacing(row[column] or "")
                    if not raw.strip():
                        continue
                    actual = "".join(
                        (item.code or "") + (getattr(item, body_attribute) or "")
                        for block in blocks
                        for item in getattr(block, attribute)
                    )
                    patterns = {
                        "outputs": r"O\d+(?:[-.]\d+)*|0\d+(?:[-.]\d+)+",
                        "behavioral": r"[PT]\.?\d+(?:[-.]\d+)*",
                        "knowledge": r"[KS]\d+(?:[-.]\d+)*",
                        "skills": r"[KS]\d+(?:[-.]\d+)*",
                    }
                    first_code = re.search(patterns[field], raw, re.IGNORECASE)
                    # Coded bodies are checked against one block above. Check
                    # the uncoded leading fragment separately; repeated source
                    # items may legally collapse to a single identical item.
                    fragment = raw[: first_code.start()] if first_code else raw
                    if comparable(fragment) and comparable(fragment) not in comparable(actual):
                        errors.append(f"{location}: uncovered {field} text")
        attitude_lines = txt.section_lines(
            source, "職能內涵", end="說明與補充", qualifier="attitude"
        )
        attitude_output = "".join(
            (item.code or "") + (item.name or "") for item in model.ocs_attitude.attitudes
        )
        for line in attitude_lines:
            if comparable(line) and comparable(line) not in comparable(attitude_output):
                errors.append("Attitude section: uncovered source text")
        note_output = "".join(model.notes.prerequisites + model.notes.supplements)
        for line in txt.section_lines(source, "說明與補充"):
            if PREREQUISITE_HEADER.search(line):
                continue
            if "其他補充說明" in line:
                line = re.split(r"[：:]", line, maxsplit=1)[-1] if re.search(r"[：:]", line) else ""
            body = ITEM_MARKER.sub("", line)
            if comparable(body) and comparable(body) not in comparable(note_output):
                errors.append("Notes section: uncovered source text")
        return not errors, errors
