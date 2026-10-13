/* Generated from apps/api/contracts; do not edit. */

/**
 * 只填 query；搜尋數量由工具固定為最多五份，不接受職務、版本、排除清單或數量參數。
 */
export interface SearchOccupationReferencesArguments {
  /**
   * 以自然語言描述員工已確認實際負責的主要工作，保留辨認工作所需的對象、行動與範圍。排除顧問問題、明確未做及尚未確認的工作；不是只填職稱或公版 ID。必須有非空白內容，最多 12,000 字元。
   */
  query: string;
}
