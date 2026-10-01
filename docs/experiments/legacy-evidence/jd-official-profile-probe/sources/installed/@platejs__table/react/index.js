import { $ as getSelectedCellEntries, C as moveSelectionFromCell, Ct as getColSpan, K as getSelectedCellsBorders, S as setBorderSize, St as getRowSpan, V as getTableOverriddenColSizes, W as getTableCellBorders, X as getTopTableCell, Z as getSelectedCellsBoundingBox, _ as hasAdjacentBlockInCell, _t as getCellTypes, a as BaseTableRowPlugin, b as setTableMarginLeft, bt as computeCellIndices, et as getSelectedCellIds, ft as getLeftTableCell, g as getTableMoveSelectionContext, i as BaseTablePlugin, n as BaseTableCellHeaderPlugin, q as isSelectedCellBorder, r as BaseTableCellPlugin, t as KEY_SHIFT_EDGES, v as shouldMoveSelectionFromCell, x as setTableColSize, y as setTableRowSize, yt as getCellIndices } from "../constants-6xljcM3U.js";
import { Hotkeys, KEYS, PathApi } from "platejs";
import { atom, createAtomStore, toPlatePlugin, useEditorPlugin, useEditorSelector, useElement, useElementSelector, usePluginOption, useReadOnly } from "platejs/react";
import { c } from "react-compiler-runtime";
import React from "react";
import { resizeLengthClampStatic } from "@platejs/resizable";

//#region src/react/onKeyDownTable.ts
const shouldMoveSingleCellSelection = (editor, key) => {
	const context = getTableMoveSelectionContext(editor, editor.selection?.focus);
	if (!context) return false;
	const { blockPath, cellPath, point } = context;
	if (key === "shift+left") return editor.api.isStart(point, cellPath);
	if (key === "shift+right") return editor.api.isEnd(point, cellPath);
	if (hasAdjacentBlockInCell(editor, {
		blockPath,
		cellPath,
		reverse: key === "shift+up"
	})) return false;
	return shouldMoveSelectionFromCell(editor, {
		blockPath,
		point,
		reverse: key === "shift+up"
	});
};
const onKeyDownTable = ({ editor, event }) => {
	if (event.defaultPrevented) return;
	if (event.which === 229 && editor.selection && editor.api.isExpanded()) {
		if (Array.from(editor.api.nodes({
			at: editor.selection,
			match: { type: getCellTypes(editor) }
		})).length > 1) {
			editor.tf.collapse({ edge: "end" });
			return;
		}
	}
	const isKeyDown = {
		"shift+down": Hotkeys.isExtendDownward(event),
		"shift+left": Hotkeys.isExtendBackward(event),
		"shift+right": Hotkeys.isExtendForward(event),
		"shift+up": Hotkeys.isExtendUpward(event)
	};
	Object.keys(isKeyDown).forEach((key) => {
		if (!isKeyDown[key]) return;
		if (moveSelectionFromCell(editor, {
			edge: KEY_SHIFT_EDGES[key],
			reverse: key === "shift+up"
		}) || shouldMoveSingleCellSelection(editor, key) && moveSelectionFromCell(editor, {
			at: editor.selection,
			edge: KEY_SHIFT_EDGES[key],
			fromOneCell: true,
			reverse: key === "shift+up"
		})) {
			event.preventDefault();
			event.stopPropagation();
		}
	});
};

//#endregion
//#region src/react/TablePlugin.tsx
const TableRowPlugin = toPlatePlugin(BaseTableRowPlugin);
const TableCellPlugin = toPlatePlugin(BaseTableCellPlugin);
const TableCellHeaderPlugin = toPlatePlugin(BaseTableCellHeaderPlugin);
/** Enables support for tables with React-specific features. */
const TablePlugin = toPlatePlugin(BaseTablePlugin, {
	handlers: { onKeyDown: onKeyDownTable },
	plugins: [
		TableRowPlugin,
		TableCellPlugin,
		TableCellHeaderPlugin
	]
});

