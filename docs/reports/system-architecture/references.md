# 附錄：術語、來源與維護方法

[報告目錄](README.md)

## 術語

| 名稱 | 本報告中的意思 |
| --- | --- |
| JD | 職務說明書；可管理的結構化產品成果，不是整份 Markdown |
| Agent | 具有特定分析職責、Prompt、Context 與工具權限的執行角色 |
| Runtime／共用執行機制 | 模型及工具的執行、接續、保存、控制；不是整個 App 後端的同義詞 |
| Turn | A 處理一次員工輸入的完整工作，可能包含多個 Step |
| Step | 一次模型回應與該次工具處理；不等於正式訪談訊息或 LangGraph super-step |
| 訪談序號 | 同一職務檔案有效訪談訊息的正式順序；不等於模型呼叫次數 |
| Context | App 實際送入這次模型請求的指令、歷史、資料與工具相關內容 |
| Memory | 原始訪談、工作情境、工作理解所形成的可回查工作記憶體系 |
| Map | 供模型辨認可讀物件的導覽，不是向量資料庫或全文摘要 |
| 候選 | 尚未正式採用的工作資料；可以已保存且可恢復，不等於只在 RAM |
| 物件身分／修訂 | 同一個情境或理解的持續身分／它在某次修改後的固定內容與關係 |
| Memory 快照 | 發布時選定的一組物件修訂及固定關係，不要求所有物件版本號相同 |
| Diff | 指定舊、新基準間的內容或關係差異；本身不是核對完成證明 |
| Checkpoint | Graph 已保存的執行狀態，不是正式 JD／Memory 的替代資料庫 |
| Compaction | 供應商產生的壓縮接續視窗；不是刪除原始訪談的保留政策 |
| 原子提交 | 一組資料修改一起成立或一起不成立；不代表跨網路所有動作永不失敗 |

## 採用的外部文件方法

查閱日期為 2026-10-01。下列是公開方法與契約；本報告的章節組合和 Caliburn 的具體取捨不是廠商替本產品做的保證。

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

本報告沒有為了新穎而重新選框架，也沒有把單一廠商作法稱為全業界唯一共識。精確依賴版本與鎖檔沿[技術決策](../../implementation/technology-decisions.md)及 repo 的 lock files；示意圖不取代相容性測試。

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

更新時先選定新的 Git 基準，再對照受影響的責任文件、程式與證據；同步修正文句、圖說與圖，最後檢查連結及實際渲染。報告發現規格衝突時，回到原責任文件處理，不在教授版偷偷決定新的產品行為。

圖中活動、來源版本與合成案例是解說，不複製完整 API 格式。待產品行為或公開契約改變，再更新相應章節即可，不必讓每次函式改名都造成整份報告重寫。基準、限制與證據必須一起更新，不能只把「未完成」刪掉。

## 本次文件校核範圍

2026-10-01 初版完成八張圖的 Mermaid 渲染與逐張目視檢查，並檢查本地連結、程式碼區塊、圖稿配對及差異格式。初版只看過 HTML 內嵌渲染，沒有驗證獨立 SVG 解析；使用者回報後，重現第 2、3、5、6、7、8 圖因未閉合的 HTML 換行標籤而解析失敗。後續改用 XML 序列化，檢查獨立 SVG 解析及圖片載入，另輸出 PNG 供正文使用，不改圖的架構意義。

2026-10-02 以 `83979421` 的程式與既有證據更新本報告、工程架構導覽與產品介紹：同步正式入口切換、45 輪長旅程及 T01–T18 結案狀態，保留品質、壓縮、恢復與跨平台驗證限制。Memory 重新准入已有實作，但三輪等待政策尚未確認，不混同為缺少全部接線。

**B2 不回交 B1 是已確認設計，不是本次提出的候選方案。**第五章與圖六因此採 B1 → B2 → 發布。靜態核對發現實作尚未完全符合：

- [B2 指引](../../../apps/api/src/caliburn/agents/work_understanding_analyst/instructions.py)仍提供 `needs_situation` 結果；[B2 執行器](../../../apps/api/src/caliburn/agents/work_understanding_analyst/runner.py)會載入該指引。
- [Memory 流程](../../../apps/api/src/caliburn/workflows/memory_batch.py)接受 `SituationRework`，預設最多回交兩次；[階段切換](../../../apps/api/src/caliburn/features/work_memory/candidate_lifecycle.py)可由理解階段切回情境階段。
- [產品啟動接線](../../../apps/api/src/caliburn/bootstrap.py)將上述流程交給背景執行服務，未關閉回交能力。因此不是只找到未使用的註解；但本次沒有新增執行實驗，也不據此斷言既有長旅程曾實際觸發回交。

這是需修正的實作差異，不重新打開單向流程決策，也不以文件更新冒充已修程式。本次只更新文件，沒有修改產品程式、重跑產品測試、存取 Demo 資料庫或呼叫付費模型。第五、七章的測試結果引用既有紀錄；後續移除回交分支並驗證後，再同步移除此限制。

文件驗證涵蓋本次更新的 17 份報告、架構與入口文件，本機連結與章節定位檢查通過；另在決策及背景生命週期入口補上有效流程註記。八組 Mermaid／SVG／PNG 檔案配對完整，SVG 可作 XML 解析；圖稿原始內容未改，另目視確認圖六仍清楚呈現單向流程。本次未重新渲染整組圖，也未重新核實所有外部網站或全部歷史規格。
