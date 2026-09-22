# Phase 2 — `packages/ocs-contract`(OCS 來源文件契約)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans。逐 task 做,每 task 結束=既有測試原樣全綠 + 新驗證綠。

**Goal:** 把「OCS 來源文件」契約(pdf-to-json **產出** → ocs-indexer **消費** 的檔案交換格式)抽成單一事實來源 `packages/ocs-contract`:一份 **JSON-Schema** → codegen 出 **Pydantic v2**,兩個消費者改吃它,並加 **schema-diff** 守門。從結構上根除 `job_categories` 那類飄移 bug。

**Architecture:** `packages/ocs-contract` 是獨立 uv 套件:`schema/ocs-document.schema.json`(權威)→ `datamodel-code-generator` 生 `src/ocs_contract/models.py`(Pydantic v2)。pdf-to-json 與 ocs-indexer 以 **per-app path 依賴**(`[tool.uv.sources]` editable path)引用,**不建 uv workspace**(避開 api 3.13 vs indexer/torch 的單一直譯器衝突)。

**Tech Stack:** JSON-Schema(Draft 2020-12)、datamodel-code-generator、Pydantic v2、jsonschema(驗證)、uv(path source)、pytest。

## Global Constraints

- **範圍只含「契約 #1:OCS 來源文件」**(pdf-to-json ↔ indexer)。**不含** indexer 查詢 API DTO(契約 #2)、api/web 著作文件(契約 #3)—— 那兩個之後另開。
- **契約以 pdf-to-json 的 `OCSDocument`(生產者)為權威結構**;indexer 的寬鬆版調和進來(tolerant:`additionalProperties: true`、optional 寬鬆),確保真實 908 檔仍載得進。
- **飄移修正烘進 schema**:`job_categories`/`occupations`/`industries` = `array<{code,name}>`(非字串);level 1–5。
- **不改業務邏輯**:消費者改吃契約型別,行為不變,以既有測試綠為準。
- **不建 uv workspace**(改 path dep);修訂 [ADR 0005](../adr/0005-per-app-uv-defer-workspace.md)。
- 路徑:monorepo 根 `/s/caliburn`。

---

### Task 1: 撰寫 canonical JSON-Schema(權威來源)

**Files:**
- Create: `packages/ocs-contract/schema/ocs-document.schema.json`

**Interfaces:**
- Produces: OCS 來源文件的權威 schema(後續 codegen 與驗證的單一來源)。

