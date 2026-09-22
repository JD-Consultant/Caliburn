# OpenRouter／Luna 對話延續 Compaction 設計

- 日期：2026-09-16
- Topic：`JD-R002／CTX-C001`
- Stage：**G7 分段施工完成；基礎元件、正式 A 與 B1／B2 App-side request-only 接線及 2026-09-22 角色化摘要／reasoning client 契約均已完成離線驗證**
- 取代：2026-09-15「等待 OpenRouter、改 direct OpenAI、另選長上下文策略」三選一的未決狀態
- 不取代：Q019 顧問 Prompt、Skills、JD relational writer、publication CAS、背景通知與准入規則；Memory 的最新 B1／B2／C 產品語意改由 [MEM-L001](2026-09-16-layered-case-and-work-understanding-memory-alignment.md) 持有

> **2026-09-17 MEM-L001 影響與 successor 結果：**本稿原只處理 A／B2，因當時 B1 是單次 structured extraction。Owner 後續將 B1 定義為維護目前案例層與案例 guide 的多步 Agent；本稿的 canonical 不破壞、runtime 依實際 request 觸發、安全工具 wave、失敗不前移邊界及 summary 不作來源等原則維持不變。App 現已把 B1／B2 各自的 middleware 從 exact injected role model 與明示 output reserve 組裝進 package workflow；B1 多窗口只壓縮已處理舊窗口，B2 固定任務、同 attempt resume 與新 attempt 清空均有離線 lifecycle 證據。後續[正式 OpenRouter／Luna 角色模型工廠](2026-09-17-openrouter-role-model-factory.md)也已離線完成；provider 自然模型、managed callback 與完整 App 仍未完成，且沒有重開 OpenRouter transport 選擇。

> **2026-09-17 正式背景限制 successor：**A 維持既有 8,192 主輸出、2,048 summary、90 秒及原步數／工具限制。B1／B2 由 App 正式 profile 提高到 32,768 主輸出、8,192 summary、300 秒；trigger 仍為實際組裝 request view 的 16,000 input tokens，保留最近 8 個安全訊息／完整工具 wave。提高輸出預留只改背景角色可用容量，不讓 compaction 壓縮 runtime context、未處理訪談、canonical source、引用或 Memory；也沒有新增隱藏重送。精確值與理由由[角色模型工廠](2026-09-17-openrouter-role-model-factory.md)持有，本稿不再保存第二份設定權威。

> **2026-09-16 CTX-W001 邊界：**主顧問在尚無 Memory、尚未觸發 compaction 或一次無法問完時所需的 Focus／待追查事項，由 [CTX-W001 訪談 Working State](2026-09-16-consultant-interview-working-state-design.md)另行承接。它與 continuity summary 都是非權威衍生狀態，但責任不同；summary 不可成為 Working State 的唯一 owner，Working State 也不取代長對話 compaction。

> **2026-09-16 G7 第一小步結果：**已新增尚未接入正式 A／B2 的共用 typed state、role profile、安全工具 wave 切點、canonical prefix digest、增量 summary prompt、request-only view 與同步 middleware。鎖定 LangChain 的真實 `create_agent`／Saver 離線反例共 12 項通過，涵蓋 canonical 不變、B2 固定任務、跨 graph 重建恢復、依實際 view 判斷、主模型失敗或截斷不發布、取消與截斷摘要拒絕。這只是基礎接點，不代表 A 與 B2 已改線、OpenRouter 自然 smoke 通過或 H4 完成；下一步才是 A 的真實 middleware 組合與 Command 累積反例。

> **2026-09-16 G7 第二小步結果：**正式 `build_consultant()` 現預設注入 A profile 的 compaction middleware，摘要沿同一個 OpenRouter／Luna model boundary，主回答預留沿顧問既有 8,192 tokens。A 的完整 JD／Memory、Skills、背景提示與工具投影先組裝，compaction 最後依真正 request view 計算；文件根 state 保留 `continuation_compaction`，不再於 child 返回 root 時遺失。真 `create_agent`＋真 OpenRouter client／合成 HTTP＋Saver 反例確認：摘要與主回答使用相同 OpenAI-only／no-fallback route、摘要 request 沒有業務 tools、兩次 usage callback 均可觀察、`jd_model_view` 與 `continuation_compaction` 同次保存且 canonical messages 未改。A／checkpoint／runtime／chat／背景提示相鄰離線回歸 134 項通過；唯一警告是測試環境無法寫 `.pytest_cache`。未修改 `JdNoticeMiddleware`、Prompt、Memory、Working State 或 B1／B2，未讀 key、未呼叫 provider。下一步才是 B2 attempt-scoped 接線。

