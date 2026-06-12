# Schema v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將 OCS chunk schema 從 v1 升級為 v2，把 K/S/A/output 從 parallel arrays 改成 code-name pairs（修正靜默 bug + 給 LLM curator 正確配對），加入 profile-level 技能雲（提升 stage 1 retrieval），新增 profile aggregated *_pairs（給 curator 完整詞彙池），block 加 evidence 結構（給 curator 引用原句），並移除合成的 block_title（不誤導 LLM）。

**Architecture:** 改動集中在 ingestion 三件套（normalizer → builder → renderer），加上 docs / validation 顯示。不動 Qdrant collection schema（vectors + payload index 不變），但需要 `--rebuild` 全量重 index 才會用新 payload 取代舊資料。

**Tech Stack:** Python 3.11 / Pydantic v2 / FlagEmbedding (BGE-M3) / qdrant-client / Typer / Rich

---

## Self-Contained Verification Approach

本 repo **沒有 pytest 框架**（依目前範圍判斷不需要）。每個 task 的「驗證」用 lightweight `scripts/verify_v2_*.py` 寫一次性檢查腳本，跑完即可確認該改動成立。腳本 commit 進 repo 供後續 regression 使用。

驗證流程通則：
```bash
uv run python -m jd_ocs_indexer.cli render tests/fixtures -o output/md_v2
uv run python scripts/verify_v2_<task>.py
```

---

## File Map（決策鎖在這）

新檔：
- `scripts/verify_v2_pairs.py` — 驗證 Task 1-2 的 pair structure
- `scripts/verify_v2_profile.py` — 驗證 Task 3 的 profile 技能雲 + all_pairs
- `scripts/verify_v2_evidence.py` — 驗證 Task 4 的 block evidence
- `scripts/verify_v2_block_title.py` — 驗證 Task 5 block_title 移除

修改：
- `src/jd_ocs_indexer/ingestion/normalizer.py` — `NormalizedBlock` 加 pair 欄位、移除 block_id 合成
- `src/jd_ocs_indexer/ingestion/builder.py` — payload 寫 pair / evidence / all_*_pairs / 技能雲
- `src/jd_ocs_indexer/ingestion/renderer.py` — profile markdown 加技能雲區塊、移除 block_title 標題、block 用 evidence 結構渲染
- `src/jd_ocs_indexer/models/chunk.py` — 加 `Pair` TypedDict / dataclass
- `src/jd_ocs_indexer/validation/smoke_query.py` / `search.py` — 顯示 pair 結構
- `docs/SCHEMA.md` — 文件更新（commit）
- `docs/CHUNKING.md` — 文件更新（commit）

不改：
- `src/jd_ocs_indexer/models/ocs.py` — 來源 schema 沒變
- `src/jd_ocs_indexer/store/schema.py` — Qdrant vectors / payload index 不變
- `src/jd_ocs_indexer/store/writer.py` — upsert 行為不變
- `src/jd_ocs_indexer/embeddings/` — embedding 不變
- `src/jd_ocs_indexer/store/qdrant_client.py` — 不變

---

## SCHEMA_VERSION 升級

從 `ocs-index-v1` 升到 `ocs-index-v2`。`config.py` 預設值改 `ocs-index-v2`，`.env.example` 同步。

**Collection 名稱**：改用 `ocs_bgem3_v2`（雖然 vector 維度與模型沒變，但 payload schema 大幅變動，新 collection 比較乾淨且可保留舊 `ocs_bgem3_v2` 當歷史參考）。

`.env` / `.env.example` 同步改 `QDRANT_COLLECTION=ocs_bgem3_v2`。舊 `ocs_bgem3_v2` 不需要動，可隨時手動刪除。

---

## Task 1: 加 Pair dataclass + normalizer 產生 K/S/A/output pairs

**Files:**
- Modify: `src/jd_ocs_indexer/models/chunk.py`
- Modify: `src/jd_ocs_indexer/ingestion/normalizer.py:34-44` (NormalizedBlock)
- Modify: `src/jd_ocs_indexer/ingestion/normalizer.py:200-220` (block 組裝段)

### Steps

- [ ] **Step 1: 加 `Pair` dataclass 進 chunk.py**

`src/jd_ocs_indexer/models/chunk.py` 在 SparseVector 上方新增：

```python
@dataclass
class Pair:
    """Code-name pair for K/S/A/output/industry/occupation/job_category.

    Always written together — never separate the code from the name. Code-only
    lookups still use the parallel `*_codes` arrays for Qdrant payload index
    filters; pairs are for downstream LLM curator to look up name without
    risk of misalignment.
    """
    code: str
    name: str
```

- [ ] **Step 2: 改 `NormalizedBlock` 加 pair 欄位**

`src/jd_ocs_indexer/ingestion/normalizer.py`：

從 import 加入 Pair：
```python
from jd_ocs_indexer.models.chunk import Pair
```

`NormalizedBlock` dataclass 改：

```python
@dataclass
class NormalizedBlock:
    block_order: int
    competency_level: int | None
    indicator_codes: list[str] = field(default_factory=list)
    output_codes: list[str] = field(default_factory=list)
    indicator_texts: list[str] = field(default_factory=list)
    output_names: list[str] = field(default_factory=list)
    k_codes: list[str] = field(default_factory=list)
    s_codes: list[str] = field(default_factory=list)
    knowledge_terms: list[str] = field(default_factory=list)
    skill_terms: list[str] = field(default_factory=list)
    # v2 additions
    k_pairs: list[Pair] = field(default_factory=list)
    s_pairs: list[Pair] = field(default_factory=list)
    output_pairs: list[Pair] = field(default_factory=list)
    evidence: list[Pair] = field(default_factory=list)  # indicator_code + activity_text
```

`block_id` 與 `block_title` 整個移除（task 5 才做的事，但 dataclass 一次改完整）。

- [ ] **Step 3: 改 block 組裝段同步建 pair**

`src/jd_ocs_indexer/ingestion/normalizer.py` 找到 `for b_idx, b in enumerate(group.competency_blocks, start=1):` 那段，在現有 `ind_codes = ...` 等抽取後加入：

```python
# v2: 同步建 pair 結構 — 過濾條件統一以 code AND name 都存在為準
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
```

