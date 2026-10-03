# 來源差異配對實驗 r1

狀態：執行前凍結的方法；2026-10-02。沿用使用者對有界合成實驗的授權，只研究，不改產品／前端／資料庫／模型選型。問題來自專題報告 §6.1：差異搭配新版按需讀取，能否以較少累計輸入支持正確的 JD 來源重評？

## 方法

- 六個人工構造的中文案例：頻率更正、局部分工更正、正文不變而直接情境依據改變、原來源已移除、正文相同但新修訂、期限仍未知。素材依工作分析指南的範圍、更正、不確定性原則設計，不是真員工資料。
- 每案兩次重複、兩組，24 trials。相鄰配對，第二次反轉組序，不挑選最好結果。每 trial 使用獨立 Context。
- `full`：提供該 JD 引用的新舊來源全文及關係，不提供預算過多的無關 Memory；仍可讀新版。
- `diff`：以現行 `project_jd_source_changes` 產生 Markdown 差異，提供新版導覽，必要時讀新版。讀取會包含該物件的完整正文與來源標題；可再依標題下查。
- 兩組相同的短任務指引、導覽、既有 JD 事實、工具與輸出格式。只改變起始來源表示。這是來源重評子任務，不是完整 production 顧問 Turn；不執行 JD 寫入或引用提交。
- 模型 `gpt-6-luna`、reasoning high、store=false、all_turns、原生輸出接續、不壓縮、不用 previous_response_id。沿現有 direct Responses adapter。每次輸出最多 2,048 tokens、每 trial 最多四次生成，每次實際計數後不超過 16,000 input tokens；整批最多 96 次生成、累計准入 input 400,000 tokens、最大准入 output 196,608 tokens、40 分鐘。只記實際 usage，不把 count 當生成。
- SDK 自動重試關閉；認證／額度／網路／限流錯誤即停止此批，保留未完成狀態；若安全網路環境需要調整，以新 run 名稱記錄，不覆寫結果、不跳過已見失敗。

## 事前判準

模型以 `submit_review` 提交結構化判斷。五個內容欄位（frequency、actor、approver、deadline、scope）只是量測已知事實的簡化表示，不是新增 JD 資料表／正式工具。要求沿來源用字以便重算；空缺用「未確認」。另提交是否修訂、引用保留待核對／可對齊／移除，以及一項未受影響工作的原文。短理由不要求內部思考。

每 trial 八項精確檢查：五個事實欄位、內容動作、引用動作、未變項目原文。所有八項通過才計完整通過；同時保留逐項結果與完整短理由供內容複核。oracle 不送給模型，不以它生成工具回應。這不是人類顧問盲評，不能以此宣稱整份 JD 專業品質或未知工作完整性。

主要比較：各組完整通過數／12、逐項通過數／96；效率：每 trial 所有 response.usage.input_tokens 總和（包含工具結果與重送歷史）、output_tokens、讀取工具次數、生成次數、首則資料字元數與端到端秒數。count、生成及本地工具時間都在端到端內。快取命中另記，token 數不扣快取；不把本機服務延遲算成模型純速度。失敗／未完不補造 0 tokens 或算通過，另外列出。小樣本只作描述性比較，不聲稱統計顯著。

品質不下降且累計输入減少才支持本組測例的效率假說；若往返使輸入增加或有漏判，同樣列為結果，不調提示重跑直到過關。新增未被引用的 B1 情境屬另一個 B2 問題，本次不冒充已覆蓋。

## 可重現與安全

`cases.py` 固定可見資料與 oracle；`experiment.py` 組裝、呼叫與評分；`test_experiment.py` 檢查量測邏輯。執行前保存 suite、指引、tools 與產品 renderer SHA-256。每 trial 保存去除 opaque 欄位的完整可見請求／輸出、工具結果、usage、計時及評分；opaque 原件只在記憶體接續，不寫入資料包。金鑰只由既有 credential reader 讀明確的 env 路徑。run 目錄不可覆寫。

此實驗不需要新 eval 平台或 model judge。參考 [OpenAI 評估方法](https://developers.openai.com/api/docs/guides/evaluation-best-practices) 的任務特定判準、固定資料及結果比較，以及 [Anthropic Agent 評估](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) 的 outcome／trace 分開、多次 trial 及可檢查結果；不把任一家建議稱作統一業界規格。官方頁面已於本次查閱。
