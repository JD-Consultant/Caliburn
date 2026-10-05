# 計時修訂 02：Windows 暫時檔案鎖定

首輪實際暖機完成 23 個 trial，讀取 F02-R04-3 的 GPU 回應時發生 PermissionError。其後同一路徑已能正常讀取，40 個新 pairs 完整，表明是 Docker bind mount 交接時暫時鎖定，不是缺檔或排名改變。不放寬 ACL。

首輪 23 個時間與所有 GPU 回應保留，失敗 trial 不拼接成成功時間。修訂加入有界讀取等待，只處理 PermissionError，JSON 錯誤及內容不符仍拒絕。第二輪所有 60 個 trial 重新實際量測，900 pairs 都 fresh，不讀舊 pair 分數；模型重新載入時間另存。不覆寫品質排名與評審輸入，不重做已固定的 300 品質 pairs。

原 benchmark-results.jsonl 保留，正式比較使用 benchmark-results-02.jsonl／timing-summary-02.json。benchmark-execution-02.json 綁新腳本；原 manifest 及付費評審不變。本機計時修訂不增加模型評分外送。
