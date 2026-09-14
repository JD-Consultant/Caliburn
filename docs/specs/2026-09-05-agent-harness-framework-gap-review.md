# Agent Harness 框架承接差異審核

> 日期：2026-09-05
>
> Topic：`LLM-Q015`
>
> 狀態：**G3 Owner 暫時核准方案 C；Working architecture direction；不授權 production 施工**

## 0. Preflight

```text
Topic ID:
  LLM-Q015
Current stage:
  G3 Owner decision complete：暫時核准方案 C。
Binding decisions:
  一個 provider-neutral 顧問 agent loop；每份 JD 一個長期訪談；模型／Provider 可替換；
  Skills、Memory、JD 編輯與員工審核各依自己的責任設計；不採 subagent／shell 作第一版需求；
  Conversation／Compaction A／B 只獲准做隔離 mechanism comparison，尚未選定。
This turn's only blocking question:
  已回答：以最新 stable LangChain create_agent 作根，按責任組裝必要的官方元件；
  不採預設完整 create_deep_agent。
Already reviewed evidence:
  OpenAI Conversation／Context／Memory 既有系統圖；framework 官方完整流程事實圖；
  Conversation／Compaction framework gap review；ADR 0060 現行 production authority。
Out of scope / parking lot:
  Memory formation、progressive-disclosure tools、live repair、background worker、JD mutation schema、
  UI、provider／model 選擇、production migration、implementation、merge、push 或 PR。
```

## 1. Harness 在本題精確指什麼

Harness 不是模型、Memory、LangGraph Store，也不是 Caliburn 的職務分析方法。它只回答：

```text
誰替一個 agent 組裝：
  model↔Tool loop
  ＋ middleware 順序
  ＋ tool visibility
  ＋ backend／checkpointer／Store 接線
  ＋ context、retry、limit、cache 等通用執行能力
```

**Official fact：**LangChain `create_agent` 是 production-ready agent loop，底層編譯成
LangGraph graph。Deep Agents 是建在相同 loop 上的 opinionated harness；
`create_deep_agent` 組裝 middleware 後，最後仍呼叫 `create_agent`。因此這不是「兩套 agent
框架」之爭，而是「由預組 harness 還是由公開元件清單負責組裝」之爭。

