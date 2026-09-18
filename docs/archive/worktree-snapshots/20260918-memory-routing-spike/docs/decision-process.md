# Caliburn Decision-to-Product 流程

- 狀態：**Accepted process；2026-09-03 經 Product Owner 核准**
- 用途：讓研究與討論可停止、可追溯，並確實轉成可驗證產品
- 現行狀態入口：[`current-decisions.md`](current-decisions.md)
- 導入紀錄：[`plans/2026-09-03-decision-to-product-governance.md`](plans/2026-09-03-decision-to-product-governance.md)

## 1. 為什麼需要這份流程

Caliburn 的研究範圍很大，長對話與多份研究稿容易同時留下「舊候選、後來修正、暫時同意、施工計畫」等不同狀態。問題不是缺少資料，而是缺少一個能回答以下問題的單一入口：

1. 現在正在決定什麼？
2. 哪些已經決定，決策效力到哪一層？
3. 哪些只是官方事實、推論、候選或歷史？
4. 什麼條件下停止研究、開始驗證或施工？
5. 新證據何時足以重開舊決策？

本流程不要求所有問題一開始就有答案，也不把研究簡化成草率決策。它要求每個問題有明確 stage、輸出與退出條件，避免長文、聊天或計畫在沒有正式效力時被誤當成 production 指令。

## 2. 文件與 authority 的單一責任

| Artifact | 回答的問題 | 可以做什麼 | 不可以做什麼 |
|---|---|---|---|
| Product North Star | 為誰解決什麼問題、最終成果是什麼 | 約束所有方案與驗收 | 指定 framework、資料表或類別 |
| [`current-decisions.md`](current-decisions.md) | 現在有效、未決、暫停與下一步是什麼 | 作為第一閱讀入口與路由表 | 靜默推翻 Accepted ADR 或現行 code |
| `docs/specs/` research／design | 官方事實、診斷、選項、推論與細部設計 | 保存完整證據與候選 | 單獨授權 production 施工 |
| `docs/adr/` | 為什麼採用重大、難逆的架構決策 | 形成 Accepted production authority | Accepted 後直接改寫；翻案必須 successor |
| `docs/plans/` | 已核准設計如何分段施工與驗證 | 指導實作者逐 task 交付 | 自行補產品語意或改架構決策 |
| `docs/design/`／app README | production 現在實際如何運作 | 描述 current code seam 與不變量 | 保留已退役候選作現行流程 |
| Chat／review comments | 討論、提問與回饋 | 促成決策 | 成為唯一、長期有效的決策紀錄 |

`current-decisions.md` 是**狀態與閱讀路由的單一入口**，不是另一套架構 authority。若 Working Decision 與 Accepted ADR／現行 code 衝突，它只能觸發 successor ADR 與後續施工，不能直接讓 production 改變。

## 3. Decision-to-Product gates

### G0：產品目的

先寫清楚：

- 使用者與真實問題；
- 使用者最後看到的成果；
- 成功情境與重要失敗；
- 本輪不處理的範圍。

這一層不放 framework 名稱或既有元件名稱。Amazon 的 Working Backwards 先從客戶問題與最終體驗倒推，在開發前用精簡文件對齊價值與關鍵問題；Caliburn 採用相同的 outcome-first 原則，而不是照抄 PR/FAQ 格式。

**退出條件：** Product Owner 確認問題、成果與不做事項。

### G1：建立單一決策題

每個阻塞決策取得穩定 ID，例如 `MEM-Q001`。決策題必須包含：

- 一句可回答的問題；
- 為什麼現在需要決定；
- 它阻塞哪個產品效果或下一個 gate；
- 已有決策與不得偷翻案的邊界；
- 哪些鄰近問題放入 parking lot。

一輪可以補齊同一問題的必要上下文，但不能同時偷偷決定另一個產品語意。

**退出條件：** 問題能以「採用／不採用／選 A、B 或 C／需要哪個實驗」回答。

### G2：官方證據與選項

每個重要主張必須標成以下其中一種：

1. **Official fact**：官方直接公開的能力、限制或契約；
2. **Inference**：由一項或多項事實推得，必須明說不是官方原句；
3. **Caliburn mapping**：針對本產品目的做的映射或取捨；
4. **Unknown**：公開資料不能證明、且可能需要 spike。

