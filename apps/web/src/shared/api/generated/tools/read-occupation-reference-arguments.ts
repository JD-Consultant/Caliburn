/* Generated from apps/api/contracts; do not edit. */

/**
 * 選一份公版及可選的任務範圍；reference_id 與 task_id 都必填，讀概述／導覽時 task_id 填 null。
 */
export interface ReadOccupationReferenceArguments {
  /**
   * 原樣複製搜尋、讀取結果或 selected_reference_ids 已提供的公版定位；格式只允許英文字母、數字、底線、連字號，首字須為英文字母或數字。不是 title、ocs_code、source_sha256 或 source_file；不猜造，不以同名公版替代。未選用公版也可讀。
   */
  reference_id: string;
  /**
   * null 回公版概述及全部已解析任務導覽；否則原樣複製這份公版 units[].tasks[].task_id，回該任務全部已解析細節。格式為 u 接正整數、-t 接正整數；不要從單元順序、原件任務 code 或其他公版推算。
   */
  task_id: string | null;
}
