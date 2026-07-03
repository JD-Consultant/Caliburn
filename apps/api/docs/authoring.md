---
title: api authoring — LangGraph 訪談引擎(內部)
audience: agent-primary(也給人)
scope: apps/api/app/authoring/(LangGraph 訪談圖:pick → 逐任務深問 loop → curate → build_doc)
updated: 2026-07-04
---

# api authoring — LangGraph 訪談引擎(深文檔)

> **主讀者 = agent。狀態誠實(先讀):** 這是**原始對話式訪談引擎**(原 graph_v3)。LangGraph **保留**
> (ADR 0007),以 AG-UI agent 掛在 `/copilotkit`。**但當前 web 前端用的是知識包編輯器**
> (選職類→選任務→填格 + autosave PATCH,見 [`docs/design/editor-knowledge-pack.md`](../../../docs/design/editor-knowledge-pack.md)),
> **並未掛面板驅動這張圖**;訪談**互動模式待 ADR 0020 重新設計**(不受既有資產約束)。
> `build_doc` 產的還是**舊 doc shape**(`ocs_ksa` 等),非現行 `packages/ocs-contract`。
> 改這裡前務必先讀——**尤其 §3「別重構」**。living:改圖同 commit 更本檔。

## 1. 一句話

一張 **LangGraph 圖**,用 `interrupt` 逐槽問人:**選職類 → 建任務池 →(每任務)STAR → 5W2H → 指標 →
補 K/S/A → deterministic 組文件**。`deps`(llm / knowledge / persist ports)由 config 注入。

## 2. 圖結構([`graph.py`](../../app/authoring/graph.py))

```
START → pick_profile → build_task_pool
                          │ route_deep: index < len(tasks) ?
          ┌───────────────┴──────────────┐
        star (深問這個任務)            finish_deep(全部問完)
          │                              │
        five_w2h ◄──┐                    ▼
          │         │ route_after_    fetch_ksa_pool → curate_ks
        indicator ──┘ indicator:        → curate_attitudes → build_doc → END
          │  弱欄→five_w2h / 否則→advance
        advance_deep ── route_deep ──► star(下一任務)/ finish_deep
```

三個階段:**① pick_profile / build_task_pool**(選職類候選、建任務池)→ **② 逐任務深問 loop**
(star/five_w2h/indicator)→ **③ 收尾**(fetch_ksa_pool → curate_ks → curate_attitudes → build_doc)。

## 3. 刻意單層 loop(**別重構!**)

**逐任務深問是「圖層級的扁平 node 迴圈」**,不是巢狀子圖、不是 `Send`/map-reduce:

`star → five_w2h → indicator →(route_after_indicator)→ advance_deep →(route_deep)→ star(下一任務)`

- 迴圈靠 **conditional edges + `deep.current_task_index`** 前進(`advance_deep` 標 completed + index+1)。
- **為什麼刻意單層**:每個任務的深問要**逐槽 `interrupt` 問人、可續、可重試單欄**;扁平 node loop 讓
  「暫停點 / retry / 前進」都在同一層、checkpointer 存得乾淨。改成子圖 / `Send` 會把 interrupt 續跑
  與 per-task retry 搞複雜。**別為了「看起來乾淨」重構成巢狀。**

## 4. interrupt 驅動 HITL

節點用 `interrupt({...})` **暫停整張圖**,把 payload 丟給前端;前端把人的答案 resume 回來,節點從斷點續跑。

| payload `kind` | 何時 | 內容 |
|---|---|---|
| `ask_human` | star / five_w2h 每槽 | `stage / slot|field / task_name / label / question` |
| `preview` | build_doc | `document`(唯讀 REVIEW) |

state 由 **checkpointer 持久化**(live = Postgres,demo = MemorySaver)→ 回合制、可續。

## 5. 深問三節點內部([`deep_nodes.py`](../../app/authoring/deep_nodes.py))

- **star**:S/T/A/R 四槽各一次 `interrupt`;收齊後 LLM 精煉(`role="deep"`,**best-effort**,失敗/缺鍵保留原答)。
- **five_w2h**:先 **prefill**(STAR 的 S→situation、A→workflow_steps;catalog 的 outputs 走 `competencies` JIT 帶入)
  → 再對**仍缺**的 `FIVE_W2H_REQUIRED` 欄逐一 `interrupt` 問。
- **indicator**:① **guardrail**——必填欄缺 → 退回 five_w2h;② LLM 產指標(`role="indicator"`);
  ③ **品質分**(7 維、門檻 0.60)不足且 `retry ≤ 1` → pop 弱欄、退回 five_w2h;否則接受(`ok` / `force_accepted`)。

## 6. 收尾:curate + build_doc

`fetch_ksa_pool`(抓職類 K/S/A 池)→ `curate_ks` → `curate_attitudes` → **`build_doc`**
([`build_doc.py`](../../app/authoring/build_doc.py)):**deterministic 組裝**——依 `unit_id` 分組、
T/P/O/K/S/A **全程式化編碼**(不用 LLM)→ `interrupt(preview)` 唯讀 REVIEW → `deps.persist.save_document`。

## 7. serving + deps 注入([`serving.py`](../../app/authoring/serving.py))

- 以 **`ag-ui-langgraph` 的 `LangGraphAgent`** 服務(取代 legacy copilotkit remote endpoint);app 用
  `add_langgraph_fastapi_endpoint(app, agent, "/copilotkit")` 掛載;`AGENT_NAME = "jd_authoring"`。
- 兩條裝配:**demo**(`MemorySaver` + stub deps,測試/本地)/ **live**(`HttpIndexerClient` + `LiveDbPersist` +
  `OpenRouterLlm`)。**deps 一律經 `config={"configurable": {"deps": …}}` 注入**,節點不自己 new adapter。
- **無 `OPENROUTER_API_KEY` → `llm=None`**:深問/收尾全鏈**優雅降級**(STAR 保留原答、indicator `force_accepted`),
  仍可全程 interrupt 驅動測完整流程,且免注定失敗的 API retry。

## 8. 不變量(code 讀不出的規則)

1. **別重構單層 loop**:逐任務深問是圖層級扁平迴圈(interrupt + conditional edges),不改巢狀子圖 / `Send`(§3)。
2. **deps 注入、節點不 new adapter**:`config["configurable"]["deps"]` 給 ports → 可 fake 測(hexagonal,ADR 0008)。
3. **LLM 全程 best-effort 降級**:`llm=None` 不擋流程(§7);別假設一定有 LLM。
4. **build_doc deterministic**:編碼不用 LLM;可重現。
5. **interrupt HITL + checkpointer**:回合制、可續;state 是唯一真相。

## 9. 指路 + 狀態

- ADR [0007](../../../docs/adr/0007-langgraph-retained-mcp-ready.md)(LangGraph 保留 + 12-factor + MCP-ready)·
  [0008](../../../docs/adr/0008-api-hexagonal-layering.md)(六邊形)·
  **[0020](../../../docs/adr/0020-interview-authoring-interaction-model.md)(訪談互動模式待重設計——本引擎的未來)**。
- 當前**主要**著作路徑(非本圖):[`docs/design/editor-knowledge-pack.md`](../../../docs/design/editor-knowledge-pack.md)(知識包編輯器)。
- app 面 / 端點:[`../README.md`](../README.md)。文檔怎麼寫:[`docs/README.md`](../../../docs/README.md)。
