# 六個模型引句未逐字吻合

45個provider response均完成且有usage，初次39個通過literal證據；6個因引句抄錄差異失敗，原grading-summary、39個judgments及全部原response保留，不改原件。

逐筆核原話／公版同一段後，固定六個明確來源抄錄修正：new-011「計畫／計劃」、new-012／043／044全形及半形逗號、new-017補回原句的「也」、new-031「依據／依照」。不把後兩項冒充僅空白格式。六個原分數均為1或2；grade、uncertain、main_work、reason及limitations完全不改。

recover_quotes.py以明確before／after、來源唯一字面位置核對，再沿既有validator檢查全部證據，另外存quote-recoveries及judgments-final，不覆蓋失敗原件。不再呼叫模型或花費；這只是引用抄錄核對，不代表語意評分已人工驗收。主代理知道檢索結果，修正範圍因此嚴格限於既定引句，沒有重評或換支持理由。

analysis／verify另以02腳本讀明示final判讀，原腳本及hash不改。此為評分輸出呈現修訂，候選／排序／輸入／模型設定不變。