並把現有 `norm_blocks.append(NormalizedBlock(...))` 內加上新欄位：

```python
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
        # v2
        k_pairs=k_pairs,
        s_pairs=s_pairs,
        output_pairs=output_pairs,
        evidence=evidence,
    )
)
```

（注意：把 `block_id` 與 `block_title` 兩個欄位從 `NormalizedBlock` 構造段移除 — 因為 dataclass 已經沒這兩個欄位了）

- [ ] **Step 4: 改 attitude 也產 pair**

`src/jd_ocs_indexer/ingestion/normalizer.py` 找到 attitude 段（`attitude_codes` 那段）改成：

```python
attitude_codes: list[str] = []
attitude_terms: list[str] = []
attitude_pairs: list[Pair] = []
for a in doc.ocs_attitude.attitudes:
    if a.code:
        attitude_codes.append(a.code)
    if a.name:
        attitude_terms.append(a.name.strip())
    if a.code and a.name and a.name.strip():
        attitude_pairs.append(Pair(code=a.code, name=a.name.strip()))
```

把 `attitude_pairs` 也加進 `NormalizedOCS` dataclass 與 return：

```python
@dataclass
class NormalizedOCS:
    # ... 既有欄位
    attitude_pairs: list[Pair]  # v2
```

```python
return NormalizedOCS(
    # ... 既有欄位
    attitude_pairs=attitude_pairs,
)
```

- [ ] **Step 5: 寫驗證腳本**

新檔 `scripts/verify_v2_pairs.py`：

```python
"""Verify v2 pair structure produced by normalizer."""

from pathlib import Path

from jd_ocs_indexer.ingestion.normalizer import normalize
from jd_ocs_indexer.ingestion.reader import OCSJSONReader


def main() -> None:
    reader = OCSJSONReader(Path("S:/jd-pdf-to-json"))
    errors: list[str] = []
    files_checked = 0
    pair_check_count = 0

    for loaded, fail in reader.iter_loaded(Path("tests/fixtures")):
        if fail:
            errors.append(f"PARSE FAIL {fail.rel_path}: {fail.error}")
            continue
        assert loaded is not None
        norm = normalize(loaded.document)
        files_checked += 1

        # attitude pairs
        for ap in norm.attitude_pairs:
            if not ap.code or not ap.name:
                errors.append(f"{loaded.rel_path}: empty attitude pair {ap}")
            pair_check_count += 1

        for u in norm.units:
            for g in u.task_groups:
                for b in g.blocks:
                    for kp in b.k_pairs:
                        if not kp.code or not kp.name:
                            errors.append(f"{loaded.rel_path}: empty k pair {kp}")
                        pair_check_count += 1
                    for sp in b.s_pairs:
                        if not sp.code or not sp.name:
                            errors.append(f"{loaded.rel_path}: empty s pair {sp}")
                        pair_check_count += 1
                    for op in b.output_pairs:
                        if not op.code or not op.name:
                            errors.append(f"{loaded.rel_path}: empty output pair {op}")
                        pair_check_count += 1
                    for ev in b.evidence:
                        if not ev.code or not ev.name:
                            errors.append(f"{loaded.rel_path}: empty evidence {ev}")
                        pair_check_count += 1

                    # 反過來檢查：每個 k_code 都應該對應到 k_pair
                    pair_codes = {kp.code for kp in b.k_pairs}
                    for c in b.k_codes:
                        if c not in pair_codes:
                            errors.append(
                                f"{loaded.rel_path}: k_code {c} 沒對應 k_pair"
                            )

    print(f"files: {files_checked}, pairs checked: {pair_check_count}")
    if errors:
        for e in errors:
            print(f"  ERR: {e}")
        raise SystemExit(1)
    print("OK: all pairs well-formed")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: 跑驗證腳本**

```bash
uv run python scripts/verify_v2_pairs.py
```

Expected: `OK: all pairs well-formed`，無錯誤。

- [ ] **Step 7: Commit**

```bash
git add src/jd_ocs_indexer/models/chunk.py src/jd_ocs_indexer/ingestion/normalizer.py scripts/verify_v2_pairs.py
git commit -m "feat(normalizer): produce code-name pairs for K/S/A/output/evidence

Adds Pair dataclass and v2 fields on NormalizedBlock / NormalizedOCS.
Pairs guarantee code-name alignment (fixes parallel-array filter mismatch
bug where 'if k.code' vs 'if k.name' could produce mismatched lists).

Removes block_id and block_title from NormalizedBlock (synthetic, removed
per v2 design — block identity comes from block_order in chunk_key)."
```

---

## Task 2: builder 把 pair 寫進 chunk payload

**Files:**
- Modify: `src/jd_ocs_indexer/ingestion/builder.py:150-200` (block_record)
- Modify: `src/jd_ocs_indexer/ingestion/builder.py` (\_base_payload，加 schema_version 升級)

### Steps

- [ ] **Step 1: schema_version 預設升 v2，collection 改 v2**

`src/jd_ocs_indexer/config.py` 把 default 改成 `ocs-index-v2` 與 `ocs_bgem3_v2`：

```python
qdrant_collection=_env("QDRANT_COLLECTION", "ocs_bgem3_v2") or "ocs_bgem3_v2",
schema_version=_env("SCHEMA_VERSION", "ocs-index-v2") or "ocs-index-v2",
```

同步改 `.env.example` 與 `.env`：
```
QDRANT_COLLECTION=ocs_bgem3_v2
SCHEMA_VERSION=ocs-index-v2
```

- [ ] **Step 2: 改 builder.py 的 \_block\_record 加 v2 payload 欄位**

`src/jd_ocs_indexer/ingestion/builder.py` 找到 `_block_record` 方法，payload 加入：

```python
payload.update(
    {
        # ... 既有欄位保留
        "unit_id": unit.unit_id,
        "unit_title": unit.unit_title,
        # ... 中略
        "k_codes": block.k_codes,
        "s_codes": block.s_codes,
        "knowledge_terms": block.knowledge_terms,
        "skill_terms": block.skill_terms,
        "work_activity_terms": block.indicator_texts,
        # v2 additions: pair structures
        "k_pairs": [{"code": p.code, "name": p.name} for p in block.k_pairs],
        "s_pairs": [{"code": p.code, "name": p.name} for p in block.s_pairs],
        "output_pairs": [{"code": p.code, "name": p.name} for p in block.output_pairs],
        "evidence": [
            {"indicator_code": p.code, "activity_text": p.name}
            for p in block.evidence
        ],
        # v2: remove synthetic block_title
        "block_id": None,           # 不再合成
        "block_title": None,        # 不再合成
        # ... 既有欄位繼續
    }
)
```

注意：`block_id` 與 `block_title` 保留欄位 key 但設 `None`，給 consumer 端漸進相容。

- [ ] **Step 3: 改 \_unit\_record 也輸出 pair（從 child blocks 聚合）**

`src/jd_ocs_indexer/ingestion/builder.py` 的 `_unit_record` 方法，在聚合 K/S 那段加入 pair 聚合：

```python
# 既有的 K/S codes 聚合保留
# v2 additions: aggregate pairs (dedup by code)
k_pairs_dict: dict[str, str] = {}  # code -> name
s_pairs_dict: dict[str, str] = {}
output_pairs_dict: dict[str, str] = {}
for group in unit.task_groups:
    for block in group.blocks:
        for p in block.k_pairs:
            k_pairs_dict.setdefault(p.code, p.name)
        for p in block.s_pairs:
            s_pairs_dict.setdefault(p.code, p.name)
        for p in block.output_pairs:
            output_pairs_dict.setdefault(p.code, p.name)

