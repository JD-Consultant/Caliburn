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
