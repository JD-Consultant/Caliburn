# ADR 0009 — embedding 版本 manifest + 查詢前相容驗證;瘦 CLI

- **狀態**:Accepted（2026-06-28;Phase 3c）。

## 脈絡

`apps/ocs-indexer`(pdfplumber-JSON → BGE-M3 → Qdrant;FastAPI 查詢 API 供 `apps/api` 用)有兩個問題:

- **嵌入身分沒被記錄**:建索引用的 embedding 模型(provider `bge-m3`、model `BAAI/bge-m3`、dim 1024)沒存在任何地方(payload 的 `version` index 是 OCS *文件*版本,不是模型)。查詢端 `embed_query` 後直接搜,**從不檢查查詢用的 embedder 是否與建索引時一致**。一旦改 `BGE_M3_MODEL` 或維度,就會靜默回傳垃圾相似度,或丟維度錯。
- **CLI 不夠瘦**(394 行):`index` 把整條 pipeline 塞在指令體內;embedder 建構在 index/query/api 三處複製。

權威依據:Qdrant 官方 *Migrate to a New Embedding Model* + *Collections*(無 collection-level metadata → 記在 payload;換模型 = 重嵌入重建,index 視為原子單位);Zilliz 版本化 FAQ(記 provider+model+dim、語意版本、追蹤每筆由哪個模型產生);TianPan「index drift」(**在設定/查詢前就驗證相容,別等查詢才爆**);Typer 官方(業務邏輯放純函式、CLI 只當 interface 層)。研究紀錄:`docs/specs/2026-06-28-ocs-indexer-embedding-version-thin-cli-research.md`。

## 決定

**A. 嵌入版本標記(feature,TDD)**
- 在嵌入契約加穩定身分 `EmbeddingSignature{provider, model, dim, revision}`(`revision` 在前處理/正規化改變時遞增,即使模型名不變)。`BGEM3Embedder.signature` 由既有屬性導出。
- 建索引時寫一筆 **manifest 保留點**:固定 id、payload `chunk_level="_manifest"`,記 signature + `built_at`。因現有搜尋皆按 `chunk_level ∈ {profile, task}` 過濾,manifest 點**天生被排除**,不汙染結果。`store/manifest.py` 提供 `write_manifest`/`read_manifest`。(D-3c-1:保留點,非 per-point payload、非 collection 改名 —— 單一真相、O(1) 驗證、無膨脹、無命名耦合。)
- 查詢前 `assert_compatible(read_manifest(...), embedder.signature)` **fail-fast**:provider/model/dim 不符 → 丟 `EmbeddingMismatchError`(API 映成 HTTP 409);無 manifest(舊索引)→ 軟性放行 + 警告;僅 revision 不同 → 警告。healthcheck/stats 顯示 `index_model`。

**B. 瘦 CLI(move-only)**
- `embeddings/factory.make_embedder(settings)` —— embedder 唯一建構點(index/query/api.app 共用)。
- `pipeline.run_index(settings, scan_dir) -> IndexReport` —— index 編排移出 CLI;`cli index` 變薄殼(只渲染 rich 報表)。
- presentation(rich tables/console)留在 `cli.py`(interface concern)。

全程以既有測試套件當安全網,測試數階梯 35→36→38→41,Thread B move-only、Thread A TDD(先寫失敗測試)。

## 後果

- ✅ 換模型/維度不再靜默壞掉:查詢前就擋下、明確報錯;ops 從 healthcheck/stats 看得到索引用哪個模型。
- ✅ pipeline 與 embedder 建構成為可重用純函式(CLI/API/batch 共用),CLI 變薄。
- ✅ 行為相容:manifest 點不進搜尋結果;舊索引(無 manifest)軟性放行。
- 📌 tag:`phase3c-ocs-indexer`。

## 已知後續(本 ADR 範圍外)
- **零停機換模型**:Qdrant named-vectors / alias / dual-write 的 live migration(未來;本次只做「記錄 + 驗證」,不做遷移)。
- 每次查詢都讀一次 manifest(多一次 retrieve);可改為啟動時驗證一次或加快取。
- manifest 點會讓 `stats` 的 total_points +1;若要精確可在計數時排除 `_manifest`。
