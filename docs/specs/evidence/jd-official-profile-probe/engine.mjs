import { createSlateEditor, createSlatePlugin } from 'platejs';
import { BaseHeadingPlugin, BaseBlockquotePlugin, BaseHorizontalRulePlugin, BaseBoldPlugin, BaseItalicPlugin, BaseUnderlinePlugin, BaseStrikethroughPlugin } from '@platejs/basic-nodes';
import { BaseListPlugin } from '@platejs/list-classic';
import { BaseTablePlugin } from '@platejs/table';

export const profile = {
  name: 'jd-plate-clean-v1 F02 headless',
  nodeId: { reuseId: true, initialValueIds: 'always' },
  idCreator: 'native default nanoid(10); not overridden',
  normalization: 'native core + official basic/list/table; no custom normalizer; explicit force normalize at durable observation boundaries',
  plugins: ['BaseHeadingPlugin(levels:[1,2,3])', 'BaseBlockquotePlugin', 'BaseHorizontalRulePlugin', 'BaseBoldPlugin', 'BaseItalicPlugin', 'BaseUnderlinePlugin', 'BaseStrikethroughPlugin', 'BaseListPlugin(default)', 'BaseTablePlugin(default)', 'jd_section/jd_duty/jd_task ordinary isElement:true'],
};
export function editor(value) {
  return createSlateEditor({
    value: structuredClone(value),
    nodeId: profile.nodeId,
    plugins: [
      BaseHeadingPlugin.configure({ options: { levels: [1, 2, 3] } }),
      BaseBlockquotePlugin, BaseHorizontalRulePlugin,
      BaseBoldPlugin, BaseItalicPlugin, BaseUnderlinePlugin, BaseStrikethroughPlugin,
      BaseListPlugin, BaseTablePlugin,
      ...['jd_section', 'jd_duty', 'jd_task'].map(key => createSlatePlugin({ key, node: { isElement: true } })),
    ],
  });
}
export const clone = structuredClone;
export const flush = () => new Promise(resolve => setImmediate(resolve));
export const textOf = node => typeof node.text === 'string' ? node.text : node.children.map(textOf).join('');
export const allText = value => value.map(textOf).join('');
export function entry(e, id) {
  const matches = [...e.api.nodes({ at: [], mode: 'all', match: n => n.id === id && Array.isArray(n.children) })];
  if (matches.length !== 1) throw new Error(`Expected one fixture ID ${id}; found ${matches.length}`);
  return matches[0];
}
export const node = (e, id) => entry(e, id)[0];
export const path = (e, id) => entry(e, id)[1];
export function capture(e) {
  const batches = [], previous = e.onChange;
  e.onChange = options => { batches.push({ operations: clone(e.operations), value: clone(e.children) }); previous(options); };
  return batches;
}
export function walk(value) {
  return value.flatMap(n => [n, ...(n.children ? walk(n.children) : [])]);
}