# payload.update 內加：
payload.update({
    # ... 既有
    "k_pairs": [{"code": c, "name": n} for c, n in k_pairs_dict.items()],
    "s_pairs": [{"code": c, "name": n} for c, n in s_pairs_dict.items()],
    "output_pairs": [{"code": c, "name": n} for c, n in output_pairs_dict.items()],
})
```

- [ ] **Step 4: 改 \_profile\_record 輸出 all\_\*\_pairs**

`src/jd_ocs_indexer/ingestion/builder.py` 的 `_profile_record` 方法 加入 OCS-wide aggregation：

```python
def _profile_record(self, norm: NormalizedOCS, ctx: BuilderContext, chunk_key: str) -> ChunkRecord:
    payload = self._base_payload(norm, ctx, chunk_key, "profile")

    # v2: aggregate ALL pairs across all child blocks (for curator pool)
    all_k_dict: dict[str, str] = {}
    all_s_dict: dict[str, str] = {}
    all_output_dict: dict[str, str] = {}
    for u in norm.units:
        for g in u.task_groups:
            for b in g.blocks:
                for p in b.k_pairs:
                    all_k_dict.setdefault(p.code, p.name)
                for p in b.s_pairs:
                    all_s_dict.setdefault(p.code, p.name)
                for p in b.output_pairs:
                    all_output_dict.setdefault(p.code, p.name)

    payload.update(
        {
            "unit_id": None,
            "unit_title": None,
            # ... 既有保留
            # v2 additions: profile-level pools
            "all_k_pairs": [{"code": c, "name": n} for c, n in all_k_dict.items()],
            "all_s_pairs": [{"code": c, "name": n} for c, n in all_s_dict.items()],
            "all_a_pairs": [
                {"code": p.code, "name": p.name} for p in norm.attitude_pairs
            ],
            "all_output_pairs": [
                {"code": c, "name": n} for c, n in all_output_dict.items()
            ],
            # ... 既有 source_path, source_labels 等保留
        }
    )

    return ChunkRecord(
        chunk_key=chunk_key,
        chunk_level="profile",
        text="",
        payload=payload,
    )
```

- [ ] **Step 5: 加新驗證腳本 — 驗證 payload 真的有 pair**

修改 `scripts/verify_v2_pairs.py` 多檢查 `builder + render` 後 payload 結構（接著 normalize 改檢查 builder 輸出的 records）：

```python
"""Verify v2 pair structure in payload after build+render."""

from pathlib import Path

from jd_ocs_indexer.config import load_settings
from jd_ocs_indexer.ingestion.normalizer import normalize
from jd_ocs_indexer.ingestion.reader import OCSJSONReader
from jd_ocs_indexer.ingestion.builder import BuilderContext, ChunkBuilder
from jd_ocs_indexer.ingestion.renderer import MarkdownRenderer


def main() -> None:
    s = load_settings()
    reader = OCSJSONReader(s.source_root)
    builder = ChunkBuilder()
    renderer = MarkdownRenderer()
    errors: list[str] = []

    for loaded, fail in reader.iter_loaded(Path("tests/fixtures")):
        if fail:
            errors.append(f"PARSE: {fail.rel_path}: {fail.error}")
            continue
        assert loaded is not None
        norm = normalize(loaded.document)
        ctx = BuilderContext(
            source_root_alias=s.source_root_alias,
            source_file=loaded.rel_path,
            source_json_hash=loaded.source_json_hash,
            schema_version=s.schema_version,
            embedding_provider=s.embedding_provider,
        )
        records = builder.build(norm, ctx)
        renderer.render(norm, records)

        for r in records:
            p = r.payload
            if r.chunk_level == "block":
                for kp in p.get("k_pairs", []):
                    if not kp.get("code") or not kp.get("name"):
                        errors.append(f"{loaded.rel_path}/{r.chunk_key}: bad k_pair {kp}")
                for sp in p.get("s_pairs", []):
                    if not sp.get("code") or not sp.get("name"):
                        errors.append(f"{loaded.rel_path}/{r.chunk_key}: bad s_pair {sp}")
                for ev in p.get("evidence", []):
                    if not ev.get("indicator_code") or not ev.get("activity_text"):
                        errors.append(f"{loaded.rel_path}/{r.chunk_key}: bad evidence {ev}")
            elif r.chunk_level == "profile":
                if "all_k_pairs" not in p:
                    errors.append(f"{loaded.rel_path}: profile missing all_k_pairs")
                if "all_s_pairs" not in p:
                    errors.append(f"{loaded.rel_path}: profile missing all_s_pairs")
                if "all_a_pairs" not in p:
                    errors.append(f"{loaded.rel_path}: profile missing all_a_pairs")
                # 至少有 1 個 pair (fixtures 都有 K/S/A)
                if not p.get("all_k_pairs"):
                    errors.append(f"{loaded.rel_path}: empty all_k_pairs")

    if errors:
        for e in errors:
            print(f"  ERR: {e}")
        raise SystemExit(1)
    print("OK: payload pairs verified")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: 跑驗證**

