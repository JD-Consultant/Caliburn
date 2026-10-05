# 附錄：術語與參考來源

[報告目錄](README.md)

## 術語

下表依產品資料、分析角色與執行機制區分名詞。同一份內容可能出現在模型 Context 中，但可引用的來源資格及正式版本仍由原業務模組管理。

| 名稱 | 本報告中的意思 |
| --- | --- |
| JD | 職務說明書；可管理的結構化產品成果，不是整份 Markdown |
| AI 分析角色（Agent） | 依特定分析職責設定提示詞、上下文與工具權限的執行角色，如 A、B1、B2 |
| 共用執行機制（Runtime） | 處理模型與工具的執行、接續、保存及控制，是後端的一部分 |
| Turn | A 處理一次員工輸入的完整工作，可能包含多個 Step |
| Step | 一次模型回應與該次工具處理；不等於正式訪談訊息或 LangGraph super-step |
| 訪談序號 | 同一職務檔案有效訪談訊息的正式順序；不等於模型呼叫次數 |
| 上下文（Context） | App 實際送入這次模型請求的指令、歷史、資料與工具相關內容 |
| 工作記憶（Memory） | 原始訪談、工作情境、工作理解所形成的可回查資料體系 |
| 導覽（Map） | 列出可讀物件，協助模型定位；不是向量資料庫或全文摘要 |
| 候選 | 尚未正式採用的工作稿；保存後可預覽與恢復，完成提交前仍與正式結果分開 |
| 物件身分／修訂 | 同一個情境或理解的持續身分／它在某次修改後的固定內容與關係 |
| Memory 快照 | 發布時選定的一組物件修訂及固定關係，不要求所有物件版本號相同 |
| 差異（Diff） | 指定舊、新基準間的內容或關係變化；讀取差異不代表已核對完成 |
| 執行檢查點（Checkpoint） | Graph 已保存的執行狀態，用於接續工作，不取代正式 JD／Memory 的保存 |
| 上下文壓縮（Compaction） | 由供應商產生壓縮後的接續視窗，不決定原始訪談是否保留 |
| 原子提交 | 一組資料修改一起成立或一起不成立；不代表跨網路所有動作永不失敗 |
| 公版參考 | 外部職能標準的職位與任務資料，供顧問查漏；不代表員工已負責該工作 |
| 排除範圍 | 員工明確表示沒做或不負責的具體工作，由 App 獨立保存；不寫入 Memory，也不自動加入向量查詢 |

## 採用的外部文件方法

以下公開方法用於安排報告的層次與閱讀順序；具體章節與設計取捨依 Caliburn 的需求決定。

| 來源 | 本報告如何使用 |
| --- | --- |
| [C4 diagrams](https://c4model.com/diagrams)／[component](https://c4model.com/diagrams/component)／[dynamic](https://c4model.com/diagrams/dynamic) | 先看系統邊界，再看關鍵內部合作；只畫有解釋價值的層級 |
| [arc42 building-block view](https://docs.arc42.org/section-5/)／[runtime view](https://docs.arc42.org/section-6/) | 分開靜態責任與代表執行情境，不用一張巨圖混畫所有關係 |
| [Microsoft architecture design specification](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-design-specification) | 讓設計理由、圖、取捨與業務目標對應，保留可追查依據 |
| [Diátaxis explanation](https://diataxis.fr/explanation/) | 以解說幫助讀者理解原因與關係，API 細節及操作步驟另有文件說明 |

## 技術依據與 Caliburn 選擇

| 官方能力 | Caliburn 的使用方式／限制 |
| --- | --- |
| [OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling) | 模型提出工具要求，App 執行並回傳結果；工具集合、順序和候選權限由本產品決定 |
| [OpenAI Compaction](https://developers.openai.com/api/docs/guides/compaction) | 承接 standalone 返回視窗；何時壓縮、如何保存與取消，是 App 的政策 |
| [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | 用持久 Checkpointer 承接 Graph 狀態；產品 Memory 仍有自己的版本、引用與發布責任 |
| [PostgreSQL Transactions](https://www.postgresql.org/docs/current/tutorial-transactions.html) | 為界線內的資料修改提供交易機制；App 定義正式化、操作重入與發布的業務邊界 |

表中分開官方提供的能力與 Caliburn 的使用方式：框架提供保存與接續機制，產品仍須定義資料資格、採用時點及取消規則。各來源是設計依據，不代表業界唯一共識。精確依賴版本以[技術決策](../../implementation/technology-decisions.md)與專案鎖檔為準，相容性仍須由測試確認。

## 設計文件與驗證來源

| 閱讀主題 | 延伸閱讀 |
| --- | --- |
| 產品需求與架構關係 | [產品概念](../../product-concept.md)、[架構 Map](../../target-architecture-map.md) |
| 職務分析的專業方法 | [完整工作分析](../../guides/2026-09-09-complete-work-analysis-guide.md)、[JD 撰寫](../../guides/2026-09-09-jd-field-and-writing-guide.md) |
| 工具與模型參數設計 | [共用工具設計](../../specs/2026-09-27-agent-tool-contract-design-research.md)、[Memory 工具](../../specs/2026-09-27-memory-object-update-tool-contract.md)、[JD 工具](../../specs/2026-09-29-jd-model-tool-contract-review.md) |
| Context、執行與恢復 | [共用執行機制](../../specs/2026-09-27-shared-agent-execution-and-state-design.md)、[資料保存](../../architecture/persistence.md) |
| 程式模組的劃分 | [系統責任與資料流](../../architecture/system-boundaries.md) |
| 實驗範圍與驗證限制 | [驗證對照](../../history.md#source-d58692bbe6b4baa7267f)、[實驗發現彙整](../experiment-findings.md) |
