# Phase 3b — pdf-to-json `ocs_transformer.py` god-file 拆解 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans。逐 task,每 task 結束 = **golden 比對逐字節相同 + `uv run --extra dev pytest -q` 綠**。

**Goal:** 把 1492 行的 `OCSTransformer`(單一 god-class)拆成 `support/`(共用工具)+ `sections/`(五個區段擷取器,Pipes-and-Filters)+ 瘦 `ocs_transformer.py`(orchestrator),**行為逐字節不變**。

**Architecture:** Extract Class「搬移式」重構(逐字搬方法、不改邏輯)。先用真實 PDF 建 golden/characterization 測試當安全網(Feathers),再由葉子(support)往上搬到 sections,最後 orchestrator 變薄。研究見 `../specs/2026-06-28-pdf-to-json-transformer-decomposition-research.md`。

**Tech Stack:** Python、pytest、pdfplumber(既有 parser)、ocs-contract 型別(Phase 2)。

## Global Constraints

- **行為不變**:每步 golden 輸出**逐字節相同** + 既有 11 測試綠。**只搬不改邏輯**。
- **搬移式**:方法整段搬到新模組;stateless 工具 → 模組函式;有狀態/分區的 → 區段類別。呼叫點同步改(`self._x()` → `text.x()` 等)。
- 真實 PDF 取自 `/s/jd-pdf-to-json/data/*.pdf`(908 個);取**少數多樣**幾個複製進 fixture。
- 不改 `base.py`(`BaseOCSTransformer` port)、不改對外行為(`transform(raw_data)->OCSDocument` 簽章不變)。

---

### Task 1: golden/characterization 安全網

**Files:**
- Create: `apps/pdf-to-json/tests/fixtures/sample_pdfs/*.pdf`(複製 5 個多樣真實 PDF)
- Create: `apps/pdf-to-json/tests/fixtures/golden/*.json`(對應 transform 輸出)
- Create: `apps/pdf-to-json/tests/test_golden.py`
- Create: `apps/pdf-to-json/scripts/gen_golden.py`(產 golden 用,可重跑)

**Interfaces:**
- Produces: 一組「PDF → 預期 OCSDocument JSON」golden;`test_golden.py` 跑全管線比對。

- [ ] **Step 1: 複製 5 個多樣 PDF 進 fixture**

```bash
cd /s/caliburn/apps/pdf-to-json && mkdir -p tests/fixtures/sample_pdfs tests/fixtures/golden
# 取 5 個跨類別的(名稱以實際為準)
for n in "3D列印積層製造工程師" "AIoT應用工程師" "AI應用規劃師"; do
  cp "/s/jd-pdf-to-json/data/${n}-職能基準.pdf" tests/fixtures/sample_pdfs/ 2>/dev/null || true
done
ls tests/fixtures/sample_pdfs
```
(挑 3–5 個即可;確保複製成功。)

- [ ] **Step 2: 寫 `scripts/gen_golden.py`(產 golden)**

```python
"""Generate golden transform outputs from sample PDFs (run once / when behaviour intentionally changes)."""
import json
from pathlib import Path
from jd_pdf_to_json.parsers.pdf_parser import PDFParser   # 以實際 parser 類名為準
from jd_pdf_to_json.transformers.ocs_transformer import OCSTransformer

HERE = Path(__file__).resolve().parent.parent
PDFS = HERE / "tests/fixtures/sample_pdfs"
GOLD = HERE / "tests/fixtures/golden"

def main():
    GOLD.mkdir(parents=True, exist_ok=True)
    parser, tx = PDFParser(), OCSTransformer()
    for pdf in sorted(PDFS.glob("*.pdf")):
        raw = parser.parse(pdf)
        doc = tx.transform(raw)
        out = GOLD / (pdf.stem + ".json")
        out.write_text(json.dumps(doc.model_dump(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        print("wrote", out.name)

if __name__ == "__main__":
    main()
```
(`PDFParser` / `parse` 名稱以 `parsers/pdf_parser.py` 實際為準,執行前確認。)

- [ ] **Step 3: 產生 golden(基準 = 現有行為)**

