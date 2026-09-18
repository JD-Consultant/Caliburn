# ADR 0015 — 文件存檔採樂觀並發(version 守衛),回合制協作不上 CRDT/OT

- **狀態**:Accepted（2026-06-30）。
- 研究依據:[`../specs/2026-06-30-web-data-layer-optimization-research.md`](../specs/2026-06-30-web-data-layer-optimization-research.md)(§2)。

## 脈絡

工作台目前以**整份 OcsDocument PATCH** 存草稿([documents.py:63](../../apps/api/app/api/routes/documents.py)
`upsert_draft`),後端**不檢查 version** → last-write-wins。即使無 LLM,使用者開兩個分頁即互蓋;
未來 LLM 會與使用者**共編同一份文件**,模式為**回合制 / 提議套用**(非逐字即時同步)。

並發三層做法(見研究紀錄):樂觀並發(version/ETag→409)、OT(Google Docs)、CRDT(Figma/Notion)。
本文件是**高度結構化 JSON**、編輯本就是 [ocsDoc.ts](../../apps/web/src/lib/ocsDoc.ts) 的離散不可變操作;
`version` 欄位**全鏈路已存在但未當守衛**。AI agent 產出比人快 25–100×,需 agent 層批次+人類優先。

## 決定

採**樂觀並發**;**保留**既有樂觀更新(React Query `onMutate`/rollback)+ debounce 自動儲存 + `version` 欄位。
分兩層,**先 minimal**:

- **minimal(先做)**:① **no-op 跳過**——維護 last-saved 快照,`commit` 結構相等比對,相等不送 PATCH;
  儲存狀態改由「current vs baseline 是否相等」推導。② **啟用 version 守衛**——PATCH 帶 expected version,
  server 版本不符回 **409** → 前端重抓最新 + 重套未存編輯。回合制下即正確(LLM turn +1;使用者舊版本存檔 →
  409 → 重抓重套)。dirty 模型對齊 React Hook Form `isDirty`(對 baseline 比對;存檔成功後重設 baseline)。
- **full(延後/選用)**:整份 PATCH → **逐操作/逐區段 PATCH**,使用者與 LLM 改不同處時免 409、自動併;
  LLM 走**同一操作 seam** + 批次/人類優先。

**不採 CRDT/OT**:對「回合制 + 結構化文件」屬過度設計(CRDT 每字 16–32B metadata、OT 複雜度)。
若日後要 Google-Docs 式即時逐字共編、看得到對方游標,再開新 ADR 翻案。

## 後果

- ✅ 杜絕 last-write-wins 互蓋(分頁/LLM);**幾乎全用現有件**,minimal 改動小。
- ✅ no-op 不送 PATCH → 省往返、儲存狀態更準。
- ✅ 對齊主流(REST 樂觀並發、GitHub API 409/412;RHF dirty)。
- ⚠️ 409 時前端需「重抓 + 重套未存編輯」的合併邏輯(minimal 即需,但範圍小)。
- ⚠️ full(逐操作)是日後 LLM 與人同時改同一份的 UX 精修,非正確性必需;延後不阻塞。
- 📌 階段化見研究紀錄 §5;批次 catalog 端點見 [ADR 0016](0016-batch-task-catalog-endpoint.md)。