//#endregion
//#region src/react/components/TableCellElement/getOnSelectTableBorderFactory.ts
/** Helper: sets one cell's specific border(s) to `size`. */
function setCellBorderSize(editor, at, directions, size) {
	if (!at) return;
	if (directions === "all") setBorderSize(editor, size, {
		at,
		border: "all"
	});
	else for (const dir of directions) setBorderSize(editor, size, {
		at,
		border: dir
	});
}
const getSelectedCellBorderTargets = (editor, cells) => cells.map((cell) => {
	const path = editor.api.findPath(cell) ?? null;
	const { col, row } = getCellIndices(editor, cell);
	return {
		cSpan: getColSpan(cell),
		col,
		leftCellPath: path ? getLeftTableCell(editor, { at: path })?.[1] ?? null : null,
		path,
		rSpan: getRowSpan(cell),
		row,
		topCellPath: path ? getTopTableCell(editor, { at: path })?.[1] ?? null : null
	};
});
/**
* Toggle logic for `'none'`, `'outer'`, `'top'|'bottom'|'left'|'right'`.
* `'none'` toggles no borders ↔ all borders, `'outer'` toggles the bounding
* rectangle's outer edges on/off, `'top'|'bottom'|'left'|'right'` toggles only
* that side of the bounding rect.
*/
function setSelectedCellsBorder(editor, { border, cells }) {
	if (cells.length === 0) return;
	const targets = getSelectedCellBorderTargets(editor, cells);
	if (border === "none") {
		const { none: allNone } = getSelectedCellsBorders(editor, cells);
		const newSize$1 = allNone ? 1 : 0;
		for (const target of targets) {
			if (!target.path) continue;
			const edges = [];
			if (target.row === 0) edges.push("top");
			if (target.col === 0) edges.push("left");
			edges.push("bottom", "right");
			if (target.row > 0) setCellBorderSize(editor, target.topCellPath, ["bottom"], newSize$1);
			if (target.col > 0) setCellBorderSize(editor, target.leftCellPath, ["right"], newSize$1);
			if (edges.length > 0) setCellBorderSize(editor, target.path, edges, newSize$1);
		}
		return;
	}
	if (border === "outer") {
		const { outer: allOut } = getSelectedCellsBorders(editor, cells);
		const newSize$1 = allOut ? 0 : 1;
		const { maxCol: maxCol$1, maxRow: maxRow$1, minCol: minCol$1, minRow: minRow$1 } = getSelectedCellsBoundingBox(editor, cells);
		for (const target of targets) {
			if (!target.path) continue;
			for (let rr = target.row; rr < target.row + target.rSpan; rr++) for (let cc = target.col; cc < target.col + target.cSpan; cc++) {
				const edges = [];
				if (rr === minRow$1) edges.push("top");
				if (rr === maxRow$1) edges.push("bottom");
				if (cc === minCol$1) edges.push("left");
				if (cc === maxCol$1) edges.push("right");
				if (edges.length > 0) setCellBorderSize(editor, target.path, edges, newSize$1);
			}
		}
		return;
	}
	const newSize = isSelectedCellBorder(editor, cells, border) ? 0 : 1;
	const { maxCol, maxRow, minCol, minRow } = getSelectedCellsBoundingBox(editor, cells);
	for (const target of targets) {
		if (!target.path) continue;
		const edges = [];
		if (border === "top" && target.row === minRow) if (target.row === 0) edges.push("top");
		else setCellBorderSize(editor, target.topCellPath, ["bottom"], newSize);
		if (border === "bottom" && target.row + target.rSpan - 1 === maxRow) edges.push("bottom");
		if (border === "left" && target.col === minCol) if (target.col === 0) edges.push("left");
		else setCellBorderSize(editor, target.leftCellPath, ["right"], newSize);
		if (border === "right" && target.col + target.cSpan - 1 === maxCol) edges.push("right");
		if (edges.length > 0) setCellBorderSize(editor, target.path, edges, newSize);
	}
}
/**
* Returns a function that sets borders on the selection with toggling logic. If
* selection has one or many cells, it's the same approach: we read the bounding
* rectangle, then decide which edges to flip on/off.
*/
const getOnSelectTableBorderFactory = (editor) => (border) => () => {
	let cells = editor.getApi(TablePlugin).table.getSelectedCells();
	if (!cells || cells.length === 0) {
		const cell = editor.api.block({ match: { type: getCellTypes(editor) } });
		if (cell) cells = [cell[0]];
		else return;
	}
	setSelectedCellsBorder(editor, {
		border,
		cells: cells.map((v) => v)
	});
};

//#endregion
//#region src/react/components/TableCellElement/roundCellSizeToStep.ts
/**
* Rounds a cell size to the nearest step, or returns the size if the step is
* not set.
*/
const roundCellSizeToStep = (size, step) => step ? Math.round(size / step) * step : size;

//#endregion
//#region src/react/components/TableCellElement/useIsCellSelected.ts
const useIsCellSelected = (element) => {
	const $ = c(3);
	let t0;
	let t1;
	if ($[0] !== element.id) {
		t0 = (editor) => editor.getApi(TablePlugin).table.isCellSelected(element.id);
		t1 = [element.id];
		$[0] = element.id;
		$[1] = t0;
		$[2] = t1;
	} else {
		t0 = $[1];
		t1 = $[2];
	}
	return useEditorSelector(t0, t1);
};

