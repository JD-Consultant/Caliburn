---
title: web 資料層 — cache-as-state + autosave 狀態機
audience: agent-primary(也給人)
scope: apps/web/src/hooks/useDocument.ts + useKnowledge.ts + Providers(選擇性持久化)
updated: 2026-07-04
---

# web 資料層 — cache-as-state + autosave 狀態機(深文檔)

> **主讀者 = agent。** web 最燒腦的一塊:**React Query cache 就是編輯器狀態**,加 autosave 的
> baseline / no-op / 409 機制。編輯器**內容面**(pack → 選單 → `_ref`/URN)見
> [`docs/design/editor-knowledge-pack.md`](../../../docs/design/editor-knowledge-pack.md);並發正確性的**為什麼**(漏存 bug)
> 見 [`docs/specs/2026-07-02-2a-minimal-save-concurrency-spec.md`](../../../docs/specs/2026-07-02-2a-minimal-save-concurrency-spec.md) §6.3。
> living:改 [`useDocument.ts`](../src/hooks/useDocument.ts) 同 commit 更本檔。

## 1. cache-as-state(核心心智模型)

- **document 的 React Query cache = 編輯器狀態**:UI 直接讀 `envelope.content`,**不另設 local state**;
  `useAutosaveDocument` 靠同頁掛著的 `useDocument` 訂閱驅動重繪。
- **兩個 query、兩種性質**:

| queryKey | staleTime | 持久化 | 性質 |
|---|---|---|---|
| `["document", id]` | 0 | **否(刻意)** | **可寫的工作狀態** |
| `["knowledge", id]` | 24h | **是** | 唯讀參考池(選單資料源) |

- **一句心法**:**document 是「可寫工作狀態」,其餘全是「唯讀參考池」**——決定誰能持久化、誰走 invalidate、誰的 cache 可本地先寫。

## 2. autosave 狀態機(`useAutosaveDocument`)

```
commit(next):
  a. setQueryData(["document"])         # 畫面即時(樂觀、純本地)
  b. no-op skip:JSON.stringify(next)==baseline.content → 取消排程,不打網路
  c. 否則 debounce 500ms → flushPatch
flushPatch():
  PATCH …/document?expect_version&expect_revision           # 帶 baseline 的雙 token
  onSuccess(env): baseline = { 送出的 content, env.version, env.revision }   # ⚠ 見 §2.2
  onError 409:  setConflict(current token)                  # 不回滾本地編輯
```

### 2.1 `baseline` = 唯一真相

`baseline = {content, version, revision}` 是「最後已知 server 狀態」。**dirty 判定、no-op skip、樂觀鎖 token**
全以它為準。存兩份**永遠一起寫**:`baselineRef`(給非 render 的 callback 讀當下值)+ `baseline` state
(給 render 期讀、觸發 status 重算;lint 禁 render 期讀 ref.current)。

### 2.2 為什麼 onSuccess 的 baseline 用「送出的 content」不是 cache(**漏存 bug**)

PATCH 飛行中使用者可能**又打了字**(cache 已比送出的 content 新)。若用 `env.content` / cache 當新 baseline,
會把那些**還沒存的字誤標成「已存」** → 漏存(2a spec §6.3 點名)。所以 onSuccess **只用這次 mutation
送出的 `content`**(closure 捕捉)當 baseline。

### 2.3 `ownWrite` flag:分辨「自己的 PATCH」vs「外部變化」

本 hook 送出的 PATCH 會讓 cache 的 version/revision 變——**不能**被下面的「外部變化」effect 誤判成外部變化
而用 cache 重設 baseline。`flush` 前設 `ownWrite=true`;外部變化 effect 讀到就跳過並清旗標。

### 2.4 外部變化 effect + 409

- **外部變化**(GET 首載後的 invalidate/refetch、`setOccupations`/`finalize` 成功、載入最新版):
  `envelope` 的 version/revision 變且 `!ownWrite` → 用**新 envelope 整包重設 baseline**(此時 cache 才是新 server 真相),
  並清掉待送的 debounce。
- **409 衝突**:`setConflict(server current token)`,**不回滾本地編輯**(使用者的字留畫面)→ `ConflictDialog`
  二選一:`loadLatest`(refetch 換 server 版)/ `overwriteWithLocal`(用 current token 重送本地內容)。

## 3. status 推導(給頂欄提示)

`conflict → saving(patch.isPending)→ unsaved(dirty)→ error(patch.isError)→ saved(有 baseline)→ idle`。
`dirty = stringify(envelope.content) !== stringify(baseline.content)`。

## 4. 選擇性持久化(`Providers.tsx`)

`PersistQueryClientProvider`(localStorage `caliburn-rq-cache`,buster `ocs-v4-3`,maxAge 24h)**只還原**
標了 `meta.persist === true` 的 query(= knowledge)。**document 永遠重新 GET**(of-record 即時,還原舊文件會蓋掉 server 真相)。
另一把鑰匙:`caliburn-user`(zustand 匿名 userId)。

## 5. 不變量(code 讀不出的規則)

1. **cache-as-state**:UI 讀 document cache,不另設 local state(§1)。
2. **baseline 一律成對寫**(ref + state),且 onSuccess 用**送出的 content**——不是 cache(§2.1–2.2)。
3. **document 刻意不持久化**;只有唯讀池(knowledge)持久(§4)。
4. **409 不回滾本地編輯**:暫停 autosave,等 ConflictDialog 解(§2.4)。
5. **no-op skip 誤差方向安全**:stringify 鍵序不同只會多存一次(判 dirty),**不會**把真 dirty 判成 clean(漏存)。
6. **單一寫入路徑**:所有編輯 → `commit` → PATCH;選職類另走 `PUT occupations`(換同步點)。

## 6. 指路

- 編輯器內容面 / 選單 / 三分:[`docs/design/editor-knowledge-pack.md`](../../../docs/design/editor-knowledge-pack.md)。
- 並發正確性(漏存 bug、反例):[`docs/specs/2026-07-02-2a-minimal-save-concurrency-spec.md`](../../../docs/specs/2026-07-02-2a-minimal-save-concurrency-spec.md);ADR [0015](../../../docs/adr/0015-document-save-optimistic-concurrency.md)。
- app 面 / codemap:[`../README.md`](../README.md)。後端對應:[`apps/api/docs/document-of-record.md`](../../api/docs/document-of-record.md)。
