# P3 首例 C-W 校準資料包

版本1；2026-09-10。**公開 calibration／已曝光／非 held-out；0次自然trial、0次模型執行、0項實測結果。** 本包只把已接受[品質材料](../../2026-09-10-jd-product-quality-acceptance.md)§5 C-W及§6零付費準備第2／4項拆成可使用材料，不新增雇主事實或改rubric。

## 內容與存取

- [employee-card.md](employee-card.md)：人員扮演卡，開場與W01–W10；W05晚期查證、M-W1純手改／後續澄清分開。
- [release-protocol.md](release-protocol.md)：依自然追問揭露、事件界線及空揭露紀錄；非固定問卷／工具腳本。
- [oracle.md](oracle.md)：供判讀者的獨立語意支持／排除與Q01–15映射。被測顧問不得讀oracle；卡／程序亦不整份入prompt，只送實際回答。
- [results-template.md](results-template.md)：空trial／逐輪／逐request／逐Q／首敗帳本，不含虛構結果。
- [manifest.json](manifest.json)：本包版本、來源hash、曝光、執行限制及各檔SHA256；不hash自己。hash僅核內容未變，不證保密／未見。

全為既有合成零件倉儲收發員設定，不含真實姓名／雇主／客戶資料。O*NET只曾幫原作者核職業合理性，不是本人的事實來源。沒有混用CT49／r2／C-M／C-S，也沒有製作其他6次P6未見案例。

## 執行尚未授權

首批提案仍是**最多180次provider requests、12個員工回合、US$1.00硬上限：NOT AUTHORIZED**。CT49–51舊授權不沿用。此包沒有金鑰、provider連線、模擬員工LLM、judge或任何推論執行；準備材料不等於批准執行。

先等核心Task1–6完成，再凍結exact commit／lock／prompt／Skill／schema hashes、實際model ID／high／8192／既有額度及compaction。這些runtime值目前標待定，不假填。另須具體付費授權、當日實際provider費率、所有在途保留與逐請求最壞費用guard、離線拒provider／拒超限證據，以及空JD／訪談／Memory的隔離trial起點；本包未完成這些工程前置。

獲授權後，人員按自然追問扮演，記實際揭露子內容；晚期更正與手改分開，不提示工具路徑、不強制Memory整併。到任一上限或無法對帳即停，不增cap／續費。自然未觸發的背景未整併／compaction效果如實NOT_OBSERVED。

已揭露才判內容漏寫；未追到重要工作判訪談廣度不足。允許合理措辭／分組，oracle不當唯一golden JD。Q01–15適用且觸發項須各有證據，不計總分、不挑最好一次、不把工程／自然／真人效果混用。

## 曝光與準備限制

C-W在原品質材料公開時已曝光給研究／實作流程，本包建立又供Codex準備者及主工作單位核對；不是封存未見資料，未來不可改名成held-out。作者／判读者是否獨立，實際trial另記；本輪沒有假稱獨立實測評讀。

本包只完成材料拆分與靜態核對，**未完成自然揭露演練、判定者校準、執行guard或P3**。文件有歧義時回查原材料、由主工作單位處理；不加新公司設定補答案。
