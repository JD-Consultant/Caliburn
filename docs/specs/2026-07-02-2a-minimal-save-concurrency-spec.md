# 2a-minimal 存檔並發 — 實作 Spec(交接文件,可獨立執行)

> **類型**:細節設計 spec。**尚未實作**;維護者將以新 session 依本 spec + plan 實作。
> **日期**:2026-07-02
> **執行順序**:[plan `2026-07-02-2a-minimal-save-concurrency.md`](../plans/2026-07-02-2a-minimal-save-concurrency.md)
> 的 Task A→B→C→D(一 task 一 commit,綠了才 commit)。
> **決策依據**:[ADR 0015](../adr/0015-document-save-optimistic-concurrency.md)(樂觀並發、回合制、minimal 先)。
> 維護者已拍板(2026-07-02):**新 `revision` 欄位**(非 bump version)+ **409 衝突對話框**(非自動重載)。
> **背景**(為何值得做):北極星研究([`2026-07-02-llm-interview-authoring-research.md`](2026-07-02-llm-interview-authoring-research.md)
> §3/§4)——未來 LLM 訪談 agent 與人回合制共編同一文件,2a 是回合邊界的並發地基;ADR 0020 已定互動模式。

---

## 1. 現況事實(已讀碼查證,含錨點)

1. **last-write-wins**:`PATCH /job-profiles/{id}/document` → `DocRepo.upsert_draft`
   ([persistence.py:61](../../apps/api/app/adapters/persistence.py))——最新列是 draft 就**就地覆蓋 content,不做任何檢查**。
2. **draft 存檔不動 `version`**:`version` 只在「INSERT 新 draft / finalize」時 +1;就地更新不變。
   → 兩個分頁都拿 v3,拿 version 當守衛**擋不到任何東西**(這是 ADR 0015 文字沒挖到的實作細節,本 spec 的 token 設計即為此而生)。
3. **`version` 是 user-facing**:[page.tsx:89](../../apps/web/src/app/documents/[id]/page.tsx) 顯示「已產生正式版本 v{n}」
   → **不可**改成每次存檔 bump version(會看到 v347 且污染 draft/final 世系)。
4. **`DocumentVersion` model 無 `updated_at`、無 `revision`**([models/job_profile.py:43-53](../../apps/api/app/models/job_profile.py))。
5. **web 的 `request()` 丟字串 Error,拿不到 HTTP status**([api.ts:22-34](../../apps/web/src/lib/api.ts))→ 409 偵測需先補。
6. **autosave**:[useDocument.ts:107-135](../../apps/web/src/hooks/useDocument.ts) `useAutosaveDocument`——
   `commit()` 寫 cache + 500ms debounce PATCH;status 由 mutation 狀態推導(無 dirty 概念、無 no-op skip)。
7. **document query `refetchOnWindowFocus:false` 必須維持**:重抓會把 server 內容寫進 cache=編輯器狀態,**蓋掉未存編輯**。
8. **agent 寫入路是另一條**:`LiveDbPersist.save_document` → `DocRepo.save`(INSERT 新 version 列)——**本輪不動**
   (agent turn 天然=新版本;使用者舊 token 下次 PATCH 會 409,正是要的行為)。
9. **baseline(green-before)**:api `uv run pytest` = **149 passed**;web `npx tsc --noEmit` + `npm run lint` 乾淨。

## 2. 設計

### 2.1 並發 token:雙 token(`version` + `revision`)

- `version`(既有)=文件世系(draft/final 遞增)。**語意不變。**
- `revision`(新)=**單一列的編輯回合計數**。同一 draft 列每次 UPDATE +1。
- 衝突判定:client 送出的 `(expect_version, expect_revision)` 與**最新列**的 `(version, revision)` 不完全相等 → 409。
  - 涵蓋:另一分頁存過(revision 前進)、agent/finalize 開了新列(version 前進)、首存競態(見 §4)。

### 2.2 DB / ORM(Task A)

