import * as api from '../content-api';

export type CatalogKind = 'knowledge' | 'skills';

export const catalogOperations = {
  knowledge: {
    label: '知識',
    marker: 'K',
    add: api.addKnowledge,
    update: api.updateKnowledge,
    remove: api.deleteKnowledge,
    move: api.moveKnowledge,
    link: api.linkKnowledge,
    createAndLink: api.createAndLinkKnowledge,
    unlink: api.unlinkKnowledge,
    moveReference: api.moveKnowledgeReference,
    referenceField: 'knowledge_ids' as const,
  },
  skills: {
    label: '技能',
    marker: 'S',
    add: api.addSkill,
    update: api.updateSkill,
    remove: api.deleteSkill,
    move: api.moveSkill,
    link: api.linkSkill,
    createAndLink: api.createAndLinkSkill,
    unlink: api.unlinkSkill,
    moveReference: api.moveSkillReference,
    referenceField: 'skill_ids' as const,
  },
};