//#endregion
//#region src/react/components/TableCellElement/useTableBordersDropdownMenuContentState.ts
const useTableBordersDropdownMenuContentState = (t0) => {
	const $ = c(14);
	let t1;
	if ($[0] !== t0) {
		t1 = t0 === void 0 ? {} : t0;
		$[0] = t0;
		$[1] = t1;
	} else t1 = $[1];
	const { element: el } = t1;
	const { editor } = useEditorPlugin(TablePlugin);
	const element = useElement() ?? el;
	let t2;
	if ($[2] !== element) {
		t2 = [element];
		$[2] = element;
		$[3] = t2;
	} else t2 = $[3];
	const borderStates = useEditorSelector(_temp$5, t2);
	let t3;
	if ($[4] !== editor) {
		t3 = getOnSelectTableBorderFactory(editor);
		$[4] = editor;
		$[5] = t3;
	} else t3 = $[5];
	let t4;
	if ($[6] !== borderStates.bottom || $[7] !== borderStates.left || $[8] !== borderStates.none || $[9] !== borderStates.outer || $[10] !== borderStates.right || $[11] !== borderStates.top || $[12] !== t3) {
		t4 = {
			getOnSelectTableBorder: t3,
			hasBottomBorder: borderStates.bottom,
			hasLeftBorder: borderStates.left,
			hasNoBorders: borderStates.none,
			hasOuterBorders: borderStates.outer,
			hasRightBorder: borderStates.right,
			hasTopBorder: borderStates.top
		};
		$[6] = borderStates.bottom;
		$[7] = borderStates.left;
		$[8] = borderStates.none;
		$[9] = borderStates.outer;
		$[10] = borderStates.right;
		$[11] = borderStates.top;
		$[12] = t3;
		$[13] = t4;
	} else t4 = $[13];
	return t4;
};
function _temp$5(editor_0) {
	return getSelectedCellsBorders(editor_0);
}

//#endregion
//#region src/react/hooks/useCellIndices.ts
const useCellIndices = () => {
	const $ = c(5);
	const { editor } = useEditorPlugin(TablePlugin);
	const element = useElement();
	const cellIndices = usePluginOption(TablePlugin, "cellIndices", element.id);
	let t0;
	bb0: {
		if (!cellIndices) {
			let t1$1;
			if ($[0] !== editor || $[1] !== element) {
				t1$1 = computeCellIndices(editor, { cellNode: element }) ?? {
					col: 0,
					row: 0
				};
				$[0] = editor;
				$[1] = element;
				$[2] = t1$1;
			} else t1$1 = $[2];
			t0 = t1$1;
			break bb0;
		}
		let t1;
		if ($[3] !== cellIndices) {
			t1 = cellIndices ?? {
				col: 0,
				row: 0
			};
			$[3] = cellIndices;
			$[4] = t1;
		} else t1 = $[4];
		t0 = t1;
	}
	return t0;
};

//#endregion
//#region src/react/components/TableCellElement/useTableCellBorders.ts
function useTableCellBorders(t0) {
	const $ = c(6);
	let t1;
	if ($[0] !== t0) {
		t1 = t0 === void 0 ? {} : t0;
		$[0] = t0;
		$[1] = t1;
	} else t1 = $[1];
	const { element: el } = t1;
	const { editor } = useEditorPlugin(TablePlugin);
	const element = useElement() ?? el;
	const cellIndices = useCellIndices();
	let t2;
	if ($[2] !== cellIndices || $[3] !== editor || $[4] !== element) {
		t2 = getTableCellBorders(editor, {
			cellIndices,
			element
		});
		$[2] = cellIndices;
		$[3] = editor;
		$[4] = element;
		$[5] = t2;
	} else t2 = $[5];
	return t2;
}

//#endregion
//#region src/react/stores/useTableStore.ts
const { TableProvider, tableStore, useTableSet, useTableState, useTableStore, useTableValue } = createAtomStore({
	colSizeOverrides: atom(/* @__PURE__ */ new Map()),
	marginLeftOverride: null,
	rowSizeOverrides: atom(/* @__PURE__ */ new Map())
}, { name: "table" });
const useOverrideSizeFactory = (setOverrides) => {
	const $ = c(2);
	let t0;
	if ($[0] !== setOverrides) {
		t0 = (index, size) => {
			setOverrides((overrides) => {
				const newOverrides = new Map(overrides);
				if (size === null) newOverrides.delete(index);
				else newOverrides.set(index, size);
				return newOverrides;
			});
		};
		$[0] = setOverrides;
		$[1] = t0;
	} else t0 = $[1];
	return t0;
};
const useOverrideColSize = () => {
	return useOverrideSizeFactory(useTableSet("colSizeOverrides"));
};
const useOverrideRowSize = () => {
	return useOverrideSizeFactory(useTableSet("rowSizeOverrides"));
};
const useOverrideMarginLeft = () => {
	return useTableSet("marginLeftOverride");
};

