/* Generated from apps/api/contracts; do not edit. */

/**
 * Create one complete work situation in this batch's unpublished candidate. Supply all initial content and this layer's references; [] explicitly means no sources. Content, title uniqueness and sources must all be valid before adoption. Success is not Memory publication. The App binds scope, role, baseline and operation identity.
 */
export interface CreateWorkSituationArguments {
  /**
   * Complete nonblank title, unique among active objects in this candidate layer. Preserve the intended spelling; the domain checks uniqueness and nonblank content.
   */
  title: string;
  /**
   * Complete nonblank navigation description explaining the work scope and reading cues. Do not put source references here.
   */
  description: string;
  /**
   * Complete initial Markdown body, with known facts and unknowns distinguished. References belong in the separate reference collection, not the body.
   */
  body: string;
  /**
   * Select formal interview sequences already provided by the App. The domain checks source eligibility, job file and this batch's fixed upper bound; repeated selections are deduplicated by resolved identity.
   */
  interview_references: number[];
}
