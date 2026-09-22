# T02 三組固定情境結果

2026-09-09；功能 run：`results/run-20260909T144514Z/`。`node probe.mjs` 結束碼 **2**，表示保留缺口，不是全綠。沒有修改 vendor 或新增修訂／history／group engine。

| 組別 | 實際結果 | 限定結論 |
|---|---|---|
| A：兩個獨立 pending | 通過。兩段 native ReplaceStep 建立 A／B，doc JSON 寫檔 → 全新 EditorState／plugin，套件 range reject A 恢復原文，B 的完整節點 JSON（文字、pending marks、attrs、sourceRefs）不變 | 此固定、不重疊且各自連續的文字範圍可分別取消；不是原生 groupId command 或任意相依群組保證 |
| B：同一 A，AI → 人工 → AI | 通過。`每月檢查一次` → `每週檢查一次` → `每週檢查兩次` → `每週巡檢兩次`；JSON 重開後取消恢復初始原文，接受保留最後文字；pending 清除 | 本例在現有 insertion mark 內續改成立；AI／人工是 deterministic transaction 的作者標記，沒有模型呼叫。原生 mark 仍保留初次 AI 的 username／stage，不是完整逐次作者紀錄 |
| C：link href／title | 有 pending 且 JSON 重開保留；接受得到新版 link 與正確正文。但取消得到 `參閱設備手冊設備手冊。`：第一份文字有原 link，第二份無 link，造成重複 | 第一個實際套件缺口。單次 `tr.addMark` 更新同型 link 實際產生 **RemoveMarkStep + AddMarkStep**，不是單一 AddMarkStep。未修補 |
| C：JD node scope attr | `tr.setNodeAttribute` 實際為 **AttrStep**。`applyTransaction` 在套件處理 `step.from`／`step.to` 的 slice 路徑拋 `RangeError: Position undefined out of range` | 沒有成功返回新 state，因此未進入 JSON 重開／取消。不把 requested transaction 的已變值文件當成功提交，不據此宣稱任何保存原子性 |

三組共同限制：沒有 DOM／IME、模型定位、LLM 接線、DB、新 browser／新作業系統程序、任意相依群組或已接受歷史回退驗證；沒有把必要 attrs 靜默排除。以固定 fixture 節點及唯一已知文字取得位置，不走套件的 first-match `applySuggestion` helper。groupId 只存在套件允許的 transaction metadata；probe 讀 marks 決定套件 range command 的範圍，遇到其中含別组即拒絕，不代替套件復原原文。

## 證據與前置失敗

- 主要原始結果：`results/run-20260909T144514Z/report.json`。
- 逐步 before／requested steps／appended transactions／after／exception：同目錄 A、B、C 三個 JSON。
- 各組重開前 doc JSON、取消／接受後完整 doc JSON 均保存；C AttrStep 的 requestedDoc 與 callerStateAfterThrow 在 C trace 中，沒有冒稱已套用。
- report SHA-256：`cf52931703b94c36204f3b588ecbbb3d39a206f4dd416df2fda4b3d74bcb60e5`。
- 實際執行的發布 ESM bundle `node_modules/prosemirror-suggestion-mode/dist/index.js` SHA-256：`ccaaaf5d181c1fbc7bfab99f98218a2e9febdacd136f16a41c7ee864adbf9a6f`。
- report 中固定的 4 個輸入檔與 12 個結果 artifact hash 已重新唯讀核對一致；完整保存清單另見 `results/evidence-manifest.json`。
- 安裝先遇到 only-if-cached，再遇 sandbox proxy ECONNREFUSED；日誌保留。經既有研究授權下載固定發布，使用 `--ignore-scripts --no-audit --no-fund --workspaces=false`，cache 也在本目錄。
- 第一個程式執行只在自建 schema 初始化失敗：required paragraph 帶無 default 的 id，尚未進入套件功能。只補 id default null，實際 fixture id 不變；初版原碼、錯誤、exit 1 均保留。此後僅一輪功能 run，exit 2；沒有修 vendor／反覆調 fixture 湊通過。

## 真正安裝依賴與授權限定

Node v22.12.0；正式發布 `prosemirror-suggestion-mode@1.0.79`，MIT 為 package／README 宣告。實際發布樹同樣沒有獨立 LICENSE，README 保留 WIP。此採用前材料缺件不因研究結果消失。

六個直接 peer 由既有作者 source lock 固定：`prosemirror-keymap@1.2.2`、`prosemirror-menu@1.2.4`、`prosemirror-model@1.25.0`、`prosemirror-state@1.4.3`、`prosemirror-transform@1.10.3`、`prosemirror-view@1.38.1`。

另由正式依賴範圍解析並鎖定六個 transitive packages：`crelt@1.0.7`、`orderedmap@2.1.1`、`prosemirror-commands@1.7.2`、`prosemirror-history@1.5.0`、`rope-sequence@1.3.4`、`w3c-keyname@2.2.8`。它們不是另選 peer；完整 integrity／resolved 见 package-lock 与 `results/dependency-tree.json`。history 為 menu 的安裝依賴，本實驗沒有把 history plugin 掛入 EditorState。沒有 jsdom、額外測試框架或自建 parser。

結論：T02 對「待審文字取消」比先前只列底座／未知更具體，A／B 本例已實證；但必要 mark attrs 與 node attrs 的原生追蹤／取消仍有反例，因此不足以翻成完整 JD 原生首選或採用決策。
