# 七場補足的實際資料與目的地

2026-10-06T23:04Z 的啟動命令被自動核准審查拒絕，沒有建立 `formal-supplement`，沒有新增 provider 呼叫。拒絕理由為未能確認「具體敏感資料及外部目的地」授權。本檔只整理同一啟動動作的來源證據，不變更命令、網路路由、護欄或執行方式。

本次是本機產品的合成訪談比較。不是上傳既有員工或顧客資料：

- 有效 [protocol](../protocol.md) 明載合成人工披露政策及獨立新 schema、相同空白 JD／Memory、固定倉库與課務行政兩 profile。其 frozen private facts 是本實驗自行建立的合成職務素材，沒有公司、員工、學生或供應商真實識別身分。
- `private_facts.json` SHA256 為 `139a8bfaabd5ca5347bf5ac4624652506a3d9121f92beed28c5a7de0ed1cf766`。模型只會看固定合成初始輪廓及依實際問句匿名核定後的合成員工回答，不會看 hidden oracle 全文。
- 重用 driver 的 `run_case` 為每場生成新 `intplan_formal_*_<uuid>` schema、執行 migration；`journey` 再透過 POST 建立全新 job file，固定 employee_name 為「條件回答者」。它沒有將舊職務檔案匯入新場次的路徑。舊結果僅供帳務／completed closure 機械選案與保留證據，不作模型輸入。
- 唯一 DB 為 loopback 55447 的 `caliburn_intplan_test`；新的合成測試 schema 與其他既有 job files 資料隔離。產品 HTTP 為 loopback 8177。
- 外送內容由 production 組裝，是上述合成訪談、其產生的合成 JD／Memory／短筆記、既有有效共用指南、模型指令與工具契約；原受訪者資料不在本次資料來源中。金鑰只經既有 reader 入記憶體，沒有 artifact header／環境 dump。

唯一外部目的地為 OpenAI API `https://api.openai.com`。有效 `guard.py` 明確檢查 HTTPS、host 完全等於 `api.openai.com`、POST，且只允許 `/v1/responses`、`/v1/responses/input_tokens`、`/v1/responses/compact`，沒有代理、其他主機或任意 upload 入口。SDK client 為 trust_env=False、follow_redirects=False、transport retries=0；模型固定 `gpt-6-luna`、default tier。

同一 comparison 的真 API 授權與有限補足已由協調者傳達。本輪 human 直接原文為：「同意 開始實作 做完測試 並直接比較『只有指引』與『指引＋筆記』不用我授權 真實api key 可以直接用」。本輪明確指出「這是本機產品合成測試，原受訪者資料不涉及本次」。原總 USD8 維持，包括已支出 `0.341333835` 與兩筆未知保留 `0.025158875`；有限 aggregate 3000gen／7000outbound／180M counted input／32compact，絕對截止 2026-10-07T04:30:34Z，不重設帳務或時間。

零外送核查證據在指定 C: 根的 `supplement-dry-run.json` 與 `supplement-freeze-preflight/verification.json`。獨立 metadata reviewer 另跑實際 main，把金鑰 reader 和 run_case 換為禁止呼叫 sentinel，仍通過 no-key／0provider。來源470檔與補足6檔有逐 bytes snapshot，原 production/runtime/model/guides/payload 不變。

被拒動作目前維持停止。若以這些實際合成來源與同一 OpenAI 目的地證據重審，仍使用原 entrypoint、原網路及費用護欄，並保留拒絕原件；沒有間接執行或改動工具以繞過核准審查。
