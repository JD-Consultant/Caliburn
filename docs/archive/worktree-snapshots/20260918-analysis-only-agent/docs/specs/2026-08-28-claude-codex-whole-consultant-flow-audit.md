# Claude／Codex 整體顧問流程回歸審核

- **日期**：2026-08-28
- **狀態**：Working Research；先供產品大方向對齊，不是實作授權或 Accepted ADR
- **範圍**：從員工開始／恢復訪談，到 Context、工作理解、JD 編輯、驗證、待審、失敗恢復與下一輪續談的完整生命週期
- **不在本輪**：RAG／Reference、能力級別與 A、正式 eval、多 Agent、auto-accept、production code 修改

## 0. 結論先行

Caliburn 最新大方向與 Claude Code／Codex 的成熟 agent 產品方法**整體一致，不需要因本輪研究重寫產品流程或更換 runtime**：

1. 不是一次 prompt 直接產生最終文件，而是 durable session／thread 中的一位主顧問，以 Tool-feedback loop 持續理解、行動、驗證與回覆。
2. session history、送入模型的 Context、可修訂工作理解、目前 JD workspace 與員工核准權分層；不能把聊天摘要當產品記憶，也不能讓模型直接寫核准文件。
3. 固定規則保持精簡；詳細職務分析方法、來源、JD 區塊與 Tool schema 按需載入。
4. AI 與員工面對同一份目前 JD；AI 變更以 semantic diff 待審，員工接受後才提升到 approved baseline。
5. ordinary ambiguity 留在可修訂工作理解；只有無法安全繼續的阻塞歧義，才暫停並要求員工確認。
6. 不建立固定 wizard、百分比、model-owned Agenda 或每輪必跑 JD 階段；一個 product run 可依需要有多個 model／Tool step。

本輪找到三個應明確補強的跨流程項目，但都不應新增 semantic authority：

1. **本輪結果摘要**：每輪結束時，由已提交的 understanding delta、JD diff、required input、Focus 與 receipt deterministic 投影「這輪理解了什麼、改了什麼、還要處理什麼」。不是讓模型另寫一份摘要記憶。
2. **技術執行狀態與訪談概況分離**：`已收到訊息 → 正在整理理解 → 正在檢查／編輯 JD → 正在驗證 → 完成／需要確認／失敗` 是短暫執行狀態；「目前訪談重點、待釐清、待補充／目前足夠、待審數」才是跨輪語意概況。兩者不得混成假進度條。
3. **終止狀態必定解除寫入鎖**：成功、需要確認或失敗都必須進入可識別 terminal state。失敗時保留已先寫入的員工訊息與安全提交結果，回滾未完成 stage，解除 composer／JD 鎖，允許重試或直接送新訊息；不能只剩「重試」。

## 1. 審核方法與來源限制

本輪只把 Claude／Codex 當作**成熟 agent 產品與 harness 方法的佐證**，不把 coding 名詞直接搬成職務分析 domain：

- Codex 的 repository／Git diff／stage／worktree，對應的是「同一 current workspace、可檢視差異、可復原與人類 authority」的產品原則，不代表 JD 要模仿 Git 資料模型。
- Claude 的 file checkpoint，對應的是「agent edit 可復原且與 durable session 分離」，不代表每個 JD 欄位要建立檔案快照。
- 兩者的 auto memory 是 recall layer，不足以承接需要 source、revision、lineage 與 deterministic validation 的工作理解。
- 兩者的 Agent SDK／app-server 是 runtime 候選，不會替 Caliburn 定義 Task／Duty／OPKS、工作理解或員工核准語意。

主要官方來源：

