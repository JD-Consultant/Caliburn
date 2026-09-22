# Task 3 獨立 spec／quality review

2026-09-10；JD-R002/C03；隔離 G7。

**Spec verdict：FAIL。Quality verdict：CHANGES REQUIRED。** 四個具體 finding，均限 Task 3 已授權接點。完整 lifecycle／MV18／browser 不列阻擋。

## Review 範圍與證據

- 基線 `23bf0161d3d61dc8517ec1ecf4ee9ad5cb8e5a6d`，HEAD 未提交。依 `task-3-review-manifest.json` 與 `task-3-review.diff`（23 paths、153,210 bytes）審閱凍結變更一次；先前 README 11 行與既有工具契約全文未冒充新增範圍。
- 已讀實作者 report、final r2 原紀錄；確認 **177 passed、1 既有 Starlette warning、169.04 秒**，不重跑 suite。模型 schema 的 actual SDK 測試、正常 graph/child/root 與兩個 PG 新程序的 manifest 測試有實作，未拿它們代稱自然模型品質。
- 僅為具體疑慮讀既有 `runtime.build_agent` middleware composition、`sources` capture/extraction 邊界、`live_memory.wrap_tool_call` 與 `memory_read_tools` 原 owner 工廠。未重審 Task 1/2 原生或 PG 核心。
- 四項下列 focused reproduction 以 inline Python 執行，未建立測試檔／改 runtime：原生 selection + 純 App mapping；真 LangGraph/SDK `offline_model` MockTransport 的後置 middleware；原 notification helper 的確定性事件 fixture；真正 `memory_read_tools` factory + canonical InMemorySaver source + 真 graph/SDK。無 DB 改動、無 key 讀取、無外部或付費模型請求。
- Root 後增 `.gitattributes` 的兩行只將 `docs/specs/evidence/jd-editor-task3/*.txt` 設為 `-text`，與保存 raw captured bytes 的既有 Task 2 做法一致；有限核對無 finding。

## T3-R01 — P1：局部選取可授權修改未讀的整個 block

**位置：** `experiments/analysis-agent/src/analysis_agent/jd_tools.py:221`（亦涉及 `:204` 的 selection fragment targets）。

`jd_read({})` 的 selection capture 無條件以 `supplied=True` 發出整段 target，即使那個 block 不在當頁 `fragment/targets`，模型只收到選取的數個字。`_resolve` 隨後接受此 `selection.target_ref` 作 `replace_block_content`、remove 等整段命令。另以 `selection_ref` 再讀時，原生 fragment 是截取後的 block，`:204` 也將它當完整 block 的 supplied target。

**重現：** native 兩段 `[first: 'first page', second: 'selected UNREAD REMAINDER']`，實際 `JdEngine.selection` 選第二段前 8 字，`page_size=1`。本次 read 的正式 fragment 只有 first、selection content 只有 `selected`；使用其 `selection.target_ref` 的 whole-block replace 仍被 `_resolve` 成功映為 `target_id='second'`。沒有提供 `UNREAD REMAINDER`，卻已授權覆蓋它。

**影響與依據：** 違反 Task 3 已發配 refs 的實際供給範圍與「完整正文 read 才可整段改寫」；MV08/16 要求局部供給不冒充整版／完整 scope。這是資料遺失風險，不是後續 browser capture 的要求。

**最小修正：** selection 的 range capability 可保持可寫；它關聯的整段 target 應為導航／未供給，除非同次 read 真正返回完整 block。原生 selection fragment 中的 target 亦不可因此升格整段權限。模型可沿 target_ref 再讀完整 block 後取得完整寫入權。補 off-page 選取與 `jd_read(selection_ref)` 後直接 whole-block edit 的 focused 負例，並保留合法 replace_selection 通過。

## T3-R02 — P2：後置 model middleware 可破壞最終 schema／通知，manifest 仍宣稱已供給

**位置：** `experiments/analysis-agent/src/analysis_agent/jd_tools.py:130`–`:150`；最後 `JdExecutionIdentity` 只有 tool wrapper。

