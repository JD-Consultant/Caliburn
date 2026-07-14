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

### T8|service 回合序 v4+guardrail+梯子退役(+design 文檔同 commit)

- 改:`service.py` 依 spec §3.2 重排:agenda_view 注入顧問 context;
  close/auto-close 觸發 `harvest_pass`+`_persist`(409 同書記重放);
  attempts 改 episode 粒度(T2 止血版讓位);`signals` 驅動提示/auto-close。
- 刪:`ledger.next_gap` 梯子+`ledger_summary`/`_ONBOARD_STEER` 中被 artifact
  取代的部分;`ledger.py` 剩餘狀態函式併入 agenda.py 後**整檔退役**
  (re-export 清掉,import 全改 coverage/agenda)。
- onboarding/curation 縫判定(原⓪/⓪′)搬 agenda(條件不變:無參考→選職類;
  無任務→intake/curation)。
- 測:service 套件改寫斷言(黃金流程:開場→open→深挖 2 輪→飽和提示→
  close→收割落 P→換事件);梯子測試刪除。
- 測【接縫】:(a)build_consultant_messages 輸出含 `<議程>` 區塊(artifact
  真的注入);(b)close_episode → harvest_pass 被呼(mock 斷言,「收了真的
  有收割」);(c)第 3 輪零收益 → auto-close 觸發收割;(d)repo 內 grep 無
  `next_gap` 殘留引用。
- 文檔:**同 commit** 更新 `docs/design/interview-engine.md`(§4 回合序 v4、
  §5 載體表加收割、不變量 13=議程決策唯一路=顧問工具+guardrail、
  退役禁令加 next_gap 梯子)。
- 驗:api 全綠+`npx turbo test` 全綠。

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
