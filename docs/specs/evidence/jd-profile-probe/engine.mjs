import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { types, clone } from './fixture.mjs';
const requirePinned = createRequire(new URL('../jd-editor-native-probe/package.json', import.meta.url));
export const { createSlateEditor, createSlatePlugin, NodeIdPlugin } = await import(pathToFileURL(requirePinned.resolve('platejs')).href);
export const resolvePinned = name => pathToFileURL(requirePinned.resolve(name)).href;
export function editor(value) {
  let sequence = 0;
  return createSlateEditor({
    value: clone(value),
    nodeId: { reuseId: true, initialValueIds: 'always' },
    plugins: [
      NodeIdPlugin.configure({ options: { idCreator: () => `f01-generated-${++sequence}` } }),
      ...types.filter(key => key !== 'p').map(key => createSlatePlugin({ key, node: { isElement: true } })),
    ],
  });
}
export function entry(e, id) {
  const matches = [...e.api.nodes({ at: [], mode: 'all', match: node => node.id === id && Array.isArray(node.children) })];
  if (matches.length !== 1) throw new Error(`Fixture ID ${id}: ${matches.length} matches`);
  return matches[0];
}
export const node = (e, id) => entry(e, id)[0];
export const path = (e, id) => entry(e, id)[1];
export const flush = () => new Promise(resolve => setImmediate(resolve));
