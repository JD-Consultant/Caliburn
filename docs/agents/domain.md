# Domain docs

本 repo 採 multi-context domain docs。開始探索或修改某個 bounded context 前，先讀根目錄
`CONTEXT-MAP.md`、相關 `CONTEXT.md`，以及 `docs/adr/` 中適用的 ADR；檔案尚未存在時直接繼續，等
`domain-modeling` 實際確立詞彙時再建立，不預先填充。

## Context 配置

| Bounded context | Domain glossary | 使用範圍 |
|---|---|---|
| PDF 解析 | `apps/pdf-to-json/CONTEXT.md` | OCS PDF 到結構化 JSON |
| OCS 檢索 | `apps/ocs-indexer/CONTEXT.md` | 索引、檢索、Qdrant 與 embedding |
| JD 著作 | `apps/api/CONTEXT.md` | API 與 Web 共用的職務分析、訪談及 JD 著作語彙 |

根目錄 `CONTEXT-MAP.md` 在第一份 context glossary 建立時一併建立，負責把工作範圍導向上述 glossary。
系統級與跨 context 的決策留在 `docs/adr/`。

## 使用規則

- 使用 glossary 已定義的 canonical term，不任意改用同義詞。
- 找不到術語時，先判斷是否用了錯誤語言；若確為缺口，交由 `domain-modeling` 處理。
- 任何輸出若與既有 ADR 衝突，必須指出衝突與重新開啟決策的理由，不得靜默覆蓋。
- `apps/web` 共用 JD 著作 context，不建立重複 glossary。
