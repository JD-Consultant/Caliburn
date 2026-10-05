"""Content extractor: OCU units, tasks, competency blocks (Phase 3b).

The largest section. Moved from OCSTransformer: extract_content drives table
discovery/merge; parse_ocu_table_units does the row-by-row assembly;
parse_task_codes splits combined task-code cells.
"""

import re
from typing import Any

from jd_pdf_to_json.core.models import (
    CompetencyBlock,
    CompetencyItem,
    OCSContent,
    OCSUnit,
    Task,
    TaskCodeEntry,
)
from jd_pdf_to_json.transformers.support import dedupe as dd
from jd_pdf_to_json.transformers.support import items as itm
from jd_pdf_to_json.transformers.support import scanning as scan
from jd_pdf_to_json.transformers.support import tables as tbl
from jd_pdf_to_json.transformers.support import text as txt
from jd_pdf_to_json.utils.exceptions import TransformationError


def extract_content(pdf) -> OCSContent:
    """Extract OCU units: tasks, outputs, behavioral indicators, K/S competencies."""
    ocu_units: list[OCSUnit] = []
    known_ocu_names: dict[str, str] = {}

    try:
        merged_content_rows = []
        for _table, rows in tbl.mapped_content_tables(pdf):
            merged_content_rows.extend(rows)

        if merged_content_rows:
            merged_table = [tbl.CANONICAL_HEADER] + merged_content_rows
            parsed_units = (
                parse_ocu_table_units(merged_table)
                if tbl.is_ocu_candidate_table(merged_table)
                else []
            )

            for unit in parsed_units:
                if re.fullmatch(r"T\d+", unit.ocu_code) and not scan.is_generic_unit_name(
                    unit.ocu_name
                ):
                    known_ocu_names[unit.ocu_code] = unit.ocu_name

                if not re.fullmatch(r"T\d+", unit.ocu_code) or scan.is_generic_unit_name(
                    unit.ocu_name
                ):
                    grouped: dict[str, list[Task]] = {}
                    for task in unit.tasks:
                        primary_code = task.task_codes[0].code if task.task_codes else ""
                        match = re.match(r"(T\d+)", primary_code)
                        ocu_code = match.group(1) if match else unit.ocu_code
                        grouped.setdefault(ocu_code, []).append(task)

                    for ocu_code, tasks in grouped.items():
                        fallback_name = (
                            unit.ocu_name
                            if not scan.is_generic_unit_name(unit.ocu_name)
                            else "Unknown"
                        )
                        scan.merge_ocu_unit(
                            OCSUnit(
                                ocu_code=ocu_code,
                                ocu_name=known_ocu_names.get(ocu_code, fallback_name),
                                tasks=tasks,
                            ),
                            ocu_units,
                        )
                else:
                    scan.merge_ocu_unit(unit, ocu_units)

        if any(scan.is_generic_unit_name(u.ocu_name) for u in ocu_units):
            text_ocu_names = scan.scan_ocu_names_from_text(pdf)
            for unit in ocu_units:
                if scan.is_generic_unit_name(unit.ocu_name) and unit.ocu_code in text_ocu_names:
                    unit.ocu_name = text_ocu_names[unit.ocu_code]

        if any(
            entry.name == ""
            for unit in ocu_units
            for task in unit.tasks
            for entry in task.task_codes
        ):
            text_task_names = scan.scan_task_names_from_words(pdf)
            for unit in ocu_units:
                for task in unit.tasks:
                    for entry in task.task_codes:
                        if entry.name == "" and entry.code in text_task_names:
                            entry.name = text_task_names[entry.code]

    except Exception as e:
        raise TransformationError(f"Content extraction failed: {e}") from e

    return OCSContent(ocu_units=ocu_units)