> **2026-09-17 G7 背景 Agent 接線結果：**package 的 B1／B2 state 現承載可選 App-owned middleware；fresh start／new attempt 清空 `continuation_compaction`，same-attempt resume 與完成結果查回保留既有 state。`build_background_memory_workflow()` 以原 `case_model`／`understanding_model` 物件建立各角色 middleware，summary 直接呼叫該未綁業務 tools 的 injected model，主 Agent 才由框架綁工具；這是 App-side model-object identity 證據，不是正式 OpenRouter／Luna factory 或 provider wire 證據。固定合成模型＋真 Agent graph／Saver 測試另證明 B1 正常單一窗口即使多個工具 wave 也不摘要，多窗口只把第一個已完成窗口送 summary、第二個未處理窗口逐字保留，canonical graph messages 不混入 summary 且兩個 window／signed source 仍可讀回精確原文；B2 同 attempt transport failure 後恢復固定任務與 summary，新 attempt 首次 request 無舊 summary。fresh 精確受影響回歸為 App **52 passed／0 skipped**、package **50 passed／0 skipped**，兩邊 compileall 成功。這些測試沒有涵蓋完整 publication／JD byte-for-byte unchanged-state，也沒有 provider／credential／network、Prompt／Skills／Memory／C、DB／schema／migration／dependency 變更。

> **2026-09-22 角色化摘要與 reasoning successor 結果：**回看 A 訪談 Working State、完整工作分析／JD 寫作、B1 案例維護、B2 工作理解及跨 Agent 證據契約後，確認共用 compaction 元件與 authority 邊界不變，但三個角色不能只共用一段沒有角色目的的通用摘要指令。既有 `CompactionProfile` 現已加入角色專用 retention instructions；B2 摘要模型另把逐字保留的固定任務當作唯讀 orientation。沒有新增 Agent、Memory、資料表、schema compiler、第二套摘要狀態或新的 boundary policy。Opaque `reasoning_details` 不送入 Caliburn semantic summary、也不升格為 Memory／evidence／JD basis；未被 boundary 覆蓋的近期 canonical tail 維持完整 `AIMessage`。零付費 checkpoint／request-view characterization 已證明該 metadata 原樣保留，沒有出現需要「額外保留最近 completed wave」的反例，因此維持既有安全工具 wave 與最近八則訊息規則。
>
> **2026-09-22 真 Luna prompt 品質 successor：**首輪角色化實測確認 B2 仍會把 `protected_orientation` 改寫成摘要目標，原因是共用「保留目前目標」與 B2「不重述 orientation」互相拉扯。現行規則已收斂為：所有角色只記錄受控輸入明確支持的狀態，未提及不能推論為未完成／沒有發生／沒有待辦／已確認；B2 summary 只保存相對於 fixed task 的新進度、差異及未解事項，不能另列目標、限制或下一步來重抄、改寫或概括 orientation。這只調整既有 summary instructions，不新增後處理器或 rejection／retry loop。真 Luna 兩請求重測已證 fixed task 不再重複、支持／反證／例外仍保留；精確證據見[元件優先驗收](evidence/2026-09-22-jd-component-first-acceptance.md)。

> **2026-09-22 A 同回合工具迴圈 successor：**真 Luna JD 成文驗收在同一則員工輸入後自然執行 24 次工具判斷與 1 次 final；durable canonical messages 的離線輸入下界約 78,816 tokens，卻因 `protect_latest_human_turn` 把最新 `HumanMessage` 之後整段都排除而沒有 safe boundary。這與本稿「完成 wave 可壓縮、最新員工原話逐字保留」的效果要求不符。現行最小 successor 沿用同一 middleware、summary、digest、checkpoint 與 16K 門檻：A 將最新員工訊息作 Runtime 推導的逐字 `protected_orientation`，其後已完成 wave 可進累積摘要；B1 仍保護整個未處理窗口，B2 仍保護固定任務。state format v2 只新增 Runtime-owned `protected_message_id`，不由模型填寫，也不新增 Agent、資料表或第二種 compaction。原失敗 run 的同一 canonical history 現可選出第 41 則安全邊界；精確證據見[元件優先驗收](evidence/2026-09-22-jd-component-first-acceptance.md)。

## 1. 決定與產品效果

採用 **LangChain／LangGraph → OpenRouter → OpenAI-only route → Luna** 的既定單一模型路徑，在 App 內加入一個薄的、非破壞式 `ContinuationCompactionMiddleware`：

```text
canonical conversation（Saver，完整且唯一）
    ↓ 只讀
選出已完成、可安全切割的舊對話前綴
    ↓ 同一 OpenRouter／Luna，獨立摘要 request
continuation_compaction = 摘要文字＋涵蓋邊界＋來源指紋
    ↓
本次模型 request view = 必要的固定任務原文＋continuity summary＋未涵蓋尾段＋當次 JD／Memory context
```

這個摘要只回答「對話／工作目前進行到哪裡、已完成什麼、下一步是什麼」。它不是員工原話、訪談詳記、工作資訊候選、工作理解、JD 或 publication basis。canonical conversation 不被刪除、改寫或用摘要取代；既有原話、詳記與 Memory 回查一律讀原 owner。

