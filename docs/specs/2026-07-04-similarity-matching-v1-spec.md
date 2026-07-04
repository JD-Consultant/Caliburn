# 相似比對(similarity matching)v1 — 設計 spec

> **類型**:設計 spec(已與維護者逐段確認,2026-07-04)。
> **研究依據**:[`2026-07-02-multi-ocs-candidate-dedup-research.md`](2026-07-02-multi-ocs-candidate-dedup-research.md)
> (五輪;門檻與灰區體積皆有實驗出處)。**決策**:ADR 0022。
> **一句話**:現有系統一個都不動;indexer 多一個 endpoint,api 組完知識包後多打一通電話,
> web 多畫幾個徽章。非破壞性——**不刪任何項目**。

## 0. 定位、範圍、非目標

- **病兩種,處置兩種**:(1) 真重複(同義異字,如「團隊合作↔團隊意識」0.93)→ 收成群、
  顯示代表、可展開;(2) 相似但不同(「製程品質巡檢↔製程品質控管」)→ 不合併,標「相似」
  徽章 + 差異並排,由人判斷。機器永遠不裁決灰區(實驗:任務層真重複與相關任務分數帶重疊)。
- **v1 範圍**:indexer `POST /items:match`(kind 通用)+ 校準腳本 + api 搬運掛載 +
  web 兩個表面(態度池收合、任務勾選相似徽章)。
- **非目標(v1)**:reranker(升級槽,見 §10)、K/S/O/P/units 表面接線(校準先跑)、
  SaaS/多租戶語料分區(`sources` 欄位已容納,零預埋)、快取、LLM 消費(未來訪談引擎
  拿同一 endpoint 當 tool,零改動)。
- **未來消費者**:LLM 訪談引擎(ADR 0020)以灰區對產生鑑別提問——工具是確定性契約,
  LLM 是上層消費者(Anthropic 工具設計順序)。

## 1. 契約(`packages/indexer-contract`;rubric row 3,ADR 0010 機制沿用)

### Request — `POST /items:match`

```jsonc
{
  "kind": "attitude",            // task|output|indicator|knowledge|skill|attitude|unit
  "items": [                     // ≤500,超過 → 413
    { "id": "團隊合作:積極參與…",     // 池 key(pack 裡 key = 文字本身)
      "text": "團隊合作:積極參與…",   // 比對用文字
      "sources": ["MQM2141-001v4"] }  // 來源基準(可多個——pack row 跨來源合併過)
  ]
}
```

### Response

```jsonc
{
  "groups": [                    // 真重複群(≥θ_high)
    { "medoid": "團隊合作:積極參與…",          // 幾何代表(群內平均相似度最高)
      "members": [ { "id": "...", "score": 1.0 }, { "id": "...", "score": 0.93 } ] }
  ],
  "possible_matches": [          // 灰區對([θ_low, θ_high))
    { "a": "...", "b": "...", "score": 0.72 }
  ],
  "config": { "kind": "attitude", "theta_high": 0.9, "theta_low": 0.7, "model": "bge-m3" }
}                                // config 供重現(對齊 ADR 0009 版本紀律);distinct 不回傳
```

## 2. indexer 內部管線(六步直線,無狀態、不碰 DB)

```
⓪ 驗證      items ≤500(413)、kind 在表(422)
① 清洗      剝【T*】【註N】;CJK 字間空白刪、拉丁 token 間保留單一空格;trim
② 同字收斂  key = NFKC(清洗後文字);同 key 合併(pack 已做原字串去重,此步防禦性)
③ 嵌入      唯一文字一批 → embedder /embed(dense-only)——唯一 I/O、唯一失敗點
④ 兩兩打分  sources 有交集的對跳過(同基準=編輯意圖刻意分開);其餘 cosine
⑤ 分帶      per-kind {θ_high, θ_low} 查表 → 自動群桶 / 灰區桶 / 丟棄
⑥ 分群      貪婪星型:對按(分數降序、id 升序)決定論處理;成員與中心直連 ≥θ_high
            為硬條件(SKOS closeMatch 非遞移紅線——A≈B≈C 不得鏈成群);算 medoid;
            ②合併的同字條目展開回 members
```

- **⓪①②④⑤⑥全純函式**(僅③有 I/O):同輸入必同輸出;單測餵假分數矩陣即可,不需 GPU。
- **顯示文字永不變**:①②只產比對 key;回應引用一律原 id。
- **不抄 SemDeDup 的代表選法**(它留離中心最遠者——目標是訓練資料多樣性;我們要可讀代表)。

### 門檻(indexer settings;實驗出處見研究 §9.4)

| kind | θ_high | θ_low | 依據 |
|---|---|---|---|
| attitude | 0.90 | 0.70 | 斷崖分布三次驗證(0.986 → 0.72);灰區 0–5 對 |
| task | 0.95 | **0.80** | 真重複全在 0.83+;0.70 起算灰區 24–39 對=噪音,0.80 後 5–10 對 |
| knowledge / skill | 0.85 | 0.65 | 校準用;**v1 不接表面**(skill 灰區 116–186 對,見 §10) |
| unit | 0.95 | 0.80 | 暫比照 task;**未經實驗**,校準腳本先跑、乾淨才接線 |

