# 端到端先導

本次只驗證長訪談比較所需的真實接線與計量，不執行四組主實驗、不修改正式產品。沿用現行 Luna/high、16,384 輸出預留、128K／160K 壓縮時點、原生 items、JD 工具及 B1 → B2 → 發布。

## 路徑與外送界線

- 使用既有隔離 PostgreSQL 容器 `caliburn-jd-docker-test-postgres-1` 的 `55441`、`caliburn_docker_test`，建立新的隨機 schema 與空職務檔案；不讀取正式資料、不清除 volume。
- 員工依序提供 `e001`、`e002`、`e004`、`e006`；每則均走現行 A 及正式完成交易。完成後，以該輪有效員工來源建立一批真實 Memory；這是研究固定批次，不要求模型必須通知整理。
- Memory 發布後提供 `e055`，觀察後續 A 回查、回答及 JD 改動。未必主動採用 Memory，須從實際 trace 判讀；不以資料庫有產物宣稱模型用了它。
- 五輪不是完整職務訪談；未涵蓋的職責與未發生的壓縮不計為通過。正式開場沿現行產品產生，不置換成研究者的假顧問回答。
- 本批最多 **48 次生成、160 次全部外送、2,000,000 累計生成輸入 tokens、每次 16,384 輸出 tokens、30 分鐘**。每次生成前須有同一完整請求的官方計數；計量不明、預算不足或 HTTP 失敗即停止，不重試。
- 研究估算預算 **US$1.00**：使用現行 Luna Standard 定價，生成以最昂貴輸入／輸出預留，計數每次另預留 US$0.0001。這是本機研究准入估算，不是遠端帳單硬上限。
- 本小批 **不准外送 Compaction**：若原有合法時點要求壓縮，停止並保留原因；不繞過它、不截斷、不降低正式門檻。主實驗的 compact 另定界線。
- 所有輸出僅合成資料。公開 trace 保留 native item 的欄位、訊息 phase、工具配對及 usage，但 encrypted_content 僅保留長度與 SHA256；可接續原件仍由真 PostgreSQL checkpoint 保存。金鑰與連線密碼不進證據。

## 任務與驗證

1. [x] 實驗護欄行為測試：拒絕錯配／缺失計數、超量、未授權 compact，覆蓋計數及生成外送；不寫第二套產品 runtime。
2. [x] 使用現有 Workflow／Runner 執行五輪及一批 Memory，保存正式原話、JD 修訂、Memory 快照、來源回查、原始輸出和完整計量。
3. [x] 核對真正請求的 Context 組裝、工具順序、已保存結果及早期事實；記錄失敗與未驗項目，更新先導結果，不覆寫既有 preflight／舊實驗。

現行既有 Docker／OCS／PDF／報告修改不屬本切片，保留不動；不 commit、push、merge。本研究資料夾已隔離文件與腳本，不另開修改產品的分支。

## 執行紀錄

- 前置準備已完成，沿用 `preparation-plan.md` 與 `offline-02`；不重做五次官方計數。
- API 契約與 Luna 容量核對：[官方模型文件](https://developers.openai.com/api/docs/models/gpt-6-luna)。定價沿現行 `openai_pricing.py`，與官方已公告 Luna Standard 表相符。
- 已核對並啟動上述隔離 PostgreSQL；原正式 PostgreSQL `55437` 未啟停。
- [pilot-01](pilot-01/result.json)已完成：23 次生成、27 次計數，耗時 393.7 秒，最高單次輸入 22,072；沒有 Compaction。事實、Context、正式保存及未施測範圍見 [先導結果](pilot-results.md)。此狀態不代表四組主比較完成。
- 收尾前確認隔離容器無其他用戶連線，已停止本輪啟動的 `caliburn-jd-docker-test-postgres-1`；schema 與 volume 保留。正式 `caliburn-jd-postgres-18-6` 仍運行。下次需要資料庫回查時先依此身分重啟，不另建或清除資料。
