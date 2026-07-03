# apps/api 深文檔(agent-facing 內部設計)

> [`../README.md`](../README.md) 是「面」(codemap / 端點 / 生命週期);這裡是各子系統「**內部怎麼跑 + 為什麼**」。
> 改對應碼**同 commit** 更新。文檔怎麼寫見 [`docs/README.md`](../../../docs/README.md) / [`docs/design/README.md`](../../../docs/design/README.md)。

- [`knowledge-pack-assembly.md`](knowledge-pack-assembly.md) — **`build_pack`**:indexer DTO → `GET /knowledge` 那一包(12 池 / 去重 key / `source_tasks` 反掛 refs)。
- [`document-of-record.md`](document-of-record.md) — **`ocs_doc`**:`skeleton` / `assemble_final` / `validate` / 完成度(**finalize 的 gate**、`_` 欄剝除)。
- [`authoring.md`](authoring.md) — **LangGraph 訪談引擎**:逐任務深問**單層 loop「別重構」**、interrupt HITL(待 ADR 0020 重設計)。
- [`ai-suggestions.md`](ai-suggestions.md) — **`services/ai`** 提議鏈:catalog-first / grounded / 降級(**web 目前零呼叫**)。
