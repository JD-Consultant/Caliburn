# Q019-APP-01 Task 2：安全收尾與訪談來源

> 2026-09-06 · **Task2／Checkpoint A已保存：`e1a3cbf0`／`q019-safe-turn-closure-v1`；209 passed／0 skipped，獨立複核R01 CLOSED。**先停止回報，不接API／UI。§3–4保留原停點／核准沿革；最終結果见§7。本稿不是新的Memory設計。
> [決策入口](../current-decisions.md) → [核准接線 §4–5](2026-09-06-analysis-only-agent-application-wiring-design.md#4-a一份文件一份完整訪談每次發言有自己的執行範圍) → [Task 2 計畫](../plans/2026-09-06-analysis-only-agent-application-wiring.md#task-2安全結束與可抽取來源)。

## 1. 範圍與起點

隔離 `S:/caliburn/.worktrees/analysis-only-agent`、`codex/analysis-only-agent`。Task 1 保存於 `3118e8a1`，只提交8個指定檔案；提交前全回歸177 passed／0 skipped（19.91s）、compileall、offline lock與diff check通過。初次命令誤用另一個環境變數，明確得到159 passed／18 skipped；修正成測試所讀的 `Q019_TEST_DATABASE_URL` 後才取得完整PG結果，不把跳過算通過。

本段目標：安全結束的失敗／取消回合仍保留員工內容，來源可供B1抽取；可恢復／未確定發布的回合不被當完成；不偽造模型成功、工具結果或回滾已發布Memory。原生items、Memory五產物／B1／B2／C不重設計。實際服務worker與UI取消入口留Task3。

## 2. 公開機制核對（2026-09-06重新開啟官方頁面）

| 官方直接能力 | 本段適用範圍／不能推論 |
|---|---|
| [LangGraph Checkpointers：Update state](https://docs.langchain.com/oss/python/langgraph/checkpointers#update-state)：`update_state`新增checkpoint，經既有reducer；`as_node`影響後續節點。 | 可以記錄系統的終止结果，不覆寫歷史checkpoint。**不是停止仍在執行的worker或資料庫交易**；收尾前須已到安全執行邊界。 |
| [Subgraph persistence](https://docs.langchain.com/oss/python/langgraph/use-subgraphs#subgraph-persistence)：per-invocation繼承父Saver，單次可恢復；公開state可檢視子流程。 | 支持本案既有root／child接法。不能只讀root舊outcome，便稱pending child已結束。 |
| [Fault tolerance：error handling](https://docs.langchain.com/oss/python/langgraph/fault-tolerance#error-handling)：型別化error handler、失敗保存、subgraph exception向上傳遞。 | 接點不等於本案已接好；unknown publish不能用catch-all吃掉當成功END。 |
| [OpenAI function-calling結果](https://developers.openai.com/api/docs/guides/function-calling#formatting-results)：結果配對call ID，可回傳成功／錯誤文字，再供模型繼續。 | 格式由應用提供；不能把「不知寫入結果」編成失敗。也不代表OpenAI使用本案的終止enum或資料表。 |

本地 `langgraph==1.2.11` `pregel/main.py` 的公開 `update_state` 實作另有 `values=None, as_node=END` 清除待執行工作路徑；這是source觀察，**不直接當成本段採用方案**。`use-time-travel` 的明確子checkpoint範例用 `checkpointer=True`，不能誤套成 `None` per-invocation 取消的完整官方recipe。具體採用接法與測試結果須在下節記錄。

錯誤分類／不疊重試等已研究原則仍由[失敗處理核對](2026-09-06-analysis-only-agent-failure-recovery-review.md)持有，不重貼整份研究。不宣稱各家有相同底層或本方案品質已實證最好。

## 3. 實作、驗證與審核

### 3.1 T2-B01：Memory 修補可恢復，但停止端拿不到精確對帳身分

**上輪停點：Important／OPEN，當時Task2施工暫停。**Owner已於§4.1核准局部修復，現已恢復進行；本節保留缺口的原始證據，不是本輪再次要求核准。範圍只在現有接線，不是推翻 A／B／C 或 Memory 五產物。

[`live_memory.py:41`](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/live_memory.py:41) 在 `repair_memory` 工具函式內呼叫 C graph；[`repair.py:95`](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/repair.py:95) 的 prepare 節點保存 request，publish 節點再提交。原 publication 已有 [`receipt(operation_id)`](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/publication.py:113)。**缺的不是回執功能，而是外層停止端如何可靠取得「這次工具呼叫對應哪次發布」的身分。**

新增兩個特徵案例，各自在 publish 注入不同中斷：①提交前中斷；②確實提交後、回覆遺失。外層公開 `get_state(..., subgraphs=True)` 兩者都顯示 A 停在 tools；tool task 沒有可查看的 C state，A values 沒有 request 或成功 ToolMessage；`get_subgraphs(recurse=True)` 都只有 analysis。注入器持有真 operation ID，所以測試能確認兩者 receipt／head 確實不同；**正式呼叫端不能使用測試注入器的變數作解法**。

官方直接說明：[Subgraphs — View subgraph state](https://docs.langchain.com/oss/python/langgraph/use-subgraphs#view-subgraph-state) 要求子圖可被靜態發現，工具函式／間接呼叫中的子圖不支援同樣的外層 state inspection；interrupt 傳播是另一件事。這與本地 pinned 1.2.11 實測一致。不能將「有 checkpoint」推成「任何外層 API 都可取得每個內層狀態」，也不能說框架完全沒有對帳或恢復能力。

普通 `invoke(None)` 仍可恢復既有 C：有回執時不重複提交；沒有時會繼續真正發布。因此**恢復工作不等於停止工作時的唯讀對帳**。本段不以恢復偷偷完成員工要停止的寫入、不按最新 head 猜本次成功、不拼私有 namespace、不偽造未配對工具失敗，也不回滾已發布的 Memory。查無 receipt 本身亦不能證明另一筆交易不會提交；需先滿足 worker 已停止的前提。

### 3.2 驗證範圍與目前紅燈

- Worker：新增四種 terminal 來源驗收與兩個上述特徵案例；只改 `tests/test_conversation_lifecycle.py`，未改 runtime／source／B1 實作。
- RED：`pytest -q tests/test_conversation_lifecycle.py -k 'terminal_source or nested_uncertain' --tb=short` → **4 failed、2 passed、19 deselected，4.03s**。失敗分別是沒有 reader `turns` metadata、limit 仍不准抽取、configuration／cancelled 尚無收尾接點。這四項未改 skip／xfail，**目前工作樹不是全綠**。
- 既有回歸＋特徵：`pytest -q tests/test_conversation_lifecycle.py tests/test_extraction.py -k 'not terminal_source' --tb=short` → **41 passed、4 deselected，5.24s**。明確排除新增未實作驗收，不當 Task2 通過。
- Controller 獨立針對風險重跑兩種寫入真值的公開 state 特徵：`pytest -q tests/test_conversation_lifecycle.py -k nested_uncertain --tb=short` → **2 passed、23 deselected，3.40s**。沒有重跑整套產生假完成結論。
- 假模型使用 HTTPX MockTransport；實際 LangChain／LangGraph／SQLite publication 行為。**付費模型呼叫0**；Task2沒跑新 PG 驗證。Task1提交前177項含PG通過不能當本段通過。
- Docker／既有專用PG保持運行，未重啟／清除／搬移資料。Task2未 commit／tag；新增驗收留工作樹待接續。不派完成審核，因實作尚不存在。

完整施工報告：[`task-2-report.md`](../../.worktrees/analysis-only-agent/.superpowers/sdd/2026-09-06-analysis-only-agent-application-wiring/task-2-report.md)。此忽略目錄是詳細過程，不當唯一 durable 決策；阻塞、來源、測試與下一個 gate 已在本稿及 register 保存。

## 4. 上輪提出的接續 gate 與本輪核准

**上輪待討論、現已核准：局部調整 C 與外層停止流程的對帳接線，而非僅修改 conversation／sources。**需要跨到 `live_memory.py`／`repair.py`。以下是當時的候選，不代表已選定實作；本輪授權見§4.1，實際選擇與驗證另記，避免把歷史問題重新當成未決。

1. 優先評估官方可發現子圖接法，讓外層拿到真 C state／request；官方提供元件能力，但如何與既有 create_agent 工具迴圈相接尚未驗證，不宣稱可直接搬用。
2. 若前者必須大幅改 Agent loop，才評估在同一 Checkpointer 以最少技術狀態保存工具呼叫與發布身分的關聯；這是本案接線候選，**不是已研究證實的廠商同款 recipe**。

無論選哪個，都不讓模型多填 ID／版本，不加第二份 Memory／對話庫，不增加模型呼叫，也不改背景整理與即時修補的產品目的。只查回執不足以回答全部安全終止情況，未知仍要留 pending；實際 worker 停止仍屬 Task3。

Owner 確認最小接點範圍後，先補官方 API／最小反例，再完成 Task2來源／取消／未知提交案例及PG回歸，做獨立spec＋quality review；通過才保存本段，回報Checkpoint A。不得越過去做API／排程／UI，也不重開全套 Memory 研究。

### 4.1 Owner核准後的窄幅接續（2026-09-06）

Owner對「先補齊對帳接線，再完成安全停止」回覆同意。准調整C與外層連接，不是先選死資料結構；不得要求模型多填欄位、增加模型呼叫、第二份對話／Memory庫或重写Agent loop。具體公開接法以小型反例與既有恢復測試選定，完成Task2及Checkpoint A先回報。

本轮重開官方 subgraphs／custom middleware／checkpointers，並重讀本案完整接線計畫與來源／發布邊界。既有Docker專用PG仍運行；只讀檢查，沒有重新啟動。Task1的177項為保存點證據，不冒充本輪結果。

### 4.2 局部接線選擇（實作中，尚待整合驗收）

採用官方middleware的`after_model`／自訂state擴充：在工具執行前保存runtime計算的「本輪、模型訊息、tool-call → publication operation」關聯；C沿用該operation。停止端據此查既有publication receipt，不再試圖由ToolNode向內探索隱藏C子图，也不重寫Agent loop。

- [Custom middleware — Custom state schema](https://docs.langchain.com/oss/python/langchain/middleware/custom#custom-state-schema)直接支持由hook維護跨執行接點的技術狀態；[Node-style hooks](https://docs.langchain.com/oss/python/langchain/middleware/custom#node-style-hooks)說明回傳dict如何更新Agent state。
- [Checkpointers — Update state](https://docs.langchain.com/oss/python/langgraph/checkpointers#update-state)是安全收尾所用的公開元件：新增checkpoint、經reducer寫入runtime結果；不執行Memory發布。不把它當worker取消功能。
- **本案映射而非廠商同款recipe：**關聯欄位／穩定operation計算法與terminal來源metadata是為了本案既有publication接點的最少接線。模型schema不增加欄位，沒有第二個Memory／對話庫，也沒有額外模型呼叫。即使查不到receipt仍不可宣稱未執行；必須保留未知狀態。

驗收將覆蓋：已知尚未執行、真正已提交且回覆遺失、尚無確定回執、PG重建後對帳、非成功terminal來源與B1不跳過中段。這些是待驗目標，不將上述官方擴充能力等同實作已通過。

## 5. 本輪整合驗證（程式已交付，獨立review中）

Controller以既有專用PG執行完整package回歸：`pytest -q -rs --tb=short` → **196 passed／0 skipped，23.44s**，exit0。`compileall`、`uv lock --check --offline`（73packages）、`git diff --check`亦通過；Git的LF→CRLF提示不是測試warning。測試全用假模型transport，**付費呼叫0**，未重啟Docker或碰production資料。

此結果針對當次施工snapshot，並不提前宣告Checkpoint A完成。後續若review修正程式或測試，需重新取得最終回歸證據；Task2尚未commit／tag，API／排程／UI未開始。

Worker收尾後，controller再對完整交付重跑：**198 passed／0 skipped，23.31s**，exit0；compileall／offline lock／diff check亦通過。新增的收尾寫回中斷情境已包含在內，沒有用前次196項代替。獨立spec＋quality reviewer已收到Task2-only diff；尚待其裁決，不先宣告Checkpoint A完成。

### 5.1 驗收追溯

| 本段要求 | 測試／實作入口 |
|---|---|
| 成功、limit、配置失敗、已確認取消皆保存員工與先前顧問問題 | [四類來源驗收](../../.worktrees/analysis-only-agent/experiments/analysis-agent/tests/test_conversation_lifecycle.py:303) |
| C已提交只回報真結果；尚不明不發布、不回滾、不接受替代input | [精確對帳](../../.worktrees/analysis-only-agent/experiments/analysis-agent/tests/test_conversation_lifecycle.py:368)、[未明來源與input阻擋](../../.worktrees/analysis-only-agent/experiments/analysis-agent/tests/test_conversation_lifecycle.py:569) |
| 確知未執行才補配對結果；原生items不改写 | [取消前工具驗收](../../.worktrees/analysis-only-agent/experiments/analysis-agent/tests/test_conversation_lifecycle.py:412)、[未知結果不偽造](../../.worktrees/analysis-only-agent/experiments/analysis-agent/tests/test_conversation_lifecycle.py:504) |
| child已封閉、root寫回失敗可續收尾，不重跑工具／模型 | [兩步收尾故障驗收](../../.worktrees/analysis-only-agent/experiments/analysis-agent/tests/test_conversation_lifecycle.py:466) |
| B1拿到真terminal metadata，跨頁保留全文、不跳過中間待處理回合 | [來源metadata／全文](../../.worktrees/analysis-only-agent/experiments/analysis-agent/tests/test_extraction.py:281)、[不跳過中段](../../.worktrees/analysis-only-agent/experiments/analysis-agent/tests/test_extraction.py:311) |
| 重建PG clients後resume／cancel仍分清commit前後 | [四種PG組合](../../.worktrees/analysis-only-agent/experiments/analysis-agent/tests/test_postgres_conversation_lifecycle.py:28) |

入口是[`close_turn`](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/conversation.py:153)與[`send_input`](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/conversation.py:223)。已停止worker並序列化該文件是呼叫前提；實際worker管理仍留Task3。child／root是兩次checkpoint，不宣稱單一SQL transaction；root尚pending時B1不前推，重複收尾只合回已terminal child。Task2不承諾跨舊版本pending checkpoint搬移，也不是實際聊天網頁的取消功能已上線。

## 6. 獨立審核與修復

**T2-R01／Important／修復中：前輪過長時必要問句被連帶省略。**Reviewer完整讀Task2diff，對官方終止接點與source風險作定向檢查。C對帳／停止接線無其他Critical或Important，但用真graph／InMemorySaver重現：前輪員工1600字、AI問「是由主管核准嗎？」；本輪答「不是，是處長」後配置失敗安全封閉，B1的`context_reference=None`。原因是只在**整個前輪**不超過1500字時提供context，即使短問句能放得下也被一併省略。

Controller核對`sources.py`的實際條件與B1consumer確認成立。這是原已核准「保留員工及之前顧問問句」的缺口，不新增產品需求／Memory層。局部修復方向：完整前輪放不下時，仍沿canonical reference提供必要可見問句；保持角色與總字數界線，必要內容確實放不下就明確失敗，不靜默省略。不新增模型呼叫。修後須有實際B1payload回歸、限定複核與fresh full PG；198項舊green不能替代。

第一個R01修復以6項RED重現後，83項局部回歸通過；controller完整PG再驗**204 passed／0 skipped，25.08s**。整前輪放不下時改用原checkpoint的問句reference，必要問句超context或總budget明確失敗，不截斷；沒有增加模型或第二份來源。仍待限定複核；controller另指出「連續安全失敗、緊鄰前輪沒有可見AI問句」屬同一問句保留邊界，需確認不被漏掉。不得僅因204項green就提前關閉R01。

限定複核確認R01仍OPEN：問「是由主管核准嗎？」→員工「不是，是處長」並安全配置失敗→員工「只限特殊案件」再次安全失敗，第二個window只帶前個Human而漏問句。需要跨過沒有可見AI的安全封閉回合，沿canonical range保留最近真問句及中間回答；完整必要range超額仍明確拒絕，不泛化成無界搜尋／另做摘要。第一修復的正常長前輪與預算行為已獲複核；無其他Important。另核實`capture_input`遇前一Human便停止，不能誤宣稱它已提供跨輪方案；本次維持B1來源修復範圍。

## 7. 最終驗收與段落停止

R01第二次局部修補：5項RED證實連續失敗缺問句／完整range超額未拒絕；修後88項局部回歸通過。使用同一canonical reference由最近可見AI至前輪結束保留中間回答，兩個context分支都先驗必要範圍，超context或總budget明確失敗。原始對話／C／Memory分析方式不變。獨立reviewer限定複核裁決 **T2-R01 CLOSED，沒有修法新引入的Important**；其餘Task2項目上一輪已通過，不擴大成整branch merge review。

Controller對最終程式重跑全部package＋既有專用PG：**209 passed／0 skipped，25.83s**；compileall、offline lock（73packages）、diff check通過。只有Git換行提示，無pytest warnings。**付費模型呼叫0**；這是程式、SDK假HTTP與真DB驗證，不是實際訪談品質測試。沒有重啟Docker、不碰正式資料、不改依賴／production。

本地保存只包括本段5個source、3個test、README與隔離結果檔；詳細過程另在main本稿與SDD report留存，不stage main其他歷史修改。保存點完成後更新入口。**Task3–5／API／排程／UI不開工，先停在Checkpoint A回報。**下段需落實worker確實停止／單文件准入，不可把目前`quiescent=True`前提當成已能終止背景thread。若新反例推翻已驗邊界、官方公開API改變或Owner改scope才重開，不重啟全套Memory研究。

保存完成：本地commit `e1a3cbf0601886a4100ab285253ad03547168a4e`，tag `q019-safe-turn-closure-v1`指向同一HEAD；只提交10個指定檔案（875 insertions／47 deletions），staged diff check通過，隔離worktree乾淨。未merge／push，main只更新決策／設計狀態與紀錄，不暫存其他歷史修改。
