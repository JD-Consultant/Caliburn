# Schema v3 Phase 1 — Indexing Pipeline (in-place rewrite)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite jd-ocs-indexer's indexing pipeline **in place** to produce **profile points + per-task task points** (schema v3) instead of profile/unit/block, with the v3 payload and the embed string built at index time (not stored).

**Architecture:** The `normalizer` is reused (it already produces the OCS tree) — we add only an aligned `tasks` pair list. `builder.py` and `schema.py` are **rewritten** to v3 (no separate v3 files — nothing consumes the v2 query API yet, so there is nothing to keep running). `builder.build()` emits one `profile` record per OCS and one `task` record per task (aggregating that task-group's blocks). Embed text is on `ChunkRecord.text` for the embedder but **never written to payload**. The `index` command is rewritten to v3 (no markdown renderer); the `render` command is removed. Points go to a fresh `ocs_v3` collection; the old `ocs_bgem3_v2` collection's data stays in Qdrant (orphaned, not overwritten).

> **TDD ordering note:** Tasks 4-6 rewrite `builder.py`, which breaks `cli.py`'s import at *runtime* (it still imports the removed `ChunkBuilder`). This is fine for the test suite — **no pytest test imports `cli.py`**, so `uv run pytest` stays green throughout. Task 7 restores the CLI. Do NOT run `jd-ocs-indexer ...` between Tasks 4 and 7; do run `uv run pytest`.

**Tech Stack:** Python 3.11, Pydantic v2, Qdrant, BGE-M3, pytest, uv. Spec: [docs/superpowers/specs/2026-06-14-schema-v3-design.md](../specs/2026-06-14-schema-v3-design.md).

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/jd_ocs_indexer/models/chunk.py` | add `"task"` to `ChunkLevel` | Modify |
| `src/jd_ocs_indexer/ingestion/normalizer.py` | add aligned `tasks: list[Pair]` | Modify |
| `src/jd_ocs_indexer/store/schema.py` | **rewrite** `PAYLOAD_INDEXES` to v3 (9 fields) | Modify |
| `src/jd_ocs_indexer/ingestion/builder.py` | **rewrite** → `build()` emits profile + task records | Modify |
| `src/jd_ocs_indexer/store/writer.py` | parametrize `ensure_payload_indexes(indexes=...)` | Modify |
| `src/jd_ocs_indexer/cli.py` | rewrite `index` to v3; remove `render`; v3 collection default | Modify |
| `src/jd_ocs_indexer/config.py` | default collection → `ocs_v3` | Modify |
| `tests/test_normalizer_task_pairs.py` | aligned task pairs | Create |
| `tests/test_builder.py` | profile + task records, payload, embed text | Create |
| `tests/test_schema.py` | v3 index set | Create |

**Run tests with:** `uv run pytest` (Windows / PowerShell).

> `src/jd_ocs_indexer/ingestion/renderer.py` becomes unused after this phase (nothing imports `MarkdownRenderer`). Leave the file; it can be deleted in a later cleanup.

---

## Task 1: Add `"task"` chunk level

**Files:**
- Modify: `src/jd_ocs_indexer/models/chunk.py`
- Test: `tests/test_chunk_level.py`

- [ ] **Step 1: Write the failing test**

```python
from typing import get_args
from jd_ocs_indexer.models.chunk import ChunkLevel


def test_task_is_a_valid_chunk_level():
    members = get_args(ChunkLevel)
    assert "task" in members
    assert "profile" in members
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_chunk_level.py -v`
Expected: FAIL — `"task"` not in `get_args(ChunkLevel)`.

- [ ] **Step 3: Add `"task"` to the Literal**

In `src/jd_ocs_indexer/models/chunk.py`, change:
```python
ChunkLevel = Literal["profile", "unit", "block"]
```
to:
```python
ChunkLevel = Literal["profile", "unit", "block", "task"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_chunk_level.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/jd_ocs_indexer/models/chunk.py tests/test_chunk_level.py
git commit -m "feat(models): add task chunk level for v3"
```

---

## Task 2: Aligned task pairs in the normalizer

**Files:**
- Modify: `src/jd_ocs_indexer/ingestion/normalizer.py`
- Test: `tests/test_normalizer_task_pairs.py`

The normalizer builds `task_ids` (filter `code`) and `task_titles` (filter `name`) as two independent lists — they can misalign. v3 needs an aligned `(id, title)` per task.

- [ ] **Step 1: Write the failing test**

```python
from jd_ocs_indexer.models.ocs import OCSDocument
from jd_ocs_indexer.ingestion.normalizer import normalize


def _doc_with_partial_task() -> OCSDocument:
    return OCSDocument.model_validate({
        "ocs_profile": {"ocs_code": "OC1v1", "ocs_name": {"occupation_name": "JT"}},
        "ocs_content": {"ocu_units": [
            {"ocu_code": "U1", "ocu_name": "Unit 1", "tasks": [
                {"task_codes": [
                    {"code": "T1.1", "name": "任務一"},
                    {"code": "T1.2", "name": ""},
                    {"code": "T1.3", "name": "任務三"},
                ], "competency_blocks": []},
            ]},
        ]},
    })


def test_task_pairs_are_aligned():
    norm = normalize(_doc_with_partial_task())
    group = norm.units[0].task_groups[0]
    pairs = [(p.code, p.name) for p in group.tasks]
    assert pairs == [("T1.1", "任務一"), ("T1.3", "任務三")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_normalizer_task_pairs.py -v`
Expected: FAIL — `NormalizedTaskGroup` has no attribute `tasks`.

- [ ] **Step 3: Add the `tasks` field + populate it**

In `src/jd_ocs_indexer/ingestion/normalizer.py`, add `tasks` to `NormalizedTaskGroup` (after `primary_task_key`):

```python
    primary_task_key: str                    # sorted(task_ids)[0]; fallback to padded order
    tasks: list[Pair] = field(default_factory=list)   # v3: aligned (code, title) — single filter
    blocks: list[NormalizedBlock] = field(default_factory=list)
```

In `normalize()`, after `task_titles` is computed (before `task_orders`), add:

```python
            # v3: aligned (code, title) pairs — single filter so code↔title never drifts
            task_pairs = [
                Pair(code=tc.code, name=tc.name.strip())
                for tc in task_codes
                if tc.code and tc.name and tc.name.strip()
            ]
```

And pass it into `NormalizedTaskGroup(...)`:

```python
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
```

- [ ] **Step 4: Run test + full suite**

Run: `uv run pytest tests/test_normalizer_task_pairs.py -q && uv run pytest -q`
Expected: new test passes; full suite still green (additive field with default).

- [ ] **Step 5: Commit**

```bash
git add src/jd_ocs_indexer/ingestion/normalizer.py tests/test_normalizer_task_pairs.py
git commit -m "feat(normalizer): aligned task pairs on NormalizedTaskGroup (v3)"
```

---

## Task 3: Rewrite schema PAYLOAD_INDEXES to v3

**Files:**
- Modify: `src/jd_ocs_indexer/store/schema.py`
- Test: `tests/test_schema.py`

- [ ] **Step 1: Write the failing test**

```python
from jd_ocs_indexer.store import schema


def test_v3_indexes_are_the_nine_global_filterable_fields():
    keys = [name for name, _ in schema.PAYLOAD_INDEXES]
    assert keys == [
        "chunk_level", "ocs_code", "ocs_code_base", "job_title",
        "is_current", "version", "ocs_level",
        "industry_codes", "occupation_codes",
    ]


def test_v3_drops_ocs_local_and_constant_indexes():
    keys = {name for name, _ in schema.PAYLOAD_INDEXES}
    for dropped in ("k_codes", "s_codes", "attitude_codes", "task_ids",
                    "unit_id", "schema_version", "embedding_provider", "competency_level"):
        assert dropped not in keys
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_schema.py -v`
Expected: FAIL — the v2 `PAYLOAD_INDEXES` has 18 entries / different order.

- [ ] **Step 3: Rewrite `PAYLOAD_INDEXES` in `src/jd_ocs_indexer/store/schema.py`**

Replace the entire `PAYLOAD_INDEXES` list (keep `dense_vector_params` / `sparse_vector_params` unchanged) with:

```python
PAYLOAD_INDEXES: list[tuple[str, models.PayloadSchemaType]] = [
    ("chunk_level", models.PayloadSchemaType.KEYWORD),
    ("ocs_code", models.PayloadSchemaType.KEYWORD),
    ("ocs_code_base", models.PayloadSchemaType.KEYWORD),
    ("job_title", models.PayloadSchemaType.TEXT),
    ("is_current", models.PayloadSchemaType.BOOL),
    ("version", models.PayloadSchemaType.KEYWORD),
    ("ocs_level", models.PayloadSchemaType.INTEGER),
    ("industry_codes", models.PayloadSchemaType.KEYWORD),
    ("occupation_codes", models.PayloadSchemaType.KEYWORD),
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_schema.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/jd_ocs_indexer/store/schema.py tests/test_schema.py
git commit -m "feat(store): rewrite payload indexes to v3 (9 global-filterable fields)"
```

---

## Task 4: Rewrite builder.py — context + aggregation

**Files:**
- Modify: `src/jd_ocs_indexer/ingestion/builder.py` (full rewrite)
- Test: `tests/test_builder.py`

> After this task `cli.py` is broken at runtime (it imports the now-removed `ChunkBuilder`). Pytest stays green (no test imports cli). Task 7 fixes cli.

- [ ] **Step 1: Write the failing test**

```python
from jd_ocs_indexer.models.chunk import Pair
from jd_ocs_indexer.ingestion.normalizer import NormalizedBlock, NormalizedTaskGroup
from jd_ocs_indexer.ingestion.builder import _aggregate_group


def _group() -> NormalizedTaskGroup:
    b1 = NormalizedBlock(
        block_order=1, competency_level=2,
        k_pairs=[Pair("K01", "知識一")], s_pairs=[Pair("S01", "技能一")],
        output_pairs=[Pair("O01", "產出一")],
        evidence=[Pair("P01", "活動句一"), Pair("P02", "活動句二")],
    )
    b2 = NormalizedBlock(
        block_order=2, competency_level=3,
        k_pairs=[Pair("K01", "知識一"), Pair("K02", "知識二")],
        s_pairs=[Pair("S02", "技能二")], output_pairs=[],
        evidence=[Pair("P03", "活動句三")],
    )
    return NormalizedTaskGroup(
        task_orders=[1], task_ids=["T1.1"], task_titles=["任務一"],
        primary_task_key="T1.1", tasks=[Pair("T1.1", "任務一")], blocks=[b1, b2],
    )


def test_aggregate_group_dedups_and_collects():
    agg = _aggregate_group(_group())
    assert [(p.code, p.name) for p in agg["k_pairs"]] == [("K01", "知識一"), ("K02", "知識二")]
    assert [(p.code, p.name) for p in agg["s_pairs"]] == [("S01", "技能一"), ("S02", "技能二")]
    assert [(p.code, p.name) for p in agg["output_pairs"]] == [("O01", "產出一")]
    assert agg["activities"] == ["活動句一", "活動句二", "活動句三"]
    assert agg["competency_level"] == 3


def test_aggregate_group_block_less():
    g = NormalizedTaskGroup(
        task_orders=[1], task_ids=["T9"], task_titles=["空任務"],
        primary_task_key="T9", tasks=[Pair("T9", "空任務")], blocks=[],
    )
    agg = _aggregate_group(g)
    assert agg["k_pairs"] == [] and agg["activities"] == [] and agg["competency_level"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_builder.py -v`
Expected: FAIL — `cannot import name '_aggregate_group'`.

- [ ] **Step 3: Rewrite `src/jd_ocs_indexer/ingestion/builder.py`**

Replace the **entire file** with:

```python
"""Schema v3 chunk builder: profile + per-task records.

Reuses the normalizer's OCS tree. Emits one `profile` record per OCS and one
`task` record per task (aggregating that task-group's blocks). The embed string
is set on ChunkRecord.text for the embedder but is NEVER written to payload.
"""

from __future__ import annotations

from dataclasses import dataclass

from jd_ocs_indexer.models.chunk import ChunkRecord, Pair
from jd_ocs_indexer.ingestion.normalizer import (
    NormalizedOCS,
    NormalizedTaskGroup,
    NormalizedUnit,
)

_ACTIVITY_EXAMPLES = 3


@dataclass
class BuildContext:
    source_file: str
    indexed_at: str


def _dedup_pairs(pairs: list[Pair]) -> list[Pair]:
    out: list[Pair] = []
    seen: set[str] = set()
    for p in pairs:
        if p.code not in seen:
            seen.add(p.code)
            out.append(p)
    return out


def _aggregate_group(group: NormalizedTaskGroup) -> dict:
    """Aggregate a task-group's blocks into per-task K/S/output/activities/level."""
    k: list[Pair] = []
    s: list[Pair] = []
    out: list[Pair] = []
    activities: list[str] = []
    levels: list[int] = []
    for b in group.blocks:
        k.extend(b.k_pairs)
        s.extend(b.s_pairs)
        out.extend(b.output_pairs)
        for ev in b.evidence:  # ev.name == activity text
            if ev.name and ev.name not in activities:
                activities.append(ev.name)
        if b.competency_level is not None:
            levels.append(b.competency_level)
    return {
        "k_pairs": _dedup_pairs(k),
        "s_pairs": _dedup_pairs(s),
        "output_pairs": _dedup_pairs(out),
        "activities": activities,
        "competency_level": max(levels) if levels else None,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_builder.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/jd_ocs_indexer/ingestion/builder.py tests/test_builder.py
git commit -m "feat(builder): rewrite to v3 — per-group aggregation (cli wired in Task 7)"
```

---

## Task 5: builder.py — profile record

**Files:**
- Modify: `src/jd_ocs_indexer/ingestion/builder.py`
- Test: `tests/test_builder_profile.py`

- [ ] **Step 1: Write the failing test**

```python
from jd_ocs_indexer.models.chunk import Pair
from jd_ocs_indexer.ingestion.normalizer import (
    NormalizedBlock, NormalizedTaskGroup, NormalizedUnit, NormalizedOCS,
)
from jd_ocs_indexer.ingestion.builder import build, BuildContext


def _norm() -> NormalizedOCS:
    block = NormalizedBlock(
        block_order=1, competency_level=2,
        k_pairs=[Pair("K01", "資料處理概念")], s_pairs=[Pair("S01", "Python")],
        output_pairs=[Pair("O01", "清理後資料集")], evidence=[Pair("P01", "用Python清洗資料")],
    )
    group = NormalizedTaskGroup(
        task_orders=[1], task_ids=["T1.1"], task_titles=["資料清理"],
        primary_task_key="T1.1", tasks=[Pair("T1.1", "資料清理")], blocks=[block],
    )
    unit = NormalizedUnit(unit_order=1, unit_id="U1", unit_title="資料處理",
                          unit_key="U1", task_groups=[group])
    return NormalizedOCS(
        ocs_code="OC1v2", ocs_code_base="OC1", job_title="資料分析師",
        job_category="資訊", job_category_codes=["JC1"],
        industry_codes=["I1"], industry_names=["資訊業"],
        occupation_codes=["OCC1"], occupation_names=["分析師"],
        job_description="負責資料分析", ocs_level=4,
        version="v2", version_seq=2, update_date="2025/12/31", is_current=True,
        units=[unit], attitude_codes=["A01"], attitude_terms=["主動積極"],
        attitude_pairs=[Pair("A01", "主動積極")],
        prerequisites=["大學以上學歷"], supplements=["須具備證照"],
    )


_CTX = BuildContext(source_file="jd-ocs/OC1v2.json", indexed_at="2026-06-14T00:00:00+00:00")


def test_profile_record_payload():
    profile = [r for r in build(_norm(), _CTX) if r.chunk_level == "profile"][0]
    p = profile.payload
    assert profile.chunk_key == "ocs:OC1v2:profile"
    assert p["chunk_level"] == "profile"
    assert p["ocs_code"] == "OC1v2" and p["ocs_code_base"] == "OC1"
    assert p["job_title"] == "資料分析師" and p["is_current"] is True
    assert p["ocs_level"] == 4 and p["version"] == "v2"
    assert p["job_description"] == "負責資料分析"
    assert p["all_a_pairs"] == [{"code": "A01", "name": "主動積極"}]
    assert p["prerequisites"] == ["大學以上學歷"]
    assert p["supplements"] == ["須具備證照"]
    assert "text" not in p


def test_profile_embed_text_has_signal():
    profile = [r for r in build(_norm(), _CTX) if r.chunk_level == "profile"][0]
    for token in ["資料分析師", "負責資料分析", "資料清理", "Python", "資料處理概念"]:
        assert token in profile.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_builder_profile.py -v`
Expected: FAIL — `cannot import name 'build'`.

- [ ] **Step 3: Append profile builder + `build` to `builder.py`**

Append to `src/jd_ocs_indexer/ingestion/builder.py`:

```python
def _all_skill_names(norm: NormalizedOCS) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for u in norm.units:
        for g in u.task_groups:
            for b in g.blocks:
                for p in (*b.k_pairs, *b.s_pairs):
                    if p.name and p.name not in seen:
                        seen.add(p.name)
                        names.append(p.name)
    return names


def _profile_embed_text(norm: NormalizedOCS) -> str:
    task_titles = [p.name for u in norm.units for g in u.task_groups for p in g.tasks]
    sample_activities: list[str] = []
    for u in norm.units:
        for g in u.task_groups:
            for b in g.blocks:
                for ev in b.evidence:
                    if ev.name and len(sample_activities) < 20:
                        sample_activities.append(ev.name)
    parts = [
        norm.job_title,
        norm.job_description or "",
        "工作內容：" + "、".join(task_titles),
        "活動：" + "、".join(sample_activities),
        "技能：" + "、".join(_all_skill_names(norm)),
    ]
    return "\n".join(part for part in parts if part.strip())


def _profile_record(norm: NormalizedOCS, ctx: BuildContext) -> ChunkRecord:
    payload = {
        "chunk_level": "profile",
        "ocs_code": norm.ocs_code,
        "ocs_code_base": norm.ocs_code_base,
        "job_title": norm.job_title,
        "job_category": norm.job_category,
        "industry_codes": list(norm.industry_codes),
        "industry_names": list(norm.industry_names),
        "occupation_codes": list(norm.occupation_codes),
        "occupation_names": list(norm.occupation_names),
        "version": norm.version,
        "version_seq": norm.version_seq,
        "is_current": norm.is_current,
        "update_date": norm.update_date,
        "ocs_level": norm.ocs_level,
        "job_description": norm.job_description,
        "all_a_pairs": [{"code": p.code, "name": p.name} for p in norm.attitude_pairs],
        "prerequisites": list(norm.prerequisites),
        "supplements": list(norm.supplements),
        "source_file": ctx.source_file,
        "indexed_at": ctx.indexed_at,
    }
    return ChunkRecord(
        chunk_key=f"ocs:{norm.ocs_code}:profile",
        chunk_level="profile",
        text=_profile_embed_text(norm),
        payload=payload,
    )


def build(norm: NormalizedOCS, ctx: BuildContext) -> list[ChunkRecord]:
    return [_profile_record(norm, ctx)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_builder_profile.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/jd_ocs_indexer/ingestion/builder.py tests/test_builder_profile.py
git commit -m "feat(builder): profile record + embed text (no stored text)"
```

---

## Task 6: builder.py — task records + assemble

**Files:**
- Modify: `src/jd_ocs_indexer/ingestion/builder.py`
- Test: `tests/test_builder_task.py`

- [ ] **Step 1: Write the failing test**

```python
from jd_ocs_indexer.models.chunk import Pair
from jd_ocs_indexer.ingestion.normalizer import (
    NormalizedBlock, NormalizedTaskGroup, NormalizedUnit, NormalizedOCS,
)
from jd_ocs_indexer.ingestion.builder import build, BuildContext


def _norm_two_tasks() -> NormalizedOCS:
    block = NormalizedBlock(
        block_order=1, competency_level=3,
        k_pairs=[Pair("K01", "知識一")], s_pairs=[Pair("S01", "技能一")],
        output_pairs=[Pair("O01", "產出一")],
        evidence=[Pair("P01", "活動一"), Pair("P02", "活動二"), Pair("P03", "活動三"), Pair("P04", "活動四")],
    )
    multi = NormalizedTaskGroup(
        task_orders=[1, 2], task_ids=["T1.1", "T1.2"], task_titles=["任務一", "任務二"],
        primary_task_key="T1.1",
        tasks=[Pair("T1.1", "任務一"), Pair("T1.2", "任務二")], blocks=[block],
    )
    blockless = NormalizedTaskGroup(
        task_orders=[3], task_ids=["T1.3"], task_titles=["任務三"],
        primary_task_key="T1.3", tasks=[Pair("T1.3", "任務三")], blocks=[],
    )
    unit = NormalizedUnit(unit_order=1, unit_id="U1", unit_title="單元一",
                          unit_key="U1", task_groups=[multi, blockless])
    return NormalizedOCS(
        ocs_code="OC1v1", ocs_code_base="OC1", job_title="JT",
        job_category=None, job_category_codes=[], industry_codes=[], industry_names=[],
        occupation_codes=[], occupation_names=[], job_description=None, ocs_level=None,
        version="v1", version_seq=1, update_date=None, is_current=True, units=[unit],
        attitude_codes=[], attitude_terms=[], attitude_pairs=[],
        prerequisites=[], supplements=[],
    )


_CTX = BuildContext(source_file="jd-ocs/OC1v1.json", indexed_at="2026-06-14T00:00:00+00:00")


def test_one_task_record_per_task_id():
    tasks = [r for r in build(_norm_two_tasks(), _CTX) if r.chunk_level == "task"]
    assert sorted(r.payload["task_id"] for r in tasks) == ["T1.1", "T1.2", "T1.3"]


def test_task_record_payload_and_examples():
    t11 = [r for r in build(_norm_two_tasks(), _CTX) if r.payload.get("task_id") == "T1.1"][0]
    p = t11.payload
    assert t11.chunk_key == "ocs:OC1v1:unit:U1:task:T1.1"
    assert p["chunk_level"] == "task" and p["ocs_code"] == "OC1v1"
    assert p["unit_id"] == "U1" and p["unit_title"] == "單元一"
    assert p["task_id"] == "T1.1" and p["task_title"] == "任務一"
    assert p["k_pairs"] == [{"code": "K01", "name": "知識一"}]
    assert p["s_pairs"] == [{"code": "S01", "name": "技能一"}]
    assert p["output_pairs"] == [{"code": "O01", "name": "產出一"}]
    assert p["competency_level"] == 3
    assert p["activity_examples"] == ["活動一", "活動二", "活動三"]
    assert "text" not in p
    assert "任務一" in t11.text and "活動一" in t11.text


def test_block_less_task_record():
    t13 = [r for r in build(_norm_two_tasks(), _CTX) if r.payload.get("task_id") == "T1.3"][0]
    assert t13.payload["k_pairs"] == [] and t13.payload["activity_examples"] == []
    assert t13.payload["competency_level"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_builder_task.py -v`
Expected: FAIL — `build` returns only the profile record.

- [ ] **Step 3: Add `_task_record` + extend `build`**

In `src/jd_ocs_indexer/ingestion/builder.py`, add `_task_record` (after `_profile_record`):

```python
def _task_record(norm: NormalizedOCS, unit: NormalizedUnit, task: Pair, agg: dict, ctx: BuildContext) -> ChunkRecord:
    activities = agg["activities"]
    embed_parts = [task.name, *activities]
    payload = {
        "chunk_level": "task",
        "ocs_code": norm.ocs_code,
        "unit_id": unit.unit_id,
        "unit_title": unit.unit_title,
        "task_id": task.code,
        "task_title": task.name,
        "activity_examples": activities[:_ACTIVITY_EXAMPLES],
        "k_pairs": [{"code": p.code, "name": p.name} for p in agg["k_pairs"]],
        "s_pairs": [{"code": p.code, "name": p.name} for p in agg["s_pairs"]],
        "output_pairs": [{"code": p.code, "name": p.name} for p in agg["output_pairs"]],
        "competency_level": agg["competency_level"],
        "source_file": ctx.source_file,
    }
    return ChunkRecord(
        chunk_key=f"ocs:{norm.ocs_code}:unit:{unit.unit_key}:task:{task.code}",
        chunk_level="task",
        text="\n".join(part for part in embed_parts if part and part.strip()),
        payload=payload,
    )
```

Replace `build` with the full version:

```python
def build(norm: NormalizedOCS, ctx: BuildContext) -> list[ChunkRecord]:
    records: list[ChunkRecord] = [_profile_record(norm, ctx)]
    for unit in norm.units:
        for group in unit.task_groups:
            agg = _aggregate_group(group)
            for task in group.tasks:
                records.append(_task_record(norm, unit, task, agg, ctx))
    return records
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_builder_task.py tests/test_builder_profile.py tests/test_builder.py -v`
Expected: all passed (3 + 2 + 2).

- [ ] **Step 5: Commit**

```bash
git add src/jd_ocs_indexer/ingestion/builder.py tests/test_builder_task.py
git commit -m "feat(builder): per-task records (multi-task split + block-less)"
```

---

## Task 7: Rewrite the `index` command + remove `render` + v3 collection

**Files:**
- Modify: `src/jd_ocs_indexer/config.py`
- Modify: `src/jd_ocs_indexer/store/writer.py`
- Modify: `src/jd_ocs_indexer/cli.py`
- Modify: `.env.example`

> This task restores the CLI (broken since Task 4).

- [ ] **Step 1: Default collection → `ocs_v3` (config.py)**

In `src/jd_ocs_indexer/config.py`, change the `qdrant_collection` default in `load_settings()`:

```python
        qdrant_collection=_env("QDRANT_COLLECTION", "ocs_v3") or "ocs_v3",
```

- [ ] **Step 2: Parametrize writer payload indexes (writer.py)**

In `src/jd_ocs_indexer/store/writer.py`, change `ensure_payload_indexes`:

```python
    def ensure_payload_indexes(self, indexes=None) -> None:
        for field_name, field_schema in (indexes if indexes is not None else PAYLOAD_INDEXES):
            try:
                self.client.create_payload_index(
                    collection_name=self.collection,
                    field_name=field_name,
                    field_schema=field_schema,
                )
            except Exception:
                continue
```

- [ ] **Step 3: Rewrite cli.py — remove `render`, rewrite `index`, fix imports**

In `src/jd_ocs_indexer/cli.py`:

(a) Replace the builder/renderer imports:
```python
from jd_ocs_indexer.ingestion.builder import BuildContext, build
```
(remove the old `from ... builder import BuilderContext, ChunkBuilder` and `from ... renderer import MarkdownRenderer`).

(b) **Delete the entire `render` command** (the `@app.command()` `def render(...)` block).

(c) Replace the `index` command body (the `@app.command()` `def index(...)` and `_index_impl(...)`) with this self-contained v3 version (full build, no manifest, no renderer):

```python
@app.command()
def index(
    scan_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    limit: int = typer.Option(0, "--limit", help="Stop after N files (0 = all)."),
) -> None:
    """v3 pipeline: reader -> normalize -> build -> embed -> upsert (profile + task points)."""
    settings = load_settings()
    reader = OCSJSONReader(settings.source_root)

    from jd_ocs_indexer.embeddings.bge_m3 import BGEM3Embedder
    from jd_ocs_indexer.store import schema

    embedder = BGEM3Embedder(
        model_name=settings.bge_m3_model, device=settings.bge_m3_device,
        use_fp16=settings.bge_m3_use_fp16, batch_size=settings.bge_m3_batch_size,
    )
    client = make_client(url=settings.qdrant_url, api_key=settings.qdrant_api_key, timeout=settings.qdrant_timeout)
    writer = QdrantWriter(
        client, settings.qdrant_collection,
        dense_size=embedder.dense_size, supports_sparse=embedder.supports_sparse,
        batch_size=settings.index_batch_size,
    )
    writer.ensure_collection()
    writer.ensure_payload_indexes(schema.PAYLOAD_INDEXES)

    started = time.time()
    indexed = failed = total = 0
    for i, (loaded, fail) in enumerate(reader.iter_loaded(scan_dir)):
        if limit and i >= limit:
            break
        if fail is not None:
            failed += 1
            console.print(f"[red]FAIL[/red] {fail.rel_path}: {fail.error}")
            continue
        assert loaded is not None
        norm = normalize(loaded.document)
        ctx = BuildContext(source_file=loaded.rel_path, indexed_at=_now_iso())
        records = build(norm, ctx)
        vecs = embedder.embed_texts([r.text for r in records])
        embedded = [EmbeddedChunk(record=r, dense=v.dense, sparse=v.sparse) for r, v in zip(records, vecs)]
        report = writer.upsert(embedded)
        total += report.upserted
        indexed += 1

    elapsed = time.time() - started
    table = Table(title="Index v3 report")
    table.add_column("metric"); table.add_column("value", justify="right")
    table.add_row("collection", settings.qdrant_collection)
    table.add_row("indexed_files", str(indexed))
    table.add_row("failed_files", str(failed))
    table.add_row("points", str(total))
    table.add_row("elapsed_sec", f"{elapsed:.1f}")
    console.print(table)
```

> If a `from jd_ocs_indexer.ingestion import manifest as manifest_mod` import (or `ChunkRecord` import) is now unused after removing `render`/old `index`, remove it too. Keep `EmbeddedChunk`, `normalize`, `OCSJSONReader`, `make_client`, `QdrantWriter`, `time`, `Table`, `_now_iso`, `console` — all still used.

- [ ] **Step 4: Verify the CLI is restored**

Run: `uv run jd-ocs-indexer --help`
Expected: lists commands WITHOUT `render`, WITH `index` (and the others: stats/doctor/smoke-query/query[/serve]).

Run: `uv run python -c "from jd_ocs_indexer.cli import app; from jd_ocs_indexer.ingestion.builder import build"`
Expected: exit 0, no output.

- [ ] **Step 5: Update `.env.example`**

In `.env.example`, change the collection line to the v3 default:
```bash
QDRANT_COLLECTION=ocs_v3
```

- [ ] **Step 6: Run full suite**

Run: `uv run pytest -q`
Expected: all pass (existing + new chunk/normalizer/schema/builder tests).

- [ ] **Step 7: Commit**

```bash
git add src/jd_ocs_indexer/config.py src/jd_ocs_indexer/store/writer.py src/jd_ocs_indexer/cli.py .env.example
git commit -m "feat(cli): rewrite index to v3, remove render, default ocs_v3 collection"
```

---

## Manual acceptance (after Task 7 — needs BGE-M3 + live Qdrant)

Not in CI. Run once:

```bash
jd-ocs-indexer index ./data/jd-json --limit 5
jd-ocs-indexer stats --collection ocs_v3
```

Expected: ~5 profile points + one task point per task; no unit/block points. The old `ocs_bgem3_v2` collection is untouched in Qdrant.

---

## Notes for the implementer

- **In-place rewrite**: there is no v2 builder anymore. The old `ocs_bgem3_v2` collection's *data* stays in Qdrant but is no longer written to; v3 writes to `ocs_v3`.
- **embed = action, not field**: embed string is on `ChunkRecord.text` (embedder reads it), never copied into `payload`. Tests assert `"text" not in payload`.
- **pairs are canonical**: K/S/output/attitude/task are `{code,name}` / aligned `Pair`; no flat code/term arrays in v3 payload.
- **completeness**: every task (incl. block-less) → a task point; multi-task groups → one point per task_id.
- **renderer.py is now unused** (nothing imports it) — leave it; delete in a later cleanup.
- **The v2 query API / reranker are still v2-shaped** — they get reworked for v3 in Phase 2/3 (expected).
- **No Co-Authored-By trailer** on commits (repo convention).
```
