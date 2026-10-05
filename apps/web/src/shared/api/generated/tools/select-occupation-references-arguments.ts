/* Generated from apps/api/contracts; do not edit. */

export interface SelectOccupationReferencesArguments {
  /**
   * 本次完整選用集合，取代舊集合；要保留的舊 reference_id 必須一起填入，不是追加。可多選；[] 表示看過但沒有適合的參考。不是認定員工職稱，也不表示未選公版的工作未做。
   */
  reference_ids: string[];
}