```bash
uv run python scripts/verify_v2_pairs.py
```

Expected: `OK: payload pairs verified`。

- [ ] **Step 7: Commit**

```bash
git add src/jd_ocs_indexer/ingestion/builder.py src/jd_ocs_indexer/config.py .env.example scripts/verify_v2_pairs.py
git commit -m "feat(builder): write code-name pairs + profile aggregated pools into payload

- block payload: k_pairs / s_pairs / output_pairs / evidence (indicator + text)
- unit payload: aggregated k_pairs / s_pairs / output_pairs (dedup by code)
- profile payload: all_k_pairs / all_s_pairs / all_a_pairs / all_output_pairs
  (OCS-wide vocabulary pool for LLM curator to pick from)
- schema_version default bumped to ocs-index-v2
- block_id / block_title now None (synthetic identity removed)"
```

---

## Task 3: profile renderer 加技能雲

**Files:**
- Modify: `src/jd_ocs_indexer/ingestion/renderer.py` (`_render_profile` method)

### Steps

- [ ] **Step 1: 改 `_render_profile` 加技能雲區塊**

`src/jd_ocs_indexer/ingestion/renderer.py` 的 `_render_profile` 方法在「## 主要工作任務」段之後加入：

```python
def _render_profile(self, norm: NormalizedOCS) -> str:
    lines: list[str] = [_heading_title(norm)]
    # ... 既有 meta + 工作描述 + 主要工作任務 保留

    # v2: aggregate skill cloud for retrieval signal
    all_k_names: list[str] = []
    all_s_names: list[str] = []
    seen_k: set[str] = set()
    seen_s: set[str] = set()
    for u in norm.units:
        for g in u.task_groups:
            for b in g.blocks:
                for p in b.k_pairs:
                    if p.name not in seen_k:
                        seen_k.add(p.name)
                        all_k_names.append(p.name)
                for p in b.s_pairs:
                    if p.name not in seen_s:
                        seen_s.add(p.name)
                        all_s_names.append(p.name)

    if all_k_names:
        lines.append("")
        lines.append("## 核心知識領域")
        lines.append(_bullet_list(all_k_names))

    if all_s_names:
        lines.append("")
        lines.append("## 核心技能")
        lines.append(_bullet_list(all_s_names))

    # 既有的態度需求 / 任職條件 / 補充說明 保留
    # ... rest unchanged
    return "\n".join(lines).rstrip() + "\n"
```

注意：技能雲放在「主要工作任務」之後、「態度需求」之前。

- [ ] **Step 2: 寫驗證腳本**

新檔 `scripts/verify_v2_profile.py`：

```python
"""Verify v2 profile markdown contains skill cloud."""

from pathlib import Path

from jd_ocs_indexer.config import load_settings
from jd_ocs_indexer.ingestion.normalizer import normalize
from jd_ocs_indexer.ingestion.reader import OCSJSONReader
from jd_ocs_indexer.ingestion.builder import BuilderContext, ChunkBuilder
from jd_ocs_indexer.ingestion.renderer import MarkdownRenderer


def main() -> None:
    s = load_settings()
    reader = OCSJSONReader(s.source_root)
    builder = ChunkBuilder()
    renderer = MarkdownRenderer()
    errors: list[str] = []
    sample_text = None

    for loaded, fail in reader.iter_loaded(Path("tests/fixtures")):
        if fail:
            continue
        assert loaded is not None
        norm = normalize(loaded.document)
        ctx = BuilderContext(
            source_root_alias=s.source_root_alias,
            source_file=loaded.rel_path,
            source_json_hash=loaded.source_json_hash,
            schema_version=s.schema_version,
            embedding_provider=s.embedding_provider,
        )
        records = builder.build(norm, ctx)
        renderer.render(norm, records)

        for r in records:
            if r.chunk_level != "profile":
                continue
            text = r.text
            if "## 核心知識領域" not in text:
                errors.append(f"{loaded.rel_path}: profile missing '核心知識領域'")
            if "## 核心技能" not in text:
                errors.append(f"{loaded.rel_path}: profile missing '核心技能'")

            # profile 應該至少有 5 個 K (fixtures 都有充足 K)
            k_section = text.split("## 核心知識領域")[1].split("## ")[0] if "## 核心知識領域" in text else ""
            k_bullets = [l for l in k_section.splitlines() if l.startswith("- ")]
            if len(k_bullets) < 5:
                errors.append(f"{loaded.rel_path}: profile 核心知識 only {len(k_bullets)} bullets")

            if sample_text is None:
                sample_text = text

    if errors:
        for e in errors:
            print(f"  ERR: {e}")
        raise SystemExit(1)
    print("OK: profile skill cloud present")
    if sample_text:
        print("\n--- sample profile markdown (first 80 lines) ---")
        for ln in sample_text.splitlines()[:80]:
            print(ln)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 跑驗證 + 人工檢查樣本輸出**

```bash
uv run python scripts/verify_v2_profile.py
```

Expected: `OK: profile skill cloud present` + 印出 sample 範例 markdown。

人工確認樣本：
- 技能雲區塊有 K 名稱去重列出
- 順序合理（先 K 後 S）
- 中文沒亂碼（如果在 PowerShell 跑要先 `$env:PYTHONIOENCODING="utf-8"`）

- [ ] **Step 4: Commit**

```bash
git add src/jd_ocs_indexer/ingestion/renderer.py scripts/verify_v2_profile.py
git commit -m "feat(renderer): add skill cloud to profile markdown

Aggregates dedup K-names and S-names from all child blocks into the
profile chunk text under '核心知識領域' and '核心技能' headings. This
provides the retrieval signal needed for stage 1 candidate-OCS selection
when user query contains tool-level terms (SQL, Python, BI...) that
otherwise only appear in deeply-nested block chunks."
```

---

## Task 4: block evidence 結構在 renderer 顯示更清楚

**Files:**
- Modify: `src/jd_ocs_indexer/ingestion/renderer.py` (`_render_block_from_payload` method)

### Steps

- [ ] **Step 1: 改 `_render_block_from_payload` 用 evidence 結構渲染**

`src/jd_ocs_indexer/ingestion/renderer.py` 的 `_render_block_from_payload` 方法 — 把現有的「工作活動」段改成基於 evidence pair 列出：

找到：
```python
activities = p.get("work_activity_terms") or []
if activities:
    lines.append("")
    lines.append("工作活動：")
    lines.append(_bullet_list(activities))