- OpenAI，[Codex as a platform](https://developers.openai.com/blog/codex-as-a-platform)（2026-08-19）：agent harness 負責 context、Tool、進度、失敗與 approval；host application 保留工作專用 UI、business context、規則、Tool 與 system of record。
- OpenAI，[Unrolling the Codex agent loop](https://openai.com/index/unrolling-the-codex-agent-loop/)（2026-01-23）：一個 user turn 可包含多次模型／Tool iteration；append-only input、prompt cache 與 compaction 是 harness 責任。
- OpenAI，[Unlocking the Codex harness](https://openai.com/index/unlocking-the-codex-harness/)（2026-02-04）：thread persistence、typed item lifecycle、progress event、diff 與 approval request 是 UI／runtime protocol，不是單次 request／response。
- OpenAI，[Harness engineering](https://openai.com/index/harness-engineering/)（2026）：短小索引、結構化 docs、progressive disclosure、mechanical enforcement；遇到失敗應補可觀察能力與約束，而不是只叫模型更努力。
- OpenAI，[Codex Code Review](https://learn.chatgpt.com/docs/code-review)：人與 agent 可在同一 working tree 編輯，以 diff 範圍 review／revert，而不是維護兩份互不相干的文件。
- Anthropic，[How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works)：核心循環是 gather context、act、verify；session durable event history 與有限 context window 分離，先清 Tool output 再 compaction。
- Anthropic，[Claude Agent SDK agent loop](https://code.claude.com/docs/en/agent-sdk/agent-loop)：prompt → model → Tool → result → repeat；同一 user request 可有多個 turn，並受成本／step 上限控制。
- Anthropic，[Claude Code checkpointing](https://code.claude.com/docs/en/checkpointing)：每次 prompt 與 agent edit 有可恢復 checkpoint，且 code／conversation 可分開回復。
- Anthropic，[Claude Code memory](https://code.claude.com/docs/en/memory)：精簡 `MEMORY.md` index 常駐，詳細 topic 按需讀取；持久規則與模型生成記憶分層。
- Anthropic，[Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)：最小充分 Context、低重疊 Tool、固定 orientation＋just-in-time retrieval 的 hybrid 模式。
- Anthropic，[Managed Agents](https://www.anthropic.com/engineering/managed-agents)（2026-04-08）：append-only session log、可替換 harness 與 action/tool boundary 分離；session 不是 context window，harness 可 crash 後從 event log 恢復。
- Anthropic，[Harness design for long-running apps](https://www.anthropic.com/engineering/harness-design-long-running-apps)（2026-03-24）：Planner／Evaluator 對困難長任務可能有效，但 bulky、slow、expensive；每個 harness 元件的假設都可能過時，應逐項證明其必要性。

## 2. Claude／Codex 的共同完整流程

雖然兩者 UI 與 runtime 不同，成熟設計可整理成同一個高階循環：

```text
使用者輸入
  ↓ durable session／thread 記錄
建立當輪最小充分 Context
  ↓
主 Agent：理解目前任務／狀態
  ↓
按需讀取資料、Skills、Tools
  ↓
對同一 working workspace 行動
  ↓
由 Tool／測試／validator 回饋結果或錯誤
  ↺ 必要時有限修正
  ↓
輸出結果、diff、進度或 approval request
  ↓
人類 review／接受／拒絕／修改
  ↓
下一次輸入從 durable state 重新建立 Context
```

這個循環的重點不是 coding，而是五條可轉移原則：

1. **thread/session 是完整事件史；context 只是本次推理切片。**
2. **模型不必一次就對；Tool result 與 validator error 是正常回饋。**
3. **工作發生在真實 working workspace，review 是其差異投影。**
4. **高影響寫入有明確 approval boundary。**
5. **UI 必須忠實顯示 progress、diff、需要輸入與 terminal failure。**

## 3. Caliburn 逐階段對照

| 完整階段 | Claude／Codex 成熟做法 | Caliburn 最新基線 | 審核 |
| --- | --- | --- | --- |
| 開始／恢復 | 以 session／thread 恢復 durable history，不假定整段 history 都在 model context | 每份 JD 一條 durable consultant thread；從 checkpoint／Store 重建 | 符合 |
| 收到輸入 | user event 先進 session，再驅動 agent loop | employee turn 先 durable 保存，之後才啟動分析 | 符合；必須維持 source-first |
| 固定規則 | `AGENTS.md`／`CLAUDE.md` 放穩定規則，保持精簡 | versioned consultant policy＋Skill catalog | 符合；不能把所有分析方法塞 base prompt |
| Context | 小型 orientation 常駐，檔案／Tool／Skill JIT；context 與 durable history 分離 | 本輪原話＋最短近期對話＋相關工作理解＋Focus＋workspace orientation＋pending provenance；來源／JD／Skills 按需讀 | 符合 |
| 主循環 | gather／understand → act → verify，Tool result 回到同一 loop | 先校正工作理解；有局部充分資料時再按需分析／編輯 JD；deterministic feedback 可有限 repair | 符合；不固定兩次模型，也不固定每輪編輯 JD |
| 記憶 | auto memory／notes 幫助 recall，但規則與真實 workspace 另有 owner | Work Understanding 是 source-linked typed semantic collection；不是聊天摘要或 generic memory | 符合，而且比 coding memory 有更強 domain authority |
| 工作區 | 人與 AI 面對同一 working tree；diff／checkpoint 提供 review 與 recovery | 員工與 AI 面對同一目前 JD；approved baseline 不另作第二個可編輯文件 | 符合 |
| AI 寫入 | Tool 直接形成 working change；高影響動作可等 approval | AI 只能修改 pending working values；employee direct edit 依 authority command 處理 | 符合；產品比 coding agent 更嚴格 |
| 審核 | diff、comment、revert／accept，approval 可暫停 thread | semantic atomic group；員工可編輯綠色 after-state，仍須 Accept；Reject 整組回退 | 符合 |
| 必要輸入 | agent 在安全邊界 request approval／user input，session 可恢復 | blocking ambiguity 才用 `需要你的確認`＋LangGraph interrupt；一般問題留 Unresolved | 符合 |
| 進度 | typed event lifecycle、Tool activity、diff 與 final result 分開呈現 | 已有 graph/SSE/receipt 基礎，但需把 technical run status 與 interview progress 明確分層 | **需補強產品投影** |
| 失敗 | Tool error 回到模型；harness／session 可恢復；terminal failure 可重試或繼續 | 每個 authority stage 有有限 repair，失敗 rollback；UI 必須解除鎖並保留 source | 方向符合；**terminal UI invariant 要列一級 gate** |
| 長期續談 | session 可 resume；compaction 只管理 model context | sources、完整理解、JD、review 不作有損 compaction；舊 chat／Tool trace 才可清理 | 符合 |
| 結束 | coding task 常有 done criteria；使用者可再開新 turn | 訪談沒有固定完成點；員工可停、關頁、續談或匯出 | 刻意不同且合理 |

## 4. 建議保留的最新版 Caliburn 整體流程

### 4.1 開啟或返回文件

UI 從同一 durable state 投影：目前 JD、待審變更、目前訪談重點、一般待釐清、coverage、是否需要員工確認，以及上一輪結果。不要求 LLM 先重讀完整聊天或重造摘要。

### 4.2 員工送出一般訊息

1. 先保存員工完整原話；
2. 鎖定 composer 與 JD 寫入，保持單一 writer；
3. 建立最小充分 Context；
4. 同一主顧問更新／修訂 Work Understanding；沒有實質變化就不建新 version；
5. deterministic transition 驗 source、revision、lineage 與 role invariant；
6. 若局部資料已足夠且 JD 真的需要調整，才載入相應 Task／Duty／O／P／K／S Skill 與 JD 區塊，透過受限 Tool 編輯目前 workspace；
7. verifier 回傳成功或 typed error，同一 product run 可在總 step／cost budget 內修正；
8. 成功、需要確認或失敗都結束 active-run lock。

### 4.3 阻塞歧義

如果猜測會產生實質不同的工作理解／JD，且只有員工能決定：先提交本輪可安全成立的 understanding effects，停止相依 JD 工作，在安全 graph boundary 顯示「需要你的確認」。員工答案是新的普通 employee turn；恢復後先校正工作理解，再處理 JD。這與 Codex／Claude 的 approval／input request 同型，但問題語意由 Caliburn 定義。

### 4.4 員工看到本輪結果

顧問自然回覆之外，UI deterministic 顯示簡短「本輪結果」：

- 工作理解：新增／修訂／無實質變化；
- JD：新增或更新幾組待審變更／本輪未動；
- 訪談：目前重點與新形成的待釐清；
- 狀態：完成、需要確認或失敗；
- 下一步：自然續談、審核變更或回答 blocking question。

這個投影只讀 committed transition／receipt，不讓模型另外維護一份 `Progress`、Agenda 或 session summary。

### 4.5 員工審核或直接編輯

- AI 變更：在同一目前 JD 上顯示紅／綠 semantic diff；可直接編輯綠色 after-state，但仍保持 pending；Accept 才提升到 approved baseline，Reject 整組回退。
- 普通 direct edit：沒有 active AI difference 時立即更新目前值與 approved baseline；下一輪顧問只看自上次成功分析後的 JD delta。
- direct edit 與工作理解衝突時，顧問下一輪以聊天追問員工；不靜默把 JD 文字反向當員工工作事實。

### 4.6 自然離開與恢復

員工不需按「本輪可停」。關頁或停止送訊息就是休息。返回時從 durable state 恢復，而不是從壓縮聊天猜測；上一輪結果、Focus、Unresolved 與 pending review 由同一 authority 投影。

## 5. 三項優化的具體邊界

### 5.1 本輪結果摘要不是第二份記憶

推薦來源只有：

- 本輪 committed understanding record IDs／revision；
- 本輪 semantic review group IDs；
- Focus／Unresolved／required input 的 state delta；
- terminal execution receipt。

它可以在 Web projection／API response 中即時計算；若 reconnect 需要同一 timeline，保存的是最小 typed events／receipt，不保存模型自由文字版「我做過什麼」作 authority。

### 5.2 兩種進度必須分開

**短暫技術狀態**回答「系統現在在做什麼」：

```text
received → understanding → document_work → validation
         → completed | needs_input | failed
```

這不是固定模型呼叫數；沒有 JD 工作時可從 understanding 直接 completed。UI 可用自然語句顯示，不必暴露 graph node 名稱。

**跨輪訪談概況**回答「這份職務目前了解多少」：目前訪談重點、Pattern 的待補充／目前足夠、一般待釐清、未定位線索、需要確認與待審數。它不是百分比，也不是單向 stage。

### 5.3 鎖定與恢復

Claude／Codex 支援長 run 中 steer／interrupt；Caliburn 第一版仍採 owner 已確認的短 run 單一 writer：分析中不可送新訊息，也不可編輯 JD。這是避免同一 current workspace 同時被兩方改動的刻意產品選擇，不是落後。

但鎖必須由 terminal event 解除，不能依「最後一段 assistant text 有沒有成功」猜測。第一版不增加 queue、double-texting、parallel branch 或中途自由編輯；若將來真實 latency 證明需要，優先評估單一「停止分析」而不是允許併發寫入。

## 6. 刻意不照抄 Claude／Codex 的部分

1. **不新增 durable Planner／Todo。** Codex／Claude 的計畫適合有明確交付與完成條件的長自主任務；探索式訪談由 Pattern／Unresolved／Focus／coverage 導航即可。
2. **不新增多 Agent／Evaluator。** Anthropic 的長任務實驗證明可能提升複雜交付品質，也明確指出 bulky、slow、expensive；本產品先用一位主顧問、Skill 與 deterministic verifier。
3. **不把 auto memory 當工作理解。** generic memory 可幫 recall，沒有 Caliburn 所需的員工 source、修訂 lineage 與 authority gate。
4. **不把 file checkpoint 當 JD authority。** JD 需要 semantic atomic group、approved baseline 與 employee Accept／Reject，不是 byte-level file undo。
5. **不要求訪談有全域 done。** 員工可以自然離開；`目前足夠` 只代表某個工作模式在目前 evidence basis 下局部足夠。
6. **不因新 app-server 立即更換 LangGraph。** 框架比較必須看產品效果與完整覆蓋，不以新舊或程式量決定。

## 7. Runtime／框架結論

OpenAI Codex app-server 與 Claude Agent SDK 都已是成熟的可嵌入 agent loop，能提供 thread/session、Tool loop、事件、progress、approval、compaction 與恢復。它們因此是**真實同目的 runtime 候選**，不能只說「會與現有狀態重疊」就排除。

但本輪沒有足夠理由取代 LangChain 1.x＋LangGraph：

| 能力 | LangGraph 現行選擇 | Codex app-server／Claude Agent SDK |
| --- | --- | --- |
| provider／模型可替換 | 已透過 LangChain／OpenRouter binding | 各自以 OpenAI／Claude harness 為中心 |
| typed domain state／transaction | checkpoint transition、interrupt、Store／Saver 可由 application 定義 | 提供 session／loop／events；官方仍要求 host app 擁有 business records／system of record |
| semantic review／JD authority | 已能由 Caliburn command／projection 定義 | 無 Task／Duty／OPKS 或 employee authority 現成語意 |
| progress／failure UI | 能由 graph stream／receipt 實作，但產品投影仍需補強 | protocol 現成度較高 |
| 遷移收益 | 保留既有已驗證機制 | 目前只能確定替換 generic loop，無證據會改善職務分析效果或降低整體複雜度 |

所以目前裁決應是：

- **產品方法**：積極採用 Claude／Codex 的 session ≠ context、agent loop、JIT context、working workspace、diff／approval、typed events 與 failure recovery 方法。
- **production runtime**：維持 LangGraph，補齊 event／turn outcome projection；不增加第二 harness。
- **重新比較觸發條件**：只有實作後出現可重現的 thread recovery、context continuity、streaming／approval 或 model portability 硬缺口，才用固定情境比較完整替換，不雙寫。

## 8. 本輪大方向稽核結果

### 沒有偏離

- 一位專業顧問、非多 Agent；
- 工作理解先於 JD，且每輪理解、JD 按需；
- Task／Duty／OPKS 分析方法保留在 Skills；
- 詳細工作理解跨輪保存，聊天 Context 最小化；
- AI 與員工編輯同一份目前 JD；
- AI 寫入先待審，員工 direct edit 與 employee authority 分明；
- 一般待釐清與 blocking confirmation 分流；
- RAG、A／能力級別與正式 eval 延後；
- 成本優先，不為框架功能增加 Planner／Evaluator／第二模型。

### 需要在後續計畫中顯式加入

1. typed run event／terminal state；
2. deterministic「本輪結果」projection；
3. technical run status 與 semantic interview overview 分離；
4. terminal failure 解鎖與「重試或送新訊息」acceptance test；
5. reconnect 後從 durable state 重建同一 UI，而非依最後一段 assistant text 猜狀態。

### 不構成新產品元件

上述五項都應由 LangGraph stream、checkpoint、execution receipt、understanding delta 與 semantic diff 組合；不得因此新增 `Progress` authority、Agenda store、第二份 summary memory 或另一份 JD。

## 9. Owner 對齊（2026-08-28）

Owner 已確認採用以下整體呈現：

> 每次員工送出訊息後，系統短暫顯示技術執行狀態；完成後以自然顧問回覆＋一小段 deterministic 本輪結果收尾。工作理解與 JD 仍由同一主顧問處理，JD 只有需要時才改；員工另外在同一份目前 JD 上審核 semantic diff。訪談概況不因技術步驟改成 wizard 或百分比。

具體邊界同步確認如下：

- 短暫技術狀態只回答「AI 現在做到哪裡」，本輪不需 JD 工作時可略過該狀態；terminal state 後即結束，不成為訪談 stage。
- 小型本輪結果只回答「這輪實際做了什麼」，從 committed understanding delta、semantic diff、Focus／Unresolved delta 與 execution receipt deterministic 投影；不增加模型呼叫，也不是工作理解、聊天摘要或長期記憶。
- 本輪結果在顧問回覆附近以簡潔、可收合方式呈現，不搶走聊天與 JD 主畫面。
- 訪談概況繼續回答跨輪的工作理解 coverage、目前訪談重點、待釐清、需要確認與待審數；不顯示百分比或固定 wizard。

下一步可把最新版 ADR 0071 與 implementation plan 做一次整體同步；在同步完成並再次審核前，不施工 production code。
