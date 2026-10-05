# 公版職位參考 API 施工計畫

> 執行：使用 executing-plans inline 及 TDD；最後由 requesting-code-review 派獨立 reviewer。不提交、不切換正式 App。使用者已授權本輪 API 及必要重構，依 AGENTS 自行決定可逆工程細節，不重問施工許可。

**Goal:** 提供可獨立啟動、未接 Agent 的公版參考搜尋與按需讀取 API。
**Spec:** [責任契約](../specs/2026-10-05-occupation-reference-api-design.md)。
**Architecture:** `references` 管來源投影、搜尋用例、Qdrant adapter；`api/reference_routes` 只驗 HTTP 與投影。現有 embedding HTTP port 重用；rerank 的真正 I/O 使用窄 Protocol。GPU 推論保持在既有 embedder 服務。
**Tech Stack:** 既有 Python／Pydantic／FastAPI／Qdrant 1.18／httpx；無 indexer torch 新相依。

## Constraints / review focus

查詢不得輸出適用／完成判定；無員工狀態；完整目錄不限於命中點；原始來源 hash 綁定；不得偷偷改歷史實驗。檢查無碼重複 task、多 T 共用區塊、初始化失敗、模型尾端截斷、集合與 embedding 不相容、上游失敗不可當空結果。當前 checkout 已有本輪資料與其他變更，保留；本計畫僅改自己列出的範圍，不自動建立需複製未提交資料的 worktree。

## Tasks

1. 契約與來源：在 shared contract 增加 reference DTO；`references/source.py` 從既有 OCSDocument 驗證投影。`build_reference(source_utf8, source_file)` 產生有來源 hash 的完整目錄與 D/T 正文。測來源、無碼、共用群組與前處理。
2. 檢索與索引：`references/store.py` 管 exact 父 group、ready manifest／JSON 保存與 reads；`references/service.py` 注入 embedder／store／reranker，做 D/T 完整聯集後 rerank。CLI `index-references` explicit 新 collection。測完整聯集、empty／failure、身分、實際 SDK。
3. HTTP 與 GPU：`api/reference_routes.py`、app lifespan／settings 組裝普通 use case；`reranking/http_reranker.py` 驗上游 response；既有 embedder 增 `/rerank` 及 token-window helper。測 422／404／409／502／503、GPU 邊界、資源、OpenAPI。
4. 回歸與重播：既有 indexer 測試、新 API 測試、格式／型別／schema／build；固定資料重播（body hash 與 final ranks）另記證據。獨立 review、修高影響問題；更新 README／目前決策／設計路由，不接正式 App。

每項先測反例 Red，再 Green／Refactor；驗證命令與實際結果寫下方 evidence，非 git commit 授權。

## Evidence

- Preflight：`S:\caliburn`，branch `jd-app-docker`；已有大量變更保留。無局部 AGENTS。qdrant-client 1.18.0、Pydantic 2.13.4、FastAPI 0.136.3、httpx 0.28.1。
- 設計及既有 ports／資料契約已核。新 endpoint 命名遵循 ADR0019；RAG Pydantic authority 延續既有 indexer-contract，不改正式 App 生成來源。

### Red → Green 與實際交付

1. 新搜尋／讀取 endpoint 原為 404，聯集搜尋用例尚不存在；補來源、use case、Qdrant adapter 與薄 HTTP 投影。測試驗證兩路聯集中的候選全送 rerank，最後才截五份，未命中任務仍留在完整目錄。
2. 無效模型結果原被接受：空回覆／零向量／不同模型，以及同名模型的不同權重，都有 `DID NOT RAISE` 反例；補身分、數量、維度、有限值及非零驗證。固定 BGE-M3 權重與實驗一致。
3. 未 ready 的來源讀取原未拒絕；在 read use case 加 manifest 驗證後通過。無碼群組、多 T 共用區塊、原始來源 hash 及重複版本均有行為測試。
4. 獨立 reviewer：Critical 0／Important 0／Minor 1。Minor 是 GPU 初始化失敗後保留已載模型；反例先失敗，再將 startup 包在同一 `try/finally`，測試通過。使用者已授權必要優化，因此本輪直接修正。該 review 不涵蓋搜尋品質或完整 JD 旅程。

### 最終驗證層級

- 本機 indexer／embedder 回歸：86 項通過；命令與輸出另存[驗證證據](evidence/2026-10-05-occupation-reference-api/README.md)。包含既有 API 與新 API 契約、404／409／422／502／503、OpenAPI、資源 ownership／啟動失敗、HTTP adapter、SDK 索引與來源讀取。
- Ruff E/F/I 及 format：20 個本輪 Python 檔通過；strict mypy：11 個來源檔通過（新 feature、契約、helper 及 HTTP embedding adapter），不是全 repo strict 檢查。
- 根 `pnpm build` 通過，包含 App 契約 codegen、Web TypeScript 與 build。一般沙盒起初拒絕 uv cache，使用核准的快取存取後通過；既有 bundle 大小提示不影響結果。
- `pnpm --filter @caliburn/ocs-contract run check-codegen` 在 Windows Bash 權限處失敗，未執行生成。讀腳本發現它會用 `git checkout` 還原未提交生成物；本工作區已有他人／前輪 schema 與 model 修改，因此不以 Git HEAD 做有破壞性的重試。改將同一 generator／flags 生成到全新暫存檔，與目前 Python model 比對一致，未修改來源檔。此輪未改 OCS schema／TS 契約。
- 真 Qdrant 1.18.2 重播：805 份來源 UTF-8 hash、805 份 D 正文、8,068 個 T／概述正文均與凍結實驗一致；新 API 八案前五完全相同，來源目錄及任務正文可讀。向量／logit 使用舊快取，明確不算 fresh 模型或新品質評分。
- 禁網路 GPU 實測：1 筆 fresh query embedding、5 組 fresh rerank；向量最大絕對差 `0.000051792705398789884`，logit 最大差 `0`。公開權重沿固定 revision；實際 torch 2.6.0+cu124、transformers 4.57.6、FlagEmbedding 1.4.0、FastAPI 0.115.0。
- 新 API 接真 Qdrant／GPU HTTP：固定合成全端 F01，1 筆 fresh embedding、完整聯集 34 組 fresh rerank、64 個 task reads 通過，最終五份與舊結果相同。單次觀察約 3.54 秒含來源讀取，不是速度 benchmark；805／8,068 個索引向量仍為凍結快取，未重算全庫 embedding。

### 界線與保留資料

四項 task 已完成。本輪未接 JD App／Agent、不評員工適用性或完整度、不重選官方版本，也未改歷史實驗或付費外送。20／5 是可執行控制初值，仍需更多真實輸入與品質評分才可採納通用參數。未提交、push 或 merge。

重播原件、fresh 結果、程式 hash、驗證輸出及自有服務狀態保留於[本輪證據](evidence/2026-10-05-occupation-reference-api/README.md)；不把它們寫回封存實驗。自有模型／Qdrant 測試程序在驗證後停止，未停止既有 JD PostgreSQL 或啟動舊實驗 bootstrap。