```

改成：
```python
evidence = p.get("evidence") or []
if evidence:
    lines.append("")
    lines.append("工作活動：")
    for ev in evidence:
        code = ev.get("indicator_code", "")
        text = ev.get("activity_text", "")
        if code and text:
            lines.append(f"- ({code}) {text}")
        elif text:
            lines.append(f"- {text}")
```

同樣的，把現有 outputs 段（`outputs = b.output_names` 那段）改成：

```python
output_pairs = p.get("output_pairs") or []
if output_pairs:
    lines.append("")
    lines.append("工作產出：")
    for op in output_pairs:
        code = op.get("code", "")
        name = op.get("name", "")
        if code and name:
            lines.append(f"- ({code}) {name}")
        elif name:
            lines.append(f"- {name}")
```

並把 K / S 也改成顯示 (code) name：

```python
k_pairs = p.get("k_pairs") or []
if k_pairs:
    lines.append("")
    lines.append("必備知識：")
    for kp in k_pairs:
        lines.append(f"- ({kp['code']}) {kp['name']}")

s_pairs = p.get("s_pairs") or []
if s_pairs:
    lines.append("")
    lines.append("必備技能：")
    for sp in s_pairs:
        lines.append(f"- ({sp['code']}) {sp['name']}")
```

把現有 `knowledge_terms_local` / `skill_terms_local` 那塊整段移除（用 pair 取代）。

- [ ] **Step 2: 寫驗證腳本**

新檔 `scripts/verify_v2_evidence.py`：

```python
"""Verify v2 block markdown uses evidence + pair structure."""

from pathlib import Path

from jd_ocs_indexer.config import load_settings
from jd_ocs_indexer.ingestion.normalizer import normalize
from jd_ocs_indexer.ingestion.reader import OCSJSONReader
from jd_ocs_indexer.ingestion.builder import BuilderContext, ChunkBuilder
from jd_ocs_indexer.ingestion.renderer import MarkdownRenderer


def main() -> None:
    s = load_settings()
    reader = OCSJSONReader(s.source_root)
    builder = ChunkBuilder()
    renderer = MarkdownRenderer()
    errors: list[str] = []
    sample_block_text = None

    for loaded, fail in reader.iter_loaded(Path("tests/fixtures")):
        if fail:
            continue
        assert loaded is not None
        norm = normalize(loaded.document)
        ctx = BuilderContext(
            source_root_alias=s.source_root_alias,
            source_file=loaded.rel_path,
            source_json_hash=loaded.source_json_hash,
            schema_version=s.schema_version,
            embedding_provider=s.embedding_provider,
        )
        records = builder.build(norm, ctx)
        renderer.render(norm, records)

        for r in records:
            if r.chunk_level != "block":
                continue
            text = r.text
            # 必須有 indicator code 的格式 (PN.N.N)
            import re
            if not re.search(r"\(P\d", text):
                errors.append(f"{loaded.rel_path}/{r.chunk_key}: block lacks (Pn.n.n) indicator code")
            if "必備知識：" not in text:
                errors.append(f"{loaded.rel_path}/{r.chunk_key}: missing 必備知識 section")
            # 必備知識下必須有 (Knn) 格式
            kn_section = text.split("必備知識：")[1].split("必備技能：")[0] if "必備知識：" in text else ""
            if not re.search(r"\(K\d{2}\)", kn_section):
                errors.append(f"{loaded.rel_path}/{r.chunk_key}: K codes not formatted as (Knn)")

            if sample_block_text is None:
                sample_block_text = text

    if errors:
        for e in errors[:20]:
            print(f"  ERR: {e}")
        raise SystemExit(1)
    print("OK: block evidence structure verified")
    if sample_block_text:
        print("\n--- sample block markdown ---")
        print(sample_block_text)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 跑驗證 + 人工確認樣本**

```bash
uv run python scripts/verify_v2_evidence.py
```

Expected: `OK: block evidence structure verified` + 印出範例 block。

人工確認：
- 工作活動的每一條都帶 (P1.1.1) 之類的 indicator code
- 必備知識 / 必備技能每一條都帶 (K01) / (S01) 之類的 code
- 視覺上易讀，code 不會壓過 name

- [ ] **Step 4: Commit**

```bash
git add src/jd_ocs_indexer/ingestion/renderer.py scripts/verify_v2_evidence.py
git commit -m "feat(renderer): block markdown uses (code) name format

Block work activities, knowledge, skills, and outputs now render each
item with its OCS code in parentheses. This makes LLM curator citation
trivial (the code is right next to the content) and provides clean
audit trail. Renderer reads from payload pair structures rather than
parallel arrays."
```

---

## Task 5: 移除合成 block_title 與 block_id（含 chunk_key 影響檢查）

**Files:**
- Modify: `src/jd_ocs_indexer/ingestion/normalizer.py` (移除 block_id / block_title 合成段)
- Modify: `src/jd_ocs_indexer/ingestion/builder.py` (chunk_key 用 block_order，payload block_id/title=None)
- Modify: `src/jd_ocs_indexer/ingestion/renderer.py` (block markdown 標題改用 task title)

### Steps

- [ ] **Step 1: 移除 normalizer 內 block_id / block_title 合成段**

`src/jd_ocs_indexer/ingestion/normalizer.py` 找到：

```python
block_id = None
if ind_codes:
    head = ind_codes[0]
    parts = head.split(".")
    if len(parts) >= 2:
        block_id = ".".join(parts[:-1])
if not block_id:
    block_id = _padded(b_idx)

block_title = None
if out_names:
    block_title = out_names[0]
elif ind_texts:
    snippet = ind_texts[0].strip()
    block_title = snippet[:24] + ("…" if len(snippet) > 24 else "")
```

整段刪除。`NormalizedBlock` 構造段也對應移除 `block_id` 與 `block_title` 參數（Task 1 已經改過 dataclass）。

- [ ] **Step 2: 確認 builder 的 chunk_key 與 payload 對應**