LLM／agent 技術優先查 OpenAI、Anthropic 與所選 framework 的官方資料；其他大廠官方資料可用來交叉驗證共同做法。產品／工程治理則使用真正公開該流程的 Amazon／AWS、Microsoft、Google 資料，不能把未公開的 OpenAI／Anthropic 內部流程當成事實。

研究不是以「看過多少網頁」結束。以下全部成立即可停止廣泛搜尋：

- 所有會改變方案的主張都有直接來源或明確標成 unknown；
- 主要來源間的矛盾已列出，不被摘要掩蓋；
- 新增來源已不再產生新的決策分支；
- 剩餘不確定性可以由最小實驗回答，或不影響本輪選擇。

**退出條件：** 最多提出三個實質不同方案，依產品效果、功能完整性、錯誤風險、成本、複雜度與可逆性比較，並給出一個建議。

### G3：Owner 決策

Product Owner 的裁決必須在同一工作段落內寫入 `current-decisions.md`，不能只留在聊天。狀態分為：

- `WORKING`：可供後續研究與設計使用；翻案前有約束力，但不越過既有 production authority；
- `ACCEPTED`：已有 Accepted ADR 或等效 production authority；
- `OPEN`：尚未決定；
- `PAUSED`：證據、方向或前置決策不足，禁止往下施工；
- `PARKED`：目前不阻塞；只有指定 trigger 成立才重開；
- `SUPERSEDED`：已由另一個具 ID 的決策取代。

**退出條件：** 記錄決定、理由、效力範圍、來源、重開條件、supersedes 關係與下一個 gate。

### G4：可驗證設計

設計只能從 G0–G3 的有效決策推導，至少寫清楚：

- 正常資料流；
- authority 與 framework 責任；
- 錯誤、恢復與成本邊界；
- 代表性產品情境；
- 可觀察的 pass／fail；
- 明確不做事項。

Google 的 review guidance 建議先看變更是否合理及主要設計，再審細節；Caliburn design review 同樣先做 North Star／authority／data flow gate，通過後才看 schema、函式與 UI 細節。

**退出條件：** Reviewer 能只靠設計與引用回答「做成什麼、為什麼、如何證偽」，且沒有尚未交給 Owner 的產品選擇。

### G5：必要時做 isolated spike

Spike 只驗證官方資料不能回答、而且會改變選擇的假設。每個 spike 必須列出：

- 假設；
- 最便宜的可信測法；
- pass／stop 門檻；
- 成本上限；
- 明確不接 production。

若文件與既有測試已足以回答，不做 spike。Spike 成功也只形成選擇證據；要進 production 仍須 G6。

**退出條件：** 假設被支持、推翻或證明無法用此測法判斷，結果回寫原 decision ID。

### G6：正式化

- 重大、跨 seam、難逆、改 authority／framework／契約的決策：Proposed ADR → review → Accepted／Rejected；
- 小而可逆的產品或實作選擇：保留在決策表與核准設計，不濫開 ADR；
- Accepted／Rejected ADR 保持 immutable；翻案另開 successor 並雙向連結。

AWS 與 Microsoft 都將 ADR 視為帶狀態的 decision log，要求保存 context、decision、consequences；Accepted 後以新 ADR supersede，而不是改掉歷史。

**退出條件：** production authority、current decision register、設計狀態與文檔索引一致。

### G7：小型垂直施工

每個 task 必須：

- 引用它實現的 decision ID 與 spec 段落；
- 交付一個可獨立理解、測試、審核與回滾的效果；
- 同步測試及受影響的 current design；
- 完成後做一次 North Star／decision drift check。

Google 建議 small、self-contained changes，因為更容易完整審核、較少漏看、返工與回滾成本也較低。Caliburn 以**產品效果切片**，不是為了縮行數把一個行為任意拆散。

**退出條件：** task tests 通過、review 無未處理 finding、決策追溯完整。

### G8：產品驗收與收尾

最後驗證代表性使用者情境，而不只驗證函式：

