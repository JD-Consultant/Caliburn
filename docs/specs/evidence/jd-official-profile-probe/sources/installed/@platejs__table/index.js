import { $ as getSelectedCellEntries, A as normalizeInitialValueTable, B as deleteColumnWhenExpanded, C as moveSelectionFromCell, Ct as getColSpan, D as deleteTable, E as insertTable, Et as getEmptyCellNode, F as deleteTableMergeRow, G as getTableAbove, H as getTableColumnCount, I as deleteRowWhenExpanded, J as isSelectedCellBordersNone, K as getSelectedCellsBorders, L as deleteTableMergeColumn, M as mergeTableCells, N as insertTableMergeRow, O as deleteRow, P as insertTableMergeColumn, Q as getSelectedCell, R as getTableMergedColumnCount, S as setBorderSize, St as getRowSpan, T as insertTableColumn, Tt as getEmptyRowNode, U as getTableCellSize, V as getTableOverriddenColSizes, W as getTableCellBorders, X as getTopTableCell, Y as isSelectedCellBordersOuter, Z as getSelectedCellsBoundingBox, _ as hasAdjacentBlockInCell, _t as getCellTypes, a as BaseTableRowPlugin, at as isSelectingCell, b as setTableMarginLeft, bt as computeCellIndices, c as withSetFragmentDataTable, ct as getTableMergeGridByRange, d as withInsertFragmentTable, dt as getNextTableCell, et as getSelectedCellIds, f as withGetFragmentTable, ft as getLeftTableCell, g as getTableMoveSelectionContext, gt as getTableEntries, h as withApplyTable, ht as getAdjacentTableCell, i as BaseTablePlugin, it as isCellSelected, j as splitTableCell, k as deleteColumn, l as withNormalizeTable, lt as findCellByIndexes, m as withDeleteTable, mt as getCellInNextTableRow, n as BaseTableCellHeaderPlugin, nt as getSelectedTableIds, o as withTable, ot as getTableGridAbove, p as preventDeleteTableCell, pt as getCellInPreviousTableRow, q as isSelectedCellBorder, r as BaseTableCellPlugin, rt as getSelectedTables, s as withTableCellSelection, st as getTableGridByRange, t as KEY_SHIFT_EDGES, tt as getSelectedCells, u as withInsertTextTable, ut as getPreviousTableCell, v as shouldMoveSelectionFromCell, vt as getCellRowIndexByPath, w as insertTableRow, wt as getEmptyTableNode, x as setTableColSize, xt as getCellIndicesWithSpans, y as setTableRowSize, yt as getCellIndices, z as getCellPath } from "./constants-6xljcM3U.js";
import { PathApi } from "platejs";

//#region src/lib/queries/getTableColumnIndex.ts
/** Get table column index of a cell node. */
const getTableColumnIndex = (editor, cellNode) => {
	const path = editor.api.findPath(cellNode);
	if (!path) return -1;
	const [trNode] = editor.api.parent(path) ?? [];
	if (!trNode) return -1;
	let colIndex = -1;
	trNode.children.some((item, index) => {
		if (item === cellNode) {
			colIndex = index;
			return true;
		}
		return false;
	});
	return colIndex;
};

//#endregion
//#region src/lib/queries/getTableRowIndex.ts
/** Get table row index of a cell node. */
const getTableRowIndex = (editor, cellNode) => {
	const path = editor.api.findPath(cellNode);
	if (!path) return 0;
	return PathApi.parent(path).at(-1);
};

//#endregion
//#region src/lib/queries/isTableBorderHidden.ts
const isTableBorderHidden = (editor, border) => {
	if (border === "left") {
		const node = getLeftTableCell(editor)?.[0];
		if (node) return node.borders?.right?.size === 0;
	}
	if (border === "top") {
		const node = getTopTableCell(editor)?.[0];
		if (node) return node.borders?.bottom?.size === 0;
	}
	return editor.api.node({ match: { type: getCellTypes(editor) } })?.[0].borders?.[border]?.size === 0;
};

