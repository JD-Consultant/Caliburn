/* Generated from apps/api/contracts; do not edit. */

/**
 * Revise one work situation in this batch's unpublished candidate. Short fields take complete new values; body takes V4A hunks; references take only the requested add/remove sides. Use at most one entry per field; omitted fields and reference members stay unchanged. The App binds the original object before any rename. All content and reference changes succeed or fail together, without publishing Memory. Invalid or ambiguous patches require corrected context, not an unchanged retry.
 */
export interface UpdateWorkSituationArguments {
  /**
   * Select the current exact title from this layer's map, read or successful result. Preserve whitespace, case and Unicode. The App resolves identity and binds the candidate baseline; do not invent an ID or version.
   */
  target_title: string;
  /**
   * Select only intended changes, with at most one entry per field. No null or empty reference-operation placeholders. Runtime/domain reject duplicate fields, blank content and identities selected on both sides; already-present additions are unchanged and removal must select an existing relationship.
   *
   * @minItems 1
   * @maxItems 4
   */
  changes:
    | [
        | MemoryTextChange
        | MemoryBodyChange
        | AddInterviewReferences
        | RemoveInterviewReferences
        | ChangeInterviewReferences
      ]
    | [
        (
          | MemoryTextChange
          | MemoryBodyChange
          | AddInterviewReferences
          | RemoveInterviewReferences
          | ChangeInterviewReferences
        ),
        (
          | MemoryTextChange
          | MemoryBodyChange
          | AddInterviewReferences
          | RemoveInterviewReferences
          | ChangeInterviewReferences
        )
      ]
    | [
        (
          | MemoryTextChange
          | MemoryBodyChange
          | AddInterviewReferences
          | RemoveInterviewReferences
          | ChangeInterviewReferences
        ),
        (
          | MemoryTextChange
          | MemoryBodyChange
          | AddInterviewReferences
          | RemoveInterviewReferences
          | ChangeInterviewReferences
        ),
        (
          | MemoryTextChange
          | MemoryBodyChange
          | AddInterviewReferences
          | RemoveInterviewReferences
          | ChangeInterviewReferences
        )
      ]
    | [
        (
          | MemoryTextChange
          | MemoryBodyChange
          | AddInterviewReferences
          | RemoveInterviewReferences
          | ChangeInterviewReferences
        ),
        (
          | MemoryTextChange
          | MemoryBodyChange
          | AddInterviewReferences
          | RemoveInterviewReferences
          | ChangeInterviewReferences
        ),
        (
          | MemoryTextChange
          | MemoryBodyChange
          | AddInterviewReferences
          | RemoveInterviewReferences
          | ChangeInterviewReferences
        ),
        (
          | MemoryTextChange
          | MemoryBodyChange
          | AddInterviewReferences
          | RemoveInterviewReferences
          | ChangeInterviewReferences
        )
      ];
}
export interface MemoryTextChange {
  field: 'title' | 'description';
  /**
   * Complete nonblank new value for the selected short field. The domain validates content and same-layer title uniqueness.
   */
  value: string;
}
export interface MemoryBodyChange {
  field: 'body';
  /**
   * 對目前 body 的 V4A 正文修改字串。每個 hunk 以獨立一行 @@ 開始；正文行第一個字元用 + 新增、- 刪除或一個空白保留上下文，其後才是正文原字元。刪除與上下文須使用目前正文的完整行；以實際換行為界，句號及畫面折行不會另成一行。保留足以唯一定位的真實上下文，hunks 按原文先後排列。不包含 Markdown 圍欄、SEARCH/REPLACE 標記、數字行號 unified diff 標頭、檔名或檔案 wrapper。@@ 及 *** End of File 是控制行，不加正文前綴；後者只在需限定文末時使用，並須結束整份 diff。新增空行是只含 + 的行；Markdown 原有的 - 是正文，不能丟掉。JSON 解碼後須為真正多行，不能仍是反斜線加 n 的單行字串。
   */
  diff: string;
}
export interface AddInterviewReferences {
  field: 'interview_references';
  /**
   * Select formal interview sequences already provided by the App. The domain checks source eligibility, job file and this batch's fixed upper bound; repeated selections are deduplicated by resolved identity.
   *
   * @minItems 1
   */
  add: [number, ...number[]];
}
export interface RemoveInterviewReferences {
  field: 'interview_references';
  /**
   * Select formal interview sequences already provided by the App. The domain checks source eligibility, job file and this batch's fixed upper bound; repeated selections are deduplicated by resolved identity.
   *
   * @minItems 1
   */
  remove: [number, ...number[]];
}
export interface ChangeInterviewReferences {
  field: 'interview_references';
  /**
   * Select formal interview sequences already provided by the App. The domain checks source eligibility, job file and this batch's fixed upper bound; repeated selections are deduplicated by resolved identity.
   *
   * @minItems 1
   */
  add: [number, ...number[]];
  /**
   * Select formal interview sequences already provided by the App. The domain checks source eligibility, job file and this batch's fixed upper bound; repeated selections are deduplicated by resolved identity.
   *
   * @minItems 1
   */
  remove: [number, ...number[]];
}