- [ ] **Step 1: 寫 schema**(依 pdf-to-json `OCSDocument` 結構,飄移修正烘入)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://caliburn.dev/schema/ocs-document.schema.json",
  "title": "OCSDocument",
  "description": "職能基準(OCS)來源文件 — pdf-to-json 產出、ocs-indexer 消費的交換格式。",
  "type": "object",
  "required": ["ocs_profile"],
  "additionalProperties": true,
  "properties": {
    "version_info": { "$ref": "#/$defs/VersionInfo" },
    "ocs_profile": { "$ref": "#/$defs/OcsProfile" },
    "ocs_content": { "$ref": "#/$defs/OcsContent" },
    "ocs_attitude": { "$ref": "#/$defs/OcsAttitude" },
    "notes": { "$ref": "#/$defs/Notes" }
  },
  "$defs": {
    "CodeName": {
      "type": "object",
      "required": ["code", "name"],
      "additionalProperties": true,
      "properties": { "code": { "type": "string" }, "name": { "type": "string" } }
    },
    "CodeText": {
      "type": "object",
      "required": ["code", "text"],
      "additionalProperties": true,
      "properties": { "code": { "type": "string" }, "text": { "type": "string" } }
    },
    "VersionEntry": {
      "type": "object",
      "additionalProperties": true,
      "properties": {
        "version": { "type": "string" },
        "ocs_code": { "type": "string" },
        "ocs_name": { "type": "string" },
        "status": { "type": "string" },
        "update_note": { "type": ["string", "null"] },
        "update_date": { "type": "string" }
      }
    },
    "VersionInfo": {
      "type": "object",
      "additionalProperties": true,
      "properties": { "versions": { "type": "array", "items": { "$ref": "#/$defs/VersionEntry" } } }
    },
    "OcsName": {
      "type": "object",
      "additionalProperties": true,
      "properties": {
        "job_category_name": { "type": ["string", "null"] },
        "occupation_name": { "type": ["string", "null"] }
      }
    },
    "Category": {
      "type": "object",
      "additionalProperties": true,
      "properties": {
        "job_categories": { "type": "array", "items": { "$ref": "#/$defs/CodeName" } },
        "occupations": { "type": "array", "items": { "$ref": "#/$defs/CodeName" } },
        "industries": { "type": "array", "items": { "$ref": "#/$defs/CodeName" } }
      }
    },
    "OcsProfile": {
      "type": "object",
      "required": ["ocs_code"],
      "additionalProperties": true,
      "properties": {
        "ocs_code": { "type": "string" },
        "ocs_name": { "$ref": "#/$defs/OcsName" },
        "category": { "$ref": "#/$defs/Category" },
        "job_description": { "type": "string" },
        "ocs_level": { "type": "integer", "minimum": 1, "maximum": 5 }
      }
    },
    "CompetencyBlock": {
      "type": "object",
      "additionalProperties": true,
      "properties": {
        "competency_level": { "type": ["integer", "null"], "minimum": 1, "maximum": 5 },
        "indicators": { "type": "array", "items": { "$ref": "#/$defs/CodeText" } },
        "outputs": { "type": "array", "items": { "$ref": "#/$defs/CodeName" } },
        "knowledge": { "type": "array", "items": { "$ref": "#/$defs/CodeName" } },
        "skills": { "type": "array", "items": { "$ref": "#/$defs/CodeName" } }
      }
    },
    "TaskGroup": {
      "type": "object",
      "additionalProperties": true,
      "properties": {
        "task_codes": { "type": "array", "items": { "$ref": "#/$defs/CodeName" } },
        "competency_blocks": { "type": "array", "items": { "$ref": "#/$defs/CompetencyBlock" } }
      }
    },
    "OcuUnit": {
      "type": "object",
      "additionalProperties": true,
      "properties": {
        "ocu_code": { "type": "string" },
        "ocu_name": { "type": "string" },
        "tasks": { "type": "array", "items": { "$ref": "#/$defs/TaskGroup" } }
      }
    },
    "OcsContent": {
      "type": "object",
      "additionalProperties": true,
      "properties": { "ocu_units": { "type": "array", "items": { "$ref": "#/$defs/OcuUnit" } } }
    },
    "OcsAttitude": {
      "type": "object",
      "additionalProperties": true,
      "properties": { "attitudes": { "type": "array", "items": { "$ref": "#/$defs/CodeName" } } }
    },
    "Notes": {
      "type": "object",
      "additionalProperties": true,
      "properties": {
        "prerequisites": { "type": "array", "items": { "type": "string" } },
        "supplements": { "type": "array", "items": { "type": "string" } }
      }
    }
  }
}
```

- [ ] **Step 2: 用真實 OCS 檔驗證 schema 正確**(取一個 indexer 的真實來源檔)

```bash
cd /s/caliburn/packages/ocs-contract
# 找一個真實 OCS JSON(indexer 的測試 fixture 或 data/);路徑以實際為準
uv run --with jsonschema python -c "
import json, glob, jsonschema
schema = json.load(open('schema/ocs-document.schema.json', encoding='utf-8'))
f = glob.glob('/s/jd-pdf-to-json/output/*.json') or glob.glob('/s/caliburn/apps/ocs-indexer/tests/**/*.json', recursive=True)
doc = json.load(open(f[0], encoding='utf-8'))
jsonschema.validate(doc, schema); print('OK valid:', f[0])
"
```
Expected:`OK valid: ...`。若真實檔含 schema 沒涵蓋的必要結構,放寬該欄(optional / additionalProperties 已開)後再過。

- [ ] **Step 3: 反向驗證能抓到飄移**(job_categories 給字串應 fail)

```bash
cd /s/caliburn/packages/ocs-contract
uv run --with jsonschema python -c "
import json, jsonschema
schema = json.load(open('schema/ocs-document.schema.json', encoding='utf-8'))
bad = {'ocs_profile': {'ocs_code':'X','category':{'job_categories':['不是物件']}}}
try:
    jsonschema.validate(bad, schema); print('FAIL: 應該要報錯')
