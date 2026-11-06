import type {
  CitationResponse,
  JobDescriptionContentResponse,
} from '../../../shared/api/generated/types.gen';
import { conditionLabels } from '../labels';

export function citationTargetLabel(
  citation: CitationResponse,
  jd: JobDescriptionContentResponse,
): string {
  switch (citation.target_kind) {
    case 'job_description':
      return '基本資料';
    case 'duty':
      return `職責 · ${jd.duties.find((item) => item.id === citation.target_id)?.name ?? '原職責'}`;
    case 'task':
      return `任務 · ${jd.tasks.find((item) => item.id === citation.target_id)?.name ?? '原任務'}`;
    case 'knowledge':
      return `知識 · ${jd.knowledge.find((item) => item.id === citation.target_id)?.name ?? '原知識'}`;
    case 'skill':
      return `技能 · ${jd.skills.find((item) => item.id === citation.target_id)?.name ?? '原技能'}`;
    case 'collaboration':
      return `協作 · ${jd.collaborations.find((item) => item.id === citation.target_id)?.collaborator_name ?? '原協作對象'}`;
    case 'condition': {
      const condition = jd.conditions.find((item) => item.id === citation.target_id);
      return condition
        ? `${conditionLabels[condition.kind]} · ${condition.text}`
        : '共通條件';
    }
  }
}
