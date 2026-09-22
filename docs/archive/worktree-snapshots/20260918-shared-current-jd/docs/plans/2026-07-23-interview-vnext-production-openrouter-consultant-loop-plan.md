# Interview AI vNext：Production OpenRouter 與最小顧問 Loop 實作計畫

- 狀態：complete（production backend slice；尚未接 local Web）
- 日期：2026-07-23
- Research：[production loop research](../specs/2026-07-23-interview-vnext-production-openrouter-consultant-loop-research.md)
- 前置：`turn.interpret/2.0.0`、`question.select/1.0.0`、Authoring Core、provider conformance均已完成

## 1. 切片與順序

### P1 Production provider promotion

1. 將schema catalog移到`app/interview_vnext/llm/schema_catalog.py`，以operation name解析：
   - `turn.interpret/2.0.0`；
   - `question.select/1.0.0`。
2. 將OpenRouter config／catalog／routing／Chat adapter移到`app/interview_vnext/providers/`。
3. production名稱：
   - `OpenRouterChatConfig`
   - `OpenRouterChatAdapter`
   - `build_openrouter_config`
   - `build_openrouter_binding`
4. `evals/`原路徑保留薄wrapper／alias，舊測試與batch不得複製實作。
5. `contains_test_data`由config明確決定，不得硬編碼。

最小gate：

- schema catalog針對兩個operation各一個正向案例；
-既有OpenRouter focused adapter suite；
-dependency guard。

### P2 Atomic durable command plan

在`application/durable_operations.py`加入只供verified operation使用的command-plan commit：

- non-empty、固定順序；
-每個command的`expected_state_version`必須連續；
-第一次reduce前比較context的state version/hash；
-同一UoW依序呼叫既有`_commit_command_core`；
-保存一個typed plan-result artifact，列出ordered command/reduction refs與final state；
-保存operation response artifact；
-checkpoint只在全部成功後轉committed；
-任一步CAS／domain failure整筆rollback；
-provider/network永不在UoW內。

不新增table、不改既有單command `commit_verified_operation()`。

### P3 Explicit `execute_question_select`

新增`application/question_select_executor.py`：

- build `QuestionAgenda`、question context、input、portable schema projection與request artifacts；
-沿用durable attempt／provider gate／schema repair規則；
- local parse `QuestionSelectOutput`；
- `verify_question_select_output`拒絕時typed failed；
- `materialize_question_selection`產生既有command plan；
- P2原子commit；
- committed／failed／pending可replay。

第一版不抽象成generic operation executor。只將真正provider-neutral且已存在的helper移到小型shared module；若抽取成本高，
question executor可直接使用durable primitives，但不得複製OpenRouter wire parser。

### P4 Consultant loop control

新增`application/consultant_loop.py`：

- pure `plan_loop_control(state, latest_receipt, operation_id, occurred_at)`；
- STOP -> `TransitionSessionCommand(FINISHING)`；
- explicit shift -> unresolved gaps deferred -> episode closing -> closed；
- possible shift／possible close -> 不mutation；
- `continue_after_interpretation(...)`先套control，再讀Authoring digest，再執行question select；
-若STOP則question LLM call count必須為0。

控制command使用既有`apply_durable_command`；shift command IDs使用UUIDv5固定label，expected version逐步遞增。

### P5 Composition與live smoke

新增最小composition helper：

-環境只讀`OPENROUTER_API_KEY`；
-開發預設request model為`openai/gpt-5.4-mini`、exact endpoint為`openai/flex`、reasoning effort為`low`；
-catalog必須解析到permanent canonical `openai/gpt-5.4-mini-20260317`；若官方catalog已改變則停止，不偷偷沿用舊snapshot；
-啟動時取得一次model／endpoint snapshot、preflight；
-同一secret-free config建立兩個operation binding；
-同一adapter instance服務兩個operation；
-不把key或完整環境dump進Capture。

live smoke只跑`question.select`：

-使用測試session／document；
-exact model與endpoint由現行catalog解析，不使用auto/free/latest；
-最高成本以owner既有OpenRouter key上限控制；
-成功條件是wire success、conformance eligible、local verifier accepted；
-live失敗不得改寫scripted gate為通過。

## 2. 少量高價值測試

1. schema catalog可解析兩個active output contract；
2. production adapter outbound body仍為exact schema、single HTTP call；
3. atomic command plan成功時兩個command與checkpoint一起commit；
4.第二個command失敗時第一個command也不留存；
5. question executor以scripted provider在real PostgreSQL commit問題+QuestionFrame；
6. STOP不呼叫question LLM；
7. explicit shift關閉episode後走broaden；
8.一個mocked production composition確認key不進config/artifact。

不做每個error code、每個provider response shape或所有episode排列的新增matrix；既有provider與durable regression就是安全網。

## 3. 停線條件

