/* Generated from apps/api/contracts; do not edit. */

export interface UpdateExcludedWorkArguments {
  /**
   * 新增的工作範圍文字，依員工明確表示沒做或不負責的內容填寫；沒有新增時填 []。完整文字去重，不得與 remove 有相同文字。
   *
   * Items: 一筆完整範圍文字，須含非空白內容且不含 NUL；系統保留原文字，不自動修剪空白。
   */
  add: string[];
  /**
   * 要解除的舊範圍，逐筆原樣取自目前 state 的 excluded_work；須完整精確命中，不能只填關鍵字。沒有移除時填 []；add 與 remove 不可同時為空。
   *
   * Items: 一筆完整範圍文字，須含非空白內容且不含 NUL；系統保留原文字，不自動修剪空白。
   */
  remove: string[];
}
