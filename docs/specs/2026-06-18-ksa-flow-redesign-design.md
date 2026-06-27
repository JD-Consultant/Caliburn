# jobintel-ai v3 — KSA 流程重設計（Design Spec）

> 日期：2026-06-18。分支 `feat/v3`。
> 上層架構：`2026-06-16-jobintel-ai-v3-architecture.md`（本文件細化其 §2 flow / §9 walkthrough 的 ④ 收尾段）。
> 決策紀錄：`2026-06-16-refactor-decision-log.md`（本次 = D24）。
> 緣由：使用者發現實作的使用者流程與設想有出入；經 brainstorming + 權威資料佐證後重設計收尾段。

---

## 1. 問題

現況 `assemble_ksa` **一步**把 K/S/A 全從**職類層** `pairs()` 撈、一次 `interrupt(edit_ksa)` 編完。這與 OCS 職能基準的真實結構**不一致**，且互動過粗。

## 2. 權威依據

**(A) OCS 職能基準結構**（indexer 領域模型 `jd_ocs_indexer/models/ocs.py`，吃官方「XXX-職能基準.json」）：

```
OCSDocument
├── ocs_content.ocu_units[].tasks[].competency_blocks[]
│       ├── knowledge[]   ← K  ★ 任務層（綁在每個工作任務的能力區塊下）
│       └── skills[]      ← S  ★ 任務層
└── ocs_attitude.attitudes[]  ← A  ★ 頂層、職類層、不綁任務
```

→ **K/S 綁任務、A 綁職類**是官方標準結構，不是 UX 偏好。indexer 對應供應：
- `POST /tasks/by-id` → `TaskDetail.k_pairs` / `s_pairs`（任務層 K/S）
- `GET /profile/{ocs}/pairs` → `attitudes`（職類層 A）

**(B) HITL 主流模式**（LangChain/LangGraph 官方、CopilotKit/AG-UI）：
- 決策類型收斂為 approve / edit / reject / respond；主流是「**一個可編輯審閱面**」把選+改合一，非兩段式。
- **idempotency-on-resume**：node 從 `interrupt()` resume 會**整個重跑**；interrupt 前的副作用（API 呼叫、DB 寫）必須 idempotent，否則每次 resume 重打。
- CopilotKit gen-UI 分層：我們用 **Controlled（AG-UI）**——後端定資料、前端定渲染。
- 來源：docs.langchain.com/oss/python/langchain/human-in-the-loop、langchain.com/blog（interrupt）、docs.copilotkit.ai/human-in-the-loop、copilotkit.ai/generative-ui。

## 3. 新流程

| 步驟 | 節點 | 互動 | 資料來源 |
|---|---|---|---|
| ① 選職類 | `pick_profile` | 複選 + 順序＝優先度（已實作） | `search()` |
| ② 任務 | `build_task_pool` | **單一可編輯審閱面**（勾/改/增/刪 → 確認） | `task_pool()` |
| ③ 逐任務深問 | deep loop（單層，不變） | STAR → 5W2H → 行為指標，每問一 interrupt | catalog prefill（best-effort） |
| ④ **逐任務 KS** | **新 `curate_ks` 迴圈** | **全部訪談完後**，逐任務一個審閱面（K 段 + S 段，可改/增/刪 → 確認）→ 下一任務 | **`pairs()` 職類池（interim）** |
| ⑤ **全域 A** | **新 `curate_attitudes`** | 一次，單一審閱面 | `pairs()` → `attitudes` |
| ⑥ REVIEW | `build_doc` | **唯讀**預覽完整 OCS 文件 → 確認存檔 | 組裝 state |

```
pick_profile → build_task_pool → [deep loop] → [ks loop] → curate_attitudes → build_doc(review) → done
                                  ↑ 既有單層    ↑ 新增，鏡像 deep loop 的單層迴圈
                                  (task_index)  (ks_index 前進)
```

## 4. 決策（D24 子項）