- **Alembic migration**:`document_versions` 加 `revision INTEGER NOT NULL SERVER DEFAULT 1`(加欄不動既有資料)。
- **model**:
  ```python
  revision = Column(Integer, nullable=False, default=1, server_default=text("1"))
  __mapper_args__ = {"version_id_col": revision}
  ```
  SQLAlchemy `version_id_col`(官方樂觀鎖,[docs](https://docs.sqlalchemy.org/en/20/orm/versioning.html)):
  每次 ORM flush UPDATE 自動發 `SET revision=n+1 WHERE … AND revision=n`;
  0 rows(同毫秒競態)→ 拋 `sqlalchemy.orm.exc.StaleDataError`。**遞增與 CAS 都免手寫**。
- 注意:`version_id_col` 只作用於 ORM flush(unit-of-work)路徑;本 repo 的寫入皆走 ORM(`row.content = …; flush()`)✓。

### 2.3 API 契約(Task B)

- **PATCH `/api/v1/job-profiles/{id}/document`**
  - Query params(**optional**):`expect_version: int`、`expect_revision: int`。
    **不帶=不守衛**(legacy 相容;web 一律帶。docstring 記明 opt-in 現況)。
  - Body 不變(整份 OCS 文件 dict)。
  - 成功 → envelope(見下)。
  - 衝突 → **409**:
    ```json
    {"detail": {"code": "version_conflict", "current_version": 3, "current_revision": 7}}
    ```
    (帶當前 token → 前端「覆蓋」路徑免多打一次 GET。)
- **envelope**(`DocRepo._to_dict`)加 `"revision"`:`{id, version, revision, content, status}`。
  GET 無文件的空殼 → `"revision": 0`(與 `version: 0` 一致)。
- **實作**:`DocRepo.upsert_draft(profile_id, content, *, expected_version=None, expected_revision=None)`;
  兩者皆非 None 才檢查;不符 raise 自訂 `DocConflictError(current_version, current_revision)`
  (定義放 `app/adapters/persistence.py` 或 `app/core/domain`,實作者判斷;route 捕捉映 409)。
  `StaleDataError` 同樣映 409(此時 current token 取 refresh 後的列;或簡化回 409 不帶 current、前端 fallback GET——
  **擇一並在測試固定行為**,建議前者)。

### 2.4 web(Task C)

- **`types`**:`DocumentEnvelope` 加 `revision: number`。
- **`lib/api.ts`**:
  - `class ApiError extends Error { constructor(public status: number, message: string) }`;
    `request()` 改丟 `ApiError`(status 可判 409;既有呼叫端 catch `Error` 不受影響——`ApiError instanceof Error`)。
  - `patchDocument(profileId, content, expect?: { version: number; revision: number })` →
    有 expect 時 URL 加 `?expect_version=&expect_revision=`。
- **`useAutosaveDocument` 重構**(核心):
  - `baseline = useRef<{content, version, revision} | null>`:
    - 初始:document query 首次有資料時設(envelope.content/version/revision);
    - PATCH 成功:設為 `{content: 送出的 content, version: env.version, revision: env.revision}`;
    - `useBuildTasks`/`useSetOccupations`/`useFinalizeDocument` 成功已 setQueryData/invalidate →
      baseline 需隨新 envelope 重設(監聽 query data 的 version/revision 變化,或在各 onSuccess 重設——實作者擇一)。
  - **no-op skip**:`commit(next)` 時 `JSON.stringify(next) === JSON.stringify(baseline.content)` →
    取消 pending debounce、不排 PATCH。(誤差方向安全:鍵序不同只會「多存」,不可能「漏存」。**不加 npm 依賴**。)
  - **status 推導**(取代現在的 mutation-status):
    `conflict`(有衝突待處理)> `saving`(pending)> `unsaved`(dirty)> `saved`(clean 且存過)> `idle`。
    dirty = 目前 content 與 baseline.content 不等。
  - **flush 帶 token**:送 `expect = {version: baseline.version, revision: baseline.revision}`。
  - **409 處理**:進 `conflict` 狀態(存 409 回傳的 current token)、**暫停 autosave**、**不回滾本地編輯**(使用者的字留在畫面)。
- **ConflictDialog**(新元件;Word Copilot staged 審閱/VS Code file-changed 同款):
  文案「此文件已在別處被更新」+ 兩鍵:
  - **[載入最新版]**:invalidate/refetch document → cache 換成 server 版 → baseline 重設 → 離開 conflict。
    (本地未存編輯被捨棄——使用者明選。)
  - **[以我的版本覆蓋]**:用 409 給的 current token 重送本地 content → 成功後 baseline 重設 → 離開 conflict。
  - 掛載點:工作台頁(`documents/[id]/page.tsx`)讀 autosave hook 的 conflict 狀態。
- **儲存狀態 UI**:沿用現有顯示點,新增 `unsaved`/`conflict` 兩態的呈現(小改)。

## 3. 測試矩陣

**backend**(擴 `test_documents_api.py` 或新檔):
| case | 預期 |
|---|---|
| PATCH 不帶 expect(legacy) | 200,行為同現況 |
| 帶 expect、token 相符 | 200;回應 revision = 原 +1 |
| expect_revision 過期(另一「分頁」先存) | 409 + `current_version/current_revision` 正確 |
| expect_version 過期(finalize 後 / `DocRepo.save` 插新列後) | 409 |
| 無文件首存:expect (0,0) | 200,建 draft(version 1, revision 1) |
| 無文件但 expect (0,0) 且已被別人建立 | 409 |
| upsert 兩次(不帶 expect) | revision 1→2(version_id_col 生效) |
| finalize | 新列 version+1、revision=1 |

**web**:`npx tsc --noEmit` + `npm run lint` 綠;手動雙分頁腳本(plan Task C 驗收):
分頁 A 改存 → 分頁 B 改存 → B 出對話框;「載入最新」與「覆蓋」各驗一次;
單分頁連打同值(no-op)→ Network 無 PATCH。

## 4. 邊界與已知取捨

- **首存競態**:兩分頁同時首存 → 一個 INSERT 成功,另一個(expect 0,0 但已有列)409。
- **StaleDataError 視窗**:應用層檢查通過後、flush 前被搶先——由 `version_id_col` CAS 兜住,映 409。
- **no-op 判定用 stringify**:僅可能誤判為 dirty(多一次 PATCH),不可能漏存。
- **agent 路不守衛**(本輪):`DocRepo.save` 簽名不變;未來訪談 agent 立項時由流程持 token(ADR 0020 §後果)。
- **`refetchOnWindowFocus` 維持 false**(§1.7);2a-full(逐操作 PATCH)依 ADR 0015 延後。

## 5. 交接:環境與驗證指令(新 session 照抄)

```bash
# infra(Windows 注意 -p caliburn;見 CLAUDE.md 踩雷節)
docker compose -p caliburn -f S:/caliburn/docker-compose.yml up -d db

# backend 測試(DB 整合測試需 TEST_DATABASE_URL;無則 skip)
cd /s/caliburn/apps/api
export TEST_DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/caliburn_test"
export PYTHONUTF8=1
uv run pytest -q          # green-before 基準:149 passed

# migration
uv run alembic revision -m "document_versions add revision" ; uv run alembic upgrade head
# (caliburn_test 由 conftest 管 schema?→ 不是:integration 測試連 caliburn_test,
#  migration 需對 dev DB(caliburn)與 test DB(caliburn_test)都跑;runbook「跑後端 DB 整合測試」節有既有做法,照它。)

# web
cd /s/caliburn/apps/web && npx tsc --noEmit && npm run lint
```

- 改後端碼要**手動重啟** api(reload 已關,CLAUDE.md)。
- commit 訊息與拆分照 plan(Task A/B/C/D 各一 commit,標 `[2a, ADR 0015]`)。
- 完成後 living docs:api README(PATCH 守衛一句)、runbook(409 疑難排解行)——plan Task D。

## 6. 參考實作(**未套用**;新 session 依此改寫,以當時實際碼為準)

### 6.1 model + migration(Task A)

```python
# app/models/job_profile.py — DocumentVersion 增列
revision = Column(Integer, nullable=False, default=1, server_default=text("1"))
__mapper_args__ = {"version_id_col": revision}   # ORM UPDATE 自動 +1 + CAS(StaleDataError)
```

```python
# alembic revision -m "document_versions add revision"
def upgrade():
    op.add_column("document_versions",
        sa.Column("revision", sa.Integer(), nullable=False, server_default=sa.text("1")))

def downgrade():
    op.drop_column("document_versions", "revision")
```

### 6.2 repo 守衛 + route 409(Task B)

```python
# app/adapters/persistence.py
class DocConflictError(Exception):
    """樂觀鎖衝突:client expected token 與最新列不符(ADR 0015)。"""
    def __init__(self, current_version: int, current_revision: int):
        self.current_version, self.current_revision = current_version, current_revision
        super().__init__(f"document changed: v{current_version} r{current_revision}")


async def upsert_draft(self, job_profile_id, content, *,
                       expected_version: int | None = None,
                       expected_revision: int | None = None) -> dict:
    """最新列若為 draft → 原地更新(revision 由 version_id_col 自動 +1);否則 INSERT 新 draft。
    expected_* **皆給**時做樂觀鎖檢查:與最新列 (version, revision) 不符 → DocConflictError;
    無列視為 (0, 0)。不帶=不守衛(legacy)。"""
    row = await self._latest_row(job_profile_id)
    if expected_version is not None and expected_revision is not None:
        cur = (row.version, row.revision) if row else (0, 0)
        if (expected_version, expected_revision) != cur:
            raise DocConflictError(*cur)
    if row is not None and row.status == "draft":
        row.content = content
    else:
        row = DocumentVersion(job_profile_id=job_profile_id,
                              version=(row.version if row else 0) + 1,
                              content=content, status="draft")
        self.s.add(row)
    await self.s.flush()
    return self._to_dict(row)

# _to_dict 加 "revision": r.revision
```

```python
# app/api/routes/documents.py
from sqlalchemy.orm.exc import StaleDataError
from app.adapters.persistence import DocConflictError

@router.patch("/{profile_id}/document")
async def patch_document(
    profile_id: UUID,
    body: dict = Body(...),
    expect_version: int | None = None,
    expect_revision: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """PATCH 整份 OCS 文件。樂觀鎖 opt-in:帶 expect_version+expect_revision 且不符最新 → 409
    {code: version_conflict, current_*}(ADR 0015)。"""
    await _require_profile(profile_id, db)
    try:
        return await DocRepo(db).upsert_draft(
            profile_id, body,
            expected_version=expect_version, expected_revision=expect_revision)
    except DocConflictError as e:
        raise HTTPException(status_code=409, detail={
            "code": "version_conflict",
            "current_version": e.current_version,
            "current_revision": e.current_revision})
    except StaleDataError:
        # CAS 競態(應用層檢查通過後被搶先)。⚠ flush 失敗後 session 需先 rollback 才能再查;
        # 注意與測試 conftest 的 transaction-rollback 模式互動(必要時降級為 409 不帶 current,
        # 前端 fallback 走 GET)。行為擇一後用測試釘死。
        await db.rollback()
        row = await DocRepo(db)._latest_row(profile_id)
        raise HTTPException(status_code=409, detail={
            "code": "version_conflict",
            "current_version": row.version if row else 0,
            "current_revision": row.revision if row else 0})
```

```python
# 測試骨架(擴 tests/test_documents_api.py;矩陣見 §3)
@pytest.mark.asyncio
async def test_patch_stale_revision_409(client):
    p = await _mk_profile(client._db)
    r1 = await client.patch(f"/api/v1/job-profiles/{p.id}/document", json={"a": 1})
    v, rev = r1.json()["version"], r1.json()["revision"]
    await client.patch(  # 「另一分頁」先存 → revision 前進
        f"/api/v1/job-profiles/{p.id}/document?expect_version={v}&expect_revision={rev}",
        json={"a": 2})
    r3 = await client.patch(  # 舊 token 再存 → 409 + 當前 token
        f"/api/v1/job-profiles/{p.id}/document?expect_version={v}&expect_revision={rev}",
        json={"a": 3})
    assert r3.status_code == 409
    d = r3.json()["detail"]
    assert d["code"] == "version_conflict" and d["current_revision"] == rev + 1
```

### 6.3 web(Task C)

```ts
// lib/api.ts
export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
  }
}
// request():throw new ApiError(res.status, `${res.status} ${text}`, tryParseJson(text))
// (既有 catch (e: Error) 不受影響:ApiError instanceof Error)

export const patchDocument = (
  profileId: string,
  content: OcsDocument,
  expect?: { version: number; revision: number },
) =>
  request<DocumentEnvelope>(
    `/job-profiles/${profileId}/document` +
      (expect ? `?expect_version=${expect.version}&expect_revision=${expect.revision}` : ""),
    { method: "PATCH", body: JSON.stringify(content) },
  );
```

```ts
// hooks/useDocument.ts — useAutosaveDocument 重構要點(示意)
export type SaveStatus = "idle" | "unsaved" | "saving" | "saved" | "conflict" | "error";

// baseline = 最後「已知的 server 狀態」:{content, version, revision}
// ⚠ 關鍵:PATCH onSuccess 的 baseline.content 必須用「送出的 content」(variables),
//   不能用 cache 的 env.content——usePatchDocument.onSuccess 保留 old.content(可能已有更新的按鍵),
//   用 cache 會把未存的字誤標成已存(漏存 bug)。
// 外部變化(GET/invalidate/buildTasks/setOccupations/載入最新)→ env.version/revision 改變
//   且非本 hook 的 PATCH 寫回(onSuccess 設 flag 區分)→ baseline 以 env 整包重設。
// commit(next):
//   JSON.stringify(next) === JSON.stringify(baseline.content) → flushPatch.cancel(); return;  // no-op skip
//   否則照舊寫 cache + debounce。
// flush:patch.mutate(latest.current, { expect: {version: baseline.version, revision: baseline.revision} })
// onError:e instanceof ApiError && e.status === 409 →
//   setConflict((e.body as any)?.detail ?? null);  // {current_version, current_revision}
//   不回滾本地 cache(使用者的字留著);conflict!=null 時 commit 仍可編但不 flush。
// status 推導:conflict > saving(isPending) > unsaved(dirty) > saved > idle;
//   dirty = stringify(cacheContent) !== stringify(baseline.content)。
```

```tsx
// components/…/ConflictDialog.tsx(示意)
// 「此文件已在別處被更新」
// [載入最新版]   → qc.invalidateQueries(["document", profileId]) → baseline 隨新 envelope 重設 → clear conflict
// [以我的版本覆蓋] → patch.mutate(本地 content, { expect: conflict 給的 current token }) → onSuccess 清 conflict
```

> 以上為**參考**:命名/檔案位置以實作當下的碼為準;任何與 §2 設計衝突處,以 §2 為準並回寫本 spec。
