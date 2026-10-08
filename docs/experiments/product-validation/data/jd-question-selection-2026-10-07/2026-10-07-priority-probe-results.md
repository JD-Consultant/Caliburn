# 選問優先順序：單段替換的隔離實測

本批保留原件收於[私人 ZIP](https://github.com/JD-Consultant/Caliburn-archives/releases/download/storage-2026-10-08/caliburn-selected-c-evidence-20261008.zip)；各原件的包內路徑見連結標題或下文。按需取回方式見[私人歷史材料與資料庫封存](../../../artifact-storage.md#私人歷史材料與資料庫封存)。

**狀態：二十四案完成，全部匿名評閱先鎖後解盲；本候選未證改善，未採用。** 日期：2026-10-07。這是筆記工具修復及[八案核心比較](../../interview-plan-comparison-2026-10-07/results.md)完成後的獨立候選試驗，不改核心比較的品質判讀或帳務終態。候選只替換一段選問說明，沿[凍結協議](2026-10-07-priority-candidate-protocol.md)與[接線](priority-probe-README.md)；兩組皆不啟用筆記，production 選問指引未切換。

## 有限窗口的結果

十二個探索案中，原指引 B0 與候選 B1 **各有 1／6 案直接中立問到目標**；相關但不等同目標的探索分別 1／6、2／6。取得目標回答並正確有限入稿，B0 為 1／6、B1 為 0／6。B1 的直接目標問句出現在末問，沒有後續回答；不能寫成「完全沒問」或推論完整訪談永遠無法取得。

每案最多三次顧問回覆，只有前兩個問句可取得後續條件回答；末問仍評是否中立、具體及合理，但未答不當成已取得或已入稿。上述比例分開量測，不是完整 JD 的成功率，也沒有統計顯著或真人負擔結論。本窗口未證候選改善，因此不切換 production、不另加條件清單。

第一輪旺季 B0 問「您的收貨量會不會在某些時段或季節特別集中？若會，通常會怎麼安排收貨和上架？」取得員工原話 `b630f098-4841-4e9c-988e-4af57d8f3fd4`：月底／促銷前進貨量增加、來不及上架，排程者及本人調整權仍未知。正式收貨要求有據保存量增及延誤，沒有新增本人排程權。B1 則中立問十二月財務盤點負荷，實際回答未知；這是合理相關問題，不能借它當成已問或取得收貨量目標。

B1 第一輪旺季另有獨立品質錯誤：將已確認「收不收或退不退由採購決定」及「本人不決定調整庫存」，擴寫成「收貨或退貨及庫存調整由採購決定」。原話沒有指派庫存調整決定權，附引用也不能補足這一步推論。此錯誤與未取得目標分開記，不能被成功率掩蓋。

[全部二十四份匿名評閱鎖（私人 ZIP）](https://github.com/JD-Consultant/Caliburn-archives/releases/download/storage-2026-10-08/caliburn-selected-c-evidence-20261008.zip "包內：caliburn-intplan-comparison/question-priority-probe/quality-lock-all-24.json") SHA256 `8803b0294a2aa84b1b2287d173aa635c99532fc5367297beb9f6314dd28381b8` 記鎖定時主代理未讀正文；[解盲映射（私人 ZIP）](https://github.com/JD-Consultant/Caliburn-archives/releases/download/storage-2026-10-08/caliburn-selected-c-evidence-20261008.zip "包內：caliburn-intplan-comparison/question-priority-probe/deblind-mapping-all-24.json")只在全部鎖定後建立，末段 path clarification 與原報告一併鎖定，未覆寫原判讀。

## 十二組配對與界線

十二個界線案均未等義重問未知／拒答，或把已排除退貨反轉成本人責任，核心行為維持 12／12；但四個退貨排除案均未完整保存正式分工明文及直接引用，完整保存為 0／4。行為克制不能代替事實保存，未知案亦有起始稿既存引用限制。

| 條件／重複 | 原指引 B0 | 候選 B1 | 重要差異與限制 |
|---|---|---|---|
| 冷藏 r1 | 未問目標，無回答／入稿 | 末問直接中立，未答／未入稿 | B1 已知單位未利用、範圍重確認；流程與引用限制另列。 |
| 冷藏 r2 | 未問目標，無回答／入稿 | 末問相關現場要求，未直接問場所，未答 | B1 已知單位未利用、「唯一」過早收束；兩案流程合併支持有限。 |
| 錯儲位 r1 | 未問差錯目標，無回答／入稿 | 未問差錯目標，無回答／入稿 | 兩案其他問題有合理用途，掃描與儲位權限維持；不以詞彙出現計探索。 |
| 錯儲位 r2 | 未問差錯目標，無回答／入稿 | 未問差錯目標，無回答／入稿 | 異常紀錄、搬運及基本資料是不同合理缺口。 |
| 旺季 r1 | 收貨量目標取得並有限入稿 | 年度盤點負荷已問未知 | B1 另有無據採購庫存調整決定權，與取證差異分開記。 |
| 旺季 r2 | 盤點負荷已問未知 | 未問負荷目標 | 均無收貨目標入稿；B1「沒有必須再追問的缺口」過早收束。 |
| 已知未知 r1 | 停止等義追問，轉登記；新問未答 | 同左 | 正式未知保留；未知與停止原話的直接引用仍有起始限制。 |
| 已知未知 r2 | 轉問上架安排來源；新問未答 | 轉問登記依據；新問未答 | 均遵守界線；已鎖補充只修正欄位路徑縮寫。 |
| 拒答 r1 | 尊重拒答，正式稿不變 | 尊重拒答，有據整理既有內容 | 末問均未答，整理不能當新資訊取得。 |
| 拒答 r2 | 尊重拒答，有據整理 | 尊重拒答，正式稿不變 | B0 另問稍預設、缺否認退路；保留原判措辭差異。 |
| 非本人職責 r1 | 不加入／重問退貨；有據整理 | 同左 | 均缺完整正式退貨分工與引用；範圍重確認疑慮仍在。 |
| 非本人職責 r2 | 問其他固定工作，未答 | 問相關負荷，未答 | 均尊重排除但正式保存有限；B1「最忙」稍預設。 |

[已鎖品質彙整（私人 ZIP）](https://github.com/JD-Consultant/Caliburn-archives/releases/download/storage-2026-10-08/caliburn-selected-c-evidence-20261008.zip "包內：caliburn-intplan-comparison/question-priority-probe/operational-evidence/locked-quality-synthesis.md") SHA256 `38897d8b245090cdd87752dd3611384db0222190e1bce7a54524bedaaf87651d`；[二十四案索引與必要來源（私人 ZIP）](https://github.com/JD-Consultant/Caliburn-archives/releases/download/storage-2026-10-08/caliburn-selected-c-evidence-20261008.zip "包內：caliburn-intplan-comparison/question-priority-probe/operational-evidence/locked-quality-synthesis.json") SHA256 `5a6f9f331cec570b6b35d669dc75b5728e44ee24983138c7e16100cc4e2ec076`。48 個實際問句唯一對回 consultant source ID，89 個必要正式欄位／值已核；彙整不修改或重評 primary。

## 完成與接續

最終二十四個 logical trial 全部完成，共 48 次完整樣本回覆與一個中斷回覆，合計 49 次實際回覆。二十四份正式 JD、員工原話及匿名評閱皆保存；全部判讀鎖定後才解盲。未完成案保留為中斷原件，不作完整品質樣本。

第一批完成五個 logical trial，取得 16 次實際顧問回覆，其中一個回覆屬未完成的第六案。續跑另完成十九案、33 次回覆，原五案機械保留；沒有因品質判讀選樣。

第一批因原 08:30:34 UTC 時間截止而停止。使用者隨後明確指示「不用管截止」，取消絕對及經過時間截止，保留原有費用、tokens、requests、模型、固定案例與候選。續跑只補十九個未完成 logical trial；中斷案另建空白隔離資料重做，不重放舊員工回答、不挑選品質較好的版本。

原計畫二十四案最多 48 次完整試驗回覆，加已發生中斷回覆一個，完整接續的實際上限為 49；中斷消耗全部計入原累計。一次語意裁決等待仍有界，逾時停下，不自動重試。

## 費用與來源界線

第一批終態 spent US$2.016560225、occupied US$2.064305725，1,796 generations／14 compact／3,973 outbound／91,281,083 counted input。這是承接核心比較、舊失敗與短測的累計，不能當五案自身費用。三筆未知預留共 US$0.047745500 全部保留。

最終累計 spent US$2.100509695、occupied US$2.148255195，1,911 generations／14 compact／4,217 outbound／93,522,696 counted input，stop reason 為 null；三筆未知預留仍為 US$0.047745500。本 probe 新增估算 US$0.133723300，173 generations／370 outbound／3,429,314 counted input／0 compact，包含中斷回覆；沒有將其成本從帳務刪除。

本 probe 累計 occupied 上限固定 US$2.514531895；累計 generations／outbound／counted input／compact 上限固定為 1,994／4,447／106,093,382／22，同時受原全域上限限制。取消時間不重置增量額度或未知預留。173 個准入生成皆有對應 received，197 個計數 calls 的保守估計費用亦已納入；usage 換算與預留不是 provider 發票。[最終帳務與完整性核對（私人 ZIP）](https://github.com/JD-Consultant/Caliburn-archives/releases/download/storage-2026-10-08/caliburn-selected-c-evidence-20261008.zip "包內：caliburn-intplan-comparison/question-priority-probe/operational-evidence/final-accounting-and-integrity.json")

- [原凍結 manifest（私人 ZIP）](https://github.com/JD-Consultant/Caliburn-archives/releases/download/storage-2026-10-08/caliburn-selected-c-evidence-20261008.zip "包內：caliburn-intplan-comparison/question-priority-probe/priority-probe-after-repair-v1/manifest.json")，SHA256 `dd1a6db33b0ea582617b7202ce1c46fb3aafadabf03bcfffdaed48fd561b9237`。
- [第一批終態（私人 ZIP）](https://github.com/JD-Consultant/Caliburn-archives/releases/download/storage-2026-10-08/caliburn-selected-c-evidence-20261008.zip "包內：caliburn-intplan-comparison/question-priority-probe/priority-probe-after-repair-v1/final-ledger.json")，SHA256 `3053780855ec46e8c56606d18300331dd57f52573ddb2f8f860e116200317eaf`。
- [使用者取消時間與承接界線（私人 ZIP）](https://github.com/JD-Consultant/Caliburn-archives/releases/download/storage-2026-10-08/caliburn-selected-c-evidence-20261008.zip "包內：caliburn-intplan-comparison/question-priority-probe/time-limit-revocation-user-receipt.json")，SHA256 `a0f24a1b21752c3dc232f68493308dff641121ae833b0f08573ecffb59de50a4`。

問到但回答未知、末問未答與根本沒問分開；單案取得回答不等於候選穩定改善，短段試驗也不代替高品質完整 JD 的長訪談驗收。

## 披露、保存與關閉

四份獨立來源稽核累計 **48／48 accepted source ID/body、24／24 已提交 question→decision→POST→正式 body** 一致；裁決為 unknown 22、normal clarification 1、target answer 1，未見確定的披露政策違反。最後未回答問句沒有生成下一次選擇，十二個 max-1 界線 trial 沒有外部裁決屬預期。舊 partial 的未裁決問句沒有補送。

稽核按當次 source IDs 檢驗；十處在最終快照重算 `eligible_sources` 會納入較晚同文 unknown 的歧義，全部單列，沒有冒充當次錯存或多送來源。保存、裁決接線一致也不代替 JD 語意或引用品質。

- [初始五案來源稽核（私人 ZIP）](https://github.com/JD-Consultant/Caliburn-archives/releases/download/storage-2026-10-08/caliburn-selected-c-evidence-20261008.zip "包內：caliburn-intplan-comparison/question-priority-probe/operational-evidence/initial-five-source-audit.md")。
- [續跑首七案（私人 ZIP）](https://github.com/JD-Consultant/Caliburn-archives/releases/download/storage-2026-10-08/caliburn-selected-c-evidence-20261008.zip "包內：caliburn-intplan-comparison/question-priority-probe/operational-evidence/resume-first-seven-source-audit.md")、[第二輪首二案（私人 ZIP）](https://github.com/JD-Consultant/Caliburn-archives/releases/download/storage-2026-10-08/caliburn-selected-c-evidence-20261008.zip "包內：caliburn-intplan-comparison/question-priority-probe/operational-evidence/resume-r2-first-two-source-audit.md")、[第二輪最後十案（私人 ZIP）](https://github.com/JD-Consultant/Caliburn-archives/releases/download/storage-2026-10-08/caliburn-selected-c-evidence-20261008.zip "包內：caliburn-intplan-comparison/question-priority-probe/operational-evidence/resume-r2-final-ten-source-audit.md")。
- [續跑最終 ledger（私人 ZIP）](https://github.com/JD-Consultant/Caliburn-archives/releases/download/storage-2026-10-08/caliburn-selected-c-evidence-20261008.zip "包內：caliburn-intplan-comparison/question-priority-probe/priority-probe-resume-after-revocation-v1/final-ledger.json")，SHA256 `3a8560948c31f4fc3d0c69f08d5a144642351141a90d46cb345ff5a157b3249e`。
- [資源關閉（私人 ZIP）](https://github.com/JD-Consultant/Caliburn-archives/releases/download/storage-2026-10-08/caliburn-selected-c-evidence-20261008.zip "包內：caliburn-intplan-comparison/question-priority-probe/operational-evidence/resource-close-receipt.json")：付費程序 exit 0，自有容器核對身分後停止；容器、volume、資料及原件保留，沒有動到其他程序。

## 接續的驗證層級

[續跑薄包裝器](priority-resume-README.md)只在實驗程序重綁時間檢查、承接帳務、保存位置與有界等待，正式 App、HTTP、Writer、SDK 仍由原 runner 負責。26 個新增離線反例及 Ruff／format 通過，包含費用與計數不重配、未知預留保留、只能機械保留完成前綴，以及 300 秒後才出現的判讀檔不可提交。原 35 個與時間無關的 probe 反例仍通過；原 prepare 反例在舊截止後會拒絕 `Absolute deadline expired`，原凍結測試未改。這些工程測試不代替真模型品質判讀。

實際續跑 manifest SHA256 為 `179396b915ce5129fbfc1921350a52de750c45b9e7bf6919c6e365440ffb67e5`，406 份來源凍結與 129 份前批原件 hash 保持不變；正式 paid prepare 為 0 key／DB／provider。續跑使用自有 PostgreSQL、ASGITransport 的正式 App HTTP route 與真 SDK；職業參考使用固定雙組一致的 fixture，沒有驗真瀏覽器或 RAG 檢索品質。[實際續跑 manifest（私人 ZIP）](https://github.com/JD-Consultant/Caliburn-archives/releases/download/storage-2026-10-08/caliburn-selected-c-evidence-20261008.zip "包內：caliburn-intplan-comparison/question-priority-probe/priority-probe-resume-after-revocation-v1/manifest.json")
