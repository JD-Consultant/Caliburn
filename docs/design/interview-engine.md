---
title: 訪談引擎 × 文件工作台 — 端到端設計
audience: agent-primary(也給人)
scope: apps/api app/interview/* + routes/interview + apps/web 面板/稽核頁(引擎 v1)
updated: 2026-07-05
---

# 訪談引擎 × 文件工作台 — 端到端設計(職務說明書訪談面)

> **主讀者 = coding agent。** 目的:不看 code 也能改對這條線——不亂發明端點、不把
> 信任機制交給 LLM、不繞過單一寫入路徑。**living:動到這條線的碼,同 commit 更新本檔。**
> 決策:ADR [0023](../adr/0023-interview-engine-stateless-turns.md)(骨幹)/
> [0024](../adr/0024-llm-wiring-select-schema.md)(接線)/ [0025](../adr/0025-coedit-authority-dual-channel.md)(共編權限);
> spec:[`2026-07-05-interview-engine-v1-spec.md`](../specs/2026-07-05-interview-engine-v1-spec.md)。

## 1. 一句話

員工在工作台開「AI 訪談」側欄,LLM 顧問**每回合**從枚舉指令集選動作(填槽/追問/抓漏/跳過/
前進),executor **確定性**執行(通道分流+守門+quote 驗證),文件經**編輯器同一條 draft
seam** 即時長出細項;人碰過的內容走建議層批審;顧問事後開稽核頁看「每個槽值對到員工哪句
原話」。**無狀態回合:狀態=DB 進度列+文件本身,引擎零私有長壽命狀態。**

## 2. 資料模型(真名)

| 東西 | 住哪 | 要點 |
|---|---|---|
| 任務細項 `details`(11 槽) | 文件 `task["details"]`;契約=ocs-contract `TaskDetails` | **正式欄位**(活過 finalize/export);OCS 官方來源永遠無/`null` |
| 進度列 `interview_sessions` | DB | status/phase/focus(task_path+skipped)/counters(追問記帳)/human_touched;**partial unique 守一 profile 一 active** |
| 逐字稿 `interview_turns` | DB | (session,seq) 唯一;**quote 驗證的真相來源**(勞動部 2.2.2 紀錄義務) |
| 證據 `interview_evidence` | DB | doc_path↔quote↔verified;顧問稽核視圖的料;**不落文件**(文件乾淨) |
| 建議 `interview_suggestions` | DB | pending/accepted/rejected;= 未套用 diff(ADR 0025) |

## 3. 一回合資料流(runtime)

```
面板 send(text) → POST …/interview:turn
  ① 載入 draft + session + 逐字稿;append 員工 turn
  ② context.build_prompt:結構化狀態優先(焦點任務現況/缺口+SLOT_DEFS 問法/預算/已跳)
     + 近 12 回合窗——不整卷重播
  ③ LlmPort.select_schema(turn_output_schema(choice_ids)) ← 受限解碼(0024;
     ask_choice 變體只在有池 id 時存在;model_select 須過對抗驗收)
  ④ TurnOutput 語義驗證;違規→帶錯誤重問 1 次→仍壞 LlmSchemaError→route 502
  ⑤ executor.apply(確定性,LLM 繞不過):
       set/correct:path∈human_touched→建議層;否則直改(details 缺殼自動建)
       add_task/add_duty:一律建議(renumber=前端 ocsDoc 職權)
       ask:每槽預算(v0=2)超額擋;advance:gate_missing 扣 justified-skip 才放行
       quote:NFKC+空白摺疊=逐字稿子串;失敗標 unverified 不阻塞
  ⑥ 寫回 upsert_draft(雙 token)→409 重讀重放 1 次→再衝突→本回合直改全數建議化
     + evidence/suggestions/counters/skipped/phase 落庫 + 顧問 turn 落逐字稿
  ⑦ 回 {say, question|widget, doc_changed, pending_suggestions, progress}
web:doc_changed → invalidate ["document"] → data-layer 外部變化 effect 重設 baseline
     (LLM 寫入=外部變化,零新機制)
```

## 4. UI 動作 → 請求對照

| 動作 | 元件 | 網路 |
|---|---|---|
| 開始/續談 | InterviewPanel | `POST …/interview:start`(冪等;無任務→409 no_tasks) |
| 回答/選卡片 | InterviewPanel(ChoiceCard 送文字) | `POST …/interview:turn {text}` |
| 批審套用 | SuggestionReview → 面板 decide | `POST …/interview:review {accept,reject}` → **前端** `applyAccepted` → `persist`(autosave PATCH) |
| 顧問稽核 | `/documents/[id]/interview` 頁 | `GET …/interview`(逐字稿+證據+建議歷史) |
| 人直接改文件 | 既有編輯器 | PATCH(**diff 記入 human_touched**,`interview/diff.py`) |

## 5. 不變量(code 讀不出的規則)

1. **LLM 不選通道、不能繞 guard**:分流/門檻/預算/quote 驗證全在 executor(確定性);
   指令集是**受限解碼 enum**——改詞彙表=改 `commands.py` schema,不是改 prompt。
2. **單一寫入路徑不破**:引擎 server 端寫 draft 走 `upsert_draft` 同 seam;**人核准的建議
   由前端套用**(`applyAccepted`+autosave PATCH)——「人核准的變更=人的寫入」;
   `:review` 只轉狀態。add_* 永遠不 server 套(renumber 是前端 `ocsDoc.renumber` 職權)。
3. **path 文法全域一致**(`diff.py`/`executor.py`/web `interviewDoc.ts` 三處鏡像):
   段以 `.` 連接,list 段用穩定 id(`_tid`/`_uid`/`_id`)優先、index 後援——改文法要三處同步。
4. **quote 溯源住 session 不落文件**:契約文件只有「結論」;稽核走 evidence join。
5. **覆蓋門檻/預算/core 判準數字 = v0 出廠值**(`slots.py`/`executor.py` 常數):
   改數字=跑校準(`evals/interview_sim.py`)留紀錄 `docs/specs/`,不改碼形。
6. **select_schema 失敗必須顯式**(`LlmSchemaError`→502/503),不准靜默降級成提示層;
   換 `model_select`=重跑 `scripts/validate_select_schema.py` 留紀錄(0024 驗收紀律)。
7. **舊 authoring graph(LangGraph)= 退役待清**:新引擎全新實作不整合舊碼(0023 決定 6);
   舊圖/AG-UI/checkpointer/CopilotKit provider 在新引擎可用後一次清除,期間互不干擾。

## 6. 指路

- 端點面:[`apps/api/README.md`](../../apps/api/README.md);碼:`apps/api/app/interview/`
  (slots/commands/executor/context/service/diff)+ `routes/interview.py` + `adapters/interview_repo.py`。
- web:`components/interview/InterviewPanel|SuggestionReview` + `lib/interviewDoc.ts` +
  `hooks/useInterview.ts`;資料層機制 [`apps/web/docs/data-layer.md`](../../apps/web/docs/data-layer.md)。
- 編輯器內容面(池/選單/`_ref`):[`editor-knowledge-pack.md`](editor-knowledge-pack.md)。
- 黃金範本(品質尺):[`../specs/2026-07-05-golden-sample-software-tester.md`](../specs/2026-07-05-golden-sample-software-tester.md);
  驗收紀錄:select_schema 對抗驗收 + interview_sim 校準(`docs/specs/`)。
