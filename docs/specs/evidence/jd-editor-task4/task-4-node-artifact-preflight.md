# Task 4.0 Node portable artifact 前置核對

**保存說明：**本頁是完成下載驗證時的紀錄；以下原始非執行材料以相同bytes保存。35.7MB portable ZIP仍留本機隔離plan scratch，不納Git；其官方下載來源、簽署hash及本機驗證紀錄保留。真正runtime導入／回歸另記Task4實作報告，不能由本頁推定已完成。

- 日期：2026-09-10；完成紀錄 UTC 01:13:26／Asia-Taipei 09:13:26。
- 範圍：JD-R002／Task 4.0 前置下載與完整性核對。Task 3 尚在執行，本輪不切 runtime。
- 結論：**PASS：官方簽署 SHASUMS 驗證成功，Windows x64 portable archive 的 SHA256 與已驗簽 payload 一致。** 這是來源及下載完整性證據，未執行新版 Node，未做 runtime／安全全認證。

本機 OSArchitecture 與目前程序 ProcessArchitecture 均為 X64，選用 `node-v22.23.2-win-x64.zip`（35,683,585 bytes）。全部材料位於本計畫已受 git ignore 的 [task4-node-preflight](task4-node-preflight/) 目錄；沒有解壓到 active runtime。

## 簽章與 archive

使用本機既有 `D:/Git/usr/bin/gpgv.exe`：GnuPG `2.4.5-unknown`、libgcrypt `1.9.4-unknown`。未安裝新驗證工具，keyring 與 GPG homedir 均限定在本 scratch。

- `gpgv` exit code：**0**；狀態含 `GOODSIG` 與 `VALIDSIG`。
- 簽署 identity：`marco-ippolito <marcoippolito54@gmail.com>`。
- 完整 fingerprint：`CC68F5A3106FF448322E48ED27F5E38D5B0A215F`。
- 簽署時間：`2026-07-29T13:56:01Z`。
- 此 fingerprint／identity 與下載自 [v22.23.2 官方 README](https://raw.githubusercontent.com/nodejs/node/v22.23.2/README.md) 第 798–799 行的 Marco Ippolito release key 相符。
- Archive SHA256：`1177b4137ba5adaa56354ae40f1080c7450e8ae09cecb47da459d1c52ac99f97`；與 `gpgv` 驗簽輸出的 [verified-SHASUMS256.txt](task4-node-preflight/verified-SHASUMS256.txt) 對應檔名完全相符。

完整 [gpgv log](task4-node-preflight/gpgv-verification.log) 與 [驗證結果](task4-node-preflight/verification-result.json) 已保留。這是 clearsigned SHASUMS：log 提醒另下載的 `SHASUMS256.txt` 不是 detached signature 的被驗檔；本輪以 **驗簽後輸出的 payload** 為 archive digest authority，再確認它與另下載的 plain SHASUMS 逐 bytes 相等，沒有把該提醒忽略或僅憑未簽署清單稱驗簽成功。

## 官方來源與材料 hash

全部檔案的 SHA256、byte size、來源 URL 及本機寫入時間集中於 [artifact-manifest.json](task4-node-preflight/artifact-manifest.json)，包含原始簽章、keyring、LICENSE、README、已驗 payload、驗證結果與失敗沿革。核心下載來源如下：

| 檔案 | 官方來源 |
|---|---|
| portable archive | [Node 22.23.2 win-x64 ZIP](https://nodejs.org/dist/v22.23.2/node-v22.23.2-win-x64.zip) |
| signed SHASUMS | [SHASUMS256.txt.asc](https://nodejs.org/dist/v22.23.2/SHASUMS256.txt.asc) |
| plain SHASUMS | [SHASUMS256.txt](https://nodejs.org/dist/v22.23.2/SHASUMS256.txt) |
| release public keyring | [nodejs/release-keys 官方 keyring](https://github.com/nodejs/release-keys/raw/HEAD/gpg/pubring.kbx) |
| 授權 | [v22.23.2 LICENSE](https://raw.githubusercontent.com/nodejs/node/v22.23.2/LICENSE) |
| 驗證方法與 signer 對照 | [v22.23.2 README](https://raw.githubusercontent.com/nodejs/node/v22.23.2/README.md) |

Node 本體採 MIT；分發包附帶元件授權分列於 LICENSE，不能將整包所有檔案一概稱為 MIT。官方 keyring URL 的 HEAD 是可變來源；本輪保存其下載 bytes 與 SHA256 `610b8d249da3d5733f5a128def2dd0294dbbf5b5713e6ca2529db8db419dee00`，並用精確 release tag README 交叉核對實際 signer。未新增個人／全機 GPG trusted keyring。

## 執行沿革與剩餘 gate

受限執行環境最初阻擋 proxy 下載與 Git MSYS signal pipe；取得限定下載／既有工具驗證的執行權限後完成，沒有自動審批拒絕。第一次驗簽因傳給 Git gpgv 的 Windows keyring 路徑被當相對路徑而回 `NO_PUBKEY`；該次 [失敗 log](task4-node-preflight/gpgv-attempt1.log) 與明標未驗的 plaintext 已保留。改用同一 scratch 的 MSYS 絕對路徑後，以上正式驗簽與 hash 核對通過；沒有更換 key 或略過簽章。

本輪沒有執行下載的 Node／npm、解壓 archive、改 PATH、全機安裝、改 code／package／lock、操作 Task 3 程序／模型／DB 或 commit。待 Task 3 通過，再按 Task 4.0 導入隔離 runtime、重建 API／JdEngine 並核實際 executable／版本，完成原計畫必要回歸；本報告不能替代該 gate，也不改写 Task 1–3 的舊 runtime 測試證據。
