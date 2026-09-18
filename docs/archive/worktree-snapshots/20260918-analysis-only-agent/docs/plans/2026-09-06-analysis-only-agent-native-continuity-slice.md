# Q019 第一切片：原生訊息延續接線 Implementation Plan

> For agentic workers: use `superpowers:executing-plans` for this tightly coupled compatibility slice; use test-driven development and review before completion. Do not execute the entire product design as if this were its implementation plan.

**Goal:** 以極小、離線、可重現的接線，確認選定框架不遺失 OpenAI Responses reasoning／phase／tools／compaction；不測模型聰明程度。

**Architecture:** 全新 Python package，只有原生模型配置與 request-view 接點；實際 LangChain／OpenAI SDK 走 `httpx.MockTransport` 代替收費 HTTP 端。用官方 serializer 驗證保存後的訊息可再送出。所有 fixture 都是合成內容，不讀金鑰、訪談或既有 App。

**Tech Stack:** Python 3.12、uv；PyPI 2026-09-06 查得穩定版本：langchain 1.4.0、langchain-openai 1.6.0、langgraph 1.2.11、langgraph-checkpoint 4.2.0、openai 3.8.0、httpx 0.28.1、pytest 9.1.1。先解析相容性並產 lockfile；不能解析則先記錄依賴限制，不偷偷改成私有版。這不是每個 dependency 都必須放進 production。

**Spec:** [Q019 總覽](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-design.md)、[Runtime §3–4](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-runtime-design.md)、[驗收／停止條件](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-design-review.md)。主 checkout `S:/caliburn/docs` 持有最新設計；新 worktree 從乾淨 HEAD 建立，不能把其舊 register 當最新設計。

## Global Constraints

- User 已批准繼續隔離開發；本切片不改 `apps/`、舊環境、資料庫、production ADR，不 push／merge。
- 新位置：`S:/caliburn/.worktrees/analysis-only-agent/experiments/analysis-agent`，分支 `codex/analysis-only-agent`。主 checkout 只更新文件。
- 不實作 JD、B/C Memory、Web、排程或新來源 store；後續各段另寫小計畫。
- 不用 `.text` 取代完整 message、不解碼私有 reasoning、不用 generic summary 冒充原生延續。
- 配置使用 `store=False`、Responses、`reasoning.context=all_turns`、medium、禁止 parallel tool calls；不混 `previous_response_id`。測試 model 字串是合成配置，不證明帳戶有該模型。
- 只 mock HTTP；不 mock adapter、訊息轉換、serializer。fixture 使用官方 response items schema；保存／重送行為斷言不得只檢查 mock 被呼叫。
- 使用公開 API；adapter 若遺失必要原生資料，記錄精確 wire 差異並暫停該路線，不先寫 private converter patch。
- 無付費呼叫。加密 sentinel 只測位元內容保存，不代表服務端接受或真實推理效果。

## Task 1：配置與原生往返（本輪唯一施工段）

**Files**（相對上述新 package）：

- Create: `pyproject.toml`、`uv.lock`、`.gitignore`
- Create: `src/analysis_agent/__init__.py`、`src/analysis_agent/provider.py`
- Create: `tests/test_native_continuity.py`
- Create: `README.md`（執行方式、已完成與未證明）
- 主 checkout Create: `docs/specs/2026-09-06-analysis-only-agent-native-continuity-results.md`

### 步驟與介面