except jsonschema.ValidationError: print('OK 抓到飄移')
"
```
Expected:`OK 抓到飄移`。

- [ ] **Step 4: Commit**

```bash
cd /s/caliburn && git add packages/ocs-contract/schema && git commit -m "feat(contract): OCS document JSON-Schema (source of truth)"
```

---

### Task 2: scaffold `ocs-contract` 套件 + codegen → Pydantic

**Files:**
- Create: `packages/ocs-contract/pyproject.toml`
- Create: `packages/ocs-contract/package.json`（turbo codegen shim）
- Create: `packages/ocs-contract/src/ocs_contract/__init__.py`
- Generate: `packages/ocs-contract/src/ocs_contract/models.py`（codegen 產出,入庫)

**Interfaces:**
- Produces: `from ocs_contract.models import OCSDocument`(Pydantic v2)。
- Consumes: Task 1 的 schema。

- [ ] **Step 1: `pyproject.toml`**

```toml
[project]
name = "ocs-contract"
version = "0.1.0"
description = "Caliburn OCS document contract — schema + generated Pydantic models"
requires-python = ">=3.11"
dependencies = ["pydantic>=2.9,<3"]

[dependency-groups]
dev = ["datamodel-code-generator>=0.26", "jsonschema>=4.20"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/ocs_contract"]
```

- [ ] **Step 2: `src/ocs_contract/__init__.py`**

```python
from ocs_contract.models import OCSDocument  # noqa: F401
```

- [ ] **Step 3: codegen 指令(產 models.py)**

```bash
cd /s/caliburn/packages/ocs-contract && uv sync
uv run datamodel-codegen \
  --input schema/ocs-document.schema.json --input-file-type jsonschema \
  --output src/ocs_contract/models.py \
  --output-model-type pydantic_v2.BaseModel \
  --use-standard-collections --use-union-operator --use-schema-description \
  --target-python-version 3.11
```
Expected:產生 `src/ocs_contract/models.py`,含 `OCSDocument` 等類別。

- [ ] **Step 4: `package.json`（turbo codegen shim,供 schema-diff / 重生用）**

```json
{
  "name": "@caliburn/ocs-contract",
  "private": true,
  "scripts": {
    "codegen": "uv run datamodel-codegen --input schema/ocs-document.schema.json --input-file-type jsonschema --output src/ocs_contract/models.py --output-model-type pydantic_v2.BaseModel --use-standard-collections --use-union-operator --use-schema-description --target-python-version 3.11",
    "build": "echo \"no build\""
  }
}
```

- [ ] **Step 5: 驗證生成的模型可載入 + 驗真實檔**

```bash
cd /s/caliburn/packages/ocs-contract
uv run python -c "
import json, glob
from ocs_contract.models import OCSDocument
f = glob.glob('/s/jd-pdf-to-json/output/*.json')[0]
doc = OCSDocument.model_validate(json.load(open(f, encoding='utf-8'))); print('OK loaded', f)
"
```
Expected:`OK loaded ...`。

- [ ] **Step 6: Commit**

```bash
cd /s/caliburn && git add packages/ocs-contract && git commit -m "feat(contract): ocs-contract package — codegen Pydantic v2 from schema"
```

---

### Task 3: pdf-to-json 改吃契約(path 依賴)

**Files:**
- Modify: `apps/pdf-to-json/pyproject.toml`（加 `ocs-contract` path 依賴）
- Modify: `apps/pdf-to-json/src/jd_pdf_to_json/core/models.py`（改為 re-export 契約模型)
- Modify: `apps/pdf-to-json/src/jd_pdf_to_json/writers/json_writer.py`（寫檔前依 schema 驗證 — 若易接)

**Interfaces:**
- Consumes: `ocs_contract.models`。
- Produces: pdf-to-json 產出的 OCS 文件型別來自契約。

- [ ] **Step 1: 加 path 依賴**(`apps/pdf-to-json/pyproject.toml`)

```toml
# [project].dependencies 加:
#   "ocs-contract",
# 檔案末加:
[tool.uv.sources]
ocs-contract = { path = "../../packages/ocs-contract", editable = true }
```

- [ ] **Step 2: `core/models.py` 改為 re-export 契約**(保留既有匯入點不破壞)

```python
"""Data models for OCS documents — now sourced from the shared ocs-contract."""
from ocs_contract.models import (  # noqa: F401
    OCSDocument, OcsProfile, OcsContent, OcsAttitude, Notes,
    OcuUnit, TaskGroup, CompetencyBlock, CodeName, CodeText, VersionInfo,
)
# 若 transformer 用了本檔原本的舊類名(如 OCSUnit/Task/OutputItem…),
# 在此加別名:OCSUnit = OcuUnit; Task = TaskGroup; 等(以 transformer 實際 import 為準)。
```

- [ ] **Step 3: 同步 sync + 對齊 transformer 的匯入名**

```bash
cd /s/caliburn/apps/pdf-to-json && uv sync --extra dev
uv run python -c "import jd_pdf_to_json.transformers.ocs_transformer"   # 確認 import 不爆
```
Expected:import 成功(若 NameError,回 Step 2 補別名)。

- [ ] **Step 4: 跑既有測試**

```bash
cd /s/caliburn/apps/pdf-to-json && uv run --extra dev pytest -q
```
Expected:與 Phase 1 相同(11 passed)。**不得改業務邏輯;只調匯入。**

- [ ] **Step 5: Commit**

```bash
cd /s/caliburn && git add apps/pdf-to-json && git commit -m "refactor(pdf-to-json): source OCS models from ocs-contract (path dep)"
```

---

### Task 4: ocs-indexer 改吃契約(path 依賴)

**Files:**
- Modify: `apps/ocs-indexer/pyproject.toml`（加 `ocs-contract` path 依賴）
- Modify: `apps/ocs-indexer/src/jd_ocs_indexer/models/ocs.py`（改用契約模型;保留 tolerant 包裝)

**Interfaces:**
- Consumes: `ocs_contract.models`。

- [ ] **Step 1: 加 path 依賴**(`apps/ocs-indexer/pyproject.toml`)

```toml
# [project].dependencies 加 "ocs-contract";檔末:
[tool.uv.sources]
ocs-contract = { path = "../../packages/ocs-contract", editable = true }
```

- [ ] **Step 2: `models/ocs.py` 改用契約**(保留寬鬆載入語意)

```python
"""OCS source-doc models — from shared ocs-contract (tolerant: schema 已 additionalProperties)."""
from ocs_contract.models import (  # noqa: F401
    OCSDocument, OcsProfile, OcsContent, OcsAttitude, Notes,
    OcuUnit, TaskGroup, CompetencyBlock, CodeName, CodeText,
)
# indexer 原本的 ingestion/normalizer 若 import 本檔的舊類名,於此加別名對齊。
# 原本 OCSDocument 的 `raw: dict|None` 若 ingestion 有用到,改在 normalizer 端自行保留 raw。
```

- [ ] **Step 3: sync + 對齊 ingestion/normalizer 匯入**

```bash
cd /s/caliburn/apps/ocs-indexer && uv sync --all-extras
uv run python -c "import jd_ocs_indexer.ingestion.normalizer; import jd_ocs_indexer.ingestion.reader"
```
Expected:import 成功(NameError → 回 Step 2 補別名 / 在 normalizer 處理 `raw`)。

- [ ] **Step 4: 跑既有測試**

```bash
cd /s/caliburn/apps/ocs-indexer && uv run --all-extras pytest -q
```
Expected:與 Phase 1 相同(35 passed)。

- [ ] **Step 5: Commit**

```bash
cd /s/caliburn && git add apps/ocs-indexer && git commit -m "refactor(ocs-indexer): source OCS models from ocs-contract (path dep)"
```

---

### Task 5: schema-diff 守門(生成碼與 schema 同步檢查)

**Files:**
- Create: `packages/ocs-contract/scripts/check-codegen.sh`(或納入 CI)
- Modify: `turbo.json`（可選:加 `codegen` task）

**Interfaces:**
- Produces:一個會在「schema 改了但沒重生 models.py」時 fail 的檢查。

- [ ] **Step 1: 檢查腳本**(`packages/ocs-contract/scripts/check-codegen.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
cp src/ocs_contract/models.py /tmp/ocs_models_before.py
npm run codegen
if ! diff -q /tmp/ocs_models_before.py src/ocs_contract/models.py >/dev/null; then
  echo "ERROR: models.py 與 schema 不同步 — 請跑 'npm run codegen' 並 commit。"; exit 1
fi
echo "OK: 生成碼與 schema 同步。"
```

- [ ] **Step 2: 本地驗證**

```bash
cd /s/caliburn/packages/ocs-contract && bash scripts/check-codegen.sh
```
Expected:`OK: 生成碼與 schema 同步。`

- [ ] **Step 3: Commit**

```bash
cd /s/caliburn && git add packages/ocs-contract/scripts && git commit -m "chore(contract): schema↔codegen sync check"
```

---

### Task 6: 收尾 — 全綠 + 更新 ADR

**Files:**
- Modify: `docs/adr/0004-contract-first-ocs-contract.md`（狀態 → 已實作 #1)
- Modify: `docs/adr/0005-per-app-uv-defer-workspace.md`（補:workspace 由 path dep 取代,不需建)

- [ ] **Step 1: 全倉測試綠**

```bash
cd /s/caliburn && npx turbo test 2>&1 | grep -E "Tasks:|passed|Failed"
```
Expected:3/3(api 86/61skip、ocs-indexer 35、pdf-to-json 11)。

- [ ] **Step 2: 更新兩份 ADR**(狀態/補註,內容照實)
- [ ] **Step 3: Commit + tag**

```bash
cd /s/caliburn && git add docs/adr && git commit -m "docs(adr): 0004 contract #1 implemented; 0005 workspace superseded by path deps"
git tag -a phase2-ocs-contract -m "Phase 2: OCS source-doc contract extracted (schema → Pydantic, consumers wired, schema-diff)"
```

---

## 完成定義

- `packages/ocs-contract`:schema(權威)+ 生成 Pydantic + schema-diff 檢查。
- pdf-to-json、ocs-indexer 皆以 path 依賴吃契約;`turbo test` 3/3 綠。
- `job_categories` 等飄移由 schema 結構上防止。
- **不含** TS(web 不讀 OCS 來源)、契約 #2(indexer 查詢 API)、契約 #3(api/web 著作文件)—— 後續另開。

## 注意 / 已知

- **api 不在本 Phase**:api 吃 indexer 的查詢 API(契約 #2),不直接讀 OCS 來源檔,故不接 ocs-contract。
- **不建 uv workspace**:改 per-app path dep(避開 api 3.13 / indexer torch 的單一直譯器衝突)。ADR 0005 隨之修訂。
- 別名對齊(Task 3/4 Step 2)是主要風險點:消費者用的舊類名 ↔ 契約新類名,以「import 不爆 + 既有測試綠」為準,逐一補別名,**不動業務邏輯**。