//#endregion
//#region src/react/components/TableElement/useSelectedCells.ts
const hasSameIds$1 = (nextValue, prevValue) => {
	if (nextValue === prevValue) return true;
	if (!nextValue || !prevValue) return !nextValue && !prevValue;
	if (nextValue.length !== prevValue.length) return false;
	for (const [index, nextId] of nextValue.entries()) if (nextId !== prevValue[index]) return false;
	return true;
};
const hasSameSelectionState = (nextValue, prevValue) => nextValue.selectedContent === prevValue.selectedContent && hasSameIds$1(nextValue.selectedCellIds, prevValue.selectedCellIds);
const useSelectedCells = () => {
	const $ = c(8);
	const readOnly = useReadOnly();
	const { setOptions } = useEditorPlugin(BaseTablePlugin);
	let t0;
	let t1;
	if ($[0] !== readOnly) {
		t0 = (editor) => {
			if (readOnly) return {
				selectedCellIds: null,
				selectedContent: null
			};
			const selectedCellIds = getSelectedCellIds(editor);
			return {
				selectedCellIds,
				selectedContent: selectedCellIds ? editor.children : null
			};
		};
		t1 = [readOnly];
		$[0] = readOnly;
		$[1] = t0;
		$[2] = t1;
	} else {
		t0 = $[1];
		t1 = $[2];
	}
	let t2;
	if ($[3] === Symbol.for("react.memo_cache_sentinel")) {
		t2 = { equalityFn: hasSameSelectionState };
		$[3] = t2;
	} else t2 = $[3];
	const selectionState = useEditorSelector(t0, t1, t2);
	let t3;
	let t4;
	if ($[4] !== selectionState || $[5] !== setOptions) {
		t3 = () => {
			const nextSelectedCellIds = selectionState.selectedCellIds;
			setOptions((draft) => {
				if (!hasSameIds$1(draft._selectedCellIds, nextSelectedCellIds)) draft._selectedCellIds = nextSelectedCellIds;
				if (draft._selectedTableIds !== void 0) draft._selectedTableIds = void 0;
				draft._selectionVersion = (draft._selectionVersion ?? 0) + 1;
			});
		};
		t4 = [selectionState, setOptions];
		$[4] = selectionState;
		$[5] = setOptions;
		$[6] = t3;
		$[7] = t4;
	} else {
		t3 = $[6];
		t4 = $[7];
	}
	React.useLayoutEffect(t3, t4);
};

//#endregion
//#region src/react/components/TableElement/useTableColSizes.ts
/**
* Returns colSizes with overrides applied. Unset node.colSizes if `colCount`
* updates to 1.
*/
const useTableColSizes = (t0) => {
	const $ = c(8);
	let t1;
	if ($[0] !== t0) {
		t1 = t0 === void 0 ? {} : t0;
		$[0] = t0;
		$[1] = t1;
	} else t1 = $[1];
	const { disableOverrides: t2, transformColSizes } = t1;
	const disableOverrides = t2 === void 0 ? false : t2;
	const colSizeOverrides = useTableValue("colSizeOverrides");
	let t3;
	let t4;
	if ($[2] !== colSizeOverrides || $[3] !== disableOverrides || $[4] !== transformColSizes) {
		t3 = (t5$1) => {
			const [tableNode] = t5$1;
			const colSizes = getTableOverriddenColSizes(tableNode, disableOverrides ? void 0 : colSizeOverrides);
			if (transformColSizes) return transformColSizes(colSizes);
			return colSizes;
		};
		t4 = [
			disableOverrides,
			colSizeOverrides,
			transformColSizes
		];
		$[2] = colSizeOverrides;
		$[3] = disableOverrides;
		$[4] = transformColSizes;
		$[5] = t3;
		$[6] = t4;
	} else {
		t3 = $[5];
		t4 = $[6];
	}
	let t5;
	if ($[7] === Symbol.for("react.memo_cache_sentinel")) {
		t5 = {
			key: KEYS.table,
			equalityFn: _temp$4
		};
		$[7] = t5;
	} else t5 = $[7];
	return useElementSelector(t3, t4, t5);
};
function _temp$4(a, b) {
	return !!a && !!b && PathApi.equals(a, b);
}

//#endregion
//#region src/react/components/TableElement/useTableElement.ts
const useTableElement = () => {
	const $ = c(5);
	const { editor, getOptions } = useEditorPlugin(TablePlugin);
	const { disableMarginLeft } = getOptions();
	const element = useElement();
	const marginLeftOverride = useTableValue("marginLeftOverride");
	const marginLeft = disableMarginLeft ? 0 : marginLeftOverride ?? element.marginLeft ?? 0;
	let t0;
	if ($[0] !== editor) {
		t0 = { onMouseDown: () => {
			if (editor.getOption(TablePlugin, "isSelectingCell")) editor.tf.collapse();
		} };
		$[0] = editor;
		$[1] = t0;
	} else t0 = $[1];
	let t1;
	if ($[2] !== marginLeft || $[3] !== t0) {
		t1 = {
			marginLeft,
			props: t0
		};
		$[2] = marginLeft;
		$[3] = t0;
		$[4] = t1;
	} else t1 = $[4];
	return t1;
};