JD wrapper 在呼叫後續 handler **之前**核工具及準備 manifest，卻沒有核對後續 middleware 最終交給模型的 tools/messages。最後 identity guard 僅在 ToolNode 生效。後置 model middleware 可以換同名 JD schema，或移除 App notice，外層仍將原先準備的 manifest 與 completed response 一起保存。

**實際 graph→SDK 重現：**

1. 在 session 後加入一個 `wrap_model_call`，把 raw `jd_read` 換成同名 BaseTool。最終 MockTransport 捕到 `description='Wrong schema replacement.'`、required `arbitrary:string`、無 JD `strict:false`，graph 正常完成，沒有 fail closed。
2. 同位置僅移除 request messages 中含 `app_jd_context` 的消息。最終 wire 的 **user items 僅剩員工問句**，但保存的 `jd_last_model_view.notice_scope` 仍為 `kind='exact', complete=True`，並推進 current revision。注意只搜尋整個 request 的 `app_jd_context` 會誤判，因 system guidance 仍有該字串；本重現核對實際 user items。

**影響與依據：** Task 3 固定 factory/model-view 原格式及 model-view 設計 §4 明定後續 middleware 必須保留資料；MV14/17 要證明實際 request supplied。當輪通知未到模型仍推 B，會漏掉後續應補的人工更動，並把不曾送出的 exact content 標為供給。

**最小修正：** 在現有 composition 的最終公開 model wrapper 邊界驗證 JD model views 與 request-only notice 仍為本次授權內容，或把最終準備／確認放在所有可改 request 的 middleware 之後。須保留其他 middleware commands／system 內容及非 JD 工具，不建立新 model chain。補兩個 actual SDK 負例：同名 schema 替換、notice 刪除／修改；失敗時 provider 不執行且 manifest 不前進。

## T3-R03 — P2：合併本輪／本次事件後裁成四筆，省略數仍用裁切前資料

**位置：** `experiments/analysis-agent/src/analysis_agent/jd_context.py:66`–`:70`。

`basis.interval.events` 與 `since.events` 合併後再取最後四筆，但 `turn_start_interval.omitted_events`、`since_last_response.omitted_events` 原樣沿用各自裁切前的數字，沒有依最終實際顯示明細重算。

**確定性重現：** 前輪 B 後有四次 manual committed，當輪第一 request 保存 manifest；接著同輪一個 AI committed。下個通知的 `turn_start_interval` 為 `manual_count=4,total=4,omitted_events=0`，實際 `events` 卻是 `[manual,manual,manual,ai]`。一筆人工事件已被省略而 envelope 明說零省略。此反例沿既有兩個 interval 設計，不需 race 或取消。

**影響與依據：** MV06/14 要求長歷史明示尾段與未列數，固定跨輪通知在後續 requests 仍據實；目前模型無法依 envelope 判定哪個 interval 還有未展開事件。

**最小修正：** 先決定最終四筆明細，再按各 interval 的實際列出事件數计算省略數／標示其覆蓋範圍。保留整區間 committed counts、B0/H0 與本次 B/H，不增加預算或新歷史 owner。補「四 manual 跨輪＋同輪 AI」及重疊 interval 的 focused 對照。

## T3-R04 — P1：來源 acquisition 根據外層舊 tool 身分，接受後置同名 fake 結果

**位置：** `experiments/analysis-agent/src/analysis_agent/jd_tools.py:159`–`:165`。

來源 instrumentation 判斷的是呼叫 `handler` **之前**的 `request.tool`，但後置 middleware 可替換實際執行工具。回來只要是 success ToolMessage，含 reference 與一個 user segment 就 checkpoint `jd_sources`。最終 JD-only guard 不保護此 acquisition；`validate_sources` 再讀真正 owner 只能證明 handle 存在／window 閉合，不能證明模型先前收到的是原話。

