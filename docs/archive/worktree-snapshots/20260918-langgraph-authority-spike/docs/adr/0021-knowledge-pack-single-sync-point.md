# ADR 0021 — 知識包:選職類=唯一 knowledge 同步點;indexer 給資料、api 處理、web 讀寫

- **狀態**:Accepted(2026-07-03)。
- 研究依據:[`../specs/2026-07-03-editor-provenance-knowledge-pack-decisions.md`](../specs/2026-07-03-editor-provenance-knowledge-pack-decisions.md)
  (§1 原則、§5 設計與抓取策略研究:TanStack/Next.js/web.dev 官方 + 實測 27KB/職類)。

## 脈絡

web 對 knowledge 的取用切成四個投影端點(header-meta / task-candidates / task-catalogs /
per-task fallback),散在時間軸上逐面抓(waterfall),且投影時把來源資訊揉掉(級別/描述/NOTE
無來源可標)——與「所有資料必標來源」原則衝突。同時 per-task 快取鍵用文件位置碼,結構性編輯後
錯位(review finding A1)。官方基準是**版本化不可變**資料,選定的 2–5 個職類 gzip 後僅
~10–50KB,後續每個編輯面都必用。核心投資方向是 LLM(訪談/去重),不是網路層。

## 決定

1. **三層職責**:indexer「只給資料」(現有 3 個資源 GET,零改動);api「資料處理」
   (聚合/投影/標來源一律後端);web 只讀 knowledge + 讀寫文件。
2. **選職類 = 唯一同步點**:`PUT occupations` 後 web 背景抓一次
   `GET /job-profiles/{id}/knowledge`(每官方項已帶 `srcs: SourceRef[]`;catalogs 以 URN
   `ocs:{code}:T:{task_code}` 為鍵);此後 web 對 indexer 資料零請求。
   例外(特殊功能):目錄搜尋、`tasks:findSimilar`/去重、`/ai/*`。
3. **組裝最小化**:per-code 並行 + 單包降級 `meta.partial`(沿 ADR 0018);全包失敗才 5xx。
   **不做** HTTP 加固/server 快取/indexer 新參數(本地部署、只有 LLM API 走雲端——YAGNI,
   per-code 組裝即未來拆分縫)。
4. 既有三個投影端點過渡期保留(agent/相容),web 遷移完成後收斂。

## 後果

- ✅ 來源不再被投影揉掉:級別/描述/NOTE 的來源標記有了資料基礎(spec §1–§3);
  LLM 工具與引用共用同一 grounding 基座(URN 身分詞彙,對齊 indexer `api/urn.py`)。
- ✅ waterfall 消除(選任務/開格 0 等待,ADR 0016 模式放大);快取鍵=身分,結構性編輯不再錯位。
- ⚠️ web 資料層要遷移(五個 query 收斂為 document+knowledge);持久化 buster 需 bump。
- ⚠️ pack 形狀是 api↔web 內部 seam(契約策略:同 ADR 0016 類,不 codegen);agent 端點收斂另議。
- 📌 取代關係:ADR 0016 的批次 catalog 端點被 pack 涵蓋(0016 不翻案,其「批次+seed」原則
  由本 ADR 一般化;task-catalogs 端點依第 4 點過渡後退役)。