//#endregion
//#region src/react/components/TableElement/useTableSelectionDom.ts
const hasSameIds = (nextValue, prevValue) => {
	if (nextValue === prevValue) return true;
	if (!nextValue || !prevValue) return !nextValue && !prevValue;
	if (nextValue.length !== prevValue.length) return false;
	for (const [index, nextId] of nextValue.entries()) if (nextId !== prevValue[index]) return false;
	return true;
};
const TABLE_CELL_SELECTED_ATTRIBUTE = "data-table-cell-selected";
const TABLE_SELECTING_ATTRIBUTE = "data-table-selecting";
const TABLE_CELL_SELECTOR = "[data-table-cell-id]";
const setTableSelectingAttribute = (table, isSelecting) => {
	if (isSelecting) {
		table.setAttribute(TABLE_SELECTING_ATTRIBUTE, "true");
		return;
	}
	table.removeAttribute(TABLE_SELECTING_ATTRIBUTE);
};
const escapeForAttributeSelector = (value) => globalThis.CSS?.escape ? globalThis.CSS.escape(value) : value.replaceAll("\"", "\\\"");
const createTableCellElementsById = (table) => {
	const tableCellElementsById = /* @__PURE__ */ new Map();
	table.querySelectorAll(TABLE_CELL_SELECTOR).forEach((element) => {
		const cellId = element.getAttribute("data-table-cell-id");
		if (cellId) tableCellElementsById.set(cellId, element);
	});
	return tableCellElementsById;
};
const getSelectedCellElement = (table, cellId, tableCellElementsById) => {
	const cachedElement = tableCellElementsById.get(cellId);
	if (cachedElement?.isConnected && table.contains(cachedElement)) return cachedElement;
	const element = table.querySelector(`[data-table-cell-id="${escapeForAttributeSelector(cellId)}"]`);
	if (element) tableCellElementsById.set(cellId, element);
	else tableCellElementsById.delete(cellId);
	return element;
};
const useTableSelectionDom = (tableRef) => {
	const $ = c(5);
	const previousTableRef = React.useRef(null);
	const previousSelectedCellIdsRef = React.useRef(null);
	const tableCellElementsByIdRef = React.useRef(null);
	let t0;
	let t1;
	if ($[0] === Symbol.for("react.memo_cache_sentinel")) {
		t0 = [];
		t1 = { equalityFn: hasSameIds };
		$[0] = t0;
		$[1] = t1;
	} else {
		t0 = $[0];
		t1 = $[1];
	}
	const selectedCellIds = useEditorSelector(_temp$3, t0, t1);
	let t2;
	if ($[2] !== selectedCellIds || $[3] !== tableRef) {
		t2 = () => {
			const table = tableRef.current;
			if (!table) return;
			const tableChanged = previousTableRef.current !== table;
			const previousSelectedCellIdsRefValue = previousSelectedCellIdsRef.current;
			if (!tableChanged && hasSameIds(selectedCellIds, previousSelectedCellIdsRefValue)) return;
			const previousSelectedCellIds = tableChanged ? [] : previousSelectedCellIdsRefValue ?? [];
			const nextSelectedCellIds = selectedCellIds ?? [];
			const tableCellElementsById = tableChanged || !tableCellElementsByIdRef.current ? createTableCellElementsById(table) : tableCellElementsByIdRef.current;
			tableCellElementsByIdRef.current = tableCellElementsById;
			if (previousSelectedCellIds.length === 0) {
				setTableSelectingAttribute(table, nextSelectedCellIds.length > 0);
				nextSelectedCellIds.forEach((cellId) => {
					getSelectedCellElement(table, cellId, tableCellElementsById)?.setAttribute(TABLE_CELL_SELECTED_ATTRIBUTE, "true");
				});
				previousTableRef.current = table;
				previousSelectedCellIdsRef.current = nextSelectedCellIds;
				return;
			}
			if (nextSelectedCellIds.length === 0) {
				setTableSelectingAttribute(table, false);
				previousSelectedCellIds.forEach((cellId_0) => {
					getSelectedCellElement(table, cellId_0, tableCellElementsById)?.removeAttribute(TABLE_CELL_SELECTED_ATTRIBUTE);
				});
				previousTableRef.current = table;
				previousSelectedCellIdsRef.current = nextSelectedCellIds;
				return;
			}
			const nextSelectedCellIdsSet = new Set(nextSelectedCellIds);
			const previousSelectedCellIdsSet = new Set(previousSelectedCellIds);
			setTableSelectingAttribute(table, true);
			previousSelectedCellIds.forEach((cellId_1) => {
				if (nextSelectedCellIdsSet.has(cellId_1)) return;
				getSelectedCellElement(table, cellId_1, tableCellElementsById)?.removeAttribute(TABLE_CELL_SELECTED_ATTRIBUTE);
			});
			nextSelectedCellIds.forEach((cellId_2) => {
				if (previousSelectedCellIdsSet.has(cellId_2)) return;
				getSelectedCellElement(table, cellId_2, tableCellElementsById)?.setAttribute(TABLE_CELL_SELECTED_ATTRIBUTE, "true");
			});
			previousTableRef.current = table;
			previousSelectedCellIdsRef.current = nextSelectedCellIds;
		};
		$[2] = selectedCellIds;
		$[3] = tableRef;
		$[4] = t2;
	} else t2 = $[4];
	React.useLayoutEffect(t2);
};
function _temp$3(editor) {
	return getSelectedCellIds(editor);
}

