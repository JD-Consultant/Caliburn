# JobIntel AI — 文件索引

> 企業職務知識萃取 / OCS 職務說明書生成 AI（v3）

v3 重構後，**架構/決策/計畫文件集中在 [`superpowers/`](./superpowers/)**（本地記錄、未納版控）。

## 設計與決策（`superpowers/specs/`）
| 文件 | 說明 |
|---|---|
| `2026-06-16-jobintel-ai-v3-architecture.md` | v3 目標架構（5 骨幹節點 + 深問迴圈 + KnowledgeClient + persistence） |
| `2026-06-16-refactor-decision-log.md` | 決策日誌 D1–D25（含權威來源、取捨、討論過程） |
| `2026-06-18-ksa-flow-redesign-design.md` | 逐任務 K/S + 全域 A + REVIEW（D24，已實作） |
| `2026-06-18-db-document-centric-design.md` | DB 文件導向重設計（D25，已核准／待實作） |
| `2026-06-15-architecture-research.md` | 架構研究資料總表 |
| `2026-06-14-jobintel-ocs-integration-design.md`／`2026-06-14-jd-authoring-flow.md` | 早期整合設計／流程目標 |

## 實作計畫（`superpowers/plans/`）
各 phase（資料層／骨幹／深問／assemble-build／OTel-eval）＋ Concern B、Live-wire A、KSA 流程重設計的 subagent-driven 計畫（歷史執行紀錄）。

## 仍有效的參考文件
| 文件 | 說明 |
|---|---|
| [ocs-schema.md](./ocs-schema.md) | OCS 職能文件 JSON 結構 + 代碼規則（T/P/O/K/S/A），對應 v3 `build_doc` 產出 |

---

> **註**：頂層原有的舊架構文件（`architecture` / `db-schema` / `api` / `graph-pipeline` / `frontend` / `icap-pipeline` / `rag-pipeline` / `export` / `roadmap` / `testing`）描述的是重構前架構（iCAP 比對、RAG、pgvector、舊 8 節點狀態機、手刻 SSE 前端），已於 v3（Concern B + D24/D25）移除，故一併刪除。需要時可由 git 歷史取回。v3 的權威說明見上方 `superpowers/`。
