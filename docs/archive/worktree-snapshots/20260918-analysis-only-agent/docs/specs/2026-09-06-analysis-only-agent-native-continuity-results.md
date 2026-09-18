# Q019 第一切片：原生延續離線接線結果

> 2026-09-06 · **第一切片離線 gate 與獨立 code review 通過。不是完整 Agent／Memory 產品完成，也不是模型效果驗收。**
> 唯一施工範圍：[第一切片計畫](S:/caliburn/docs/plans/2026-09-06-analysis-only-agent-native-continuity-slice.md)。設計入口：[Q019](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-design.md)。

## 1. 做到哪裡

新 worktree：`S:/caliburn/.worktrees/analysis-only-agent`，分支 `codex/analysis-only-agent`，起點 `8979494`。新程式僅在 `experiments/analysis-agent`；沒有 import 舊 App、沒有改 production、沒有讀 `.env`、沒有清空任何資料。

只完成兩個小接點：

1. **原生 Responses 配置**：公開 ChatOpenAI 介面，`store=False`、medium／all_turns、Responses content blocks、序列化工具呼叫；可配置 compaction threshold，未假定每模型通用預設。
2. **非破壞 Context 視圖**：依最新 inline server compaction item 建立 detached request；同一 AIMessage 內的 block 也能切，後續 reasoning／tool items 保留；canonical 完整訊息不動。只處理 conversation，固定 instructions／Memory 導覽由未來 middleware 另加。

這不是另一個自訂 Agent loop，也沒有先做新 Memory engine。兩個接點皆依公開格式，沒有 patch 框架 private helper。

## 2. 可重現環境

2026-09-06 查詢 PyPI 官方 JSON，選當日最新穩定版；`uv sync` 實際成功解析 51 packages、安裝 49 packages，產生獨立 `uv.lock`。

| 套件 | 鎖定版本 |
|---|---|
| Python | 3.12.13 |
| LangChain／langchain-core | 1.4.0／1.6.2 |
| langchain-openai | 1.6.0 |
| LangGraph／langgraph-checkpoint | 1.2.11／4.2.0 |
| OpenAI SDK | 3.8.0 |
| HTTPX／pytest | 0.28.1／9.1.1 |

使用真實 adapter、SDK、JsonPlusSerializer；**只有 HTTP endpoint 由 MockTransport 代替**。測試回應先由鎖版 OpenAI `Response.model_validate` 檢查，包含官方 item 型別／usage 格式。全部中文、opaque 字串與 token 數都是合成樣本，不能當真實使用量。測試停用外部 tracing。

## 3. 測試與結果

| 觀察 | 本輪結果 | 不能據此宣稱 |
|---|---|---|
| 發出的 provider request | `/v1/responses`、store false、all_turns／medium、parallel false；未混 previous_response_id | 帳戶模型確實可用、服務端 effective mode 已確認 |
| reasoning → tool → result → reasoning → 下一輪 | opaque 內容、phase、call_id、argument 與 result 正確保留／重送 | 模型真的記得全部分析、分析品質已通過 |
| 官方 serializer 保存／載入 | 重新載入後仍有原始問答與 native blocks | PostgreSQL／重啟／compiled graph 已驗 |
| 同 AIMessage 內 compaction | request 從正確 block 開始；後續工具配對仍在 | 任意 provider 格式／standalone compact 可套同一剪法 |
| compaction 前的 tool convenience metadata | 隨切點移除，避免 adapter 又把舊 call 帶回 request | 並行工具／所有 builtin tools 已全面驗證 |
| canonical 不被視圖改寫 | 舊原文留存，view 改動不影響 canonical | 已完成原文回查工具 |
| compaction 參數 | 正值傳給 provider；0／負值本地拒絕 | 已驗閾值觸發、token 預算或實際壓縮效果 |

初輪測試樣本漏了新版 SDK usage 的 `cache_write_tokens` 必填值，先依官方 schema 補正 fixture；這是測試資料問題，沒有為了過測試放寬 SDK／產品 validation。此錯誤不計成產品 RED 證據。