//#endregion
//#region src/react/components/TableCellElement/useTableCellSize.ts
function useTableCellSize(t0) {
	const $ = c(10);
	let t1;
	if ($[0] !== t0) {
		t1 = t0 === void 0 ? {} : t0;
		$[0] = t0;
		$[1] = t1;
	} else t1 = $[1];
	const { element: el } = t1;
	const { api } = useEditorPlugin(TablePlugin);
	const element = useElement() ?? el;
	const colSizes = useTableColSizes();
	const cellIndices = useCellIndices();
	let t2;
	let t3;
	if ($[2] === Symbol.for("react.memo_cache_sentinel")) {
		t2 = [];
		t3 = { key: KEYS.tr };
		$[2] = t2;
		$[3] = t3;
	} else {
		t2 = $[2];
		t3 = $[3];
	}
	const rowSize = useElementSelector(_temp$2, t2, t3);
	let t4;
	if ($[4] !== api.table || $[5] !== cellIndices || $[6] !== colSizes || $[7] !== element || $[8] !== rowSize) {
		t4 = api.table.getCellSize({
			cellIndices,
			colSizes,
			element,
			rowSize
		});
		$[4] = api.table;
		$[5] = cellIndices;
		$[6] = colSizes;
		$[7] = element;
		$[8] = rowSize;
		$[9] = t4;
	} else t4 = $[9];
	return t4;
}
function _temp$2(t0) {
	const [node] = t0;
	return node.size;
}

//#endregion
//#region src/react/components/TableCellElement/useTableCellElement.ts
const useTableCellElement = () => {
	const $ = c(18);
	const { api } = useEditorPlugin(TablePlugin);
	const element = useElement();
	const isCellSelected = useIsCellSelected(element);
	let t0;
	if ($[0] === Symbol.for("react.memo_cache_sentinel")) {
		t0 = [];
		$[0] = t0;
	} else t0 = $[0];
	const isSelectingCell = useEditorSelector(_temp$1, t0);
	const rowSizeOverrides = useTableValue("rowSizeOverrides");
	let t1;
	if ($[1] !== element) {
		t1 = { element };
		$[1] = element;
		$[2] = t1;
	} else t1 = $[2];
	const { minHeight, width } = useTableCellSize(t1);
	let t2;
	if ($[3] !== element) {
		t2 = { element };
		$[3] = element;
		$[4] = t2;
	} else t2 = $[4];
	const borders = useTableCellBorders(t2);
	const { col, row } = useCellIndices();
	const colSpan = api.table.getColSpan(element);
	const endingRowIndex = row + api.table.getRowSpan(element) - 1;
	const endingColIndex = col + colSpan - 1;
	let t3;
	if ($[5] !== endingRowIndex || $[6] !== minHeight || $[7] !== rowSizeOverrides) {
		t3 = rowSizeOverrides.get?.(endingRowIndex) ?? minHeight;
		$[5] = endingRowIndex;
		$[6] = minHeight;
		$[7] = rowSizeOverrides;
		$[8] = t3;
	} else t3 = $[8];
	let t4;
	if ($[9] !== borders || $[10] !== colSpan || $[11] !== endingColIndex || $[12] !== endingRowIndex || $[13] !== isCellSelected || $[14] !== isSelectingCell || $[15] !== t3 || $[16] !== width) {
		t4 = {
			borders,
			colIndex: endingColIndex,
			colSpan,
			isSelectingCell,
			minHeight: t3,
			rowIndex: endingRowIndex,
			selected: isCellSelected,
			width
		};
		$[9] = borders;
		$[10] = colSpan;
		$[11] = endingColIndex;
		$[12] = endingRowIndex;
		$[13] = isCellSelected;
		$[14] = isSelectingCell;
		$[15] = t3;
		$[16] = width;
		$[17] = t4;
	} else t4 = $[17];
	return t4;
};
function _temp$1(editor) {
	return editor.getApi(TablePlugin).table.isSelectingCell();
}

