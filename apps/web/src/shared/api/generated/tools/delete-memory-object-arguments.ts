/* Generated from apps/api/contracts; do not edit. */

/**
 * Delete one object from the tool's authorized candidate layer, not published history. The App binds role, scope, baseline and operation identity. Deleting a work situation also unlinks candidate understanding references in the same adoption without deleting understandings or exposing their contents; deleting an understanding preserves upstream sources. Success means candidate removal and its original result are reliable, not Memory publication.
 */
export interface DeleteMemoryObjectArguments {
  /**
   * Select the current exact title from this layer's map, read or successful result. Preserve whitespace, case and Unicode. The App resolves identity and binds the candidate baseline; do not invent an ID or version.
   */
  target_title: string;
}
