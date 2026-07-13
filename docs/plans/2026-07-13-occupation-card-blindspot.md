# 職類建議卡 + 引擎參考集合盲區修復 — 實作計畫

> 依 specs/2026-07-13-occupation-consent-write-research.md(研究)+ 維護者討論定案
> (2026-07-13):**參考集合維持人選**(否決 AI 代寫 WRITE 工具);A 案聊天建議卡
> +常駐 chip+dismissed 知情換話術;**反騷擾規則暫不做**。一 task 一 commit,綠了才 commit。

**目標**:新手口頭聊完 → 卡片一鍵把顧問建議的職類加入參考;關掉不斷頭;
引擎看得見 profile 上的參考集合(修 session 6f807f1e 鬼打牆根因)。

## T1 引擎盲區修復(api;bug fix,無 UI)

- `service.run_turn`:`ref_ocs = set(profile.selected_ocs_codes) ∪ _doc_ocs_codes(doc)`
  成為唯一碼集合,餵給 ①ledger(`next_gap`/`can_finish`/`coverage` 的 has_occupation
  判定加 `ref_codes` 參數)②`build_task_pool(knowledge, codes)`(簽名改吃碼列表)
  ③`scribe_pass(..., ref_ocs_codes)` → `build_pool_inputs` 聯集 ④consultant
  `_reference_block(doc, pool_tasks, ref_codes)`(前綴 2 顯示參考,顧問不再誤判空白)。
- 測試(回歸釘死事故):profile 有碼+文件空 → `next_gap == CURATION_TASKS`、
  scribe 池非空、reference block 含碼。`run_finish` 態度池同步吃聯集。

## T2 occupation widget 帶建議 + dismissed 知情話術(api)

- widget 加 `precheck: [{code, name, reason}]`:來源=本回合 `occ_searches` top 命中
  (確定性;reason=「依你描述:『{query 截 40 字}』」),含顧問提過的碼。
- `interview:review-events` 的 decision 收 `occupation_dismissed`(text 欄,無 migration);
  `run_turn` 讀最近 dismissed 事件 → 動態區注入一行:「他關掉了職類選窗——下回合用
  一句白話說明選參考的用途+安撫可之後再選,不要複讀同一批建議」。
- 測試:widget 形狀;dismissed 事件→ctx 含該指示。

## T3 web 聊天建議卡 + 常駐 chip

- `OccupationSuggestCard`(InterviewPanel 對話流內,ChoiceCard 同位置):
  precheck 預勾+每列 reason;「加入參考(N)」→ `useSetOccupations` →
  invalidate document+knowledge+任務盤鋪設(沿 onApplied);「其他(自由輸入)」→
  聚焦輸入框;「✕」→ `postReviewEvents([occupation_dismissed])` + 收合。
- chip:參考集合為空時面板頂常駐「📌 待選:職能基準參考〔開啟〕」→ 開現有
  OccupationPicker modal(重入口);選後消失。參考集合狀態源=profile
  (`useProfile.selected_ocs_codes`)。
- task picker widget 維持 modal(僅職類改卡片);`onWidget` 只再服務 task。
- 測試:vitest 純函式部分(precheck→卡片 props 映射入 interviewUi.ts);
  其餘 tsc+lint gate。

## T4 文檔 + ADR

- **ADR 0031**:職類參考=聊天建議卡(推翻 0028 D1「不另做聊天 widget」之職類段)+
  參考集合維持人選(否決 AI 代寫;紀錄否決理由與重啟條件)+引擎參考集合來源=
  profile∪doc 不變量;更新 `docs/adr/README.md` 索引。
- 清 0029 前化石:api/web README、CLAUDE.md 的「PUT occupations 刷表頭」句;
  `docs/design/interview-engine.md` 補參考集合來源不變量+卡片/chip/dismissed 流。
- 研究紀錄補「裁決」段(人選定案、反騷擾緩做)。

完成定義:`npx turbo test` 全綠;手測劇本=新手 persona 重跑(不點 UI,只點卡片一鍵)
→ 任務盤開 → 書記開始落綠字。

## T5 任務載體路由(v2;ADR 0032——**廢止先前 b 案版本**)

