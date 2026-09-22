# RS-4：新宿主 AI 回合恢復與原結果查回

日期：2026-09-13。施工基準 `3980689a`；隔離 `experiments/jd-relational-app`，production ADR0060 不變，ADR0075 Proposed。本稿承接[本程序回合與工具](2026-09-13-jd-ai-runtime-and-tools-slice.md)；**新宿主四組真程序／PG 恢復已通過，相關離線最終293 PASS；完整聊天／Memory App 尚未完成。**

## 1. 本次效果與責任

App 重啟時先查明上次 AI 的實際保存結果，再開放新的手改／訪談。原始問答、已完成的模型回覆和已保存 JD 都保留；不重新呼叫模型、不重建原候選、不重做工具命令。正常 terminal 回合只讀。上次未完成的 running 回合在結果查明後標為 failed，已保存 JD 仍依各自原回執表示成功；這是本案中斷處理選擇，不代表兩家模型公司規定的產品狀態。

唯一當前 JD 是十三張業務／保存表的共同權威；本次不新增 run 表、聊天副本、程序登記表或通用回退引擎。訪談／工具訊息仍使用 LangGraph 原生 Saver。Memory、來源與選區、聊天 HTTP／Web 仍接續施工，Excel 延後，0 產品模型呼叫。

## 2. 依據分工與採用限制

使用者再次要求 LLM 相關以 OpenAI／Anthropic 官方資料為基準。本次細節沿[聊天契約前置](evidence/jd-relational-ai-restart/chat-contract-preflight.md)的兩家工具結果與續接對照；AWS 僅作業務操作重試參考，不替代模型契約。

