/* Generated from apps/api/contracts; do not edit. */

/**
 * Revise one work understanding in this batch's unpublished candidate. Short fields take complete new values; body takes V4A hunks; references take only the requested add/remove sides. Use at most one entry per field; omitted fields and reference members stay unchanged. The App binds the original object before any rename. All content and reference changes succeed or fail together, without publishing Memory. Invalid or ambiguous patches require corrected context, not an unchanged retry.
 */
export interface UpdateWorkUnderstandingArguments {
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
        | AddWorkSituationReferences
        | RemoveWorkSituationReferences
        | ChangeWorkSituationReferences
      ]
    | [
        (
          | MemoryTextChange
          | MemoryBodyChange
          | AddWorkSituationReferences
          | RemoveWorkSituationReferences
          | ChangeWorkSituationReferences
        ),
        (
          | MemoryTextChange
          | MemoryBodyChange
          | AddWorkSituationReferences
          | RemoveWorkSituationReferences
          | ChangeWorkSituationReferences
        )
      ]
    | [
        (
          | MemoryTextChange
          | MemoryBodyChange
          | AddWorkSituationReferences
          | RemoveWorkSituationReferences
          | ChangeWorkSituationReferences
        ),
        (
          | MemoryTextChange
          | MemoryBodyChange
          | AddWorkSituationReferences
          | RemoveWorkSituationReferences
          | ChangeWorkSituationReferences
        ),
        (
          | MemoryTextChange
          | MemoryBodyChange
          | AddWorkSituationReferences
          | RemoveWorkSituationReferences
          | ChangeWorkSituationReferences
        )
      ]
    | [
        (
          | MemoryTextChange
          | MemoryBodyChange
          | AddWorkSituationReferences
          | RemoveWorkSituationReferences
          | ChangeWorkSituationReferences
        ),
        (
          | MemoryTextChange
          | MemoryBodyChange
          | AddWorkSituationReferences
          | RemoveWorkSituationReferences
          | ChangeWorkSituationReferences
        ),
        (
          | MemoryTextChange
          | MemoryBodyChange
          | AddWorkSituationReferences
          | RemoveWorkSituationReferences
          | ChangeWorkSituationReferences
        ),
        (
          | MemoryTextChange
          | MemoryBodyChange
          | AddWorkSituationReferences
          | RemoveWorkSituationReferences
          | ChangeWorkSituationReferences
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
   * V4A body-update hunks with enough real context for one qualified location; no file paths, Add File or Delete File operations. The editor validates all hunks, uniqueness and resulting content.
   */
  diff: string;
}
export interface AddWorkSituationReferences {
  field: 'work_situation_references';
  /**
   * Select exact visible work-situation titles already provided by the App. Preserve whitespace, case and Unicode. The domain resolves candidate identities and deduplicates repeated selections; a relationship is not a version confirmation.
   *
   * @minItems 1
   */
  add: [string, ...string[]];
}
export interface RemoveWorkSituationReferences {
  field: 'work_situation_references';
  /**
   * Select exact visible work-situation titles already provided by the App. Preserve whitespace, case and Unicode. The domain resolves candidate identities and deduplicates repeated selections; a relationship is not a version confirmation.
   *
   * @minItems 1
   */
  remove: [string, ...string[]];
}
export interface ChangeWorkSituationReferences {
  field: 'work_situation_references';
  /**
   * Select exact visible work-situation titles already provided by the App. Preserve whitespace, case and Unicode. The domain resolves candidate identities and deduplicates repeated selections; a relationship is not a version confirmation.
   *
   * @minItems 1
   */
  add: [string, ...string[]];
  /**
   * Select exact visible work-situation titles already provided by the App. Preserve whitespace, case and Unicode. The domain resolves candidate identities and deduplicates repeated selections; a relationship is not a version confirmation.
   *
   * @minItems 1
   */
  remove: [string, ...string[]];
}
