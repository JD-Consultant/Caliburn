# JD 人工變更通知與模型回覆保存：RS-4 第一段

日期：2026-09-13。範圍：JD-R002／`experiments/jd-relational-app`，隔離施工；本稿記錄本次接點與驗收。完整 AI 回合、Memory／來源採用、聊天 API 及自然訪談尚未完成；不變更 ADR0060 production authority。

## 1. 本次實際效果

App 從同一版 JD 歷史取得人工／AI 修改事件，在實際模型請求中提供數量、類型與可查回的引用。通知不冒充員工原話，不改 Memory，也不把「收到通知」當成讀完或理解 JD。模型完成一次回覆後，原生 Agent 將完整 `AIMessage` 與該次通知邊界一起交给 checkpoint 保存。

本次只完成可接合的顧問節點與其保存證据。正式入口尚未開放 AI；固定回應、真 SDK、真資料庫與真模型品質分開記錄。

## 2. 官方依據、版本與本案映射

延續[前置研究](evidence/2026-09-13-jd-consultant-context-preflight.md)，不是重新選擇所有框架。以下資料查閱日期皆為 2026-09-13。

| 官方事實 | 本案採用與限制 |
|---|---|
| [AWS hexagonal architecture](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/hexagonal-architecture.html)支持多種輸入共用 domain，隔離 UI、DB 與外部服務；也提醒額外分層有維護成本。 | JD domain／共同保存不放模型角色、stream 或 UI 邏輯；本次新增有限模型及歷史投影接點。AWS 沒有指定本案表數、notice schema 或框架，沒有新增通用 Agent／repository 引擎。 |
| [OpenAI conversation state](https://developers.openai.com/api/docs/guides/conversation-state#manually-manage-conversation-state)要求自行管理時保留適用完整輸出；[streaming](https://developers.openai.com/api/docs/guides/streaming-responses)有完成與錯誤事件。 | 回覆保留原生內容、工具、thinking、metadata／usage，不只存文字；此處採 Anthropic adapter，不宣稱已實作 OpenAI runtime。 |
| [Anthropic streaming](https://platform.claude.com/docs/en/build-with-claude/streaming)以 `message_stop` 結束，串流內仍可能 error；[Messages API](https://platform.claude.com/docs/en/api/http/messages/create)提供 top-level system。 | 必須看到原始終端事件且合法完成回覆。所選 adapter 不支援 non-consecutive system；使用 top-level 原生 system blocks，可能降低 prompt cache 命中，不改寫其角色 mapper。 |
| [LangChain context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)區分 transient input 與 persistent state；[custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)支援 `ExtendedModelResponse`＋`Command`。 | `request.override(system_message=...)`只投影當次輸入；模型節點透過原生 middleware 同步傳遞回覆與 `jd_model_view`，不寫假 HumanMessage／ToolMessage。 |
| [LangGraph 子圖](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)與[checkpoint](https://docs.langchain.com/oss/python/langgraph/checkpointers)有明確 state／保存／replay 契約。 | root 與 child 都宣告 `jd_model_view`；最新 state 只用來定位，再以固定 checkpoint 讀取並核對完整回覆、通知及 graph 已結束。查回不 invoke／resume，不據此授予 writer。 |

跨來源共同原則是輸入／執行／保存責任明確、完整結果與可查回狀態。以下 notice 格式、digest、run 綁定及停止條件是本案的有限實作，不能稱作大廠共同指定的 schema。

**精確依賴：**新增 `langchain==1.4.0`／`langchain-anthropic==1.7.2`，皆為當日官方非預覽、未撤回的 MIT 套件；官方 wheel SHA、METADATA 相容範圍與發布日期在[版本附件](evidence/jd-relational-context/adapter-versions.json)。安裝只增加兩套件，既有 `langchain-core 1.6.3`、`langgraph 1.2.11`、checkpoint `4.2.0`、PG Saver `3.1.2`、Anthropic `1.5.0` 及 Python `3.12.13` 不升級。服務文件是商業 API 契約，與套件免費開源授權分開。

## 3. 正常流程與責任

1. 後續 AI runtime 先在 graph 調用前驗文件、取得同文件前景執行權及固定 run；本次沒有代替此 admission。App 取得原 `ModelView` 基準 B 與回合起點通知。
2. `NoticeHistoryReader` 在既有短 `READ ONLY REPEATABLE READ` 內取得 H、B、完整區間事件數及最多指定數量的事件。A→B→A 是兩次修改；`no_change`／失敗沒有新增 revision。只讀現有關聯歷史，不讀所有 snapshot，不新增資料表。
3. `JdNoticeMiddleware` 以原生 runnable config 再驗 thread/document 一致，再讀最新材料。初始人工事件窗口保留整輪；每次工具往返後另加前次模型回覆至目前 H 的事件窗口。
4. system 通知只有可信種類、計數及 App 簽發引用，沒有員工／任務任意文字；`content_included=false`、省略數與原 H 的 history anchor 明示需再讀。通知上限 64 KiB、每窗口最多 20 事件；不是整體模型 context 預算。
5. 原生 provider adapter 處理真正的工具／文字／thinking／用量。單一回覆的工具平行要求關閉；SDK／模型自動重試及 LangChain 回覆 cache 關閉。完整工具回覆 `tool_use` 也能形成一次通知綁定，仍須後續真正執行工具。
6. `ExtendedModelResponse` 隨該模型步驟保存完整回覆與通知：document／dataset／run、revision、response id／digest、原 notice／digest。這些全由 App 提供，LLM 不填版本、身分或保存欄位。
7. 外部收尾只接受固定 root checkpoint 中的成對結果與空 next／tasks／interrupts。最新 `get_state` 可能覆疊 pending writes，不能單看其 values 宣稱已保存或完成。JD SQL 與 Saver 仍是不同交易，沒有跨兩者原子性宣稱。

程式落點：[context](../../experiments/jd-relational-app/src/jd_relational/consultant_context.py)、[history](../../experiments/jd-relational-app/src/jd_relational/notice_history.py)、[model](../../experiments/jd-relational-app/src/jd_relational/consultant_model.py)、[root state](../../experiments/jd-relational-app/src/jd_relational/runtime_checkpoints.py)。

## 4. 已發現失敗與有限修正

| 反例 | 處理與保證界線 |
|---|---|
| 原 SDK／adapter 在少了 `message_stop` 時仍可能回結果，甚至已有 `stop_reason`／`chunk_position=last`。 | 保留原生 SSE parser／mapper，只在 raw event hook 記錄 terminal；正常 EOF 缺 terminal 失敗，不更新通知邊界。不能只看最後文字。 |
| 關閉 adapter iterator 不一定關閉原 HTTP response。初版兩個 early-close 測試失敗。 | `_create/_acreate`旁存原 response；每次 `_stream/_astream` 的 `finally` 明示 close／aclose。原 SDK error／取消保留，secondary cleanup failure 只加固定安全 note；單獨清理失敗不能算完整成功。 |
| 獨立審查 CC-R01／P2：同 thread／同 async task 交錯兩條 iterator，跨 yield 的 ContextVar 會將完整 A 的 terminal 記給不完整 B。兩反例先紅。 | 每次原生 next／anext 只在執行期間設定自身 context，yield 前還原；關閉時亦使用自家 context。新增兩反例通過，獨立窄複核 9 PASS，CC-R01 CLOSED。 |
| root 未宣告 child 的自訂欄位會遺失通知；latest 可能顯示尚未完成的 pending 結果。 | 共同 state＋固定 checkpoint 核对。保存前失敗維持未確認；保存後 ACK 遺失只讀查回原結果，不重叫模型。[四案例原生探針](evidence/jd-relational-context/graph_checkpoint_closure_probe.py)／[結果](evidence/jd-relational-context/graph_checkpoint_closure_probe.stdout.txt)。 |
| graph thread 與 context document 不同仍可進模型。新增同步／非同步反例均先失敗。 | middleware 使用已安裝 LangGraph `config.get_config()`原生接點，在讀歷史／呼叫模型前拒絕。graph invocation 前的人類訊息 scope 保護仍由後續 runtime admission 負責。 |

stream guard 使用所選版本三組 private seams：`_stream/_astream`、`_create/_acreate`、`_make_message_chunk_from_anthropic_event`。它們不是穩定公開擴充契約；升級必重驗，不能假設新版保持此形狀。這是已觀察缺口的有界接合，沒有另寫模型工具迴圈、重試器或 SSE parser。替代方案是改走 SDK 直連並重做 Agent 接點，或放棄完整串流保證；目前保留已驗的原生 Agent、限定補終端與清理。API 本身支援某能力也不代表所選 adapter 全數支援。

每次 stream 的狀態彼此獨立，只在推進／關閉原生 iterator 時短暫放入 ContextVar，不跨 yield 保持；取消須由實際 run owner 等待退出。直接原生 iterator close／aclose 與 public ainvoke 取消有測試，沒有宣稱任意上層消費者丟棄 public generator 都能立即清理。

## 5. 驗收紀錄

主代理最終受影響組 **74 PASS**：context 17、model 30、notice 25（其中 11 真 PG）、native Agent／PG Saver 接合 2 真 PG。固定 SSE 全部在 `httpx2.MockTransport` 程序內攔截，沒有 provider／真訪談資料；PG 只用已明示初始化的 localhost:55436 專用合成 DB。沒有付款模型呼叫。

| 驗證 | 實際結果與限制 |
|---|---|
| [模型與通知](../../experiments/jd-relational-app/tests/test_consultant_context.py)／[串流](../../experiments/jd-relational-app/tests/test_consultant_model.py) | 同步／非同步、thread 不符、完整工具往返與 thinking signature、usage、tool pairing、原話保持、一次回合兩次通知、缺 terminal、cancel／cleanup、交錯隔離；固定模型／SSE，不是真自然顧問。 |
| [同版事件](../../experiments/jd-relational-app/tests/test_notice_history.py) | A→B→A、不變／失敗排除、H 以後提交不混入、有界事件與省略計數、原歷史可查、基準／producer／receipt 不一致拒絕；真 PostgreSQL 18.6。 |
| [真 SDK＋Agent＋PG](../../experiments/jd-relational-app/tests/test_consultant_context_postgres.py) | 兩輪人工 A→模型 H2；人工 B→A＋no_change→模型 H4，通知為 2 事件；所有持久 root 的 view 均配對完整 AIMessage。另驗第二輪缺 terminal 保留 H1 與原話；關連線／新 Saver、graph 只讀重開均不發新 HTTP。合計 4 次固定 SDK 請求、0 provider。人工 fixture 的 FakeAuthority 不證明 AI writer／host admission。 |
| root／人工流程回歸 | `notice_history`、`manual_runtime_postgres`、`runtime_checkpoints` 合組 88 PASS，含 8 項人工 native PG 接合與 11 項 notice PG。此組與上述 74 有重疊，不加總為獨立案例數。 |
| Python 全組 | 首跑 1593 PASS／193 PG SKIP／31 setup ERROR；31 全因 Windows pytest 暫存目錄 ACL，尚未進測試。全新專案暫存目錄仍遇 sandbox 權限，沙箱外全新合成目錄僅補跑該檔，31 PASS。合計 1624 非 PG 案例通過，**不是一次全組零錯輸出**；193 個 opt-in 未全跑，僅受影響 PG 組按上列實測。 |
| 契約／依賴 | Python／TypeScript codegen check PASS；lock 只新增兩套件，不改其他版本。未改 Web，未重跑無關 UI／build。 |
| 獨立審查 | 一項 P2 CC-R01 已修並 9 案窄複核通過，其餘 context/history/root 無未解 P1／P2。審查者未跑 PG；真 PG 結果由主代理及指定實作者另外驗證。 |

首敗保留：新模組未建立的 collection error；thread mismatch 兩案先紅；early-close 兩案先紅；CC-R01 兩案先紅。PG 接合首次兩敗是測試誤用 `codec.read` 及過窄 exception regex，改用正式 `resolve`／固定 error code 後通過，未放寬產品行為。驗收摘要見[結果記錄](evidence/jd-relational-context/validation.txt)。

重現：在隔離 App 使用已鎖定 uv runtime，`pytest -q -p no:cacheprovider`；若 Windows temp 權限不符，指定**尚不存在且位於專案內**的 `--basetemp`，不要指定有資料的目錄。PG 另明示 `JD_RELATIONAL_TEST_DB=1`，執行上述四個新測試檔；不自動 setup／drop／清除合成資料。

## 6. 下一工作與未完成界線

下一單位接前景 AI run 的 admission、取消／退出／重開收尾及 JD 工具實際執行，把已驗共同業務保存接進原生 Agent。先固定回應完成初稿→手改→AI續改→純訪談不改；來源 handle／Memory 採用及聊天 HTTP／Web 隨相依接合，不用假來源或 placeholder 冒充完成。

原 notice counts／refs 不代表模型能自然正確用工具；完整 context 預算、晚期問答未進 Memory、壓縮後回查、反覆更正、整輪只撤回 JD、自然職位品質均仍待原計畫驗收。Excel 延後有效。沒有需要重新確認的產品選項，不因本切片重開已收斂的品牌研究。