def parse_task_codes(
    task_code_raw: str, task_name_raw: str, same_column: bool
) -> list[TaskCodeEntry]:
    """Extract one or more TaskCodeEntry from raw cell values.

    Separate columns with a clean T-code produce a single entry.
    A combined cell or embedded codes produce one entry per T-code found.
    """
    task_code_raw = txt.normalize_code_spacing(task_code_raw)
    if not same_column and re.fullmatch(r"T\d+(?:\.\d+)?", task_code_raw, re.IGNORECASE):
        return [TaskCodeEntry(code=task_code_raw, name=txt.compact_wrapped_text(task_name_raw))]

    text = txt.normalize_code_spacing(task_name_raw or task_code_raw)
    if not text:
        return []

    matches = list(re.finditer(r"(T\d+(?:\.\d+)?)(?![.\d])", text, re.IGNORECASE))
    entries: list[TaskCodeEntry] = []
    for i, m in enumerate(matches):
        name_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        entries.append(
            TaskCodeEntry(
                code=m.group(1),
                name=txt.compact_wrapped_text(text[m.end() : name_end]),
            )
        )
    return entries


def parse_ocu_table_units(table: list[list[Any]]) -> list[OCSUnit]:
    """Parse a merged OCU table into one or more OCSUnit objects."""
    if not table or len(table) < 2:
        return []

    try:
        header_idx, col_map, header_span = tbl.find_ocu_header_row(table)
        if header_idx is None:
            return []

        header = tbl.merge_rows_for_header(table[header_idx : header_idx + header_span])
        ocu_code = "Unknown"
        ocu_name = "Unknown"

        for meta_row in table[: header_idx + header_span]:
            for i, cell in enumerate(meta_row):
                norm_cell = txt.normalize_text(cell)
                if "職能單元代碼" in norm_cell or "ocu代碼" in norm_cell:
                    value = tbl.find_value_to_right(meta_row, i)
                    if value:
                        ocu_code = value
                if "職能單元名稱" in norm_cell or "ocu名稱" in norm_cell:
                    value = tbl.find_value_to_right(meta_row, i)
                    if value:
                        ocu_name = value

        if ocu_code == "Unknown" and header and header[0]:
            ocu_code = str(header[0]).strip()
        if ocu_name == "Unknown" and len(header) > 1 and header[1]:
            ocu_name = str(header[1]).strip()

        data_rows = table[header_idx + header_span :]
        units: list[OCSUnit] = []
        unit_tasks: dict[str, list[Task]] = {}
        unit_names: dict[str, str] = {}
        last_task_by_ocu: dict[str, Task] = {}
        current_ocu_code = ocu_code
        current_ocu_name = ocu_name

        def _ensure_unit(code: str, name: str) -> None:
            unit_tasks.setdefault(code, [])
            unit_names.setdefault(code, name)

        _ensure_unit(current_ocu_code, current_ocu_name)

        for row in data_rows:
            if not row:
                continue

            if "major_duty" in col_map and row:
                major_duty_raw = txt.compact_wrapped_text(row[col_map["major_duty"]])
                duty_match = re.match(r"(T\d+)(.+)", major_duty_raw)
                if duty_match:
                    current_ocu_code = duty_match.group(1)
                    current_ocu_name = duty_match.group(2).strip() or current_ocu_name
                    _ensure_unit(current_ocu_code, current_ocu_name)
                elif major_duty_raw and current_ocu_code in unit_names:
                    current_ocu_name = txt.append_text_if_new(current_ocu_name, major_duty_raw)
                    unit_names[current_ocu_code] = current_ocu_name

            task_code_idx = col_map.get("task_code")
            task_name_idx = col_map.get("task_name")
            task_code = (
                str(row[task_code_idx]).strip()
                if task_code_idx is not None and task_code_idx < len(row) and row[task_code_idx]
                else ""
            )
            task_name = (
                str(row[task_name_idx]).strip()
                if task_name_idx is not None and task_name_idx < len(row) and row[task_name_idx]
                else ""
            )
            if not task_name and task_code_idx is not None and task_code_idx < len(row):
                task_name = str(row[task_code_idx]).strip() if row[task_code_idx] else ""

            same_column = (
                task_code_idx is not None
                and task_name_idx is not None
                and task_code_idx == task_name_idx
            )
            parsed_task_codes = parse_task_codes(task_code, task_name, same_column)
            primary_task_code = parsed_task_codes[0].code if parsed_task_codes else ""

            outputs = (
                itm.extract_output_items(row[col_map["outputs"]])
                if "outputs" in col_map and col_map["outputs"] < len(row)
                else []
            )

            knowledge: list[CompetencyItem] = []
            if "knowledge" in col_map and col_map["knowledge"] < len(row):
                knowledge = itm.extract_competency_items(row[col_map["knowledge"]], "K")
            if not knowledge:
                knowledge = itm.extract_competency_items_from_row(row, "K")

            skills: list[CompetencyItem] = []
            if "skills" in col_map and col_map["skills"] < len(row):
                skills = itm.extract_competency_items(row[col_map["skills"]], "S")
            if not skills:
                skills = itm.extract_competency_items_from_row(row, "S")

            behavioral_indicators = (
                itm.extract_behavioral_indicators(row[col_map["behavioral"]])
                if "behavioral" in col_map and col_map["behavioral"] < len(row)
                else []
            )
            if not behavioral_indicators:
                behavioral_indicators = itm.extract_behavioral_indicators_from_row(row)

            # Historical PDFs: task-code cell may be None (merged cell); derive from P-code.
            if (
                not primary_task_code
                and behavioral_indicators
                and not last_task_by_ocu.get(current_ocu_code)
            ):
                derived = scan.derive_task_code_from_p_codes(behavioral_indicators)
                if derived:
                    parsed_task_codes = [TaskCodeEntry(code=derived, name="")]
                    primary_task_code = derived

            # T codes without P-codes: attach to the previous task (cross-page pattern).
            if primary_task_code and not behavioral_indicators:
                previous_task = last_task_by_ocu.get(current_ocu_code)
                if previous_task:
                    existing_codes = {e.code for e in previous_task.task_codes}
                    for entry in parsed_task_codes:
                        if entry.code not in existing_codes:
                            previous_task.task_codes.append(entry)
                    primary_task_code = ""
                    parsed_task_codes = []

            # Continuation rows: append content to the previous task's last block.
            if not primary_task_code:
                previous_task = last_task_by_ocu.get(current_ocu_code)
                if previous_task:
                    if not previous_task.competency_blocks:
                        previous_task.competency_blocks.append(
                            CompetencyBlock(
                                competency_level=itm.extract_task_level(row, col_map),
                                indicators=[],
                                outputs=[],
                                knowledge=[],
                                skills=[],
                            )
                        )
                    previous_block = previous_task.competency_blocks[-1]
                    if (
                        outputs
                        and all(item.code is None for item in outputs)
                        and previous_block.outputs
                    ):
                        outputs = []

                    output_idx = col_map.get("outputs")
                    behavioral_idx = col_map.get("behavioral")
                    knowledge_idx = col_map.get("knowledge")
                    skills_idx = col_map.get("skills")

                    output_tail = (
                        txt.compact_wrapped_text(row[output_idx])
                        if output_idx is not None and output_idx < len(row) and row[output_idx]
                        else ""
                    )
                    behavioral_tail = (
                        txt.compact_wrapped_text(row[behavioral_idx])
                        if behavioral_idx is not None
                        and behavioral_idx < len(row)
                        and row[behavioral_idx]
                        else ""
                    )
                    knowledge_tail = (
                        txt.compact_wrapped_text(row[knowledge_idx])
                        if knowledge_idx is not None
                        and knowledge_idx < len(row)
                        and row[knowledge_idx]
                        else ""
                    )
                    skills_tail = (
                        txt.compact_wrapped_text(row[skills_idx])
                        if skills_idx is not None and skills_idx < len(row) and row[skills_idx]
                        else ""
                    )

                    # A continuation can finish the prior item AND start new
                    # coded items in the same cell. Keep the leading fragment.
                    output_tail = txt.normalize_code_spacing(output_tail)
                    behavioral_tail = txt.normalize_code_spacing(behavioral_tail)
                    knowledge_tail = txt.normalize_code_spacing(knowledge_tail)
                    skills_tail = txt.normalize_code_spacing(skills_tail)
                    output_tail = re.split(
                        r"O\d+(?:[-.]\d+)*", output_tail, maxsplit=1, flags=re.IGNORECASE
                    )[0]
                    behavioral_tail = re.split(
                        r"[PT]\.?\d+(?:[-.]\d+)*", behavioral_tail, maxsplit=1, flags=re.IGNORECASE
                    )[0]
                    knowledge_tail = re.split(
                        r"K\d+(?:[-.]\d+)*", knowledge_tail, maxsplit=1, flags=re.IGNORECASE
                    )[0]
                    skills_tail = re.split(
                        r"S\d+(?:[-.]\d+)*", skills_tail, maxsplit=1, flags=re.IGNORECASE
                    )[0]

                    if (
                        output_tail
                        and previous_block.outputs
                        and not re.search(r"\bO\d+(?:[-.]\d+)*", output_tail, flags=re.IGNORECASE)
                    ):
                        previous_block.outputs[-1].name = txt.append_text_if_new(
                            previous_block.outputs[-1].name, output_tail
                        )

                    if (
                        behavioral_tail
                        and previous_block.indicators
                        and not re.search(
                            r"\b[PT]\d+(?:[-.]\d+)*", behavioral_tail, flags=re.IGNORECASE
                        )
                    ):
                        previous_block.indicators[-1].text = txt.append_text_if_new(
                            previous_block.indicators[-1].text, behavioral_tail
                        )

                    if (
                        knowledge_tail
                        and previous_block.knowledge
                        and not re.search(
                            r"\bK\d+(?:[-.]\d+)*", knowledge_tail, flags=re.IGNORECASE
                        )
                    ):
                        previous_block.knowledge[-1].name = txt.append_text_if_new(
                            previous_block.knowledge[-1].name, knowledge_tail
                        )

                    if (
                        skills_tail
                        and previous_block.skills
                        and not re.search(r"\bS\d+(?:[-.]\d+)*", skills_tail, flags=re.IGNORECASE)
                    ):
                        previous_block.skills[-1].name = txt.append_text_if_new(
                            previous_block.skills[-1].name, skills_tail
                        )

                    if task_name and previous_task.task_codes:
                        last_entry = previous_task.task_codes[-1]
                        last_entry.name = txt.append_text_if_new(last_entry.name, task_name)

                    # New block when both a structural trigger (new O or level change)
                    # and new K/S codes are present.
                    new_level = itm.extract_task_level(row, col_map)
                    if new_level is None:
                        new_level = previous_block.competency_level
                    level_changed = new_level != previous_block.competency_level
                    has_new_o = bool(outputs)
                    has_new_ks = bool(knowledge or skills)

                    if (has_new_o or level_changed) and has_new_ks and behavioral_indicators:
                        previous_task.competency_blocks.append(
                            CompetencyBlock(
                                competency_level=new_level,
                                indicators=dd.dedupe_indicators(behavioral_indicators),
                                outputs=dd.dedupe_outputs(
                                    outputs if outputs else list(previous_block.outputs)
                                ),
                                knowledge=dd.dedupe_competencies(knowledge),
                                skills=dd.dedupe_competencies(skills),
                            )
                        )
                    else:
                        previous_block.outputs.extend(outputs)
                        previous_block.indicators.extend(behavioral_indicators)
                        previous_block.knowledge.extend(knowledge)
                        previous_block.skills.extend(skills)
                        dd.dedupe_block(previous_block)
                    continue

                raise TransformationError(f"Orphan content continuation: {row}")

            task_level = itm.extract_task_level(row, col_map)
            if primary_task_code:
                task = Task(
                    task_codes=parsed_task_codes,
                    competency_blocks=[
                        CompetencyBlock(
                            competency_level=task_level,
                            indicators=dd.dedupe_indicators(behavioral_indicators),
                            outputs=dd.dedupe_outputs(outputs),
                            knowledge=dd.dedupe_competencies(knowledge),
                            skills=dd.dedupe_competencies(skills),
                        )
                    ],
                )
                _ensure_unit(current_ocu_code, current_ocu_name)
                unit_tasks[current_ocu_code].append(task)
                last_task_by_ocu[current_ocu_code] = task

        for code, tasks in unit_tasks.items():
            for task in tasks:
                task.competency_blocks = [
                    b
                    for b in task.competency_blocks
                    if b.indicators or b.outputs or b.knowledge or b.skills
                ]
            tasks = [t for t in tasks if t.competency_blocks]
            if tasks:
                units.append(
                    OCSUnit(
                        ocu_code=code,
                        ocu_name=unit_names.get(code, "Unknown"),
                        tasks=tasks,
                    )
                )

        return units

    except Exception as e:
        raise TransformationError(f"Content table failed: {e}") from e
