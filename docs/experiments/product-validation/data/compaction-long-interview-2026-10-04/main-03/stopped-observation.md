# 2026-10-04：長訪談續跑停止與 Context 累積觀察

`main-03` 於 16:28:58（臺灣時間）在 e061 的下一次 compact 外送前停止，原因是累計已達 16 次 compaction。這是凍結的研究護欄，不是 OpenAI 容量拒絕、費用用完或四小時逾時。第一組保存 60／61 段及四批 Memory；其餘三組尚未開始，因此尚無四組比較結果。

## 保存了什麼

| 範圍 | 已保存結果 |
|---|---|
| 沿用前綴 | main-02 成功的 e001–e051、前三批 Memory，逐檔雜湊相同 |
| 新成功段落 | e052–e060，共九段正式員工輸入與顧問答覆 |
| 新整理 | e052 後第四批 Memory；前三批不重做 |
| 未完成 | e061 只有四份模型回應及工具工作，沒有正式最終答覆或 product-061 |
| 未開始 | 單層摘要、原話按需、只有近期三組 |

原件：[result](result.json)、[failure](failure.json)、[manifest](manifest.json)、[trace](trace.jsonl.gz)。本次核對結果見 [stopped-reconciliation.json](stopped-reconciliation.json)。原始資料、執行腳本及判準不追改；没有重新外送、修改正式產品或處置資料庫。

## 用量與接續核對

新階段約 56 分 38 秒，109 次外送全部取得回應：43 次生成、56 次計數、10 次 compact。生成 usage 無缺漏；生成 input 為 5,420,449、output 為 30,849，其中 reasoning 為 19,649。這組生成用量不含 compact 的 input/output，compact 另按回傳 usage 計入估算費用。

累計護欄占用 US$1.000591120，包括 main-01 的 US$0.10 預留、main-02 的所有嘗試，以及 main-03 的生成、compact 和計數行政預留；不是已核對的帳單。累計 251 次生成、16 次 compact、587 次外送、23,982,097 admitted input。費用與四小時皆未用完，但不能自行解除另一個停止界線。

前綴及新 trace 分別檢查，均未發現原生前綴或工具配對被改寫。新 trace 的 10 份 compact output 均已由後續生成完整採用；最後 16 個工具結果尚未送入下一次生成，是 e061 未完成的接續狀態，不算成功段落。前綴末端的安全 compact 與新 e052 首次請求的既有 items 完全相同；不把兩份 trace 中間的失敗 e052 接成有效歷史。

## 為什麼頻繁壓縮仍未完成

本次 e053–e061 每段開始前都呼叫 compact。e061 的完整請求計數依序為：

```text
輪前 150,394
compact 後 153,650
讀取 JD 導覽後 155,907
讀取 17 個 JD 目標後 171,410
Step compact 後 155,109
再次讀取導覽後 157,151
再次讀取 16 個 JD 目標後 172,606
下一次 compact 被累計上限拒絕，未外送
```

以上是包含指引及工具的完整請求計數；compact usage 的輸入範圍不同，不可拿兩者直接當成壓縮率。e061 共要求 35 次 `read_jd`，尚未產生 final_answer。這個截面顯示壓縮後仍接近 Step 門檻，而重新展開 JD 又觸發下一次壓縮；尚未證明模型必然陷入無限循環。

更上游的可見累積是 App 資料訊息：e061 首次生成輸入共有 61 則 `consultant_turn_reference` user 訊息，合计 215,616 字元；另有 61 則原始 user 訊息，共 4,589 字元。這些 App 訊息內重複承載 801 則歷史訪談訊息副本。字元數不是 provider tokens，但足以定位需要檢查的累積來源：每輪組裝的導覽、近期資料與執行參考，並非只有員工原話。

這次原生 compact 回傳仍保留這些 user items；這是 trace 的實測，不延伸成所有模型永遠保留全部 user 訊息的保證。OpenAI 的 [standalone compaction 契約](https://developers.openai.com/api/docs/guides/compaction#standalone-compact-endpoint)說明 output 可能包含保留項目，必須整包用作下一個窗口；不能為了得到更小窗口，任意裁剪已回傳的 canonical output。

現行 `_capture_data` 將 App 資料與員工原文一起附加至 prepared history；成功歷史由 `RoleContextHistory` 延續到下一輪。本研究只在初始保存前投影當輪參考資料，不重寫過去原生 items。因而當輪的訪談／導覽副本會進入長期原生歷史，而不只是當輪附帶一次。

下一步應先離線檢查「App 當輪參考資料如何進入及退出可壓縮歷史」與「Step 壓縮後如何保持已讀取工作的連續性」，依官方契約提出整體修正；不是直接加大 compact 次數、降低門檻或改寫評分。保持 App 資料的 user role 與不越權要求，不把改成高權限 role 當成壓縮解法。

## 已能判讀與仍不能宣稱

e053–e060 的九個回提案例已完成，可作局部語意判讀，見 [正式答覆核對](partial-probe-review.md)。e061 的成品查核未完成，不能拿 product-060 冒充 product-061。其他三組沒有輸出，不能宣稱三層 Memory 的品質或效率優於基準。

e053 時，e001–e052 員工原文仍完整出現在原生歷史的可讀 user items，也有 App 副本與 opaque 狀態。因此，早期數值回提成功不能單獨歸因於 Memory 找回了「已不在 Context 的資訊」。可以核對系統當時有讀取什麼、回答了什麼、用了多少，但長距離記憶的因果效果仍需合適的後續對照。

## 離線分析工具的限制

既有 `continuation_analysis.py` 呼叫 `analyze_main.retrievals` 時，將帶 `/responses/compact` 路徑的 `admission_stopped` 事件誤認為有 payload 的請求，出現 `KeyError: payload`；沒有寫出 stopped-analysis.json。本次改以離線投影先選 request／response，再呼叫既有用量、工具與原生接續函式，另存核對值。沒有在磁碟上過濾或修改 trace，也未為此重跑模型。這項離線工具缺口保留，與停止實驗的 compaction_limit 分開。
