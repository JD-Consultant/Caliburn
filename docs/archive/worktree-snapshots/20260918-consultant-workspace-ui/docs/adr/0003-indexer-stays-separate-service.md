# ADR 0003 — ocs-indexer 維持獨立服務(不併進 api)

- **狀態**:Accepted（2026-06-27）

## 脈絡

`ocs-indexer` 能否併進 `api`(少一個服務、少一個網路跳轉)?

## 決定

**維持獨立服務。** 決定性理由:
- **執行環境差異大**:indexer 背 BGE-M3(重 ML / torch)+ Qdrant,記憶體/運算重、冷啟慢(~3s)。併進 api → 每次部署 api 都拖整套 ML。
- **獨立擴展**:api 隨活躍使用者擴;indexer 隨查詢/重建索引擴。
- **全域 vs 多租戶**:indexer 是全域共享(官方目錄人人同一份);api 是多租戶。角色不同。

api 透過 **HTTP** 消費 indexer(內部信任,不帶使用者 token);未來多消費者時再升級 **MCP**(見 ADR 0007)。

## 後果

- ✅ api 保持輕、可獨立部署/擴展。
- ✅ 符合「合法該拆服務」判準(不同 runtime/擴展/角色)。
- ⚠️ 多一個網路跳轉(內部、便宜)。
- ⚠️ indexer 的 Qdrant 是它的私有倉庫;**別的服務不直接連,只經 indexer API**(資料主權)。
