# 議程 v4:事件驅動議程+收割 pass 實作計畫(ADR 0033)

> 設計權威:`docs/adr/0033-episode-agenda-consultant-tools.md` +
> `docs/specs/2026-07-14-interview-agenda-architecture-research.md` §3(命名表/回合序/
> 工具規格/guardrail 表/遷移對照)。
> 紀律:一 task 一 commit、綠了才 commit、green-before==green-after;
> L1 止血(T1–T3)在前,任何時點可停下仍比現狀好。
> 測試:`cd apps/api && uv run pytest`(DB 套件需
> `TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/caliburn_test`);
> 收尾全 monorepo `npx turbo test`。

## L1 止血(獨立於 v4,先落)

### T1|BUG-1:處女文件上的官方殼直落

- 改:`verify.py` add 分支——`target_path == "ocs_content.ocu_units"` 且
  `doc.get("ocs_content")` 非 dict(缺席/None)→ 視為空容器(apply 端
  `setdefault` 鏈已能建殼,只有 verify 在擋)。
- 測:`test_interview_verify.py` 新增處女文件四格(repro 表:`{}`/
  `{"ocs_content":None}`/`{"ocs_content":{}}`/`{"ocu_units":[]}` 全放行官方殼;
  quote-only 無 ref_urn 照樣 src 拒)。
- 驗:上述新測 + 既有 verify 套件全綠。

### T2|BUG-4 止血版:progressed 對準 gap + curation 進帳

- 改:`service.py`——`note_attempt` 的 progressed 改為
  「`scribe_res.ops` 中存在 `target_path.startswith(last_gap 對應路徑前綴)`」;
  `last_gap == CURATION_TASKS` 時 `curation_landed` 計為 progressed。
  (v4 T8 再改 episode 粒度;本 task 先讓 STALL_K 語義活過來。)
- 測:`test_interview_service.py`——(a)書記落無關路徑 → attempts+1;
  (b)落 gap 前綴路徑 → 歸零;(c)curation 落地 → curation 縫歸零。
- 驗:api 套件全綠(含 DB)。

### T3|BUG-2 短效:書記 P 機會性規則

- 改:`scribe.py` `SCRIBE_SYS` 加規則 9(自 behavior-indicator 教材萃取精簡):
  「員工講出『怎樣算做好/怎麼驗收/出錯怎麼發現』→ 用 draft_indicator 起草:
  情境+可觀察行為+標準,動詞用可觀察的(執行/檢核/判定…),quote 掛他原話;
  『了解/熟悉/具備』這類不可觀察措辭不算指標。」
- 測:prompt 文字不做脆弱斷言;驗收掛 persona 重測(T10 後)。
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
  `episode_yield(ops, episode) -> bool`(本回合書記 ops 是否觸及事件相關路徑);
  `signals(state, turns_n) -> {stalled_episode, no_episode_nudge, budget}`
  (spec §3.6 表:2 輪零收益→提示、3 輪→auto_close;無事件 2 輪→nudge);
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
- 測:service 測試——顧問 mock 呼 open/close → state 正確、tool_trace 入稽核。
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
- 文檔:**同 commit** 更新 `docs/design/interview-engine.md`(§4 回合序 v4、
  §5 載體表加收割、不變量 13=議程決策唯一路=顧問工具+guardrail、
  退役禁令加 next_gap 梯子)。
- 驗:api 全綠+`npx turbo test` 全綠。

### T9|consultant prompt v4+GPT-5 世代紀律

- 改:`consultant.py` `CONSULTANT_SYSTEM`——加「議程三條」(開場先弄清他做什麼
  →open_episode;一次一事件,STAR 深挖;問透或他換話題→close_episode);
  eagerness 校準語彙(GPT-5.2:controlled scope、deliberate stopping);
  「每回合恰一問」保留。全 repo 碼註「GPT-4.1 指南」參照改「GPT-5 世代」。
- 測:prompt 建構測試(artifact 區塊在、教材掛載照 skills_for)。
- 驗:api 全綠。

### T10|模型升級+實測(待 OpenRouter 金鑰)

- interview 升 frontier 候選(過 T11 考卷:strict/tools/中文;OpenRouter
  require_parameters);.env/config 文檔更新。
- 新手 persona 全流程重測(黃金驗收:P≥1/core 任務、單事件 ≤6 輪、
  20 任務盤勾後 10 輪內首個 P 落地)。
- 驗屍紀錄寫 specs;綠後打 tag `agenda-v4`。
