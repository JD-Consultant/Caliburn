import { a as BaseNumberedListPlugin, i as BaseListPlugin, n as BaseListItemContentPlugin, o as BaseTaskListPlugin, r as BaseListItemPlugin, t as BaseBulletedListPlugin, w as BaseTodoListPlugin } from "../BaseListPlugin-n9uuTtLe.js";
import { KEYS } from "platejs";
import { toPlatePlugin, useEditorRef, useEditorSelector, useReadOnly } from "platejs/react";
import { c } from "react-compiler-runtime";

//#region src/react/ListPlugin.tsx
const BulletedListPlugin = toPlatePlugin(BaseBulletedListPlugin);
const TaskListPlugin = toPlatePlugin(BaseTaskListPlugin);
const NumberedListPlugin = toPlatePlugin(BaseNumberedListPlugin);
const ListItemContentPlugin = toPlatePlugin(BaseListItemContentPlugin);
const ListItemPlugin = toPlatePlugin(BaseListItemPlugin);
/**
* Enables support for bulleted, numbered and to-do lists with React-specific
* features.
*/
const ListPlugin = toPlatePlugin(BaseListPlugin, { plugins: [
	BulletedListPlugin,
	TaskListPlugin,
	NumberedListPlugin,
	ListItemPlugin,
	ListItemContentPlugin
] });

//#endregion
//#region src/react/TodoListPlugin.tsx
const TodoListPlugin = toPlatePlugin(BaseTodoListPlugin);

//#endregion
//#region src/react/hooks/useListToolbarButton.ts
const useListToolbarButtonState = (t0) => {
	const $ = c(8);
	let t1;
	if ($[0] !== t0) {
		t1 = t0 === void 0 ? {} : t0;
		$[0] = t0;
		$[1] = t1;
	} else t1 = $[1];
	const { nodeType: t2 } = t1;
	const nodeType = t2 === void 0 ? KEYS.ulClassic : t2;
	let t3;
	let t4;
	if ($[2] !== nodeType) {
		t3 = (editor) => !!editor.selection && editor.api.some({ match: { type: editor.getType(nodeType) } });
		t4 = [nodeType];
		$[2] = nodeType;
		$[3] = t3;
		$[4] = t4;
	} else {
		t3 = $[3];
		t4 = $[4];
	}
	const pressed = useEditorSelector(t3, t4);
	let t5;
	if ($[5] !== nodeType || $[6] !== pressed) {
		t5 = {
			nodeType,
			pressed
		};
		$[5] = nodeType;
		$[6] = pressed;
		$[7] = t5;
	} else t5 = $[7];
	return t5;
};
const useListToolbarButton = (state) => {
	const $ = c(8);
	const editor = useEditorRef();
	let t0;
	if ($[0] !== editor) {
		t0 = editor.getTransforms(ListPlugin);
		$[0] = editor;
		$[1] = t0;
	} else t0 = $[1];
	const tf = t0;
	let t1;
	if ($[2] !== state.nodeType || $[3] !== tf) {
		t1 = () => {
			tf.toggle.list({ type: state.nodeType });
		};
		$[2] = state.nodeType;
		$[3] = tf;
		$[4] = t1;
	} else t1 = $[4];
	let t2;
	if ($[5] !== state.pressed || $[6] !== t1) {
		t2 = { props: {
			pressed: state.pressed,
			onClick: t1,
			onMouseDown: _temp
		} };
		$[5] = state.pressed;
		$[6] = t1;
		$[7] = t2;
	} else t2 = $[7];
	return t2;
};
function _temp(e) {
	e.preventDefault();
}

//#endregion
//#region src/react/hooks/useTodoListElement.ts
const useTodoListElementState = (t0) => {
	const $ = c(5);
	const { element } = t0;
	const editor = useEditorRef();
	const { checked } = element;
	const readOnly = useReadOnly();
	let t1;
	if ($[0] !== checked || $[1] !== editor || $[2] !== element || $[3] !== readOnly) {
		t1 = {
			checked,
			editor,
			element,
			readOnly
		};
		$[0] = checked;
		$[1] = editor;
		$[2] = element;
		$[3] = readOnly;
		$[4] = t1;
	} else t1 = $[4];
	return t1;
};
const useTodoListElement = (state) => {
	const $ = c(7);
	const { checked, element, readOnly } = state;
	const editor = useEditorRef();
	const t0 = !!checked;
	let t1;
	if ($[0] !== editor || $[1] !== element || $[2] !== readOnly) {
		t1 = (value) => {
			if (readOnly) return;
			editor.tf.setNodes({ checked: value }, { at: element });
		};
		$[0] = editor;
		$[1] = element;
		$[2] = readOnly;
		$[3] = t1;
	} else t1 = $[3];
	let t2;
	if ($[4] !== t0 || $[5] !== t1) {
		t2 = { checkboxProps: {
			checked: t0,
			onCheckedChange: t1
		} };
		$[4] = t0;
		$[5] = t1;
		$[6] = t2;
	} else t2 = $[6];
	return t2;
};

//#endregion
export { BulletedListPlugin, ListItemContentPlugin, ListItemPlugin, ListPlugin, NumberedListPlugin, TaskListPlugin, TodoListPlugin, useListToolbarButton, useListToolbarButtonState, useTodoListElement, useTodoListElementState };