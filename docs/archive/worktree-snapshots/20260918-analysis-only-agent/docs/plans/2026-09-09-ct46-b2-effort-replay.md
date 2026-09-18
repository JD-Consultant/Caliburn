# CT46：同一失敗整併輸入的推理強度局部對照

LLM-Q019，G5／整體G8 OPEN。Owner已授權持續局部調整Luna effort與測試，重大才問；不改架構／JD／production。

## 證據與唯一假設

CT45固定587065b5版本、第8輪：A完成、B1完成；B2 high 12模型／12工具後額度耗盡，revision仍7。#61、64、69補丁舊context抄錯UUID而被拒；框架有回精確錯誤，也有重讀，但再次長段重抄仍錯。這不是「框架沒有重試」，也不證明全面加工具次數就是解法。另phase7把仍有用的維護／估算引用換成只談交付的詳記，須獨立審核。

現有prompt已有短檔多處改用write_file、長檔局部patch、保留未變內容與引用；先測**只提高B2至xhigh**，是否同一輸入能在原12／12內正確收尾。公開[GPT-5.6提示指南](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)要求先查成功條件／工具規則，再以代表性軌跡比較effort；[Luna官方模型頁](https://developers.openai.com/api/docs/models/gpt-5.6-luna)確認high/xhigh/max可用。這是有界實驗，不宣稱xhigh保證正確或為廠商共同預設。

## 測法與界線

1. CT45保存失敗、完整原話與六份詳記唯讀核對、帳本closed；原PG不變。測試audit最初把list當dict的錯誤另記，修後全六份來源吻合，與產品失敗分開。
2. 從原PG**只讀**已保存第8輪B1、與該輪寫前的正文／導覽；複製至官方InMemoryStore／Saver＋SQLite publication。不是重做B1、不是替模型補答案、不把failed staging帶入。
3. 只改B2 reasoning effort=xhigh；prompt、工具、來源、8192、12模型／12工具保持不變。24次／US$0.15新護欄（需要另一個effort對照時仍在同帳本），全部原始attempt計費與紀錄；不重開舊帳本。只送本次合成訪談／Memory至官方Responses。
4. 正確性先於次數：不丟仍有效細節、套件升級有來源與條件、沒有錯引；patch錯誤要如實記、無final則不可稱發布成功。回讀前後原PG一致。
5. 一次成功僅為局部證據；若要採用需回歸及後續固定版整份訪談，不把CT45前8輪拼成新設定從頭通過。若仍失敗，先審來源／提示與官方方法，不持續堆額度或新機制。

結果、對照prompt／來源雜湊與腳本歸同號spec/evidence；current register只留短結論／入口。CT45第9輪已準備但尚未傳送，不算已訪談。
