/* Generated from apps/api/contracts; do not edit. */

export interface ReadOccupationReferenceArguments {
  /**
   * 工具結果或已選 state 提供的精確公版定位，原樣帶回；未選公版也可讀，不猜造 ID。
   */
  reference_id: string;
  /**
   * null 讀職位概述和完整已解析任務導覽；指定導覽提供的 task_id 讀該任務全部細節。
   */
  task_id: string | null;
}
