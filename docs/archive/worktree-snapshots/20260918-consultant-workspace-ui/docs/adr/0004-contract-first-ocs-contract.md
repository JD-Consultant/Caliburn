# ADR 0004 — 契約優先 `packages/ocs-contract`

- **狀態**:Accepted；**契約 #1〔OCS 來源文件〕已實作**（Phase 2,2026-06-28,tag `phase2-ocs-contract`)

## 脈絡

OCS JSON 契約是 pdf-to-json(生產)→ ocs-indexer(索引)→ api(消費+匯出)的共用接縫,但現況是 **prose(README)+ 三處各自重編結構**(transformer 1492 行、normalizer 321 行…)→ 飄移 bug(`job_categories` 多值掉值)。

## 決定

把契約抽成 `packages/ocs-contract`,**契約優先**:
- `schema/*.schema.json`(JSON-Schema)= 單一事實來源。
- `datamodel-code-generator` 生 Pydantic v2、`json-schema-to-typescript` 生 TS。
- 每個 PR 跑 **schema-diff** 檢查。

## 後果

- ✅ 結構由契約定義一次;transformer/normalizer 只留對應邏輯 → 同時縮小+對齊。
- ✅ 從結構上根除飄移 bug。
依據:OpenAPI/契約優先、Stoplight、契約測試 2026。

## 實作(Phase 2,2026-06-28)

- `packages/ocs-contract`:`schema/ocs-document.schema.json`(權威)→ `datamodel-code-generator` 生 `src/ocs_contract/models.py`(Pydantic v2)。
- schema 兼具**結構保護**(job_categories 等必為物件陣列,擋 string 飄移)與**容忍載入**(section/array 預設空、code/name nullable)→ 驗證 908/908 真實檔。
- **pdf-to-json、ocs-indexer** 以 **per-app path 依賴**(editable)吃契約(`core/models.py` / `models/ocs.py` 改 re-export + 向後相容別名);`turbo test` 3/3 綠。
- **schema-diff 守門**:`scripts/check-codegen.sh`(codegen `--disable-timestamp` + `git diff`,確定性)。
- **僅契約 #1**;契約 #2(indexer 查詢 API)、#3(api/web 著作文件)後續另開。
