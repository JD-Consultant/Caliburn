# RS-4：聊天 HTTP 前置契約與業務責任

查閱：2026-09-13。程式基準：`3980689a`，`experiments/jd-relational-app`。本稿為有界工程前置，**只新增此文件，沒有新增 schema、API、資料表、模型呼叫或執行測試**。主代理同時處理 foreign-host AI startup；本稿不把尚在施工的恢復能力當成已完成。

結論：先接「原請求送出／查回、真回合狀態、已保存對話、明示停止與恢復」的共同 App 服務，再接同頁聊天與即時預覽。沿原生 Saver、現有 JD receipts 及同文件 owner，不增設 run 表、持久事件佇列或第二份聊天權威。HTTP 斷線不取消 writer；run failed 也不表示本輪 JD 沒有保存。

## 1. 有效需求與不可混淆的效果

需求沿[自動保存與 AI 交接](../../2026-09-12-jd-autosave-and-handoff-design.md#4-與-ai匯出及離開操作交接)、[歷史與恢復](../../2026-09-12-jd-history-and-recovery-design.md)、[整輪 JD 撤回](../../2026-09-12-jd-ai-turn-undo-design.md)、[改動呈現](../../2026-09-12-jd-change-visibility-design.md)及[最新 RS-4 結果](../../2026-09-13-jd-ai-runtime-and-tools-slice.md)。較早文件的實作狀態、舊路徑及舊 PG 版本不是本輪採用依據；只承接仍有效的產品語意。

| 使用者要得到的效果 | App 必須保證 |
|---|---|
| 同頁訪談、AI 適時改稿，不必逐次接受 | 使用唯一 JD；本輪純訪談可以零修改。聊天完成不等於專業 JD 已完整，也不自動產生 revision。 |
| 明示送出一次原話 | 同一 `run_id` 對應同一原請求與原 HumanMessage；網路重試／查回不能新增第二段相同訪談。修正原話以後續新訊息表達。 |
| 手改完成後 AI 知道最新版 | 組字結束、有效 JD 候選已確認保存，才以 App 已讀的版次准入；同文件 server gate 再核。人工 notice 是 App context，不能改寫成員工原話。 |
| 知道 AI 改了什麼 | 依該 run 的真 committed receipts 及 base/result 顯示保存與確切差異；模型說明只是說明，不能代替資料庫結果。 |
| 停止等待中的 AI | 要求同一個 run 合作停止；真 Future／SQL 與 checkpoint 尚未閉合時仍不可手改。已保存 JD、原話、完整已保存回覆保留。 |
| 撤回整輪 JD 改動 | 另一路具名人工業務；只在回合與操作閉合、完整連續鏈且沒有較晚 JD 變更時可執行。是新 JD 保存，不是 cancel、provider retry、刪聊天或倒退 Memory。 |
| 關頁後可續看 | 重開讀原結果及保存歷史，不重新啟動模型。未送出的草稿不因重開自動送出；已送但未知的原 request 不被草稿捨棄清掉。 |

沒有新增「員工專業核准」、「每次接受」、「清空原始訪談」、「重生同一回合」、「修改已保存 HumanMessage」的功能。真人顧問交付／Excel 仍延後。

## 2. 官方事實及本案映射

以下皆於查閱日開啟官方正文，停止同層品牌廣搜。**LLM 呼叫、工具結果、串流與續接以 OpenAI／Anthropic 為直接依據；AWS 只輔助業務身分及安全重試，HTTP 以 RFC 為準。**API／方法頁為現行文件，未標預覽者不額外稱 beta；文件是參考資料，不代表取得文件內容的 OSS 授權或採用商業服務。

| 官方來源、版本／狀態／授權 | 官方可證事實 | 本案映射與限制 |
|---|---|---|
| [AWS Builders’ Library：安全重試](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)，現行維護方法文，非新增套件 | caller 提供 request token；相同參數不能單獨代表相同意圖。保存原參數以拒絕同 token 改意圖；同請求可回語意等價結果，並需考慮晚到請求。 | browser 配 run ID 並保留原 request；原生 input 保存原 Human＋run descriptor，SQL 每次另沿既有 operation。**不聲稱整個跨多工具回合是一筆 ACID transaction**，不因此加 AWS queue／DynamoDB。 |
| [HTTP RFC 9110 §9.2、§15.3.3](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.3.3)，Internet Standard，IETF 文件授權 | GET 為安全讀取；202 只表示受理但尚未完成，回覆應指向狀態觀察。非冪等 method 不應無依據自動重試。 | start 的 202 不宣稱 Human／JD 已存；GET 不呼叫 start／recover。POST 重試僅沿已定原 request，不換 key 推測成功。 |
| [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html#section-3.1)，現行 Proposed Standard，取代 RFC7807，IETF 文件授權 | Problem status 應與 HTTP status 相同；detail 幫助使用者修正，不供 parser 或底層除錯。已有 domain result 不必被另一個 error 外殼取代。 | App 接受失敗用固定 Problem＋code／next_action；已知 run failed／JD committed 用正常狀態表示，不把它包成「整輪未保存」。不回 raw traceback、provider body 或原 kwargs。 |
| [OpenAI 串流](https://developers.openai.com/api/docs/guides/streaming-responses)、[Function calling](https://developers.openai.com/api/docs/guides/function-calling)，現行 Responses 契約，商業 API 參考 | 串流區分文字 delta、完整 response 及 error；App 執行 tool call，再以原 call ID 回結果。文字已開始輸出並非整個 response 已完成。 | provider terminal、native AIMessage 保存與 App run 閉合是三個層次。Web 不解析工具參數、執行 DB 或把文字 delta 當保存回執；不能把單次 response.completed 等同整輪多模型呼叫結束。 |
| [Anthropic 串流](https://platform.claude.com/docs/en/build-with-claude/streaming)、[工具結果](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)，現行 Messages 契約，商業 API 參考 | 串流最後有 message_stop，中途可能發 error；tool_result 配原 tool_use_id 並緊接原工具呼叫。provider 的 user-role tool result 不等於真人說話。 | 沿已驗 `ConfirmedChatAnthropic` terminal guard 與 native ToolMessage 配對。HTTP 中斷不拼出假的完整 AIMessage，不把工具錯誤插入原 Human。 |
| [LangGraph Streaming](https://docs.langchain.com/oss/python/langgraph/streaming)，本案 pin 1.2.11，MIT | 原生 stream 模式區分 messages／updates 等資料，可包含 subgraph；模型 token 與 state update 用途不同。 | 目前 coordinator 是 invoke＋callback，尚無 browser 訂閱 port。後續以 native stream／callback 的有界投影接預覽，不自建 Agent loop、工具 mapper 或持久事件權威。 |
| [WHATWG SSE](https://html.spec.whatwg.org/multipage/server-sent-events.html)，現行 Living Standard | EventSource 會重新建立連線；event ID／Last-Event-ID 參與重連。 | 重連是重新觀察，不是重新 POST 模型。沒有可重播事件來源時不冒稱 Last-Event-ID 能找回所有 token；以原生保存 snapshot 恢復正確畫面。 |

現有 lock 實核：Python 3.12、LangChain 1.4.0、core 1.6.3、LangGraph 1.2.11、checkpoint 4.2.0、PostgresSaver 3.1.2、langchain-anthropic 1.7.2、Anthropic SDK 1.5.0；FastAPI 0.141.1、Starlette 1.6.0、Uvicorn 0.52.4、Pydantic 2.13.5。套件沿既有免費 OSS 採用與 pin，沒有升級；完整授權與 private adapter 限制沿[前次 context 結果](../../2026-09-13-jd-consultant-context-slice.md)。

共同原則是「原請求身分、執行者持有工作、依真結果確認、串流預覽與保存分開」。下列路由、欄位及分頁是本案工程選擇，**不是 AWS／兩家模型共同指定的 App 協定**。

### 兩家模型的取消、續接與查回不能互換

- **OpenAI 工具：**`function_call` 的 `call_id` 配 App 實際執行後的 `function_call_output`；不是 message ID 或 run ID。App 已知參數由 code 提供。續談的 stateless 路徑要保留完整 response output（含 reasoning items／phase），不能只保存 `output_text` 再當完整對話。[Function calling](https://developers.openai.com/api/docs/guides/function-calling)、[Conversation state](https://developers.openai.com/api/docs/guides/conversation-state#manually-manage-conversation-state)
- **OpenAI 查回／取消：**background response 可依原 response ID polling；重複取消回原 final response，串流可按 sequence cursor 查回。這有背景請求與保存條件；[官方限制](https://developers.openai.com/api/docs/guides/background#limits)另指出 synchronous response 的停止方式是結束連線，而重新開背景串流要求原請求 `stream=true`。它不是本案所有 provider 的共同 run API，也不能查回或撤銷本機 SQL。此處不採購／切換 background mode。[Background mode](https://developers.openai.com/api/docs/guides/background)
- **Anthropic 工具／對話：**原 assistant 的 `tool_use.id` 對應後續 `tool_result.tool_use_id`，工具結果的 user role 不當作真人 Human；Messages API 是 stateless，續談由 App 提供實際歷史。fine-grained 工具參數可能是不完整 JSON，不能執行半個工具。[Messages](https://platform.claude.com/docs/en/api/http/messages/create)、[Tool results](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)、[Fine-grained streaming](https://platform.claude.com/docs/en/agents-and-tools/tool-use/fine-grained-tool-streaming)
- **Anthropic 文字續接：**現行 streaming 指南區分 4.5 以前的 assistant prefill 與 4.6 以後使用新 user continuation request；tool-use／thinking 不能部分恢復。這是在請求新的模型輸出，**不是查回原請求結果**。本案因此不把「繼續原操作」實作成偷偷追加這段人工續寫提示或再次付費叫模型；若未來需要文字續寫，必須另定清楚的新回合語意。[Error recovery](https://platform.claude.com/docs/en/build-with-claude/streaming#error-recovery)

本輪核對的 Anthropic Messages 文件未提供足以替本機工具證明死亡、回滾或完成的通用取消收據；不從 SDK close 推論 SQL 已停。合作取消／真 Future 等待沿[已核原生 owner 證據](../jd-relational-ai-runtime/ownership-preflight.md)。**兩家均未規定本案 PostgreSQL 表、原生 Saver 分層、Windows host 結構或 run descriptor；這些由 App 的已定責任與平台實證推導。**

## 3. 基準程式已能證明什麼

| 現有接點 | 已有能力 | HTTP 前真正缺口 |
|---|---|---|
| [AiRuntime](../../../../experiments/jd-relational-app/src/jd_relational/ai_runtime.py)／AiRunHandle | 同 instance 同 run 同原話回原 handle；改原話拒絕。真正 Future 完成後自動一次閉合；wait 只觀察，recover 不重播模型。 | 無 public run lookup／history／訂閱服務；只保留每文件最後 live handle。較早 Human ID 仍在但 latest root 已屬新 run 時，observe 不能查回舊 run。**GET 不能包裝 start()**。 |
| [AiRunCheckpoints](../../../../experiments/jd-relational-app/src/jd_relational/ai_checkpoints.py) | 固定 root／child 觀察、原始 input、response-backed model view、停止後 exact closure。Human 原字串保留，128 KiB UTF-8 限制、非空非全白、無 NUL。 | 目前 observe 只接受最新 root 的該 run；需有界原 run 歷史 locator，讀 native 保存而不重建當時輸入。其 observer 不授予 writer／死亡證據。 |
| [ManualRuntime](../../../../experiments/jd-relational-app/src/jd_relational/manual_runtime.py) | 同文件 foreground／manual／catalog admission；單 owner 只准一個 coordinator；真取消與排空。 | 查回、取消、恢復要按精確 run 配原 handle／restart 結果，不能直接操作私有 `_latest`，也不能取消「現在最新」而忽略路由 run。 |
| [ManualService](../../../../experiments/jd-relational-app/src/jd_relational/manual_service.py) | 合法 write_state、receipt 原結果及未知分開；已存 JD 但 gate 未解除仍可表示。 | 聊天狀態重用此 write_state，另表示 AI run 與 Human 保存；不可借 manual operation_id 充当 run_id。 |
| [HistoryReader](../../../../experiments/jd-relational-app/src/jd_relational/storage/history.py) | 固定版本分頁及原 operation 的 exact base/result；receipt 已有 ai_run_id。 | 尚缺「該 run 全部 operations」的有限查詢／分頁，不能按時間或只倒掃最後幾筆。此資料源仍是 jd_operation，不增 producer-events 表。 |
| [configured API](../../../../experiments/jd-relational-app/src/jd_relational/configured_api.py)／[managed App](../../../../experiments/jd-relational-app/src/jd_relational/managed_app.py) | 同本機 Origin、unsafe method 的單一 X-JD-Dataset、body 限制、lifespan／host；目前 manual-only composition。 | managed services 尚未建同 owner 的 AiRuntime、chat service／routes；尚無正式模型設定接合。新增路由必須同樣受門閘及關閉排空管理，不能繞出另一 FastAPI App／owner。 |

有一項需在聊天施工前補齊：既定交接要求 flush 後核預期 JD 版；現 `start(document_id, run_id, text)` 沒有 expected revision 參數。模型開始時直接讀 current，不能代替對員工已確認版的 admission 檢查。

## 4. 最小請求及 idempotency 決定

建議新增的 `ChatStartInput` 僅三欄：`run_id`、`text`、`expected_jd_revision_ref`。dataset 由既有 `X-JD-Dataset` 提供，document 在 route；body 不重複 document／dataset，所有回覆仍帶明確 scope 供前端核對。run ID 是 browser App 在明示送出時配發的 canonical UUID；沿既有 HumanMessage ID。opaque revision ref 使用既有 codec／上限，模型不填它。

- request body 沿 1 MiB 上限、重複 JSON keys／非有限數值拒絕；text 再核既有 128 KiB UTF-8 不變量。可驗「非空」但不 trim、改換行或正規化原話。文字及 prompts 不放 URL。
- 固定送出記錄先存入既有 IndexedDB，再送 HTTP。scope=`apiOrigin＋dataset＋document`；完整保存原三欄、送出記錄世代及草稿序號。只用原 run 查回，不把 request_id 診斷 UUID、provider response ID 或 tool call ID 當 run ID。
- 同 run 原 request 查回優先；已受理的原回合不因目前 JD head 前進而重做／報成新 stale。same run 改 text 或 canonical expected revision 需拒絕；只換同版 token 的簽章外殼不應被誤當新內容。
- 新 run 才在同文件 owner slot 內核預期 revision，且在保留 slot 至真正 foreground 准入間沒有另一 writer 空窗。先讀 current 再離開 gate 後 start 不符合此條；不跨模型持 SQL transaction。
- 建議 successor run descriptor 保存 **canonical start revision identity**，request digest 包含此 admission 意圖；這是原 run 的小型 metadata，不是另一份 JD。現 format1 digest 只含 dataset／document／text，不能在 HTTP 裡默默假裝已核整個新 request。具體格式版本／既有合成 checkpoint 相容拒絕需隨 schema 小切片完成，本稿未改檔。
- unknown／not_found 不自動重播；明示重試原送出只能使用完整同 request。已確知原 input 沒保存時可保留草稿供再次送出；後續修正文字或改版是新意圖。server 仍逐次檢查 scope／原身分，browser 判斷不授權 writer。

`run_id` 是一次使用者送出的工作單位，不是整份訪談 session，也不是一次 provider 呼叫。相同文字的兩次刻意補充可以有不同 run ID；一輪可包含多次模型／工具呼叫。

## 5. 最小 HTTP 面與狀態表示

下列為可施工路由方向，生成前由此決定導出 SSOT；不先手寫跨語言 DTO。

| 路由 | 行為與 HTTP 結果 |
|---|---|
| `POST /api/documents/{document_id}/chat/runs` | 固定原 request → 共用 start。未閉合回 202＋Location 指向原 run；已查得原 terminal 回 200。202 只表示已受理，不是保存成功。 |
| `GET /api/documents/{document_id}/chat/runs/{run_id}` | **純觀察** live 狀態或 native 原 run；200 回具名 found／not_found 分支。absence 不代表原請求沒有在途。找不到 document 才 404，查詢來源故障為 503。 |
| `POST /api/documents/{document_id}/chat/runs/{run_id}/cancel` | 精確原 run 的 stop request，202 回尚未閉合狀態；原 terminal 為 200 no-op。不能設 latest run 的 Event，也不刪已存 Human。 |
| `POST /api/documents/{document_id}/chat/runs/{run_id}/recover` | 顯式原 run 對帳／閉合。無模型或 command replay；本程序原 handle 與 foreign-host 恢復依各自已證條件處理。仍在處理回 202；confirmed terminal 回 200；無合法恢復證據回固定 409／503。 |
| `GET /api/documents/{document_id}/chat/history?cursor=...` | 固定原生保存上界的對話分頁，不是歷史 checkpoints 的逐頁原樣展示；每個已存 message 顯示一次。 |

查詢、cancel／recover 的原 run 身分與 dataset 都不能由可變頁面 selected 值代替。unsafe routes 沿既有 Origin／X-JD-Dataset；讀取 DTO 回 dataset，前端與當前資料集比較。body／metadata 失敗可用既有安全 Problem 外形，最低 codes 為 invalid_input、document_missing、dataset_changed、stale_view、run_conflict、busy、recovery_required、service_unavailable、origin_not_allowed；具體 next_action 為 correct_input、reread、lookup_run、wait、recover、stop，不以 detail 文字控制分支。code 與 route 的 status 映射需在 SSOT 實作時固定。

不要一個 `success: bool` 表示所有事情。snapshot 最少須分開三組事實，並以合法 union 限制矛盾，不交叉任填旗標：

1. **原回合觀察**：not_found、active、closing、recovery_required、terminal。active 的 running 由真 owner；closing 包含 Future 已停但持久收尾未完成。stop_requested 若沒有本宿主可證紀錄就保持未知，不宣稱重開後還保留原 Event。
2. **原話／回覆**：input 為 saved、not_saved、unconfirmed；只有已知本地原 attempt 的停止／exact-before-state 證據可回 not_saved。terminal 使用既有 completed／cancelled／failed 及 nullable response_message_id。已保存的完整回覆可以存在於 failed 回合；不把前一輪回覆當本輪結果。
3. **JD 與可否編輯**：重用 generated ManualDocumentState；另提供該 run 的已確認 operation／change refs，及此清單是否已完整確認。空清單不推定「絕無改動」；不能從 run status 猜 receipt。當前 view 的 revision 與原 run 的 result revision 分開，較晚內容不被覆回舊版。

例如：`terminal failed＋input saved＋一筆 committed receipt` 應呈現「訪談已保留；AI 回覆未完成，這輪已有 1 次修改保存」，並可查看該次 exact diff。`recovery_required＋已知一筆 committed＋另一筆未知` 仍可查看已存修改，但不得宣告全部保存／全部撤銷或恢復手改。`terminal failed＋input not_saved` 保留 browser 原話草稿，不能在對話區標成已存。

HTTP 200 表示狀態查詢成功，不表示整輪任務成功；HTTP 5xx／broken connection 則不證明原 input 或 JD 沒有保存。所有回應與串流禁止 cache 實際私人訪談內容，沿本機既有安全 logging，不輸出原話到診斷。

## 6. 原始對話、歷史及 JD 撤回的單一權威

新增有界 `ChatHistoryReader`／run locator，沿原生 graph 的固定 root checkpoint／Saver 讀取，不新增聊天表。原 run 可由 native root history 找到該 run 最後可驗的閉合／待恢復狀態；選定 root 後才用同一固定位置驗其 Human／record／child。分頁達界仍未找到要明說需續讀，不回「永不存在」，也不借目前 graph input 重造舊 run。native get_state_history 回的是各版本，不能把每個版本的完整 messages 串起來讓對話倍增。

給員工的 message projection 只呈現真正已保存 Human 及 assistant 公開文字；保留穩定 message ID／run 關係和確切順序。tool calls／ToolMessages／provider reasoning 仍在原 native 保存中供既定運作，不因 UI 不顯示就刪除，也不把它們變員工訊息。不從任意 provider JSON 字串化出聊天正文；没有可靠 message 時間時不捏造时间。

原 native messages 的完整性與 Web projection 分工：Web 不回傳整個 messages 陣列、修改已存訊息或自行做 tool/result 配對；HTTP 接受的是一次新 Human text。manual notice 仍由 request context 投影，JD 還原／撤回通知不倒退 model-view，也不連帶更改原話、Memory 或案例。

該 run 的 JD operations 由 `jd_operation.ai_run_id` 及原 receipt 查，非最新 `jd_ai_bindings` 暫態清單；提供相同 change-read refs 給既有 HistoryPanel。整輪撤回資格必須另核全部 committed parent 鏈、run 真閉合及當前 head identity；本次聊天接點只保留可查的 run 歸屬，不偷加 restore／undo 工具，也不以 `cancelled` 批量改寫原成功 receipts。

## 7. 串流接法的最小界線

**推薦分兩個可獨立驗收的工作包：**先上述持久控制／查詢與固定回應接合；再接原生 token 預覽。這是施工順序，並非把最終產品降為非串流。避免把開始模型與 SSE GET 綁成同一動作，讓重連／瀏覽器重試意外重開模型。

後續 live transport 可用單一只讀 `GET .../chat/runs/{run_id}/stream`：同一 owner 已在執行的原生 stream／callback 只投影公開文字 delta 與已保存 snapshot 提示。subscriber 不呼叫 graph.invoke，不接收 writer permit；unsubscribe 只停止觀看，不設 stop Event。慢讀者不得阻塞模型／SQL，有限 buffer 溢位時丟棄預覽、要求重讀已保存 snapshot，不持久保存第二套 tokens／producer events。

browser 的 delta 僅為暫時預覽，與已保存 message 用不同狀態呈現；重連清掉不可驗的預覽，按原 message ID 讀真正保存內容，再接仍存在的 live 段。沒有 durable replay 就不發明「從任意 event ID 重播」承諾；不因缺 token 向 provider 再送一次。provider message_stop／response.completed 還不是 App run terminal；原生 graph checkpoint 與 owner 收尾完成後的 status 才能解除手改。

目前尚無 subscriber port，不能直接把 invoke 的 result 改名叫 streaming；也不能公開 provider SSE 原包而洩出工具參數／thinking。這個 port 的 native version、disconnect／慢消費者及 callback 清理，需要有限合成測試後才接真正 UI。沒有採 WebSocket、新 broker 或專用 durable event 表的必要證據。

## 8. 精確下一個 App／UI 接點

| 工作包／程式位置 | 最少要補的責任與停止條件 |
|---|---|
| owner／AiRuntime 的公開 run port | `lookup_run`、精確 `cancel_run`、`recover_run`；原歷史查回、expected head 原子准入。保留唯一 coordinator；不得讓 HTTP 碰 `_latest`、自行 Future.cancel 或設定 closure 字串。foreign-host 先由主代理閉合。 |
| native history／operation 查詢 | 固定上界原 run 與對話分頁；同 run receipts／完整性狀態。只读短交易與 host 資源排空，不持 registry lock 做 I/O，不掃到中途就宣稱 not_found。 |
| chat schema／service／API | 沿契約策略生成 Python／TS，fixed safe DTO，不複製 ManualDocumentState／MutationResult。薄 route 只調 service，所有 sync I/O 走現有框架 worker seam，ASGI 生命周期排空後才關 Saver；不使用 request BackgroundTasks 當 Agent owner。 |
| [managed_app.py](../../../../experiments/jd-relational-app/src/jd_relational/managed_app.py) | 同 host／codec／actual consultant 建唯一 AiRuntime，services 注入一次。普通啟動不 setup；模型缺設定時清楚 unavailable，手動管理可用，不從任意 env 猜 key。 |
| [DocumentWorkspace.tsx](../../../../experiments/jd-relational-app/web/src/components/DocumentWorkspace.tsx) | 左側現為 placeholder，改為保存對話＋composer；右側仍唯一 JD。新 `prepareForAi` 交接呼叫現 JdSession.flush，確認 composition 結束、無 invalid/form/unknown、server gate 可用，再凍結 request；不能只看某次 flush resolve。 |
| [session.ts](../../../../experiments/jd-relational-app/web/src/lib/session.ts)／[drafts.ts](../../../../experiments/jd-relational-app/web/src/lib/drafts.ts) | 同文件 Web Lock 協調聊天送出與手改；原 chat submission 和晚輸入分開保留。收到 A 只清 A 的送出紀錄，不清晚輸入 B。StrictMode／切文件／重開不得再次 POST；dataset 不符保留材料但不套用。 |
| [api.ts](../../../../experiments/jd-relational-app/web/src/lib/api.ts)／HistoryPanel | decode 新 generated DTO、核 scope/run；GET 原結果有界刷新，POST 不無條件自動 retry。AI 完成／取消後重讀 current、write_state、run changes；不得直接把 AI 文字或舊 result snapshot 寫进編輯器。 |

送出交接需要一個明確的 JdSession 公開方法，因目前 session 只有 flush／refreshStatus 等操作，UI 不能自己重算 domain／保存不變量。畫面切換保留原 run，已持久確認的聊天可離開繼續執行；未知請求或未持久草稿則沿既定保護，不能靠 unmount 當取消。

## 9. 有限反例與進入施工的門檻

1. **雙擊與回覆遺失：**同原 request 一次 Human／一次 run；同 key 改 text／base 拒絕。start 回覆丟失後只查回，重開不自行呼叫 provider。
2. **晚到原請求：**T 已完成、U 又完成後重送 T；回 T 真結果或有界續查，不能以 latest-only not_found 重開 T。
3. **flush 到准入競爭：**手改確認 B，另一頁改到 C，再送以 B 為 precondition 的聊天；server 拒绝新准入，Human 未冒稱已存，文字仍在草稿。
4. **三層成功：**JD committed 後 provider／ToolMessage／closure 故障；run 可 failed 或 recovery_required，原 committed receipt 仍正確。反之 input 未存不能在歷史顯示已送成功。
5. **斷線與取消：**斷 SSE 只停止觀看；明示取消後尚有真 Future／SQL時仍鎖。取消與 run completion 交錯不得改另一 run 或把已完成誤標取消。
6. **初始／foreign-host：**已存 START、所有 put 失敗、native child 未解；只能依本地真正 attempt 或新宿主死亡證據／固定保存對帳。not_found／timeout／沒有本地 Future 均不能單獨證明未執行。
7. **歷史：**原 Human 空白／換行不變；tool result不變Human；分頁不重複／漏訊息，pending input 不能偽裝完整回覆，舊 revision 無法當 current refs 寫回。
8. **UI：**A 待確認時輸入 B、StrictMode 二次 mount、換文件、封存、dataset 變更；原 A 不重送、B 不清掉、晚回不污染新頁。IME 送出不截半字。
9. **可見改動：**純訪談零 revision；同 run 多次保存完整列出，失敗／no_change不假造 diff。undo 判斷不吃目前暫態 bindings，且永不改原 Human／Memory。
10. **邊界：**Origin／dataset 在 body／admission 前拒絕；重複 key、超額 UTF-8、錯 DTO、raw error 均有固定出口。read/stream shutdown 完成前不關資源；慢 subscriber 不阻塞其他文件。

目前沒有需要 Owner 重選的產品語意；主要選擇已有有效需求。剩下須由有限原碼／合成驗證閉合的是：start revision 的 successor metadata、歷史 locator／分頁、foreign-host 查回接點、同宿主資源排空及 native live observer。這些閉合後直接生成契約與施工，不重開框架品牌、資料表數或工具命名討論。
