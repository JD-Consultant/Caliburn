# 議程 v4:事件驅動議程+收割 pass 實作計畫(ADR 0033)

> 設計權威:`docs/adr/0033-episode-agenda-consultant-tools.md` +
> `docs/specs/2026-07-14-interview-agenda-architecture-research.md` §3(命名表/回合序/
> 工具規格/guardrail 表/遷移對照)。
> 紀律:一 task 一 commit、綠了才 commit、green-before==green-after;
> L1 止血(T1–T3)在前,任何時點可停下仍比現狀好。
> 測試:`cd apps/api && uv run pytest`(DB 套件需
> `TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/caliburn_test`);
> 收尾全 monorepo `npx turbo test`。

## 實作紀律(每 task 動工前重讀本節;防「憑印象做」與訓練慣性回退)

**動工前必讀**(不讀不動手;compaction/換 session 後尤其):
- 本 task 的 spec 段落(各 task 已標 §);prompt 相關一律加讀 spec §2.8(GPT-5.6)。
- 驗屍 §1 對應 BUG 段(知道自己在防什麼)。

**過時方法黑名單**(出現任何一條=打回重做;來源見 spec §2 對應節):
1. ~~關鍵規則首尾各重複一份~~(GPT-4.1 式;5.6:重複規則=不穩定來源)。
2. ~~「至多三句/be concise」粗放限制當長度控制~~(5.6 預設簡潔會過剪;
   用 verbosity 參數+任務特定描述)。
3. ~~判準/力度規則寫成碼分支~~(寫進教材/prompt 當指引;Anthropic effort-scaling 型)。
4. ~~獨立 planner LLM 呼叫~~(Microsoft SK 已廢;決策=顧問迴圈內 tool call)。
5. ~~LLM 自報信心當路由依據~~(0032 已裁:確定性 quote 判準)。
6. ~~新驅動條件散落 service~~(訊號一律進 agenda.signals;service 只消費)。
7. ~~工具說明塞進 prompt 文字~~(工具走 tools field;描述 1–2 句)。
8. ~~步驟指令式 prompt~~(5.6 outcome-first:給成功判準+停止條件,路徑讓模型選)。

**接縫測試鐵律**(本次驗屍主教訓:四 bug 全是「零件綠、接縫斷、無測試釘接縫」):
每 task 的完成定義**必含至少一條接縫斷言**——測「X 真的被載入/注入/觸發」,
不只測 X 自身。各 task 已逐條列出(標【接縫】)。

## 追溯矩陣(研究結論 → 落點 → 釘住它的測試;驗收時逐列打勾)

| # | 研究結論(spec 節) | 落點 | 釘住的接縫測試 |
|---|---|---|---|
| 1 | BEI 事件單位/STAR(§2.1) | T5/T9 | episode 狀態機測試;CONSULTANT_SYSTEM 含議程三條 |
| 2 | 決策=tool call 可稽核(§2.4) | T6 | tool_trace 含 open_episode;state 更新斷言 |
| 3 | 議程 artifact 注入(§3.3) | T8 | build_consultant_messages 輸出含 `<議程>` 區塊 |
| 4 | guardrail 後衛 2 提示/3 強制(§3.6) | T5/T8 | signals 三態;第 3 輪 auto-close 觸發 harvest(mock 斷言) |
| 5 | 收割=P 的家+教材全文注入(§3.5) | T7 | HARVEST_SYS 含 behavior-indicator 教材標誌句(**BUG-2 型接縫**) |
| 6 | 書記機會性 P(§3.5 分工) | T3 | SCRIBE_SYS 含 `draft_indicator` 字樣 |
| 7 | 處女文件官方殼(§1 BUG-1) | T1 | service 級:空 doc+precheck→落殼+任務 |
| 8 | progressed 對準/飽和讓路(§1 BUG-4) | T5/T8 | episode_yield 斷言;curation 落地→縫歸零;3 輪零收益→auto-close |
| 9 | 5.6 無重複規則/outcome-first(§2.8) | T9 | CONSULTANT_SYSTEM **不含**「再讀一次」段 |
| 10 | 梯子退役不復活(ADR 禁令) | T8 | ledger.py 刪除;grep 無 next_gap 引用 |
| 11 | 異質模型(§3.7) | T10 | 考卷紀錄(specs)+config 斷言 |

## L1 止血(獨立於 v4,先落)

### T1|BUG-1:處女文件上的官方殼直落

- 改:`verify.py` add 分支——`target_path == "ocs_content.ocu_units"` 且
  `doc.get("ocs_content")` 非 dict(缺席/None)→ 視為空容器(apply 端
  `setdefault` 鏈已能建殼,只有 verify 在擋)。
