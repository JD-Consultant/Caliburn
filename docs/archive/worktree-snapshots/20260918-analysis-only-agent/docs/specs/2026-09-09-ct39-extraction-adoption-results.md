# CT39：已驗提示＋B1 high 接入隔離 app

2026-09-09 · LLM-Q019 · 局部接線驗證；完整訪談品質 G8 OPEN

## 1. 決定與理由

Owner「交給你決定」後，採用 **CT37 frozen candidate＋B1 high，A／B2 medium**。不是所有模型改 high，也不是加入另一個分析 Agent。

- [CT37](2026-09-08-ct37-prompt-effort-comparison-results.md)：同提示、同可見來源，medium 原例仍有語意錯誤；high 有局部正向結果。
- [CT38](2026-09-08-ct38-high-extraction-medium-consolidation-results.md)：舊提示 high 仍把印象寫成肯定；候選 high→既有 B2 medium，以及後續核實資料→整併，主要檢查通過。這是有限案例證據，不是統計正確率。
- 本次只接入該組合，不再增加第三版提示或重新進行同一付費比較。[實作計畫／本輪官方來源](../plans/2026-09-09-ct39-extraction-adoption.md)。

## 2. 實際修改

1. `extraction.py` 替換兩條相近提示，採已封存版本：詳記、候選與標題都保留說話者、回答範圍、確定程度；「沒做過」不等於「未回答」，顧問回述不等於員工確認。保留既有案例辨識、範圍、頻率、權責、未變細節與引用規則。
2. `provider.py` 接受 `reasoning_effort`，預設仍 medium，沿官方 `ChatOpenAI(reasoning=...)`；保留 `context=all_turns`、Responses、`store=false`、`truncation=disabled`、原生壓縮及 SDK 重試。
3. `api.open_service` 額外建立 B1 high binding，共用原模型名稱、base URL、HTTP transport／Context budget hook、timeout 與輸出上限；在服務退出、worker 結束後關閉。沒有第二套網路／錯誤處理流程。
4. `AnalysisService.enable_background(extraction_model=...)` 將模型傳進既有 dispatcher；只有 B1 使用它，B2 及主顧問仍使用原 model。未注入的獨立測試／呼叫仍沿原 model，不偷偷全域升級。

提示 SHA256：`0f621a77a1a8f04edb1edac59ef1c2eee349c2467f7d0325049e36b19f7355c5`，與 CT37／CT38 封存候選一致。這個雜湊檢查只保證採用正確版本，不保證模型遵守提示。

## 3. 新驗證與限制

`tests/test_extraction_role.py` 使用真 SDK／LangChain／graph／SQLite catalog／Memory Store，HTTP 回應由測試提供；根 factory 測試另以官方記憶型 Saver／Store 代替 PostgreSQL。不把人工準備的回應當作模型品質證據。

- RED：未加介面前 6 個測試因 `reasoning_effort` 不支援而失敗；兩次 sandbox 暫存目錄權限中斷另記，不視為產品 RED。
- GREEN：7 個新測試通過；原 202 個相關回歸也通過。factory 測試曾修正兩項測試本身問題：slots 物件不能臨時增加 `setup`；SDK timeout 是顯式 float，HTTP client 才是 Timeout 物件。沒有為通過測試更改產品保護。
- 實際序列確認：A medium→A tool 後續 medium→B1 high→B2 medium→A medium；未注入時仍全程原 model。1000／6000 輸出上限及 all_turns 保持。
- 真正 `open_service` factory：同 transport／budget hook、同 endpoint／timeout／壓縮閾值、B1 high、B2 medium，完成 rev1 發布並正確關閉客戶端。
- 完整離線 suite：`python -m pytest tests -q --tb=short --basetemp <新的隔離暫存路徑>`，**551 passed、41 skipped、1 warning，61.27秒，exit 0**。41項是未啟用專用 PostgreSQL 的測試，不算持久／並行驗收；warning 是既有 Starlette／AnyIO deprecation，不在本局部變更內。測試沒有讀 `.env` 或使用真實模型。
- 新付費生成 **0 次、US$0**。CT38 的真實抽取與整併證據沒有改寫為本輪真測。
- Newton 唯讀 review 未報重要 finding：確認 B1 單獨注入、A／B2 binding、預算／輸出／重試不變，以及 service 先等待工作結束、再關閉共用 transport 的生命週期。Reviewer 未獨立重跑測試，不冒稱雙份驗證。

## 4. 邊界與下一步

不改 Memory 分層、schema、工具、排程時機、模型步數上限、Skill、B2 提示、主顧問提示、C 停放政策或 production／JD。沒有修改已保存的舊錯誤 Memory；新版須重啟隔離服務後才生效，已生成產物不會自動重算。

下一段是**用這套已接入配置繼續正常訪談品質驗收**，觀察不確定性、部分回答、案例細節與後續核實能否保持；不宣稱已完成長訪談，也不要求每輪全量重算 Memory。若 high 成本／延遲或語意結果仍不理想，再用新證據重開本局部選擇，不因看到另一框架名稱就重開全部設計。

## 5. 引用的效力

2026-09-09 實際重讀：[OpenAI effort 指引](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6#reasoning-effort)支持先看提示與 baseline、按測試選 effort；[LangChain 官方接點](https://docs.langchain.com/oss/python/integrations/chat/openai#reasoning-output)提供 reasoning 設定；[Anthropic 幻覺控制](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations#basic-hallucination-minimization-strategies)支持保留不確定及以來源為準。兩家沒有保證本繁中提示永不錯，LangChain 也不負責判斷語意真偽。更早的 Codex 原始提示追查由 CT37／CT38持有，不重複貼長篇資料。
