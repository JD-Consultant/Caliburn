# ADR 0016 — 後端批次 task-catalog 端點(每 ocs_code 撈一次池)

- **狀態**:Accepted（2026-06-30）。
- 研究依據:[`../specs/2026-06-30-web-data-layer-optimization-research.md`](../specs/2026-06-30-web-data-layer-optimization-research.md)(§1)。

## 脈絡

per-task 官方 catalog(K/S/O/P/level)來自 [ai.py](../../apps/api/app/api/routes/ai.py) 的
`knowledge.competencies(ocs_code)`——**一次撈整個 ocs_code 的能力池**,再在記憶體切某 task
([task_detail.py](../../apps/api/app/services/knowledge/task_detail.py))。前端每任務各打一次
`recommend-ks` + 一次 `draft-op` → **同一個 ocs_code 的整池被重撈 N×2 次**(一份 10 同職類任務 = 撈池 20 次)。
`task-candidates` 回應**不帶 K/S/O/P**,故無法在「選任務當下」push catalog。

## 決定

新增**唯讀批次端點**(暫名 `GET /job-profiles/{id}/task-catalogs`):

- 後端對該文件涉及的**每個不同 `ocs_code` 只撈一次池**,切出**所有任務**的
  `{task_key → {knowledge, skills, outputs, indicators, competency_level}}` 一次回。
- **note-less catalog 路徑**(確定性、可快取);不跑 LLM。
- 前端用 `setQueryData` 把結果灌進各 `["task-catalog", profileId, taskKey]`(TkDodo seeding/push);
  開填格 0 等待、不發請求。與既有 per-task `recommend-ks`/`draft-op`(帶 note 的 LLM 個人化)並存、不取代。
- **O/P 一併帶回 `code`**(契約 DTO `CitableItem.code` 本就有,僅前面被丟掉)——同時服務 2b 的 provenance 身分(研究紀錄 §3)。

## 後果

- ✅ N×2 整池重撈 → 壓到「不同 ocs_code 數」次;indexer 負載大降。
- ✅ catalog 一次到位 → 前端可預灌快取 + 持久化(研究紀錄 §1 D-1b/D-1d)。
- ✅ 走既有 `KnowledgeClient.competencies` seam,无 indexer 改動。
- ⚠️ 新端點屬 api⇄web 新 seam,依 `docs/contract-strategy.md` 選契約機制(回傳形狀對齊既有 per-task)。
- ⚠️ 大文件回應較大;可接受(唯讀、可快取),必要時分頁/按需。
