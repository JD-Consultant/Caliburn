import React, { useMemo } from 'react';
import { createPlateEditor, createPlatePlugin, Plate, PlateContent, PlateElement, PlateLeaf } from 'platejs/react';
import { computeDiff } from '@platejs/diff';
import { nodeTypes } from './fixture.mjs';

export const printable = value => value === undefined ? 'undefined（未設定／原生移除值）' : JSON.stringify(value, null, 2);
export function updateText(operation) {
  if (operation?.type !== 'update') return operation?.type ?? '';
  return Object.keys(operation.newProperties).map(key => `${key}: ${printable(operation.properties[key])} → ${printable(operation.newProperties[key])}`).join('\n');
}
function DiffLeaf(props) {
  const operation = props.leaf.diffOperation;
  return <PlateLeaf {...props} attributes={{ ...props.attributes, 'data-diff-type': operation?.type, title: updateText(operation) }} className={operation ? `diff-${operation.type}` : ''}>{props.children}</PlateLeaf>;
}
function Element(props) {
  const { element, children } = props;
  const operation = element.diffOperation;
  const attributes = { ...props.attributes, 'data-fixture-id': element.id, 'data-diff-type': operation?.type, title: updateText(operation) };
  const className = operation ? `diff-${operation.type}` : '';
  if (element.type === 'hr') return <PlateElement {...props} attributes={attributes} className={className}><span contentEditable={false}><hr /></span>{children}</PlateElement>;
  return <PlateElement {...props} as={element.type} attributes={attributes} className={className}>{element.type === 'table' ? <tbody>{children}</tbody> : children}</PlateElement>;
}
export const plugins = [
  ...nodeTypes.map(key => createPlatePlugin({ key, node: { isElement: true }, render: { node: Element } })),
  createPlatePlugin({ key: 'bold', node: { isLeaf: true }, render: { as: 'strong' } }),
  createPlatePlugin({ key: 'italic', node: { isLeaf: true }, render: { as: 'em' } }),
  createPlatePlugin({ key: 'diff', node: { isLeaf: true }, render: { node: DiffLeaf } }),
];
export function nativeDiff(before, after) {
  // No property filtering, relation override, special-case repair, or diff persistence.
  const editor = createPlateEditor({ plugins, nodeId: false, value: structuredClone(before) });
  return computeDiff(structuredClone(before), structuredClone(after), { isInline: editor.api.isInline, lineBreakChar: '¶' });
}
export function ReadOnlyDocument({ value, name }) {
  const editor = useMemo(() => createPlateEditor({ plugins, nodeId: false, value: structuredClone(value) }), [value]);
  return <div className="document" data-editor-name={name}><Plate editor={editor} readOnly><PlateContent aria-label={name} /></Plate></div>;
}
export function nativeOperations(value, path = []) {
  // Read only the diffOperation payload that native computeDiff emitted.
  return value.flatMap((node, index) => [
    ...(node.diffOperation ? [{ path: [...path, index], id: node.id, type: node.type ?? 'text', operation: node.diffOperation }] : []),
    ...(node.children ? nativeOperations(node.children, [...path, index]) : []),
  ]);
}