- 測:`test_interview_verify.py` 新增處女文件四格(repro 表:`{}`/
  `{"ocs_content":None}`/`{"ocs_content":{}}`/`{"ocu_units":[]}` 全放行官方殼;
  quote-only 無 ref_urn 照樣 src 拒)。
- 測【接縫】:service 級——**空 doc**+quote-backed precheck → 兩相落地成功,
  landed_doc 含殼+任務 `_pending`(= session 330a0bed 第 3 輪的全滅場景轉綠)。
- 驗:上述新測 + 既有 verify 套件全綠。

### ~~T2~~|BUG-4 不做獨立止血(2026-07-14 維護者裁決:過渡補丁=白工)

- BUG-4 的修法**併入 v4 本體**:episode 收益判定=T5 `episode_yield`;
  curation 落地計入=T5 `signals`(curation 縫進帳);episode 粒度 attempts=T8。
- 保險價值評估:獨立修活不到 T8 就被重寫,且不改變使用者可感知的 P 問題——砍。
- 唯一代價:v4 落地前的 live 測試仍有「飽和不讓路」行為;接受(期間不排 live 驗收)。

### T3|BUG-2 短效:書記 P 機會性規則

- 改:`scribe.py` `SCRIBE_SYS` 加規則 9(自 behavior-indicator 教材萃取精簡):
  「員工講出『怎樣算做好/怎麼驗收/出錯怎麼發現』→ 用 draft_indicator 起草:
  情境+可觀察行為+標準,動詞用可觀察的(執行/檢核/判定…),quote 掛他原話;
  『了解/熟悉/具備』這類不可觀察措辭不算指標。」
- 測【接縫】:`"draft_indicator" in SCRIBE_SYS`(釘「規則存在」的接線,
  非散文斷言);語氣/成效驗收掛 persona 重測(T10 後)。
  `records_to_ops` 的 draft_indicator 映射既有測試不動。
- 驗:api 套件全綠;`SCRIBE_SYS` 長度仍在合理範圍(<1200 字)。

## v4 主體

### T4|coverage.py:ledger 純函式 move-only 拆分

- 新:`coverage.py` ← 搬 `iter_tasks/_seg/tier/share_sum/blocks_missing/
  task_missing/has_occupation/checklist/derive_phase/attitudes_missing/_gap/
  coverage/can_finish` + 門檻常數(MIN_*/SHARE_TOL/BLOCK_KEYS)。
- `ledger.py` 暫留 re-export(下游 import 不斷)+ 狀態函式(note_attempt/held/
  boundary/fatigue/is_stalled)。`next_gap` 本 task **不動**。
- 測:測試檔同步搬 import;**不改任何斷言**(characterization)。
- 驗:api 套件全綠,git diff 確認 move-only。

### T5|agenda.py:episode 狀態機+訊號+artifact(TDD,純函式)

- 新:`agenda.py`——
  `episode_state(state) -> {target,opened_seq,touched}|None`;
  `open_episode(state, target, seq)` / `close_episode(state, reason, seq)`
  (回新 state,episode 歸檔進 `state["episodes"]`);
  `episode_yield(ops, episode) -> bool`(本回合書記 ops 是否觸及事件相關路徑;
  =BUG-4 progressed 的 v4 語義);
  `signals(state, turns_n) -> {stalled_episode, no_episode_nudge, budget}`
  (spec §3.6 表:2 輪零收益→提示、3 輪→auto_close;無事件 2 輪→nudge;
  **curation 落地計入 curation 縫進帳**——BUG-4 反向病灶在此根治);
  `agenda_view(doc, state, pool_tasks, ref_codes) -> str`(spec §3.3 artifact:
  事件狀態+壓縮覆蓋地圖(語意名)+訊號+候選事件方向 3 條)。
  候選事件方向=覆蓋空白區 top-N(from coverage.task_missing),id 穩定
  (task_path)、標籤語意(「任務X 最近一次實際發生」)。
- 測:`test_interview_agenda.py` 每函式 TDD(開/收/收益/三訊號/視圖含空白區名)。
- 驗:新套件綠;既有全綠。

### T6|議程工具接線(記帳,先不收割)

- 改:`tools.py` `CONSULTANT_TOOLS` + `open_episode`/`close_episode` 定義
  (描述 1–2 句照 spec §3.4;target enum 由 service 每回合注入候選 id——
  工具 schema 的 enum 動態組,同書記 schema 慣例)。
- 改:`service.py` dispatch 包一層攔議程工具:open→`agenda.open_episode` 記
  state、回確認+空缺摘要;close→記 state+`pending_harvest=True`、回
  「已記,收割將於本回合完成」。
- 測【接縫】:(a)`CONSULTANT_TOOLS` 含兩工具且 target enum 由候選注入;
  (b)顧問 mock 呼 open/close → `agenda_state` 更新、`tool_trace` 入稽核表。
