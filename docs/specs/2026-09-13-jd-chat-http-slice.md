# JD 聊天控制、保存對話與原修改結果接合

日期：2026-09-13。Topic JD-R002／RS-4 局部；隔離施工基準 `2734b82b`。此單位已通過離線、真 PG 接合及獨立窄審；不代表完整 App 通過。零產品模型呼叫、沒有新增資料表或更改 production authority；ADR0075 仍 Proposed、正式 ADR0060 不變。

本單位讓同一個 App 接受原訪談請求、查看原回合狀態、取消／恢復並讀取已保存對話。JD 修改直接沿原共同業務保存；聊天 API 回傳真實修改結果，沒有逐次接受流程、另存一份聊天／JD 或新增 LLM 工作區。

## 1. 已確認需求與實作界線

依[施工計畫](../plans/2026-09-13-jd-relational-app-implementation.md)、[聊天業務前置](evidence/jd-relational-ai-restart/chat-contract-preflight.md)及[單一生成格式](evidence/jd-relational-chat-control/schema-preflight.md)施工。上一單位完成 V2 起始 JD 版次與原請求查回，本單位接公開契約及 HTTP；不是重新設計 JD 欄位或 Memory。

Owner 本輪再次提醒：需求不清楚，或缺依據的做法可能增加複雜度／做錯功能時，可以安全暫停該部分討論。此規則適用後續產品取捨，不能把必要可驗接點變成反覆要求 Owner 選底層欄位。眼前送出、看原話、看改動、取消及續看均已有需求；不新增配置平台、事件佇列或通用 Agent 管理器。

日常 CLI 仍傳相容的 inspection-only Agent；`open_managed_app(enable_chat=False)` 預設拒绝新 AI 請求，回明確 `ai_unavailable`，不先保存一輪再假裝 AI 已開始。原有對話、原回合及 JD 管理仍可使用。只有 trusted composition 明示開啟並注入實際顧問才准入新回合；此開關不是授權付費模型测试，也不是新的使用者權限系統。

## 2. 公開介面及責任

| 入口 | 實際行為 |
|---|---|
| `POST /api/documents/{document_id}/chat/runs` | 原 `run_id`／原話／已確認 JD ref；同請求查回優先，新請求再核起始 JD 版次及文件 owner。未閉合回 202＋原狀態 Location。 |
| `GET …/chat/runs/{run_id}` | 原 native run、原 SQL 回執及當前文件寫入狀態；不啟動、重試或修復模型。 |
| `POST …/chat/runs/{run_id}/cancel` | 只請求該本地回合合作停止；原輪已結束則無事可取消，不停止後來的另一輪。 |
| `POST …/chat/runs/{run_id}/recover` | 原執行真正停止後才核回執並收尾；仍活動時只回狀態，不重播模型、來源或命令。 |
| `GET …/chat/messages` | 固定 root／source 的原話及 AI 公開文字分頁；不暴露工具、thinking、signature 或原 provider payload。 |

Input／RunState／HistoryPage／Problem 來自 [JSON Schema](../../experiments/jd-relational-app/contracts/jd-chat-http.schema.json)，用既有標準工具生成 Python／TypeScript，結果與人工 write state 直接引用原契約。[契約結果](evidence/jd-relational-chat-http/schema-results.md)列版本、首敗與適用限制；不手改生成物或要求模型填 HTTP 身分。

`AiRuntime.inspect_run` 提供原回合事實；`ChatService` 接同一 `ManualService.status` 和結果投影；FastAPI 只做 route／輸入／固定錯誤出口。所有同步保存資料讀取納入同 owner 的關閉排空，實際 Future 仍由 App 持有；HTTP 等待者或斷線不取得 writer 生殺權。Origin、dataset 先於 body parsing，沿原 middleware、lifespan、threadpool、CORS 與安全診斷。保存或回覆遺失不能靠再送一次新 key 猜成功。

## 3. 三件事分開報告

1. **原話有沒有保存：**saved、只有本地原 attempt 才可證的 not_saved、或 unconfirmed。跨重啟查無紀錄只是不確定，不當成已證未存。
2. **AI 回合到哪裡：**running 只表示 actual Future 未完成；Future 完成但 callback／native closure 未結束是 closing，遇原收尾故障才需明示 recovery。completed 不表示這份 JD 專業上已完整。
3. **JD 真的改了什麼：**從 `jd_operation.ai_run_id` 的原回執配 native bindings，沿原結果投影，顯示原 operation／revision／change refs。AI 最後失敗仍可能已有 committed JD；純訪談可以零修改。

SQL 讀取在短 READ ONLY REPEATABLE READ 交易中查同文件／同 run 全集，[實測](evidence/jd-relational-chat-http/operation-results.md)包含交錯 COMMIT。原生 bindings 順序用於呈現；SQL 的 operation UUID 排序不冒充執行序。terminal 只有在原 record closed、無未配對工具、每筆回執與身分／內容一致、SQL operation 集合與 bindings 完全相等時才投影 settled。