**真 owner／graph 重現：** 先用正常 graph 完成一輪並 `ConversationReader.capture` 得真 closed-window handle；使用真正 `memory_read_tools(MemoryArtifacts(InMemoryStore()), None, reader)` 建立原 `read_conversation` factory，再由 session 後置 tool middleware 替換同名 fake。fake 回原本存在但尚未 acquisition 的 handle，segment 只有 `FAKE EMPLOYEE WORDS`。實際觀察為：`owner_read_count_during_graph=0`、`fake_handle_acquired=true`、canonical ToolMessage 是假文字；其後 `validate_sources([reference], result['jd_sources'], reader)` 仍成功。

**影響與依據：** 直接違反 Task 3.3「未讀／捏造 handle 拒絕」、原 factory／source owner 授權與 report 的「same-name replacement cannot grant original-source acquisition」。之後 JD 可帶來源引用，但模型看到的是替代工具捏造的原話。

**最小修正：** acquisition 必須來自實際原 source owner 的本次 successful read 及其返回內容／scope，不能由外層舊工具身分加任意結果外形推定。沿既有原 owner／factory 的有限接點核實，兼容 MemorySession 為 pinned version 合法建立的 reader；不需重建 Memory 或通用 guard。補同名後置 reader replacement 的真 graph 負例：原 owner 未讀時不發 acquisition、fake 結果不得通過來源授權；原 Memory reader 正常路徑維持通過。

## 其他已核對項與退出條件

兩處 SSOT description 及生成改動符合指定 shape-only 邊界；完整 ModelInput validator 在 Node 前存在；正常 current/history/pinned continuation、K/S mapping、no-change vs comparison、原 source window 解析及 before-Node binding 的官方 after_model 接點均可辨識。same stop Event 的實際 edit/read-selection forwarding 存在，unconfirmed 會保留 pending 並阻止下一 model request；未因此宣稱完整 worker 停止／reconcile 安全。

上述四項修正後做有限反例與受影響接點驗證，再對修正差異窄複核。不要求重新廣搜、重跑全部 177 項或提前做 Task 4/5。本 review 不修改工作樹程式／index／HEAD，不提交或 spawn；僅產生此 scratch 報告。production authority、付費 provider 接受度、自然品質與 Memory 正式化 gate 維持原限制。

## Fix1 窄複核 — 2026-09-10

**Spec verdict：FAIL；quality：CHANGES REQUIRED。T3-R01／R03／R04 CLOSED，T3-R02 尚有同一供給完整性缺口。**

本輪只讀 `task-3-fix1-report.md`、五檔 `task-3-fix1-review.diff`／manifest 與相關驗收尾段。確認 initial RED 7 fail、初次 GREEN 7 pass、affected matrix 42 pass + 一個 child/root 測試觀察失敗、final focused 9 pass、owner regression 34 pass；沿報告去重為 **77 distinct affected cases**，不把 final 9 再加總，也未重跑原 177。`sources.py` 的 invocation-local observer 是 root 明示核准的有限 seam，未要求重做 Memory policy/owner。

- **R01 CLOSED：** selection-only read 不再發完整 block supplied target，off-page capture 亦如此；實際完整 target reread 才給另個可寫 target。兩種原反例及合法完整 reread→commit 都有同一 focused 測試；原 API/native replace_selection 在受影響矩陣內。
- **R03 CLOSED：** `coverage()` 依最終四筆明細對各 interval 計 omitted count；原四 manual + 本輪 AI 反例現為 omitted=1，本次 interval omitted=0。重疊事件以 change_ref 集合去重，不新增 state owner 或提高上限。
- **R04 CLOSED：** acquisition 核對本次真正 `ConversationReader.read` 成功觀察到的 deep-copied projection；未讀 owner 的替代結果、真讀後改字均拒絕。觀察資料只活在 context manager，finally reset。合法 pinned Memory reader 與既有 source owner 回歸已通過。
- **R02 原三個負例已修：** 最終公開 model wrapper 在 provider 前驗 raw JD schemas 及 notice exact dump；同名 schema 替換、notice 移除／修改均有 transport=0、manifest 不前進的測試；合法 System additions／其他 state Command 有正例，沒有為它改原 child state 責任。

### T3-R02 殘留 — P2：相同 ToolMessage ID 的內容篡改仍被確認為原結果供給

**修正後位置：** `experiments/analysis-agent/src/analysis_agent/jd_tools.py:372`（最終 guard）及 `:376`（confirmation）。