改門檻 = 改 settings + 跑校準腳本留紀錄(進 `docs/specs/`),不改碼。
**絕對門檻不可移植**(各向異性,EMNLP 2020):數字只對「本池 × bge-m3」有效。

## 3. api 整合(純搬運,~30 行)

`get_knowledge_pack`(documents.py)在 `build_pack` 之後:

1. 把態度池/任務池 rows 映射成 items(id=text=池 key;sources:態度池取 srcs 的
   ocs_code、任務池從 URN `ocs:{ocs_code}:T:{code}` 取 ocs_code)。
2. `KnowledgeClient` 加 `match(kind, items)` 方法;兩 kind **並行**呼叫。
3. 成功 → 原樣掛 `pack["similarity"] = {"attitude": resp, "task": resp}`;
   任一失敗 → 該 kind 不掛(**enrichment 語意**,ADR 0018;不動 `meta.partial`
   ——那是池本體的旗標)。api **不拆包、不選代表、不改池**。

## 4. web 整合(pack.ts 純函式 + 兩個小 UI)

### 型別(全 optional、additive;文件 OcsDocument 零變動)

```ts
KnowledgePack.similarity?: { attitude?: MatchResult; task?: MatchResult }
OptionItem.variants?: OptionItem[]                       // 群成員(收合展示)
TaskRowVM.similarTo?: { name: string; score: number }[]  // 灰區對
```

### 鐵律:選擇邏輯跑在平選項上,分群只是 render 顯示變換

`primaryDefaults` / 首開自動套 / 勾選狀態 / 寫入文件身分——**既有碼路一行不改**,
操作對象永遠是平的成員 OptionItem。新純函式放在選擇邏輯**之後**:

- `groupedValueOptions(options, match?, primaryCode)` — 把平選項折疊成顯示列;
  **survivorship 在此**(代表 = 主基準成員優先 → 文字最長,決定論 tie-break)。
  收合列**就是代表成員本人**(群無可選身分);群列 checked = 任一成員 checked,
  展開顯示勾的是哪個變體、可改選/加選。
- `taskRowsWithSimilar(pack, match?)` — TaskRowVM 加 similarTo;徽章點開並排全文+來源,
  **不自動勾、不合併、不擋**。
- `match` 為 undefined → 兩函式原樣返回,行為與現狀逐位元相同(降級 = 一行 if)。

### 湧現不變量(規則保證,非防禦碼)

- **A**:④的來源不相交規則 ⇒ 一群內每基準最多一條 ⇒ 自動勾選不可能勾雙。
- **B**:survivorship 主基準優先 ⇒ 主基準成員在群內必為代表 ⇒ 首開自動套勾到的
  就是主基準身分。主基準清空(`clearPrimaryBasis`)→ 自動套本就不跑(`isOfficialBasis`)。

## 5. 錯誤處理與限制

| 情況 | 行為 |
|---|---|
| embedder 掛/超時 | indexer 回錯 → api 不掛該 kind → web 當沒這功能(池原樣) |
| items > 500 | indexer 413(n² 上限保護) |
| kind 不認得 | indexer 422 |
| 池 < 2 條 | 直接回空 groups/pairs(不打 embedder) |

## 6. 測試策略

- **indexer 單測**(假分數矩陣,無 GPU):分帶邊界、星型紅線(A≈B≈C 鏈不得成群;
  成員-中心直連硬條件)、決定論(同輸入同輸出、tie-break)、medoid、同字收斂展開。
- **前處理 golden**:【T1.1】/【註3】/CJK 斷行空白/全半形 進出對照。
- **web vitest**(pack.ts,沿用 field-identity 模式):
  1. 群含主基準成員 + 首開自動套 → 恰好主基準那條被勾;
  2. 群不含主基準成員 → 自動套零動作;
  3. 展開加勾第二變體 → 文件兩條、各自身分(合法);
  4. 自動勾選重按 → 冪等;
  5. 主基準清空 → 分群照常顯示、自動套不跑;
  6. survivorship:主基準在→必為代表;不在→文字最長。
- **整合測試**(需 embedder):態度層「團隊合作↔團隊意識 → 同群」characterization。
- **校準腳本**(Task 0,scratchpad 雛形進 repo):輸出 per-kind 分布 + 斷崖位置 +
  灰區對數;units 一起跑。輸出存 `docs/specs/` 當校準紀錄。

## 7. 升級槽(一行註記,不預建)

- **reranker(bge-reranker-v2-m3)**:已實測可行(4060 同容器共存、權重在 volume)且
  鑑別力已知(底部大掃除強、中段一樣被騙 → 只當灰區過濾/排序器,永不合併)。
  **觸發條件:K/S 混池表面上線前必開**,或校準顯示徽章噪音高。屆時 embedder 加
  `/rerank` + indexer 灰區補打分。
- 其餘:sparse 混合、mean-centering、Qdrant payload cluster_id 下沉、人工確認對持久化
  (SKOS exactMatch/closeMatch)——均先不做。

## 8. 文檔更新義務(同 commit)

- [`docs/design/editor-knowledge-pack.md`](../design/editor-knowledge-pack.md):
  similarity 掛載點、web 顯示變換鐵律、不變量 A/B。
- `apps/ocs-indexer/README.md`(items:match 端點面)· `apps/web/README.md`(分群顯示)·
  `apps/api/README.md`(similarity 掛載)。
- ADR 索引(0022)。