本輪不切 direct OpenAI，不把 OpenRouter key 傳給 OpenAI endpoint，不新增 fallback，也不再把 OpenRouter 原生 inline compaction 當成 App 可用的前置條件。OpenAI Responses 的 native compaction 可保留為未來 provider optimization；若日後採用，仍須轉成相同 request-only 效果並通過本稿驗收，不能改變資料 authority。

## 2. 為什麼不是重做一套 Memory 或摘要框架

| 元件 | 本輪處理 |
|---|---|
| LangChain／LangGraph | 繼續負責 agent loop、Tool 配對、middleware、state reducer、Saver／Store 與恢復 |
| OpenRouter／Luna | 產生顧問回答及需要時的 continuity summary；沿同一 route／receipt／成本邊界 |
| Caliburn 薄 middleware | 只負責安全切點、摘要狀態、request-only view 與失敗語意 |
| 分層 Memory | 沿 MEM-L001 的案例／案例 guide、工作理解／理解 guide、C 即時修補及共同 publication，完全不由 continuity summary 取代 |

不直接採 LangChain `SummarizationMiddleware`，因鎖定版本會以摘要與尾段更新 graph `messages`，不符合 canonical 原文不可被有損投影覆寫的要求。第一個切片也不直接採 Deep Agents summarizer：其額外 history offload 與 overflow 分支超出本次薄接合；`ExtendedModelResponse` 的 middleware 組合則由鎖定的 LangChain 1.4.0 原生承接，不是拒用理由。LangMem 目前未安裝，且既有研究已找到多工具切點與保存時點仍需產品接合；第一版不為了包住相同缺口新增依賴。

這不是另寫 agent loop、tokenizer、Checkpointer 或工作理解引擎。只使用公開 middleware／`ModelRequest.override`／`ExtendedModelResponse`／`Command`／模型 Runnable 接點；不複製框架 private helper。

## 3. 本 compaction 切片新增的衍生狀態

在各 agent 的 typed state 增加一個可為空的整體欄位；欄位名稱與最小內容固定如下：

```json
{
  "continuation_compaction": {
    "format_version": 1,
    "summary_text": "...",
    "covered_through_message_id": "...",
    "covered_prefix_digest": "sha256:...",
    "protected_message_id": null
  }
}
```

- `summary_text` 與涵蓋邊界必須作為同一個 state value 更新，不能只前移位置或只保存文字。
- `covered_through_message_id` 指向 canonical conversation 中實際存在的安全終點。
- `covered_prefix_digest` 由該次已涵蓋 canonical prefix 的穩定序列化產生，用來攔截邊界指錯、內容暗變或跨文件重用；模型不填這兩個欄位。
- format v1 維持原連續 prefix 語意，`protected_message_id=null`；A 的 format v2 由 Runtime 填入 covered prefix 中唯一且最新的員工 `HumanMessage.id`。摘要不包含該訊息，request view 則把原訊息逐字放在 summary 前。ID 不存在、重複、不是 `HumanMessage` 或不是該 prefix 最新 HumanMessage 時 fail closed。
- B2 的初始任務訊息由固定 role profile 從 canonical attempt messages 推導並逐字保留，不複製進此 state，也不增加一個可由模型填寫的 identity 欄位；digest 仍涵蓋它所在的 canonical prefix。
- 不建立新的 SQL table、原文副本、詳記副本或第二個 publication head。此 state 由既有 Checkpointer 按原 thread／attempt 保存。
- request view 是臨時值，不另存完整副本。只保存能重建它的 summary 與邊界。

若狀態格式、message id、digest 或 scope 不一致，視為 `invalid_continuation_compaction`。仍在安全輸入預算內時可忽略壞的衍生摘要、以 canonical view 繼續並留下診斷；已超出安全預算時必須明確失敗，不能猜切點、刪原文或無界重送。

## 4. 安全切割與增量摘要

### 4.1 切割單位

middleware 只摘要**已完成的舊互動 wave**。「完成」是指一組模型／工具往返已在 checkpoint 中完整配對，不是整個 A 回合或整個 B2 attempt 已經結束：

- A 的最新員工訊息在該回合始終逐字保留；它本身不進摘要，但它之後已完整配對並離開近期尾段的舊模型／工具 wave 可以進摘要。當前尚未完整配對的 wave 與最近八則仍逐字留在尾段；不能因整個 A 回合尚未 final 就阻止前段已完成工作被壓縮；
- B1 正常以一個完整 canonical 訪談 batch 工作，不固定觸發摘要；若因來源交付或模型限制使用多個窗口，最新 `HumanMessage` 所帶的尚未完整處理窗口必須逐字留在尾段。前一窗口只有在其模型／工具 wave 安全完成、Runtime 已將 `window_position` 推進並保存 checkpoint 後，才可連同該舊 wave 納入後續 request-only compaction；不是只因訊息較舊就可壓縮；
- B2 的第一則 `HumanMessage` 是本 attempt 的任務原文，整個 attempt 期間都逐字固定在 request 開頭。它不會因「任務尚未完成」而阻止後續已完成的舊工具 wave 被摘要；
- 不切開 `AIMessage.tool_calls` 與所有對應 `ToolMessage`；
- 不切開同一次模型回覆的平行工具結果；
- 終點必須位於沒有 pending tool call 的完成邊界；
- 至少保留最近八則可壓縮訊息；B2 固定任務原文另計。若八則會拆開一個完整 wave，尾段向前擴大到安全邊界；
- 找不到安全切點時不生成新摘要。若因此無法形成安全 request，回報明確錯誤，不以任意最後 N 則替代。

