# JD 跨輪人工變更通知：Task 3.3a 有限設計

2026-09-10；JD-R002/C03；**G4有限設計已通過獨立review並納回register／六切片**，見[審查證據](evidence/2026-09-10-jd-model-view-design-review.md)。本稿只閉合已批准人工變更感知的技術未知，不改production authority。§6.2的SSOT description在Task 3接線前更新及重生，Task 1當前驗收schema不在修正中途變動。

## 1. Preflight 與結論

- Topic ID：JD-R002/C03，核心 Task 3.3a。
- Current stage：成品總計畫隔離 G7；主線目前 Task 1，Task 2 在其 review 後接續。本稿是 Task 3 前置 G4。
- Binding decisions：持續同份 Plate v2 工作稿、同 PG 保存、三工具、人工保存後下一輪回應前主動通知、canonical 原話與 Memory 不受通知污染。ADR 0060 仍為 production authority；0073／0074 的 gate 不變。
- Only blocking question：如何明確且有界地比較已保存事件、證明供給模型的版本／範圍，並在重開、縮減及失敗時不假報「沒有改動／全部已讀」？
- Already reviewed evidence：[現行 register](../current-decisions.md)、[決策流程](../decision-process.md)、[核心 Task 3](../plans/2026-09-10-jd-editor-core-implementation.md#task-3同一既有顧問的三工具已發配-refs-與來源)、[主設計 §3.1](2026-09-09-jd-editor-app-integration-design.md#31-不每輪改稿的顧問接點)、[官方整合研究](2026-09-10-jd-context-change-and-source-research.md)、其 OpenAI／Anthropic 證據及 active v2 三工具 schema。
- Out of scope：Memory 設計或設定、通用同步／已讀追蹤服務、新 Agent、額外模型呼叫／token 預算、production、DB 新表、schema／plan／register 直接修改、自然模型驗收。

**推薦：以既有 JD revision 歷史作事件比較，以既有 LangGraph checkpoint 保存一筆有限的「最近成功返回之模型請求供給紀錄」，每次 model call 在 compaction 投影之後重新加入當輪 JD 狀態。**比較基準只代表上次請求提供的文件狀態版本，從不代表模型讀過該版全部內容。通知與工具結果的內容範圍另行標示。無法證明基準時，明示未知、提供目前內容及歷史回查入口。

三工具不新增名字或 ModelInput 分支。長事件串以既有 `jd_read` 的 `change_refs` 及 `jd_change_read` 的前版 reference 回查；需補既有結果欄位的最小語意保證，見 §6。本稿沒有改公開 wire。

## 2. 已核對的實際接點與證據效力

本節「現行 code」指隔離 checkout `S:/caliburn/.worktrees/analysis-only-agent/experiments/analysis-agent`，不是 production API。

| 接點／官方事實 | 實際限制與本案映射 |
|---|---|
| `src/analysis_agent/runtime.py: native_context_view` 用 `request.override(messages=server_compaction_view(...))`，位於 `build_agent` middleware 首位 | JD wrapper 放在其後、接收已投影 messages，才組 model-only context；不改原 messages state |
| `context.py: server_compaction_view` 自最後 inline compaction block 切出模型視圖，會裁掉前段工具便利欄位；canonical 不被裁 | 「checkpoint 裡有舊 ToolMessage」不等於此次 wire 有它；opaque compaction 不證明任何指定 JD 原文仍存在 |
| `conversation.py: ConversationState`／`TurnState`、直接 child subgraph；目前跨邊界只有共享的 messages／outcome／closed_turns | 僅增加 child middleware 欄位無法保證跨輪。有限 JD 供給欄位須在 root 與 child 共用並明確傳回；child 不再另掛 root saver |
| `live_memory.py` 的官方 middleware 示範每輪固定 view／`after_model` binding | 只借接點，不向 Memory guide 加 JD 通知、不修改 Memory fields／policy／版本 |
| 已安裝 `langchain/agents/middleware/types.py: ExtendedModelResponse`，及 `factory.py` 組合處理 | 官方允許 wrapper 回傳 `ExtendedModelResponse(model_response=..., command=Command(update=...))`；同 model node 完成時追加 state update。不可用 `goto/resume/graph`，不可將通知加到 command 的 messages |
| `service.py: CooperativeStop` 與 `conversation.py: close_turn` | after-model stop 可能早於其他 after-model hook；供給紀錄若只在晚期 hook 落盤會遺失。close 的 child→root 搬運也須包含已確認紀錄，不能用結束版本自行補造 |
| `budget.py: ResponsesBudget` 在最終 SDK request 執行現有 preflight；`truncation=disabled` | 通知必須被現有計數／容量檢查涵蓋。字元／byte 上限只是 App 呈現限制，不是模型 token 上限；不擴大既有 capacity、output、compaction 或模型／工具次数 |

供應商依據沿既有 [OpenAI](evidence/2026-09-10-jd-context-openai.md)／[Anthropic](evidence/2026-09-10-jd-context-anthropic.md) 的當日定點查核；本輪未重新廣搜，也沒有把公開測試碼當已執行測試。正式接點為 [LangChain context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering#messages)；`ExtendedModelResponse` 的可用性另由上述已安裝原碼核對。Codex experimental injection、Claude hook 的大小政策仍只作先例，不成為本案依賴或數值規範。

## 3. 三種基準不能混用

### 3.1 事件比較基準 B

`B` 是同文件最近一筆可證明「有模型回應、且供給紀錄與回應已保存」的請求所載 `current_revision`。`H` 是當次 request 送出前在 JD owner 讀到的 current head。比較範圍精確為祖先鏈 **(B, H]** 的 committed revisions；B 本身不包含，H 包含。

首次 model call 使用上次 run 的 B。當輪後續 model call 使用上一個成功返回請求所載 head 作 B，另保留本輪開始的 B0，持續呈現 **(B0, 本輪起始 H0] 的跨輪人工事件摘要**。因此第一個 request 看過通知、第二個 request 做純訪談或遇 compaction，不會失去本輪人工更動的提醒；該固定跨輪區間明標歷史，另有本次 current H。當輪 AI 新保存事件則由 (上一 request head, H] 顯示，不能把 H0 再稱 current。

只計 `committed` 的 revision 事件，按真 origin 區分 manual／ai／initial。沒有新 revision 的 `no_change` 是「保存完成但內容未變」，不冒充人工改動；失敗／dirty／unknown 不算新版。no_change receipt 仍按既有工具可查，不為通知另造 attempt log。

事件數與內容淨差異是兩回事：manual r2 改字、manual r3 改回，即使 B=r1 與 H=r3 全值相等，仍報兩次人工已保存變更；兩版比較是淨結果，逐事件差異才能看中途版本。只改 marks、順序、K／S links 或來源 metadata 也由新 revision 計入，不靠純文字 diff 或最後作者判斷。

若舊 checkpoint 缺 B 或其格式未留下可核對的祖先基準，`baseline=unknown`；不能改用 current、最後 `jd_read` 或最後工具回執補作 B。可讀取目前 head 且歷史可查時允許正常訪談，明示先前供給基準未知及 current 部分內容。若紀錄明確指到另一文件、聲稱存在的 revision 消失、或查得 B 並非 H 祖先，屬資料／scope 故障，不能降成合法 unknown 掩蓋。已知存在的 B／H／事件鏈讀取出現 DB 錯誤也屬故障，見 §7。B=H 僅可說「本明示區間無新增已保存事件」，不能說文件從未有人工修改。

### 3.2 當次供給範圍，不叫「已讀」

每筆有限 request manifest 區分下列資訊：

1. `current_revision`：只證明通知提供該版的狀態／reference。
2. `notice_scope`：通知實際附的 exact fragment／僅文字預覽／無正文；各自標 revision、fragment digest／可定位範圍與 complete／partial。不得把 preview 冒充完整 native JSON。
3. `visible_jd_results`：此 request 的 compaction 後 messages 中，真正存在的原 factory JD ToolMessage 對應工具結果 id。由既有 checkpointed issued-result binding 回查精確 revision、read_kind、range／頁面、continuation 與結果內容，不再複製另一份完整文件。
4. `context_cut`：本次原 messages 經 compaction 裁切的識別／有無；被裁掉的結果不計為 currently supplied。opaque summary 一律不證明任一 exact fragment。

這是最後一個請求的有限清單，不累積所有曾讀過之 blocks、不建立 read coverage union，不判「理解／同意／已核准」。清單上限取既有一次 run 的 tool-call 界線；歷史訊息超出摘要列表時標 `earlier_result_coverage=not_enumerated`，不能說不存在或完整已讀。manifest 可保存其餘可見結果訊息的有界索引／範圍而非正文，若上限不足就保守只宣告列出的精確供給，從不把截掉索引的內容標成已讀。

通知並不發 current targets。模型需要改稿仍呼叫 `jd_read({})`、取得 actual current-base refs；explicit revision 及通知 refs 全唯讀。`jd_edit` 成功只證明結果／actual_changes 所提供範圍，不能把新 revision 全文記成已供給。tool 執行成功但尚無下一次 request，不算模型已收到其結果。

### 3.3 成功返回與傳輸未知

`wrap_model_call` 準備 manifest，但只在 handler 返回有效 provider response（沿既有 `status=completed` 條件）、具有可對應的 AI message id 時，透過 `ExtendedModelResponse` 的 state-only `Command(update=...)` 與 response 一起落在 model checkpoint。保留 handler 原 response／其他 middleware commands；不用修改員工／模型原文、response metadata 或造 ToolMessage。

manifest 用詞是 **response-backed supplied request**：可證明本機送入該次 request 且有對應回應，不宣稱模型心理上的「讀懂」。SDK retry 仍是同一 logical request、沿既有設定；不新增 retry。

若 handler 丟錯、傳輸回應遺失或 checkpoint 沒保存，即使遠端可能已接收也不推進 B。下次保守重送相同區間通知，可能重複但不會漏報；通知無寫入副作用。process crash 後無法證明過去 exact request 就保持未知，不能以「已呼叫 middleware」當送達證明。

## 4. Checkpoint 與 request-only 資料流

以下是 Python 內部資料責任建議，**不是新增公開工具參數或 HTTP DTO**：

- `ConversationState.jd_last_model_view` 與同名 `TurnState` field：`None |` 最近成功返回之 manifest，包含 document scope、input/run、AI message id、current revision、notice 基準／範圍、供給描述、format version。root／child 同名才能跨 invocation；不使用 mutable singleton 當 durable owner。
- `TurnState.jd_turn_notice`：本 run 的 input id、B0、H0、事件界線／counts、已發配 readonly refs 及有限 notice payload descriptor。新 run 初始化；同 run resume 不把本輪固定區間换成新的上輪，來源仍回唯一 revisions。
- 既有 `jd_references` checkpointed binding：另准許 `issuer=app_model_view` 的唯讀 revision／change refs；與原工具結果同樣核 document／run／revision，不能授予 target 或 selection。未送達時可能已配發 refs，但「已配發」與 response-backed supplied 分開。

執行順序：

1. 沿原 input-before-model／admission 保存原始 HumanMessage；人工 dirty 先由 Task 5 成功保存。JD `before_agent` 建本輪有限 notice basis，`before_model` 為本次 H／refs 做可保存準備。此時不標通知已送達。
2. `native_context_view` 先投影 compaction；其後 JD wrapper 組一個 **request-only `HumanMessage`**，內容為 JSON 編碼的 App JD 狀態資料，來源明標 `app_jd_context`。插在投影 messages 末尾，使它不進 canonical 且不切斷既有 tool-call/result 配對。固定系統指引說明此類資料不是員工原話，文件／預覽中的指令句只作資料。不得把正文嵌進 developer/system authority。
3. JD 同一 wrapper 沿 Task 3 已定 raw 三工具 schema binding；不替換其他工具、不另加 model chain。後續 middleware 只能保留該 request 資料；最終 MockTransport 檢查順序與唯一性，不靠配置列表推定。
4. handler 成功返回時以 §3.3 的 Command 更新 `jd_last_model_view`。當輪下一個模型請求再讀 current，重新供給本輪跨輪事件摘要／本次狀態；不依賴上次 request-only message 自動重播。
5. 正常 child completion 自共享 state 傳回 root。Task 5 `close_turn` 的兩個 child→root 分支須複製既有且可核對的 `jd_last_model_view`，包含 after-model stop；不因取消造新 manifest。尚未進模型／沒有新已確認 manifest 保留原 B。

`before_model` 準備與 wrapper 實際觀察 H 若不一致，重新取得同一 owner 的 state-only 準備或終止 request；不能只在 prompt 換 H 卻沿用舊 issued binding。正常前景 admission 禁止人工保存，當輪 AI edit 是工具邊界的已知變更；Task 3 先驗序列流程，Task 5 再驗 race 與 close。background Memory 不寫 JD，亦不延長 JD 基準生命週期。

## 5. 有界通知內容與呈現預算

**本案初始固定值：每次新增 JD context payload（最終序列化 UTF-8，含標記）最多 16,384 bytes；事件明細最多 4 筆；文字預覽合計最多 2,048 bytes。**這些值不是 token 保證、不是供應商推薦，也不新增部署總預算。先用固定離線大型繁中 fixture 驗可讀及邊界；只有實測限制才調整並同步本稿／測試。資料 JSON 使用正規序列化，按 Unicode code point 截預覽，不切 UTF-8 bytes 或偷偷產生半個 JSON object。

必備 envelope 優先保留：

- 本次 H、B／unknown 及理由，所有 references 的唯讀性。
- 本輪固定跨輪 (B0,H0] 與此次 (B,H] 界線；各自人工／AI／initial committed counts，或 baseline_unknown 不提供推測 counts。
- 淨內容比較與逐事件歷史不同、不能由最新 origin 推論整份文件作者。
- 有哪些內容實際附上／省略，以及完整讀取入口。
- `manual` 不等於 verified fact、未看見／未列出的內容不能當不存在；需要續編先 current read。

事件明細取該區間最新 4 筆，**按保存順序呈現並標出其只涵蓋尾段**；counts 是整個區間的查核總數，若未列事件仍明示數目。每筆列 before／after refs、origin、change_ref；可可靠定位的 element IDs／標題只按保存資料顯示，任意人工 full-value 保存缺 affected IDs 就明示定位未知，不能補造語意摘要。計數／尾段由 JD owner 查現有 revision／operation，不新增 revision chain store。

正文分兩種：

1. 對已列事件，完整原生 before／after 結果（含 metadata／marks）整筆裝入剩餘預算才附上並標 exact。完整性以該工具結果的 continuation 與實際範圍判斷，不能見一頁就稱整份完整。若 exact event pair 太大，整筆不放，保留 change_ref。
2. 至少為 current 提供可辨識的文字預覽（未知基準也適用），明標 `text_only_preview`、只取目前文件開頭之有界文字，不聲稱保留表格／marks／metadata 或已提供完整任務。空白文件明確表示已保存空稿。若 current 全原生值很小，可用 exact current fragment 取代預覽；否則由 `jd_read({})` 取得 current。預覽不發可寫 targets。

短通知可以附精確前後；長通知一定保留歷史回查、明示未展開與下一個合法呼叫。不得移除必備 envelope 來硬塞內容。若連 envelope 都超限（例如異常 ref 長度），視為組裝失敗，不截 reference、不隱藏更新、不增加预算。

歷史事件很長時，模型可按 §6 分頁／回查，在原工具／模型限额內停止並據實表示未全部檢查；「可完整回查」不承諾所有歷史必在本輪讀完，也不每輪強制讀所有頁或修改 JD。

## 6. 三工具是否需要改 wire

### 6.1 推荐維持 existing defs

已核對 `JdReadModelInput` 允許 `{}`／一個 revision、target、selection 或 continuation；`JdChangeReadModelInput` 允許 change、兩版比較或 continuation；`JdEditModelInput` 只有 commands。它們足以接通知所發唯讀 refs。`JdReadSuccess.change_refs` 與 `JdChangeReadSuccess.before_revision_ref` 可串回真實事件，不必加第四工具、history cursor 或新的 ModelInput 模式。

**需要主線納回的既有欄位語意增補（shape 不變）：**

- `JdReadSuccess.change_refs`：current／explicit revision 的全文件讀取，包含「建立此返回 revision 的 committed change」reference；fresh initial 沒有可用建立 change 時為空。若其他既有用法亦返回更多 refs，建立事件須可可靠辨識，首版建議這兩種 read 僅返回該一筆。同一 revision 的各內容續頁回傳一致。target／selection 不因此承諾完整 revision 歷史。
- `JdChangeReadSuccess` 的 mode=change：actual committed 事件的 after 是所建立版、before 為直接父版，origin 是該次保存來源。no_change 則 before=after，不得混入 committed revision 建立事件鏈。
- history read 給出的 revision／change refs 仍 readonly，不能透過鏈取得 current targets；所有 references 必須經原 issuance／document scope 核對。

有限演算法：通知給 H 與 B 及尾段 refs；欲看漏列事件，可從最早已列事件的 before 版 R 呼叫 `jd_read({revision_ref:R})`，取得該版建立的 change_ref；`jd_change_read({change_ref})` 返回 exact 前後、origin 與下一個 before 版。直到 B（不讀 B 的建立事件）或 initial。每次完整 change 先沿該比較 continuation 讀完；不拿新 head 換後頁。大版的 history 首頁可直接給建立 change ref，不必先讀完整原文才導航；但只導航不表示已讀全文。

當 B 未知，從 H 可回查既有歷史到 initial，通知不冒稱此整串就是「上輪之後」。兩版比較仍由原 ModelInput `{before_revision_ref,after_revision_ref}` 提供，不拿淨比較取代事件串。

### 6.2 Exact defs 變更建議及 gate

**本方案新增／刪除公開 defs：無。**建議僅補 `JdReadSuccess.properties.change_refs.description` 及對應工具責任文件的上述語意，並讓 ModelInput description 由同一 SSOT 加入一句如何從已發配歷史 revision 查建立 change。description 修改也须按 Task 1／3 codegen、SSOT 閉包與最終 SDK request 全等檢查，不能在 wrapper 私寫第二份工具說明。

供納回的 exact description 文案（保留原 description 其餘內容）：

- `JdReadSuccess.properties.change_refs.description`：`For whole-document current/history reads, contains exactly the committed change that created revision_ref, or an empty array for an initial revision without a creating change. Content continuation pages retain the same reference. This is not a complete list of earlier changes; inspect that change and follow its before_revision_ref to walk older revisions. No-change receipts are not revision-creating changes.`
- `JdReadModelInput.description` 追加：`Whole-document current/history reads expose the change that created the returned revision. To inspect earlier saved events, use its issued change_ref with jd_change_read, then read the returned before_revision_ref; stop at the stated baseline. Reading navigation references alone does not read the document content.`

這兩處不改 `required`／`oneOf`／enum／reference shape；若 root 選擇保留 current/history 多個 change refs，就須先明定如何識別建立事件，再改此段候選，不能依 array 順序猜測未定義的語意。

內部 `jd_last_model_view`／`jd_turn_notice`／App context payload 用 Python typed runtime state 定義，不接受模型輸入、不進 HTTP DTO；其具體欄位是內部實作契約。若實作發現既有 JD owner 無法從 revision 唯讀取得建立事件，先在 Task 2 的既有 revision／operation 關係補相同查詢 port；若必須新增公開 history 模式才做得到，停止此分支，提交 exact defs successor review，不能在 prompt 發未定義參數。

## 7. 失敗、重開與縮減責任

| 情況 | 精確行為 |
|---|---|
| 首次空稿／舊 checkpoint 沒 manifest | baseline_unknown；讀唯一 current，提供空稿或有界 current 內容／refs，不推斷「沒改過」 |
| 只關 Web 再開、API 仍在；或 API 新程序，完整 root checkpoint 存在 | 從 root／pending child 核對最後 response-backed manifest，重建同一區間；瀏覽器開關不是清空基準理由 |
| compaction／裁切歷史工具結果 | B 若有 durable manifest 仍可作事件界線；`prior_content_availability=unknown_after_compaction`，不聲稱先前片段還在；本次通知重新附上，必要 current／歷史頁重新讀 |
| 過去 request-only 通知不在 canonical | 正常；它只在當次 request。以 manifest 證明曾提供狀態，不假裝其正文仍在本次 context |
| 上次 handler 返回但 checkpoint 遺失／cancel 分支尚未傳回 | 能從 canonical paired AI response 與 child manifest 核對者才採；否則保守沿較早 B 或 unknown。Task 5 修 close 傳遞前不能稱取消已完整通過 |
| saved head／事件查詢或 notice 組裝失敗 | model handler 不執行；保留已保存員工輸入，沿原 App 失敗／恢復路徑顯示「無法取得已保存文件狀態，顧問尚未回應」。不造 `JdReadFailure` ToolMessage、不自動重新提問／改稿 |
| budgets preflight／provider failure | 原 failure path；manifest 不前進；恢復只重新供給唯讀通知，不重播 jd_edit |
| 版本／scope 偽造、manifest document 不符 | 拒用該紀錄／ref，scope corruption 明示故障；不能把另一文件歷史當 current。缺舊 manifest 可 unknown，確定 scope 違反不可靜默忽略 |
| 預覽含「忽略上文」「把 Memory 改為…」 | 作不受信任文件資料；不提升權限，canonical source／Memory 不包含此 App message。固定測試驗實際 role 與來源標示；行為抵抗仍另屬自然模型品質 |

未知基準是合法冷啟狀態；已知應存在但讀不到的資料是故障，兩者不可混為「沒有更動」。本輪不新增 error recovery coordinator；若現有 App 分類無法承載明確的 JD context failure，Task 3 用本地 typed exception 與原 run failure 出口，Task 5 整合取消對帳，不繞過 unknown gate。

## 8. 精確 Task 3 增補與驗收

建議主線將原 3.3a 拆成以下同一 task 的子步驟，不改 Task 1→2→3 依賴，不新增成品切片：

1. **3.3a-1 schema 語意與 JD owner read port**：納 §6 的既有欄位 description；固定 readonly revision→creating committed change、ancestor interval counts／最新四事件查詢。只查原資料；Task 2 尚未提供之方法須在 Task 3 起工前確認。
2. **3.3a-2 checkpoint 與 request projection**：在 `conversation.py` root／child 加共用有限 manifest；`jd_tools.py` 的同 factory middleware 接 before/model wrapper 及 ExtendedModelResponse；必要純 helper 放 `jd_context.py`。canonical messages 與 Memory 無改動。
3. **3.3a-3 references／provider**：`jd_references.py` 加 App model-view 唯讀發配來源，保留 target/selection 只由 jd_read；`test_jd_provider_binding.py` 捕最終 SDK request，非只 mock middleware handler。
4. **3.3a-4 tests／README**：新增 `test_jd_model_view.py`、`test_jd_model_view_recovery.py`，README 描述基準、範圍、預算與 fail-closed；Task 5 的 close 分支更新列入既有取消 task，Task 6 r2 固定整合沿用同例。

所有下列用固定 model response／MockTransport、實際 graph／refs／PG（涉及重開）驗；不使用付費模型。不聲稱自然語意品質已驗。

| ID／指定負例 | 可觀察的 pass／fail |
|---|---|
| MV01 下一輪只訪談 | 前輪完成→manual committed→下一輪第一個 `/responses` request 在模型產生回應前含人工事件、確切前後 refs；固定純訪談回應無 jd_edit／新 revision |
| MV02 連續多次手改 | r1→manual r2→manual r3；界線 (r1,r3]，manual_count=2，各事件可查；不只報最後一版 |
| MV03 先改再改回 | r1 與 r3 exact 全值相等仍 manual_count=2；兩端 compare 空不覆蓋兩次事件的真前後內容 |
| MV04 AI 後再人工／人工後再 AI | 保存序列 origin 精確，最新 ai 不抹除較前 manual；notification 不稱任一 origin 擁有整份內容 |
| MV05 只有格式／來源／link 改動 | 真 revision 事件必通知；exact native 前後保留 marks／source refs／K/S links；text preview 不稱完整差異 |
| MV06 長文件／超過四次保存 | context ≤16,384 UTF-8 bytes，preview ≤2,048，最多四明細；總數／尾段界線／省略明確；沿 revision→creating change→before chain 收齊所有中間事件，途中 head 改變不換比較 |
| MV07 大單一 block／繁中與 emoji | 預覽不破 UTF-8／JSON，不造 range；exact fragment 不夠放則整筆省略、真內容仍能原工具分頁收齊；不以 byte 數冒稱 token 數 |
| MV08 局部 read／分頁／edit feedback | 只讀第一頁，manifest 不称整版已供給；拿 continuation 不算內容；edit 新版不等全文；tool result 尚未進下一次 request 不算 supplied |
| MV09 跨文件 | B、ref、event／manifest 來自另一文件均拒絕，不洩漏另一文件預覽；合法文件各自独立 |
| MV10 保存失敗／no_change／dirty | current 與 counts 不變；unknown receipt 不冒稱 committed；no_change 不增 revision／manual edit count，回查 no-change 仍空差異 |
| MV11 canonical／Memory | 員工 HumanMessage 的 content／id 全等；root、child canonical 與 ConversationReader 原始來源都無 App injection；extractor 輸入無假問答；Memory 設定／命名空間未改 |
| MV12 正常重開 | PG 完成一輪→終止 process→新 process→manual 保存→新輪；由 durable manifest 得同 B 並通知；不靠 service instance cache |
| MV13 舊 checkpoint／未確認傳輸 | 沒 manifest／provider 回應遺失／model checkpoint 未落盤；不得推進 B，不報無改；重新供 current 且 readonly 通知重送不新增 revision |
| MV14 compaction 同輪及跨輪 | 最終 wire 的 latest compaction item 後有當次通知；被裁原文不列現在已提供；本輪固定跨輪事件摘要仍可見，current H 隨 AI 保存更新 |
| MV15 通知組裝／讀庫／容量失敗 | handler invocation=0（本地故障／preflight），保存 input 仍存在；沒 notice 不能默認繼續；manifest 不更新，未造 ToolMessage；恢復不重播寫入 |
| MV16 references authority | 通知 refs 已發配且可 history read／change read；直接 jd_edit 不能拿通知當已讀 current，猜真 ID／history refs／跨版均拒絕 |
| MV17 request／checkpoint 同步 | 成功返回後 AI response 與 manifest 在同一次 model checkpoint；wrapper 返回後 before after-model stop 的 snapshot 可見；子圖正常結束傳 root，沒有 messages 更新或原 metadata 改寫 |
| MV18 取消與 child→root | Task 5 覆蓋兩條 close 分支：confirmed manifest 保留、未發送準備不升格；工具結果補齊但尚無模型請求不新增 supplied claim |
| MV19 readonly 長串遇工具限額 | 停在原限額時明示未全讀；不聲稱完整、沒有補造尾段，沒有增加 budget／自動開下一輪 |

Task 3 退出要求 MV01–17、19 的離線 request／state 證據；MV12 若已有 Task 2 專用 PG 就直接跑新程序，不能用 in-memory 冒稱；MV18 與真正取消 fault injection 仍在 Task 5。Task 3 報告須分列未通過項，不將尚待 Task 5 的取消整合隱藏成全綠。測試使用 actual provider serialization 捕 request，外部 model create/count 請求數為 0；count 模式若要測同樣用 transport fixture。

## 9. 選項、取捨及 closure

| 選項 | 判斷 |
|---|---|
| 只記最後 jd_read 版本、只看 head origin 或兩端文字差異 | 不採：純訪談、分頁、AI 後人工、revert、marks 都可能誤報或漏報，違反已定產品效果 |
| 所有保存事件全文每輪送入模型，或另建逐 block「已讀」服務 | 不採：無界 context／狀態增長，且「供給」仍不等模型理解；超出本輪簡單接線與 Memory 邊界 |
| 本稿：有限 response-backed request manifest＋原 revisions 查詢＋request-only 有界通知 | 推薦：事件不漏認、範圍據實、重開可保守恢復、三工具不增加形狀；代價是長歷史按需多次回查，完整性與工具限額需明示 |

Decision / finding：既有正式 middleware／LangGraph state／三工具具足夠接點；需補 root-child 共用供給紀錄、既有 change_refs 建立事件語意及指定負例，不能只加 prompt。

Status：G4有限設計review PASS，已由主線納回register與Task 2／3／5；runtime及自然效果仍未驗。

Why：使用唯一保存歷史與既有 runtime 就能區分 committed 事件、淨差異、實際供給與未知，不新增同步／Memory owner。

Affected artifacts：主線納回時才更新核心 plan Task 3／5、三工具 SSOT descriptions、工具責任文件及隔離 README；程式／schema／plan／register 本輪均未改。

Reopen trigger：review 證明 readonly revision→建立事件鏈無法落在既有 owner、SDK request 缺通知、model checkpoint 無法同存 manifest、原工具分頁無法保留完整內容、或實測呈現上限不能保留必備 envelope。自然模型未理解屬後續有預算的品質驗收，不以泛搜替代實證。

Next gate：按原Task 1→2→3順序施工，Task 3先納§6.2同一SSOT descriptions、codegen與最終request驗收；Task 5補取消對帳、Task 6固定整合。未實作、未跑runtime測試、未安裝、未呼叫付費模型；不宣稱已通過實際provider或自然模型驗收。
