# T02 待審取消最小隔離實證

日期：2026-09-09。用途：JD-R002/C03 的有限開源對照；不是套件採用或 production 授權。

## 固定來源、版本與授權材料

- 正式 npm 發布：`prosemirror-suggestion-mode@1.0.79`。
- 已讀作者 source：`davefowler/prosemirror-suggestion-mode`，commit `e61b70c3cd313979778677bb448b13c0a78cfa20`。
- 六個正式 peer 的固定版本直接取自該 source 的 `package-lock.json`：keymap 1.2.2、menu 1.2.4、model 1.25.0、state 1.4.3、transform 1.10.3、view 1.38.1。本目錄另存實際安裝 lock、發布 metadata、依賴樹。
- package／README 宣告 MIT，但既有下載 source 缺獨立 LICENSE；README 明示 WIP、仍有已知問題。此為採用前材料缺件，不能因本次研究安裝或局部通過而改判。
- 僅在本目錄安裝；停用 install scripts，不改其他 node_modules 或 runtime，不用 T01，不呼叫模型、不連 DB、不做廣搜。

## 安裝前固定的三組範圍

A. 兩個互不重疊 pending，以明確 fixture 位置及原生 transaction 建立 A／B；doc JSON 寫檔，再以該 JSON 建立新的 EditorState／plugin；用套件 range reject 取消 A，檢查 A 原文、B 全文及 pending marks 是否保留。不得用撤銷歷史或自建 before-image 恢復。

B. 同一 A 依序 AI → 人工 → AI 續改，作者及階段由 transaction metadata 表示；保存 JSON、新 EditorState 後分別觀察套件取消／接受的實際結果。不自行重建原文，不重新分配 marks 以修補套件，也不發明跨範圍群組引擎。

C. 必要正文格式（包括有屬性的 link）及 JD node attrs 修改，記錄 actual step type，觀察是否追蹤、JSON 保存及取消後恢复；純文字通過不能替代 attrs／marks 驗證。

位置來自固定 fixture 及當前文件明確節點，不用有 first-match 疑點的 applySuggestion helper。允許讀 doc marks 決定本例套件 range command 的目前範圍；不把這項有限接線宣稱為原生 groupId API。

## 記錄與停止條件

- 第一個缺口保存完整輸入、交易 steps、輸出／例外，不修 vendor、不增加 diff／history／group engine 以湊全綠。仍可完成三組中獨立的觀察，最多三組。
- 每步保留 doc JSON、套件產生的 appended transactions、pending marks／attrs；重開前後材料及檔案 hash 固定保存。
- 新 EditorState 意指從 JSON 建立全新 state／plugin，沒有沿用先前 history 或 plugin state；不是新 browser，也不宣稱完整 app 程序恢復。
- 結論不涵蓋精確模型定位、LLM、DOM／IME、任意相依群組、通用 block move／split、DB 原子性、production schema 或已接受歷史回退。
- 尚未執行時不預填通過。正式結果以 `results/` 原始輸出及執行日誌為準。

## 執行前置紀錄

第一次執行在 probe 自建 schema 初始化失敗：`paragraph+` 為必要內容而 paragraph `id` 無 default，ProseMirror 拒絕 non-generatable node。尚未進入 A／B／C，不能列為 suggestion plugin 失敗。只將 schema 的 id default 設為 null；三個實際 fixture 的 id 仍全部明確提供且不變。原腳本保留於 `results/first-run-schema-error-probe.mjs`，原日誌為 `results/probe-first-run.log`；沒有修 vendor。