已存在有效 summary 時，只把「舊邊界之後到新安全邊界」的增量連同前一版 summary 交給摘要模型，產生一份新的累積 summary；不每次重讀從第一則開始的全部原文。舊 summary 是可替換的衍生狀態，不形成版本歷史產品功能。

### 4.2 摘要內容

摘要 prompt 與主顧問 Prompt 分開；本輪不修改已校準的顧問訪談 Prompt。摘要指令沿既有顧問 runtime 已使用的「non-authoritative conversational continuity」原則，至少要求：

- 保留目前訪談／整併目標、已確認的更正、尚待回答事項；
- 保留已完成 Tool 的真實結果及後續仍需配對的名稱／識別，不把 request 當成成功；
- 保留不確定性、衝突與失敗，不補造員工未說的事；
- 不把摘要宣稱成 employee evidence、Memory、JD 或 source of truth。

若 A 另有 `CTX-W001` 的 current Focus／待追查項目，摘要可保留當時與對話延續有關的簡短投影，但不用複製完整 item collection；下一次 request 仍由 Runtime 從獨立 Working State 注入最新 orientation。摘要未提到某 item，不能據此刪除或視為已解決。

摘要模型不取得 JD 編輯、Memory 修改、背景通知或其他業務 Tool。它只收到上一份 summary 與選定的 canonical prefix。

### 4.3 共用不變量與三種角色保留規則

本產品只保留一個 `ContinuationCompactionMiddleware`、一個 `continuation_compaction` state shape 及一套 safe-boundary／digest／發布流程。角色差異只放在既有 `CompactionProfile` 的 summary instructions，不建立三個 compactor、三套 prompt engine 或新的角色狀態。

共同摘要必須保留可觀察且續作需要的：目前目標、已確認更正、已完成工具效果、未解問題、衝突／失敗、承諾及下一步；不得保存隱藏推理、補造事實、把 tool request 當成功，或複製會由 Runtime 重新注入的完整 JD／Memory／Working State。再按角色補下列重點：

| 角色 | 角色專用 retention instructions | 明確不做 |
|---|---|---|
| A 主顧問 | 目前訪談焦點與完整工作覆蓋缺口；員工已確認事實、更正、未知／衝突與尚缺資訊；最近問答進度；已完成 JD／Working State／來源讀取的真實結果；背景整理只能記「已通知／receipt」，不能記成已完成；下一個適合詢問或處理的步驟 | 不複製完整 Working State、JD 或 Memory；不把每個分析面向變成固定問卷；不把摘要當員工原話 |
| B1 案例維護 | 本次來源／窗口的處理位置；案例身分與差異；觸發、輸入、本人行動、判斷、成果、分工、條件、例外、更正、時間範圍與未知；已讀 evidence keys；staged create／revise／split／merge／retire／route、驗證結果與下一步 | 不把案例直接抽象成穩定工作理解；不摘要尚未完整處理的最新訪談來源；不以 summary 取代 canonical 引用 |
| B2 工作理解 | 固定任務與 base orientation；B1 change set；已讀案例／理解及其支持、反證與差異；共同穩定任務、責任、條件、例外及未知；staged create／revise／revalidate／split／merge／retire／route、case rework、衝突與下一步 | 不修改案例；不把單一案例條件誤寫成共同模式；不因某一案例改變就假定其他案例也改變；不以 summary 取代案例／原話回查 |

這些 retention instructions 是 continuation 的選材規則，不是 A／B1／B2 主 Prompt 的副本。摘要只記「繼續工作不可缺少的狀態」，完整工作與 JD 品質仍由主 Prompt、Skills、Working State、案例／理解 artifacts、guides 及按需讀取共同完成。

### 4.4 B2 固定任務與 A 最新員工輸入只作唯讀 orientation

B2 的首個固定 `HumanMessage` 仍由 `preserve_initial_messages=1` 逐字放在每次主 request 的 summary 前，且不被 summary 覆蓋。摘要 request 另把同一則**既有 model-visible 原文**放入 `protected_orientation`，讓摘要模型知道此次 attempt 的固定目標、base 與 B1 change set，據此判斷哪些舊工具結果及未完事項值得保留。

