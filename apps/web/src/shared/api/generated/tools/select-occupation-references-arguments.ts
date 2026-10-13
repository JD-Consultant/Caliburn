/* Generated from apps/api/contracts; do not edit. */

export interface SelectOccupationReferencesArguments {
  /**
   * 本次要保留的全部公版 reference_id，取自搜尋、讀取或已選 state；不能填 task_id 或公版名稱。完整取代舊集合，要保留的舊 ID 一併列入，重複 ID 去重；[] 清空選用並表示已選擇但沒有適合參考，不接受 null。
   *
   * Items: 一份公版的精確 reference_id，使用工具或已選 state 提供的值。
   */
  reference_ids: string[];
}