來源：[LangChain Agents](https://docs.langchain.com/oss/python/langchain/agents)、
[Deep Agents overview](https://docs.langchain.com/oss/python/deepagents/overview)、
[Deep Agents `create_deep_agent` source](https://github.com/langchain-ai/deepagents/blob/main/libs/deepagents/deepagents/graph.py)。

## 2. 官方完整責任分層

| 層 | 官方元件 | 實際責任 | 本題是否裁決 |
|---|---|---|---:|
| Agent framework | LangChain `create_agent` | model／Tool loop、structured output、middleware 組合 | 是 |
| Durable runtime | LangGraph | graph execution、checkpoint、Store、interrupt／resume | 否，沿用有效決策 |
| Opinionated harness | Deep Agents `create_deep_agent` | 預組 filesystem、summarization、patch、cache、skills／memory／subagent 等 | 是 |
| 公開可組合能力 | LangChain／Deep Agents middleware | 可逐項接到 `create_agent`，不必採整包 harness | 是 |
| Product policy | Caliburn Skills／Tools／authority | 要分析什麼、可改什麼、何時需員工審核 | 否 |

LangChain 官方另提供「從零組裝 Deep Agent」教學：若預設 harness 不合需求，可從
`create_agent` 開始，逐項加入 Deep Agents 的 filesystem、summarization、skills 與 subagent
middleware。這表示「stable root＋官方 Deep Agents 元件」是官方支持的組合方式，不是
Caliburn 自行發明一個 agent loop。

來源：[Build a data analysis agent from scratch](https://github.com/langchain-ai/docs/blob/main/src/oss/langchain/deep-agent-from-scratch.mdx)、
[LangChain middleware overview](https://docs.langchain.com/oss/python/langchain/middleware/overview)。

## 3. `create_deep_agent` 現在實際帶入什麼

### 3.1 最新官方公開版的組裝順序

研究基準採 2026-09-05 最新公開的 `deepagents==0.7.13` 與 upstream 官方文件／原始碼，
而不是受 Caliburn 現行 pin 限制。主 agent 的組裝順序為：

```text
SkillsMiddleware                    # 只有傳 skills= 才有
FilesystemMiddleware               # 固定 scaffolding
SubAgentMiddleware                 # 有同步 subagent 才有；預設會建立 general-purpose subagent
SummarizationMiddleware
PatchToolCallsMiddleware
AsyncSubAgentMiddleware            # 只有傳 async subagent 才有
caller middleware
profile extra middleware
provider prompt-caching middleware
MemoryMiddleware                   # 只有傳 memory= 才有
HumanInTheLoopMiddleware           # 只有設定 interrupt／permission 才有
→ LangChain create_agent(...)
```

`checkpointer`、`store`、`response_format`、`state_schema`、`context_schema` 都只是往下傳給
`create_agent`；Deep Agents 沒有另建第二個 durable runtime。

官方來源：
[Customize Deep Agents](https://docs.langchain.com/oss/python/deepagents/customization)、
[`create_deep_agent` reference](https://reference.langchain.com/python/deepagents/graph/create_deep_agent)、
[`create_deep_agent` upstream source](https://github.com/langchain-ai/deepagents/blob/main/libs/deepagents/deepagents/graph.py)、
[Deep Agents PyPI](https://pypi.org/project/deepagents/)。Caliburn 目前的 `0.7.5` 只列為未來
migration gap，不限制本稿的設計結論。

### 3.2 可以裁剪，但不是空殼

**Official fact：**目前 Deep Agents 可透過 Harness Profile：

- 停用預設 general-purpose subagent，使 `task` tool 不出現；
- 排除不用的 tools／middleware；
- 覆寫工具描述、prompt 與同名 middleware；
- 保留自訂 backend、Skills、Memory、HITL 與 response format。

但 `FilesystemMiddleware` 屬 protected scaffolding，不能從 harness stack 移除，只能隱藏
不需要的 filesystem tools。未排除的工具即使本輪不用，完整 schema 仍會進每次模型呼叫。

來源：[Deep Agents profiles](https://docs.langchain.com/oss/python/deepagents/profiles)、
[Deep Agents context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering)、
[Deep Agents subagents](https://docs.langchain.com/oss/python/deepagents/subagents)。

### 3.3 版本成熟度與文件漂移

**Official fact：**LangChain 1.x 與 LangGraph 1.x 是 stable／LTS 線；Deep Agents 尚未到 1.0，
官方列為 active-development／Beta。0.7 已移除預設 Todo middleware，官方理由是評估顯示它
增加成本與延遲、沒有提升表現。這是好的精簡方向，也證明 pre-1.0 harness defaults 仍會變動。

因此設計應以最新公開能力判斷，不因目前 repo pin 缺少新能力而降級；進入實作 gate 時再鎖定
當時最新的候選版本，並以 import／behavior canary 驗證實際 stack，防止 Beta defaults 漂移。

來源：[LangChain release policy](https://docs.langchain.com/oss/python/release-policy)、
[Versioning](https://docs.langchain.com/oss/python/versioning)、
[Deep Agents changelog](https://github.com/langchain-ai/deepagents/blob/main/libs/deepagents/CHANGELOG.md)、
[Deep Agents v0.7 release rationale](https://github.com/langchain-ai/deepagents/issues/5071)、
[Deep Agents PyPI](https://pypi.org/project/deepagents/)。

## 4. Caliburn 目前真正需要 Harness 承接的效果

這裡只用產品效果，不用舊元件名稱反推：

| 必要效果 | 框架可直接承接 | 是否需要完整 harness 才有 |
|---|---|---:|
| 單一顧問反覆呼叫 Tools 直到完成／達上限 | `create_agent` | 否 |
| 可換模型／Provider 與參數 | LangChain model binding | 否 |
| typed response、model／tool retry、call limits | LangChain middleware／response format | 否 |
| 長訪談 continuation／compaction | LangGraph＋待選 summarization mechanism | 否 |
| 按需載入職務分析 Skills | Deep Agents `SkillsMiddleware`＋受限 backend | 否 |
| 在虛擬 JD workspace 讀／增／改／刪 | Deep Agents filesystem middleware／backend primitives | 否 |
| prompt caching | provider middleware／adapter capability | 否 |
| 員工審核 AI 文件變更 | Caliburn 文件 authority；不是一般 tool-call interrupt | 否 |
| subagent、shell、通用任務規劃 | 第一版沒有產品需求 | 不應預設帶入 |

**Caliburn mapping：**目前沒有一項已核准的產品效果只能靠完整 `create_deep_agent` 才能做到；
需要的通用能力都有公開可組合元件。但 Caliburn 確實需要其中多項 Deep Agents primitives，
所以答案也不是「不用 Deep Agents」，而是要決定是否採其**根 harness 組裝器**。

## 5. 三個實質方案

### A. Deep Agents 預設 harness

直接以 `create_deep_agent` 的預設 stack 為產品根，只追加 Caliburn Tools／Skills。

**優點：**開箱功能最多，官方負責 stack 組裝。

**缺點：**預設 general-purpose subagent、filesystem 工具面與額外策略超出第一版需求；每輪長訪談
會承擔無用 tool schema／prompt／可能額外 model call。`memory=`、HITL／permissions 雖非預設
啟用，但採整包 root 也會讓這些相鄰生命週期落入同一 harness configuration surface。

**判斷：不建議。**功能多不等於產品效果更好；官方也明示簡單 agent 應考慮 `create_agent`。

### B. 高度裁剪的 Deep Agents harness

仍以 `create_deep_agent` 作根，但停用預設 subagent、明確排除不用的 tools／middleware，只保留
filesystem、skills、選定 summarization、patch、cache 與 Caliburn middleware。

**優點：**多項必要能力由 harness 統一排序與接線；新版本的 profile／tool exclusion 已使它比
舊版更可控。日後真的需要更多 Deep Agents 能力時擴充容易。

**缺點：**根 package 仍為 Beta；FilesystemMiddleware 是 protected scaffolding；需要 profile
持續抵消預設能力。版本升級可能改變 stack、prompt 或 tool surface。若裁剪後和 C 的模型可見
行為相同，B 的主要收益只剩 assembly convenience，尚無產品效果優勢。

### C. Stable `create_agent`＋選定的官方 middleware（推薦）

以 LangChain stable `create_agent` 作唯一根 loop；逐項組裝已證明必要的 LangChain／Deep Agents
公開元件，例如 filesystem backend、Skills、選定 summarization、patch-tool-call、retry、limits、
provider cache 與 Caliburn 的窄 policy middleware。

**優點：**保留所有目前必要功能與 framework reuse；模型只看到核准的工具／prompt；root API
在 stable 1.x；不需靠 exclusions 抵消不需要的預設。官方有逐項組裝教學，並非自行重寫 loop。

**缺點：**Caliburn 必須明確列出 middleware 順序與 exact version compatibility；Deep Agents
公開元件本身仍受其 pre-1.0 版本風險影響。若日後需要 harness 大部分預設能力，需重新比較 B。

## 6. 比較結論

| 評估面 | A 預設 Deep Agents | B 裁剪 Deep Agents | C stable root＋官方元件 |
|---|---|---|---|
| 目前產品效果 | 可達成 | 可達成 | 可達成 |
| 不需要的功能／模型面 | 高 | 可降至低，但需持續排除 | 最低，明確加入 |
| framework 重用 | 最高 | 高 | 高 |
| root API 成熟度 | Beta | Beta | Stable 1.x |
| provider／model 可替換 | 是 | 是 | 是 |
| 預設漂移風險 | 高 | 中 | 低；選用的 Beta 元件另鎖 pin |
| 產品專屬程式量 | 最少 | 少 | 稍多，主要是 declarative assembly |
| 已證明的效果優勢 | 無 | 尚無勝過 C 的證據 | 具備必要效果，工具面最精確 |

**Inference：**B 與 C 共用同一 `create_agent` loop，也可使用同一批 middleware。沒有證據顯示
`create_deep_agent` 這個組裝函式本身能改善職務分析品質；效果差異只會來自最後實際啟用的
prompt、tools、middleware、model 與 context。若這些相同，B 不應被當成品質更高。

**Caliburn mapping：**本案是單一顧問、固定產品工具、長期多輪訪談，不是任意通用電腦代理。
目前最合適的是 C：以 stable root 保持明確邊界，同時大量採用公開成熟／官方元件。這符合
「優先效果與功能，再看成本與程式量」；不是因為 C 程式較少，而是 B 沒有多提供目前需要且
可觀察的產品效果。

## 7. Unknown 與 stop rule

下列未知**不阻塞 G3 選擇 C**，但若 Owner 想改選 B，才值得做最小 harness-shape spike：

1. 在選定的最新版本下，B 經 profile 裁剪後的最終 tool names／schemas、system prompt fragments 與
   middleware order 是否能與 C 完全等價；
2. B 的 provider profile／prompt-cache defaults 是否會在換模型時加入非預期行為；
3. B 相較 C 是否產生可觀察的恢復、錯誤處理或功能優勢。

最小測法不需要真模型品質 eval：編譯兩個隔離 graph，輸出模型可見工具、prompt fragments、
middleware 順序與持久 owner，並以 fake model 跑一次 tool success／repair。若沒有差異，就沒有
理由僅為「整包」改用 Beta root harness。

停止廣泛搜尋：官方架構、可裁剪能力、預設 stack、成熟度與可組合替代均已有直接來源；新增
同類文件不再產生第四個方案。剩餘 unknown 可由上述 bounded spike 回答。

## 8. 建議 Owner 裁決

**推薦 C：**以 LangChain stable `create_agent` 作 Harness baseline，按產品效果逐項組合
LangChain／Deep Agents 公開 middleware 與 backend primitives；不採預設或完整
`create_deep_agent` 作根。

這項裁決若核准，表示：

- 保留一個 framework-owned model↔Tool loop，不自寫 agent loop；
- Deep Agents 的 Skills、filesystem、summarization 等公開元件仍可照責任採用；
- 每個新增 middleware 都必須對應已核准效果，不能因整包預設而自動出現在模型 Context；
- Conversation／Compaction A／B 隔離比較照原 scope 進行，不因 Harness 決策偷選 A 或 B；
- 若未來需要 subagent／shell／通用長任務 harness，或 Deep Agents 1.0 提供可證明的效果優勢，
  依 reopen trigger 比較 B，不永久排除。

這是 Working architecture direction；要改現行 Accepted ADR 0060 或 production，仍需後續
可驗證設計、必要 spike 與 successor ADR／正式施工 gate。

Product Owner 已於 2026-09-05 暫時核准方案 C。這是可經後續證據重開的 Working Decision，
不是永久排除 Deep Agents，也不是 production 施工授權。

## 9. Closure

```text
Decision / finding:
  Deep Agents 與 plain LangChain agent 共用 create_agent loop；差別是預組 stack。
  預設 harness 帶入第一版不需要的能力；高度裁剪 harness 已可行，但仍是 Beta，且尚無
  勝過「stable create_agent＋同一批公開元件」的產品效果證據。
Status:
  G3 Owner 暫時核准 C；Working architecture direction；不授權 production。
Why:
  官方來源已直接回答 harness 分層、精確 stack、可裁剪性、component composition 與成熟度；
  剩餘差異只需在 Owner 改選 B 時做 bounded harness-shape spike。
Sources:
  本稿 §1～§3 的官方連結；研究當日最新公開版本；既有 OpenAI／framework 系統圖。
Affected artifacts:
  本稿與 current decision register；不改 production、ADR、API 或 Web。
Reopen trigger:
  Deep Agents 到達 1.0；產品明確需要 subagent／shell／大部分預設 harness；或 exact-pin
  spike 證明 B 有 C 無法提供的產品效果／可靠性優勢。
Next gate:
  進入 LLM-Q016：逐責任比對 OpenAI Memory 流程與最新框架功能等價性；
  Conversation／Compaction A／B comparison 仍是獨立窄 gate。
```