- `protected_orientation` 不計入新 summary 的 covered incremental messages；
- 不建立縮短版 task、第二份 task state 或新的持久欄位；
- summary 不必重抄整份固定任務，且不得改寫其內容；
- B1 的 `preserve_initial_messages=0`，且未處理窗口仍由 latest-turn boundary 保護；A 不固定保留第一則訊息，而是由 Runtime 從當前 canonical messages 推導最新員工 `HumanMessage`。只有 safe boundary 已越過該訊息時，A 才把它作動態 `protected_orientation` 並發布 format v2；模型不選 ID；
- 任務內若含 Runtime-issued handles，它們仍只在原 attempt／scope 有效，summary 文字不能延長其權限。

採逐字既有 model-view，而不是另做「精簡 B2 任務投影」，是為避免新增一份可能遺漏或漂移的語意轉換。若日後實測證明固定任務本身造成不可接受的預算壓力，再以具體 token／品質證據重開；第一版不先猜測並新增抽取器。

A 的動態 orientation 同樣逐字取自 canonical message，不建縮短版。當下一則員工訊息進入且新 safe boundary 前移時，前一則受保護訊息會作為受控增量併回累積摘要，新訊息接替成為唯一逐字保護項；因此不會永久累積每一輪原話，也不會在換輪時靜默遺失前一輪員工要求。

### 4.5 Reasoning continuation 與 semantic summary 的界線

Reasoning 是 provider／模型延續用的 Context，不是產品權威資料。Caliburn 採以下單一政策：

1. canonical message／checkpoint 沿框架既有 serializer 保存已收到的 `AIMessage.additional_kwargs`；不因 compaction 物理刪除 provider metadata；
2. 尚未被 boundary 覆蓋的近期 tail 以 deep copy 原樣進主 request view，鎖定 `langchain-openrouter==0.2.7` 負責把 `reasoning_content`／`reasoning_details` 序列化回 OpenRouter；
3. safe boundary 不切進未完成的 tool call／result wave；A 逐字保護最新員工 HumanMessage 但允許其後完成 wave 壓縮，B1 則保護最新未處理 Human turn／來源窗口；
4. boundary 以前的 completed old reasoning 不送入 Caliburn summary model，也不轉寫成可見的「推理摘要」；續作所需結論必須已出現在可觀察對話、ToolMessage、Working State、Memory、JD receipt 或 continuation summary；
5. summary 只能承接可觀察的 task state、工具結果、未解事項及下一步，不建立 Reasoning Memory、Reasoning DB 或 reasoning evidence；
6. 未來若 provider route 真正提供且驗證 native reasoning-aware compaction，可作 transport optimization，但仍不得改變 canonical／Memory／JD authority。

正式零付費測試已固定這條 client contract：鎖定 adapter 收到 `reasoning_details` 後放入 `AIMessage.additional_kwargs`，`message_to_dict／messages_from_dict` 與未被覆蓋的 request tail 都保留它；`_summary_input()` 則刻意排除 opaque 值。這只證明客戶端 checkpoint／request-view 路徑，不冒稱每次真 Luna 都一定回傳 reasoning metadata，也不把 source inspection 冒稱新的 provider smoke。測試沒有顯示 `keep_messages=8` 會切掉當前未完成工具 wave，因此沒有增加另一個 token／wave retention policy。

## 5. 預算、呼叫與保存時點

- 第一版沿既有 OpenRouter 顧問政策，以完整 request 約 **16,000 input tokens** 作摘要觸發起點，保留至少八則近期訊息；這兩項放入 role profile，不散落硬編碼。
- 每次先驗證並套用上一份有效 compaction，組出本次**實際準備送出的 request view**，再判斷是否超過門檻；不能因 Saver 中仍有較長 canonical history 就每次重做摘要。
- 實際 request 的預算判斷必須包含 system／developer instruction、JD／Memory context、Tool schemas、B2 固定任務原文、continuity summary、未涵蓋尾段及輸出預留，不能只數 canonical `messages`。
- continuity summary 輸出第一版上限 **2,048 tokens**。每個 model step 最多觸發一次摘要，不因摘要內容不滿意自動再問。
- summary request 使用同一個 OpenRouter model factory、OpenAI-only provider restriction 與 no fallback；SDK hidden retry 為 0。它必須沿同一次 graph invocation 的 callbacks／runtime context，讓自己的 route 與 usage 可觀察，不能偽裝成主模型沒有額外呼叫。
- 目前新 App 真實已有的是 model／tool call ceiling、單次輸出上限、request timeout、零 hidden retry、`stop_event` 與模型回覆的 usage metadata；**現碼沒有一套持久的通用美元費用帳本**。本切片不把不存在的帳本寫成既有能力，也不為 compaction 另造通用計費系統。付費 smoke 仍使用每次另行核准的外送次數與費用上限。
- 摘要前先檢查停止訊號；摘要請求沿用既有取消 callback；摘要回來後、主模型送出前再檢查一次。若此時已取消，不得再送主模型；已發生的摘要呼叫仍在實測 usage／外送次數中照實列出，但不保存新的 compaction state。
- v1 不為摘要另加一個持久工作節點。摘要成功且主模型成功時，由同一 model step 的 `ExtendedModelResponse` 保存「模型結果＋summary／boundary」；主模型失敗時新摘要不推進，canonical 與上一個已保存摘要保持不變，恢復時只可在既有 model-step／recovery 次數界線內重算，不自動重試摘要。這是明示的有限重算，不宣稱 exactly-once。

