# 契約策略與邊界

本頁維護跨語言及模組接縫採用什麼契約、為什麼，以及相容界線。生成器、輸出位置、打包與執行時驗證由[資料與契約接線](../implementation/data-and-contracts.md#5-唯一契約來源及生成)維護；操作命令見 [API 開發說明](../../apps/api/README.md)。

## 現行規則

正式產品為 `apps/api` 與 `apps/web`，依 [ADR0079](../adr/0079-target-rebuild-production-cutover.md)維護 App 自有契約。JSON Schema 是 App 跨語言傳輸格式的唯一來源；HTTP DTO 與模型工具按各自用途投影，不強制使用相同 envelope。型別與對外格式沿生成鏈維護，避免人工修改多份 shape。

API 的領域與用例模組不直接依賴 transport DTO；傳輸層負責 DTO 與內部型別的轉換。Python 內部 port 使用明確型別或 Protocol，不因共用而另建泛用契約套件。模型原生 Responses items 沿 SDK 接續契約保存，不套入 App 自製的訊息 schema；App schema 的額外欄位限制不應套用到原生接續 metadata。

依 [ADR0084](../adr/0084-canonical-wire-admission.md)，JSON Schema 同時決定 wire 輸入的接受政策。HTTP 與模型工具先以 canonical schema 驗證原 JSON，再以生成 DTO 轉成 Python 型別；DTO 的預設 strict／coercion 行為不另訂輸入規格。JSON 數學整數包含 `1.0`，不包含布林或字串；`uuid` 採 JSON Schema 2020-12 §7.3.5 的連字號形式，容許十六進位大小寫，不接受 compact 或 URN 拼法。Web 的 Ajv 使用同一份 schema 與相同 UUID 格式政策。[JSON Schema](https://json-schema.org/draft/2020-12/json-schema-validation)

現有 wire 整數都是序號、索引或計數，canonical 統一將上限明訂為 `9007199254740991`，既有較小上限仍保留。這是本案跨 Python／JavaScript 精確表示的契約政策，沿 [RFC 8259 §6](https://www.rfc-editor.org/rfc/rfc8259#section-6) 的互通範圍；JSON 本身不禁止更大的數字，內部 DB 型別也不因此改變。新增不同用途的數值時須先決定其表示契約。

文字是否非空沿現有領域的 Python 3.14 `str.strip()`／`str.isspace()` 語意：Unicode 分類 `Zs` 或 bidirectional class `WS/B/S` 視為空白；U+FEFF 不屬此集合。canonical pattern 明列碼點，不用各語言不同的 `\s` 推定同義；須禁止 NUL 的欄位也在同一 pattern 表達，保留原文字而不自動 trim。這是 Caliburn 的業務政策，不是所有產品通用的 Unicode 清理規則。[Python 字串規格](https://docs.python.org/3.14/library/stdtypes.html#str.isspace)

## 隔離與歷史範圍

保留的 RAG 有自己的跨語言契約 `packages/ocs-contract`，以 JSON Schema 生成目前 Python 消費者使用的 Pydantic model；無消費者的 TypeScript 產物已移除，生成檢查只在暫存目錄產生並比較，不更動工作檔或 Git index。生成檢查沿[該套件說明](../../packages/ocs-contract/README.md)。它不屬於正式 JD 產品的契約，App／Web 不 import 或消費它；RAG 的隔離邊界不因契約存在而改變。

`experiments/jd-relational-app`、`packages/consultant-memory` 與 `packages/job-analysis-contract` 已退役並移出工作樹，沿革由Git 歷史取回，不作現行依賴，也不為已移除的 interview／job-authoring 接縫新增相容契約。

## 選擇判準

| 接縫 | 機制 |
|---|---|
| App 跨語言或對外的 JSON shape | JSON Schema 單一來源與生成型別；CI 驗證再生成無差異 |
| 純 Python、同 repo、少數消費者的內部 port | 共用型別模組或明確 Protocol；不另建泛用契約套件 |
| 未來出現外部或未知消費者 | 依決策流程研究版本與相容承諾，再評估 OpenAPI-first 或 consumer-driven contract |

## 交付流程

1. 確認受影響的介面、資料責任與既有 schema，沿責任文件維護契約；不另建重複規格。
2. 改變權責、相容承諾或跨層契約的重大取捨，依[決策流程](decision-process.md)記錄 ADR；效果等價的局部修改沿既有規則處理。
3. 依[開發規範](development-standard.md)拆出可驗證的行為切片，以反例先測，再修改 schema、生成器或消費端。提交依任務授權，不規定一項 task 只能有一個 commit。
4. 依 [API README](../../apps/api/README.md)執行生成命令，核對 schema 與生成差異，再跑受影響的 API／Web 契約及行為測試；離線 SDK payload 通過不代表遠端模型已接受。
5. 依受影響 App 的生成檢查、建置及差異檢查完成驗證；RAG 另沿其套件命令。純文件修改只核對內容、路由與一致性，不重跑無關產品測試。
