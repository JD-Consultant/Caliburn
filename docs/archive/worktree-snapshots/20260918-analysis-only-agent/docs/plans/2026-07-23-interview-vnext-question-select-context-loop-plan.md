# Interview AI vNext：`question.select` Context／Loop 最小垂直切片實作計畫

- 狀態：completed
- 日期：2026-07-23
- Authority：[ADR 0038](../adr/0038-interview-vnext-context-engine-and-professional-consultant-workflow.md)
- Research：[question selection research](../specs/2026-07-23-interview-vnext-question-selection-context-loop-research.md)
- 前置：R5-A／R5-BC／R5-D、Minimal Authoring Core 已完成

## 1. 交付目標

實作一條 provider-neutral、無新資料表的最小垂直切片：

```text
InterviewState + JobStateDigest
  -> deterministic QuestionAgenda
  -> QuestionSelectContext
  -> QuestionSelectInput
  -> scripted structured output
  -> local verification
  -> existing domain command plan
  -> reducers persist consultant turn + QuestionFrame (+ gap asked/open episode)
```

完成後能證明下一題不是憑完整聊天紀錄自由生成，而是從 committed Evidence／accepted document 的少量候選中選出。

## 2. 不在本切片

- production route／OpenRouter live call；
- `episode.code` 與文件 proposal；
- K/S、指標、主要職責、匯出；
- Web UI／API endpoint；
- migration、新 table、SaaS、登入、組織、多租戶；
- 通用 graph／agent framework；
- 大型 eval matrix。

## 3. 檔案與責任

### 3.1 Agenda

新增 `application/agenda.py`：

- `QuestionAgendaCandidate`
- `QuestionAgenda`
- `build_question_agenda(state, job_digest)`

候選必須有 operation-local ordinal、gap dimension、question goal、priority features、supporting Evidence IDs 與來源類型。
existing gap 使用既有 `gap_id`；synthetic candidate 只在本次 projection 中存在，不先 mutation domain。

排序：

1. contradiction；
2. high JD value；
3. non-redundant；
4. low sensitivity／burden；
5. dimension；
6. stable key。

cap 固定為 3。

### 3.2 Context

修改 `llm/context.py`：

- `QuestionSelectContextPolicy` 1.0.0；
- `QuestionSelectContextPacket`；
- `QuestionSelectContextBuildResult`。

不把新 packet 塞進既有 `ContextPacket.v2` union，避免在同 schema/version 下改寫已發布 contract。

修改 `application/context_builder.py`，新增：

```python
build_question_select(
    *,
    state: InterviewState,
    agenda: QuestionAgenda,
    job_digest: JobStateDigest,
    operation_id: UUID,
    operation_definition_hash: str,
    policy: QuestionSelectContextPolicy,
) -> QuestionSelectContextBuildResult
```

section order：

1. injection boundary；
2. latest employee turn；
3. recent consultant question；
4. active episode；
5. agenda candidates；
6. supporting evidence；
7. job state digest；
8. dialogue limits。

最多 3 candidates、6 Evidence；transcript只選必要的最近 turn，不提供完整歷史。manifest要明列所有 selected/excluded state source；
digest以 `digest_hash` 封裝在 packet，且 document/session必須匹配。

### 3.3 LLM contract

新增 `llm/question_select.py`：

- `QuestionSelectInput`
- `QuestionSelectAction`
- `QuestionSelectOutput`
- `QuestionSelectRejectCode`
- `QuestionSelectVerificationReport`

Output：

```text
acknowledgement: 0..160 chars
action: ask_gap | broaden_coverage | offer_finish
selected_gap_ordinal: int | null
question_text: 1..320 chars
```

規則：

- `ask_gap` 必須有 ordinal；
- 其他 action 必須為 null；
- `offer_finish` 的 question text 仍是可回答的單一邀請，例如是否要完成或繼續補充；
- 不輸出 ID、frame、reasoning。

### 3.4 Prompt／operation document／schemas

新增：

- `llm/prompts/question-select.1.0.0.md`
- `llm/operations/question-select.1.0.0.json`
- `llm/context_policies/question-select.1.0.0.json`
- 四個 active schemas：context、input、portable output、verification report。

prompt 依 outcome-first 寫法，只保留 role、evidence boundary、decision rules、question quality、output／stop boundary。
不加入 few-shot，除非後續 eval 證明有必要。

operation：

- no tools；
- one model attempt；
- schema repair最多一次；
- semantic repair 0；
- no chain-of-thought；
- 4,096 output token上限（實際 schema輸出遠低於此值）。

### 3.5 Application verifier／materializer

新增 `application/question_select.py`：

- `project_question_select_input(context_result)`
- `verify_question_select_output(input, output)`
- `materialize_question_selection(...) -> QuestionSelectionPlan`

本地驗證：

