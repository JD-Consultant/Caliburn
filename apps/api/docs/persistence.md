---
title: api 持久化 + 樂觀鎖 — DocRepo / document_versions
audience: agent-primary(也給人)
scope: apps/api/app/adapters/persistence.py + models(document_versions)
updated: 2026-07-04
---

# api 持久化 + 樂觀鎖 — `DocRepo`(深文檔)

> **主讀者 = agent。** server 端:文件怎麼存、**version/revision 兩 token 樂觀鎖**怎麼守。
> 並發模型 + 漏存 bug 的完整**「為什麼」= [2a spec](../../../docs/specs/2026-07-02-2a-minimal-save-concurrency-spec.md)**;
> **client 端機制 = [`apps/web/docs/data-layer.md`](../../web/docs/data-layer.md) §2**;決策 = ADR [0015](../../../docs/adr/0015-document-save-optimistic-concurrency.md)。
> living:改 [`persistence.py`](../../app/adapters/persistence.py) 同 commit 更本檔。

## 1. 資料模型:兩個 token

`document_versions`(Alembic 管 schema),**每份 profile 多列**:

| token | 語意 | 何時變 |
|---|---|---|
| `version` | **文件世系** | `finalize` / 重建 → **INSERT 新列**、+1 |
| `revision` | **同一列的編輯回合** | 每次 UPDATE → **`version_id_col` 自動 CAS +1** |

`content` = 整份 OCS JSON(JSONB;draft 含 `_` UI 欄)。`(version, revision)` 兩者構成 PATCH 樂觀鎖 token。

## 2. `DocRepo` 四個操作

| 方法 | 做什麼 |
|---|---|
| `latest` | 取最新 version 列 → `{id, version, revision, content, status}` |
| `save` | INSERT 新 draft(version = max+1)——無守衛版 |
| **`upsert_draft`** | 樂觀鎖 + 「最新是 draft 就原地更新、否則 INSERT」(§3) |
| `finalize` | INSERT 新 **final** 列(version+1;無文件 → `ValueError`) |

## 3. 兩 token 樂觀鎖(**opt-in**,兩層保險)

```
upsert_draft(content, expected_version, expected_revision):
  # 應用層檢查(兩者皆給才守;無列視為 (0,0))
  if expected_* 都給 and (expected_version, expected_revision) != (row.version, row.revision):
      raise DocConflictError(current_version, current_revision)   # → route 409
  # 寫入
  最新列是 draft → 原地更新 content(version 不變、revision 由 version_id_col 自動 +1)
  否則           → INSERT 新 draft(version+1)
```

- **只給一個 token 或都不給 = 不守衛**(legacy 相容;web 前端一律帶兩個)。
- **DB 層兜底**:`revision = version_id_col`——通過應用層檢查後、flush 前被搶先的**同毫秒競態**,由 CAS
  失敗擋下(`StaleDataError` → route `rollback` → 讀當前列 → **409**)。應用層檢查 + DB CAS = **雙保險**。
- 409 body 帶 `current_version` / `current_revision`,前端「覆蓋」路徑免多打一次 GET。

## 4. write-through(`LiveDbPersist`)

Live serving 的 `PersistPort`:**每操作開一短命 session、委派 `DocRepo`/`ProfileRepo`、各自 `commit`**
(deps 在 app 啟動**一次性**注入、無 per-request scope,故用 session **factory**)。`ProfileRepo.set_selected_ocs`
UPDATE `job_profiles.selected_ocs_codes`。

## 5. 不變量(code 讀不出的規則)

1. **version = 世系、revision = 回合**,別混(§1)。
2. **樂觀鎖 opt-in**:兩 token 皆給才守;web 一律帶。
3. **雙保險**:應用層先比 + DB `version_id_col` CAS 兜同毫秒競態(§3)。
4. **draft 原地更新、final/世系 INSERT**:同一份 draft 反覆 PATCH 不長 version(只 +revision);finalize 才 +version。
5. **409 不由 repo 決定回滾**:repo 只 raise/CAS;route 轉 409、前端不回滾本地編輯(見 web data-layer §2.4)。

## 6. 指路

- 完整並發模型 + 漏存 bug(權威 why):[2a spec](../../../docs/specs/2026-07-02-2a-minimal-save-concurrency-spec.md);ADR [0015](../../../docs/adr/0015-document-save-optimistic-concurrency.md)。
- client 端狀態機(baseline / expect / 409 / ConflictDialog):[`apps/web/docs/data-layer.md`](../../web/docs/data-layer.md) §2。
- 存的內容契約:[`document-of-record.md`](document-of-record.md)(`ocs_doc`);端點 / 生命週期:[`../README.md`](../README.md) §1。