活動 run 的原生快照與 SQL 可能在兩次讀取間前進，因此即使其中 A 已確定，整輪仍為 unconfirmed；空清單不說成「沒有改動」。讀 snapshot 後 owner 已放行的一個短競爭窗，用最多一次純重讀重新對齊；不修復、不造事件、不無限重試。terminal 的當前文件仍可被後來的另一輪或封存阻擋，兩者不混為同一狀態。

## 4. 固定歷史及官方依据

[歷史實證](evidence/jd-relational-chat-http/history-results.md)發現同一 root 的 child 可以繼續前進；只有固定 root 不足以保證翻頁一致。窄擴既有 `observe_at(source_config=…)`，原生固定 root/task namespace 及原 source checkpoint，省略參數的舊契約不變。續頁不讀 latest child 作替代，缺原位置則明確失敗。

公開文字使用 LangChain Core 1.6.3 的 `.text` property；完整 AIMessage 仍保存在原 Saver。ItsDangerous 2.2.0 使用同設定 key/dataset、獨立用途 salt，沒有新 key 檔或資料表。頁面最多 50 則／1 MiB，token 最多 4 KiB、run 結果最多 96；這些是本案界線，**不是大廠共同指定的數字或統一 schema**。超界明確失敗，不截斷後冒稱完整。

LLM 契約承接已核 [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling) 與 [Anthropic tool results](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)：App 承擔工具執行、身分与真實結果回傳；provider call ID、App run ID、SQL operation ID 各司其職。原生完整回覆／串流限制及現行版本見[官方前置](evidence/jd-relational-ai-restart/chat-contract-preflight.md#2-官方事實及本案映射)。

原 request 查回與固定意圖依 [AWS 安全重試](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)，202／GET 沿 [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.3.3)，錯誤沿 [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html)。本輪未升級原框架；具體 HTTP 分支、scope 與 UI 投影是本案有界映射，未聲稱知道 OpenAI／Anthropic 產品未公開的内部資料庫。

## 5. 驗證、審查及未完成

| 驗證 | 實际結果與界線 |
|---|---|
| 最後完整離線回歸 | **2211 PASS／209 SKIP／1 既有 Starlette AnyIO alias deprecation warning，41.84s**；PG 關閉。先前同輪全組2191 PASS／206 SKIP由此最終結果取代，不加總。Windows 已知暫存ACL問題使用全新專用basetemp，以正常權限執行，沒有刪既有資料。 |
| 聊天 HTTP／真 PG／原生 SDK | [三個情境分批通過](evidence/jd-relational-chat-http/http-results.md)：純訪談不增JD版、AI新增工作後人工改稿仍查回原結果、最後模型故障仍保留已提交JD。TestClient為ASGI接合，非socket／瀏覽器；模型請求由MockTransport攔截，0 provider。 |
| 原回合 SQL 讀取 | [37個新離線及5個真PG案例通過](evidence/jd-relational-chat-http/operation-results.md)；另既有history25例通過，範圍分開記，未假稱全PG回歸。 |
| 單一生成格式 | [最後chat91例、codegen check、全生成TS與consumer正反例通過](evidence/jd-relational-chat-http/schema-results.md)。ai_unavailable有獨立出口；沒有升級原套件或手改生成檔。 |
| 獨立審查 | [CH-R01／P2已修且窄複核關閉](evidence/jd-relational-chat-http/review-results.md)。另一組service／HTTP／scope／排空審查新增[13個反例](../../experiments/jd-relational-app/tests/test_chat_boundary_review.py)，包含原祖先查找缺口仍503、不新准入及查讀結束前不能close；未見新增P1/P2。這13例亦包含於最後完整離線數字。 |

首敗如實保留：新inspection port尚不存在時收集ImportError；新契約／SQL接點各自的先行反例詳子報告。主代理另先驗到兩個錯誤出口失配（缺文件與錯run字串被包為service_unavailable，**2 FAIL／3 PASS**），分開型別／HistoryError映射後相同反例通過，相關69例與最終全組均通過。真PG首敗是測試錯把「最新頁anchor」要求固定；人工保存本來會產生新root，修正為核消息不變、且舊cursor續頁仍固定，不放寬產品契約。沒有以刪除失敗紀錄或重跑到偶然成功代替修正。

仍待後續：同頁聊天 Web／送出草稿保護與原請求重開查回、自然顧問／Memory／來源接合、較深原 run 查找的後續出口、選取後 AI 修改、整份還原／整輪 JD 撤回、完整維護與成品驗收。既有原 run locator 超過 256 祖先或缺鏈仍明確失敗，不冒充不存在；本次聊天內容分頁不能被宣稱已解决那個原 run locator 限制。頁面雖有輸出界線，原 Saver 仍載入固定的完整 messages；長訪談／compaction 前須驗證，不先造另一份聊天儲存。

本次沒有新瀏覽器／自然模型／真人證據；不因 HTTP 或固定 SDK 通過就宣稱員工已能完成自然訪談。Excel 仍延後。