| 官方來源／版本 | 可證事實 | 本案映射 |
|---|---|---|
| [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling#handling-function-calls)，查閱 2026-09-13，現行 Responses API／商業 API 參考 | App 執行 client function，以原 call_id 回傳結果；結果可表達失敗，不能把模型提出呼叫當作已執行。 | 原 SQL 回執投影回原工具 call，不另產生工具意圖或用 AI 敘述代替保存證據。 |
| [Anthropic handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)，查閱 2026-09-13，現行 Messages API／商業 API 參考 | client tool 結果須配原 tool_use_id；失敗以 tool_result 的錯誤表示，順序與訊息區塊有明確限制。 | 保留原完整 AIMessage，僅補尚未回答的原工具結果；已回答者與原回執不符便阻擋。SDK 格式轉換留給已驗 adapter。 |
| [AWS safe retries](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)，現行公開方法文 | 原意圖、原 request token 與原結果要相符；回覆遺失不應製造第二次效果。 | 沿現有 operation identity／digest／receipt；一次 AI 回合可有多個獨立保存操作，不冒充跨回合 ACID transaction。 |
| [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[BaseChatModel](https://reference.langchain.com/python/langchain-core/language_models/chat_models/BaseChatModel)、[middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)，Python LangGraph 1.2.11／LangChain 1.4.0／core 1.6.3，已鎖穩定套件，MIT | 原生 checkpoint／subgraph 由已編譯的圖讀取；實際 task／channel 相容性須核本版原碼與 probe。 | 共用同一 create_agent 工廠、state／context／tools／middleware 節點結構；檢視模式不開 provider，model／tool wraps 與原 after_model hook 明確拒絕執行。這是有限接合，非大廠內部實作宣稱。 |
| [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)、[PG18 locking](https://www.postgresql.org/docs/18/explicit-locking.html)、[READ COMMITTED](https://www.postgresql.org/docs/18/transaction-iso.html#XACT-READ-COMMITTED) | OS 程序組停止與 DB transaction 結果是不同事實；取得原操作的交易屏障後仍須讀原結果。 | 沿現行真正 HostLease 與 JdStorage 的 document→head row locks。沒有本地 Future 不能當作舊宿主已停止；本次恢復路徑沒有 advisory lock。 |

兩家模型文件沒有指定本案資料表、HostLease 或 LangGraph checkpoint 結構。套件授權與既有 provider 私有接點限制仍見[上輪結果](2026-09-13-jd-ai-runtime-and-tools-slice.md)，本次沒有升級依賴。完整宿主約束與四組驗收設計見[宿主前置](evidence/jd-relational-ai-restart/host-validation-preflight.md)。

## 3. 新增有限接點

1. `AiRunCheckpoints.discover(document_id, dataset_id)`：一次 latest 僅取得位置，再固定 root／child；START 必讀原 Saver input。scope／原話 digest／原模型材料不符或未知 pending 即阻擋。None 只表示沒有 AI 材料，不表示沒有人工 pending，也不證明舊宿主停止。
2. `ManualRuntime` 同一 startup scan 先交 AI coordinator 對帳，再走原人工檢查。全 catalog 包含封存文件，全部可確認才 ready。失敗與逾時保留實際 Future，client 不能以等不到結果取消 writer。
3. `adopt_previous_foreground` 僅限本次真 startup callback、exact 文件與 scan 執行緒、已注入有效 previous-host capability。foreign reservation 沒有偽造 Future，只能查原結果／完成停止後收尾；不能執行原 BoundEdit。
4. AI recovery 共用本程序的 binding decoder、原 AIMessage／call 核對、SQL receipt 投影、未回答工具補結果與 native close。沒有 receipt 時才沿共同 failure-only 對帳，取得真 SQL 結果後再閉合原回合。確認已保存但回覆遺失，讀回原紀錄；unknown 保持阻擋。
5. managed App 在 lifespan 開放請求前建立同 owner 的 AI coordinator。尚未開訪談服務時，用同一 Agent 工廠的 execution-disabled 檢視模式讀原紀錄；不以簡化 MessagesState 圖誤讀 pending 工具。

檢視模式只供 get_state／get_tuple 與有停止證據的既有 close adapter 使用。即使誤 invoke 被攔截，LangGraph 仍可能先保存 input／error checkpoint；因此它不是任意圖操作的唯讀沙盒，App 恢復流程本身永不 invoke／resume。

## 4. 驗證與尚未完成

首敗：既有 startup 對原 running／START 只能回 document_busy；新原生恢復反例先失敗後通過。managed composition 未註冊 AI owner 的反例也已修正。獨立審查重現 AR-R01：損壞紀錄同時出現 running AI 與人工 pending 時，原流程雖不會 ready，卻先改了 AI 狀態。已在共同 root／child material 讀取時拒絕，原 checkpoint／內容不動；合法 terminal AI 後的人工 pending 保持可恢復。

| 實際驗證 | 結果與證據層級 |
|---|---|
| 修改後整個隔離 Python 組 | [1830 PASS／197 opt-in PG SKIP／1 warning](evidence/jd-relational-ai-restart/full-tests.txt)，27.82 秒。此組在 AR-R01 最後修正前；不能改稱最終完整重跑。 |
| AR-R01 修正後相關組 | [293 PASS／1 warning](evidence/jd-relational-ai-restart/focused-final-tests.txt)，5.23 秒。含真 native Agent／Saver／Future，OS／SQL 依各檔明示使用合成埠。 |
| 既有 AI／人工宿主真 PG 回歸 | [8 PASS](evidence/jd-relational-ai-restart/regression-postgres-tests.txt)，33.71 秒；其中4個本程序 AI 固定 SDK、4個原人工新宿主案例。 |
| 新 AI 真宿主／PG 四組 | [最終4 PASS](evidence/jd-relational-ai-restart/host-final-tests.txt)，52.89 秒；真正 open_manual_host／HostLease／PG Saver。原 host 合计12次 SDK 請求全部 MockTransport；接替 host 的 model／tool／execute／setup 計數全部0。 |
| 相容檢視與 discovery 獨審 | [獨立報告](evidence/jd-relational-ai-restart/checkpoint-independent-review.md)：82項離線檢查及 AR-R01 修正後2個窄案例分次通過，AR-R01 CLOSED。 |
| owner／AI／managed 接合獨審 | [獨立報告](evidence/jd-relational-ai-restart/runtime-independent-review.md)：39項離線檢查通過，無剩餘此範圍 P1／P2；審查者各自不把自己實作列作獨立證據。 |

warning 是 Starlette TestClient 使用 AnyIO 已棄用 alias 的上游提示；本次未改版本。沒有 Web／生成契約變更，不重跑無關前端 build。原碼／測試／必要文件的空白與本地連結另核。

新宿主四組分別證明：正常 AI 結束後全部原資料／位置只讀不變；真 SQL 候選在 transaction 內存在但未提交，活 host 擋住競爭者後真正退出，再查原結果；A 已保存且 B 真 COMMIT 後回覆遺失，兩份原回執保持精確不變；after_model binding 已保存但 SQL 尚未執行，與另一文件 START input 尚未進模型的兩個回合同時恢復。最後一案保留先前完整問答與新原話，沒有假造操作。

第一輪宿主驗收為[3 PASS／FH04 觀測失敗](evidence/jd-relational-ai-restart/host-first-tests.txt)：測試把未固定 latest 的 next 當作原始 START 證據，受到 pending overlay 影響。改用 observed.root_config 固定讀取，另核 source=input 與原 get_tuple 的 checkpoint ID；[FH04 窄跑](evidence/jd-relational-ai-restart/host-fh04-corrected-tests.txt)及最終四組都通過。產品 recovery 本身原已使用固定位置，本項修正只改驗收 oracle；首敗未覆寫。

專用 `jd_ai_host_test` 四張 Saver 表由主代理在測試前一次明示初始化，核 PG18.6、測試 DB／user、migration0–9；測試與一般啟動禁止 setup，沒有 DROP／清資料／CREATE DATABASE。[結果摘要](evidence/jd-relational-ai-restart/host-result-summary.json)保留實際新舊 PID、文件／revision／receipt 結果、原始合成紀錄路徑與 hash。FH02 沒有另外製造存活子程序，不冒稱本次重驗強制終止活子群；原 Job 原語仍見先前宿主結果。

下一個相依單位是聊天契約實作。已有前置指出兩個必要缺口：原生舊回合定位，以及員工保存後預期 JD 版本的原子准入。兩者須在接 HTTP 前閉合；本次不偷改 run format1 的語意、不增加第二份對話權威。自然模型、完整 Memory／source 接合及成品驗收維持未完成。

提交的兩份失敗輸出僅去除行尾空白；原始輸出保留在 `.research-tmp/jd-ai-host-first-tests.txt` 與 `.research-tmp/jd-ai-restart-r01-reproduced.txt`。最後調正合成回執的 origin 後，恢復案例另窄跑10 PASS，產品程式未再變更。
