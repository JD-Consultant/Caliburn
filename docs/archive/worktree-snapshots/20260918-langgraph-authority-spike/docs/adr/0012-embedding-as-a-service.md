# ADR 0012 — 嵌入服務化:自建 BGE-M3 容器(FlagEmbedding,保留 dense+sparse)

- **狀態**:Accepted（2026-06-29）。

## 脈絡

`ocs-indexer` 把 BGE-M3 嵌入(FlagEmbedding/torch)**跑在自己的進程內、在 Windows host**,被解析到的 `torch 2.12.0+cu130` 連環不穩:OMP segfault(已用 `OMP_NUM_THREADS=1` 繞)、`torch._dynamo` mega-cache **雙註冊 AssertionError**(uvicorn `serve` 下 lazy import 必爆 → 查詢全 500)。經證據式排查:**與版本無關**(torch 2.6/2.12、transformers 4.57/5.9、numpy 1.26/2.4 都重現;模型檔 sha256 相符);`index`(CLI 乾淨 import)能跑、`serve` 不行。根因是「torch 跑在 app 進程 + Windows」這個架構,版本 pin 治不好。見 [[windows-openmp-bge-segfault]]、研究紀錄 `docs/specs/2026-06-29-embedder-service-bge-m3-research.md`。

權威研究:主流是**嵌入用獨立推論服務**(TEI/Triton/TorchServe/Infinity),非 in-process。但 **TEI 與 Infinity 都不支援 BGE-M3 的 sparse**([TEI #289](https://github.com/huggingface/text-embeddings-inference/issues/289);Infinity README「bge-m3, no sparse」)。我們要保留 **dense+sparse hybrid**(使用者決定)。BGE-M3 sparse 只有 **FlagEmbedding** 做得到。

## 決定

**嵌入改為獨立服務,自建一個薄 BGE-M3 容器**:
- **新服務 `apps/embedder`**:`nvidia/cuda` base + Python + **pinned 穩定 torch(Linux cu12x)** + flagembedding + 一支 FastAPI(`POST /embed` 回 dense+sparse、`GET /health`),產生**與現行 `BGEM3Embedder` 完全相同**的向量。
- **`ocs-indexer` 去 torch 化**:新 `adapters/http_embedder.py` 實作 3c `EmbeddingService`(httpx 打 embedder),`factory` 回傳它;**移除 torch/flagembedding/transformers 依賴 + 砍掉 in-process `BGEM3Embedder`**。3c manifest/signature 不變(`bge-m3/BAAI/bge-m3/1024`)。
- **compose / 一鍵**:加 `embedder` 服務(`gpus: all`、模型快取 volume、`/health` healthcheck);`npm run up` 一起起。env `EMBEDDER_URL`。
- **重建一次 `ocs_v4`**(經服務;index+query 同源,sparse 一致)。

**為何這樣**:① 把 Windows 專屬的 torch 坑**從架構根除**(容器內是 Linux,torch 穩定);② 保留 hybrid(現成伺服器做不到);③ indexer 變純 Python、嵌入成為可獨立部署/擴展的服務(對齊 ADR 0003 + 3c port 抽象 + 一鍵 compose)。

**否決**:TEI/Infinity(無 BGE-M3 sparse,會失去 hybrid);in-process + torch 降版(仍是 anti-pattern + Windows 脆弱);TorchServe/Triton(現階段過重,留作未來升級)。

## 後果

- ✅ 查詢可用、hybrid 保留、Windows torch 坑消失;indexer venv 大幅瘦身(無 torch)。
- ✅ 嵌入服務獨立鎖版/重啟/擴副本/重現(image)。
- ⚠️ 多一個要維護的容器 + image(~數 GB);需 GPU 容器(本機已驗證 RTX 4060 可用)。
- ⚠️ indexer↔embedder 的 HTTP 形狀目前手寫;未來可升級為 **contract #4**(見 `docs/contract-strategy.md`)。
- 📌 tag `embedder-service`。後續可換 TorchServe/Triton/m3serve 而不動 indexer(port 抽象)。
