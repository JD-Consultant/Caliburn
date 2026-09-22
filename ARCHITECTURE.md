# Caliburn 架構

> 正式權責以 [ADR0077](docs/adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)、
> [目前決策](docs/current-decisions.md)與各責任設計文件為準。本頁只提供現行鳥瞰，不複製完整規則。

Caliburn 是本機 Web AI 職務分析與職務說明書（JD）App。員工可直接編輯 JD，也可與顧問持續訪談，
由 LLM 透過相同的 App 業務規則讀寫 JD。單一操作者可管理多份彼此隔離的文件；目前沒有登入、ACL、
多租戶、計費、雲端部署或多人協作。

## 現行組成

```text
Next.js／TypeScript Web (:3002)
              │ HTTP
              ▼
FastAPI JD App (loopback；port 由受保護設定提供)
       │
       ├─ 關聯式 JD domain／service（人與 LLM 共用）
       ├─ A 主顧問與 JD／Memory／來源工具
       ├─ B1 案例整理、B2 工作理解、C 即時更正
       ├─ App-side continuation compaction 與 Working State
       ├─ LangGraph Saver／Store、Memory publication
       └─ OpenRouter → OpenAI-only Luna（無自動 fallback）
              │
              ▼
PostgreSQL 18.6
  public      關聯式 JD 與背景准入
  jd_runtime  對話、執行狀態、Memory 與 publication
```

正式程式位於：

| 路徑 | 責任 |
|---|---|
| [`experiments/jd-relational-app/`](experiments/jd-relational-app/README.md) | App composition root、API、JD domain、A／B1／B2／C runtime、持久化與驗收 |
| [`experiments/jd-relational-app/web/`](experiments/jd-relational-app/web/README.md) | 同頁訪談、六章 JD 編輯、改動／來源查看與只撤回本輪 JD |
| [`packages/consultant-memory/`](packages/consultant-memory/README.md) | 分層案例／工作理解 Memory、Skills 與 publication 元件 |

`apps/api`、`apps/web`、`packages/job-analysis-contract` 的舊可執行程式已退役；保留的 README 只供歷史追溯，
不可成為 import、啟動或契約 authority。

## 權責不變量

- PostgreSQL 是正式資料 owner；Web 不保存第二份正式 JD，也不重算 domain invariant。
- 人工編輯與 LLM 工具可使用不同 endpoint，但必須經過同一套 JD service、驗證、版本與保存規則。
- 原始訪談完整保存；案例與工作理解分層整理、可引用回查。Compaction 只管理模型延續 context，不能取代原話或工作理解 Memory。
- 文件、版本、scope、引用解析、寫入條件與 persistence 由 Runtime／App 管理，不要求模型自行生成。
- `request_memory_consolidation` 是非等待式通知；背景整理不阻斷 A 的自然回答。
- 本輪 JD 撤回只撤回該輪 JD effects，不撤回原始對話、來源或 Memory。
- OpenRouter credential 只存 Windows 認證管理員；無 key 時人工 JD 仍可使用，AI 明示停用。

詳細責任見 [JD App README](experiments/jd-relational-app/README.md)、
[跨 Agent 來源與 JD context 契約](docs/specs/2026-09-20-cross-agent-evidence-and-jd-context-contract.md)、
[分層 Memory 背景流程](docs/specs/2026-09-17-layered-memory-background-workflow-design.md)及
[runbook](docs/runbook.md)。

## RAG（保留、隔離）

`apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder`、`packages/ocs-contract` 與
`packages/indexer-contract` 是可獨立執行的 RAG bounded context，目前沒有正式 JD App consumer。
只有 `pnpm rag:*` 才會明示啟動；詳見 [RAG 設計](docs/design/rag-pipeline.md)。
