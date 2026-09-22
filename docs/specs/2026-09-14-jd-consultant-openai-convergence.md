# 產品顧問收斂到 OpenAI：修正施工期留下的 provider 接線

> **2026-09-15 最新閱讀校正：本稿的「OpenAI 是模型供應商」有效，但把它推成直連 `ChatOpenAI`、單一 `OPENAI_API_KEY` 或移除 OpenRouter 的部分無效。Owner 已確認目前產品路徑是 LangChain／LangGraph framework → OpenRouter → OpenAI-only route → `openai/gpt-5.6-luna`，禁止 fallback，日後由 profile 換模型。本文只保留 2026-09-14 施工期衝突證據；不得用 §3–§5 直接施工。最新基線見 [目前決策](../current-decisions.md) 與 [接線對齊稿](evidence/2026-09-15-jd-integration-document-reconciliation.md)。**

日期：2026-09-14；Topic：JD-R002。Owner 於 2026-09-14 重新整理正確基線後指示本單位。這不是重選 provider，而是**把施工過程留下的 Anthropic 接線收回到既定產品方向**。

## 1. 正確基線（Owner，2026-09-14）

- 產品是**單一** AI 職務說明書顧問；員工與顧問共用同一套 JD 業務邏輯、資料庫與保存服務。
- 產品**主要使用 OpenAI**。不建立 Anthropic 顧問路徑、不做雙 provider 選單、不做自動 fallback。
- 產品對使用者提供一位顧問。B1 抽取與 B2 整併是 Memory 背景流程；C 是顧問可使用的即時 Memory 修補流程。它們不構成使用者管理的多代理產品；framework 的內部 graph／child 不因此被禁止。（2026-09-15 分層澄清，依 H4 現況與 runtime repair 接點。）
- Claude CLI／Opus 只可能是**開發期**的外部實作者或審查工具，完全不屬於產品 runtime。
- 框架負責 Agent、工具、狀態、checkpoint 與執行流程；OpenAI adapter 負責模型通訊。框架支援多 provider **不代表**產品要同時用兩家。
- 9/12 核心方向仍有效：關聯式 current rows 是唯一可寫 JD，revision 是歷史快照，operation 是保存回執；同畫面聊天與唯一可編 JD；AI 可直接改但員工看得見當輪差異；Memory、原始對話與 JD 分開保存。

## 2. 目前的實際矛盾

| 位置 | 現況 | 問題 |
|---|---|---|
| `consultant_model.py` | `ConfirmedChatAnthropic`，固定連 `api.anthropic.com` | 產品顧問被釘在 Anthropic |
| `consultant_context.py` `_bound_response` | 以 Anthropic 的 `stop_reason ∈ {end_turn, tool_use, stop_sequence}` 判終局 | 換 provider 後這條判斷不成立 |
| `consultant_context.build_consultant_node` | 驗 `isinstance(model, ConfirmedChatAnthropic)` 及 streaming 旗標 | 同上 |
| `provider_keys.py` | 同時保存 `anthropic` 與 `openai` 兩把金鑰 | 產品只需要一家 |
| `managed_app.py` ／ `__main__.serve` | 日常入口以 `enable_chat=False`、`unavailable_consultant()` 開啟 | **日常訪談從未接上**；因此「H4 全部完成、只差 model id」不能當成產品可用的證據 |

已定的角色配置（[採用映射 §4](2026-09-13-jd-consultant-b1-b2-adoption-mapping.md)、[品質驗收 binding decisions](2026-09-10-jd-product-quality-acceptance.md)）：**A 與 B2 皆為每工作 16 模型步／15 工具呼叫的 Agent；A／B1／B2 effort high、顯式輸出 8192；provider 接線的 native compaction 12000。**A 目前缺這些預算，也是待補的實際缺口。

## 3. 範圍

| 做 | 不做 |
|---|---|
| 顧問模型組裝改用既有已驗的 OpenAI 形狀（responses API、`store=False`、不平行工具、effort high、顯式 8192、compaction 12000） | 不新增第二套 Agent loop、第二個 JD 寫入者或第二份資料權威 |
| 終局判斷改用與 B1／B2 **同一條**規則（`status == "completed"` 且無 refusal），集中於一處 | 不保留 Anthropic 分支、不做 provider 分歧判斷、不做自動 fallback |
| 補上 A 已定的 16 模型步／15 工具呼叫預算 | 不新增使用者可見的模型選單或 subagent 管理 |
| provider 金鑰收斂成單一 OpenAI 角色 | 不刪既有 JD／Memory／保存契約，不動 B1／B2 與框架 |
| 日常入口在金鑰已設定時組出真顧問並啟用聊天 | 不在沒有金鑰時偷開 provider，也不為檢查設定而發付費呼叫 |

## 4. 先寫的反例

**模型組裝**
- 顧問模型必須是 OpenAI 組裝；傳入 Anthropic 模型必須被拒，不得靜默接受。
- 產品程式不得再 import `langchain_anthropic`／`anthropic`。
- 組出的模型必須帶 `use_responses_api`、`store=False`、`parallel_tool_calls=False`、effort high；任一不符即失敗。

**終局判斷**
- `status != "completed"`（含 `incomplete`，即被輸出上限截斷）必須拒絕，不得當成短的成功。
- 帶 refusal 區塊的回覆必須拒絕。
- 這條規則與 B1 使用**同一個**實作，不是第二份複製。

**預算**
- 顧問的模型步與工具呼叫上限必須是已定的 16／15，且由組裝處明示。

**金鑰與啟動**
- 只有一個 provider 角色；舊的 `anthropic` 角色不再存在。
- 沒有金鑰時：人工 JD 完全可用，聊天送出得到明確未啟用訊息，**不呼叫 provider**。
- 有金鑰時：日常入口組出真顧問並啟用聊天。
- 金鑰仍不得進入設定檔、資料庫、prompt、對話、checkpoint、前端、日誌或備份。

## 5. 驗收

固定回覆＋真 PostgreSQL 驗接線；自然模型驗收另行標記，**不把合成測試當顧問品質**。真瀏覽器旅程沿既有 helper 重跑。零付費呼叫。
