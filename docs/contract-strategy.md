# Caliburn Contract Strategy

## 現行規則

正式產品為 `apps/api` 與 `apps/web`，依 [ADR0079](adr/0079-target-rebuild-production-cutover.md)維護 App 自有的 `apps/api/contracts/`。JSON Schema 是 App 跨語言傳輸格式的唯一來源；`http/` 定義 HTTP DTO，`tools/` 定義模型工具的輸入與結構化回傳。HTTP 與模型工具各有必要投影，不強制使用相同 envelope。

[`apps/api/scripts/generate_contracts.py`](../apps/api/scripts/generate_contracts.py)使用鎖定的 datamodel-code-generator 與 json-schema-to-typescript，產生下列檔案：

| 生成物 | 位置與用途 |
|---|---|
| Python DTO | `apps/api/src/caliburn/contracts/generated/`；工具型別位於其 `tools/` 子目錄 |
| TypeScript 型別 | `apps/web/src/shared/api/generated/`；工具型別位於其 `tools/` 子目錄 |
| 工具 schema 資源 | `apps/api/src/caliburn/contracts/generated/tools/*.schema.json`；從原 schema 複製，供安裝後的工具定義讀取 |

生成檔不得手改。OpenAPI 由 API 使用的生成型別形成；HTTP／tool 入口仍須執行時驗證，TypeScript 型別不能代替它。Web 使用同一份 HTTP schema 驗證回傳，再放入查詢快取，不手寫第二份資料 shape。詳細生成與驗證邊界見[資料與契約](implementation/data-and-contracts.md#5-唯一契約來源及生成)。

API 的領域與用例模組不直接依賴 transport DTO；傳輸層負責 DTO 與內部型別的轉換。Python 內部 port 使用明確型別或 Protocol，不因共用而另建泛用契約套件。模型原生 Responses items 沿 SDK 接續契約保存，不套入 App 自製的訊息 schema；App schema 的額外欄位限制不應套用到原生接續 metadata。

## 隔離與歷史範圍

保留的 RAG 有自己的跨語言契約 `packages/ocs-contract`，以 JSON Schema 生成 Pydantic model 與 TypeScript type；`pnpm --filter @caliburn/ocs-contract run check-codegen` 檢查生成物。它不屬於正式 JD 產品的契約，App／Web 不 import 或消費它；RAG 的隔離邊界不因契約存在而改變。

`experiments/jd-relational-app`、`packages/consultant-memory` 與 `packages/job-analysis-contract` 的舊程式或契約已退役，保留資料只供沿革查考，不作現行依賴，也不為已移除的 interview／job-authoring 接縫新增相容契約。

## 選擇判準

| 接縫 | 機制 |
|---|---|
| App 跨語言或對外的 JSON shape | JSON Schema 單一來源與生成型別；CI 驗證再生成無差異 |
| 純 Python、同 repo、少數消費者的內部 port | 共用型別模組或明確 Protocol；不另建泛用契約套件 |
| 未來出現外部或未知消費者 | 依決策流程研究版本與相容承諾，再評估 OpenAPI-first 或 consumer-driven contract |

## 交付流程

1. 確認受影響的介面、資料責任與既有 schema，沿責任文件維護契約；不另建重複規格。
2. 改變權責、相容承諾或跨層契約的重大取捨，依[決策流程](decision-process.md)記錄 ADR；效果等價的局部修改沿既有規則處理。
3. 依[開發規範](implementation/development-standard.md)拆出可驗證的行為切片，以反例先測，再修改 schema、生成器或消費端。提交依任務授權，不規定一項 task 只能有一個 commit。
4. 依 [API README](../apps/api/README.md)執行生成命令，核對 schema 與生成差異，再跑受影響的 API／Web 契約及行為測試；離線 SDK payload 通過不代表遠端模型已接受。
5. 契約變更跑根目錄 `pnpm build`（含 `codegen:check`）與 `git diff --check`；RAG 契約變更另跑其檢查命令。純文件修改只核對內容、路由與一致性，不重跑無關產品測試。