真正 TDD 紅燈：預設 builder 缺 `store=False`；未實作視圖仍送舊 prefix；淺複製會讓 view 改到 canonical；未連接 compaction threshold。分別完成最小接線後綠燈。

最後已執行（package 目錄）：

```text
uv run --no-sync pytest -q
8 passed in 1.69s
uv run --no-sync python -m compileall -q src tests
exit 0
```

`uv sync --locked --offline`：解析／環境稽核通過；9 個新 package 檔案 whitespace／conflict marker 掃描為 0 問題；6 份主 checkout 文件共 40 個本地引用均存在。這些文件檢查不是模型品質測試。

**實際模型 API 費用：0。** 沒有真實 token／cache 節省或多輪品質結論。

## 4. 尚未發現需換框架的阻擋，但不能過度宣稱

- 鎖版 adapter 可保存本切片所測必要 items，不需 native SDK 替代或 private patch。
- `store=False` 時 adapter 依其公開實作省略不能服務端解析的 assistant message ID；canonical 本地仍保留 ID。不是要求 wire 與原始 JSON 每個 metadata byte 都相同。
- 鎖版 adapter 的 response metadata allowlist 沒有暴露 response 頂層 `reasoning.context`。這是設計階段已記錄的限制；後续最小真實測試需在原生 response 層確認 effective mode，不能拿 configured all_turns 或 LLM 自我報告當證明。
- 本切片同步、非串流；後續接 `create_agent`、串流及 PostgreSQL 時還要驗同樣 item 契約。沒有「先測五分鐘代表所有層都已成熟接好」。

## 5. Review／下一步

獨立 read-only reviewer：spec compliance 與 code quality 無 Critical／Important，判定 **Ready for local slice commit**。定向檢查包含多 phase、切點前有效／無效 tool metadata、切點後配對與 canonical 深層不變性；未重跑全套測試、未付費。

非阻擋建議：現有 pre-cut metadata 回歸測試直接驗 view，尚未將 reviewer 的 outbound wire／`invalid_tool_calls` 探測納入永久測試。**保留到下一段 compiled Agent 接線時補測**，不宣稱目前八項涵蓋所有 streaming／工具型態。

本切片沒有改需求或框架路線，沒有臨時發明兼容方案。結果只支持繼續下一段，不支持 production 合併。

下一段：用官方 compiled Agent／Checkpointer 接一份可保存與恢复的訪談，將這個 request view 接入 model middleware，同時驗原文完整保存與工具往返。再接 B1/B2、C 發布／回查與簡單 UI。依 Q019 分段審查，不把舊系統搬回來。

每個新段落先寫小計畫；涉及修改需求、原生 adapter 不相容、新增顯著複雜度或付費品質測試，再向 Owner 說明。不要重開已完成的整套 Memory 原理研究。

## 6. 精確依據

- [OpenAI reasoning](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-across-calls)：all_turns、完整 output／phase、effective context 與 opaque 限制。
- [OpenAI compaction](https://developers.openai.com/api/docs/guides/compaction)：server-side input chaining 可移除最新 compaction 前內容；**standalone 回傳的整個 window 不可同樣剪掉**。
- [ChatOpenAI 公開介面](https://docs.langchain.com/oss/python/integrations/chat/openai)：Responses、reasoning、content blocks。鎖版 wheel 的 `langchain_openai/chat_models/base.py` §4749–4920／§4990–5180 是本輪讀取的轉換／metadata source；沒有呼叫其 private helper。
- [LangGraph serializer](https://docs.langchain.com/oss/python/langgraph/persistence#serializer)：本段只驗序列化，不冒充 DB 操作。
- [HTTPX MockTransport](https://www.python-httpx.org/advanced/transports/#mock-transports)：公開 HTTP 邊界替換方式。
- [PyPI langchain-openai](https://pypi.org/project/langchain-openai/1.6.0/)、[OpenAI SDK](https://pypi.org/project/openai/3.8.0/)、`uv.lock`：版本／依賴可重現。

這是對 Q019 接線的實證，不是「各大廠都有完全相同自訂函式」的主張。
