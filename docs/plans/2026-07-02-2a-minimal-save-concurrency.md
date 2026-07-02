# Plan — 2a-minimal:存檔樂觀鎖(revision token + 409)+ no-op skip

> **交接**:細節設計 + 參考實作(含程式碼)見
> [spec `2026-07-02-2a-minimal-save-concurrency-spec.md`](../specs/2026-07-02-2a-minimal-save-concurrency-spec.md)。
> 新 session 讀 CLAUDE.md + 該 spec + 本 plan 即可獨立開工。

- 依據:[ADR 0015](../adr/0015-document-save-optimistic-concurrency.md)(決策不變)·
  研究 [`../specs/2026-06-30-web-data-layer-optimization-research.md`](../specs/2026-06-30-web-data-layer-optimization-research.md) §2 ·
  [`../specs/2026-07-02-llm-interview-authoring-research.md`](../specs/2026-07-02-llm-interview-authoring-research.md)(軸 3/4:回合制 + staged 審閱背書)。
- **ADR 0015 實作精化(非翻案)**:ADR 說「啟用 version 守衛」;實查發現 draft 就地更新**不動 version**
  (version 只在新 draft/finalize +1,且 UI 顯示「正式版本 vN」)→ 光靠 version 擋不到「兩分頁改同一 draft」。
  故 token 精化為**雙 token**:`version`(文件世系,語意不變)+ 新增 `revision`(單列編輯回合計數)。
  守衛精神與 ADR 一致。維護者已拍板(2026-07-02):**revision 欄位** + **409 衝突對話框**。
- 原則:green-before==green-after(api baseline 149 passed);一 task 一 commit;**不加 npm 依賴**;
  agent 寫入路(`DocRepo.save`,INSERT 新版本)**不動**。

## Task A — DB:revision 欄位 + SQLAlchemy 樂觀鎖

- Alembic migration:`document_versions` 加 `revision INTEGER NOT NULL SERVER DEFAULT 1`(加欄不動資料)。
- `models/job_profile.py::DocumentVersion`:加 `revision` Column + `__mapper_args__ = {"version_id_col": revision}`
  → 每次 ORM UPDATE 自動發 `SET revision=n+1 WHERE … AND revision=n`(CAS);同毫秒競態 → `StaleDataError`
  (SQLAlchemy 官方機制,見研究)。INSERT 新列(finalize/新 draft)revision 從 1 起。
- `DocRepo._to_dict` envelope 加 `"revision"`。
- 測試:upsert_draft 兩次 → revision 遞增;finalize 新列 revision=1。
- **commit**:`feat(api): document revision column + SQLAlchemy version counter [2a, ADR 0015]`

## Task B — 守衛 + 409 契約

- `DocRepo.upsert_draft(profile_id, content, *, expected_version=None, expected_revision=None)`:
  兩者皆給時,與最新列(無列視為 version=0)比對;不符 → raise `DocConflictError(current_version, current_revision)`。
- PATCH route:query params `expect_version`/`expect_revision`(**optional;不帶=不守衛**,保守相容——web 一律帶;
  docstring 記明 opt-in 現況與未來收緊)。`DocConflictError` 與 `StaleDataError` → **409**
  `{"detail": {"code": "version_conflict", "current_version": v, "current_revision": r}}`(帶當前 token,前端免多打一次)。
- 測試:token 相符 → 200 且 envelope.revision +1;revision 過期 → 409 + 當前 token;
  version 過期(finalize 後舊分頁)→ 409;不帶參數 → 200(legacy);首存(無列)expected 0/1 邊界。
- **commit**:`feat(api): optimistic-concurrency guard on document PATCH (expect_version/revision → 409) [2a, ADR 0015]`

## Task C — web:no-op skip + token + 409 對話框

1. `types`:`DocumentEnvelope` 加 `revision: number`。
2. `lib/api.ts`:`request()` 丟自訂 `ApiError extends Error { status }`(409 偵測需要);
   `patchDocument(profileId, content, expect?: {version, revision})` → query string 帶 token。
3. `useAutosaveDocument` 重構:
   - **baseline ref** `{content, version, revision}` = 最後成功存檔快照(初始 = GET 到的 envelope;
     PATCH 成功後重設為送出的 content + 回應 token;buildTasks/setOccupations 成功已 setQueryData/invalidate → 同步重設)。
   - **no-op skip**:`commit()` 以 `JSON.stringify` 對 baseline.content 比對(誤差方向安全:只可能多存不會漏存),
     相等 → 取消排程、不送 PATCH。
   - **status 推導**(對齊 RHF isDirty):`saved`(clean)/`unsaved`(dirty 未送)/`saving`/`conflict`/`error`。
   - flush 送 baseline 的 token;**409 → 進 conflict 狀態、暫停 autosave、不回滾本地編輯**(使用者的字還在畫面上)。
4. **ConflictDialog**(Word Copilot staged 審閱精神/VS Code file-changed 同款):
   「此文件已在別處被更新」→ **[載入最新版]**(refetch → 取代本地 + 重設 baseline)/
   **[以我的版本覆蓋]**(用 409 回傳的當前 token 重送本地 content)。兩向都是使用者明選,無靜默丟失。
5. **不動**:document query `refetchOnWindowFocus:false` 必須維持(重抓會蓋掉未存編輯;碼註解記理由)。
- 驗收:`npx tsc --noEmit` + `npm run lint`;手動雙分頁腳本(A 改存 → B 改存 → B 得對話框;兩鍵各驗)。
- **commit**:`feat(web): no-op save skip + optimistic-concurrency tokens + conflict dialog [2a, ADR 0015]`

## Task D — living docs

- `apps/api/README.md`:PATCH 守衛一句(expect token → 409)。
- `docs/runbook.md`:疑難排解加「儲存顯示版本衝突」行。
- 研究紀錄 §5/ADR 0015 已載;plan 本檔即實作紀錄。
- **commit**:`docs: propagate 2a save-concurrency into api README + runbook`

## 明確不做(YAGNI,依據見研究)

- CRDT/OT、自動三方合併(回合制下 409 即回合邊界;CHI 2026 支持建議通道而非即時逐字)。
- 逐操作 PATCH(2a-full,ADR 0015 已延後)。
- agent 寫入路守衛(agent 走 `DocRepo.save` INSERT 新版本 = 天然回合;接 LLM 時由流程持 token)。

## 回滾

- Task A migration 為加欄,revert = drop column(無資料遷移);B/C 各自 revert commit 即可。
