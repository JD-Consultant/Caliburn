"""Normalize parsed OCSDocument into a flat shape that the builder consumes.

Responsibilities:
  - Fill nullable / empty-array defaults so the builder never branches on missing fields.
  - Derive version + version_seq from `ocs_code` tail (v1, v2 ...) when version_info is empty.
  - Decide `is_current` (latest version flag).
  - Compute order indices for units / tasks / blocks.
  - Compute ocs_code_base (code without trailing version segment).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from jd_ocs_indexer.models.chunk import Pair
from jd_ocs_indexer.models.ocs import OCSDocument


_OCS_CODE_VERSION_TAIL = re.compile(r"(?i)v(\d+)$")
_LATEST_STATUS_TOKENS = ("最新",)


@dataclass
class NormalizedBlock:
    block_order: int                         # 1-based within parent task group
    competency_level: int | None
    indicator_codes: list[str] = field(default_factory=list)
    output_codes: list[str] = field(default_factory=list)
    indicator_texts: list[str] = field(default_factory=list)
    output_names: list[str] = field(default_factory=list)
    k_codes: list[str] = field(default_factory=list)
    s_codes: list[str] = field(default_factory=list)
    knowledge_terms: list[str] = field(default_factory=list)
    skill_terms: list[str] = field(default_factory=list)
    # v2: pair structures (code-name bound together to prevent misalignment)
    k_pairs: list[Pair] = field(default_factory=list)
    s_pairs: list[Pair] = field(default_factory=list)
    output_pairs: list[Pair] = field(default_factory=list)
    evidence: list[Pair] = field(default_factory=list)  # indicator code + activity text


@dataclass
class NormalizedTaskGroup:
    """A task_codes -> competency_blocks group inside an ocu_unit."""

    task_orders: list[int]                   # 1-based per task entry within the unit
    task_ids: list[str]                      # full list of T-codes
    task_titles: list[str]
    primary_task_key: str                    # sorted(task_ids)[0]; fallback to padded order
    tasks: list[Pair] = field(default_factory=list)   # v3: aligned (code, title) — single filter
    blocks: list[NormalizedBlock] = field(default_factory=list)


@dataclass
class NormalizedUnit:
    unit_order: int                          # 1-based
    unit_id: str | None
    unit_title: str | None
    unit_key: str                            # ocu_code or zero-padded fallback
    task_groups: list[NormalizedTaskGroup] = field(default_factory=list)


@dataclass
class NormalizedOCS:
    # Profile
    ocs_code: str
    ocs_code_base: str
    job_title: str
    job_category: str | None
    job_category_codes: list[str]
    job_category_names: list[str]
    industry_codes: list[str]
    industry_names: list[str]
    occupation_codes: list[str]
    occupation_names: list[str]
    job_description: str | None
    ocs_level: int | None

    # Version
    version: str | None
    version_seq: int | None
    update_date: str | None
    is_current: bool

    # Units
    units: list[NormalizedUnit]

    # Attitudes
    attitude_codes: list[str]
    attitude_terms: list[str]                # rich descriptive text
    attitude_pairs: list[Pair]               # v2: code-name bound

    # Notes
    prerequisites: list[str]
    supplements: list[str]


def _padded(n: int) -> str:
    return f"{n:04d}"


def _ocs_code_base(ocs_code: str) -> str:
    m = _OCS_CODE_VERSION_TAIL.search(ocs_code)
    if not m:
        return ocs_code
    return ocs_code[: m.start()]


def _derive_version(doc: OCSDocument) -> tuple[str | None, int | None, str | None, bool]:
    """Returns (version, version_seq, update_date, is_current).

    Prefer explicit version_info entry matching ocs_code; otherwise infer from
    ocs_code tail. `is_current` is True when the matching entry's status
    contains "最新", or when no version_info exists (single-version files).
    """
    ocs_code = doc.ocs_profile.ocs_code
    versions = doc.version_info.versions if doc.version_info else []

    matched = None
    for entry in versions:
        if entry.ocs_code and entry.ocs_code == ocs_code:
            matched = entry
            break

    if matched:
        version = matched.version
        update_date = matched.update_date
        status = matched.status or ""
        is_current = any(tok in status for tok in _LATEST_STATUS_TOKENS)
    else:
        version = None
        update_date = None
        is_current = not versions  # no version_info -> treat as current

    # Derive numeric seq
    version_seq: int | None = None
    if version:
        m = _OCS_CODE_VERSION_TAIL.search(version)
        if m:
            version_seq = int(m.group(1))
    if version_seq is None:
        m = _OCS_CODE_VERSION_TAIL.search(ocs_code)
        if m:
            version_seq = int(m.group(1))
            if version is None:
                version = f"V{version_seq}"

    return version, version_seq, update_date, is_current


def normalize(doc: OCSDocument) -> NormalizedOCS:
    profile = doc.ocs_profile
    ocs_code = profile.ocs_code
    ocs_code_base = _ocs_code_base(ocs_code)

    job_title = (profile.ocs_name.occupation_name if profile.ocs_name else None) or ocs_code
    job_category = (profile.ocs_name.job_category_name if profile.ocs_name else None)

    category = profile.category
    job_category_codes: list[str] = []
    job_category_names: list[str] = []
    industry_codes: list[str] = []
    industry_names: list[str] = []
    occupation_codes: list[str] = []
    occupation_names: list[str] = []
    if category is not None:
        # job_categories 是多值 [{code,name}]（同 occupations/industries）。code+name
        # 鎖步收集、依 code|name 去重，確保兩平行陣列永遠對齊。
        seen_jc: set[str] = set()
        for jc in category.job_categories:
            key = jc.code or jc.name
            if key and key not in seen_jc:
                seen_jc.add(key)
                job_category_codes.append(jc.code or "")
                job_category_names.append(jc.name or "")
        for ind in category.industries:
            if ind.code:
                industry_codes.append(ind.code)
            if ind.name:
                industry_names.append(ind.name)
        for occ in category.occupations:
            if occ.code:
                occupation_codes.append(occ.code)
            if occ.name:
                occupation_names.append(occ.name)

    version, version_seq, update_date, is_current = _derive_version(doc)

    units: list[NormalizedUnit] = []
    for u_idx, u in enumerate(doc.ocs_content.ocu_units, start=1):
        unit_id = u.ocu_code or None
        unit_title = u.ocu_name or None
        unit_key = unit_id or f"unit_{_padded(u_idx)}"

        groups: list[NormalizedTaskGroup] = []
        # task orders are 1-based across the unit
        task_order_cursor = 0
        for g_idx, group in enumerate(u.tasks, start=1):
            task_codes = group.task_codes or []
            task_ids: list[str] = []
            task_titles: list[str] = []
            for tc in task_codes:
                if tc.code:
                    task_ids.append(tc.code)
                if tc.name:
                    task_titles.append(tc.name.strip())
            # v3: aligned (code, title) pairs — single filter so code↔title never drifts
            task_pairs = [
                Pair(code=tc.code, name=tc.name.strip())
                for tc in task_codes
                if tc.code and tc.name and tc.name.strip()
            ]
            task_orders: list[int] = []
            for _ in range(max(len(task_codes), 1)):
                task_order_cursor += 1
                task_orders.append(task_order_cursor)

            if task_ids:
                primary_task_key = sorted(task_ids)[0]
            else:
                primary_task_key = f"task_{_padded(g_idx)}"

            norm_blocks: list[NormalizedBlock] = []
            for b_idx, b in enumerate(group.competency_blocks, start=1):
                # v2: build pairs first (single filter — code AND name both present),
                # then derive parallel arrays from the pairs so they're always aligned.
                k_pairs = [
                    Pair(code=k.code, name=k.name.strip())
                    for k in b.knowledge
                    if k.code and k.name and k.name.strip()
                ]
                s_pairs = [
                    Pair(code=s.code, name=s.name.strip())
                    for s in b.skills
                    if s.code and s.name and s.name.strip()
                ]
                output_pairs = [
                    Pair(code=o.code, name=o.name.strip())
                    for o in b.outputs
                    if o.code and o.name and o.name.strip()
                ]
                evidence = [
                    Pair(code=i.code, name=i.text.strip())  # name field reused as activity_text
                    for i in b.indicators
                    if i.code and i.text and i.text.strip()
                ]

                # Parallel arrays derived from pairs — guaranteed aligned.
                k_codes = [p.code for p in k_pairs]
                s_codes = [p.code for p in s_pairs]
                k_terms = [p.name for p in k_pairs]
                s_terms = [p.name for p in s_pairs]
                out_codes = [p.code for p in output_pairs]
                out_names = [p.name for p in output_pairs]
                ind_codes = [p.code for p in evidence]
                ind_texts = [p.name for p in evidence]

                norm_blocks.append(
                    NormalizedBlock(
                        block_order=b_idx,
                        competency_level=b.competency_level,
                        indicator_codes=ind_codes,
                        output_codes=out_codes,
                        indicator_texts=ind_texts,
                        output_names=out_names,
                        k_codes=k_codes,
                        s_codes=s_codes,
                        knowledge_terms=k_terms,
                        skill_terms=s_terms,
                        k_pairs=k_pairs,
                        s_pairs=s_pairs,
                        output_pairs=output_pairs,
                        evidence=evidence,
                    )
                )

            groups.append(
                NormalizedTaskGroup(
                    task_orders=task_orders,
                    task_ids=task_ids,
                    task_titles=task_titles,
                    primary_task_key=primary_task_key,
                    tasks=task_pairs,
                    blocks=norm_blocks,
                )
            )

        units.append(
            NormalizedUnit(
                unit_order=u_idx,
                unit_id=unit_id,
                unit_title=unit_title,
                unit_key=unit_key,
                task_groups=groups,
            )
        )

    # v2: build pairs first, derive parallel arrays from them
    attitude_pairs = [
        Pair(code=a.code, name=a.name.strip())
        for a in doc.ocs_attitude.attitudes
        if a.code and a.name and a.name.strip()
    ]
    attitude_codes = [p.code for p in attitude_pairs]
    attitude_terms = [p.name for p in attitude_pairs]

    prerequisites = [p.strip() for p in doc.notes.prerequisites if p and p.strip()]
    supplements = [s.strip() for s in doc.notes.supplements if s and s.strip()]

    return NormalizedOCS(
        ocs_code=ocs_code,
        ocs_code_base=ocs_code_base,
        job_title=job_title.strip(),
        job_category=job_category.strip() if job_category else None,
        job_category_codes=job_category_codes,
        job_category_names=job_category_names,
        industry_codes=industry_codes,
        industry_names=industry_names,
        occupation_codes=occupation_codes,
        occupation_names=occupation_names,
        job_description=(profile.job_description.strip() if profile.job_description else None),
        ocs_level=profile.ocs_level,
        version=version,
        version_seq=version_seq,
        update_date=update_date,
        is_current=is_current,
        units=units,
        attitude_codes=attitude_codes,
        attitude_terms=attitude_terms,
        attitude_pairs=attitude_pairs,
        prerequisites=prerequisites,
        supplements=supplements,
    )
