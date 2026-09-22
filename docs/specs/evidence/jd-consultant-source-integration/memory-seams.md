# OI-01／02：已驗 Memory、案例與原話的接線核對

2026-09-13；唯讀核對／隔離 G4→有界施工前置。新版基準 `c135f18202a888a478ac2d67a72e1e811643e079`；舊實證 checkout HEAD `033540cef870d1f92baa5c69133a799231c46d48`，本次所讀 analysis-agent src／pyproject／lock 無工作樹修改。只寫本文；沒有安裝、模型、服務、DB 或新測試。

## 結論與效力

**先接「本輪已保存原話→顧問可用的確切來源→JD 引用→原話回查」，再接已有 Memory 的讀取、即時更正及背景整理。**本輪原話不必等 B1／B2 完成才可成為 JD 依據；原話回查完成也不代表整套 Memory 已完成。先做這條路可立即驗新版來源 owner，沒有理由另建原話表、先複製一份聊天或重跑整套 Memory 研究。

有效路由為[目前決策](../../../current-decisions.md)、[未完清單 OI-01／02](../../2026-09-13-jd-app-open-issues.md)及[來源契約 §9](../../2026-09-12-jd-relational-agent-tool-contract.md#9-來源引用契約)。[ADR0074](../../../adr/0074-tested-consultant-runtime-source-and-memory-adoption.md)與 [ADR0075](../../../adr/0075-relational-jd-authority-and-structured-editor.md)仍 Proposed；本文不改正式 ADR0060，不要求整合舊服務或舊 JD 格式。

## 已驗成果，不能直接移植的結論

- [CT49](../../../../.worktrees/analysis-only-agent/docs/specs/2026-09-09-ct49-fixed-long-interview-results.md)在固定版完成一個接案前端全職位的 11 輪自然訪談、案例差別、晚期更正及原話回查；8 份詳記／來源頁、重開原話核對相等。導覽繞路、重複措辭及更正延遲有已知 Minor；不是所有職位、百輪或 JD 生成驗收。
- [CT50](../../../../.worktrees/analysis-only-agent/docs/specs/2026-09-09-ct50-tested-profile-results.md)採 A／B2 16 模型／15 工具，A／B1／B2 high，顯式輸出 8192、OpenAI native compaction 12000；564 離線、41 真 PG 及限定續談回查通過。[CT51](../../../../.worktrees/analysis-only-agent/docs/specs/2026-09-09-ct51-output-budget-results.md)8K／16K 比較未證明升級必要，沒有採用 16K。
- 這些結果是舊 `ChatOpenAI Responses` 路線及固定提示／情境的證據。新版 `ConfirmedChatAnthropic` 的接合測試不等於已重現 CT49 的自然內容品質；不能把 OpenAI compaction blocks、`response_metadata.status` 或舊 `closed_turns` 欄位直接套到新版。
- 舊 JD 後續已修正來源取得細節：[Task6 原話取得回歸](../../../../.worktrees/analysis-only-agent/docs/specs/evidence/jd-editor-task6/task6-source-acquisition-regression-report.md)有真 owner read／替換工具偽造回傳／current-input binding 保留的 3 個情境。這是應帶到新版的反例，不能複用其 Plate writer。

## 能力與實際接點對照

下表舊檔均位於 `.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/`；新版檔位於 `experiments/jd-relational-app/src/jd_relational/`。它們是實際公開函式／類別接點，不表示已有可安裝的正式 package。

| 效果 | 舊實證接點 | 新版已具備／必要接合 |
|---|---|---|
| 本輪原話已保存後取得來源 | [sources.py](../../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/sources.py) `ConversationReader.capture_input(message_id)`；`live_memory.py:MemorySession.before_agent` 凍結初始 guide／head／來源 | [ai_runtime.py](../../../../experiments/jd-relational-app/src/jd_relational/ai_runtime.py) `_run` 以 `durability="sync"` 送原 `HumanMessage` 與 V2 run。來源取得須在實際 input checkpoint 之後，不在 HTTP 收到文字或 `_run` invoke 之前宣稱已保存。 |
| 精確原話及長文分頁 | `ConversationReader.read(reference, offset)`／`capture`；每頁至多 3000 可見文字字元，保留 role、message_id、text_offset，省略工具／推理／runtime notice | [ai_checkpoints.py](../../../../experiments/jd-relational-app/src/jd_relational/ai_checkpoints.py) `discover`／`observe_at(..., root_config, source_config=...)` 已解析固定 root／child／START；`AiRunObservation.messages` 是原生資料的副本。可作新版來源 reader 的共用輸入，無須再寫另一套 checkpoint decoder。 |
| 員工看到原話 | 舊 reader 的可見原文投影 | [chat_history.py](../../../../experiments/jd-relational-app/src/jd_relational/chat_history.py) `public_chat_text`／`ChatHistoryService.read` 已提供固定 root＋source 的原對話頁。chat cursor 是整段聊天分页，不等於一個可引用的問答範圍；不能直接把它當 JD source token。 |
| Memory 導覽→理解→案例→原話 | [memory_tools.py](../../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/memory_tools.py) `memory_access`、`memory_read_tools`、`readonly_file_tools`；官方 `ls`／`grep`／`read_file` 與具名 `read_conversation` | 新版只有 `jd_read`／`jd_change_read` 和業務工具，尚無這條讀取路由。先接具名原話 reader；Memory 就緒後再讓 summary path 經 owner 解析原始來源，不讓模型重抄編碼 metadata。 |
| 可修訂工作理解與案例詳記 | [memory.py](../../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/memory.py) `MemoryArtifacts.reader`／`guide`／`read_text`／`source_window`；`save_extraction` 產不可變 summary＋candidates，`save_memory` 僅準備新版本 | `knowledge.md`／`guide.md` 及 `/interviews/.../summary.md` 是內容投影；來源 header 是 App 生成。案例不是另一張待新設的永久工作事實表；詳記只描述其來源範圍，後續更正須再讀目前理解。 |
| Memory 正式版本與成功結果 | [publication.py](../../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/publication.py) `PublicationStore.current`／`prepare`／`publish`／`receipt`／`repair_receipts` | 官方 Store 保存內容；既有 head／receipt 選有效版本、CAS 及同 key 查回。新 JD 保存不可另存一份可写 Memory；新版 host 目前尚無 Store 或此 metadata 的配置、初始化與排空。 |
| 顧問即時更正同份 Memory | [live_memory.py](../../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/live_memory.py) `MemorySession`、`repair_memory`／`reconcile`，`RepairWorkflow` 使用既有 patch 能力 | 本輪固定 initial guide；相符的 C feedback 才更新本輪 read head。舊輸入 C feedback 不蓋新 guide，背景發布不偷偷改 active run 讀取版。新版需接相同責任與原 receipt 收尾，不能把 JD undo 同時套到 Memory。 |
| 背景產生詳記／整理理解 | [extraction.py](../../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/extraction.py) `ExtractionWorkflow.start`／`reextract`／`resume`；[consolidation.py](../../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/consolidation.py) `ConsolidationWorkflow.start`／`start_reextraction`／`resume` | B1 保留來源角色、條件、案例與候選；B2 原子發布，成功才推進 processed_source，C 更正不推進此游標。沿已驗具名能力和受控派發，不從舊 `AnalysisService` 連同 catalog／global lock／Plate 接回。 |
| 來源確實取得後寫入 JD | 舊 [jd_tools.py](../../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/jd_tools.py) `before_agent`、`wrap_tool_call`；`sources.observe_reads` 比對真 owner 回傳；[jd_references.py](../../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/jd_references.py) `validate_sources` | [reads.py](../../../../experiments/jd-relational-app/src/jd_relational/reads.py) `command_context` 已呼叫 `source_resolver(token, document_id)`，只接受同文件且可讀的 `domain.Source`；`basis_refs`／`jd_source_link`／文字 basis digest 已存在。不另加語意判定引擎。 |

## 單一資料權威與依賴實況

| 資料 | 沿已驗分工的 owner | 禁止混淆 |
|---|---|---|
| 原始 Human／AI／工具／原生執行資料 | 同一文件的 PostgresSaver；reader 只投影確切 checkpoint 範圍 | 不從公開聊天頁反建原生訊息、不把 Memory 詳記當逐字原話、不另外建立原話副本。 |
| Memory／案例詳記內容 | PostgresStore／StoreBackend；不可變 artifact/version，PublicationStore 選 current | published head 未前進不能宣稱新版理解已生效；JD current／revision 不成為 Memory 第二權威。 |
| JD 正文／關係／來源 link | 新版 relational current＋原 revision／operation | link 僅保存 owner locator 與目標 basis；原話不複製進 JD。來源存在不證明語意支持正確，修改 basis 後須保留 `needs_recheck`。 |
| 執行／通知狀態 | 新版原生 root／child 與各業務 receipt | 手改通知是 request 投影，不能作 Human 或自動改 Memory；active child 期間不以 root `update_state` 插入另一權威。 |

版本直接讀兩個 `uv.lock`，不是查 PyPI 最新版；以下相同版本可減少接合面，但不構成自動相容證明。

| 依賴 | 已驗 analysis-agent 現行 lock | 新版 lock |
|---|---|---|
| Python／LangChain／LangGraph | 3.12；1.4.0／1.2.11 | 相同 |
| core／checkpoint／PostgresSaver | 1.6.2／4.2.0／3.1.2 | 1.6.3／4.2.0／3.1.2 |
| SQLAlchemy／psycopg／pool | 2.0.52／3.3.5／3.3.1 | 相同 |
| Deep Agents | 0.7.13 | 未加入 |
| OpenAI route | langchain-openai 1.6.0、openai 3.8.0、openai-agents 0.22.0 | 僅 dev openai 3.13.0；未接此產品路線 |
| Anthropic route | lock 含 adapter 1.7.1／SDK 1.4.0，但 CT49–51 不是此路驗收 | 已接 adapter 1.7.2／SDK 1.5.0 的完整終端 guard |

[舊 pyproject](../../../../.worktrees/analysis-only-agent/experiments/analysis-agent/pyproject.toml) 明示 `tool.uv.package=false`，`__init__.py` 僅模組說明；還含舊 JD contract 的 editable path。正式 `packages/` 現只有 OCS、indexer、job-analysis contracts，`apps/api/app`／`packages` 無上述 `MemoryArtifacts`／`ConversationReader`／`PublicationStore` 實作。**目前沒有可直接加入 dependency 的受測 Memory 正式套件。**不能把修改 PYTHONPATH、editable 指到 worktree 或 wrapper import 說成完成採用。

## 最短正確施工順序（本案映射）

1. **先只接原話 owner。**在目前 AI run 內，input 已同步保存後，從 `AiRunCheckpoints` 的固定 observation 取得原始 Human 與必要前問／中間回答。沿既有測試保留「只答『對』必須有問題脈絡」「技術回合的原回答不可消失」。App 產生 dataset／document／固定 root＋source／message 範圍的 locator；不讓 LLM 填 checkpoint、版本、ID 或自行編碼。確切 token shape 留同一來源契約正式生成時決定。
2. **來源供給與取得分開。**本輪直接供給的原話 locator 是 App 對「這批已保存且提供的輸入」的綁定；歷史原話須走真 owner read。可變 guide／summary path、可解析 token 或工具名稱相同，都不能冒充成功讀取。有限接合須保留原工具 call/result 配對與取得依據，重開後仍可核，不新增取得事件表。
3. **讓顧問沿原 JD 業務工具使用 `basis_refs`。**同 run 的 resolver 回實際同 dataset／document 可讀結果，在現有 binding 前檢查；歷史或恢復查原 identity／receipt，不因 cache 遺失重讀後重 bind。保存後經同來源 reader 回查精確原話；新的 public source DTO／HTTP 只為此投影，不重造聊天服務。
4. **再接 Memory owner 與已驗角色。**先完成固定 head 的導覽／正文／詳記讀取，續接 C 明示更正，再接 B1／B2 既有發起／發布責任。正式模組落點、Store initialization／close／backup、provider 適配一起有界驗證；不改已同意三層語意，不要求每輪產 JD／Memory，也不新造 broker 或通用 queue。

## 真正阻擋接線的三項缺口

| ID | 可重現現況與影響 | 下一最小動作／退出條件 |
|---|---|---|
| MS-01：新版尚無來源取得與工具分類 | `AiRuntime.source_resolver` 預設缺省；`AiToolSession._no_sources` 明示不可用；`open_managed_app` 未注入。`_call_identity` 只認 JD tools，`AiRuntime._verify_saved_results` 只認兩個 JD read：直接加 `read_conversation` 會被拒絕或在收尾被當成無 receipt 的 mutation。 | 在原生工具接點明確加入唯一 read-only source 能力與回傳分類，注入同 owner resolver；測本輪及歷史真讀→JD link→重開原话相等、假回傳／跨 scope／未讀拒絕。不要把所有未知工具當 read 豁免。 |
| MS-02：舊來源／Memory hook 依賴不同持久格式與 provider | 舊 `ConversationReader` 只讀 root、locator 沒有 dataset／child namespace；`MemorySession.after_model` 要求 OpenAI `status=completed`，舊 compaction 投影只認 Responses blocks；新圖使用 root＋child、START material、Claude `stop_reason`／終端事件。 | 用新版現有 observation／native完整回覆接點承接同語意，避免 copy 舊 graph decoder。驗 active child 固定來源不漂移、缺終端不取得新回覆權、上一 guide/C 回傳不覆蓋本輪及純訪談不強迫寫稿。 |
| MS-03：Memory 未有可採用的 package／資料生命週期 | 新 host 只開 JdStorage＋Saver，setup/check 只核 JD 與 Saver；沒有 Store／publication metadata／B/C 收尾接點。舊 package=false 且依賴舊 JD editable contract。 | 在核准新落點形成獨立 Memory 能力及公開 ports，排除舊服務／JD import；明示初始化 Store 與 publication、共享宿主排空和既有 receipt 查回。用固定模型／真 PG 驗 C與B不覆蓋較新版本、重開原話／Memory／JD一致。完成之前 OI-02 仍是核心未完。 |

MS-01 可先交付完整原話縱向切片；MS-02／03 是接完整 Memory 的工程門檻，不是要求重啟既有品牌研究或再次詢問員工資料表選擇。自然內容品質仍另按核准資料／次數／預算驗收，不能以固定 SDK 代替 CT49 等級的新路線實測。

## 官方依據與本次查核界線

本輪沿[已核兩家及原生 context 接點](../2026-09-13-jd-consultant-context-preflight.md#2-官方事實)，沒有重新廣搜：OpenAI [function calling](https://developers.openai.com/api/docs/guides/function-calling)與 [conversation state](https://developers.openai.com/api/docs/guides/conversation-state#manually-manage-conversation-state)支持 App 執行、原 call/result 配對及完整原生回覆延續；Anthropic [tool results](https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use)／[streaming](https://platform.claude.com/docs/en/build-with-claude/streaming)支持實際工具結果與終端判斷。各家沒有指定 Caliburn 的 source locator、Memory 表或三層格式。

LangChain／LangGraph／Deep Agents 的原生讀取、middleware、Store 與同步 checkpoint 已在既有研究／固定版測試核對；本文只比對現碼，未宣稱重新取得最新版官方正文。來源已足以支持有限接合，後續只針對上述不相容或實測反例補核。本文所有 PASS 都是引用舊報告；本次沒有重跑其模型、PG 或測試。
