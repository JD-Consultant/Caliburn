# 契約策略與邊界

本頁維護跨語言及模組接縫採用什麼契約、為什麼，以及相容界線。生成器、輸出位置、打包與執行時驗證由[資料與契約接線](../implementation/data-and-contracts.md#5-唯一契約來源及生成)維護；操作命令見 [API 開發說明](../../apps/api/README.md)。

## 現行規則

正式產品為 `apps/api` 與 `apps/web`，依 [正式產品與選型](../architecture/design-decisions.md)維護 App 自有契約。JSON Schema 是 App 跨語言傳輸格式的唯一來源；HTTP DTO 與模型工具按各自用途投影，不強制使用相同 envelope。型別與對外格式沿生成鏈維護，避免人工修改多份 shape。

API 的領域與用例模組不直接依賴 transport DTO；傳輸層負責 DTO 與內部型別的轉換。Python 內部 port 使用明確型別或 Protocol，不因共用而另建泛用契約套件。模型原生 Responses items 沿 SDK 接續契約保存，不套入 App 自製的訊息 schema；App schema 的額外欄位限制不應套用到原生接續 metadata。

## 模型工具的共同邊界

工具提供具名業務操作，模型只填分析所需參數；檔案、執行、版本、來源範圍與權限由 App 綁定。輸入 shape 合法不等於具備寫入資格，業務驗證與原子提交仍在 owner。

確定拒絕須回安全原因與合法下一步，例如重新讀取目標或修正參數；結果未知時先依原操作查回，不換新識別、重套 patch 或猜測已回滾。call ID 的配對與業務冪等各有責任。格式由 [HTTP／Tool Schema](../../apps/api/contracts)維護，接線見[資料與契約](../implementation/data-and-contracts.md)。

## 隔離與歷史範圍

保留的 RAG 有自己的跨語言契約 `packages/ocs-contract`，以 JSON Schema 生成 Pydantic model 與 TypeScript type；生成檢查沿[該套件說明](../../packages/ocs-contract/README.md)。它不屬於正式 JD 產品的契約，App／Web 不 import 或消費它；RAG 的隔離邊界不因契約存在而改變。

`experiments/jd-relational-app`、`packages/consultant-memory` 與 `packages/job-analysis-contract` 的舊程式或契約已退役，保留資料只供沿革查考，不作現行依賴，也不為已移除的 interview／job-authoring 接縫新增相容契約。

## 選擇判準

| 接縫 | 機制 |
|---|---|
| App 跨語言或對外的 JSON shape | JSON Schema 單一來源與生成型別；CI 驗證再生成無差異 |
| 純 Python、同 repo、少數消費者的內部 port | 共用型別模組或明確 Protocol；不另建泛用契約套件 |
| 未來出現外部或未知消費者 | 先確認版本與相容承諾，再評估 OpenAPI-first 或 consumer-driven contract |

## 交付流程

1. 確認受影響的介面、資料責任與既有 schema，沿責任文件維護契約；不另建重複規格。
2. 改變權責、相容承諾或跨層契約時，依[變更範圍與審查](../../CONTRIBUTING.md#變更範圍與審查)確認有效決定及受影響責任，再以可驗證的行為切片修改 schema、生成器或消費端。
3. 依 [API README](../../apps/api/README.md)執行生成命令，核對 schema 與生成差異，再跑受影響的 API／Web 契約及行為測試；離線 SDK payload 通過不代表遠端模型已接受。
4. 依受影響 App 的生成檢查、建置及差異檢查完成驗證；RAG 另沿其套件命令。純文件修改只核對內容、路由與一致性，不重跑無關產品測試。
