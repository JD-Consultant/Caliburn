# JD 按需定位施工切片（2026-09-24）

依據：[設計 §7](../specs/2026-09-24-jd-context-navigation-design.md#7-反例後的最小選擇與界線2026-09-24)、[ADR 0078](../adr/0078-current-jd-read-only-locator.md)。僅正式新 App；保留 A/B1/B2/C、Memory、JD Domain、來源與保存權責。

1. **反例與既有證據。** 保存同版全讀、逐章、局部讀的回傳量；用測試重現「無 locator、缺頁或讀甲改乙仍進 writer」。只在這些反例成立時動正式接線。已通過。
2. **同一讀取工具擴充。** JSON Schema 增唯讀 `locator`，生成 DTO；既有 `ReadService` 從 current snapshot 投影短線索、既有 codec 發 navigation ref；body read 回現有 current refs。測跨文件／跨版／cursor／不作寫入憑證；不動 DB／Agent 角色／Memory。離線測試通過。
3. **原工具會話內的讀取證明。** 只接受本輪模型可見、同版、分頁完整的可信 JD 正文；命令所有 JD refs 均須被完整讀取涵蓋。保留跨多頁／多項讀取與 compaction 後重讀。反例、獨立複核與全套回歸已通過。
4. **同稿對照與有限真模型。** 全合成同名異範圍（只給 `jd_read`、以及給全部 10 個 JD 工具）與保存 C-W 稿中的相關 Task 選擇，共 3 次有界真模型請求已通過，且後者可本機讀回正文；使用者已明確准許該份唯讀定位清單外送。仍需在完整 A 旅程驗自發定位、跨關聯擴讀、回答與恰當 JD；記實際 outbound requests、tokens、成本、命中／漏找與結果。不因工具 bytes 降低宣稱品質通過。若新路徑漏重要工作或成本反增，停止採用、保留 `current` 回退；不改 Prompt／Memory／provider 做補丁。[目前證據](../experiments/legacy-evidence/2026-09-24-jd-locator-acceptance.md)。
5. **產品收尾。** 正式 API／Web build、來源與撤回不變；完整自然訪談與專業 JD 品質仍依原 P3／Q gates 驗收。只在上述證據足夠後，更新 ADR／決策狀態；本切片不能替代完整 App PASS。