- 驗:api 全綠。

### T7|harvest.py:事件收割 pass(TDD)

- 新:`harvest.py`——`harvest_schema(slot_paths, pools, task_keys)`(mirror
  scribe_schema:draft_indicator/record_task_pool/record_task_custom/set_slot/
  none);`HARVEST_SYS`(BEI 編碼員人格+behavior-indicator、ks-distinction
  教材全文注入=skill_loader 固定掛載);`harvest_pass(llm, knowledge, *, doc,
  turns, episode, header_codes, ref_ocs_codes) -> ScribeResult`
  (episode.turn 範圍取逐字稿;records_to_ops/land_ops 復用;fail-open)。
- 測:`test_interview_harvest.py`——schema 變體隨輸入生滅;守衛(quote 逐字/
  池外拒);land 走 verify(dup 擋);LLM mock。
- 測【接縫,BUG-2 型】:HARVEST_SYS 組裝結果**含 behavior-indicator 教材
  標誌句**(如「可觀察」動詞清單開頭)與 ks-distinction 標誌句——
  釘「教材真的被載入 prompt」,正是這次驗屍中斷掉沒人發現的那條線。
- 驗:新套件綠;既有全綠。

### T8|service 回合序 v4(拆三子步:先加新軌綠→再拆舊軌;green-before==green-after)

**拆分理由**:原 T8 把「啟用新架構+刪舊梯子」擠一個 commit=最高風險。改雙軌:
T8a/T8b 增量加新行為(舊梯子仍在跑,不刪),各自綠;T8c 才拆舊梯子。任何子步可停。

#### T8a|收割接線:close/auto-close → harvest_pass(新架構第一次真的產 P)

- 改:`service.py` run_turn——書記 pass 後加收割段:
  `sig = AG.signals(state, emp_turn.seq)`;auto-close(sig["auto_close"] 且事件開著)
  先 `AG.close_episode(reason="auto")`+設 pending_harvest;
  `pending_harvest` → 取 `episodes[-1]` 為收割對象 → `harvest_pass(doc=收割前最新doc,
  turns=turns_map, episode=harvest_ep, ...)` → `_persist`(復用書記 409 重放路) → 清 flag。
  收割吃**書記落地後**的 doc(避免蓋掉本回合綠字);doc_changed |= 收割落地。
- 測【接縫】:(a)手動 close(chat_trace)+ fake 收割 select → P 落 `_pending`、
  pending_harvest 清;(b)auto-close(state 預置 dry_streak=3)→ episode 歸檔 reason=auto
  +收割被呼。
- 驗:api 全綠(舊梯子/next_gap 仍在,行為疊加不衝突)。

#### T8b|artifact 注入 + episode 進帳(顧問看得到議程;飽和訊號活過來)

- 改:`consultant.build_consultant_messages` 加 `agenda_view: str = ""` 參數,
  非空則注入 `<議程>` 區塊(**加**在 ctx,暫不刪 ledger_summary——雙軌並存驗證);
  `service` 算 `AG.agenda_view(work_doc, state, ..., turns_n=emp_turn.seq)` 傳入。
- 改:收帳 `state = AG.bump_streaks(state, has_episode=..., progressed=episode_yield(...))`
  (episode 粒度;與舊 note_attempt 並存,T8c 拆舊)。
- 測【接縫】:(a)messages 含 `<議程>`;(b)開著事件連 2 輪零落地 → signals
  stalled_episode True;(c)auto_close 在第 3 輪。
- 驗:api 全綠。

#### T8c|梯子退役(拆舊軌;**盤點後細化——耦合比原估廣,分三類**)

**2026-07-14 盤點發現**(grep next_gap/CURATION_TASKS/ONBOARD_OCCUPATION):
舊 ledger 的東西**不是一坨梯子**,要拆三類、去向不同——混為一談會破壞裁剪縫:

**A 類=梯子槽優先序(確定刪)**:`next_gap` 的 ①預算槽→②③細項槽→④P/K/S→⑤⑥
排序邏輯。被議程取代。使用點:`service.py:159 last_gap`、`consultant.ledger_summary`
的槽排序段、`gap_label` 的槽名。

**B 類=議程階段判定(保留!搬 coverage,不可刪)**:`ONBOARD_OCCUPATION`/
`CURATION_TASKS` 常數 + 判定。**v4 仍需**,被三處依賴:(a)`service.py:167` 裁剪縫
`if last_gap==CURATION_TASKS`(新手核心流程!)、(b)`skill_loader.py:26` 教材掛載、
(c)`consultant._ONBOARD_STEER` onboarding 話術。

