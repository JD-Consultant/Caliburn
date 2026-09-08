# CT25：GPT 提示架構與即時修補完整候選

2026-09-08 · Q019-MEM-CADENCE-01／CT15-R07 · **Owner已核准M1＋T1；隔離接線及544項離線回歸通過，只讀review通過，G8 OPEN。§1–6保留原候選研究，最新接線與舊防錯核對見§7；未新增付費生成、未接production。**

## 1. 本輪決策與閱讀入口

Owner同意[CT24](2026-09-08-ct24-live-repair-use-and-background-timing-review.md)後，補充必須看最新GPT的提示建議與撰寫架構。本輪只完成完整提示對照，保留「即時修補優先；背景以LLM段落通知＋文字量後備，低資訊量先累積」。不重新選Memory架構、不加Agent、不強制tool choice、不換Luna／medium、不改reasoning／compaction或JD。

- 狀態入口：[主register](../../../../docs/current-decisions.md)；[討論流程](../../../../docs/decision-process.md)。
- 已有事實：[CT22結果](2026-09-08-ct22-memory-prompt-contract-results.md)是回答正確但0工具、持久Memory仍舊；根因仍未知，不能聲稱只是步數或patch問題。
- 完整現況：[CT21規範化system＋6工具](evidence/2026-09-08-ct21-memory-prompt-candidate.json)，即目前CT22接線的基準；不是另一套新候選。
- **本輪完整候選：[CT25 JSON](evidence/2026-09-08-ct25-memory-prompt-candidate.json)**。包含完整可見system、6工具、條件性背景提示及請求設定；不是只展示一段漂亮prompt，也不是實際送出的新請求。

## 2. 最新GPT官方建議：看架構，不盲套新模型設定

本輪重新取得官方文件：latest-model現指GPT-6 Astra [O1]；另完整讀GPT-5.6家族提示指南 [O2]，與目前Luna更直接相關。**最新模型的行為、參數及改善幅度不能直接套到Luna；沒有換模型。** Anthropic的Memory/tool研究沿用CT24§2、§6，不重複展開。

| 官方公開建議 | 本案怎麼用 | 不可以推論成什麼 |
|---|---|---|
| 先定義成果、重要限制、可用證據與完成條件，減少重複絕對指令 [O2] | 清楚區分「答覆已更正」與「Memory寫入成功」；不在每個工具重複加MUST | 提示更短或更強就保證保存 |
| 連同Skills、文件指令與工具說明一起檢查衝突 [O1][O2] | 審核完整system、3份按需Skill及6工具，而非只改Memory段落 | 為跟最新版一致而重寫所有提示 |
| 用標題／邊界分隔角色、規則、例子與context；固定前綴與動態資料分開 [O3] | 保留現有角色與Skills區；Memory分成修補／背景／正反情境；沿用獨立guide資料標記 | 官方強制只有一種八段模板，或必須換API message role |
| 工具需寫清楚何時用、不用、輸出與錯誤處理；不要要求模型重填已知資料 [O2][O4] | 校正讀取工具實際能力；保留Runtime處理來源／版本，repair仍只填path＋diff | 為了可追溯而新增LLM必填來源、Skill、時間、ID欄位 |
| 反覆出錯可考慮例子，但推理模型也可能因此變差 [O4] | 僅一對短動作情境，另用不同內容驗證，未證明有效就不推廣 | 官方已保證few-shot適合這次Luna失敗 |

這些是官方建議；§3的具體職務情境、段落時機、中文字句是**Caliburn映射**，不是OpenAI或Anthropic正在使用的同一份prompt。[O2]提到持續reasoning也可能延續過時方向；本案看不到opaque內容，無法認定CT22由此造成，所以暫不改reasoning設定。

## 3. 候選的兩組變更

### M1：原候選的具體文字（現已核准，接線見§7）