## 6. A、B1 與 B2 的生命週期

### A：文件唯一對話

- `continuation_compaction` 位於 `ConsultantState`，跟隨該文件既有 `thread_id=document_id` checkpoint 跨回合恢復。
- A 的正式 `graph.invoke(..., durability="sync")` 每輪只提交新 `HumanMessage`，同一 `thread_id` 由 Checkpointer 恢復前輪 state；跨回合與關閉重開後取回 compaction 是既有呼叫鏈上的驗收，不是另一套保存設計。
- A 的最新員工 `HumanMessage` 是逐字 orientation，不是 summary source。若 16K 門檻在同一回合工具迴圈內觸發，Runtime 可摘要該訊息之後已完成的舊 wave；下一輪新的員工訊息進入後，舊 protected message 才併入累積摘要並由新訊息接替。
- 每個 model step 先由既有 `JdNoticeMiddleware` 組入當次 JD／source／Memory context，再由 compaction middleware 以完整 projected request 判斷預算；它只替換送模型的 `messages` view。
- summary 不進 `source_notice`、B1 source window、Memory reader 或 JD `basis_refs`。
- 不同文件的 runtime context、thread、summary、boundary 與 digest 不得互用。

### B1：一個固定 batch 的案例維護 attempt

- 能在一次 request 內完整交付並完成的正常 batch 不需要固定摘要呼叫；只有套用既有 summary 後的真實後續 request 達門檻，才執行 compaction。
- 若同一 batch 必須分成多個來源窗口，當前最新窗口與未完成工具配對保持逐字；上一窗口在安全完成並由 Runtime checkpoint 推進後，才成為可壓縮的舊 Context。這沿用現有 graph 的 `window_position`／完成邊界，不增加讓模型填寫的處理狀態。
- 「已處理」不等於「一定已被案例引用」。重複、無關或經判斷不需修改案例的來源仍可能合法完成；反之，只有引用存在也不能取代安全完成與 checkpoint 邊界。
- 被壓縮的是後續模型 request view，不是 canonical source。原始訪談、signed references、evidence registry 與 staged 案例仍完整保存；B1 對摘要有疑問時沿既有按需來源讀取回查原文，summary 不得作 evidence。
- 新 stale attempt 從空的 `continuation_compaction` 開始；不得把舊 base 的工作摘要當成新版案例判斷。

### B2：單次有界整併 attempt

- 使用相同 middleware 行為，但 state 只存在於該 B2 attempt 的 graph／checkpoint。
- 每次 attempt 唯一的初始任務 `HumanMessage` 始終逐字放在 summary 前；summary 只涵蓋它之後已完整配對的舊模型／工具 wave，當前未完成 wave 保留在尾段。因此 B2 可在任務尚未結束時壓縮，不必等 publication 完成。
- 同一 attempt 中斷後可沿原 state 恢復。
- publication stale 後既有流程建立新版重整 attempt；新 attempt 從空的 `continuation_compaction` 開始，只讀新版 Memory 及 runtime 受控提供的更正來源。不得沿用舊 attempt 的 summary、opaque context 或工具尾段。
- B1 依 `MEM-L001` 已升格為可多步讀寫的案例 Agent；上節已固定其未處理來源保護、已處理舊窗口與 attempt scope。B1 不使用 continuity summary 或 A 的 Working State 作來源，summary 只協助續作。

## 7. Middleware Command 組合：由鎖定框架承接，先驗收而非先改碼

目前 A 的 middleware 順序讓 `JdNoticeMiddleware` 位於外層，compaction 位於內層；這可確保摘要預算看見已組入的 JD／Memory／Tool context。先前曾誤判內層 `ExtendedModelResponse` 會直接傳入外層 `_bound_response()`，因而要求修改 `JdNoticeMiddleware`。

依鎖定的 LangChain 1.4.0 實際 `_chain_model_call_handlers()`：框架會先取出內層 `ExtendedModelResponse.command`，只把其中的普通 `ModelResponse` 傳給外層 handler，最後再以 inner-first、outer-last 累積兩層 Commands。因此現有 `_bound_response()` 接受 `ModelResponse` 是正確的；`continuation_compaction` 與 `jd_model_view` 是不同欄位，也沒有 reducer 衝突。**本切片不先修改 `JdNoticeMiddleware`。**

G7 只補一條使用真實 `create_agent` 組裝順序的整合反例，證明同一次 model step 後兩個欄位都保存、canonical `messages` 沒被 compaction command 更新。只有這條測試以鎖定版本重現實際遺失或衝突時，才提出最小程式修正；不能只看單一 `_bound_response()` 函式推定框架行為。