- [x] 建立獨立 pyproject／lock；不執行舊 monorepo setup。先檢查鎖定套件的公開 OpenAI item schema 與 adapter 參數。
- [x] 先寫 consumer test。配置入口為 `build_model(*, model: str, api_key: str, http_client: httpx.Client, compact_threshold: int | None = None) -> ChatOpenAI`；HTTP fixture 返回帶 opaque reasoning、assistant phase、function call 的實際 Responses 形狀。threshold 沿官方參數，無通用預設。
- [x] RED：先提供明確缺少必要配置的最小入口，觀察 wire payload 缺 `store=False`／`reasoning.context` 等的斷言失敗；不是把 ImportError 當產品 bug。然後用官方公開參數完成最小 builder。
- [x] GREEN：收到 reasoning／工具呼叫後，加入匹配 ToolMessage，再次呼叫模型；確認 outbound `input` 仍帶原 opaque 字串、正確 call_id／順序與 phase。禁止只取 text 再傳。
- [x] 保存：透過官方 `JsonPlusSerializer.dumps_typed/loads_typed` round-trip 後再送下一回合；確認原始對話與 native items 均可重送。這只驗序列化，不冒稱 PostgreSQL 重啟已驗。
- [x] Compaction：合成官方 compaction output；確認 native item 與其後 output 可保存重送。若需要自訂 request view，先寫不改 canonical 的測試，再用公開 content block 形成視圖；官方規則不清或 adapter 無法保留就停止並記錄。
- [x] 清楚分開 configured all_turns 與 response effective context 可見性；缺 metadata 不以模型自我報告補足。報告列出 live smoke 後續要驗什麼。
- [x] 替代路線 gate 已檢查：本段沒有必要 item 遺失，不觸發替換；無 xfail 或 private patch。後續串流／持久 Agent 若反證仍需重開。
- [x] 執行全切片測試、compile、whitespace／conflict 檢查；8 項通過，compiler exit 0。結果持有於[驗證紀錄](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-native-continuity-results.md)。
- [x] 完成獨立 code review：無 Critical／Important，准許離線切片本地 commit／tag；一項非阻擋測試補強已列下一段。這不是整個 analysis-only app 已完成。

### 手工可判讀的期待例子

```text
模型 output: reasoning(encrypted_content="opaque-test-1"), function_call(call_id="call_case")
工具 result: call_id="call_case", output="A 網站使用單次付款"
下一次 request: reasoning + 同一 function_call + 同一 function_call_output
下一輪 user: "B 網站改採月租"
保存再載入後: A 問答仍保留；原生 reasoning 仍在；B 訊息只新增一次
```

會讓測試失敗的具體回歸：builder 回到 chat-completions、遺失 reasoning block、改寫 encrypted 字串、丟 phase／tool call identity、compaction 直接刪 canonical。測試不斷言官方內部 private helper 的實作。

**Commands**（新 package 工作目錄）：

```text
uv sync --locked
uv run --no-sync pytest -q
uv run --no-sync python -m compileall -q src tests
git diff --check
```

## Review／進度記錄

| 檢查 | 結果／邊界 |
|---|---|
| Spec vs task | 只驗 Q019-F01/F03/F10 的離線接點，未越界建 Memory 或 product |
| 介面共享 | 單一 task，tests 消費 provider 公開 builder；fixture 不進 production |
| 原文保存 | serializer 能力檢查不是 DB 持久／原文 reader 交付，需明列 |
| 框架選型 | 最新穩定 pin 先解析；失敗後有停止條件，不以私有 API 過關 |
| 費用 | 離線 HTTP transport；不讀 `.env`，無付費模型呼叫 |

執行紀錄集中在結果稿，這裡只更新 checkbox／gate，不再追加另一份研究長文。

## Sources

- [OpenAI preserve reasoning](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-across-calls)：完整 output items、effective mode、opaque state 的適用範圍。
- [OpenAI compaction](https://developers.openai.com/api/docs/guides/compaction)：原生有效視窗不是刪本地來源政策。
- [ChatOpenAI](https://docs.langchain.com/oss/python/integrations/chat/openai)：公開 Responses／reasoning 接點；實際鎖版 source 要再比對。
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)：serializer 與 checkpoint 責任；本段沒有完成 DB durability。
- [HTTPX transports](https://www.python-httpx.org/advanced/transports/#mock-transports)：只替換 HTTP 邊界，真正 adapter／SDK 仍執行。
- [PyPI langchain-openai](https://pypi.org/project/langchain-openai/)、[OpenAI SDK](https://pypi.org/project/openai/)：本輪版本來源；相容結果以 lockfile 為準。
