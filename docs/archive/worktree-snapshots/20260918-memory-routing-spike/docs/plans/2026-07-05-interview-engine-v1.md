# 訪談引擎 v1 — 實作計畫

> **依據**:spec [`2026-07-05-interview-engine-v1-spec.md`](../specs/2026-07-05-interview-engine-v1-spec.md)
> (定稿)+ ADR 0023/0024/0025。**紀律**:一 task 一 commit、綠了才 commit、TDD(測先行)、
> 文檔義務同 commit;**不 push**。收尾打 tag `interview-v1`。
> **驗證環境**:api `cd apps/api && uv run pytest -q`;web `npm run test` + `npx tsc --noEmit`;
> 契約 `packages/ocs-contract/scripts/check-codegen.sh`;遷移 `npm run db:migrate`。

## 全域約束

- 引擎狀態只住 DB(sessions 表)+ 文件;**禁止**模組級可變狀態(ADR 0023)。
- 引擎寫文件一律走既有 draft 儲存 seam(帶雙 token;409 → 重讀重放一次 → 再衝突建議化)。
- LLM 不選寫入通道、不能繞 guard——分流與門檻全在 executor(ADR 0025/0023)。
- quote 驗證:NFKC + 空白摺疊後為逐字稿子串;失敗 retry 1 → 標 unverified。
- 所有新 pydantic 模型 `extra="ignore"` 慣例對齊 indexer-contract `_Base`。

---

## Phase 0 — 契約

### T1 ocs-contract:task 加 `details`(11 槽 optional)

- **檔**:`packages/ocs-contract/schema/ocs-document.schema.json`(task $def 加
  `details: {$ref: TaskDetails}`,新 $def `TaskDetails`:11 欄全 optional——
  `frequency/duration/volume/trigger/inputs/tools/collaborators/wait_points/exceptions/standards`
  為 `["string","null"]`,`time_share_pct` 為 `["number","null"]`)→ 跑 codegen 重生
  pydantic(`src/`)與 TS(`types/`)。
- **步**:①改 schema ②跑 `scripts/check-codegen.sh`(或其內部 regen 命令)③`git diff` 檢查
  兩端生成物只多 `details` ④api/web 測試綠(details optional 不影響既有)
  ⑤更新 `docs/ocs-schema.md`(details 節)。
- **驗**:check-codegen 綠;`uv run pytest -q`(api)綠;`npx tsc --noEmit`(web)綠。
- **commit**:`feat(contract)!: ocs-document task 加 details 11 槽(additive optional;訪談引擎 v1)`

## Phase 1 — 資料層(api)

### T2 四張表 + models + repo

- **檔**:`apps/api/alembic/versions/xxxx_interview_tables.py`(sessions/turns/evidence/suggestions,
  欄照 spec §2;sessions 加 partial unique index `job_profile_id WHERE status='active'`)、
  `app/adapters/db/…`(照既有 persistence 模式放 models + `InterviewRepo`:
  `get_active/create/update_session/append_turn/add_evidence/add_suggestion/list_pending/apply_suggestion_status`)。
- **測**:照 `tests/` 既有 persistence 測試模式(先讀 conftest 選 fake/DB 路線);
  CRUD + 「同 profile 第二個 active → 拒絕」。
- **驗**:`npm run db:migrate` 成功;pytest 綠。
- **commit**:`feat(api): interview 四表 + repo(sessions/turns/evidence/suggestions)`

### T3 human_touched 記錄鉤子

- **檔**:documents PATCH handler(`app/api/routes/documents.py`)——存檔成功後若有 active
  session:diff 前後 doc(重用/新增 `interview/diff.py` 純函式,輸出 path 列表),
  merge 進 `session.human_touched`。
- **測**:diff 純函式單測(改格/加任務/刪列 → 正確 path);handler 整合測(fake repo)。
- **commit**:`feat(api): 人工存檔 diff 記入 session.human_touched(0025 provenance)`

## Phase 2 — 引擎核心(api,`app/interview/`)

### T4 槽位定義 `slots.py`

- **內容**:`SLOT_DEFS`(11 槽:key/中文名/問法提示/值域說明)、`core_criteria(task)`
  (頻率+比重 → core/supplemental)、`coverage(task)->(filled,required)`、
  `COVERAGE_GATE = {core: 12槽含outputs, light: 4}`(黃金範本 §8.3/附錄)。純函式+常數。
- **測**:coverage 計算、core 判準邊界。
- **commit**:`feat(api): interview 槽位定義與覆蓋率(黃金範本 v0 定版)`

### T5 指令模型 `commands.py`

- **內容**:pydantic tagged union(9 指令,spec §5)+ `TurnOutput{commands, saturation}` +
  `turn_output_schema(choice_ids: list[str]) -> dict`(產 strict-subset JSON schema:
  根 object、additionalProperties:false、required 全列、可空 null union、union 用 anyOf+type const;
  `ask_choice.options` 灌 per-request enum)。
- **測**:schema 產出含上述性質(斷言鍵存在);pydantic 解析 9 指令樣本。
- **commit**:`feat(api): interview 指令詞彙表 v1 + strict-subset schema 產生器`

### T6 executor `executor.py`(純函式,零 I/O)

- **簽名**:`apply(turn: TurnOutput, *, doc: dict, session: SessionState, transcript: list[str])
  -> ExecResult{doc_patch: dict|None, suggestions: list, evidence: list, next_prompt, guard_log}`。
- **邏輯**:quote 驗證(`normalize()` NFKC+空白摺疊)→ 指令逐個執行:set/correct →
  path ∈ human_touched?建議:直改;add_task/add_duty → 建殼列(重用 web ocsDoc 對應的
  server 邏輯=直接改 dict + 標記需 renumber?v1:add 類一律走**建議**,由人核准後前端套
  ——避免 server 重編碼與 renumber 漂移);ask 過預算 → 改 forced skip;advance 未達
  coverage → 拒絕+缺口;刪除類不存在(詞彙表就沒有)。
