/* Generated from apps/api/contracts; do not edit. */

/**
 * App 固定工作與可見範圍內，員工明確表示不負責的工作；不包含公版選擇或來源定位。
 */
export interface ExcludedWorkView {
  /**
   * 用於避免把未負責的工作補回 Memory；不是原話引用或完成判定。
   */
  excluded_work: string[];
}