1. **核實後修補：**已發布Memory與員工更正，或已回查核實的原始訪談不一致時，讀受影響內容並呼叫`repair_memory`，依工具結果完成或恢復。涵蓋模型先前整理錯誤，不只等員工說「請改記憶」。
2. **不能以聊天代替保存：**即使前輪已回答正確，Memory仍舊就仍有修補工作；只有目前Memory已正確、沒有其他新資訊，才是無需寫入的重述。不要求每輪例行查完所有Memory。
3. **短正反例：**聊天確認「本人覆核、主管核准」，Memory仍寫「本人核准」→讀取並修補；Memory已一致且無新增→不重寫、不通知背景。例子明標不是員工事實，不使用原失敗的日期答案。
4. **背景只對齊時機：**以累積尚未通知的實質資訊判斷有無整理價值；零碎新資訊先累積。沒有可修補目標的短更正不一律通知。已有保存的原始問答不因這個選擇刪除；文字量後備仍由系統處理。
5. **工具結果一致：**`no_memory`表示沒有可修補目標，停止這次編輯，回到背景時機規則；其他不可重試失敗／repair_limit仍依既有回復契約請求背景保存未保留更正，不將錯誤一概吞掉。這是低資訊量政策的對齊，不是新錯誤分類器。

成功修補同一更正後不重複通知背景；同輪另有其他累積進展仍可通知。含糊指涉／案例身分未明時先詢問或回查，不採「比較新一定對」。背景通知回執不等於Memory已更新，不等背景完成才答覆。

### T1：完整提示審核找到的接線落差（現已核准，接線見§7）

| 現況 | 候選修正 | 證據／邊界 |
|---|---|---|
| system允許已知地址直接讀，但`ls`預設幾乎總要求先列目錄 | 未知路徑才列目錄，已知路徑直接讀 | **不是新發現**：B2已在[MP-02a](2026-09-07-memory-prompt-live-calibration.md)處理；這次確認共用唯讀工具仍有通用版本 |
| `read_file`建議同次回覆並行多個讀取，但本runtime關閉parallel_tool_calls | 說明一次一工具、按缺漏續讀 | 保留既有序列呼叫，不新增並行能力 |
| `grep`建議使用沒有綁定的`execute` | 只說明literal搜尋、分別搜尋或讀相關段落 | 6工具沒有execute，不以工具名稱相似推定可執行程式 |
| 描述包含offload目錄與通用多媒體讀取 | 移除未在本text Memory／訪談詳記／Skill工作面提供的路徑與用途 | 本案刻意未註冊FilesystemMiddleware的offload hooks；這不是宣稱DeepAgents本身沒有offload／多媒體能力 |

**框架怎麼接：**本案`readonly_file_tools()`取用`FilesystemMiddleware(...).tools`，沒有註冊其model-call hooks；官方完整middleware原會在準備模型請求時依execute可用性調整grep說明。本案只拿tools所以沒經過該步。官方公開`custom_tool_descriptions`可在建構工具時覆寫ls／read_file／grep [F1]；候選建議用這個介面，不修改套件、不手刻工具、不為修提示啟用整組offload／scrubbing hooks。

已對照實際`memory_tools.py`、`skills.py`、Memory reader的CompositeBackend與官方工具factory／description-filter hook。所選路徑都是虛擬文字資產；Skill只掛載套件內唯讀方法，不提供任意主機檔案。**這些是實際提示落差，但不能證明造成CT22零工具；修正它們不等於修補效力已驗成。**

## 4. 明確保留與成本

- 6工具名稱、所有參數schema、工具回傳及執行流程不變。`read_conversation`與背景通知tool全文不變。
- 完整保留patch格式、行號顯示與真實縮排區分、精確上下文定位、stale／重試回饋，以及未被更正的工作細節／案例邊界／引用保護。
- 保留原顧問角色、3份Skill正文與按需載入規則、progressive read、guide版本與本輪修補結果優先關係、條件性背景可用性提示。
- 固定規則→當前guide／狀態→近期／compaction延續的既有責任不變；候選JSON沒有复制所有歷史、opaque reasoning或tool結果，更不把它們當新system規則。
- 可見system文字由**4,617→4,889字元**，工具描述由**5,576→5,197字元**；合計**10,193→10,086字元（少107）**。只比較字元，**不是token、計費或效果的改善證據**；參數schema未縮減。保留重要防錯條件優先於硬砍字數。