B2 沒有 A 的 JD notice，但仍用相同 compaction state 與 request-only 不變量。既有 `native_context_view` 保留作 Responses adapter 的已驗歷史接縫與 characterization test，不接進新 OpenRouter 正式路徑，也不刪除其證據。

## 8. 失敗與禁止降級

| 情況 | 唯一允許行為 |
|---|---|
| 未達門檻 | 不呼叫摘要模型，沿既有 request |
| 找不到安全切點 | 不移動邊界；仍可安全送出則繼續，否則明確失敗 |
| 摘要呼叫失敗／截斷／拒絕 | 不保存新狀態、不刪原文；依本次既有有限預算失敗 |
| 主模型在新摘要後失敗 | 不推進新摘要；恢復時可在既有次數界線內有限重算，已發生的摘要 usage／外送次數不能當作零 |
| 摘要期間或摘要後取消 | 停止訊號立即生效；摘要完成後不得再送主模型，新摘要不保存，已發生呼叫照實列入使用量 |
| summary／boundary 損壞 | 不猜、不跨 scope 使用；安全預算外明確失敗 |
| OpenRouter 未來產生 native item | 不自動混用；另經相同契約驗證後才可作 adapter optimization |

禁止的替代方案：長期每輪重送全部原始訪談、刪除 canonical messages、把 summary 餵給 B1 冒充原話、把 summary 變成第二套 knowledge、切換 credential／provider、無界摘要重試，或為了通過測試把工具結果／目前員工訊息藏在 system prompt 重複提供。

## 9. G7 最小施工與驗收

原施工 1–4 與 2026-09-22 successor 的第 5–6 小步均已完成離線驗證；沒有重做舊切片，也沒有以此自動執行新的付費 smoke：

1. 新增 typed compaction state、公開 middleware 與 profile 設定；不加 dependency／table／migration。
2. 正式 A 注入新 middleware；以鎖定 LangChain 的真實組裝測試證明 `jd_model_view` 與 `continuation_compaction` 同時保存，不預設修改 `JdNoticeMiddleware`。
3. B1／B2 各自使用 exact injected role model object 與 role-scoped／attempt-scoped middleware；B1 正常單一 batch 不固定摘要，多窗口時只允許已安全完成並 checkpoint 推進的舊窗口進入 request-only summary，當前未處理窗口逐字保留；B2 的固定任務原文與 stale 新 attempt 邊界保持本稿規則。正式 OpenRouter／Luna role-model factory 已由 successor 離線完成，舊 direct Responses／native `context_management` 不接回正式路徑；舊 adapter 契約測試保留作歷史證據。
4. 已跑受影響離線回歸與 compileall；付費／自然 smoke 仍須另依費用授權，不在本文件切片讀 key 或呼叫 provider。
5. reasoning-continuity characterization 已固定：checkpoint round-trip 與 request-only tail 保留近期 `reasoning_details`，summary projection 不包含它；既有行為成立，因此未修改 serializer／adapter／boundary。
6. 既有 profile／prompt seam 已補 A／B1／B2 retention instructions 與 B2 `protected_orientation`；只修改共用 compaction 模組及受影響測試，沒有修改主 Prompt、Memory／JD、Agent graph 或 provider factory。

最少固定反例：

- Saver 重載後 canonical messages 逐項未變，summary＋boundary 可重建相同 request view；
- 最新員工訊息與多工具 call/result wave 不被切開；
- B2 任務原文逐字固定，任務尚未結束時仍可摘要其後已完成的舊工具 wave；
- 已有 summary 的下一次只摘要增量，不重送全歷史給摘要模型；
- 是否再摘要以本次真正送出的 view 計算，不以 canonical history 總長度觸發；
- summary 成功／主模型失敗不前移狀態，恢復重算受既有次數界線約束；
- 摘要前取消不呼叫 provider；摘要後取消不再送主模型，已發生摘要 usage 可觀察；
- A 同時保存 `jd_model_view` 與 `continuation_compaction`；
- A 跨回合恢復且兩文件隔離；
- B1 單一正常 batch 不產生不必要的摘要呼叫；多窗口時，未處理的最新窗口逐字保留，只有 Runtime 已推進的舊窗口可壓縮，且壓縮後仍可沿正式引用讀回原話；
- B2 同 attempt 恢復，stale 新 attempt 不帶舊 summary；
- summary 不是 source／Memory／JD basis，不能取代 B1 canonical 訪談或引用；
- 完整 request 預算、輸出上限、OpenAI-only／no-fallback 與 usage receipt 均可觀察。
- A／B1／B2 的 summary request 分別取得正確 retention instructions；通用規則與角色規則不互相覆蓋；
- B2 摘要可看到逐字固定任務作 `protected_orientation`，但該任務仍逐字留在主 request、沒有被 summary boundary 吞掉或複製成第二份持久 task；
- recent tail 的 `reasoning_details` 經 checkpoint／request view／OpenRouter serializer 原樣保留，covered old reasoning 不進 semantic summary，也不形成 evidence／Memory／JD basis；
- 角色摘要對完整工作與 JD 品質只保留續作線索：A 保留待訪談缺口，B1 保留案例差異／更正，B2 保留跨案例支持／反證；不把十四分析面向、完整 artifacts 或 guides 全量複製進 summary。

