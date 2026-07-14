---
title: api AI 提議服務 — /ai/*(services/ai)
audience: agent-primary(也給人)
scope: apps/api/app/services/ai/(recommend_ks / draft_op / extract_tasks / structure_task / clarify)
updated: 2026-07-04
---

# api AI 提議服務 — `services/ai`(深文檔)

> **主讀者 = agent。狀態(先讀):** 5 個純函式掛在 `/ai/*` 端點後面,**只提議、不寫 DB**。
> **目前 web 零呼叫**(填格 / 選任務改吃知識包,P3);**server 端點保留**,未來自主訪談 agent 重用(ADR 0020)。
> living:改 [`services/ai/`](../../app/services/ai/) 同 commit 更本檔。

## 1. 共同 pattern(design §I:同一組函式,✨ 面板今天用、未來 agent 原封重用)

- **純、無狀態、explicit 輸入**(task / note / catalog candidates + optional `LlmPort`);**無 DB、無 FastAPI、不綁呼叫者**。
- **catalog-first**:標準項一律來自 indexer(該 `task_code` 的 `competencies`);**LLM 只個人化 / 篩選 / 草擬**。
- **降級**:無 LLM(無金鑰)或無 note → catalog-only / fallback / 空;**不崩、catalog 有就不留空**。
- **每項標 `source: "catalog" | "ai"`**(K/S 另帶一句 `reason`);LLM **grounded**——AI 發明的 code/id **丟掉**。
- 統一 `role="cheap"`(便宜模型;對比訪談引擎的 `interview`/`select`)。

## 2. 五個服務([`services/ai/*`](../../app/services/ai/))

| 服務 | 輸入 | 輸出 | 無 LLM / 無 note |
|---|---|---|---|
| `recommend_ks` | task_name, note, k/s_candidates | `{knowledge, skills}` 每項 `{code, name, source, reason?}` | 全 catalog(`source=catalog`) |
| `draft_op` | task_name, note, outputs/indicators_catalog | `{outputs[{code,name,source}], indicators[{code,text,source}]}`;**AI 項 `code=""`** | 全 catalog(catalog 空則空) |
| `extract_tasks` | intake, candidates`[{id,title}]` | `{suggested_task_ids(**grounded 到 candidates**), custom_candidates[{name}]}` | 空 |
| `structure_task` | description, occupation_context | `{task_name, unit_suggestion}` | fallback = description 原文 |
| `clarify` | task, note | 一句追問 `str` \| `None` | `None` |

> 「grounded」= LLM 只能從 candidate 清單挑 id/code;回傳裡不在清單的一律過濾掉(§2 `extract_tasks` 的
> `i in known`、`recommend_ks` 的 `code in by_code`)——**AI 不能無中生有官方碼**。

## 3. 不變量(code 讀不出的規則)

1. **只提議、不寫 DB**:提議由前端套用後走 PATCH(與知識包編輯器同一寫入路徑)。
2. **catalog-first + grounded**:官方項來自 indexer;LLM 不發明官方 code/id。
3. **source 標記**:catalog 項留原始 code(provenance 身分);**AI 個人化項 `code=""`、`source="ai"`**。
4. **無金鑰全鏈優雅降級**:`llm=None` 不發注定失敗的呼叫;面板永不因缺 LLM 而空(catalog 有的話)。
5. **路由層薄**:route 載文件 → 定位任務(provenance)→ 委派這些純函式;同邏輯給未來訪談 agent。

## 4. 指路

- 端點面 / 降級分級:[`../README.md`](../README.md)(§4 AI 提議降級鏈、端點表 `POST /ai/*`)。
- 訪談引擎(重用這些純函式):[`docs/design/interview-engine.md`](../../../docs/design/interview-engine.md)(ADR 0030)。
- catalog 從哪來:[`../../ocs-indexer/docs/pipeline.md`](../../ocs-indexer/docs/pipeline.md)(competencies)+ [`knowledge-pack-assembly.md`](knowledge-pack-assembly.md)。
- ports(`LlmPort`):`app/core/ports.py`;LLM adapter:`app/adapters/llm_openrouter.py`(per-role + JSON 重試)。