//#endregion
//#region src/react/components/TableCellElement/useTableCellElementResizable.ts
const useTableCellElementResizable = (t0) => {
	const $ = c(57);
	const { colIndex, colSpan, rowIndex, step, stepX: t1, stepY: t2 } = t0;
	const stepX = t1 === void 0 ? step : t1;
	const stepY = t2 === void 0 ? step : t2;
	const { editor, getOptions } = useEditorPlugin(TablePlugin);
	const element = useElement();
	let t3;
	if ($[0] !== getOptions) {
		t3 = getOptions();
		$[0] = getOptions;
		$[1] = t3;
	} else t3 = $[1];
	const { disableMarginLeft, minColumnWidth: t4 } = t3;
	const minColumnWidth = t4 === void 0 ? 0 : t4;
	let t5;
	let t6;
	if ($[2] !== colIndex || $[3] !== colSpan) {
		t5 = (t7$1) => {
			const [node] = t7$1;
			return colSpan > 1 ? node.colSizes?.[colIndex] : void 0;
		};
		t6 = [colSpan, colIndex];
		$[2] = colIndex;
		$[3] = colSpan;
		$[4] = t5;
		$[5] = t6;
	} else {
		t5 = $[4];
		t6 = $[5];
	}
	let t7;
	if ($[6] === Symbol.for("react.memo_cache_sentinel")) {
		t7 = { key: KEYS.table };
		$[6] = t7;
	} else t7 = $[6];
	const initialWidth = useElementSelector(t5, t6, t7);
	let t8;
	let t9;
	if ($[7] === Symbol.for("react.memo_cache_sentinel")) {
		t8 = [];
		t9 = { key: KEYS.table };
		$[7] = t8;
		$[8] = t9;
	} else {
		t8 = $[7];
		t9 = $[8];
	}
	const marginLeft = useElementSelector(_temp, t8, t9);
	let t10;
	if ($[9] === Symbol.for("react.memo_cache_sentinel")) {
		t10 = { disableOverrides: true };
		$[9] = t10;
	} else t10 = $[9];
	const colSizesWithoutOverrides = useTableColSizes(t10);
	const colSizesWithoutOverridesRef = React.useRef(colSizesWithoutOverrides);
	let t11;
	let t12;
	if ($[10] !== colSizesWithoutOverrides) {
		t11 = () => {
			colSizesWithoutOverridesRef.current = colSizesWithoutOverrides;
		};
		t12 = [colSizesWithoutOverrides];
		$[10] = colSizesWithoutOverrides;
		$[11] = t11;
		$[12] = t12;
	} else {
		t11 = $[11];
		t12 = $[12];
	}
	React.useEffect(t11, t12);
	const overrideColSize = useOverrideColSize();
	const overrideRowSize = useOverrideRowSize();
	const overrideMarginLeft = useOverrideMarginLeft();
	let t13;
	if ($[13] !== editor || $[14] !== element || $[15] !== overrideColSize) {
		t13 = (colIndex_0, width) => {
			setTableColSize(editor, {
				colIndex: colIndex_0,
				width
			}, { at: element });
			setTimeout(() => overrideColSize(colIndex_0, null), 0);
		};
		$[13] = editor;
		$[14] = element;
		$[15] = overrideColSize;
		$[16] = t13;
	} else t13 = $[16];
	const setColSize = t13;
	let t14;
	if ($[17] !== editor || $[18] !== element || $[19] !== overrideRowSize) {
		t14 = (rowIndex_0, height) => {
			setTableRowSize(editor, {
				height,
				rowIndex: rowIndex_0
			}, { at: element });
			setTimeout(() => overrideRowSize(rowIndex_0, null), 0);
		};
		$[17] = editor;
		$[18] = element;
		$[19] = overrideRowSize;
		$[20] = t14;
	} else t14 = $[20];
	const setRowSize = t14;
	let t15;
	if ($[21] !== editor || $[22] !== element || $[23] !== overrideMarginLeft) {
		t15 = (marginLeft_0) => {
			setTableMarginLeft(editor, { marginLeft: marginLeft_0 }, { at: element });
			setTimeout(() => overrideMarginLeft(null), 0);
		};
		$[21] = editor;
		$[22] = element;
		$[23] = overrideMarginLeft;
		$[24] = t15;
	} else t15 = $[24];
	const setMarginLeft = t15;
	let t16;
	if ($[25] !== colIndex || $[26] !== minColumnWidth || $[27] !== overrideColSize || $[28] !== setColSize || $[29] !== stepX) {
		t16 = (t17$1) => {
			const { delta, finished, initialSize: currentInitial } = t17$1;
			const nextInitial = colSizesWithoutOverridesRef.current[colIndex + 1];
			const complement = (width_0) => currentInitial + nextInitial - width_0;
			const currentNew = roundCellSizeToStep(resizeLengthClampStatic(currentInitial + delta, {
				max: nextInitial ? complement(minColumnWidth) : void 0,
				min: minColumnWidth
			}), stepX);
			const nextNew = nextInitial ? complement(currentNew) : void 0;
			const fn = finished ? setColSize : overrideColSize;
			fn(colIndex, currentNew);
			if (nextNew) fn(colIndex + 1, nextNew);
		};
		$[25] = colIndex;
		$[26] = minColumnWidth;
		$[27] = overrideColSize;
		$[28] = setColSize;
		$[29] = stepX;
		$[30] = t16;
	} else t16 = $[30];
	const handleResizeRight = t16;
	let t17;
	if ($[31] !== overrideRowSize || $[32] !== rowIndex || $[33] !== setRowSize || $[34] !== stepY) {
		t17 = (event) => {
			const newHeight = roundCellSizeToStep(event.initialSize + event.delta, stepY);
			if (event.finished) setRowSize(rowIndex, newHeight);
			else overrideRowSize(rowIndex, newHeight);
		};
		$[31] = overrideRowSize;
		$[32] = rowIndex;
		$[33] = setRowSize;
		$[34] = stepY;
		$[35] = t17;
	} else t17 = $[35];
	const handleResizeBottom = t17;
	let t18;
	if ($[36] !== colIndex || $[37] !== marginLeft || $[38] !== minColumnWidth || $[39] !== overrideColSize || $[40] !== overrideMarginLeft || $[41] !== setColSize || $[42] !== setMarginLeft || $[43] !== stepX) {
		t18 = (event_0) => {
			const initial = colSizesWithoutOverridesRef.current[colIndex];
			const complement_0 = (width_1) => initial + marginLeft - width_1;
			const newMargin = roundCellSizeToStep(resizeLengthClampStatic(marginLeft + event_0.delta, {
				max: complement_0(minColumnWidth),
				min: 0
			}), stepX);
			const newWidth = complement_0(newMargin);
			if (event_0.finished) {
				setMarginLeft(newMargin);
				setColSize(colIndex, newWidth);
			} else {
				overrideMarginLeft(newMargin);
				overrideColSize(colIndex, newWidth);
			}
		};
		$[36] = colIndex;
		$[37] = marginLeft;
		$[38] = minColumnWidth;
		$[39] = overrideColSize;
		$[40] = overrideMarginLeft;
		$[41] = setColSize;
		$[42] = setMarginLeft;
		$[43] = stepX;
		$[44] = t18;
	} else t18 = $[44];
	const handleResizeLeft = t18;
	const hasLeftHandle = colIndex === 0 && !disableMarginLeft;
	let t19;
	if ($[45] !== handleResizeBottom) {
		t19 = { options: {
			direction: "bottom",
			onResize: handleResizeBottom
		} };
		$[45] = handleResizeBottom;
		$[46] = t19;
	} else t19 = $[46];
	const t20 = t19;
	const t21 = !hasLeftHandle;
	let t22;
	if ($[47] !== handleResizeLeft) {
		t22 = { options: {
			direction: "left",
			onResize: handleResizeLeft
		} };
		$[47] = handleResizeLeft;
		$[48] = t22;
	} else t22 = $[48];
	const t23 = t22;
	let t24;
	if ($[49] !== handleResizeRight || $[50] !== initialWidth) {
		t24 = { options: {
			direction: "right",
			initialSize: initialWidth,
			onResize: handleResizeRight
		} };
		$[49] = handleResizeRight;
		$[50] = initialWidth;
		$[51] = t24;
	} else t24 = $[51];
	const t25 = t24;
	let t26;
	if ($[52] !== t20 || $[53] !== t21 || $[54] !== t23 || $[55] !== t25) {
		t26 = {
			bottomProps: t20,
			hiddenLeft: t21,
			leftProps: t23,
			rightProps: t25
		};
		$[52] = t20;
		$[53] = t21;
		$[54] = t23;
		$[55] = t25;
		$[56] = t26;
	} else t26 = $[56];
	return t26;
};
function _temp(t0) {
	const [node_0] = t0;
	return node_0.marginLeft ?? 0;
}