本切片的直接證據為：compaction／adapter／背景 Agent **29 passed**，A／App 組裝與相鄰 context **55 passed**；排除本機 ACL 會阻擋的 Credential Manager／operator 兩個測試模組後，新 JD App 其餘完整離線套件為 **3061 passed／322 skipped／0 failed**。另有一項既有 Memory repair 測試只縮窄故障注入時點，使其仍在 `repair_memory` 綁定而非較早的合法 evidence projection 觸發；產品程式未因該測試修改。這些結果代表 A／B1／B2 的 App-side compaction 接線、角色摘要及 client-side reasoning continuity 契約通過；不代表正式 16K 自然長訪談、每次真 Luna 都返回 reasoning metadata、provider-native compaction 或付費摘要品質已由本切片驗證。其他 dispatcher、完整 App 與真模型旅程狀態以 `docs/current-decisions.md` 較新的驗收條目為準，本稿不保存第二份總狀態。

## 10. 官方交叉核對與本案選擇

本稿在施工前重新核對 OpenAI、Anthropic 及鎖定框架文件／原始碼。可稱為跨來源共同原則的只有：長任務要主動管理 active context、摘要／compaction 應保留續作所需目標與未完事項、持久 Memory 與 context compaction 是不同責任，以及工具互動不可因裁切失去配對。各家沒有共同規定 Caliburn 必須採用同一個 summary schema、message boundary、digest 或 publication 方式；這些是本產品為了 canonical 原話、JD／Memory authority 與恢復需求所作的選擇。

- OpenAI 的 [Compaction 指南](https://developers.openai.com/api/docs/guides/compaction)與 [長任務模型指引](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.5)支持在長任務中壓縮工作上下文，保留已完成動作、有效假設、識別資料、工具結果、未解阻塞與下一目標；原生 opaque item 是 Responses transport 能力，不等於本產品的工作理解 Memory。
- OpenAI Agents SDK 的 [`OpenAIResponsesCompactionSession`](https://openai.github.io/openai-agents-python/ref/memory/openai_responses_compaction_session/)明確把 user messages 排除在 compaction candidates 外；這支持「員工輸入保留、其餘已完成工作可壓縮」，不代表 Caliburn 必須採其 Responses transport 或改寫 canonical history。
- OpenAI 的 [Reasoning 指南](https://developers.openai.com/api/docs/guides/reasoning#keeping-reasoning-items-in-context)建議函式呼叫期間保留最近使用者訊息以後的 reasoning／function call／output items；原生 Responses 能自行判斷可用 reasoning，不代表 App 應將 opaque metadata 轉寫成產品摘要。
- Anthropic 的 [Compaction on demand](https://platform.claude.com/docs/en/build-with-claude/compaction-on-demand)、[Context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing)、[Context windows](https://platform.claude.com/docs/en/build-with-claude/context-windows)與 [Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)同樣把 active-context 縮減與可按需讀取的持久資料分開，並允許保留近期 thinking／工具配對、清除較舊 completed tool results；這支持 hybrid retention 與責任分離，不代表其 server-side summary 格式或固定保留數量可直接當成本 App 契約。
- LangChain 的 [Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)、[Built-in middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)與 LangGraph [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)提供 request override、state update、summary middleware 與 checkpoint primitive。鎖定的 LangChain 1.4.0 built-in summarizer 會用 summary＋tail 更新 `messages`，所以本案不用它覆寫 canonical conversation；同版 factory 原始碼則證明不同 middleware 的 `Command` 可累積，故不先修改 `JdNoticeMiddleware`。

因此，官方資料支持本稿的責任切分與安全目標；「canonical messages 永久保留、衍生 summary 另存、B2 起始任務逐字保留、digest 驗證、摘要與主回答同 model step 發布」仍是 Caliburn 的產品／工程決策，不冒充大廠唯一共識。

## 11. Memory 分層參考的界線

OpenAI 官方目前只直接說明：Codex 會在背景從合格的既有聊天產生本機 memory files，跳過 active／short-lived sessions；生成資料包含 summaries、durable entries、recent inputs 與 supporting evidence，且 extraction／consolidation model 可分別設定。這支持「原始對話、抽取產物、整併結果與導覽用途分開」，但沒有規定 Caliburn 必須採相同 schema、同一版號或 publication CAS。[OpenAI Docs：Memories](https://learn.chatgpt.com/docs/customization/memories#how-local-codex-memories-work)

Caliburn 的詳記重抽另存、穩定引用、publication head 與本回合讀取基準，繼續以本案既有 Q019 設計／程式／測試為 authority。討論者提供的 Codex source trace 可作研究佐證，但未進官方文件的內部欄位與 upsert 行為不得寫成 OpenAI 對本產品的契約。