- **D24-a 逐任務 KS 在「全部訪談完之後」**（獨立 KS 階段），非交錯在深問迴圈內。理由：使用者偏好先一口氣訪談完；KS 選擇不強依賴單一任務的訪談答案。
- **D24-b 單一可編輯審閱面**（每個 curate 步：任務 / KS / A 皆同一模式），非「勾選→另一頁編輯」兩段式。對齊 LangGraph `edit` 模式；每項標 provenance（catalog / 公司）。
- **D24-c KS 來源＝`pairs()` 職類池（interim）**：因 `tasks_by_id` 現回 502 且 `pairs()` 已驗證可用。**語意**：每個任務的候選 K/S 都是**同一份職類池**，catalog 不分任務；任務間 K/S 差異由**人在各任務審閱面**挑選決定。**升級路徑**：indexer `/tasks/by-id` 修好後，把來源換成 per-task `k_pairs`/`s_pairs`，迴圈結構不變。
- **D24-d A 全域一份**，從 `pairs().attitudes`，一個審閱面。
- **D24-e REVIEW 唯讀** 預覽 + 確認 → 存 `document_versions`。要改＝回上一輪重跑（跳回特定步驟的回路屬範圍外，晚點再加）。
- **D24-f idempotency**：`pairs()` **整段只打一次**、結果快取進 state；`curate_ks` 逐任務迴圈與 `curate_attitudes` 共用同一份快取，**resume 不重打**（避開 502 / 慢呼叫 / 重複副作用）。
- **D24-g `assemble_ksa` 拆除**：由 `curate_ks`（逐任務 K/S）+ `curate_attitudes`（全域 A）取代。
- **D24-h KS 審閱面預設全不勾**：職類池列為候選但不預選，人逐任務挑「哪些適用」。避免每任務被塞滿整池；契合「任務間差異由人決定」。
- **D24-i flush 集中最後一次**：所有逐任務 K/S + 全域 A 確認完，進 build_doc/REVIEW 前一次性 flush（per-profile 重寫）。理由：最簡、單 transaction、與現有 flush_ksa 一致；checkpointer 已保障中途 resume，無需逐步 flush。
- **D24-j of-record 用既有 `ksa_items.task_id`（無 migration）**：K/S → `KsaItem(ksa_type=K|S, task_id=該任務 company_tasks.id)`；A → `KsaItem(ksa_type=A, task_id=NULL)`。schema 早已預留 `task_id` FK→`company_tasks.id`。

## 5. 受影響範圍（細節待 writing-plans 展開）

- **State**：`ksa` 從「職類層一份 {knowledge,skills,attitudes}」改為 **per-task K/S**（task_id → {knowledge, skills}）+ **全域 attitudes**；deep 段加 `ks_index`（或獨立 curate 段索引）；快取職類池 `pairs` 結果。
- **後端節點**：新增 `curate_ks`（單層迴圈，鏡像 deep loop）、`curate_attitudes`；`graph.py` 路由 deep 完成 → ks loop → attitudes → build_doc；移除 `assemble_ksa`；`build_doc` 的 KSA 組裝改吃新結構（K/S 逐任務、A 全域）。
- **前端**：`KsaEditor`（現一頁編全部）拆成「逐任務 KS 審閱面」+「A 審閱面」；新增 interrupt 種類（`curate_ks` / `curate_attitudes`，payload 待定）；REVIEW = 沿用唯讀 `DocPreviewPanel`。
- **flush**：KS 逐任務確認後 flush（或全 KS 完成後一次 flush 到 `ksa_items`）—— flush 時機 = 待討論細節。

## 6. 範圍外 / 未來

- per-task catalog K/S（待 `tasks_by_id` 502 修好，D24-c 升級路徑）。
- REVIEW 就地編輯 / 跳回特定步驟重做（D24-e）。
- A 是否也可能 task 相關（目前職能基準是職類層，維持全域）。

## 7. 細節

**已定（2026-06-18 討論）**
- ✅ KS 審閱面**預設全不勾**（D24-h）。
- ✅ flush **集中最後一次**（D24-i）。
- ✅ of-record 用既有 **`ksa_items.task_id`**，無 migration（D24-j）。

**留給 writing-plans（純實作）**
1. state 確切欄位命名與 reducer（per-task K/S 結構、ks_index、pairs 快取鍵）。
2. `curate_ks` / `curate_attitudes` interrupt payload 形狀（前端審閱面渲染契約）。
3. 逐任務 KS flush 時，graph-state 任務 → `company_tasks.id` 的對應機制（flush_tasks 後把 DB id 回灌 state，或 flush 時以 indexer_ref/task_name 對應）。
4. `ksa_items` 重寫策略（per-profile 刪重建 vs row-level upsert；tech-debt 的 UNIQUE 是否一併補）。