- production必須import `evals.*`才能完成；
-需要新增migration／table；
-必須讓provider memory成為state authority；
-command plan無法原子提交；
-explicit shift需要猜測或改寫employee Evidence；
-live只能靠fallback／auto route／plugin mutation才成功；
-任何secret出現在git diff或Capture。

## 4. 交付格式

- code與最小tests；
-研究、README、AGENTS與本計畫回寫實際證據；
-owner author／committer；
-不push；
-回報live model、endpoint、request ID、usage／cost；不得回報API key。

## 5. 實際交付（2026-07-23）

### 5.1 完成內容

- OpenRouter schema catalog、catalog/preflight、config/binding、routing normalizer 與 Chat adapter 已升至
  `app/interview_vnext/`；`evals/`只保留相容 wrapper，production 不 import `evals.*`。
- `question.select/1.0.0` 已有顯式 durable executor；沒有新增 generic agent runner。
- verified question 的「顧問問題 + gap asked／open episode」使用同一 transaction 的
  `CommittedCommandPlan` 提交；不新增 table 或 migration。
- fresh-process 從 `VERIFIED` 恢復時載回 immutable verification artifact，並確認 action／ordinal 與 output
  一致；不以當下程式碼悄悄取代先前 verdict。
- `consultant_loop.py`只負責三個 deterministic control：
  - `DialogueAct.STOP`：進 `FINISHING`，不呼叫 question model；
  - `EpisodeSignal.EXPLICIT_SHIFT`：defer unresolved gaps，再將 episode `open -> closing -> closed`；
  - `possible_shift`／`possible_close`／一般 continue：不做不可逆流程 mutation。
- `continue_after_interpretation()`由 caller 傳入 bounded `JobStateDigest`。第一版不讓 Interview application
  直接依賴 Authoring repository；local Web/API composition 在呼叫前讀 digest。這是刻意縮小耦合，不是漏做。
- 固定 development profile：
  - model `openai/gpt-5.4-mini`；
  - canonical `openai/gpt-5.4-mini-20260317`；
  - exact endpoint `openai/flex`；
  - provider `OpenAI`；
  - reasoning `low`、reasoning content excluded；
  - fallback/cache/mutating plugins disabled。

### 5.2 最小驗證

- production promotion 後 OpenRouter/OpenAI/schema/dependency focused regression：`319 passed`。
- question／loop／production provider／real PostgreSQL 精簡整合 gate：`186 passed`。
- 最終擴大 no-network vNext regression：`803 passed / 101 skipped / 482 deselected / 0 failed`
  （skip為既有 DB test nodes）。
- 最終 focused provider/question/loop + real PostgreSQL gate：`254 passed / 0 failed`。
- 真 PostgreSQL vertical 證明 `question.select` 提交 consultant turn、QuestionFrame 與 episode，replay 不重打
  provider。
- 沒有 migration、dependency、Web route、SaaS 或 key/bundle 進 git。

依 owner「加速成品、測試不追求全排列」裁決，本切片沒有另建所有 command-plan failure 組合、episode 排列或
provider response matrix；既有 durable transaction/provider regression 加上一條 real-PG vertical 作安全網。

### 5.3 Paid live smoke

使用 `apps/api/.env`的 key 以 process-local environment 注入，key 未輸出、未寫入 config/Capture/git。

| 欄位 | 結果 |
|---|---|
| outcome | `succeeded` / `completed` |
| requested/resolved model | `openai/gpt-5.4-mini` |
| upstream | `OpenAI` / `openai/flex` |
| route | `direct`，單一 upstream attempt |
| pipeline/cache | `clean` / `absent` |
| tokens | input `835`、output `109`、reasoning `38` |
| observed cost | `US$0.000558375` |
| provider request ID | response 未提供，保存為 `null`，未偽造 |
| product gate | structured output、attribution conformance、local semantic verifier、atomic DB commit 全通過 |

第一次 diagnostic run 的 request 使用固定測試時間，第一個 local durable attempt 在 HTTP 前即 deadline
expired；第二個 attempt 才送出唯一 HTTP 並成功。這是臨時 smoke clock 的限制，不是 OpenRouter timeout，也沒有
放寬 production gate。最後一次驗收同樣只有一個實際 upstream attempt並完整通過。

### 5.4 下一個產品切片

現在可以開始最小 local Web vertical：

1. 員工送出一段回答；
2. append employee turn；
3. production OpenRouter 執行既有 `turn.interpret/2.0.0`；
4. 呼叫本切片的 `continue_after_interpretation()`；
5. UI 顯示下一個顧問問題與目前 JD canvas。

下一切片仍不做 SaaS、登入、帳號、K/S 或 graph framework。先讓一輪真實對話在 localhost 可見；之後才做
`episode.code`與有 Evidence linkage 的 task/output AI proposal（接受／修改／拒絕）。
