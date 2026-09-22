import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
const require = createRequire(new URL('../../../../.research-tmp/jd-editor-official-profile-probe/package.json', import.meta.url));
const use = async name => import(pathToFileURL(require.resolve(name)).href);
const { createSlateEditor, createSlatePlugin } = await use('platejs');
const { BaseHeadingPlugin, BaseBlockquotePlugin, BaseHorizontalRulePlugin, BaseBoldPlugin, BaseItalicPlugin, BaseUnderlinePlugin, BaseStrikethroughPlugin } = await use('@platejs/basic-nodes');
const { BaseListPlugin } = await use('@platejs/list-classic');
const { BaseTablePlugin } = await use('@platejs/table');

export const profile = {
  name: 'jd-plate-clean-v2 F03 headless candidate', format_version: 2,
  nodeId: { reuseId: true, initialValueIds: 'always' },
  idCreator: 'native nanoid(10), not overridden',
  normalization: 'official core/basic/list/table; no custom normalizer; force at observation boundary',
  semanticTypes: ['jd_section', 'jd_duty', 'jd_task', 'jd_outcomes', 'jd_requirements', 'jd_knowledge', 'jd_skill'],
};
export const dependencyVersions = Object.fromEntries(['platejs', '@platejs/core', '@platejs/slate', 'slate', '@platejs/basic-nodes', '@platejs/list-classic', '@platejs/table', '@platejs/diff', 'react', 'react-dom'].map(name => {
  const p = require.resolve(`${name}/package.json`);
  return [name, { version: require(p).version, packagePath: p, resolved: require.resolve(name) }];
}));
export const clone = value => structuredClone(value);
export function editor(value) {
  return createSlateEditor({ value: clone(value), nodeId: profile.nodeId, plugins: [
    BaseHeadingPlugin.configure({ options: { levels: [1, 2, 3] } }),
    BaseBlockquotePlugin, BaseHorizontalRulePlugin, BaseBoldPlugin, BaseItalicPlugin, BaseUnderlinePlugin, BaseStrikethroughPlugin,
    BaseListPlugin, BaseTablePlugin,
    ...profile.semanticTypes.map(key => createSlatePlugin({ key, node: { isElement: true } })),
  ] });
}
export const flush = () => new Promise(resolve => setImmediate(resolve));
export const textOf = n => typeof n.text === 'string' ? n.text : n.children.map(textOf).join('');
export const allText = v => v.map(textOf).join('');
export const walk = v => v.flatMap(n => [n, ...(n.children ? walk(n.children) : [])]);
export const elements = v => walk(v).filter(n => Array.isArray(n.children));
export function entry(e, id) {
  const matches = [...e.api.nodes({ at: [], mode: 'all', match: n => n.id === id && Array.isArray(n.children) })];
  if (matches.length !== 1) throw new Error(`Expected unique fixture ID ${id}; found ${matches.length}`);
  return matches[0];
}
export const node = (e, id) => entry(e, id)[0];
export const path = (e, id) => entry(e, id)[1];
export const leafSignature = v => walk(v).filter(n => typeof n.text === 'string' && (n.text.length || Object.keys(n).length > 1)).map(clone);
export function capture(e) {
  const batches = [], previous = e.onChange;
  e.onChange = options => { batches.push({ operations: clone(e.operations), value: clone(e.children) }); previous(options); };
  return batches;
}

// Probe assertions for the four new types / two ID arrays only.
// This is not the production full-profile, source, wire or authorization validator.
export function finiteIssues(value) {
  const issues = [], all = elements(value), byId = new Map(), bodies = new Set(['p','h1','h2','h3','blockquote','ul','ol','table','hr']);
  for (const n of all) {
    if (typeof n.id !== 'string' || !n.id) issues.push({ code: 'missing_id', type: n.type });
    if (byId.has(n.id)) issues.push({ code: 'duplicate_id', id: n.id });
    byId.set(n.id, n);
  }
  function visit(nodes, parent) {
    for (const n of nodes) {
      if (!n.children) continue;
      if (n.type === 'jd_task') {
        if (!n.children.some(c => bodies.has(c.type))) issues.push({ code: 'task_body_missing', id: n.id });
        for (const type of ['jd_outcomes', 'jd_requirements']) {
          if (n.children.filter(c => c.type === type).length !== 1) issues.push({ code: 'group_count', id: n.id, type });
        }
        for (const [key, expected] of [['knowledge_ids','jd_knowledge'],['skill_ids','jd_skill']]) {
          const ids = n[key] ?? [];
          if (!Array.isArray(ids) || ids.some(id => typeof id !== 'string') || new Set(ids).size !== ids.length) issues.push({ code: 'link_shape', id: n.id, key });
          else for (const id of ids) if (byId.get(id)?.type !== expected) issues.push({ code: 'link_target', id: n.id, key, target: id, actualType: byId.get(id)?.type ?? null });
        }
      } else if ('knowledge_ids' in n || 'skill_ids' in n) issues.push({ code: 'links_on_non_task', id: n.id });
      if (n.type === 'jd_outcomes' || n.type === 'jd_requirements') {
        if (parent?.type !== 'jd_task') issues.push({ code: 'group_parent', id: n.id });
        if (!n.children.length || n.children.some(c => !bodies.has(c.type))) issues.push({ code: 'group_body', id: n.id });
      }
      if (n.type === 'jd_knowledge' || n.type === 'jd_skill') {
        const section = n.type === 'jd_knowledge' ? 'knowledge' : 'skills';
        if (parent?.type !== 'jd_section' || parent.section_kind !== section) issues.push({ code: 'item_parent', id: n.id });
        if (!n.children.length || n.children.some(c => !bodies.has(c.type))) issues.push({ code: 'item_body', id: n.id });
      }
      visit(n.children, n);
    }
  }
  visit(value, null);
  return issues;
}