`src/jd_ocs_indexer/ingestion/builder.py` 的 `_block_key` 已經是 `f"{block.block_order:04d}"`（在 Task 0 之前就修過碰撞 bug）。確認 builder 內 block_record 的 payload：
```python
"block_id": None,
"block_title": None,
```
(Task 2 已寫)

- [ ] **Step 3: 改 renderer block 標題改用 task title 當小節標**

`src/jd_ocs_indexer/ingestion/renderer.py` 的 `_render_block_from_payload` 找到：

```python
block_title = p.get("block_title") or ""
lines.append("")
lines.append(f"#### 能力區塊：{block_title}".rstrip())
if p.get("competency_level") is not None:
    lines.append(f"- 能力等級：L{p['competency_level']}")
```

改成（不用合成名稱，改顯示 task title + competency level）：

```python
# v2: no synthetic block title — use task title + block order
block_order = p.get("block_order")
lines.append("")
if block_order is not None:
    lines.append(f"#### 能力區塊 #{block_order}")
else:
    lines.append("#### 能力區塊")
if p.get("competency_level") is not None:
    lines.append(f"- 能力等級：L{p['competency_level']}")
```

- [ ] **Step 4: 驗證 — 確認沒有 block_title fallback 串字殘留**

新檔 `scripts/verify_v2_block_title.py`：

```python
"""Verify v2 block_title is None and markdown doesn't include synthetic title."""

from pathlib import Path

from jd_ocs_indexer.config import load_settings
from jd_ocs_indexer.ingestion.normalizer import normalize
from jd_ocs_indexer.ingestion.reader import OCSJSONReader
from jd_ocs_indexer.ingestion.builder import BuilderContext, ChunkBuilder
from jd_ocs_indexer.ingestion.renderer import MarkdownRenderer


def main() -> None:
    s = load_settings()
    reader = OCSJSONReader(s.source_root)
    builder = ChunkBuilder()
    renderer = MarkdownRenderer()
    errors: list[str] = []

    for loaded, fail in reader.iter_loaded(Path("tests/fixtures")):
        if fail:
            continue
        assert loaded is not None
        norm = normalize(loaded.document)
        ctx = BuilderContext(
            source_root_alias=s.source_root_alias,
            source_file=loaded.rel_path,
            source_json_hash=loaded.source_json_hash,
            schema_version=s.schema_version,
            embedding_provider=s.embedding_provider,
        )
        records = builder.build(norm, ctx)
        renderer.render(norm, records)

        for r in records:
            if r.chunk_level != "block":
                continue
            p = r.payload
            if p.get("block_title") is not None:
                errors.append(f"{r.chunk_key}: block_title={p['block_title']!r} should be None")
            if p.get("block_id") is not None:
                errors.append(f"{r.chunk_key}: block_id={p['block_id']!r} should be None")
            # markdown 不該有以 output name 截斷後當標題的串字
            # 隨機抽查：標題應該是「#### 能力區塊 #N」格式
            text = r.text
            import re
            block_heading_lines = [l for l in text.splitlines() if l.startswith("#### ")]
            for h in block_heading_lines:
                if not re.match(r"#### 能力區塊( #\d+)?$", h.rstrip()):
                    errors.append(f"{r.chunk_key}: unexpected block heading {h!r}")

    if errors:
        for e in errors[:20]:
            print(f"  ERR: {e}")
        raise SystemExit(1)
    print("OK: synthetic block_title removed cleanly")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 跑驗證**

```bash
uv run python scripts/verify_v2_block_title.py
```

Expected: `OK: synthetic block_title removed cleanly`

- [ ] **Step 6: Commit**

```bash
git add src/jd_ocs_indexer/ingestion/normalizer.py src/jd_ocs_indexer/ingestion/renderer.py scripts/verify_v2_block_title.py
git commit -m "refactor: remove synthetic block_title and block_id

OCS source JSON has no block-level label; synthesizing block_title from
the first output name or indicator text snippet was misleading (LLM
could mistake the snippet for an official block name). Block identity
is conveyed by ocs_code / unit / task / block_order alone."
```

---

## Task 6: smoke_query 與 search 顯示 pair 結構

**Files:**
- Modify: `src/jd_ocs_indexer/validation/smoke_query.py` (Hit class display fields)
- Modify: `src/jd_ocs_indexer/cli.py` (`_print_query_hit` use pair fields)

### Steps

- [ ] **Step 1: 改 cli.py 的 query 輸出用 k_pairs / s_pairs**

`src/jd_ocs_indexer/cli.py` 的 `_print_query_hit` 函式 — 找到顯示 codes 那段：

```python
k = p.get("k_codes") or []
s = p.get("s_codes") or []
if k or s:
    console.print(
        "    [dim]codes:[/dim] "
        + (f"K={','.join(k)}" if k else "")
        + ("  " if k and s else "")
        + (f"S={','.join(s)}" if s else "")
    )
```

改成：

```python
k_pairs = p.get("k_pairs") or []
s_pairs = p.get("s_pairs") or []
if k_pairs:
    lines = ", ".join(f"{kp['code']} {kp['name']}" for kp in k_pairs[:5])
    if len(k_pairs) > 5:
        lines += f" (+{len(k_pairs) - 5} more)"
    console.print(f"    [dim]K:[/dim] {lines}")
if s_pairs:
    lines = ", ".join(f"{sp['code']} {sp['name']}" for sp in s_pairs[:5])
    if len(s_pairs) > 5:
        lines += f" (+{len(s_pairs) - 5} more)"
    console.print(f"    [dim]S:[/dim] {lines}")
```

- [ ] **Step 2: 確認 smoke-query 仍能用 K/S filter（filter 用 codes 不用 pairs）**

`src/jd_ocs_indexer/validation/smoke_query.py` 的 `filter_by_ks_code` 函式 — 它用 `k_codes` / `s_codes`（不是 k_pairs），因為 Qdrant payload index 是建在 `k_codes` 上的。**不需要改**，但加註解：

```python
# Filter still uses k_codes/s_codes parallel arrays — pairs are for display only.
# The k_codes payload index supports MatchAny filter efficiently.
```

- [ ] **Step 3: 跑現有 fixture 測試 + 視覺確認 query 輸出**

```bash
# 清掉舊 v1 collection，rebuild v2
uv run python -c "
from jd_ocs_indexer.config import load_settings
from jd_ocs_indexer.store.qdrant_client import make_client
s = load_settings()
c = make_client(url=s.qdrant_url, api_key=s.qdrant_api_key)
if c.collection_exists('ocs_bgem3_v2'):
    c.delete_collection('ocs_bgem3_v2')
