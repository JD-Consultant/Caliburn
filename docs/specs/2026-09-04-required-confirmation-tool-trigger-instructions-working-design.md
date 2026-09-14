# 必要確認 Tool 的觸發指令與可用性（Working Design）

- 日期：2026-09-04
- Topic ID：`LLM-Q010`
- 階段：PAUSED；父前提由 `LLM-Q011` 重驗中
- 父決策：`LLM-Q006`～`LLM-Q009`
- 效力：只決定模型如何辨識「何時用／何時不用」confirmation Tool；不授權 production prompt、schema、UI、provider pin、測試或實作

> 本文保留為方案歷史；訪談澄清是否需要 confirmation Tool 尚未成立。Current 問題見 [`2026-09-04-conversational-question-vs-durable-interrupt-revalidation.md`](2026-09-04-conversational-question-vs-durable-interrupt-revalidation.md)。

## 1. 本輪唯一問題

confirmation Tool 的 description、主顧問 system instruction 與 Tool availability 應如何分工，才能只在真正 blocker 時 durable interrupt，避免漏呼叫，也避免把普通訪談問題都變成強制中斷？

## 2. 已固定的產品判準

依 `LLM-Q006`，只有同時符合以下四項才是 blocker：

1. 現有 conversation、Memory 與 JD 無法可靠確定答案，不能安全推測；
2. 至少存在兩個實質不同、目前都合理的解讀或選擇；
3. 猜錯會實質改變工作理解、JD 或當前 operation 的結果；
4. 當前 operation 沒有員工答案就無法安全完成。

不符合四項者是普通訪談問題：正常完成本輪，以自然語言詢問；不 durable interrupt。pending JD 審核、可稍後補充的細節、provider／Tool 錯誤也不是 confirmation blocker。

## 3. 官方事實

### F1．OpenAI：Tool 與 system prompt 都必須提供清楚的使用指令

OpenAI Function calling best practices 要求明確描述 function 目的、每個參數及輸出，並在 system prompt 說明每個 function 何時使用、何時不使用。官方也指出 examples 應用於修正常見失敗，但可能降低 reasoning model 表現；不能把 examples 當預設必要項。

OpenAI 的 `tool_choice: auto` 允許模型呼叫零個、一個或多個 Tool，也是預設模式；`required`／forced function 才會強迫 Tool call。`strict: true` 只保證呼叫符合 JSON Schema，不會判斷本輪是否真的需要 Tool。

### F2．Anthropic：Tool description 的核心是 WHEN，而不只 WHAT

Anthropic 要求 Tool description 詳細說明做什麼、何時用與何時不用、參數意義及限制，並把 description 視為 Tool 表現最重要的因素。官方 troubleshooting 更直接指出：錯選 Tool 的常見原因是 description 含糊，修正方式是用「何時使用」區分，而不只描述「做什麼」。

Anthropic 的 `tool_choice: auto` 同樣讓模型自行決定是否呼叫 Tool，也是有 Tools 時的預設。`input_examples` 適合複雜、巢狀或格式敏感 schema，且會增加 prompt tokens；不是此小型 schema 的預設要求。

### F3．LangChain：system prompt 與 Tool description 是兩個模型可見層

LangChain `create_agent` 接受 `system_prompt` 來定義 agent 行為；`@tool` 預設以 function docstring 作為模型可見的 Tool description，官方要求 description 清楚、精簡，使模型知道何時使用。這表示 framework 已提供兩個成熟位置，不需另建第三套分類格式。

### F4．不存在跨廠固定文案

OpenAI、Anthropic 與 LangChain 對責任分工有共同方向，但沒有共同的四條 blocker 文案，也沒有要求另跑一個分類模型。以下方案是把官方 primitive 映射到 Caliburn 已核准的產品判準；不能把精確 wording 冒充廠商標準。

## 4. 三個方案

| 方案 | 作法 | 優點 | 主要問題 |
|---|---|---|---|
| **A．兩層指令＋固定可見＋auto（建議）** | system instruction 用一小段固定全域規則區分普通問題與四條 blocker；Tool description 再清楚描述局部行為、何時用／不用與欄位；Tool 每輪固定可見，保持 provider 的 auto 選擇 | 同時符合 OpenAI 與 Anthropic guidance；不用額外分類模型；一個小 schema 成本低；普通回合可零 Tool call | 兩處文字必須維持同一語意，不能演變成兩套不同政策 |
| B．只靠 Tool description | 主提示不談 blocker，所有規則都放 Tool description；仍使用 auto | 最短、只有一個規則位置 | 不符合 OpenAI 明確建議在 system prompt 說明何時用／不用；顧問可能直接以普通文字問真正 blocker，造成漏 interrupt |
| C．Runtime 先分類並動態暴露／強制 Tool | 額外 classifier 判斷本輪是否可能 blocking，再隱藏、限制或強制 Tool | 理論上可減少誤呼叫 | 多一個判斷 seam、成本與延遲；classifier 本身也可能漏判，且重複主顧問已具備的語意判斷；現無證據證明必要 |

