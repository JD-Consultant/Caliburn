/* Generated from apps/api/contracts; do not edit. */

/**
 * App-produced successful candidate write results. This output is not a provider-strict arguments schema. Status-only branches do not echo inputs; updated branches report the actual title, description and effects, never publication, internal scope or an unknown save outcome.
 */
export type MemoryWriteResult =
  MemoryWriteStatusResult | WorkSituationUpdatedResult | WorkUnderstandingUpdatedResult;

/**
 * A reliably adopted creation/deletion or a confirmed absence of actual differences. Unknown save outcomes and rejections are not successful statuses.
 */
export interface MemoryWriteStatusResult {
  status: 'created' | 'deleted' | 'unchanged';
}
export interface WorkSituationUpdatedResult {
  status: 'updated';
  /**
   * Actual title after the adopted update; use it for later selections.
   */
  title: string;
  /**
   * Actual navigation description after the adopted update.
   */
  description: string;
  /**
   * Only actual changes in this layer. Omit unmodified fields and unchanged reference sides; never use empty arrays or null placeholders. No silent truncation.
   *
   * @minItems 1
   * @maxItems 4
   */
  applied_changes:
    | [
        | MemoryTextAppliedChange
        | MemoryBodyAppliedChange
        | InterviewReferencesAdded
        | InterviewReferencesRemoved
        | InterviewReferencesChanged
      ]
    | [
        (
          | MemoryTextAppliedChange
          | MemoryBodyAppliedChange
          | InterviewReferencesAdded
          | InterviewReferencesRemoved
          | InterviewReferencesChanged
        ),
        (
          | MemoryTextAppliedChange
          | MemoryBodyAppliedChange
          | InterviewReferencesAdded
          | InterviewReferencesRemoved
          | InterviewReferencesChanged
        )
      ]
    | [
        (
          | MemoryTextAppliedChange
          | MemoryBodyAppliedChange
          | InterviewReferencesAdded
          | InterviewReferencesRemoved
          | InterviewReferencesChanged
        ),
        (
          | MemoryTextAppliedChange
          | MemoryBodyAppliedChange
          | InterviewReferencesAdded
          | InterviewReferencesRemoved
          | InterviewReferencesChanged
        ),
        (
          | MemoryTextAppliedChange
          | MemoryBodyAppliedChange
          | InterviewReferencesAdded
          | InterviewReferencesRemoved
          | InterviewReferencesChanged
        )
      ]
    | [
        (
          | MemoryTextAppliedChange
          | MemoryBodyAppliedChange
          | InterviewReferencesAdded
          | InterviewReferencesRemoved
          | InterviewReferencesChanged
        ),
        (
          | MemoryTextAppliedChange
          | MemoryBodyAppliedChange
          | InterviewReferencesAdded
          | InterviewReferencesRemoved
          | InterviewReferencesChanged
        ),
        (
          | MemoryTextAppliedChange
          | MemoryBodyAppliedChange
          | InterviewReferencesAdded
          | InterviewReferencesRemoved
          | InterviewReferencesChanged
        ),
        (
          | MemoryTextAppliedChange
          | MemoryBodyAppliedChange
          | InterviewReferencesAdded
          | InterviewReferencesRemoved
          | InterviewReferencesChanged
        )
      ];
}
/**
 * The actual new value is already at the result root.
 */
export interface MemoryTextAppliedChange {
  field: 'title' | 'description';
}
export interface MemoryBodyAppliedChange {
  field: 'body';
  /**
   * Observed difference formed from actual before/after body content, including the applied location and necessary context. Not an unconditional echo of requested hunks or another command.
   */
  diff: string;
}
export interface InterviewReferencesAdded {
  field: 'interview_references';
  /**
   * @minItems 1
   */
  added: [number, ...number[]];
}
export interface InterviewReferencesRemoved {
  field: 'interview_references';
  /**
   * @minItems 1
   */
  removed: [number, ...number[]];
}
export interface InterviewReferencesChanged {
  field: 'interview_references';
  /**
   * @minItems 1
   */
  added: [number, ...number[]];
  /**
   * @minItems 1
   */
  removed: [number, ...number[]];
}
export interface WorkUnderstandingUpdatedResult {
  status: 'updated';
  /**
   * Actual title after the adopted update; use it for later selections.
   */
  title: string;
  /**
   * Actual navigation description after the adopted update.
   */
  description: string;
  /**
   * Only actual changes in this layer. Omit unmodified fields and unchanged reference sides; never use empty arrays or null placeholders. No silent truncation.
   *
   * @minItems 1
   * @maxItems 4
   */
  applied_changes:
    | [
        | MemoryTextAppliedChange
        | MemoryBodyAppliedChange
        | WorkSituationReferencesAdded
        | WorkSituationReferencesRemoved
        | WorkSituationReferencesChanged
      ]
    | [
        (
          | MemoryTextAppliedChange
          | MemoryBodyAppliedChange
          | WorkSituationReferencesAdded
          | WorkSituationReferencesRemoved
          | WorkSituationReferencesChanged
        ),
        (
          | MemoryTextAppliedChange
          | MemoryBodyAppliedChange
          | WorkSituationReferencesAdded
          | WorkSituationReferencesRemoved
          | WorkSituationReferencesChanged
        )
      ]
    | [
        (
          | MemoryTextAppliedChange
          | MemoryBodyAppliedChange
          | WorkSituationReferencesAdded
          | WorkSituationReferencesRemoved
          | WorkSituationReferencesChanged
        ),
        (
          | MemoryTextAppliedChange
          | MemoryBodyAppliedChange
          | WorkSituationReferencesAdded
          | WorkSituationReferencesRemoved
          | WorkSituationReferencesChanged
        ),
        (
          | MemoryTextAppliedChange
          | MemoryBodyAppliedChange
          | WorkSituationReferencesAdded
          | WorkSituationReferencesRemoved
          | WorkSituationReferencesChanged
        )
      ]
    | [
        (
          | MemoryTextAppliedChange
          | MemoryBodyAppliedChange
          | WorkSituationReferencesAdded
          | WorkSituationReferencesRemoved
          | WorkSituationReferencesChanged
        ),
        (
          | MemoryTextAppliedChange
          | MemoryBodyAppliedChange
          | WorkSituationReferencesAdded
          | WorkSituationReferencesRemoved
          | WorkSituationReferencesChanged
        ),
        (
          | MemoryTextAppliedChange
          | MemoryBodyAppliedChange
          | WorkSituationReferencesAdded
          | WorkSituationReferencesRemoved
          | WorkSituationReferencesChanged
        ),
        (
          | MemoryTextAppliedChange
          | MemoryBodyAppliedChange
          | WorkSituationReferencesAdded
          | WorkSituationReferencesRemoved
          | WorkSituationReferencesChanged
        )
      ];
}
export interface WorkSituationReferencesAdded {
  field: 'work_situation_references';
  /**
   * @minItems 1
   */
  added: [string, ...string[]];
}
export interface WorkSituationReferencesRemoved {
  field: 'work_situation_references';
  /**
   * @minItems 1
   */
  removed: [string, ...string[]];
}
export interface WorkSituationReferencesChanged {
  field: 'work_situation_references';
  /**
   * @minItems 1
   */
  added: [string, ...string[]];
  /**
   * @minItems 1
   */
  removed: [string, ...string[]];
}