- ordinal 存在且 action 合法；
- action符合 agenda；
- question 非最近 consultant question 的正規化重複；
- 不接受空白或只含 acknowledgement 的問題；
- selected candidate source與 state仍一致。

materializer：

- 建 `AppendConsultantQuestionCommand`；
- existing gap時建 `TransitionGapCommand(...ASKED...)`；
- broaden coverage且無 active episode時建 `OpenEpisodeCommand`；
- ID 全部由 `uuid5(operation_id, stable label)` 決定；
- `expected_state_version` 逐 command遞增，供 sequential reducer使用；
- application建 QuestionFrame definition，model不建。

先回傳 typed command plan，不新增通用 batch executor或新 UoW。production composition 留到下一切片。

## 4. 最小測試

為配合owner「少量高價值測試、不要追求全覆蓋」的裁決，實作時收斂成一個 focused test file：

1. `test_interview_vnext_question_select.py`
   - empty/no episode -> broaden；
   - action without output -> synthetic output candidate；
   - unknown time scope視為coverage但不改寫Evidence；
   - existing high-value gap排序與asked transition；
   -已有 output不再合成 output gap；
   -cap/determinism；
   - context只含 bounded必要資料與 matching digest；
   - invalid ordinal／duplicate question fail closed；
   - output gap materializes slot QuestionFrame；
   - broaden materializes open-narrative frame + episode；
   - scripted output經 reducers完成 consultant turn + active frame。

既有 ContextBuilder、schema writer、operation document drift tests需保持綠；不擴充 exhaustive corruption matrix。

## 5. 驗收

- 新 focused tests 全綠；
- 既有 `context_builder`、`question_frame`、`domain`、`workflow_reducers`、LLM schema／operation drift tests全綠；
- schema／policy／operation generator重跑 byte-stable；
- no migration；
- `app/` 不 import `evals.*`；
- `git diff --check`乾淨；
- 無 network／paid live；
- 一個 code commit、一個 docs/status commit；author／committer只使用 repo owner，未 push。

## 6. 下一步（本切片完成後）

1. production application service 以既有 durable executor呼叫 `question.select`；
2. OpenRouter provider binding與真 live smoke；
3. 最小 local Web conversation + JD canvas；
4. 用實際員工訪談 failure更新 question eval；
5. 再做 `episode.code` 與 task/output proposal。

不得在進入第 1 步前順手做 K/S、通用 graph、SaaS 或大規模 refactor。

## 7. 交付紀錄（2026-07-23）

### 7.1 Commit

- code：`ba1e4b8 feat(interview): select grounded next questions`
- author／committer：`ArIs0x145 <aris0x145@gmail.com>`
- branch：`research/llm-interview-integration`
- 未push。

### 7.2 實際交付

- `QuestionAgenda`是pure deterministic projection，不新增table／planner agent；
- 最多三個candidate，第一版主動補action、output、purpose，既有gap依priority排序；
- unknown time scope只作「已談過此工作」的coverage訊號，不被改成current；past/future/hypothetical仍排除；
- `QuestionSelectContextPacket`使用獨立`question_select_context.v1`，沒有偷偷改寫既有`ContextPacket.v2` union；
- packet只含latest employee turn、最近consultant question、active episode、最多3個gap、最多6筆supporting Evidence、
  bounded `JobStateDigest`與dialogue limits；
- model output只有acknowledgement、action、ordinal、question text；
- application驗action／ordinal／重複／明顯多問句，再建立UUIDv5 identities、QuestionFrame與existing domain commands；
- synthetic output／purpose與standard可形成slot frame；無法安全綁定的dimension使用open narrative，不猜target；
- broaden coverage先append consultant question再開新episode；existing gap先append question再轉asked；
- prompt依2026 OpenAI outcome-first guidance精簡；no tools、original call加最多一次schema repair、semantic repair 0；
- production OpenRouter composition、paid live、API、Web、episode.code與document proposal仍未做。

### 7.3 驗證

| Gate | 結果 |
|---|---:|
| 新增產品案例 | `6 passed` |
| affected focused regression | `159 passed / 0 failed` |
| full API no-network | `1166 passed / 217 skipped / 0 failed` |
| migration | 無新增；head仍`0011` |
| secret／eval import／diff check | clean |

完整suite第一次執行繼承了本機不合法的`DEBUG=release`，在test collection前被Pydantic拒絕；沒有修改`.env`，只在第二次
test process內設`DEBUG=false`，其後取得上表全綠結果。這不是產品碼或測試失敗。

### 7.4 已知邊界

- 這是provider-neutral scripted vertical，不代表真模型問題品質已通過；
- explicit `STOP`仍應由上層Loop在呼叫`question.select`前截斷；
- active episode關閉／換題的完整orchestration留給production composition slice；
- 一個episode最多兩個follow-up的budget已生效，但品質門檻要用真訪談資料校正；
- 公版retrieval、K/S與indicator尚未進入本operation，符合既定交付順序。
