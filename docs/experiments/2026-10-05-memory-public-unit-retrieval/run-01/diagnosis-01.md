# 準備步驟封存格式診斷

首個prepare在新排名／服務／provider之前失敗：遍歷所有experiment的artifact-hashes，假設都有`files` wrapper，遇到早期RAG的直接mapping而KeyError。其它家族還有list格式，無需把其資料引入本題。

沿 systematic-debugging核對現行原件與前輪prepare後，改為重用Memory輪已核1,775檔baseline，逐檔重新算hash，再加該輪158份sealed artifacts。沒有跳過受比較資料，也沒有修改任何舊seal；這是事前準備修正，未產生新排名或外送。

原錯誤：prepare.py main讀`read(mf)['files']`時KeyError: files。修正後預期1,933舊檔完整、20固定查詢、143個舊pair。