> 研究:`specs/2026-07-14-task-carrier-routing-research.md`。四格路由:有 quote→綠字
> 直落、盤=人開(intake 邀請卡/收尾 offer/工具列自取)、不確定 ≤3→聊天卡、盤上勾=
> confirmed。文檔隨各 task 同 commit 更新(interview-engine.md 判準表狀態欄)。

### T5a api:intake 邀請訊號+盤 dismissed 知情(確定性,零 LLM)

- `run_turn`:**刪** curation precheck→widget 路徑(`picker:"task"`;黑洞源頭停發);
  widget 單槽優先序=職類卡 > intake 邀請。
- 新 widget `{"kind":"open_picker","picker":"task_board_intake"}`,條件=ref_ocs 非空
  ∧ 文件無任務(`_doc_has_tasks` 純函式)∧ 無 `task_board_dismissed` 事件 ∧ 槽空。
- routes `_REVIEW_DECISIONS` + `task_board_dismissed`;consultant context 兩情境行:
  intake_eligible→「可自然提一句:想快的話可以勾任務盤(約 2 分),用聊的也行;
  別推銷第二次」;board_dismissed→「他選了用聊的——改口頭裁剪,別再提盤」。
- 測試:三布林各缺一→不發;occupation 候選同回合→職類卡佔槽;dismissed→
  不發 intake+context 含指示;`picker:"task"` 不再出現。

### T5b web:intake 卡+受控開盤

- `GlobalTaskPickerMenu` 改 optionally-controlled(`open?`/`onOpenChange?`,
  無傳入時內部 state 保底,工具列按鈕行為不變)。
- `page.tsx`:`taskBoardOpen` state 接盤;`InterviewPanel` 加 prop `onOpenTaskBoard`。
- `InterviewPanel`:widget `picker=="task_board_intake"` → intake 卡(單槽,occCard
  同款收納):「開任務盤(約 2 分鐘)」→ `onOpenTaskBoard()`+收合;「用聊的就好」→
  `postReviewEvents([{doc_path:"/", decision:"task_board_dismissed"}])`+收合。
  前端雙保險:文件已有任務→不渲染(條件自癒)。
- `interviewUi.ts` 純函式(widget 窄化 isIntakeInvite)+vitest;tsc/lint gate。

### T5c api:官方任務綠字直落(quote→land;本包最大塊)

- 裁剪 quote-backed precheck → **確定性映射**成 add-task ops(ref=池 URN+quote src)
  → 走既有 verify 六查 → `_pending`(0030 不變量不破:LLM 只出判斷,op 由確定性碼組
  ——records_to_ops 同哲學)。無 quote 者不落(留口頭/卡片)。
- 家職責解析(resolveHomeUnit 伺服器版):`build_task_pool` 池列補 unit 來源欄
  (對 indexer-contract 確認 `occupation_tasks` 的 unit src 欄位);職責在文件→掛入;
  不在→**確定性建官方殼**(name=池 unit、src=官方、`_pending` add 標)再掛。
  verify:殼只允許池內官方名、任務 ref∈池;位置碼不寫(renumber=web 獨佔)。
- ✗殼=巢狀還原(前端 `rejectPending` add 語意沿用——刪殼帶走殼下 pending 任務;補測)。
- **退役**:`interview:curation` 端點+`run_curation`+web `lib/curation.ts`(含 test)
  ——盤=乾淨自取,無疊加層(ADR 0032 #3)。
- 測試:quote→pending 任務+殼落地;無 quote→不落;池外/非官方殼名拒收;
  409 重放沿用;✗殼巢狀還原(web vitest)。

### T5d web/api:不確定候選卡(≤3 點頭;不阻斷主流,最後做)

- 裁剪「無 quote 但相關」候選:顧問口頭問升級為聊天卡(1-3 候選+理由,
  OccupationSuggestCard 一般化為 SuggestCard);確認=前端現有 `addTasksToUnit`
  (confirmed 直落,0028 D9)。候選 >3 → 不出卡,交盤(人拉)。

### T5e 收尾補漏 offer

- 顧問尾聲/finish 話術(skill 層改字):「開盤掃一遍,看有沒有漏的」;
  側欄收尾卡帶「開任務盤」鈕(同 `onOpenTaskBoard`)。
