# ADR 0010 — 契約 #2(indexer 查詢 API)用共用 pydantic 套件,非 codegen/Pact

- **狀態**:Accepted（2026-06-28;契約 #2)。

## 脈絡

indexer 查詢 API(`apps/ocs-indexer` producer ⇄ `apps/api` consumer 的 HTTP 縫)的線格式被**手寫維護兩份**:producer = `ocs-indexer/.../api/schemas.py`(FastAPI `response_model`),consumer = `api/.../core/knowledge_dto.py`(`KnowledgePort` 回傳 + `HttpIndexerClient` 解析)。兩份各自演化;consumer 的 `extra="ignore"` 還會**靜默吞掉新欄位、把改名欄位變預設值** —— 無建置期訊號。與契約 #1 修掉的 OCS 文件飄移同一類問題。

**關鍵差異(決定做法的力學)**:這條縫是 **Python↔Python、單一 producer、單一 consumer**;web 前端不直連 indexer(它連 api,api 連 indexer)。因此契約 #1 採 JSON-Schema 的理由(TS/web 消費者、語言中立、OCS 文件是真實世界標準)在 #2 **都不存在**。

權威依據:FastAPI 官方(OpenAPI-native、可由 spec 生 client);Speakeasy/TotalShiftLeft 契約測試(**內部服務用 schema-first**,Pact 消費者驅動是給對外 API、此處過重);Malt 案例(code-first 兩端手寫 → 同步問題)。研究紀錄:`docs/specs/2026-06-28-contract-2-indexer-query-api-research.md`。

## 決定

採 **Option B:共用 pydantic 套件 `packages/indexer-contract`**(純 pydantic,per-app editable **path 依賴**,同 `ocs-contract`/ADR 0005 的散布方式)。

- 套件 `indexer_contract.models` 持有**全部查詢 API 線模型**(requests + responses)。
- producer:`ocs-indexer/api/schemas.py` 改成 **re-export** 套件(`routes.py` 不動)。
- consumer:`api/core/knowledge_dto.py` 改成 **re-export** 套件(`core/ports`、adapters、services、~16 個測試的 import 路徑不動)。
- 兩端因此**共用同一個 class 物件**(已用 `A is B` 斷言驗證)→ **飄移結構上不可能**,無需 codegen、無需 schema-diff CI。
- re-export shim 沿用 Phase 2 `ocs-contract` 既有作法(定義只在套件、shim 僅保 import 路徑相容)。

**為何不用 #1 的 JSON-Schema + codegen**:沒有非 Python 消費者撐語言中立成本,對內部縫過度工程。**為何不用 Pact/CDC**:單一內部消費者,schema 即足夠;Pact 是對外/隱性多消費者才需要。

## 後果

- ✅ producer/consumer 線格式不可能再各自飄移(同一份 class);新增欄位兩端同時看到。
- ✅ 零 codegen/零 CI 機制,複雜度低於契約 #1;沿用既有 path-dep 模式。
- ✅ 行為相容:兩套件套件測試綠(ocs-indexer 41、api 86/61 skip);OpenAPI 仍正常產生。
- ⚠️ 兩端綁同一 pydantic 主版本(本就因 `ocs-contract` 如此;兩者皆 pydantic v2)。
- 📌 升級路徑:**出現非 Python 消費者時**才升級成 OpenAPI/JSON-Schema 產出物(Option A/C);tag `contract2-indexer-api`。

## 已知後續(本 ADR 範圍外)
契約 #3(api/web 著作文件)另開研究/plan;此處未把 producer-only 端點(batchGet/findSimilar/stats)從 api 移除(api 目前不消費,留在套件供 producer 用)。
