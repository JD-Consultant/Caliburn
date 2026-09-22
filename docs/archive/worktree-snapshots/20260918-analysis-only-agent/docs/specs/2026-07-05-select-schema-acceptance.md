# select_schema 對抗性驗收紀錄 #1(ADR 0024;T7)

> **紀律**:換 `model_select` = 改 settings + 重跑 `apps/api/scripts/validate_select_schema.py`
> + 在本檔追加紀錄;既有 `i in known` 保險絲觸發(生產 log error)= 立即回此重驗。

## 紀錄 #1 — 2026-07-05

| 項 | 值 |
|---|---|
| 模型 | `openai/gpt-4o-mini`(via OpenRouter 透傳,`json_schema` + `strict: true`)|
| 樣本 | n=8 對抗性提示(池外 id / 未定義指令 / 違規欄位 / 自由文字選項 / 巢狀 value / schema 外原始 JSON / 合法非法混發)|
| **逃逸** | **0** → **PASS** |
| 平均延遲 | 1.98s(成功呼叫)|
| 例外事件 | 第 1 發:模型被誘導輸出池外 id,受限解碼拒吐非法 token → 生成失控(~22K chars)至截斷 → 非法 JSON → 重試耗盡 → `LlmSchemaError`。**判定:fail-closed,非逃逸**(值承重路線失敗顯式爆炸,正是設計意圖)|

## 事後 hardening

- adapter 加 `max_tokens=2048`:失控生成的 token 成本與延遲上限鎖死;截斷=非法 JSON=照樣炸
  (不影響正常回合——TurnOutput 遠小於此)。

## spike 結論(0024 決定 4 的落地紀錄)

**選 openai SDK 直傳,不引入 Pydantic AI**:我們的 port 是「**動態 raw schema**」形
(池 id per-request 鎖 enum、`ask_choice` 變體動態進出 schema)——SDK 的 `response_format`
直傳零轉換;Pydantic AI `NativeOutput` 以型別類為中心,動態 enum 需 runtime `create_model`
反而多層。`openai` 由 langchain 的隱性傳遞依賴轉為顯性宣告。Pydantic AI 不引入
(記縫:若未來 port 轉為靜態型別輸出再評)。

## 已知邊界(誠實記錄)

1. 受限解碼保證「每個 token 合法」,**不保證「生成必然完結」**——截斷產生非法 JSON,
   由 fail-closed 承接(重試→炸→route 502/503),不會默默入庫。
2. 本驗收樣本 n=8、單模型;首次接真訪談流量後應以生產 log(保險絲觸發率)持續監控。
