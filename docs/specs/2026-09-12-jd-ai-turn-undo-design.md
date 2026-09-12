# 撤回一輪 AI 的 JD 改動

- 日期：2026-09-12；Topic：JD-R002；Owner 已選撤回單位，研究者依有界增量評估採 HR-02／G3 WORKING；本稿為 G4 設計，未實作。
- 接續：[需求 §12](2026-09-12-jd-relational-editing-requirements.md#12-hr-02撤回這輪-ai-的-jd-改動2026-09-12)、[整份還原](2026-09-12-jd-history-and-recovery-design.md)、[共同保存契約](2026-09-12-jd-relational-schema-and-write-contract.md)。不重做 Memory 或通用 Undo 引擎。

## 1. 需求、取捨與結論

Owner 重開先前「不加最近一步撤回」，表示若簡單可做，並明確選擇：**一次撤回這輪 AI 對 JD 的全部改動**。例如同輪先改任務 A、再新增 B，按一次後兩者一起回到該輪修改前；不是只撤最後新增 B。

撤回只作用於 JD。**Memory、案例理解／詳記、原始對話及原 AI 回合紀錄不隨之倒退或刪除。**它們仍沿既有方法接受新資訊、補充與更正；不把「不隨 JD 撤回」解讀為凍結 Memory。JD 是由持續累積的工作材料形成的可修訂產物，畫面稿移除不表示使用者沒有那項工作。

| 方案 | 增量與取捨 |
|---|---|
| 只撤最後一筆保存 | 最少額外邊界資料，但不符合 Owner 選定的整輪效果；不採 |
| 整輪 JD 撤回，要求沒有較晚 JD 變更 | **採為第一版設計**。共用已設計的整份還原、版本檢查與回執；補可信回合歸屬與完整範圍查詢，不另存候選稿或起終版副本 |
| 允許任意舊回合、保留所有插入修改後自動撤回 | 須辨認相依更正與合併衝突，無法靠整份舊版保證；不納入本次簡單功能 |

因此是**有界但非只加一顆按鈕**的功能。既有還原仍是已審設計，不能說目前 App 已有可直接啟用的實作。採用前須驗回合分組、未知結果及手改插入；若無法用本稿邊界保證，停在已定歷史／局部更正，不默默升級成通用回退引擎。

## 2. 最新官方依據

均於 **2026-09-12** 查閱官方正文；產品／方法文件非新增 OSS 依賴，未安裝 SDK、升級框架或執行產品模型。

| 來源、適用狀態 | 官方事實 | 本案映射與限制 |
|---|---|---|
| [Claude Code checkpointing](https://code.claude.com/docs/en/checkpointing)，現行產品文件，未標固定發行版本 | 開始 turn 的 prompt 建 checkpoint；中途加入訊息不另建；可只恢復程式，沒有受追蹤改動時不提供程式恢復 | 支持按使用者工作回合選恢復範圍；不能把檔案追蹤推成所有工具／人工改動皆可分離撤回 |
| [Claude Agent SDK file checkpointing](https://code.claude.com/docs/en/agent-sdk/file-checkpointing)，現行 SDK 指南；特定略過路徑行為要求 Code v2.1.216+ | rewindFiles／rewind_files 只還原受追蹤檔案，對話／context 保留；Write／Edit／NotebookEdit 之外有追蹤限制 | 直接支持產物恢復與對話保留可分開；此 SDK 不會替本案 PostgreSQL／Memory 還原，不直接採用 |
| [OpenAI Code review](https://learn.chatgpt.com/docs/code-review#review-in-the-app)，現行 Codex 產品文件 | Git review pane 可查看並 revert 變更；review 與實際修改不同 | 支持可檢查的產物修改；公開文件未保證任意手改插入後可無損撤銷 AI 回合，不猜其內部恢復演算法 |
| [AWS idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)，現行 Builders' Library 方法，非版本化 API | caller token 表達同意圖；效果與 token 原子保存；同 key 改參數拒絕 | 撤回是一筆新的明確業務意圖，原修改紀錄不改；撤回回覆遺失查同一 operation，不重發新 key |
| [PostgreSQL 16 row locks](https://www.postgresql.org/docs/16/explicit-locking.html#LOCKING-ROWS)，指定穩定主版本，PostgreSQL License | FOR UPDATE 保護鎖定列至交易結束，等待後按適用 isolation 取得實際資料；不同列不等於全域排隊 | 沿同文件鎖內驗 head／範圍，不能只靠 UI 按鈕狀態；用既有 transaction，不跨模型回合持鎖 |

**共同原則：**明確標示恢復範圍、保留可查歷史、App 執行並回真實結果、同意圖可安全對帳。**本案選擇：**整輪 JD、沒有較晚 JD 修改才提供快捷、只改 JD 及單一 run 關聯欄。這些不是大廠統一的表數／工具名。

## 3. 已有能力與最低缺口

下列核隔離成果，不代表 production 已採用；新 relational JD 尚未施工：

| 本地證據 | 可用與限制 |
|---|---|
| [catalog.py 的 RunRow](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/catalog.py)、[service.py 的送出流程](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/service.py) | run ID 已持久化，作實際 HumanMessage ID；有原 request 防重與既有回合 owner，不需第二套聊天回合表 |
| [jd_tools.py 的 after_model／binding](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/jd_tools.py) | 已用 document／turn／message／call 配 operation，binding 保留 base／commands；但下一 input 清空目前 jd_bindings，不能拿它當永久分組查詢 |
| [jd_store.py](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/jd_store.py)及新 schema §4.3 | 已有 committed base/result／producer；目前沒有可查的 run 欄，本輪需补 `ai_run_id`。UI envelope 有 run_ref 不代表 DB 已保存 |
| [jd_context.py](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/jd_context.py) | model-view 通知基準可延續；其 notice.start 是前次模型已讀基準，**不能當這輪修改起點** |
| service 的 close／reconcile | 已有 writer 停止＋pending bindings／操作與回合閉合；只看 completed／cancelled 字串不足以允許撤回 |

最低接合是：把 App 已知的可信 AI run identity 與每次 AI operation／receipt 原子保存，補整輪一致查詢及人工快捷入口。S／E 由現有 revisions 的真實 parent 鏈取得，不另存會失步的「回合起點／終點 JD」副本，也不新增 Undo stack 表。來源欄位、模型工具、Memory 寫入工具不因本功能增加參數。

## 4. 何時可撤回

App 針對明確回合 T 顯示「撤回這輪 JD 改動」，附該輪時間／內容變更範圍與可展開的確切比較。沒有 JD 寫入的純訪談／只改 Memory 回合不顯示可撤回效果；較晚純訪談未修改 JD 不會單憑時間使原效果消失，但只在沒有前景工作進行時可執行。

server 必須同時確認：

1. T 屬於此文件；既有 runtime 已完成或取消／失敗後確實閉合，沒有未解操作及仍可寫入的 writer。服務重開先恢復，再判斷可用；缺證據則只提供歷史查看。
2. 取得 **T 的全部 committed JD operations**，依 result revision number／parent 排序。失敗、no_change 不構成變更；第一筆 base 是 S，最後 result 是 E。
3. S 之後至 E 的完整線性 parent 路徑，與這些 committed operations 的 result 集合一一相等，且每筆 base=前一版。不能只從 head 倒掃一小段或按 created_at／origin='ai' 猜成一輪。曾跨人工／其他回合修訂而不連續時不提供快捷。
4. 目前 head **仍為 E 的同一 revision identity**。人工或其他 AI 後來修改、還原、再改回相同文字，都會有新 revision，快捷失效；不靠內容 digest 相等放行，也不自動合併保留部分。
5. 未提交人工輸入先完成或明示捨棄；若先自動保存成新 revision，原快捷失效。原在途操作先對帳，不能先撤回再處理較晚輸入。

上述有一項不成立，說明目前不可直接撤回這輪，仍可看歷史／局部更正／明確整份還原。這是避免誤蓋後來工作所需的有界限制；不讓 LLM 判斷是否可覆蓋或自行算版本。

若 T 曾寫入後又改回，S／E 內容完全相同，歷史仍有事件，但沒有淨內容需撤回；查詢顯示此原因而不產生新 revision。不得將 no_change 当重新倒退訪談或其他資料的理由。

## 5. 業務操作與可靠結果

人工端使用具名 `undo_ai_turn`，輸入是 App 發配的 T／預期 E refs 與新的 operation identity；**不讓員工或模型提供 S／原 snapshot**。server 由 §4 的持久證據推導 S。App 的可見範圍與按鈕即為這次明示撤回；一般任選歷史版的整份還原仍沿原完整預覽確認流程。

1. 查相同 operation 的原 receipt 優先於新的資格判定。同 key 相同固定意圖回原結果；不同意圖拒絕，不能因第一次已改 head 就把同次重試當新 stale。T／預期 E 納入 canonical command／request digest。
2. 沿既有 admission 綁定一次人工寫入，確認整個文件目前無 foreground writer；取得 document→head 鎖後重新驗 §4，UI 舊的 eligible=true 沒有寫入效力。T 的 run／closure 資訊來自既有 owner；新 writer 不能在人工 entry 持有期間進入，不在 SQL 交易中呼叫 LLM 或跨 store 語意服務。
3. 以 S 的 server 內部 snapshot 經 **同一 restore domain service** 形成候選、驗來源與關係、重建該文件正文；新 R 的 parent=E、origin=manual。current、snapshot、head 與新 receipt 同交易提交，source 沿歷史原 links／basis，原引用回查狀態另顯示。
4. 新 receipt 記 `undo_ai_turn`、被撤回 T、實際 S／E／R 及精確變更入口。原 T、原 AI operations／receipts 全部保留成功歷史，不改成 cancelled 或刪除；查原 operation 仍回原結果，現在的撤回效果由新事件描述。
5. COMMIT／回覆遺失沿原 operation 對帳，不由模型再改一次 JD，不重做已成功的 Memory。語意拒絕、已知 rollback、未確認 receipt、未知寫入結果仍沿共同契約分支。

`undo_ai_turn` 是人工業務入口；與模型共用 domain／保存規則，不增加模型自動撤回工具、不用模型呼叫來執行按鈕。它也不是停止 AI、對話 rewind、重新生成答案或 provider request retry。

連按同一按鈕／回覆遺失使用同一 operation。首次撤回成功後目前版是新 manual R，原 E 不再是 head，不可再以新 key 重複撤回 T。此功能不加入 undo／redo stack，不把剛才的撤回當另一輪 AI；需要恢復被撤掉的 JD，仍從歷史明示選原 E。若只有 no_change，保留原查詢原因／結果，不製造假的已撤回事件。

## 6. 與工作理解、案例及原始對話的關係

App 的人工變更通知記本次 `undo_ai_turn`、被撤回回合與 JD 前後版本，並說明「只撤回 JD，不代表否定這輪提供的工作資訊」。模型已讀基準不倒退；下一輪先取得新 current 與必要差異，不沿被撤回稿的 refs 續改。此 metadata 是 App 事實，不偽裝成員工原話，也不因按撤回就呼叫 Memory 寫入。

顧問仍可讀目前 Memory、案例材料和確切原始問答，判斷如何重新撰寫；JD 變空不應觸發清空理解。只有撤回動作、沒有說原因時，不擅自認定事實錯誤或立刻把同稿原樣寫回；下一輪按使用者意圖釐清或更正。這是顧問行為驗收，不靠資料仍存在就宣稱模型一定能完全記住或重建每項工作。

本輪「JD 可撤回或刪掉」表達產物與理解資料的分離，不自動擴為永久刪除整個 document scope 的功能。任何未來清空／重建 JD 的操作，都不能連帶 cascade 刪除访談、案例或 Memory；本輪不新增清空／永久刪除入口。

## 7. 待執行驗收與完成界線

| ID | 必須能證偽的情境 |
|---|---|
| AU-01 | 一輪 r4→改 A 得 r5→新增 B 得 r6，撤回一次得到新 r7，JD 等於 r4；r5／r6／所有原問答、案例、Memory保留 |
| AU-02 | AI 回合先有 no_change／失敗再兩次成功；範圍以全部 committed 鏈取得；零成功或淨內容相同不偽造撤回 |
| AU-03 | AI 后人工改，再改回相同文字，或另一 AI／歷史還原介入；head identity不同使快捷失效，不覆蓋較晚工作 |
| AU-04 | 同 run 操作不連續／缺 run identity／跨文件；拒絕分組，不只倒掃最後一段，不猜 timestamp |
| AU-05 | 同 run 取消或程序崩潰、最後一次結果未知；先閉合全部操作和 writer，再納入查回的真實 committed 效果 |
| AU-06 | 預覽後另一入口寫入；鎖內再驗拒絕 stale。未提交手改在場時不靜默丟棄或保存後仍照舊撤回 |
| AU-07 | 撤回 COMMIT 回覆遺失、雙擊同 key／異 key；原結果可查、只新增一次修訂、原AI receipt仍是原結果 |
| AU-08 | 撤回第二步SQL失敗、來源不可讀或舊basis待核；全成／全敗，沿用引用不假稱重新背書，沒有跨store寫入 |
| AU-09 | 下一輪／重開／context壓縮後仍可查整輪歸屬；不用已被清空的目前 jd_bindings 或 notice.start 判斷起點 |
| AU-10 | 撤回後只問工作內容／要求重寫；顧問可按現行理解與原話回查，沒有自動抹除事實或無意圖重套原稿 |

既有停止、回執及歷史的已驗成果只是接合基礎；本輪沒有新 runtime／DB／瀏覽器／自然模型實測。核心工程維持零付費。先完成本稿獨立審查及 successor schema／DTO／保存測試設計，再沿既有暫存相容性前置與整體 G4 推進；不因本功能採用就宣布 ADR0075 已 Accepted。[本輪審查與證據](evidence/2026-09-12-jd-ai-turn-undo-review.md)