//#endregion
//#region src/react/hooks/useTableMergeState.ts
const useTableMergeState = () => {
	const { api, editor, getOptions } = useEditorPlugin(TablePlugin);
	const { disableMerge } = getOptions();
	if (disableMerge) return {
		canMerge: false,
		canSplit: false
	};
	const readOnly = useReadOnly();
	const someTable = useEditorSelector((editor$1) => editor$1.api.some({ match: { type: KEYS.table } }), []);
	const selectionExpanded = useEditorSelector((editor$1) => editor$1.api.isExpanded(), []);
	const collapsed = !readOnly && someTable && !selectionExpanded;
	const selectedCellEntries = useEditorSelector((editor$1) => getSelectedCellEntries(editor$1), []);
	const isRectangularSelection = React.useMemo(() => {
		if (selectedCellEntries.length <= 1) return false;
		const selectedCells = selectedCellEntries.map(([cell]) => cell);
		const { maxCol, maxRow, minCol, minRow } = getSelectedCellsBoundingBox(editor, selectedCells);
		return selectedCells.reduce((total, cell) => total + api.table.getColSpan(cell) * api.table.getRowSpan(cell), 0) === (maxCol - minCol + 1) * (maxRow - minRow + 1);
	}, [
		api.table,
		editor,
		selectedCellEntries
	]);
	if (!selectedCellEntries) return {
		canMerge: false,
		canSplit: false
	};
	return {
		canMerge: !readOnly && someTable && selectionExpanded && selectedCellEntries.length > 1 && isRectangularSelection,
		canSplit: collapsed && selectedCellEntries.length === 1 && (api.table.getColSpan(selectedCellEntries[0][0]) > 1 || api.table.getRowSpan(selectedCellEntries[0][0]) > 1)
	};
};

//#endregion
export { TableCellHeaderPlugin, TableCellPlugin, TablePlugin, TableProvider, TableRowPlugin, getOnSelectTableBorderFactory, onKeyDownTable, roundCellSizeToStep, setSelectedCellsBorder, tableStore, useCellIndices, useIsCellSelected, useOverrideColSize, useOverrideMarginLeft, useOverrideRowSize, useSelectedCells, useTableBordersDropdownMenuContentState, useTableCellBorders, useTableCellElement, useTableCellElementResizable, useTableCellSize, useTableColSizes, useTableElement, useTableMergeState, useTableSelectionDom, useTableSet, useTableState, useTableStore, useTableValue };