```bash
cd /s/caliburn/apps/pdf-to-json && uv run python scripts/gen_golden.py && ls tests/fixtures/golden
```
Expected:每個 PDF 一個 golden JSON。

- [ ] **Step 4: 寫 `tests/test_golden.py`**

```python
import json
from pathlib import Path
import pytest
from jd_pdf_to_json.parsers.pdf_parser import PDFParser
from jd_pdf_to_json.transformers.ocs_transformer import OCSTransformer

HERE = Path(__file__).resolve().parent
PDFS = HERE / "fixtures/sample_pdfs"
GOLD = HERE / "fixtures/golden"

@pytest.mark.parametrize("pdf", sorted(PDFS.glob("*.pdf")), ids=lambda p: p.stem)
def test_transform_matches_golden(pdf):
    raw = PDFParser().parse(pdf)
    doc = OCSTransformer().transform(raw)
    got = json.loads(json.dumps(doc.model_dump(), ensure_ascii=False, sort_keys=True))
    want = json.loads((GOLD / (pdf.stem + ".json")).read_text(encoding="utf-8"))
    assert got == want
```

- [ ] **Step 5: 驗證 golden 測試通過(基準綠)**

```bash
cd /s/caliburn/apps/pdf-to-json && uv run --extra dev pytest tests/test_golden.py -q
```
Expected:全 pass(這是拆解前的行為基準)。