新 guard 對 `visible_jd_results` 只比較訊息 ID；後置 model wrapper 可保留 JD ToolMessage 的 ID/name/call，改掉其正文後再呼叫 handler。ID 清單及 compaction boolean 不變，所以 guard 放行，manifest 仍表示實際供給了原 checkpointed factory 結果。這是新 guard 的具體檢查缺口，仍屬原 R02／MV08/17 的「manifest 必須對應實際 request」，不是新架構要求。

**唯一新 focused probe：** 真 `run_calls` graph→SDK MockTransport，唯讀 in-memory JD fixture，一次 `jd_read({})` 後加入後置 wrapper，只將該 ToolMessage JSON `fragment[0].children[0].text` 改為 `ALTERED WORDS SAME ID`。實際捕獲：

```text
wire read fragment text = ALTERED WORDS SAME ID
canonical ToolMessage fragment text = CANONICAL ORIGINAL
saved manifest visible_jd_results = [原 jd-result:call ID]
provider requests = 2，沒有拒絕
```

因此既有 `jd_results`／canonical result 的 exact revision/range 已不能證明此次 request 提供的真內容；模型可在仍帶原可寫 refs 的結果中看到變造文字。無 DB、key 或付費請求，未重跑 suite。

**有限修正：** request preparation 對被宣告供給的 JD 結果保留本次 exact message projection/digest（包含 content 與配對身份），最終 guard 除 ID 外也核該內容未被後置 wrapper 改寫；或據 final actual contents 保守拒絕／移除無法證明的供給 claim。維持 canonical 不改、原限額與 request-local 結構，不新增 durable 文件／Memory store。補一個保留 ID 卻改文字的 actual SDK 負例，provider=0、manifest 不前進；正向合法 middleware 仍應通過。完成此窄修後只需複核該差異及對應證據。

## Fix2 最終窄複核 — 2026-09-10

**最終 Spec verdict：PASS。Quality verdict：APPROVED。T3-R01／R02／R03／R04 全部 CLOSED。** 前述初審與 fix1 失敗紀錄保留，不改判原結果。

僅讀本次三檔 `task-3-fix2-review.diff`、report、manifest 與 RED/GREEN/boundary 原紀錄；三個工作檔 SHA-256 均與凍結 manifest 相符。未重審其餘 Task 3 範圍，未重跑 77／177 或新增 probe。

**R02 殘留 CLOSED：** `_jd_message_projection` 現在 deep-copy 實際宣告供給的完整 ToolMessage dump（正文、ID、name、tool_call_id 等）及可見配對 AI message ID／tool-call record。準備發生於既有 compaction 投影後，最終 `JdExecutionIdentity.wrap_model_call` 在 provider handler 前做精確比較；相同 ID 修改正文已不能延續原 supplied claim。這份 projection 只放既有 request-local ContextVar，finally reset，不落入 checkpoint、JD SQL 或 Memory，不建立第二份 durable authority。

新 actual graph／SDK 負例確實保留第一個成功 request 的 prior manifest：修改發生於第二 request，transport 總數仍一（該次為零），保存 checkpoint 裡 manifest 未前進、canonical ToolMessage 原字不變。正常 read→下一 request 正例則 wire 保留原文，manifest 與返回 response 配對。

核對證據為 RED **1 expected fail／1 pass，6.71 秒**；GREEN **6 pass／8 deselected，8.21 秒**；另跑 boundary **4 pass，6.37 秒**，共 **10 distinct 直接受影響案例**。provider 三項與 compaction 一項由獨立 boundary 紀錄證明，不將被 filter deselect 當通過。fix1 的合法 System／其他 Command 正例亦在本次 focused 六項內。未見這次窄修新增具體阻擋或需擴測的反證。

Task 3 的隔離施工與上述有限修正可進入 root 的本地保存點流程。此批准仍不包含完整 OS owner/reconcile／MV18、browser/IME、真 provider schema 接受度、自然專業品質或 production authority 切換；維持原 Task 4/5 與正式化 gates，零付費模型。
