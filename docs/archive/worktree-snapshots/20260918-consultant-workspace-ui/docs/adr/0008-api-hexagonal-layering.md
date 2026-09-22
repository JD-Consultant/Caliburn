# ADR 0008 — api 六邊形分層:ports→core、adapters→edge、移除 services→graph_v3 反向邊

- **狀態**:Accepted（2026-06-28;Phase 3a）。

## 脈絡

`apps/api`(FastAPI + LangGraph 的 JD 撰寫後端)**已經**用了 ports(`Protocol`)+ adapters + Repository + DI,但分層的「擺放位置」與「依賴方向」不一致:

- **Port 住在外層**:`LlmPort`/`PersistPort` 定義在 `app/graph_v3/deps.py` 裡 —— port 是六邊形的「內層」,卻被放進「傳遞機制(graph)」。
- **應用層反向依賴傳遞層**:5 個 `app/services/ai/*` use-case 全 `from app.graph_v3.deps import LlmPort`。應用層 import 圖層 = 依賴規則反了。
- **`app/services/` 語意混雜**:同時混 port(`knowledge/base`)、adapter(`knowledge/http_client`、`persistence`)、use-case(`ai/*`、`ocs_doc`、`header_meta`)。

權威依據一致(Cockburn 六邊形原創、Martin Clean Architecture 依賴規則、Percival & Gregory《Architecture Patterns with Python》、LangGraph 官方「節點只做編排、業務邏輯分離」、PEP 544 `Protocol`):port 屬內層、應用層只依賴 port、adapter 在邊緣、graph/routes 為傳遞層在 composition root 注入。研究紀錄見 `docs/specs/2026-06-28-api-hexagonal-untangle-research.md`。

## 決定

把分層擺回正確位置,依賴方向只向內。**純 move-only 重構**,以既有測試套件當 characterization 安全網(全程 86 passed)。

- **`app/core/`(內層,純)**:`ports.py`(`KnowledgePort`/`LlmPort`/`PersistPort`,`Protocol`)+ `knowledge_dto.py`(port 的資料契約)。只依賴 stdlib + pydantic。`KnowledgePort` 為 `KnowledgeClient` 改名(保留 `KnowledgeClient = KnowledgePort` 別名,節點呼叫端不動)。
- **`app/services/`(應用 use-case)**:只 import `app.core` —— `services→graph_v3` 反向邊就此消失。
- **`app/adapters/`(邊緣)**:`llm_openrouter`(OpenRouterLlm)、`knowledge_http`(HttpIndexerClient)、`persistence`(ProfileRepo/DocRepo/DbPersist/LiveDbPersist/compute_completion)、`stubs`。
- **`app/graph_v3/`(傳遞:只剩編排)**:`deps.py` 縮成只有 `Deps` dataclass;`serving.py` 仍是 composition root,從 `app.adapters` 接線。
- **`app/api/routes/`(傳遞:HTTP)**:依賴 `app.services` + `app.core.ports`,邊緣注入 adapter。

依賴箭頭(改後,皆向內):`adapters → core` · `services → core` · `graph_v3 → services + core` · `routes → services + core`。

## 後果

- ✅ 依賴規則成立:`app/core` 與 `app/services` 經 grep 稽核**不向外 import**;反向邊歸零。
- ✅ 換 transport / LLM 供應商 / 持久化 = 換 `app/adapters/` 一個檔,內層與應用層不動。
- ✅ 全程行為不變:每個 task 後 `uv run --group dev pytest -q` = **86 passed, 61 skipped**。
- 📌 tag:`phase3a-api-hexagonal`。

## 已知後續(本 ADR 範圍外)

- **domain 抽取**:`compute_completion` 等純領域邏輯暫留 `app/adapters/persistence.py`(與用它的 `DocRepo` 同檔);未來可抽到 `app/core/domain`(原計畫 T4,已延後)。
- **`tracing` 位置**:`app/adapters/llm_openrouter.py` 仍 `from app.graph_v3.tracing import get_tracer`(adapter→傳遞層的唯一容忍引用,OTel span helper)。若要純化,可把 `tracing` 移到 `app/core/`。
- **套件改名** `app → caliburn_api`(`pyproject.toml` 已註記):純機械改動,獨立進行。
