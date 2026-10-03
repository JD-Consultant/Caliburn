/** Words for a source's state, shared by the list rows and the detail so both name the same reason. */
import type { Reference } from '../../shared/api/generated/jd-sources-view';

/** Why the source needs recheck; reading never clears it, and it is not a claim that the JD is wrong. */
export function changeLabel(reference: Reference): string {
  if (reference.jd_changed && reference.source_changed) return 'JD 與來源皆有變更';
  if (reference.jd_changed) return 'JD 已修改';
  if (reference.source_changed) return '來源已更新';
  return '待核對';
}
