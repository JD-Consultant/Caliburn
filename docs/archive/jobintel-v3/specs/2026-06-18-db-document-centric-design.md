# jobintel-ai v3 — DB 文件導向重設計（Design Spec）

> 日期：2026-06-18。分支 `feat/v3`。
> 修訂：本決策**翻轉 D6/D9**（業務表 of-record + write-through）→ **文件導向**；延續 D14（深問細節不落業務表）。
> 決策紀錄：`2026-06-16-refactor-decision-log.md`（D25）。
> 緣由：討論「何時存 DB、什麼欄位、哪些表」時，發現 v3 實際只用到關聯表的一小部分；經權威資料佐證後改採文件導向 MVP。

---

## 1. 決策

of-record 改為 **文件導向**：產出的 OCS 文件存成**有版本的 JSONB**（`document_versions`），任務/KSA/指標/深問細節**不再各自開關聯表**。業務關聯表精簡到 **3 張**：`users`、`job_profiles`、`document_versions`。進行中的工作態全在 **LangGraph checkpointer**。

## 2. 權威依據

- **JSONB vs 正規化欄位**：JSONB 適合彈性/巢狀/外部 API 回應/尚不值得開表者；正規化適合需 filter/sort/aggregate/join 的穩定實體；「JSONB 長成穩定 mini-schema 再正規化」。我們的任務/KSA 目前**無查詢需求** → JSONB 即可。來源：[nwos](https://nwos.com/daily/postgres-json-columns-when-theyre-a-lifesaver-and-when-theyre-a-trap)、[architecture-weekly](https://www.architecture-weekly.com/p/postgresql-jsonb-powerful-storage)。
- **LangGraph 三層分離**：checkpointer = 短期 thread 工作態（HITL）；store = 跨 thread；業務 DB = of-record。明確警告別把大產物塞 graph state。我們深問細節歸 checkpointer、文件歸 document_versions 正合此分法。來源：[LangChain persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[fast.io](https://fast.io/resources/langgraph-persistence/)。
- **企業結構化內容**：產出的結構化 JSON 存成有版本 + 稽核的文件（MS/IBM）。`document_versions` 即此角色。
- **Migration**：2025 主流 SQLAlchemy = **Alembic**（autogenerate、DB 內版本追蹤、可匯出 raw SQL）。來源：[Alembic best practices](https://medium.com/@pavel.loginov.dev/best-practices-for-alembic-and-sqlalchemy-73e4c8a6c205)。
- **清理策略**：expand-contract 是給正式環境零停機；我們**未上線 + 舊 code 已移除（Concern B）**，contract 前提已滿足 → 可直接破壞性清理。來源：[Prisma data guide](https://www.prisma.io/dataguide/types/relational/expand-and-contract-pattern)。

## 3. 目標 schema（3 張業務表）

**`users`**（不動）：`id, email, name, company, created_at`

**`job_profiles`**：`id, user_id, job_title, department, job_summary, selected_ocs_codes TEXT[]（有序複選）, created_at, updated_at`
- drop：`graph_state, stage, completion_pct, icap_source_type, document_draft, tenure_months, primary_stakeholders`
- `selected_ocs_code`(單) → `selected_ocs_codes TEXT[]`(有序，對齊複選決策)

**`document_versions`**：`id, job_profile_id, version, content JSONB（整份 OCS 文件）, status TEXT('draft'|'frozen'), created_at`
- drop：`file_path`（無存檔）、`format`（永遠 json；未來 docx/pdf 匯出 = on-demand 產生，不入庫）

**工作態（不在我們 migrations）**：LangGraph `AsyncPostgresSaver` 自管的 `checkpoints / checkpoint_writes / checkpoint_blobs`。

## 4. 全部 drop

表：`company_tasks`、`ksa_items`、`icap_references`、`interview_sessions`、`icap_embeddings`（+ `vector` extension、相關 index/trigger）。
SQLAlchemy models：`CompanyTask`、`KsaItem`、`IcapReference`、`InterviewSession`。

## 5. 流程 → 何時寫 DB（新）

```
新增職務(dashboard) → INSERT users(匿名,一次) + INSERT job_profiles
pick_profile 選OCS  → UPDATE job_profiles.selected_ocs_codes
任務 / 深問 / KS / A → 只進 checkpointer（不寫業務表）
build_doc REVIEW 確認 → INSERT document_versions（整份 OCS 文件 JSONB）
```

## 6. 取捨

- **好**：schema 只反映真實所需；of-record = 有版本文件 JSONB（業界標準）；persistence 大幅簡化。
- **代價**：翻轉 D6/D9 write-through；任務/KSA 不能用 SQL 查/單欄改（目前無此需求）。將來有查詢/分析需求再正規化（JSONB→欄，容易）。
- 對齊 D14。

## 7. 範圍（persistence 層重作）

1. **Alembic 導入**：以目前實際 schema 為 baseline；一個 revision 套用本設計（drop 表/欄、改 selected_ocs_codes、精簡 document_versions）。
2. **Models**：刪 `CompanyTask/KsaItem/IcapReference/InterviewSession`；`JobProfile` 砍死欄 + `selected_ocs_codes`；`DocumentVersion` 精簡。
3. **Schemas**：對應砍 Pydantic（`JobProfileOut/Create/Update`、刪 CompanyTask*/相關）。
4. **Persistence**：`PersistPort` 縮到 `set_selected_ocs(codes)` + `save_document`；刪 `TaskRepo/KsaRepo/flush_tasks/flush_ksa`；`DocRepo` 保留。
5. **Graph 節點**：`build_task_pool` 不再 flush；`build_doc` 只 `save_document`；`pick_profile` 寫 `selected_ocs_codes`。
6. **舊 code 連帶清**：`documents.py`（讀 graph_state/stage，已壞）、`main.py` demo（若僅 demo）、相關死路由。
7. **測試**：更新/刪除涉及 flush_tasks/flush_ksa/company_tasks/ksa_items 的測試；新增 document_versions of-record 測試。
8. **state**：graph state 結構不變（仍含 tasks/deep/ksa 工作態）；只是不再 flush 到關聯表。

## 8. 範圍外 / 未來

- 任務/KSA 正規化（待出現跨 profile 查詢/分析/單欄編輯需求，D25 升級路徑）。
- 文件匯出 docx/pdf（on-demand）。
- selected_ocs_codes 是否需另存優先度權重（目前順序即優先度，足夠）。

## 9. 待實作細節（writing-plans 展開）

- Alembic 導入步驟（env.py 接 settings.database_url + models metadata；baseline 如何處理既有 DB）。
- `selected_ocs_codes` reducer / set_selected_ocs(codes: list) 簽章。
- document_versions content 的 schema（沿用 build_doc `_assemble` 產出）。
- 測試 DB fixture 是否隨 Alembic 改變。