## 5. 候選階段核對與當時的下一gate（歷史，已由§7推進）

本輪純離線`tests/test_memory_prompt_contract.py`：**2 passed**，證明未改的現行實際請求仍對得上CT21基準，不是CT25已接線、更不是新提示效力通過。第一次測試因Windows暫存目錄ACL受阻；一般權限、新的專用暫存目錄重測成功，沒有為此修改產品。另核對完整候選JSON、6組schema、保留段落與局部差異。

CT22原證據SHA256仍為`932529be827921343ffe5b31e11faeb648c753c0ed35b5760bdc7b12e0d9e3cc`，FAIL／closed帳本保留。無新增模型生成，無改產品src／tests；既有其他dirty文件不納入本輪。

**下一唯一gate：Owner審核M1＋T1完整候選。**核准後局部接線，再另確認小額Luna／medium驗證範圍；不借用已封存額度。驗證新更正、聊天已正確但Memory仍舊、Memory已正確的重述、含糊說法不誤寫，並檢查原細節與引用；既有回復錯誤離線核對。自然tool selection若仍漏做，停止追加同義規則，保留失敗再討論完成機制取捨；不偷偷加Agent／強制工具。局部通過後才恢復長訪談。

## 6. 來源：查到哪裡、支援哪個主張

- [O1 OpenAI最新模型／提示建議](https://developers.openai.com/api/docs/guides/latest-model#prompting-best-practices)：2026-09-08全文讀取，目前為GPT-6 Astra；支持整體instruction stack衝突審查，不將特定模型效果套給Luna。
- [O2 GPT-5.6家族提示指南](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)：全文讀取；成果／完成條件、減少重複、保留必要限制、工具與context邊界。本輪不採其coding數據當訪談效果證據。
- [O3 Prompt的Markdown／XML架構](https://developers.openai.com/api/docs/guides/prompt-engineering#message-formatting-with-markdown-and-xml)：完整讀取該節；區分角色、規則、例子、context與可重用前綴，結構需依模型／任務調整。
- [O4 Function calling設計建議](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)：完整讀取該節；清楚工具用途、不要讓模型填已知資料、例子也可能傷害推理模型。
- [F1 DeepAgents官方0.7.13 FilesystemMiddleware](https://github.com/langchain-ai/deepagents/blob/deepagents%3D%3D0.7.13/libs/deepagents/deepagents/middleware/filesystem.py)：對照本機已安裝0.7.13的constructor、ls/read_file/grep factories、`_grep_tool_description`／`_with_filtered_grep_description`及model-call接線；公開擴充點是`custom_tool_descriptions`，不呼叫私有hook。版本固定為重現依據，**不宣稱0.7.13是最新發行版**。
- Memory即時修補的兩家原始依據與適用邊界：沿用[CT24§2、§6](2026-09-08-ct24-live-repair-use-and-background-timing-review.md)，其中同輪修補具體指令有OpenAI依據；背景段落通知＋字量後備是Owner已選的應用策略，不能冠名兩家完全相同的共識。

## 7. 核准接線：按錯誤類型整理，不逐個BUG堆句子

### 7.1 有效決定與歷史防線

Owner核准M1＋T1，並補充：舊prompt可能為修復歷史BUG而加；相似錯誤也可整理成更好的共同指引。**保留防錯目的，不要求保留每句舊文字。**本切片只接核准的Memory動作與工具說明，未擴大重寫B1/B2、顧問或Skills。

GPT官方建議[逐組精簡、保留必要限制](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6#simplify-prompts-first)：保留成果／停止條件、業務／證據／驗證限制，改一組就重跑同一組檢查。下表的分組是**Caliburn歷史證據整理**，不是兩家官方同一份prompt，也不能由建議推得效果已提升。

| 歷史問題／同類風險 | 保留或整理成的原則 | 本輪驗證邊界 |
|---|---|---|
| [CT04](2026-09-07-api-memory-interview-validation.md)整段修改遺失其他既有細節，即時與背景都發生過 | 共用`MEMORY_EDIT_GUIDANCE`：最小修改；新資料未提不等於撤銷；整段替換仍保留未更正的範圍、例外、工作細節與引用 | 共享指引原樣；`test_recorded_luna_background_patch_replays_without_changing_other_cases`驗固定patch保留其他案例，**不保證模型產出的patch保留全部語意** |
| [CT13](2026-09-07-ct13-local-repair-results.md)案例／頻率／條件錯套、顧問轉述被當成員工確認 | 保留主體、做法、條件、頻率、權責與案例邊界；含糊就查證或問，新句不一定更正確 | `MEMORY_READ_GUIDANCE`、B1/B2、顧問及3份Skill正文不動；自然模型是否遵守仍需真實訪談 |
| 舊精確編輯失敗與重複片段誤定位 | 保留顯示行號≠原文縮排、真正上下文定位、最新staged文字、失敗重讀及官方V4A格式 | `PATCH_GUIDANCE`不動；`test_background_mismatch_returns_precise_error_and_can_correct`、`test_live_patch_late_failure_does_not_publish_then_retry_succeeds`驗回饋、整批不部分發布與重試 |
| [CT22](2026-09-08-ct22-memory-prompt-contract-results.md)聊天已更正、Memory仍舊卻零工具 | M1集中動作規則：核實後修補；聊天確認不是保存回執；已存且無新增才不動作；含糊不猜 | 完整SDK請求符合核准候選；**漏選是否改善仍未知**，不以契約測試當自然選擇效果 |
| 工具說明暗示不可用能力／互相矛盾 | T1只描述實際文字讀取工作面；已知地址可直讀、序列呼叫、literal搜尋，不指示不可用execute | 公開`custom_tool_descriptions`接線；6組schema及回傳不變；`test_official_tools_follow_guide_memory_summary_source_in_compiled_agent`與Skills測試驗工具鏈 |

機械契約不概括成「自行修好」：patch格式、原子發布、`invalid_edit`／`stale`／`retryable`與成功不得重試仍清楚。唯一結果說明調整是已核准的`no_memory`：沒有修補目標時停止編輯，依資訊累積與背景時機處理，不再每個短更正一律通知。

### 7.2 實作、結果與下一步

- [接線計畫](../plans/2026-09-08-ct25-prompt-wiring-and-regression.md)：`live_memory.py`接M1，`memory_tools.py`透過[F1]接T1；不改框架原始碼、schema、patch演算法、Store／Saver、排程、reasoning或模型。Runtime不從docs載入prompt，候選JSON不改。
- 獨立CT25 fixture先接測試：**2 failed（5.03秒）**，正是舊實際system不符新候選；接線後**2 passed（4.55秒）**；只整理程式字串換行後再驗**2 passed（4.68秒）**。不是由修改後程式生成期望值。
- 與`044ec71e`比對：排除兩個核准Memory常數、新讀取說明常數及其constructor參數後，兩份src的AST完全一致；其餘src／Skills無diff。CT25候選JSON及CT22原證據不變，後者原檔SHA256仍為§5的值。
- 全部非PostgreSQL離線測試：**544 passed，45.55秒**，1個既有Starlette／AnyIO deprecation warning；明確排除`test_postgres_*`，暫存目錄`.test-tmp/ct25-offline-regression-20260908-02`。前次全套完成輸出未成功擷取，因此重跑取得可核對結果，沒有猜通過數。
- 無API請求、無新付費額度；不重跑PostgreSQL／Docker或長訪談。上述驗證是原文分頁、引用回查、版本優先、發布與錯誤恢復、工具／Skills／context接線安全網，**不是提示的語意效果驗收**。
- 只讀review無Critical／Important／Minor實質finding；已核對完整候選、共享工具入口與舊保護，未擴大範圍。可本地保存（不代表promotion）；本地commit／tag結果以主register收尾紀錄為準。G8 OPEN，CT22 FAIL／closed帳本及原證據不改。下一步另核准小額Luna／medium自然修補驗證：新更正、聊天已正確但Memory未改、已存重述、含糊不誤改，並對比既有工作細節／引用。若仍漏選，回看trace再決定，不無限追加同義prompt、不擅自加Agent或強制工具；局部通過後才恢復長訪談。
