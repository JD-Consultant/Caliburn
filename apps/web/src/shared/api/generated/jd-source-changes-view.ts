/* Generated from apps/api/contracts; do not edit. */

/**
 * The cited JD target from its last review to the selected current formal revision, and the original source chain against latest published Memory. Reading neither confirms nor aligns references.
 */
export interface JdSourceChangesView {
  revision_id: string;
  citation_id: string;
  jd_markdown: string;
  /**
   * The relevant fixed source-chain diff; null for immutable interview evidence.
   */
  source_markdown: string | null;
}
