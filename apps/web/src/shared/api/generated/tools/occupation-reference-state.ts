/* Generated from apps/api/contracts; do not edit. */

/**
 * 目前職務可見的公版參考與明確不負責的工作範圍；獨立保存、不進向量查詢，也不宣告完整度。
 */
export interface OccupationReferenceState {
  /**
   * null 尚未選擇；[] 已看過但無適合參考。
   */
  selected_reference_ids: string[] | null;
  /**
   * 員工明確否認的實際工作範圍，用於避免重問；不是整份公版排除或 JD 完成標記。
   */
  excluded_work: string[];
}
