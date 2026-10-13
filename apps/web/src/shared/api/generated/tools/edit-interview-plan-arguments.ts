/* Generated from apps/api/contracts; do not edit. */

/**
 * 只提交對目前 Markdown 工作計畫的正文修改；職務、執行及保存位置由 App 綁定。
 */
export interface EditInterviewPlanArguments {
  /**
   * 對目前 plan 正文的 V4A 修改字串，不包含 Markdown 圍欄、檔名、檔案操作或 patch wrapper。每個 hunk 以獨立一行 @@ 開始；正文行第一個字元用 + 新增、- 刪除或一個空白保留上下文，其後才是正文原字元。刪除與上下文使用目前正文的完整行，保留足以唯一定位的真實上下文，各 hunk 按原文先後排列。空正文建立時，@@ 後每行新正文加 + 前綴，最後以獨立一行 *** End of File 結尾；此控制行也可限定最後 hunk 必須命中文末。@@ 與 *** End of File 不加正文前綴，不能使用數字行號的 unified diff 標頭。新增空白行是只含 + 的行；Markdown 清單原有的 - 是正文，故刪清單行以 -- 開頭、加清單行以 +- 開頭。在 JSON 字串中正確編碼換行，解碼後須為真正多行；不要送入解碼後仍含反斜線加 n 的單行文字。
   */
  diff: string;
}
