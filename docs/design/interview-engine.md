---
title: 訪談引擎 × 文件工作台 — 端到端設計(v2 顧問 agent)
audience: agent-primary(也給人)
scope: apps/api app/interview/* + routes/interview + apps/web 面板/稽核頁(引擎 v2)
updated: 2026-07-08
---

# 訪談引擎 × 文件工作台 — 端到端設計(v2:顧問 agent + 書記 + 帳本 + backstop)

> **主讀者 = coding agent。** 目的:不看 code 也能改對這條線——不亂發明端點、不把信任機制
> 交給 LLM、不繞過單一寫入路徑。**living:動到這條線的碼,同 commit 更新本檔。**
> 決策:ADR [0027](../adr/0027-interview-engine-v2-consultant-agent.md)(v2 四組件;修正 0025 #1)、
> [0023](../adr/0023-interview-engine-stateless-turns.md)(無狀態回合,留用)、
> [0024](../adr/0024-llm-wiring-select-schema.md)(受限解碼,留用)、[0026](../adr/0026-interview-turn-model-role.md)(模型 role)。
> spec:[`2026-07-08-interview-engine-v2-spec.md`](../specs/2026-07-08-interview-engine-v2-spec.md);
> 研究:[`2026-07-06-consultant-not-formfiller-redesign-research.md`](../specs/2026-07-06-consultant-not-formfiller-redesign-research.md)(八輪+§16 實作發現)。

## 1. 一句話

員工在工作台開「AI 訪談」側欄;每回合**兩個 LLM 各做一件事**——**書記**(便宜模型)把員工
發言受限解碼抽成結構化寫入、交 executor 確定性落地;**顧問**(強模型)拿著帳本缺口、無寫入權、
用 READ 工具查官方標準,自然對話、回述+追問。**確定性覆蓋帳本**(純程式非 LLM)追進度、
守完成閘門、偵測飽和推進;收尾**backstop**(便宜模型)複查漏記/出處只提案。信任靠「不是 LLM」
的帳本 + 寫入守衛(官方碼零幻覺、引文逐字驗證)。**無狀態回合:狀態=DB 進度列+文件本身。**

## 2. 四組件(ADR 0027)

| 組件 | 是什麼 | 碼 | 權力 |
|---|---|---|---|
| 🧠 顧問 | LLM 對話主導 + READ 工具(查職類/職能) | `consultant.py`+`tools.py`+`agent_loop.py` | **無寫入權**;說話+查 |
| ✍️ 書記 | 獨立 LLM pass:發言→結構化寫入(兩通道) | `scribe_schema.py`+`scribe.py` | 提命令,executor 執行 |
| 📋 帳本 | 純程式(非 LLM):覆蓋/閘門/飽和 | `ledger.py` | 決定「問完沒/該問啥」 |
| 🔍 backstop | 收尾便宜 LLM:漏記/出處複查 | `backstop.py` | **只提案**,不直寫 |

## 3. 資料模型(真名)

| 東西 | 住哪 | 要點 |
|---|---|---|
| 任務細項 `details`(11 槽) | 文件 `task["details"]`;契約 `TaskDetails` | 正式欄位;OCS 官方來源永遠無/`null` |
| 能力區塊 `competency_blocks[0]` | 文件;`outputs/knowledge/skills`(CodeName)、`indicators`(CodeText) | 書記兩通道寫:官方碼(池)/自訂(name+quote) |
| 態度 `ocs_attitude.attitudes` | 文件層(非逐任務;iCAP 合併呈現) | 書記**只提建議**(§15.3 員工確認才落) |
| 進度列 `interview_sessions` | DB | status/phase/focus/**`ledger_state`**(attempts/tier_override/probe/last_gap;僅存不可重算態) |
| 逐字稿 `interview_turns` | DB | (session,seq) 唯一;quote 驗證真相來源 |
| 證據 `interview_evidence` | DB | doc_path↔quote↔verified↔**`review`**(auto/pending/accepted/reverted);不落文件 |
| 建議 `interview_suggestions` | DB | pending/accepted/rejected=未套用 diff(ADR 0025) |
| LLM 稽核 `interview_llm_calls` | DB | 每回合每次呼叫一列(role/model/耗時/tool_calls/guard_verdicts;多租戶 observability) |

## 4. 一回合資料流(runtime;`service.run_turn`)

```
面板 send(text) → POST …/interview:turn(注入 db+llm+knowledge)
  ① 載入 draft+session+逐字稿;append 員工 turn
  ② 書記 scribe_pass(便宜、序列先行;失敗不擋顧問=fail-open 對話、fail-closed 寫入):
       build_pool_inputs←knowledge.competencies(官方池;文件 block 預設空)
       select_schema(scribe_schema:兩通道 strict enum;role=select)→重試1
       apply_scribe(確定性守衛:quote 逐字驗、pool_id∈pools[kind]、跨任務歸位)
         池 K/S/O verified→直寫+evidence.review=pending;自訂/draft/態度/add_task→建議層
  ③ 寫回 upsert_draft(雙 token)→409 重讀重放同 records 一次→再衝突放棄直改(人優先)
       evidence(帶 review)/suggestions 落庫
  ④ 帳本:note_attempt(上一輪 last_gap 是否進帳→飽和計數)→ next_gap(本輪提示)→ ledger_state 存回
  ⑤ 顧問 chat_with_tools(role=interview;messages=帳本摘要+文件+待核准+近窗對話;
       手刻迴圈 run_tool_loop:READ 工具 dispatch、tool_call_id 對回、max_iter 補問)
  ⑥ 保底:say 空→next_gap 合成問題(靜默回合=實戰死穴);append 顧問 turn
  ⑦ 稽核落庫(書記+顧問各一列);回 {say, doc_changed, pending_suggestions, progress:{phase,coverage}}
收尾 POST …/interview:finish:backstop_pass→建議化→phase=review
```

## 5. UI 動作 → 請求對照

| 動作 | 元件 | 網路 |
|---|---|---|
| 開始/續談 | InterviewPanel | `POST …/interview:start`(冪等;**空白 doc 也可起跑**=survey 引導選職類,§9.3) |
| 回答 | InterviewPanel | `POST …/interview:turn {text}` → 回 `progress.coverage{filled,required}` |
| 收尾 | (收尾流程) | `POST …/interview:finish`(backstop+轉 review) |
| 批審套用 | SuggestionReview → 面板 decide | `POST …/interview:review {accept,reject}` → **前端** `applyAccepted`(自訂能力/態度=**append 陣列**;`appendAtPath`)→ persist |
| 顧問稽核 | `/documents/[id]/interview` 頁 | `GET …/interview`(逐字稿+證據+建議) |
| 人直接改文件 | 既有編輯器 | PATCH(diff 記入 human_touched) |

## 6. 不變量(code 讀不出的規則)

1. **顧問無寫入權、書記無對話**:顧問只 `chat_with_tools`(READ 工具)說話;所有寫入經書記
   `select_schema`→`apply_scribe`→executor 守衛。兩次獨立呼叫(顧問說話零格式負擔、書記受限
   ——「兩邊都安全」;§10.4)。**別把 set_slot 語彙放回顧問 prompt。**
2. **官方碼零幻覺**:書記池通道 pool_id 走 strict enum(當回合合法池),對不上→自訂通道
   (name+quote)。「零幻覺」=宣稱官方的必真官方,不是全部得官方(§9.1)。
3. **風險分層寫入**(修正 ADR 0025 #1):低風險(池 K/S/O、細項槽 verified)直寫+`review=pending`
   批次審;高風險/影響結構(自訂任務、模糊歸類、**態度**)→建議層。不再「人沒碰過就直改不標記」。
4. **進度=帳本、不是 LLM**:next_gap/飽和/完成閘門全在 `ledger.py`(純函式);反例=無狀態機的
   LLM 自判進度→88% 該追未追(arXiv 2410.01824,§10.2)。門檻數字=v1 出廠值,改=跑
   `interview_sim.py` 校準留紀錄,不改碼形。
5. **path 文法全域一致**(`diff.py`/`executor.py`/`ledger.py`/web `interviewDoc.ts` 鏡像):
   段以 `.` 連接,list 段用穩定 id(`_tid/_uid/_id`)優先、index 後援。
6. **quote 溯源住 session 不落文件**;每筆寫入綁引文,executor 驗「NFKC+空白摺疊後為逐字稿子串」。
7. **手刻迴圈藏 `LlmPort` 後**(12-Factor F8);迴圈邏輯在 `agent_loop.run_tool_loop`(可測)、
   adapter 只提供真實呼叫。換模型=重跑 `validate_select_schema.py --target scribe` + `interview_sim.py`。
8. **員工輸入=資料非指令**(OWASP LLM01):顧問/書記 prompt 明示;工具唯讀、寫入鎖 enum+人審、
   無對外動作、max iterations——注入天生緩解。
9. **舊 authoring graph(LangGraph)+ v1 單 LLM 路徑(context.build_prompt/turn_output_schema)
   = 退役待清**:v2 全新實作;v1 `context.py`/`commands.py` 待 v2 穩定後一次清除。
10. **空白文件先 onboarding、不掉態度**(§16.16):`next_gap` 文件無任務時回 `ONBOARD_OCCUPATION`
    (無 ocs_code)/`ONBOARD_TASKS`(有碼無任務),**不受 is_stalled 影響**(選職類前不許
    fall through 到態度);`ledger_summary` 對 onboarding 吐引導語(問實際做什麼→查職類→提
    具體職類請他從〔選職類〕確認),顧問 prompt 硬規則「選職類前不問態度、不硬猜職類硬套」。
    反例=空白文件掉進態度縫→顧問問態度→模糊 query 語意搜尋→幻覺職類(production bug 8ba32711)。
    **書記無權設 `ocs_code`**;選職類靠既有〔選職類〕按鈕(Tier 1)。職類清單 widget(ADR「選單
    阻斷確認」)=Tier 2 待做,屆時接 `TurnResult.widget`(現恆 None)。

## 7. Limitations(ADR 0027;誠實記載)

- **單信息源**:v1=單一員工自述+顧問人審(=第二來源最小版);主管確認、同職務多員工合併
  =路線圖(§17)。**純文字**:語音/情緒訊號=未來縫。延後:書記並行化、self-consistency、
  live critic、Pydantic AI 遷移。

## 8. 指路

- 碼:`apps/api/app/interview/`(ledger/slots/scribe_schema/scribe/tools/agent_loop/consultant/
  backstop/executor/commands/context/service/diff)+ `routes/interview.py` + `adapters/interview_repo.py`。
- web:`components/interview/InterviewPanel|SuggestionReview` + `lib/interviewDoc.ts` + `hooks/useInterview.ts`。
- 黃金範本(品質尺):[`../specs/2026-07-05-golden-sample-software-tester.md`](../specs/2026-07-05-golden-sample-software-tester.md);
  問句庫=研究紀錄 §15;prompt 全文+sim 劇本=[`../specs/2026-07-08-interview-v2-prompts-and-scenarios.md`](../specs/2026-07-08-interview-v2-prompts-and-scenarios.md);
  驗收/校準紀錄=研究紀錄 §16(§16.1–§16.14)。