## 5. 建議 A 的責任分工

### 5.1 System instruction：只放全域決策規則

它應清楚說明：

- 普通訪談問題以自然語言詢問並正常結束本輪；
- 只有四條 blocker 條件全部成立，才呼叫 `request_employee_confirmation`；
- 不得把 pending 審核、一般缺口、可稍後回答的細節或系統錯誤當 blocker。

它不重複 Tool schema、不列 Runtime identity，也不描述 UI 欄位。

### 5.2 Tool description：放局部操作邊界

description 應以 3～4 句清楚說明：

- 此 Tool 會暫停目前 invocation，取得安全繼續所必需的一個員工決定；
- 只有四條 blocker 條件全部成立才使用；
- 普通訪談追問、可延後資訊、JD 待審變更與執行錯誤不得使用；
- 呼叫時提出一個自成一體的問題與 2～4 個真實、互斥的選項；應用程式另提供自由文字回答。

欄位 description 只解釋 `question`、`label`、`description` 的語意，不再塞入 workflow、ID 或錯誤策略。

### 5.3 Availability 與 tool choice

- 此 Tool schema 小、可能在任何實質訪談回合成為必要控制入口，因此第一版固定提供給主顧問；
- 使用 provider／LangChain 的 auto 行為，允許零次或一次必要呼叫；不可每輪 forced／required；
- 不另跑 pre-classifier，也不先用 Tool search／deferred loading 隱藏這一個小 Tool；
- 「一個 interrupt 只含一題」的 Runtime enforcement 與跨 provider parallel-call 細節留待 implementation contract，不在本題猜定參數。

### 5.4 Strict 與 examples 的邊界

- provider 支援時採 strict Tool schema，以降低錯欄位與型別錯誤；
- strict 不是 blocker classifier，不能修正過度呼叫或漏呼叫；
- 第一版不預載 input examples：本題 schema 很小，OpenAI 警告 examples 可能傷害 reasoning model，Anthropic也把 examples 定位為複雜／格式敏感輸入的補助；
- 只有代表性 characterization 顯示持續誤判，才針對該 recurring failure 加最少量正反例並重測。

## 6. 成本、效果與複雜度

- 每輪多出的固定成本只有一個小 Tool definition 與一小段 system policy；沒有額外 model invocation。
- auto 模式讓普通回合為零 Tool call；只有真正 blocker 才 interrupt／resume。
- 固定 Tool list 與穩定 tool choice 也比每輪動態改動更利於 prompt caching；Anthropic 明確指出改變 `tool_choice` 會使部分 cached message blocks 失效。
- 最大風險不是 schema 格式，而是四條條件文字漂移或情境分類不清；因此 G4 應以少量代表性正／反例檢查過度中斷與漏中斷，而不是增加第二個分類 agent。

## 7. 建議裁決

建議暫時採方案 A：一個固定可見的小型 confirmation Tool，保持 auto；system instruction 負責全域 blocker 決策，Tool description 負責局部使用邊界與輸入語意。兩者表達同一份 `LLM-Q006` 政策，不建立兩套不同規則；第一版不加 pre-classifier、不強制每輪 Tool、不預載 examples。

本裁決若通過，下一個 gate 才處理「如何以少量代表性情境驗證漏呼叫／過度呼叫，以及如何限制同一 interruption 只出現一題」；仍不直接施工。

### 7.1 G3 裁決

Product Owner 於 2026-09-04 暫時核准方案 A：system instruction 管全域 blocker 判準，Tool description 管局部使用邊界與輸入語意；一個小 Tool 固定可見並維持 auto。第一版不加 pre-classifier、不強制每輪 Tool、不預載 examples。

本裁決只升為 Working Decision，不授權 production prompt、schema 或實作。下一個 topic `LLM-Q011` 先處理 confirmation 與其他 Tool calls 的原子性，再另決定最小 characterization；避免把兩個問題混成同一輪。

## 8. 重開條件

- 代表性情境顯示真正 blocker 經常被普通文字回答；
- 普通訪談問題經常被誤中斷；
- 特定 provider 的 auto Tool selection 無法可靠支援；
- 一個 Tool 固定可見造成可量測且不可接受的成本／cache 問題；
- 官方 Tool prompting 或 LangChain API 發生實質改變。

## 9. 官方來源

### OpenAI

- [Function calling：function instructions、Tool choice 與 strict mode](https://developers.openai.com/api/docs/guides/function-calling)

### Anthropic

- [Define tools：description、input examples 與 Tool choice](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)
- [Troubleshooting tool use：以 WHEN 消除 Tool 選擇歧義](https://platform.claude.com/docs/en/agents-and-tools/tool-use/troubleshooting-tool-use)

### LangChain

- [Tools：docstring／description 與 Tool schema](https://docs.langchain.com/oss/python/langchain/tools)
- [Agents：`create_agent` 的 system prompt 與 Tools](https://docs.langchain.com/oss/python/langchain/agents)
