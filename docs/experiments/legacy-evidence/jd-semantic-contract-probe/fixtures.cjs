// Fixed synthetic contract fixtures. These are not employee data or a JD sample.
const clone = value => JSON.parse(JSON.stringify(value));
const p = (id, text = '') => ({type: 'p', id, children: [{text}]});
const group = (type, id, texts = ['']) => ({
  type, id, children: texts.map((text, index) => p(`${id}-p${index + 1}`, text)),
});
const task = (id, text, knowledgeIds, skillIds) => ({
  type: 'jd_task', id,
  ...(knowledgeIds === undefined ? {} : {knowledge_ids: knowledgeIds}),
  ...(skillIds === undefined ? {} : {skill_ids: skillIds}),
  children: [
    p(`${id}-body`, text),
    group('jd_outcomes', `${id}-outcomes`),
    group('jd_requirements', `${id}-requirements`),
  ],
});
const item = (type, id, title, body) => ({
  type, id, children: [p(`${id}-title`, title), p(`${id}-body`, body)],
});
const find = (value, id) => {
  for (const node of value) {
    if (node.id === id) return node;
    if (Array.isArray(node.children)) {
      const found = find(node.children, id);
      if (found) return found;
    }
  }
  return undefined;
};
const withoutIds = node => {
  if (Array.isArray(node)) return node.map(withoutIds);
  if (!node || typeof node !== 'object') return node;
  return Object.fromEntries(Object.entries(node)
    .filter(([key]) => !['id', 'knowledge_ids', 'skill_ids'].includes(key))
    .map(([key, value]) => [key, withoutIds(value)]));
};

function baseline() {
  const t1 = task('task-1', '僅在主管核准後發布；緊急案件的優先順序尚未確認。', ['k-1', 'k-2'], ['s-1']);
  t1.children[0].source_refs = ['source:issued-01'];
  t1.children[1] = group('jd_outcomes', 'task-1-outcomes', ['可回查的核對紀錄。', '完整的發布內容。']);
  t1.children[2] = group('jd_requirements', 'task-1-requirements', ['逐項核對版本。', '取得主管核准。', '保留異常與處理依據。']);
  return [
    {type: 'jd_section', id: 'work-section', section_kind: 'work', children: [
      task('task-0', '尚未填入專業對應的有效草稿。'),
      t1,
      task('task-2', '整理核對結果；不代替主管核准。', ['k-1'], ['s-1', 's-2']),
    ]},
    {type: 'jd_section', id: 'knowledge-section', section_kind: 'knowledge', children: [
      item('jd_knowledge', 'k-1', '發布程序', '包括核准節點、權責分工及異常回報原則。'),
      item('jd_knowledge', 'k-2', '版本管理概念', '辨識目前基底、保存結果與歷史內容。'),
    ]},
    {type: 'jd_section', id: 'skills-section', section_kind: 'skills', children: [
      item('jd_skill', 's-1', '逐項核對', '能比較兩份內容並保留可回查的差異。'),
      item('jd_skill', 's-2', '整理說明', '能依讀者需要呈現內容與必要條件。'),
    ]},
  ];
}

function snapshots() {
  const r1 = {document_id: 'document-a', revision_id: 'a-r1', value: baseline()};
  const r2 = clone(r1);
  r2.revision_id = 'a-r2';
  find(r2.value, 'k-1-title').children[0].text = '修訂後發布程序';
  find(r2.value, 'k-1-body').children[0].text = '新增核對節點；其他工作文字與限制不變。';
  const b1 = clone(r1);
  b1.document_id = 'document-b';
  b1.revision_id = 'b-r1';
  find(b1.value, 'k-1-title').children[0].text = '另一份文件同 ID 的不同項目';
  return {r1, r2, b1};
}

// An explicit fixture table, not a production reference issuer or encoding rule.
const issuedRefs = {
  'ref:a-r1:k1': {document_id: 'document-a', revision_id: 'a-r1', item_id: 'k-1', kind: 'jd_knowledge', access: 'current_base'},
  'ref:a-r1:k1-alias': {document_id: 'document-a', revision_id: 'a-r1', item_id: 'k-1', kind: 'jd_knowledge', access: 'current_base'},
  'ref:a-r1:k2': {document_id: 'document-a', revision_id: 'a-r1', item_id: 'k-2', kind: 'jd_knowledge', access: 'current_base'},
  'ref:a-r1:s1': {document_id: 'document-a', revision_id: 'a-r1', item_id: 's-1', kind: 'jd_skill', access: 'current_base'},
  'ref:a-r2:k1': {document_id: 'document-a', revision_id: 'a-r2', item_id: 'k-1', kind: 'jd_knowledge', access: 'current_base'},
  'ref:b-r1:k1': {document_id: 'document-b', revision_id: 'b-r1', item_id: 'k-1', kind: 'jd_knowledge', access: 'current_base'},
  'ref:history:a-r1:k1': {document_id: 'document-a', revision_id: 'a-r1', item_id: 'k-1', kind: 'jd_knowledge', access: 'read_only'},
  'ref:history:head:k1': {document_id: 'document-a', revision_id: 'a-r2', item_id: 'k-1', kind: 'jd_knowledge', access: 'read_only'},
  'ref:a-r1:missing': {document_id: 'document-a', revision_id: 'a-r1', item_id: 'missing-k', kind: 'jd_knowledge', access: 'current_base'},
  'ref:a-r1:wrong-kind': {document_id: 'document-a', revision_id: 'a-r1', item_id: 's-1', kind: 'jd_knowledge', access: 'current_base'},
};

module.exports = {clone, p, group, task, item, find, withoutIds, baseline, snapshots, issuedRefs};
