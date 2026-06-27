# ADR 0004 — 契約優先 `packages/ocs-contract`

- **狀態**:Accepted（2026-06-27;**Phase 2 規劃中,尚未實作**)

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
- ⏳ 尚未實作;這也是 uv workspace 接起來的時機(見 ADR 0005)。

依據:OpenAPI/契約優先、Stoplight、契約測試 2026。
