---
title: 訪談引擎 × 文件工作台 — 端到端設計(v3 追蹤修訂/一個大腦)
audience: agent-primary(也給人)
scope: apps/api app/interview/* + skills/* + observability + routes/interview + apps/web 表格四態/側欄
updated: 2026-07-14
---

# 訪談引擎 × 文件工作台 — 端到端設計(v3:一個大腦 + op→verify→`_pending`)

> **主讀者 = coding agent。** 目的:不看 code 也能改對這條線——不亂發明端點、不把信任
> 機制交給 LLM、不繞過唯一寫入路徑。**living:動到這條線的碼,同 commit 更新本檔。**
> 決策:ADR [0030](../adr/0030-ai-coedit-tracked-changes-one-brain.md)(v3 六裁決;部分翻案
> 0025/0028)、[0032](../adr/0032-task-carrier-routing.md)(任務載體路由,§5.1)、
> [0027](../adr/0027-interview-engine-v2-consultant-agent.md)(四組件,留用)、
> [0023](../adr/0023-interview-engine-stateless-turns.md)(無狀態回合)、
> [0024](../adr/0024-llm-wiring-select-schema.md)(受限解碼)。
> 研究(單一參照點):[`2026-07-12-ai-layer-redesign-research.md`](../specs/2026-07-12-ai-layer-redesign-research.md) §6;
> 計畫:[`2026-07-13-ai-layer-v3-tracked-changes.md`](../plans/2026-07-13-ai-layer-v3-tracked-changes.md)。

## 1. 一句話

訪談引擎是**唯一 AI 大腦**,書記是**唯一寫入路徑**:員工每說一句,顧問(強模型,無寫入權)
自然對話追問,書記(便宜模型,受限解碼)抽成 **op → verify 六查(純函式,blocking)→
文件內 `_pending` 追蹤修訂標記**;人在表格上逐筆(或批量)✓/✗——✓=去標、✗=還原,
**決策無聲**(只記帳不觸發 AI)。匯出/定稿自動剝未審項。舊 LangGraph/CopilotKit 整鏈已退場。

## 2. 組件(住哪/權力)

| 組件 | 是什麼 | 碼 | 權力 |
|---|---|---|---|
| 🧠 顧問 | LLM 對話主導 + READ 工具 | `consultant.py`+`tools.py`+`agent_loop.py` | **無寫入權**;說話+查(含 `read_document` 四態視圖) |
| ✍️ 書記 | LLM 受限抽取 → op 化 | `scribe_schema.py`+`scribe.py` | **唯一寫入路徑**;產 op,落 `_pending` |
| 🛡 verify | **純函式六查(零 LLM),blocking** | `verify.py`(+`docpath.py`) | 沒過的 op 一筆都不落 |
| 📋 帳本 | 純程式:覆蓋/閘門/議程四態/疲勞 | `ledger.py` | 決定「問完沒/該問啥」;held/boundary |
| 🔍 backstop | **確定性 sweep(零 LLM)**,每 5 員工回合 | `backstop.py` | 只產 held 待問問題,不寫文件 |
| 📖 skills | 判準教材 8 檔(iCAP/O*NET/ESCO/SFIA/Bloom) | `skills/<name>/SKILL.md`+`skill_loader.py` | 確定性按 phase/gap 載入;**調教首選改 skill 不改碼** |
| 📈 tracing | OTel 手埋(gen_ai.* 現行 semconv) | `app/observability.py` | verify 拒收/審閱事件各一 span |

## 3. 資料模型(真名)

| 東西 | 住哪 | 要點 |
|---|---|---|
| 追蹤修訂標記 `_pending` | **文件本身**(契約 `PendingMark`) | 行內(條目/任務/職責)或集合式(`details`/`ocs_profile`/區塊級別 `{槽名: mark}`);`op∈add/mod/del`、`by:"ai"`、`turn_id`、mod 必帶 `prev`、表頭主基準延遲生效帶 `value` |
| 出處 `_pending.src` | 標記內(契約 `PendingSrc`) | `ref_urn`(官方)與 `quote:{turn_id,text}`(逐字原話)可並存、**至少一**(verify ③ 強制) |
| 任務細項 `details`(11 槽) | 文件 `task["details"]` | scalar 槽;標記集合式 `details._pending.<槽>` |
| 態度 `ocs_attitude.attitudes` | 文件層(非逐任務) | 收尾 `attitudes_pass` 整體編碼 → **同軌 op→verify→`_pending`** |
| 進度列 `interview_sessions` | DB | status/phase/focus/`ledger_state`(attempts/held/boundary/declined/fatigued/backstop_last_seq…僅存不可重算態) |
| 逐字稿 `interview_turns` | DB | (session,seq) 唯一;quote 驗證的真相來源 |
| 審閱事件 `interview_review_events` | DB | ✓/✗/批量的**無聲記帳**(`decision∈accepted/rejected/batch_rejected`,`seq` Identity 穩定序);ledger 下回合讀「被拒清單」 |
| LLM 稽核 `interview_llm_calls` | DB | 每回合每次呼叫一列 |
| ~~interview_evidence / interview_suggestions~~ | **已退場(migration 0008)** | 溯源住 `_pending.src`;建議層由 `_pending` 本身取代 |

## 4. 一回合資料流(runtime;`service.run_turn`)

```
面板 send(text) → POST …/interview:turn {text}
  ① 載入 draft+session+逐字稿;append 員工 turn;官方任務池 build_task_pool(fail-open)
  ② 帳本回合前視角:last_gap=next_gap(帳本尊重 held/boundary);curation 縫→curation_pass
     → quote-backed precheck 經 curation_ops **確定性映射**成 add op(官方殼+任務,
       ref=池 URN)→ 同 verify/land 路直落 `_pending`(0032;409→放棄,下回合縫自癒);
       declined→ledger_state。文件變了 → 顧問/書記/帳本後續全吃落地後文件
  ③ 顧問 chat_with_tools(role=interview;**先於書記**,吃回合前文件):
       context 三層(T7):前綴1=system+consultant-principles(全域凍結,byte 級穩定)
       → 前綴2=參考基準摘要(per-doc) → 動態區=進度/四態文件/被拒/待問/本回合欄位 skill
       工具:knowledge_search_occupations / knowledge_occupation_brief / read_document(四態視圖)
  ④ 喚醒閘 worth_scribing(確定性前濾:meta/寒暄跳過)→ 書記 scribe_pass:
       select_schema(strict)→ records_to_ops(確定性映射+kind↔pool 守衛)
       → verify_ops 六查:①契約 ②quote 逐字 ③來源(ref∈池;custom 必附 quote)
         ④寫入權限(禁無聲改) ⑤結構不變量(位置碼拒收/任務掛職責/態度文件層/重複)⑥尺寸
       → 敗筆帶具體錯誤回灌重試(≤2);過的 apply_pending_ops 落 `_pending`
  ⑤ 寫回 upsert_draft(雙 token)→409 重讀後 land_ops 重放同 ops 一次(重 verify)→再衝突放棄(人優先)
  ⑥ backstop_sweep(每 5 員工回合;確定性)→ held 待問;note_attempt+疲勞偵測
  ⑦ 三訊號(coverage 全綠/疲勞/輪數≥40)→ 回應帶 suggest_finish
  → 回 {say, widget, doc_changed, progress, suggest_finish}
```

收尾 `run_finish`(POST …/interview:finish):attitudes_pass → **op→verify→`_pending`**(態度綠標)
→ 結構化總結回讀 `summary:{lines,pending_count,accepted_count}` → phase=review。

## 5. UI 動作 → 請求對照

| UI 動作 | 發什麼 |
|---|---|
| 側欄開始訪談 | `POST /api/v1/job-profiles/{id}/interview:start`(冪等) |
| 送出一句話 / chips | `POST …/interview:turn {text}`(回覆前端打字機動畫;無 SSE) |
| 表格單筆 ✓/✗ | **不發 AI 請求**:前端 `acceptPending/rejectPending`(ocsDoc.ts)改 doc→`renumber()`→`PATCH …/document`(雙 token)+ `POST …/interview:review-events` 記帳 |
| 工具列「接受全部(N)/拒絕全部」 | 同上批量(`resolveAllPending`);拒絕批量事件 decision=`batch_rejected` |
| 「?」出處卡 | **不發請求**:讀該筆 `_pending.src`(官方來源行+「第 N 輪:『原話』」) |
| 側欄「進入收尾對帳」 | `POST …/interview:finish` → 側欄收尾卡(總結條列+補充輸入回 turn) |
| 議程清單 | `GET …/interview` 的 `agenda[]`(三態+boundary;ledger 推導) |
| intake 邀請卡「開任務盤」/「用聊的就好」 | **不發 AI 請求**:開全域任務盤(受控 open,勾選走流程 1 PATCH)/ `POST …/interview:review-events`(decision=`task_board_dismissed` 無聲記帳) |
| 匯出 JSON | `GET …/document/export`(後端 `_strip_underscore` 自動剝 `_pending`);待審>0 前端先 confirm |

### 5.1 AI→人 載體判準(ADR 0032;「狀態」欄隨實作 commit 更新)

| 情境 | 載體 | 機制 | 狀態 |
|---|---|---|---|
| 內容有家+有逐字證據(quote 過 verify ②) | 表格綠字 `_pending`,✓/✗ 就地審 | 書記 op;**官方任務**=裁剪 quote-backed→確定性 op(家職責不在→官方殼,殼必帶池 URN) | 已實作 |
| 參考集合建議(無家,住 profile) | 聊天建議卡 | 0031 職類卡(precheck=本回合搜尋真實命中;人按=PUT) | 已實作 |
| AI 不確定(無 quote;候選 ≤3) | 聊天卡片點頭 | 確認=前端 confirmed 直落(0028 D9) | plan T5d |
| 開場 intake / 收尾補漏 / 隨時自報 | 盤(全域任務窗)——**永遠人開** | intake 邀請卡(確定性三布林:參考非空∧文件無任務∧未 dismiss)/尾聲 offer/工具列自取;`task_board_dismissed` 記帳 | intake 卡=已實作;尾聲 offer=plan T5e;工具列=已實作 |

盤=乾淨自取:**無 AI 預勾疊加層**(`interview:curation`+web `lib/curation.ts` **已退役**)。

## 6. 不變量(code 讀不出的規則;違反=repo 級 bug)

1. **AI 寫入唯一路徑=op→verify→`_pending`**。任何繞過 verify 直寫文件的 AI 路徑都是回歸。
2. **verify 必 blocking**(輸出護欄):純函式、零 LLM;quote 查無=整筆拒收,不降級為警告。
3. **backstop 禁 LLM 化**(§6.4 禁令):撿漏=確定性 sweep;只產 held 問題,永不寫文件。
4. **✓/✗ 無聲**(§6.3):決策只改文件+`review-events` 記帳,**不觸發 AI 回應**;
   被拒清單下回合經 context 注入(不重提、可自然問一句原因)。
5. **renumber=web 獨佔職權**:位置碼(T/O/P/K/S/A)由前端 `renumber()` 給;AI op 寫位置碼
   =verify ⑤ 拒收。後端永不重編碼。
6. **人改=直改**,不打標記;human rewrite **不告知模型**(Claude Code 先例);
   AI 可對任何已確認內容發提議(`_pending` 即提議載體),唯一禁令=無聲修改。
7. **引擎有效參考碼=`profile.selected_ocs_codes ∪ 文件碼`**(ADR 0031):0029 脫鉤後
   選參考只寫 profile——帳本/任務池/書記官方池/顧問前綴 2 全吃聯集,只看文件=鬼打牆
   回歸(session 6f807f1e)。職類建議走**聊天建議卡**(widget `precheck` 只含本回合
   搜尋真實命中碼;確認=前端 PUT 參考集合=人選,**AI 不代寫**);✕=
   `occupation_dismissed` 記帳→下回合知情換話術;參考集合空時前端常駐「待選」chip。
8. **態度只在文件層**;任務必掛職責;官方碼必來自參考集合(池)。
9. **boundary(劃線不談)無自動解除路徑**;held=FIFO 待問。
10. **前綴穩定**:consultant context 前綴 1/2 同 session byte 級穩定(禁時間戳/UUID 進前綴)
   ——provider 快取的前提(Anthropic 系路由須另帶 `cache_control`,見 llm_openrouter.py)。
11. **調教閉環**:改判準先改 `skills/*/SKILL.md`(SME 審)→ evals regression;不改碼。
12. **任務載體路由(ADR 0032,§5.1)**:官方任務**有逐字證據才直落綠字**(無 quote
    不落,留口頭/卡片);盤永遠人開——AI 只遞邀請(intake 卡/尾聲 offer),
    `task_board_dismissed` 後知情不重推;盤上勾=confirmed 不套綠(0028 D9);
    AI 程式化開 picker / 盤預勾疊加層=回歸。

## 7. 退役禁令(別把這些救回來)

- `app/authoring/`(LangGraph 圖)、`copilotkit_live_app.py`、web CopilotKit 全家
  (`Providers` 的 CopilotKitProvider、`/api/copilotkit`、InterruptHandlers)——**已刪(T12)**;
  production 入口=`run_live.py` 直起 `app.main:app`(:8001)。
- `interview_evidence`/`interview_suggestions` 表與 `interview:review` 端點——**已刪**;
  別再寫 evidence/建議層,溯源住 `_pending.src`。
- v1 `executor.py`/`commands.py`/`context.py`(set_slot 命令流)——**已刪**;勿回收其語彙。
- web `reviewMap.ts`/`SuggestionReview`/`CurationDialog`——**已刪**;四態渲染=`_pending`
  (`PendingMark.tsx`+`ocsDoc.ts` 輔助);任務檢查表=議程狀態機+側欄成組反問。
- `interview:curation` 端點/`run_curation`/web `lib/curation.ts`(盤預勾疊加層)、
  run_turn 的 `picker:"task"` widget——**已刪(0032)**;盤=乾淨自取,quote-backed
  判斷在裁剪縫直落綠字,別再蓋「AI 疊加層等人來盤裡確認」。
- `/ai/*` 端點=read-only 純函數,保留但**不是**共編路徑。

## 8. Evals(品質迴圈;apps/api/evals/)

雙指標:**Source Score**(程式算;分母=`_pending`∪accepted,分子=出處過 verify ②③)+
Answer Score(rubric 裁判,Phase 2)。promptfoo:Python provider 包引擎回合+Simulated User
四 persona(話少/跑題/自誇/矛盾);deterministic 斷言先行;CI=`.github/workflows/evals.yml`
(prompts/skills/引擎碼變更觸發)。golden 第一題 `JD-golden-001`(**SME gate:維護者審**)。

## 9. 指路

引擎碼:`apps/api/app/interview/`(scribe/verify/ledger/consultant/skills/…)·
横切:`apps/api/app/observability.py` · web:`apps/web/src/lib/ocsDoc.ts`(pending 輔助)+
`components/interview/{PendingMark,AgendaList,InterviewPanel,JobDocTable}.tsx` ·
契約:`packages/ocs-contract/schema/ocs-document.schema.json`(PendingMark/PendingSrc)·
技術驗證:[`2026-07-13-ai-redesign-raw-impl-verification.md`](../specs/2026-07-13-ai-redesign-raw-impl-verification.md)。
