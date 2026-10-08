# 倉儲兩案機制稽核

**Plan 建立、保存及後輪全文採用有實證；within-Work C 與緊接人工改稿的 Changes 讀取未觀察到。** 僅核已完成的兩案，不重評已鎖定品質。逐項行號、call ID、重放及 142 個原件雜湊見 [JSON 詳證](mechanism-audit.json)。

| 實測 | P1 | P2 |
|---|---:|---:|
| completed Turn | 20 | 20 |
| Memory completed | 30 | 31 |
| A generation | 87 | 115 |
| Plan edit | 0 | 28 |
| Plan updated／rejected | 0／0 | 27／1 |
| A compact | 1 | 2 |

P2 第 1 輪建立，另 26 次成功修改均重放；每輪結果逐字等於正式 Plan。第 2 輪局部 patch 保留「其他工作」及「全稿核對」原段落。20 輪起始 request 均符合當時 Plan 狀態（首輪 null，後 19 輪為前輪全文）；沒有主動 read Plan 呼叫。P1 全部 A 指令／工具符合凍結模板，無 Plan 正文、工具或 projection 洩漏。

P2 第 14 輪因尾 hunk 無修改收到 `invalid_patch`（trace 454／457 行）；正文未變，修正後於 464／466 行成功，間隔 73.66 秒。區間有 4 次 A request，不把全部成本歸為純重試，也不以操作恢復宣稱原意逐項完成。

三次 C 均為 pre-work：P1 接第 19 輪，P2 接第 15、17 輪。已核正式 checkpoint 與後續完整 C hash prefix；P2 在 C 後第 43、49 個零基索引項帶入前輪 Plan 全文。每次 opaque item 僅驗 hash witness。沒有 within-Work C、bound projection 或 45K 壓力解除實證。

第 10 輪後人工改稿，兩案第 11 輪均未讀 Changes。P1 第 12 輪讀到含修改的 task；P2 第 11 輪 map 已讀到修改。第 14 輪人工差異查詢皆回 0 操作，不能算讀過那次 diff。P1 後來另有三次 Changes 查訪談來源被拒。

費用沿[中斷核帳](interruption-accounting.json)：兩案分別 US$0.263589565／0.320582750。第三案為使用者中止，未知 reserve 保留，不列產品故障。全文可見、實際讀取及成功保存均不等於語意有效使用或品質改善；本稽核未呼叫 provider／DB，未改 frozen／raw。
