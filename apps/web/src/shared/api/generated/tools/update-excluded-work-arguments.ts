/* Generated from apps/api/contracts; do not edit. */

export interface UpdateExcludedWorkArguments {
  /**
   * 員工明確表示沒做或不負責的工作範圍；未知、沒回答或拒答不能當作沒做。不用公版職稱或任務代碼代替實際範圍。
   */
  add: string[];
  /**
   * 員工更正後解除的舊排除範圍，使用 state 中的完整精確文字。不得與 add 重疊；兩欄不能同時為空。
   */
  remove: string[];
}