print('cleared')
"
rm -f .data/manifest.json
uv run python -m jd_ocs_indexer.cli index tests/fixtures
```

Expected: 66 chunks 寫入，無錯誤。

人工確認 query 輸出 K/S 用 pair 格式顯示：
```bash
uv run python -m jd_ocs_indexer.cli query "AI 部署系統整合" --top-k 2 --text-lines 0
```

預期看到：
```
K: K05 機器學習概論, K08 專案管理知識, K09 人工智慧概論, ...
S: S03 技術評估與分析能力, S05 問題解決能力, ...
```

- [ ] **Step 4: smoke-query 三類驗證仍通過**

```bash
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v2 --ocs-code SMS2512-002v1 --limit 3
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v2 -k K01 -s S01 --limit 3
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v2 --probe-vector "AI 部署" --limit 3
```

Expected: 三個都有結果，分數類似 v1（dense 0.7 範圍）。

- [ ] **Step 5: Commit**

```bash
git add src/jd_ocs_indexer/cli.py src/jd_ocs_indexer/validation/smoke_query.py
git commit -m "feat(cli): query/smoke-query display K/S as code+name pairs

Hit output now shows 'K05 機器學習概論' instead of just 'K05', so users
can read results without external lookup. Filters still use parallel
codes arrays (payload index)."
```

---

## Task 7: 更新 SCHEMA.md / CHUNKING.md 文件

**Files:**
- Modify: `docs/SCHEMA.md`
- Modify: `docs/CHUNKING.md`
- Modify: `docs/RETRIEVAL.md` (is_current default 提醒)

### Steps

- [ ] **Step 1: SCHEMA.md 加 v2 payload 欄位**

`docs/SCHEMA.md` 在 §3.1 Complete payload 內加：

```python
# v2 additions (block level)
"k_pairs": list[{"code": str, "name": str}],
"s_pairs": list[{"code": str, "name": str}],
"output_pairs": list[{"code": str, "name": str}],
"evidence": list[{"indicator_code": str, "activity_text": str}],

# v2 additions (unit level)
"k_pairs": list[...],
"s_pairs": list[...],
"output_pairs": list[...],

# v2 additions (profile level)
"all_k_pairs": list[...],   # OCS-wide K pool
"all_s_pairs": list[...],   # OCS-wide S pool
"all_a_pairs": list[...],   # OCS-wide attitude pool
"all_output_pairs": list[...],

# v2: deprecated (kept as None for backward compat)
"block_id": None,    # was synthetic, no source field
"block_title": None, # was synthetic, no source field
```

在 §3.5 Field Semantics 加：

```markdown
### `*_pairs` (v2)

Each pair is `{"code": str, "name": str}`. Code-name binding never separates
— this prevents the bug where parallel `_codes` and `_terms` lists could
desynchronize when source JSON had partial entries.

Parallel `_codes` arrays are still maintained for Qdrant payload index
filtering (e.g., "find all blocks where k_codes contains K01"). The pair
structure is purely for downstream consumers needing code-name lookup.

### `evidence` (v2, block level)

Replaces `indicator_codes` + `work_activity_terms` parallel arrays. Each
entry is `{"indicator_code": "P1.1.1", "activity_text": "..."}`. LLM
curator uses `activity_text` as the canonical OCS sentence to cite, with
`indicator_code` as the citation key.

### `all_*_pairs` (v2, profile level)

OCS-wide aggregated pools. When LLM curator generates custom job activities
that aren't in standard OCS, it picks K/S/A from `all_*_pairs` rather than
inventing new codes. Consumer can also use these as menu options when
showing "select your relevant skills" UI.
```

- [ ] **Step 2: CHUNKING.md 加 profile 技能雲說明**

`docs/CHUNKING.md` 第 4 節 Profile Chunk 加：

```markdown
### v2: 技能雲段落

profile chunk markdown 在「主要工作任務」之後新增兩個區塊：
- `## 核心知識領域`：去重彙整所有子 block 的 K-names
- `## 核心技能`：去重彙整所有子 block 的 S-names

**為什麼**：使用者粗描述常用工具名稱（SQL、Python、Power BI），這類詞
原本只在 block 層的 skill_terms 出現，profile 層 dense + sparse 都漏。
加技能雲後 stage 1 retrieval 命中率大幅提升。

成本：profile chunk text 變長（~500 → ~1500 字），但 BGE-M3 max_length
8192 容得下，sparse vector nnz 增加但 Qdrant 處理沒問題。
```

第 6 節 Block Chunk 加：

```markdown
### v2: 移除合成 block_title

OCS JSON 沒有 block 層名稱。v1 從 output[0].name 或 indicator[0].text 
截斷當作 block_title，但這會誤導 LLM 以為「這 block 叫 XXX」。v2 起
block payload `block_title = None`，markdown 改用 `#### 能力區塊 #N` 
作為小節標題（N 是 block_order，1-based）。

block 身份由 ocs_code + unit + task + block_order 共同確認，不需要
合成名稱。
```

- [ ] **Step 3: RETRIEVAL.md 加 is_current 預設提醒**

`docs/RETRIEVAL.md` 在 §3 開頭加：

```markdown
### 3.0 重要：預設加 is_current=true filter

908 份 OCS 含舊版本（v1/v2/v3/v4 並存於同一 collection）。Consumer
端寫 query 時建議預設加：

```python
models.FieldCondition(key="is_current", match=models.MatchValue(value=True))
```

避免推薦到已被取代的舊版本。只有審計、版本比對等特殊需求才查 
is_current=false。
```

- [ ] **Step 4: Commit**

```bash
git add docs/SCHEMA.md docs/CHUNKING.md docs/RETRIEVAL.md
git commit -m "docs: document v2 schema changes (pairs, skill cloud, evidence)