- **測**(重點 task):分流矩陣(人碰過/沒碰過×set/correct)、quote 失敗降級、預算強制、
  advance 門檻、add 類永遠建議化、冪等(同 turn 重放結果同)。
- **commit**:`feat(api): interview executor(通道分流+三重保險+quote 驗證;純函式)`

### T7 `LlmPort.select_schema` + adapter + 對抗驗收

- **檔**:`app/core/ports.py`(加方法)、`app/adapters/llm_openrouter.py`(實作:
  **spike Pydantic AI NativeOutput vs openai SDK `response_format`**——依 0024 以驗收腳本
  分勝負,擇一落地;`app/adapters/stubs.py` StubLlm 加可程控 select_schema)、
  `scripts/validate_select_schema.py`(對抗誘導池外 id / 違規指令 N 次,零逃逸=過)。
- **測**:port/stub 單測;腳本跑真模型(需 OPENROUTER_API_KEY)結果寫
  `docs/specs/2026-07-0X-select-schema-acceptance.md`。
- **commit**:`feat(api): LlmPort.select_schema + adapter(受限解碼)+ 對抗性驗收腳本`
  (驗收紀錄另一 commit)

### T8 回合服務 `service.py`

- **簽名**:`async def run_turn(profile_id, user_input, *, deps) -> TurnResponse`;
  內部照 spec §4 ①–⑦;context 組裝 `context.py`(結構化狀態+SLOT_DEFS 提示+近 12 回合);
  文件寫回走既有 draft 儲存函式(帶 expect tokens;409 重放一次)。
- **測**:fake deps 全流程(一回合填兩槽+追問;409 重放;LLM 掛 → 503 語意;
  schema 違規 → 內部 retry → 502)。
- **commit**:`feat(api): interview 回合服務(載入→脈絡→一呼→驗→執→寫回)`

## Phase 3 — 端點

### T9 四端點 + 整合測

- **檔**:`app/api/routes/interview.py` 掛 job-profiles router:
  `POST …/interview:start` / `POST …/interview:turn` / `GET …/interview` /
  `POST …/interview:review`(accept/reject 批次;套用走同 seam)。錯誤語意照 spec §3。
- **測**:TestClient + stub deps:start 冪等、turn 全鏈、review 套用/409、顧問視圖形狀。
- **文檔**:`apps/api/README.md` 端點表。
- **commit**:`feat(api): interview 4 端點(AIP-136)+ 整合測試 + README`

## Phase 4 — web 面板

### T10 types + client + hooks

- **檔**:`src/types/index.ts`(TurnResponse/InterviewState/Suggestion…對齊 api)、
  `src/lib/api.ts`(4 端點)、`src/hooks/useInterview.ts`(start/turn/review mutation +
  session query;turn 成功 → invalidate `["document",id]`)。
- **測**:vitest hooks 邏輯(msw 或 fetch mock 照既有慣例)。
- **commit**:`feat(web): interview api client + hooks`

### T11 面板骨架(三段軌道 + 對話流 + choice 卡片)

- **檔**:`src/components/interview/InterviewPanel.tsx`(側欄;進度條 盤點→深掘 x/y→總審;
  訊息流;輸入框;`ask_choice` → 池選項卡片,勾選送 choice)。文件工作台常駐不動。
- **測**:`npx tsc --noEmit` + lint;互動以 T14 模擬劇本驗。
- **commit**:`feat(web): 訪談面板骨架(軌道進度+對話+choice 卡片)`

### T12 建議層 UI(badge + 總審)

- **檔**:文件側段落 `AI 建議` badge(pending suggestion → 新舊對照 popover;單條接受/拒絕)
  + 總審清單(實質改動預設展開 diff、低風險預設勾、Accept all)。
- **測**:vitest(建議渲染/批次 payload 組裝純函式)。
- **commit**:`feat(web): 建議層 badge + 總審批審(0025)`

### T13 動線收攏 + 顧問視圖

- **檔**:文件頁掛面板入口(員工:intake 後自動開;顧問:可收);
  `GET …/interview` 顧問視圖頁(逐字稿 + 槽值↔quote 對照 + 建議歷史)。
- **文檔**:`apps/web/README.md`。
- **commit**:`feat(web): 訪談動線 + 顧問稽核視圖`

## Phase 5 — 驗收與收尾

### T14 模擬受訪者回歸 + E2E 對照黃金範本

- **檔**:`apps/api/evals/interview_sim.py`(persona 卡=黃金範本樣張劇本;LLM 扮員工;
  量槽位正確率/覆蓋率/追問數)+ 校準紀錄 `docs/specs/`(門檻數字第一次實測修訂)。
- **commit**:`test(api): 模擬受訪者回歸 + 覆蓋率校準紀錄 #1`

### T15 文檔義務 + tag

- **檔**:`docs/design/interview-engine.md`(端到端深文檔,照 design/README 寫法)、
  `editor-knowledge-pack.md` 不變量 2 補 engine 分句、研究紀錄補實作後記。
- **收尾**:`npx turbo test` 全綠 → tag `interview-v1`。
- **commit**:`docs: interview-engine 端到端設計文檔 + 實作後記` → tag。

---

## 任務相依

T1 →(T2,T4,T5 可並行)→ T3 → T6(需 T4+T5)→ T7 → T8(需 T2+T6+T7)→ T9 → T10 → T11/T12 → T13 → T14 → T15。
中途任何 task 發現 spec 落差:小修直接改 spec 註記;形狀級落差 → 停,回研究紀錄補輪。
