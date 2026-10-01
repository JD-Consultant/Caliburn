# 附錄：術語、來源與維護方法

[報告目錄](README.md)

## 術語

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
| 候選 | 尚未正式採用的工作資料；可以已保存且可恢復，不等於只在 RAM |
| 物件身分／修訂 | 同一個情境或理解的持續身分／它在某次修改後的固定內容與關係 |
| Memory 快照 | 發布時選定的一組物件修訂及固定關係，不要求所有物件版本號相同 |
| 差異（Diff） | 指定舊、新基準間的內容或關係變化；讀取差異不代表已核對完成 |
| 執行檢查點（Checkpoint） | Graph 已保存的執行狀態，用於接續工作，不取代正式 JD／Memory 的保存 |
| 上下文壓縮（Compaction） | 由供應商產生壓縮後的接續視窗，不決定原始訪談是否保留 |
| 原子提交 | 一組資料修改一起成立或一起不成立；不代表跨網路所有動作永不失敗 |

## 採用的外部文件方法

查閱日期為 2026-10-01。以下公開方法用於安排報告的層次與閱讀順序；具體章節與設計取捨仍依 Caliburn 的需求決定。

| 來源 | 本報告如何使用 |
| --- | --- |
| [C4 diagrams](https://c4model.com/diagrams)／[component](https://c4model.com/diagrams/component)／[dynamic](https://c4model.com/diagrams/dynamic) | 先看系統邊界，再看關鍵內部合作；只畫有解釋價值的層級 |
| [arc42 building-block view](https://docs.arc42.org/section-5/)／[runtime view](https://docs.arc42.org/section-6/) | 分開靜態責任與代表執行情境，不用一張巨圖混畫所有關係 |
| [Microsoft architecture design specification](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-design-specification) | 讓設計理由、圖、取捨與業務目標對應，保留可追查依據 |
| [Diátaxis explanation](https://diataxis.fr/explanation/) | 教授版重在理解原因與關係，不重抄 API reference 或操作手冊 |

## 技術依據與 Caliburn 選擇

| 官方能力 | Caliburn 的使用方式／限制 |
| --- | --- |
| [OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling) | 模型提出工具要求，App 執行並回傳結果；工具集合、順序和候選權限由本產品決定 |
| [OpenAI Compaction](https://developers.openai.com/api/docs/guides/compaction) | 承接 standalone 返回視窗；何時壓縮、如何保存與取消，是 App 的政策 |
| [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | 用持久 Checkpointer 承接 Graph 狀態；產品 Memory 仍有自己的版本、引用與發布責任 |
| [PostgreSQL Transactions](https://www.postgresql.org/docs/current/tutorial-transactions.html) | 為界線內的資料修改提供交易機制；App 定義正式化、操作重入與發布的業務邊界 |

本報告沿用既有框架選擇，將各來源視為可參考的方法，而非業界唯一共識。精確依賴版本以[技術決策](../../implementation/technology-decisions.md)與專案鎖檔為準，相容性仍須由測試確認。

## 設計文件與驗證來源

| 要追的問題 | 原責任文件 |
| --- | --- |
| 產品需求與架構關係 | [產品概念](../../product-concept.md)、[架構 Map](../../target-architecture-map.md) |
| 職務分析的專業方法 | [完整工作分析](../../guides/2026-09-09-complete-work-analysis-guide.md)、[JD 撰寫](../../guides/2026-09-09-jd-field-and-writing-guide.md) |
| 工具與模型參數設計 | [共用工具規範](../../specs/2026-09-27-agent-tool-contract-design-research.md)、[Memory 工具](../../implementation/memory-tools.md)、[JD 工具契約](../../specs/2026-09-29-jd-model-tool-contract-review.md) |
| Context、執行與恢復 | [共用執行實作](../../implementation/agent-execution.md)、[資料保存](../../architecture/persistence.md) |
| 代碼維護與測試方式 | [程式組織](../../implementation/code-organization.md)、[撰寫規範](../../implementation/coding-standard.md)、[SDD／TDD](../../implementation/development-standard.md) |
| 完成範圍與驗證限制 | [任務表](../../plans/2026-09-29-target-rebuild/tasks.md)、[V01–V28 驗證對照](../../plans/2026-09-29-target-rebuild/evidence/t17-v01-v28-closure.md)、[實驗發現彙整](../experiment-findings.md) |

## 如何維護這份閱讀版

報告以 Markdown 分章、PNG 顯示架構圖，保留 SVG 放大版；圖的唯一編輯來源是同名 `.mmd`。圖的編輯與重新渲染方式見 [diagrams/README](diagrams/README.md)。不需要為閱讀報告安裝或啟動 Caliburn。

更新時先選定 Git 基準，核對受影響的規格、程式與證據，再同步修改文字、圖說與圖，檢查連結和渲染結果。若發現規格衝突，須在原規格處理；本報告只解說設計，不自行改變產品行為。

圖中的活動、版本與合成案例用於解釋概念，不複製完整 API 格式。產品行為或公開契約改變時，更新相關章節；單純函式改名不必重寫整份報告。更新進度時，須一併核對基準、限制與證據。

<a id="本次文件校核範圍"></a>
## 文件校核紀錄

2026-10-01 初版完成八張圖的 Mermaid 渲染與逐張目視檢查，並檢查本地連結、程式碼區塊、圖稿配對及差異格式。初版只看過 HTML 內嵌渲染，沒有驗證獨立 SVG 解析；使用者回報後，重現第 2、3、5、6、7、8 圖因未閉合的 HTML 換行標籤而解析失敗。後續改用 XML 序列化，檢查獨立 SVG 解析及圖片載入，另輸出 PNG 供正文使用，不改圖的架構意義。

2026-10-02 以 `83979421` 的程式與既有證據更新本報告、工程架構導覽與產品介紹，記錄正式入口切換、45 輪長旅程及 T01–T18 結案狀態，並保留品質、壓縮、恢復與跨平台驗證限制。Memory 失敗後重新啟動的機制已有實作，但等待三輪的政策尚未確認。

第五章與圖六依已確認設計呈現 B1 → B2 → 發布，不回交 B1。靜態核對發現以下實作差距：

- [B2 指引](../../../apps/api/src/caliburn/agents/work_understanding_analyst/instructions.py)仍提供 `needs_situation` 結果；[B2 執行器](../../../apps/api/src/caliburn/agents/work_understanding_analyst/runner.py)會載入該指引。
- [Memory 流程](../../../apps/api/src/caliburn/workflows/memory_batch.py)接受 `SituationRework`，預設最多回交兩次；[階段切換](../../../apps/api/src/caliburn/features/work_memory/candidate_lifecycle.py)可由理解階段切回情境階段。
- [產品啟動接線](../../../apps/api/src/caliburn/bootstrap.py)將上述流程交給背景執行服務，未關閉回交能力。這是已接入產品的分支，但此次沒有新增執行實驗，無法據此判定既有長旅程是否曾觸發回交。

單向流程的設計決定維持不變；後續須移除回交分支並驗證，才能解除這項限制。此次校核只更新文件，未修改產品程式、重跑產品測試、存取 Demo 資料庫或呼叫付費模型。第五、七章的測試結果均引用既有紀錄。

上述校核涵蓋 17 份報告、架構與入口文件，本機連結與章節定位檢查通過；決策及背景生命週期入口另補上有效流程註記。八組 Mermaid／SVG／PNG 檔案配對完整，SVG 可作 XML 解析；圖稿內容未改，並目視確認圖六呈現單向流程。該次校核未重新渲染整組圖，也未重新核實所有外部網站或全部歷史規格。

同日另以 `68fbb018` 為文字整理基準，潤飾本報告、產品概念及架構正文，共 21 份文件。修訂統一中文角色名稱、拆分長句，並將歷史決定與現況分開說明；原始證據及產品程式未改。本機連結與章節定位檢查通過，改名章節保留舊定位，程式識別字與連結目標未刪除。工程分工圖僅調整一處角色標籤，其他程式碼區塊及本報告八組圖稿內容不變；未新增產品測試結果。