- SCHEMA.md: payload pair fields, all_*_pairs profile pools, evidence structure
- CHUNKING.md: profile skill cloud section, block_title removal rationale
- RETRIEVAL.md: is_current=true filter recommended default for consumers"
```

---

## Task 8: 全量 rebuild 驗證收尾

**Files:**
- 無程式修改，只跑 index + 驗證

### Steps

- [ ] **Step 1: 清掉舊 fixture collection（如 task 6 沒做）**

```bash
uv run python -c "
from jd_ocs_indexer.config import load_settings
from jd_ocs_indexer.store.qdrant_client import make_client
s = load_settings()
c = make_client(url=s.qdrant_url, api_key=s.qdrant_api_key)
if c.collection_exists('ocs_bgem3_v2'):
    c.delete_collection('ocs_bgem3_v2')
print('cleared')
"
rm -f .data/manifest.json
```

- [ ] **Step 2: fixture 端對端驗證**

```bash
uv run python -m jd_ocs_indexer.cli index tests/fixtures
uv run python -m jd_ocs_indexer.cli stats --collection ocs_bgem3_v2
```

Expected:
- index 顯示 66 chunks 寫入
- stats 顯示 total_points=66, level_profile=3, level_unit=15, level_block=48

- [ ] **Step 3: 跑全部 4 個 verify script 通過**

```bash
uv run python scripts/verify_v2_pairs.py
uv run python scripts/verify_v2_profile.py
uv run python scripts/verify_v2_evidence.py
uv run python scripts/verify_v2_block_title.py
```

Expected: 4 個都印 `OK: ...`

- [ ] **Step 4: 跑 query 視覺驗證 + 自然語言 sanity check**

```bash
# PowerShell:
# $env:PYTHONIOENCODING="utf-8"

uv run python -m jd_ocs_indexer.cli query "我會用 SQL 跟 Python 做資料清理跟 LLM 微調" --level profile --top-k 3
uv run python -m jd_ocs_indexer.cli query "AI 部署系統整合" --level block --hybrid --top-k 3
```

預期：
- profile 查詢的 top hit 是 AI 應用相關職務（因為技能雲含 LLM 相關 term）
- block 查詢的 top hit 是 T3.3 確保AI應用部署與系統整合
- K/S 用 "K05 機器學習概論" 這種 pair 格式顯示

- [ ] **Step 5: 全量索引（OPTIONAL）**

如果硬體與時間允許：
```bash
# 清掉舊 collection 再跑（不混 v1/v2）
uv run python -c "..."  # delete collection
rm -f .data/manifest.json
uv run python -m jd_ocs_indexer.cli index S:/jd-pdf-to-json/output/0518
uv run python -m jd_ocs_indexer.cli stats --collection ocs_bgem3_v2
```

CPU 預估 80-100 分鐘。Expected：
- total_points ≈ 12,869 (908 + 3,272 + 8,689)
- 三個 level 數字符合 v1 實測

- [ ] **Step 6: Commit**

無程式變更，但補一個 commit message 標記 v2 完成：

```bash
git commit --allow-empty -m "milestone: schema v2 fixture acceptance complete

- 5 P0 changes implemented (pairs / skill cloud / all_pairs / evidence / no block_title)
- 4 verify scripts pass on fixtures (66 chunks)
- query / smoke-query output displays new pair structure
- ready for full rebuild on S:/jd-pdf-to-json/output/0518"
```

---

## Self-Review Checklist

Done by plan author before handoff:

**Spec coverage:**
- [x] P0-1 K/S/A/output pairs → Task 1+2
- [x] P0-2 profile chunk skill cloud → Task 3
- [x] P0-3 profile all_*_pairs → Task 2 Step 4
- [x] P0-4 block evidence structure → Task 1 (data) + Task 4 (rendering)
- [x] P0-5 remove synthetic block_title → Task 5
- [x] schema_version bump → Task 2 Step 1
- [x] docs update → Task 7
- [x] is_current filter recommendation → Task 7 Step 3

**Anti-patterns avoided:**
- ✅ No "fill in details later"
- ✅ Every code step has exact code
- ✅ Every command has expected output
- ✅ Verify scripts exist for each schema change
- ✅ Commits between tasks (don't batch)

**Type consistency:**
- `Pair` dataclass referenced in Task 1, used in Tasks 1-6 — name stable ✓
- `k_pairs` / `s_pairs` / `output_pairs` / `evidence` field names stable across normalizer / builder / renderer / cli ✓
- `all_k_pairs` / `all_s_pairs` / `all_a_pairs` field names stable in profile payload + RETRIEVAL.md spec ✓

**Gaps fixed inline:**
- (none — all P0 covered)

---

## Estimated Time

| Task | Time |
|---|---|
| Task 1 normalizer pairs | 60 min |
| Task 2 builder payload + all_pairs | 90 min |
| Task 3 profile skill cloud | 45 min |
| Task 4 block evidence rendering | 60 min |
| Task 5 remove block_title | 30 min |
| Task 6 cli display pairs | 30 min |
| Task 7 docs update | 30 min |
| Task 8 verify + (optional) full rebuild | 30 min + 80-100 min |
| **Total（不含全量）** | **~6.5 hours** |
| **Total（含全量）** | **~8 hours** |

實際單天可完成 fixture acceptance。全量索引可隔夜跑。

---

## Open Questions for Implementation

實作前需要使用者確認的事：

1. **是否同時 commit 4 個 docs（USER_FLOW / V2_PLAN / BUG_LOG / DESIGN_DECISIONS）**
   - 使用者說「這部分不用 git」 — 我會保留 4 份 docs 不 commit，但 SCHEMA.md / CHUNKING.md / RETRIEVAL.md（task 7）是要 commit 的
   - 確認：4 份新 docs（USER_FLOW / V2_PLAN / BUG_LOG / DESIGN_DECISIONS）gitignore 嗎？還是只是不 commit？

2. **全量 rebuild 是否現在跑？**
   - 上次跑的全量索引已經寫進 collection（v1 schema）
   - v2 改動完成後，建議 `--rebuild` 全量跑一次
   - 80-100 min CPU 時間，可隔夜跑

3. **Collection 名稱**：使用者確認改用 `ocs_bgem3_v2`。舊 `ocs_bgem3_v1` collection 保留不動，當歷史參考，可隨時手動刪除。
