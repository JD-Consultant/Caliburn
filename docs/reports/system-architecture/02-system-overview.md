# 二、系統全貌與邊界

[報告目錄](README.md) · 上一章：[設計目標](01-purpose.md) · 下一章：[程式分工](03-components.md)

## 本機資料管理，外部模型推論

![圖二：Caliburn 本機 Docker 基本模式部署](../../diagrams/architecture/delivery-and-operations/local-deployment.png)

[圖源](../../diagrams/architecture/delivery-and-operations/local-deployment.mmd) · [SVG](../../diagrams/architecture/delivery-and-operations/local-deployment.svg)

圖二由[正式部署視圖](../../architecture/delivery-and-operations.md#2-最小部署視角)生成。外框區分操作者電腦與 Docker 容器；矩形表示程序／外部系統，圓柱表示資料庫。箭頭只表示發起請求的方向，標明協定，省略回傳。PDF 是 App 內的受控功能，不是獨立服務。後端將組裝好的上下文（Context）送至 OpenAI，因此需要連網，訪談資料可能隨模型請求外送。

圖中呈現未啟用公版參考的基本部署。明示設定後，後端另可透過 HTTP 查讀獨立 RAG 的公版資料；RAG 不由 JD App 自動啟動，也不成為預設依賴。這項可選路徑依 [ADR0080](../../adr/0080-opt-in-public-reference-agent-tools.md)，詳細分工見[第四章](04-agent-execution.md)。

UI 提供訪談、預覽、人工編輯、來源檢視及下載；後端檢查資料範圍與工具權限，協調正式提交及恢復。瀏覽器不持有供應商金鑰，畫面也須依後端結果判定資料是否已保存。

單一操作者可在清單管理多份資料隔離的職務檔案，包括建立、改名及確認刪除。每份檔案的訪談、JD、Memory 與執行歷史共用所屬範圍；整份刪除的確認及保存邊界見[第六章](06-jd-and-recovery.md#整份職務檔案的刪除邊界)。

目前選型為 React／TypeScript 前端，Python／FastAPI 後端，PostgreSQL 保存產品資料，LangGraph 管理可持久接續的執行。模型以 OpenAI direct Responses SDK 呼叫，產品選擇 Luna／high；這是成本與品質的產品取捨，不是宣稱它對所有任務最佳。PDF 使用受控的 HTML／CSS 與 Chromium 渲染。

## 多個分析角色，不等於多個微服務

A、B1、B2 是不同職責、工具集與 Context 的分析角色，共用執行機制。後端採**模組化單體** ：以程式模組劃分責任，尚不為每個角色建立獨立服務、網路 API 或佇列平台。

模組化單體適合目前的本機規模，部署較簡單，跨模組提交也較容易協調。不過，各模組仍須透過明確介面合作，不能直接改寫彼此的內部資料。未來若出現具體的負載或隔離需求，再評估是否拆分服務。

## 三種「資料留存」不是同一件事

| 保存範圍 | 用途 | Caliburn 的界線 |
| --- | --- | --- |
| 業務資料 | 正式訪談、JD、已發布 Memory、固定來源與操作結果 | 由對應業務模組及 PostgreSQL 管理 |
| 執行 Checkpoint | 已保存的模型／工具進度、Context 接續位置 | 用來恢復工作，不直接冒充正式產品資料 |
| 供應商 Response 狀態 | 遠端接續與保存 API 回應的能力 | 本產品用 `store=false`，不使用 `previous_response_id` 作為歷史來源 |

Context 由 App 組裝與接續，其中的 reasoning／compaction 項目可能包含供應商產生、App 無法解讀的內容。App 控制傳送哪些項目，但不能任意重寫內部推理。

`store=false` 表示本產品不以遠端 Response 保存作為恢復依據；供應商的完整隱私與資料留存政策，仍須依其契約判讀。

## 部署與權限要分開看

產品提供原生啟動與 JD App 專用 Docker Compose。Docker 以一個 App 容器提供同源 Web、API、背景工作及 PDF，PostgreSQL 容器使用獨立資料 volume；初始化與 schema 升級仍須明確執行，不自動搬移既有資料。[本機交付契約](../../implementation/interface-and-delivery.md#42-docker-交付)、[操作手冊](../../runbook.md#docker-操作)

產品程式、部署設定與已運行的映像須分開核對。2026-10-05 的 Docker 示範已更新刪除入口與介面，但尚未包含其後完成的 checkpoint 收尾防護，也未設定啟用公版工具；不能以該示範代表所有現行功能已部署。版本與限制見[示範更新](../../experiments/product-validation/2026-10-05-docker-demo-update.md)及[刪除驗證](../../experiments/product-validation/2026-10-05-job-file-deletion.md)。

產品以 loopback 本機存取為前提，並檢查請求來源；職務檔案的隔離、A 活躍時的人工寫入限制與 B1／B2 工具權限，仍必須由後端落實。單靠 UI 隱藏按鈕或 Prompt 說「不要越權」不足以建立隔離。

這套權限模型適用於本機產品，尚未驗證多租戶 SaaS 或多人服務的安全性。現行產品採用本章架構，舊產品程式已退役，兩者的沿革見 [ADR0079](../../adr/0079-target-rebuild-production-cutover.md)。

### 延伸閱讀

- 系統範圍與選型：[系統邊界](../../architecture/system-boundaries.md)、[技術決策](../../implementation/technology-decisions.md)。
- 後端組裝：[bootstrap.py](../../../apps/api/src/caliburn/bootstrap.py)。
- 供應商介面：[openai_responses.py](../../../apps/api/src/caliburn/adapters/openai_responses.py)。
- 權限與隔離的測試範圍：[本機安全測試紀錄](../../history.md#source-0e25c675694e9744582f)。