- 產品效果是否成立；
- 失敗是否可理解與可恢復；
- 成本與延遲是否在核准界線；
- current design／ADR／register 是否與實作一致；
- 未完成項目是否明確 parked，而不是藏在聊天。

Merge、push、PR 與 cleanup 仍依 repo 規則分開授權。

## 4. 防止重複與無限討論的規則

### 4.1 每輪 preflight

重大研究、設計、review 或施工前，必須先輸出並核對：

```text
Topic ID:
Current stage:
Binding decisions:
This turn's only blocking question:
Already reviewed evidence:
Out of scope / parking lot:
```

找不到目前狀態時，先補 `current-decisions.md`，不能靠記憶猜測。

### 4.2 每輪 closure

每輪結束必須寫回：

```text
Decision / finding:
Status:
Why:
Sources:
Affected artifacts:
Reopen trigger:
Next gate:
```

沒有寫回就不算已形成 durable decision。

### 4.3 重開條件

只有以下事件可以重開 `WORKING` 或 `ACCEPTED` 決策：

1. Product Owner 改變產品目的或限制；
2. 新的官方事實直接推翻原依據；
3. Spike、測試或 production evidence 證明原假設不成立；
4. 發現與另一項有效決策、現行 code 或 authority 衝突。

單純找到另一個名詞、偏好不同、或新增不會改變決策的資料，只能補充佐證。Accepted 架構仍須 successor ADR 才能改 production。

### 4.4 不再廣泛研究的判斷

當 unknown 已能被一個 bounded spike 回答，就停止再找更多同類文章。當 remaining unknown 不影響選擇，就移入 parking lot。不能用「可能還有更好的資料」讓 G2 永遠不結束。

### 4.5 Reviewer finding 格式

每項 finding 必須有：`ID／severity／位置／違反的 decision 或官方契約／產品影響／要求／狀態`。沒有指出產品、決策、契約或測試影響的意見，標成 non-blocking，不得無限阻擋。

## 5. 角色與責任

| 角色 | 負責 | 不負責 |
|---|---|---|
| Product Owner | 產品語意、重大取捨、成本／風險接受、翻案 | framework 細節與可由官方契約直接回答的問題 |
| Researcher／Designer | 查官方資料、分清事實與推論、提出選項、寫回決策 | 靜默替 Owner 選產品行為 |
| Reviewer | 先審方向，再審設計與實作；用 finding ID 收斂 | 重新發明未進決策表的新需求 |
| Implementer | 依有效決策、spec 與 plan 施工、測試、回報偏差 | 從聊天或歷史研究猜最新需求 |

如果可逆、局部且 framework 已有明確預設，Researcher／Implementer 可採成熟預設並記錄；如果選項會改變員工體驗、資料 authority、成本級別、不可逆資料或跨 seam 契約，必須回到 Owner gate。

## 6. 官方方法來源與適用邊界

- [Amazon／AWS Product Management：Working Backwards](https://aws.amazon.com/executive-insights/content/product-management-at-amazon/) — 支持先從客戶、問題與最終體驗倒推，開發前對齊核心價值與關鍵問題；Caliburn 不照抄其內部模板。
- [AWS Prescriptive Guidance：ADR process](https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html) — 支持 decision log、owner、Proposed／Accepted／Rejected lifecycle、Accepted immutable 與 successor supersede。
- [Microsoft Azure Well-Architected：Maintain an ADR](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record) — 支持 single source of truth、append-only accepted records、context／options／trade-offs／confidence／status，並直接指出未記錄決策會造成重複爭論。
- [Google Engineering Practices：Navigating a change](https://google.github.io/eng-practices/review/reviewer/navigate.html) — 支持先審核變更是否合理與主要設計，避免先投入大量細節後才發現方向錯誤。
- [Google Engineering Practices：Small changes](https://google.github.io/eng-practices/review/developer/small-cls.html) — 支持 self-contained small changes、同切片測試、較完整 review 與較低返工成本。

以上是公開流程的直接依據；「Current Decision Register 欄位、preflight／closure 格式、parking lot 與 gate 命名」是 Caliburn 為解決現有文檔失控而採用的輕量映射，不宣稱是任何一家公司的逐字內部流程。