//#endregion
//#region src/lib/merge/getSelectionWidth.ts
const getSelectionWidth = (cells) => {
	let max = 0;
	let lastCellRowIndex = getCellRowIndexByPath(cells[0][1]);
	let total = 0;
	cells.forEach(([cell, cellPath]) => {
		const currentCellRowIndex = getCellRowIndexByPath(cellPath);
		const colSpan = cell.colSpan ?? cell.attributes?.colspan;
		const colSpanNumbered = colSpan ? Number(colSpan) : 1;
		if (currentCellRowIndex === lastCellRowIndex) total += colSpanNumbered;
		else {
			max = Math.max(total, max);
			total = colSpanNumbered;
		}
		lastCellRowIndex = currentCellRowIndex;
	});
	return Math.max(total, max);
};

//#endregion
//#region src/lib/merge/isTableRectangular.ts
const allEqual = (arr) => arr.every((val) => val === arr[0]);
/**
* Checks if the given table is rectangular, meaning all rows have the same
* effective number of cells, considering colspan and rowspan.
*/
const isTableRectangular = (table) => {
	const arr = [];
	table?.children?.forEach((row, rI) => {
		row.children?.forEach((cell) => {
			const cellElem = cell;
			Array.from({ length: getRowSpan(cellElem) || 1 }).forEach((_, i) => {
				if (!arr[rI + i]) arr[rI + i] = 0;
				arr[rI + i] += getColSpan(cellElem);
			});
		});
	});
	return allEqual(arr);
};

//#endregion
//#region src/lib/transforms/setCellBackground.ts
const setCellBackground = (editor, options) => {
	const { color, selectedCells } = options;
	if (selectedCells && selectedCells.length > 0) {
		selectedCells.forEach((cell) => {
			const cellPath = editor.api.findPath(cell);
			if (cellPath) editor.tf.setNodes({ background: color }, { at: cellPath });
		});
		return;
	}
	const currentCell = editor.api.node({ match: { type: getCellTypes(editor) } })?.[0];
	if (currentCell) {
		const cellPath = editor.api.findPath(currentCell);
		if (cellPath) editor.tf.setNodes({ background: color }, { at: cellPath });
	}
};

//#endregion
export { BaseTableCellHeaderPlugin, BaseTableCellPlugin, BaseTablePlugin, BaseTableRowPlugin, KEY_SHIFT_EDGES, computeCellIndices, deleteColumn, deleteColumnWhenExpanded, deleteRow, deleteRowWhenExpanded, deleteTable, deleteTableMergeColumn, deleteTableMergeRow, findCellByIndexes, getAdjacentTableCell, getCellInNextTableRow, getCellInPreviousTableRow, getCellIndices, getCellIndicesWithSpans, getCellPath, getCellRowIndexByPath, getCellTypes, getColSpan, getEmptyCellNode, getEmptyRowNode, getEmptyTableNode, getLeftTableCell, getNextTableCell, getPreviousTableCell, getRowSpan, getSelectedCell, getSelectedCellEntries, getSelectedCellIds, getSelectedCells, getSelectedCellsBorders, getSelectedCellsBoundingBox, getSelectedTableIds, getSelectedTables, getSelectionWidth, getTableAbove, getTableCellBorders, getTableCellSize, getTableColumnCount, getTableColumnIndex, getTableEntries, getTableGridAbove, getTableGridByRange, getTableMergeGridByRange, getTableMergedColumnCount, getTableMoveSelectionContext, getTableOverriddenColSizes, getTableRowIndex, getTopTableCell, hasAdjacentBlockInCell, insertTable, insertTableColumn, insertTableMergeColumn, insertTableMergeRow, insertTableRow, isCellSelected, isSelectedCellBorder, isSelectedCellBordersNone, isSelectedCellBordersOuter, isSelectingCell, isTableBorderHidden, isTableRectangular, mergeTableCells, moveSelectionFromCell, normalizeInitialValueTable, preventDeleteTableCell, setBorderSize, setCellBackground, setTableColSize, setTableMarginLeft, setTableRowSize, shouldMoveSelectionFromCell, splitTableCell, withApplyTable, withDeleteTable, withGetFragmentTable, withInsertFragmentTable, withInsertTextTable, withNormalizeTable, withSetFragmentDataTable, withTable, withTableCellSelection };