- [ ] **Step 6: Commit**(fixtures 可能被 *.json/*.pdf gitignore → 需 `git add -f`)

```bash
cd /s/caliburn && git add -f apps/pdf-to-json/tests/fixtures && git add apps/pdf-to-json/tests/test_golden.py apps/pdf-to-json/scripts/gen_golden.py
git commit -m "test(pdf-to-json): golden/characterization net for transformer (real PDFs) before decomposition"
```

---

### Task 2: 抽 `support/text.py`(葉子工具,建立 pattern)

**Files:**
- Create: `apps/pdf-to-json/src/jd_pdf_to_json/transformers/support/__init__.py`
- Create: `apps/pdf-to-json/src/jd_pdf_to_json/transformers/support/text.py`
- Modify: `transformers/ocs_transformer.py`(移除這些方法,改呼叫 `support.text`)

**搬移清單(文字正規化,stateless → 模組函式):**
`_normalize_text`、`_compact_wrapped_text`、`_split_lines`、`_split_multi_value`、`_append_text_if_new`。

- [ ] **Step 1: 把上述方法逐字搬到 `support/text.py`** 成模組函式(去掉 `self`,名稱去前底線:`normalize_text` 等),保留邏輯不變。
- [ ] **Step 2: `ocs_transformer.py` 改呼叫**:`self._normalize_text(x)` → `text.normalize_text(x)`(import `from jd_pdf_to_json.transformers.support import text`),刪掉原方法。
- [ ] **Step 3: golden + 全測試**

```bash
cd /s/caliburn/apps/pdf-to-json && uv run --extra dev pytest -q
```
Expected:11 + golden 全綠(逐字節相同)。**有 diff → 表示搬錯,回退比對。**

- [ ] **Step 4: Commit**

```bash
cd /s/caliburn && git add apps/pdf-to-json/src && git commit -m "refactor(pdf-to-json): extract transformers/support/text (move-only; golden green)"
```

---

### Task 3: 抽其餘 `support/`(tables / items / dedupe / scanning)

**Files:**
- Create: `support/tables.py`、`support/items.py`、`support/dedupe.py`、`support/scanning.py`
- Modify: `ocs_transformer.py`

**搬移清單(依現有區段註解):**
- `tables.py`:`_row_to_normalized_cells`、`_row_to_joined_normalized_text`、`_merge_rows_for_header`、`_is_page_footer_row`、`_clean_table_rows`、`_is_content_header_row`、`_is_split_content_header`、`_detect_table_type`、`_find_ocu_header_row`、`_is_ocu_candidate_table`、`_find_value_to_right`、`_find_cell_value`、`_build_column_map`。
- `items.py`:`_extract_output_items`、`_extract_behavioral_indicators(_from_row)`、`_extract_competency_items(_from_row)`、`_extract_task_level`。
- `dedupe.py`:`_dedupe`、`_dedupe_outputs`、`_dedupe_indicators`、`_dedupe_competencies`、`_dedupe_block`。
- `scanning.py`:`_scan_ocu_names_from_text`、`_scan_task_names_from_words`、`_derive_task_code_from_p_codes`、`_is_generic_unit_name`、`_merge_ocu_unit`。

> 逐模組搬(一個 commit 一個模組,各自 golden+測試綠),降低一次搬太多的風險。stateless 的轉模組函式;若有用到 alias 表(`__init__` 的欄位)等實例狀態,改成傳參或模組常數。

- [ ] **Step 1–4(每模組重複)**:搬 → 改呼叫 → `uv run --extra dev pytest -q`(全綠)→ commit。每模組一輪。

---

### Task 4: 抽 `sections/`(五個區段擷取器,Pipes-and-Filters)

**Files:**
- Create: `sections/__init__.py`、`sections/version_extractor.py`、`profile_extractor.py`、`content_extractor.py`、`attitude_extractor.py`、`notes_extractor.py`
- Modify: `ocs_transformer.py`

**搬移清單:**
- `version_extractor.py`:`_extract_version_info`。
- `profile_extractor.py`:`_extract_profile` + profile 小工具(`_match_profile_label`、`_extract_category_code`、`_extract_occupation_code`、`_extract_first_code`、`_extract_job_categories_from_table`、`_extract_occupations_from_table`、`_extract_industries_from_table`)。
- `content_extractor.py`(最大):`_extract_content`、`_parse_task_codes`、`_parse_ocu_table_units`(含內層 `_ensure_unit`)。用 `support.tables/items/dedupe/scanning`。
- `attitude_extractor.py`:`_extract_attitude`。
- `notes_extractor.py`:`_extract_notes`。

每個擷取器設計成一個類別(或函式)`extract(pdf[, version_info]) -> <ocs-contract 區段型別>`,內部呼叫 `support.*`。

- [ ] **每區段一輪**:搬該區段方法到擷取器 → `transform()` 改呼叫擷取器 → `uv run --extra dev pytest -q` 全綠 → commit。**先小的(version/attitude/notes)再大的(profile/content)**,逐步降風險。

---

### Task 5: 瘦 orchestrator + 收尾

**Files:**
- Modify: `ocs_transformer.py`（只剩 `transform()` 編排 + alias 表/常數)

- [ ] **Step 1: 確認 `transform()` 只剩薄編排**(建各 extractor、依序跑、組 `OCSDocument`),`ocs_transformer.py` 行數大幅下降。
- [ ] **Step 2: 全綠最終驗收**

```bash
cd /s/caliburn && npx turbo test 2>&1 | grep -E "Tasks:|passed|Failed"
```
Expected:3/3(pdf-to-json = 11 + golden 全綠)。

- [ ] **Step 3: Commit + tag**

```bash
cd /s/caliburn && git add apps/pdf-to-json && git commit -m "refactor(pdf-to-json): thin transform() orchestrator over sections/support (god-file decomposed)"
git tag -a phase3b-transformer -m "Phase 3b: ocs_transformer god-file decomposed (sections + support, golden-verified)"
```

---

## 完成定義

- `ocs_transformer.py` 從 1492 行降為薄 orchestrator;邏輯分散到 `sections/`(5)+`support/`(5)。
- golden(真實 PDF)逐字節相同 + 11 測試綠,全程未改行為。
- ruff lint(185 既有問題)**不在本 plan**;但拆檔後各小檔較好之後逐一清。

## 注意 / 風險

- **最大風險 = 搬移時改錯邏輯**;golden 逐字節比對是主防線,**每搬一塊就驗**,不累積。
- `_parse_ocu_table_units`(~300 行,含內層函式 `_ensure_unit`)是最難的一塊,放 content_extractor,最後搬、單獨一輪。
- 若某工具其實依賴實例狀態(alias 表),改傳參或設模組常數;**不改其行為**。
- parser 類名/方法(`PDFParser.parse`)以實際檔為準(Task 1 Step 2 先確認)。
