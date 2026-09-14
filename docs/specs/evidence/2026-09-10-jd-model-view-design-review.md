# Task 3.3a 模型可見人工變更通知：有限設計独立審查

2026-09-10。對象：`S:/caliburn/docs/specs/2026-09-10-jd-model-view-change-notice-design.md`。本輪唯讀核對候選、既有 context 研究、Task3.3a、active v2 三工具 schema，以及隔離 runtime／已安裝 LangChain 原碼；未執行測試、未改程式或責任文件、未 commit。PDR-01–04 不在本輪範圍。

## Preflight

- Topic ID：JD-R002/C03，Task3.3a。
- Current stage：核心隔離 G7；本稿是對應接線前的有限 G4。
- Binding decisions：跨輪保存的人工變更在下輪回應前主動可見；同一JD owner／三工具；不污染 canonical 訪談／Memory；無新同步或已讀服務。
- 唯一問題：比较基準、實際供給範圍、重開／compaction、state owner 及既有框架接點是否足以施工與證偽？
- Out of scope：production authority、付費／自然模型驗收、重審已閉合產品旅程 findings、廣泛重新研究。

## Actionable findings

無。未見必須先修改此候選才可進入對應 Task3 接線的具體缺口。

## 審查依據與結論的界線

1. **事件基準與實際內容分開。** §3 的 B 僅是 response-backed request 所附 current 狀態版本，(B,H] 逐 committed revision 查事件；本輪另留 (B0,H0]，不因第一個 request 已返回、後續 compaction 或純訪談而漏掉本輪人工通知。revert、metadata-only、AI/manual 交錯與 no_change 分別處理，沒有拿最後作者或淨差異取代事件。
2. **最新可見內容不依賴舊 opaque summary。** 每次 native compaction view 後重新加入當次 H 與本輪通知；preview/exact/partial、visible tool-result 範圍及未枚舉部分各有界線。最新全文沒有承諾每次全塞，必要內容可由 current/history/change 續頁回查；這與既有 context 研究的短內容／長內容分工一致。B 可用不等於先前正文仍在 request，文件已明示此差別。
3. **同 model node state update 有實際接點。** 已安裝 LangChain `middleware/types.py:291` 的 ExtendedModelResponse 與 `factory.py:_build_commands`／`model_node`（約213–260、1466–1489）支持 response messages command 加 middleware state-only command，且明確拒絕 goto/resume/graph。候選正好沿此接點，不需增加 after-model hook 的脆弱提交時序。是否在真圖／PG同一checkpoint保存仍須 MV17，不把讀原碼當已通過測試。
4. **root／child 與取消不假定自然傳播。** 現行 `conversation.py` 共享 state 只有 messages/outcome/closed_turns；候選明加 root/child 同名 manifest，另列 close_turn 的兩個 root update 分支需帶入已確認 manifest。`service.py:CooperativeStop.after_model` 確會在模型節點後停止，故把實際 response-backed 紀錄放 model node、把 close fault injection 留 Task5 是可行且已揭露的分階段出口。
5. **資料責任保持有限。** request-only HumanMessage 僅用於 provider 的低權限 App 資料視圖，不加入 canonical messages、來源或 Memory；固定規則要求辨別來源。這與既有 context 研究 §3.2 相容，不是新增員工原话。manifest／notice basis 只保存有限的最近供給紀錄及原 owner references，不累積逐block coverage，也不建第二JD或Memory store。文件資料的指令句不提升為system authority；自然模型是否遵守仍另驗。
6. **工具形狀可沿用。** active v2 的 JdReadSuccess 有 change_refs，JdChangeReadSuccess 有 before/after revision refs、origin及continuation；候選補「該revision建立事件」語意後可逐事件向前導航。readonly、同revision續頁、current target仍須由jd_read取得，各自不混用。description須納SSOT及最終SDK request檢查已列為Task3前置，沒有偷偷發未定義ModelInput。
7. **預算與錯誤有界。** 16KiB context、4事件、2KiB預覽是標示清楚的本案初始上限；bytes不冒稱tokens，沿現行 ResponsesBudget／truncation=disabled，不增加工具或模型總額度。保存／組裝故障不送request、不推進B；回覆遺失保守重通知但不重做寫入。原工具次數不夠就承認未全讀，未透過新背景模型或新服務補讀。

## Verdict / closure

- Spec verdict：PASS（有限 G4，可供 Task3.3a 施工設計交接）。
- Quality verdict：PASS（設計一致性、現有接點可行性與可證偽性）。無 actionable findings，沒有新增會影響最新已保存變更是否主動可見的設計矛盾。
- 尚未證明：最終 `/responses` request 實際順序／完整範圍、ExtendedModelResponse在真圖及PG的同checkpoint寫入、root-child重開與取消傳播、長事件串回查及自然模型理解。依文件 MV01–17/19 在Task3驗；MV18及真正取消fault injection在Task5，不提前合稱全綠。
- Decision / finding：同意此有限接法沿既有 middleware、checkpoint與JD owner實作，不需新增Memory／同步／已讀服務或新廣搜。
- Status：獨立設計review完成；候選須由主線納回plan/register及SSOT descriptions後依Task1→2→3順序消費，production G6不變。
- Sources：上述候選§3–8；既有context研究§3；隔離runtime.py/context.py/conversation.py/live_memory.py/service.py/budget.py/provider.py；已安裝LangChain types.py/factory.py；active v2 JdReadSuccess/JdChangeReadSuccess。
- Affected artifacts：只寫本scratch report；主線負責durable closure。
- Reopen trigger：MV實測顯示通知未到wire、manifest不與response同存／跨邊界遺失、原三工具無法保真續讀或存在具體authority衝突。
- Next gate：原Task3有限接線與指定固定驗收；Task5補取消，不提前批准production或付費模型。

## 有限補核：人工全值保存的定位資料

主線指出manual validate-value的normalization紀錄從candidate起算，不是baseline→manual。原reviewer補核可行：manual actual_changes native_operations=null、affected_element_ids=[]只表示未提供可靠定位，committed／異版refs及完整快照仍證明有改，通知必計入。沒有binding矛盾、無需新schema或引擎；六切片Task2及工具責任文義已同步。AI原生transform已有真operations，不可用此人工fallback省略其已支持範圍。