**⚠️ 等價性陷阱(2026-07-14 追查發現,勿踩)**:`CURATION_TASKS` 是**雙觸發**——
next_gap ⓪「有職類 ∧ 無任務」**OR** ⓪′「有任務 ∧ 檢查表 unasked ∧ 未 stalled」。
`derive_phase` 對「有任務」一律回 `opks_deep`,**不含** ⓪′ 分支 → **兩者不等價**!
若把裁剪縫判定簡化成 `derive_phase==task_curation`,「有任務但官方清單沒問完」的
裁剪會**靜默失效**(正是本次驗屍要根治的靜默斷)。
**正解**:抽一個獨立純函式 `coverage.should_curate(doc, state, pool_tasks, ref_codes)
-> bool`,原樣搬 next_gap 的 ⓪+⓪′ 判定(含 is_stalled(CURATION_TASKS)),
service 裁剪縫改呼它;兩常數搬 coverage,三處 import 改。回歸靠 service 的
test_curation_* + 新增「有任務但 unasked→仍裁剪」測試。

**C 類=狀態函式(move-only 搬 agenda)**:held/boundary/fatigue/note_attempt/
push_held/pop_held/add_boundary/in_boundary/is_fatigued/is_stalled → agenda.py。

**步驟(每步綠了才下一步)**:
1. B 類常數搬 coverage + 裁剪縫判定改 derive_phase;三處 import 改。驗全綠(行為不變)。
2. C 類狀態函式 move-only 搬 agenda;import 改。驗全綠。
3. 刪 A 類:`next_gap` 整函式 + `consultant.ledger_summary`/`gap_label`/`_ONBOARD_STEER`
   被 artifact 取代部分(onboarding 話術改進 artifact 或保留精簡版);
   `service.py:159 last_gap` 刪。`ledger.py` 空了→整檔退役,re-export 清。
4. 改測試:`test_interview_ledger.py` 刪;`test_interview_consultant`(ledger_summary)、
   `test_interview_refcodes`(next_gap)、`test_interview_skills`(常數)、
   `test_interview_agenda_v3`(boundary)、`api/routes/interview.py:143`+
   `test_interview_routes`(議程三態 API)、`evals/interview_sim.py:206` 全改。
- 測【接縫】:grep 無 `next_gap`/`ledger_summary`;`import ledger` 歸零;
  **裁剪縫回歸**(新手選職類→官方任務綠字直落 = service T5c 測試仍綠)。
- 文檔:**同 commit** 更新 `docs/design/interview-engine.md`(§4 回合序 v4、§5 載體
  表加收割、不變量 13=議程決策唯一路、退役禁令加 next_gap 梯子)。
- 驗:api 全綠+`npx turbo test` 全綠。
- **風險提示**:B 類判定改寫若破壞 `derive_phase==task_curation` 等價性,裁剪縫會
  靜默失效(新手流回到 BUG-1 前的斷棒)。改前先確認 derive_phase 對「有職類無任務」
  回 task_curation(coverage 測試已覆蓋 test_derive_phase_progression)。

### T9|consultant prompt v4+GPT-5.6 紀律(spec §2.8)

- 改:`consultant.py` `CONSULTANT_SYSTEM` 依 GPT-5.6 outcome-first 重寫:
  (a)**刪首尾重複段**(「最重要三條再讀一次」整段刪——5.6:重複規則=
  不穩定來源),規則只留一份;(b)主體改「成功判準式」:訪談成功=每個 core
  任務有具體事件佐證(細節+可觀察指標),配議程工具的停止條件(open/close);
  (c)「至多三句」改用任務特定描述,避免 5.6 預設簡潔下過剪;
  (d)全 prompt 審一遍矛盾規則(5.6:conflicting rules>missing detail)。
  全 repo 碼註「GPT-4.1 指南」參照改「GPT-5.6 指南」(連結 spec §2.8)。
- 測【接縫】:(a)CONSULTANT_SYSTEM **不含**「再讀一次」段(黑名單 1 的
  負向斷言);(b)含議程三條關鍵詞(open_episode/close_episode);
  (c)教材掛載照 skills_for(prompt 建構測試)。
- 定稿程序:改完跑一遍**矛盾審計**(5.6:逐條規則兩兩對照,衝突=挑一條刪)。
- 驗:api 全綠。

### T10|模型升級+實測(待 OpenRouter 金鑰)

- interview 升 frontier 候選(過 T11 考卷:strict/tools/中文;OpenRouter
  require_parameters);.env/config 文檔更新。
- 新手 persona 全流程重測(黃金驗收:P≥1/core 任務、單事件 ≤6 輪、
  20 任務盤勾後 10 輪內首個 P 落地)。
- 驗屍紀錄寫 specs;綠後打 tag `agenda-v4`。
