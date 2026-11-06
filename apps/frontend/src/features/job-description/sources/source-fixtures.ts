import type {
  CitationDetailsResponse,
  CitationResponse,
} from '../../../shared/api/generated/types.gen';
import { jobDescription, workspaceId } from '../../../../tests/fixtures';

export const citation: CitationResponse = {
  id: '33112233-4455-6677-8899-aabbccddeeff',
  target_kind: 'job_description',
  target_id: jobDescription.job_description_id,
  source: {
    kind: 'memory',
    workspace_id: workspaceId,
    published_version: 3,
    item_id: '44112233-4455-6677-8899-aabbccddeeff',
  },
  jd_changed: false,
};
export const citationDetail: CitationDetailsResponse = {
  citation,
  source: {
    source: citation.source,
    availability: 'available',
    title: '固定工作情境',
    text: '引用當時的原文',
    changed_version: 2,
    item_kind: 'situation',
  },
  comparison: null,
  source_changed: null,
  needs_recheck: null,
};
