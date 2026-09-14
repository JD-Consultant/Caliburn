import { ElementApi, KEYS, NodeApi, PathApi, PointApi, RangeApi, TextApi, bindFirst, combineTransformMatchOptions, createSlatePlugin, createTSlatePlugin, getEditorPlugin, getPluginTypes } from "platejs";
import cloneDeep from "lodash/cloneDeep.js";

//#region src/lib/api/getEmptyCellNode.ts
const getEmptyCellNode = (editor, { children, header, row } = {}) => {
	header = header ?? (row ? row.children.every((c) => c.type === editor.getType(KEYS.th)) : false);
	return {
		children: children ?? [editor.api.create.block()],
		type: header ? editor.getType(KEYS.th) : editor.getType(KEYS.td)
	};
};

//#endregion
//#region src/lib/api/getEmptyRowNode.ts
const getEmptyRowNode = (editor, { colCount = 1, ...cellOptions } = {}) => {
	const { api } = editor.getPlugin({ key: KEYS.table });
	return {
		children: Array.from({ length: colCount }).fill(colCount).map(() => api.create.tableCell(cellOptions)),
		type: editor.getType(KEYS.tr)
	};
};

//#endregion
//#region src/lib/api/getEmptyTableNode.ts
const getEmptyTableNode = (editor, { colCount, header, rowCount = 0, ...cellOptions } = {}) => {
	const { api } = editor.getPlugin({ key: KEYS.table });
	return {
		children: Array.from({ length: rowCount }).fill(rowCount).map((_, index) => api.create.tableRow({
			colCount,
			...cellOptions,
			header: header && index === 0
		})),
		type: editor.getType(KEYS.table)
	};
};

//#endregion
//#region src/lib/queries/getColSpan.ts
/**
* Returns the colspan attribute of the table cell element.
*
* @default 1 if undefined.
*/
const getColSpan = (cellElem) => cellElem.colSpan || Number(cellElem.attributes?.colspan) || 1;

//#endregion
//#region src/lib/queries/getRowSpan.ts
/**
* Returns the rowspan attribute of the table cell element.
*
* @default 1 if undefined
*/
const getRowSpan = (cellElem) => cellElem.rowSpan || Number(cellElem.attributes?.rowspan) || 1;

//#endregion
//#region src/lib/merge/getCellIndicesWithSpans.ts
const getCellIndicesWithSpans = ({ col, row }, endCell) => ({
	col: col + getColSpan(endCell) - 1,
	row: row + getRowSpan(endCell) - 1
});

//#endregion
//#region src/lib/utils/computeCellIndices.ts
function computeCellIndices(editor, { all, cellNode, tableNode }) {
	const { api, getOptions, setOption } = getEditorPlugin(editor, { key: KEYS.table });
	if (!tableNode) {
		if (!cellNode) return;
		tableNode = editor.api.above({
			at: cellNode,
			match: { type: editor.getType(KEYS.table) }
		})?.[0];
		if (!tableNode) return;
	}
	const { _cellIndices: prevIndices } = getOptions();
	const cellIndices = { ...prevIndices };
	let hasIndicesChanged = false;
	const skipCells = [];
	let targetIndices;
	for (let rowIndex = 0; rowIndex < tableNode.children.length; rowIndex++) {
		const row = tableNode.children[rowIndex];
		let colIndex = 0;
		for (const cellElement of row.children) {
			while (skipCells[rowIndex]?.[colIndex]) colIndex++;
			const currentIndices = {
				col: colIndex,
				row: rowIndex
			};
			const prevIndicesForCell = prevIndices[cellElement.id];
			if (prevIndicesForCell?.col !== currentIndices.col || prevIndicesForCell?.row !== currentIndices.row) hasIndicesChanged = true;
			cellIndices[cellElement.id] = currentIndices;
			if (cellElement.id === cellNode?.id) {
				targetIndices = currentIndices;
				if (!all) break;
			}
			const colSpan = api.table.getColSpan(cellElement);
			const rowSpan = api.table.getRowSpan(cellElement);
			for (let r = 0; r < rowSpan; r++) {
				skipCells[rowIndex + r] = skipCells[rowIndex + r] || [];
				for (let c = 0; c < colSpan; c++) skipCells[rowIndex + r][colIndex + c] = true;
			}
			colIndex += colSpan;
		}
	}
	if (hasIndicesChanged) setOption("_cellIndices", cellIndices);
	return targetIndices;
}

//#endregion
//#region src/lib/utils/getCellIndices.ts
const getCellIndices = (editor, element) => {
	const { getOption } = getEditorPlugin(editor, { key: KEYS.table });
	let indices = getOption("cellIndices", element.id);
	if (!indices) {
		indices = computeCellIndices(editor, { cellNode: element });
		if (!indices) editor.api.debug.warn("No cell indices found for element. Make sure all table cells have an id.", "TABLE_CELL_INDICES");
	}
	return indices ?? {
		col: 0,
		row: 0
	};
};

//#endregion
//#region src/lib/utils/getCellRowIndexByPath.ts
const getCellRowIndexByPath = (cellPath) => {
	const index = cellPath.at(-2);
	if (index === void 0) throw new Error(`can not get rowIndex of path ${cellPath}`);
	return index;
};

//#endregion
//#region src/lib/utils/getCellType.ts
/** Get td and th types */
const getCellTypes = (editor) => getPluginTypes(editor, [KEYS.td, KEYS.th]);

//#endregion
//#region src/lib/queries/getTableEntries.ts
/**
* If at (default = selection) is in table>tr>td|th, return table, row, and cell
* node entries.
*/
const getTableEntries = (editor, { at = editor.selection } = {}) => {
	if (!at) return;
	const cellEntry = editor.api.node({
		at,
		match: { type: getCellTypes(editor) }
	});
	if (!cellEntry) return;
	const [, cellPath] = cellEntry;
	const rowEntry = editor.api.above({
		at: cellPath,
		match: { type: editor.getType(KEYS.tr) }
	});
	if (!rowEntry) return;
	const [, rowPath] = rowEntry;
	const tableEntry = editor.api.above({
		at: rowPath,
		match: { type: editor.getType(KEYS.table) }
	});
	if (!tableEntry) return;
	return {
		cell: cellEntry,
		row: rowEntry,
		table: tableEntry
	};
};

//#endregion
//#region src/lib/queries/getAdjacentTableCell.ts
const adjacentTableCellLookup = /* @__PURE__ */ new WeakMap();
const getLookupKey = (row, col) => `${row}:${col}`;
const createTableCellLookup = (editor, tableEntry) => {
	const [table, tablePath] = tableEntry;
	const cachedLookup = adjacentTableCellLookup.get(table);
	if (cachedLookup) return cachedLookup;
	const nextLookup = /* @__PURE__ */ new Map();
	table.children.forEach((rowNode, rowIndex) => {
		rowNode.children.forEach((cellNode, cellIndex) => {
			const cellEntry = [cellNode, tablePath.concat([rowIndex, cellIndex])];
			const indices = getCellIndices(editor, cellEntry[0]);
			const { col: endCol, row: endRow } = getCellIndicesWithSpans(indices, cellEntry[0]);
			for (let row = indices.row; row <= endRow; row++) for (let col = indices.col; col <= endCol; col++) nextLookup.set(getLookupKey(row, col), cellEntry);
		});
	});
	adjacentTableCellLookup.set(table, nextLookup);
	return nextLookup;
};
const getAdjacentTableCell = (editor, { at, deltaCol = 0, deltaRow = 0 } = {}) => {
	const entries = getTableEntries(editor, { at });
	if (!entries) return;
	const [cell] = entries.cell;
	const tableEntry = entries.table;
	const { col, row } = getCellIndices(editor, cell);
	const nextCol = col + deltaCol;
	const nextRow = row + deltaRow;
	if (nextCol < 0 || nextRow < 0) return;
	return createTableCellLookup(editor, tableEntry).get(getLookupKey(nextRow, nextCol));
};

//#endregion
//#region src/lib/queries/getCellInNextTableRow.ts
const getCellInNextTableRow = (editor, currentRowPath) => {
	const nextRow = editor.api.node(PathApi.next(currentRowPath));
	if (!nextRow) return;
	const [nextRowNode, nextRowPath] = nextRow;
	const nextCell = nextRowNode?.children?.[0];
	const nextCellPath = nextRowPath.concat(0);
	if (nextCell && nextCellPath) return editor.api.node(nextCellPath);
};

//#endregion
//#region src/lib/queries/getCellInPreviousTableRow.ts
const getCellInPreviousTableRow = (editor, currentRowPath) => {
	const prevPath = PathApi.previous(currentRowPath);
	if (!prevPath) return;
	const previousRow = editor.api.node(prevPath);
	if (!previousRow) return;
	const [previousRowNode, previousRowPath] = previousRow;
	const previousCell = previousRowNode?.children?.[previousRowNode.children.length - 1];
	const previousCellPath = previousRowPath.concat(previousRowNode.children.length - 1);
	if (previousCell && previousCellPath) return editor.api.node(previousCellPath);
};

//#endregion
//#region src/lib/queries/getLeftTableCell.ts
const getLeftTableCell = (editor, { at: cellPath } = {}) => getAdjacentTableCell(editor, {
	at: cellPath,
	deltaCol: -1
});

//#endregion
//#region src/lib/queries/getNextTableCell.ts
const getNextTableCell = (editor, _currentCell, currentPath, currentRow) => {
	const cell = editor.api.node(PathApi.next(currentPath));
	if (cell) return cell;
	const [, currentRowPath] = currentRow;
	return getCellInNextTableRow(editor, currentRowPath);
};

//#endregion
//#region src/lib/queries/getPreviousTableCell.ts
const getPreviousTableCell = (editor, _currentCell, currentPath, currentRow) => {
	const prevPath = PathApi.previous(currentPath);
	if (!prevPath) {
		const [, currentRowPath] = currentRow;
		return getCellInPreviousTableRow(editor, currentRowPath);
	}
	const cell = editor.api.node(prevPath);
	if (cell) return cell;
};

//#endregion
//#region src/lib/merge/findCellByIndexes.ts
const findCellByIndexes = (editor, table, searchRowIndex, searchColIndex) => {
	return table.children.flatMap((current) => current.children).find((cellNode) => {
		const indices = getCellIndices(editor, cellNode);
		const { col: _startColIndex, row: _startRowIndex } = indices;
		const { col: _endColIndex, row: _endRowIndex } = getCellIndicesWithSpans(indices, cellNode);
		if (searchColIndex >= _startColIndex && searchColIndex <= _endColIndex && searchRowIndex >= _startRowIndex && searchRowIndex <= _endRowIndex) return true;
		return false;
	});
};

//#endregion
//#region src/lib/merge/getTableGridByRange.ts
/**
* Get sub table between 2 cell paths. Ensure that the selection is always a
* valid table grid.
*/
const getTableMergeGridByRange = (editor, { at, format }) => {
	const { api, type } = getEditorPlugin(editor, BaseTablePlugin);
	const startCellEntry = editor.api.node({
		at: at.anchor.path,
		match: { type: getCellTypes(editor) }
	});
	const endCellEntry = editor.api.node({
		at: at.focus.path,
		match: { type: getCellTypes(editor) }
	});
	const startCell = startCellEntry[0];
	const endCell = endCellEntry[0];
	const tablePath = startCellEntry[1].slice(0, -2);
	const realTable = editor.api.node({
		at: tablePath,
		match: { type }
	})[0];
	const { col: _startColIndex, row: _startRowIndex } = getCellIndicesWithSpans(getCellIndices(editor, startCell), startCell);
	const { col: _endColIndex, row: _endRowIndex } = getCellIndicesWithSpans(getCellIndices(editor, endCell), endCell);
	let startRowIndex = Math.min(_startRowIndex, _endRowIndex);
	let endRowIndex = Math.max(_startRowIndex, _endRowIndex);
	let startColIndex = Math.min(_startColIndex, _endColIndex);
	let endColIndex = Math.max(_startColIndex, _endColIndex);
	const relativeRowIndex = endRowIndex - startRowIndex;
	const relativeColIndex = endColIndex - startColIndex;
	let table = api.create.table({
		children: [],
		colCount: relativeColIndex + 1,
		rowCount: relativeRowIndex + 1
	});
	let cellEntries = [];
	let cellsSet = /* @__PURE__ */ new WeakSet();
	let rowIndex = startRowIndex;
	let colIndex = startColIndex;
	while (true) {
		const cell = findCellByIndexes(editor, realTable, rowIndex, colIndex);
		if (!cell) break;
		const indicies = getCellIndices(editor, cell);
		const { col: cellColWithSpan, row: cellRowWithSpan } = getCellIndicesWithSpans(indicies, cell);
		const { col: cellCol, row: cellRow } = indicies;
		if (cellRow < startRowIndex || cellRowWithSpan > endRowIndex || cellCol < startColIndex || cellColWithSpan > endColIndex) {
			cellsSet = /* @__PURE__ */ new WeakSet();
			cellEntries = [];
			startRowIndex = Math.min(startRowIndex, cellRow);
			endRowIndex = Math.max(endRowIndex, cellRowWithSpan);
			startColIndex = Math.min(startColIndex, cellCol);
			endColIndex = Math.max(endColIndex, cellColWithSpan);
			rowIndex = startRowIndex;
			colIndex = startColIndex;
			const newRelativeRowIndex = endRowIndex - startRowIndex;
			const newRelativeColIndex = endColIndex - startColIndex;
			table = api.create.table({
				children: [],
				colCount: newRelativeColIndex + 1,
				rowCount: newRelativeRowIndex + 1
			});
			continue;
		}
		if (!cellsSet.has(cell)) {
			cellsSet.add(cell);
			const rows = table.children[rowIndex - startRowIndex].children;
			rows[colIndex - startColIndex] = cell;
			const cellPath = editor.api.findPath(cell);
			cellEntries.push([cell, cellPath]);
		}
		if (colIndex + 1 <= endColIndex) colIndex += 1;
		else if (rowIndex + 1 <= endRowIndex) {
			colIndex = startColIndex;
			rowIndex += 1;
		} else break;
	}
	const formatType = format || "table";
	if (formatType === "cell") return cellEntries;
	table.children?.forEach((rowEl) => {
		const rowElement = rowEl;
		rowElement.children = rowElement.children?.filter((cellEl) => {
			const cellElement = cellEl;
			return api.table.getCellChildren(cellElement).length > 0;
		});
	});
	if (formatType === "table") return [[table, tablePath]];
	return {
		cellEntries,
		tableEntries: [[table, tablePath]]
	};
};

//#endregion
//#region src/lib/queries/getTableGridByRange.ts
const hasMergedCells = (table) => !!table?.children.some((row) => row.children.some((cell) => {
	const tableCell = cell;
	return getColSpan(tableCell) > 1 || getRowSpan(tableCell) > 1;
}));
/** Get sub table between 2 cell paths. */
const getTableGridByRange = (editor, { at, format = "table" }) => {
	const { api } = editor.getPlugin({ key: KEYS.table });
	const { disableMerge } = editor.getOptions(BaseTablePlugin);
	const startCellPath = at.anchor.path;
	const endCellPath = at.focus.path;
	const tablePath = startCellPath.slice(0, -2);
	const tableNode = NodeApi.get(editor, tablePath);
	if (!disableMerge && hasMergedCells(tableNode)) return getTableMergeGridByRange(editor, {
		at,
		format
	});
	const _startRowIndex = startCellPath.at(-2);
	const _endRowIndex = endCellPath.at(-2);
	const _startColIndex = startCellPath.at(-1);
	const _endColIndex = endCellPath.at(-1);
	const startRowIndex = Math.min(_startRowIndex, _endRowIndex);
	const endRowIndex = Math.max(_startRowIndex, _endRowIndex);
	const startColIndex = Math.min(_startColIndex, _endColIndex);
	const endColIndex = Math.max(_startColIndex, _endColIndex);
	const relativeRowIndex = endRowIndex - startRowIndex;
	const relativeColIndex = endColIndex - startColIndex;
	const table = api.create.table({
		children: [],
		colCount: relativeColIndex + 1,
		rowCount: relativeRowIndex + 1
	});
	let rowIndex = startRowIndex;
	let colIndex = startColIndex;
	const cellEntries = [];
	while (true) {
		const cellPath = tablePath.concat([rowIndex, colIndex]);
		const cell = NodeApi.get(editor, cellPath);
		if (!cell) break;
		const rows = table.children[rowIndex - startRowIndex].children;
		rows[colIndex - startColIndex] = cell;
		cellEntries.push([cell, cellPath]);
		if (colIndex + 1 <= endColIndex) colIndex += 1;
		else if (rowIndex + 1 <= endRowIndex) {
			colIndex = startColIndex;
			rowIndex += 1;
		} else break;
	}
	if (format === "cell") return cellEntries;
	return [[table, tablePath]];
};

//#endregion
//#region src/lib/queries/getTableGridAbove.ts
/** Get sub table above anchor and focus. Format: tables or cells. */
const getTableGridAbove = (editor, { format = "table", ...options } = {}) => {
	const { api } = editor.getPlugin({ key: KEYS.table });
	const edges = editor.api.edgeBlocks({
		match: { type: getCellTypes(editor) },
		...options
	});
	if (edges) {
		const [start, end] = edges;
		if (!PathApi.equals(start[1], end[1])) return getTableGridByRange(editor, {
			at: {
				anchor: {
					offset: 0,
					path: start[1]
				},
				focus: {
					offset: 0,
					path: end[1]
				}
			},
			format
		});
		if (format === "table") {
			const table = api.create.table({ rowCount: 1 });
			table.children[0].children = [start[0]];
			return [[table, start[1].slice(0, -2)]];
		}
		return [start];
	}
	return [];
};

//#endregion
//#region src/lib/queries/getSelectedCells.ts
const selectionQueryCache = /* @__PURE__ */ new WeakMap();
const getSelectionQueryCache = (editor) => {
	const { selection } = editor;
	const { children } = editor;
	const cachedValue = selectionQueryCache.get(editor);
	if (cachedValue && cachedValue.children === children && cachedValue.selection === selection) return cachedValue;
	const nextValue = {
		children,
		selection
	};
	selectionQueryCache.set(editor, nextValue);
	return nextValue;
};
const getSelectedCellEntries = (editor) => {
	const cache = getSelectionQueryCache(editor);
	if ("cellEntries" in cache) return cache.cellEntries ?? [];
	const cellEntries = getTableGridAbove(editor, { format: "cell" });
	const nextValue = cellEntries.length > 1 ? cellEntries : [];
	cache.cellEntries = nextValue;
	return nextValue;
};
const getSelectedCells = (editor) => {
	const cache = getSelectionQueryCache(editor);
	if ("selectedCells" in cache) return cache.selectedCells ?? null;
	const cellEntries = getSelectedCellEntries(editor);
	if (cellEntries.length === 0) {
		cache.selectedCells = null;
		return null;
	}
	const nextValue = cellEntries.map(([cell]) => cell);
	cache.selectedCells = nextValue;
	return nextValue;
};
const getSelectedCellIds = (editor) => {
	const cache = getSelectionQueryCache(editor);
	if ("selectedCellIds" in cache) return cache.selectedCellIds ?? null;
	const selectedCellIds = getSelectedCellEntries(editor).map(([cell]) => cell.id).filter((id) => !!id);
	const nextValue = selectedCellIds.length > 0 ? selectedCellIds : null;
	cache.selectedCellIds = nextValue;
	return nextValue;
};
const getSelectedTableIds = (editor) => {
	const cache = getSelectionQueryCache(editor);
	if ("selectedTableIds" in cache) return cache.selectedTableIds ?? null;
	const selectedTables = getSelectedTables(editor);
	if (!selectedTables) {
		cache.selectedTableIds = null;
		return null;
	}
	const selectedTableIds = selectedTables.map((table) => table.id).filter((id) => !!id);
	const nextValue = selectedTableIds.length > 0 ? selectedTableIds : null;
	cache.selectedTableIds = nextValue;
	return nextValue;
};
const getSelectedCell = (editor, id) => {
	if (!id) return null;
	return getSelectedCellEntries(editor).find(([cell]) => cell.id === id)?.[0] ?? null;
};
const getSelectedTables = (editor) => {
	const cache = getSelectionQueryCache(editor);
	if ("selectedTables" in cache) return cache.selectedTables ?? null;
	if (getSelectedCellEntries(editor).length === 0) {
		cache.selectedTables = null;
		return null;
	}
	const nextValue = getTableGridAbove(editor, { format: "table" }).map(([table]) => table);
	cache.selectedTables = nextValue;
	return nextValue;
};
const isCellSelected = (editor, id) => !!getSelectedCell(editor, id);
const isSelectingCell = (editor) => getSelectedCellEntries(editor).length > 0;

//#endregion
//#region src/lib/queries/getSelectedCellsBoundingBox.ts
/** Return bounding box [minRow..maxRow, minCol..maxCol] of all selected cells. */
function getSelectedCellsBoundingBox(editor, cells) {
	let minRow = Number.POSITIVE_INFINITY;
	let maxRow = Number.NEGATIVE_INFINITY;
	let minCol = Number.POSITIVE_INFINITY;
	let maxCol = Number.NEGATIVE_INFINITY;
	for (const cell of cells) {
		const { col, row } = getCellIndices(editor, cell);
		const cSpan = getColSpan(cell);
		const endRow = row + getRowSpan(cell) - 1;
		const endCol = col + cSpan - 1;
		if (row < minRow) minRow = row;
		if (endRow > maxRow) maxRow = endRow;
		if (col < minCol) minCol = col;
		if (endCol > maxCol) maxCol = endCol;
	}
	return {
		maxCol,
		maxRow,
		minCol,
		minRow
	};
}

//#endregion
//#region src/lib/queries/getTopTableCell.ts
const getTopTableCell = (editor, { at: cellPath } = {}) => getAdjacentTableCell(editor, {
	at: cellPath,
	deltaRow: -1
});

//#endregion
//#region src/lib/queries/getSelectedCellsBorders.ts
/**
* Get all border states for the selected cells at once. Returns an object with
* boolean flags for each border state:
*
* - Top/bottom/left/right: true if border is visible (size > 0)
* - Outer: true if all outer borders are visible
* - None: true if all borders are hidden (size === 0)
*/
const getSelectedCellsBorders = (editor, selectedCells, options = {}) => {
	const { select = {
		none: true,
		outer: true,
		side: true
	} } = options;
	let cells = selectedCells;
	if (!cells || cells.length === 0) {
		const cell = editor.api.block({ match: { type: getCellTypes(editor) } });
		if (cell) cells = [cell[0]];
		else return {
			bottom: true,
			left: true,
			none: false,
			outer: true,
			right: true,
			top: true
		};
	}
	const cellElements = cells.map((cell) => cell);
	const { maxCol, maxRow, minCol, minRow } = getSelectedCellsBoundingBox(editor, cellElements);
	let hasAnyBorder = false;
	let allOuterBordersSet = true;
	const borderStates = {
		bottom: false,
		left: false,
		right: false,
		top: false
	};
	for (const cell of cellElements) {
		const { col, row } = getCellIndices(editor, cell);
		const cellPath = editor.api.findPath(cell);
		const cSpan = getColSpan(cell);
		const rSpan = getRowSpan(cell);
		const isFirstRow = row === 0;
		const isFirstCell = col === 0;
		if (!cellPath) continue;
		if (select.none && !hasAnyBorder) {
			if (isFirstRow && (cell.borders?.top?.size ?? 1) > 0) hasAnyBorder = true;
			if (isFirstCell && (cell.borders?.left?.size ?? 1) > 0) hasAnyBorder = true;
			if ((cell.borders?.bottom?.size ?? 1) > 0) hasAnyBorder = true;
			if ((cell.borders?.right?.size ?? 1) > 0) hasAnyBorder = true;
			if (!hasAnyBorder) {
				if (!isFirstRow) {
					const cellAboveEntry = getTopTableCell(editor, { at: cellPath });
					if (cellAboveEntry && (cellAboveEntry[0].borders?.bottom?.size ?? 1) > 0) hasAnyBorder = true;
				}
				if (!isFirstCell) {
					const prevCellEntry = getLeftTableCell(editor, { at: cellPath });
					if (prevCellEntry && (prevCellEntry[0].borders?.right?.size ?? 1) > 0) hasAnyBorder = true;
				}
			}
		}
		if (select.side || select.outer) for (let rr = row; rr < row + rSpan; rr++) for (let cc = col; cc < col + cSpan; cc++) {
			if (rr === minRow) if (isFirstRow) {
				if ((cell.borders?.top?.size ?? 1) < 1) {
					borderStates.top = false;
					if (select.outer) allOuterBordersSet = false;
				} else if (!borderStates.top) borderStates.top = true;
			} else {
				const cellAboveEntry = getTopTableCell(editor, { at: cellPath });
				if (cellAboveEntry) {
					const [cellAbove] = cellAboveEntry;
					if ((cellAbove.borders?.bottom?.size ?? 1) < 1) {
						borderStates.top = false;
						if (select.outer) allOuterBordersSet = false;
					} else if (!borderStates.top) borderStates.top = true;
				}
			}
			if (rr === maxRow) {
				if ((cell.borders?.bottom?.size ?? 1) < 1) {
					borderStates.bottom = false;
					if (select.outer) allOuterBordersSet = false;
				} else if (!borderStates.bottom) borderStates.bottom = true;
			}
			if (cc === minCol) if (isFirstCell) {
				if ((cell.borders?.left?.size ?? 1) < 1) {
					borderStates.left = false;
					if (select.outer) allOuterBordersSet = false;
				} else if (!borderStates.left) borderStates.left = true;
			} else {
				const prevCellEntry = getLeftTableCell(editor, { at: cellPath });
				if (prevCellEntry) {
					const [prevCell] = prevCellEntry;
					if ((prevCell.borders?.right?.size ?? 1) < 1) {
						borderStates.left = false;
						if (select.outer) allOuterBordersSet = false;
					} else if (!borderStates.left) borderStates.left = true;
				}
			}
			if (cc === maxCol) {
				if ((cell.borders?.right?.size ?? 1) < 1) {
					borderStates.right = false;
					if (select.outer) allOuterBordersSet = false;
				} else if (!borderStates.right) borderStates.right = true;
			}
		}
	}
	return {
		...select.side ? borderStates : {
			bottom: true,
			left: true,
			right: true,
			top: true
		},
		none: select.none ? !hasAnyBorder : false,
		outer: select.outer ? allOuterBordersSet : true
	};
};
/**
* Tells if the entire selection is currently borderless (size=0 on all edges).
* If **any** edge is > 0, returns false.
*/
function isSelectedCellBordersNone(editor, cells) {
	return cells.every((cell) => {
		const { borders } = cell;
		const { col, row } = getCellIndices(editor, cell);
		const cellPath = editor.api.findPath(cell);
		if (!cellPath) return true;
		const isFirstRow = row === 0;
		const isFirstCell = col === 0;
		if (isFirstRow && (borders?.top?.size ?? 1) > 0) return false;
		if (isFirstCell && (borders?.left?.size ?? 1) > 0) return false;
		if ((borders?.bottom?.size ?? 1) > 0) return false;
		if ((borders?.right?.size ?? 1) > 0) return false;
		if (!isFirstRow) {
			const cellAboveEntry = getTopTableCell(editor, { at: cellPath });
			if (cellAboveEntry) {
				const [cellAbove] = cellAboveEntry;
				if ((cellAbove.borders?.bottom?.size ?? 1) > 0) return false;
			}
		}
		if (!isFirstCell) {
			const prevCellEntry = getLeftTableCell(editor, { at: cellPath });
			if (prevCellEntry) {
				const [prevCell] = prevCellEntry;
				if ((prevCell.borders?.right?.size ?? 1) > 0) return false;
			}
		}
		return true;
	});
}
/**
* Tells if the bounding rectangle for the entire selection is fully set for the
* **outer** edges, i.e. top/left/bottom/right edges have size=1. We ignore
* internal edges, only bounding rectangle edges.
*/
function isSelectedCellBordersOuter(editor, cells) {
	const { maxCol, maxRow, minCol, minRow } = getSelectedCellsBoundingBox(editor, cells);
	for (const cell of cells) {
		const { col, row } = getCellIndices(editor, cell);
		const cSpan = getColSpan(cell);
		const rSpan = getRowSpan(cell);
		for (let rr = row; rr < row + rSpan; rr++) for (let cc = col; cc < col + cSpan; cc++) {
			if (rr === minRow && (cell.borders?.top?.size ?? 1) < 1) return false;
			if (rr === maxRow && (cell.borders?.bottom?.size ?? 1) < 1) return false;
			if (cc === minCol && (cell.borders?.left?.size ?? 1) < 1) return false;
			if (cc === maxCol && (cell.borders?.right?.size ?? 1) < 1) return false;
		}
	}
	return true;
}
/**
* Tells if the bounding rectangle for the entire selection is fully set for
* that single side. Example: border='top' => if every cell that sits along the
* top boundary has top=1.
*/
function isSelectedCellBorder(editor, cells, side) {
	const { maxCol, maxRow, minCol, minRow } = getSelectedCellsBoundingBox(editor, cells);
	return cells.every((cell) => {
		const { col, row } = getCellIndices(editor, cell);
		const cSpan = getColSpan(cell);
		const rSpan = getRowSpan(cell);
		const cellPath = editor.api.findPath(cell);
		if (!cellPath) return true;
		for (let rr = row; rr < row + rSpan; rr++) for (let cc = col; cc < col + cSpan; cc++) {
			if (side === "top" && rr === minRow) {
				if (row === 0) return (cell.borders?.top?.size ?? 1) >= 1;
				const cellAboveEntry = getTopTableCell(editor, { at: cellPath });
				if (!cellAboveEntry) return true;
				const [cellAboveNode] = cellAboveEntry;
				return (cellAboveNode.borders?.bottom?.size ?? 1) >= 1;
			}
			if (side === "bottom" && rr === maxRow) return (cell.borders?.bottom?.size ?? 1) >= 1;
			if (side === "left" && cc === minCol) {
				if (col === 0) return (cell.borders?.left?.size ?? 1) >= 1;
				const prevCellEntry = getLeftTableCell(editor, { at: cellPath });
				if (!prevCellEntry) return true;
				const [prevCellNode] = prevCellEntry;
				return (prevCellNode.borders?.right?.size ?? 1) >= 1;
			}
			if (side === "right" && cc === maxCol) return (cell.borders?.right?.size ?? 1) >= 1;
		}
		return true;
	});
}

//#endregion
//#region src/lib/queries/getTableAbove.ts
const getTableAbove = (editor, options) => editor.api.block({
	above: true,
	match: { type: editor.getType(KEYS.table) },
	...options
});

//#endregion
//#region src/lib/queries/getTableCellBorders.ts
const getTableCellBorders = (editor, { cellIndices, defaultBorder = { size: 1 }, element }) => {
	const cellPath = editor.api.findPath(element);
	const [rowNode, rowPath] = editor.api.parent(cellPath) ?? [];
	if (!rowNode || !rowPath) return {
		bottom: defaultBorder,
		right: defaultBorder
	};
	const [tableNode] = editor.api.parent(rowPath) ?? [];
	const tableType = editor.getType(KEYS.table);
	if (!tableNode || tableNode.type !== tableType) return {
		bottom: defaultBorder,
		right: defaultBorder
	};
	const { col } = cellIndices ?? getCellIndices(editor, element);
	const isFirstCell = col === 0;
	const isFirstRow = tableNode.children?.[0] === rowNode;
	const getBorder = (dir) => {
		const border = element.borders?.[dir];
		return {
			color: border?.color ?? defaultBorder.color,
			size: border?.size ?? defaultBorder.size,
			style: border?.style ?? defaultBorder.style
		};
	};
	return {
		bottom: getBorder("bottom"),
		left: isFirstCell ? getBorder("left") : void 0,
		right: getBorder("right"),
		top: isFirstRow ? getBorder("top") : void 0
	};
};

//#endregion
//#region src/lib/queries/getTableCellSize.ts
/** Get the width of a cell with colSpan support. */
const getTableCellSize = (editor, { cellIndices, colSizes, element, rowSize }) => {
	const { api } = getEditorPlugin(editor, { key: KEYS.table });
	const path = editor.api.findPath(element);
	if (!rowSize) {
		const [rowElement] = editor.api.parent(path) ?? [];
		if (!rowElement || rowElement.type !== editor.getType(KEYS.tr)) return {
			minHeight: 0,
			width: 0
		};
		rowSize = rowElement.size ?? 0;
	}
	if (!colSizes) {
		const [, rowPath] = editor.api.parent(path) ?? [];
		if (!rowPath) return {
			minHeight: rowSize,
			width: 0
		};
		const [tableNode] = editor.api.parent(rowPath) ?? [];
		if (!tableNode) return {
			minHeight: rowSize,
			width: 0
		};
		colSizes = getTableOverriddenColSizes(tableNode);
	}
	const colSpan = api.table.getColSpan(element);
	const { col } = cellIndices ?? getCellIndices(editor, element);
	const width = (colSizes ?? []).slice(col, col + colSpan).reduce((total, w) => total + (w || 0), 0);
	return {
		minHeight: rowSize,
		width
	};
};

//#endregion
//#region src/lib/queries/getTableColumnCount.ts
const getTableColumnCount = (tableNode) => {
	if (tableNode.children?.[0]?.children) return tableNode.children[0].children.map((element) => element.colSpan || (element?.attributes)?.colspan || 1).reduce((total, num) => Number(total) + Number(num));
	return 0;
};

//#endregion
//#region src/lib/queries/getTableOverriddenColSizes.ts
/**
* Returns node.colSizes if it exists, applying overrides, otherwise returns a
* 0-filled array.
*/
const getTableOverriddenColSizes = (tableNode, colSizeOverrides) => {
	const colCount = getTableColumnCount(tableNode);
	return (tableNode.colSizes ? [...tableNode.colSizes] : Array.from({ length: colCount }).fill(0)).map((size, index) => colSizeOverrides?.get?.(index) ?? size);
};

//#endregion
//#region src/lib/merge/deleteColumnWhenExpanded.ts
const deleteColumnWhenExpanded = (editor, tableEntry) => {
	const [start, end] = RangeApi.edges(editor.selection);
	const firstRow = NodeApi.child(tableEntry[0], 0);
	const lastRow = NodeApi.child(tableEntry[0], tableEntry[0].children.length - 1);
	const firstSelectionRow = editor.api.above({
		at: start,
		match: (n) => n.type === KEYS.tr
	});
	const lastSelectionRow = editor.api.above({
		at: end,
		match: (n) => n.type === KEYS.tr
	});
	if (!firstSelectionRow || !lastSelectionRow) return;
	if (firstRow.id === firstSelectionRow[0].id && lastSelectionRow[0].id === lastRow.id) deleteSelection(editor);
};
const deleteSelection = (editor) => {
	const cells = getTableGridAbove(editor, { format: "cell" });
	const pathRefs = [];
	cells.forEach(([_cell, cellPath]) => {
		pathRefs.push(editor.api.pathRef(cellPath));
	});
	pathRefs.forEach((pathRef) => {
		editor.tf.removeNodes({ at: pathRef.unref() });
	});
};

//#endregion
//#region src/lib/merge/getCellPath.ts
const getCellPath = (editor, tableEntry, curRowIndex, curColIndex) => {
	const [tableNode, tablePath] = tableEntry;
	const foundColIndex = tableNode.children[curRowIndex].children.findIndex((c) => {
		const { col: colIndex } = getCellIndices(editor, c);
		return colIndex === curColIndex;
	});
	return tablePath.concat([curRowIndex, foundColIndex]);
};

//#endregion
//#region src/lib/merge/getTableMergedColumnCount.ts
const getTableMergedColumnCount = (tableNode) => tableNode.children?.[0]?.children?.reduce((prev, cur) => prev + (getColSpan(cur) ?? 1), 0);

//#endregion
//#region src/lib/merge/deleteColumn.ts
const deleteTableMergeColumn = (editor) => {
	const type = editor.getType(KEYS.table);
	const tableEntry = editor.api.above({ match: { type } });
	if (!tableEntry) return;
	editor.tf.withoutNormalizing(() => {
		const { api } = getEditorPlugin(editor, BaseTablePlugin);
		if (editor.api.isExpanded()) return deleteColumnWhenExpanded(editor, tableEntry);
		const table = tableEntry[0];
		const selectedCellEntry = editor.api.above({ match: { type: getCellTypes(editor) } });
		if (!selectedCellEntry) return;
		const selectedCell = selectedCellEntry[0];
		const { col: deletingColIndex } = getCellIndices(editor, selectedCell);
		const colsDeleteNumber = api.table.getColSpan(selectedCell);
		if (getTableMergedColumnCount(table) <= colsDeleteNumber) {
			editor.tf.removeNodes({ at: tableEntry[1] });
			return;
		}
		const endingColIndex = deletingColIndex + colsDeleteNumber - 1;
		const rowNumber = table.children.length;
		const affectedCellsSet = /* @__PURE__ */ new Set();
		for (const rI of Array.from({ length: rowNumber }, (_, i) => i)) for (const cI of Array.from({ length: colsDeleteNumber }, (_, i) => i)) {
			const found = findCellByIndexes(editor, table, rI, deletingColIndex + cI);
			if (found) affectedCellsSet.add(found);
		}
		const affectedCells = Array.from(affectedCellsSet);
		const { squizeColSpanCells } = affectedCells.reduce((acc, cur) => {
			if (!cur) return acc;
			const currentCell = cur;
			const { col: curColIndex } = getCellIndices(editor, currentCell);
			const curColSpan = api.table.getColSpan(currentCell);
			if (curColIndex < deletingColIndex && curColSpan > 1) acc.squizeColSpanCells.push(currentCell);
			else if (curColSpan > 1 && curColIndex + curColSpan - 1 > endingColIndex) acc.squizeColSpanCells.push(currentCell);
			return acc;
		}, { squizeColSpanCells: [] });
		/** Change colSpans */
		squizeColSpanCells.forEach((cur) => {
			const curCell = cur;
			const { col: curColIndex, row: curColRowIndex } = getCellIndices(editor, curCell);
			const curColSpan = api.table.getColSpan(curCell);
			const curCellPath = getCellPath(editor, tableEntry, curColRowIndex, curColIndex);
			const colSpan = curColSpan - (Math.min(curColIndex + curColSpan - 1, endingColIndex) - deletingColIndex + 1);
			const newCell = cloneDeep({
				...curCell,
				colSpan
			});
			if (newCell.attributes?.colspan) newCell.attributes.colspan = colSpan.toString();
			editor.tf.setNodes(newCell, { at: curCellPath });
		});
		const trEntry = editor.api.above({ match: { type: editor.getType(KEYS.tr) } });
		/** Remove cells */
		if (selectedCell && trEntry && tableEntry && trEntry[0].children.length > 1) {
			const [tableNode, tablePath] = tableEntry;
			const paths = [];
			affectedCells.forEach((cur) => {
				const curCell = cur;
				const { col: curColIndex, row: curRowIndex } = getCellIndices(editor, curCell);
				if (!squizeColSpanCells.includes(curCell) && curColIndex >= deletingColIndex && curColIndex <= endingColIndex) {
					const cellPath = getCellPath(editor, tableEntry, curRowIndex, curColIndex);
					if (!paths[curRowIndex]) paths[curRowIndex] = [];
					paths[curRowIndex].push(cellPath);
				}
			});
			paths.forEach((cellPaths) => {
				const pathToDelete = cellPaths[0];
				cellPaths.forEach(() => {
					editor.tf.removeNodes({ at: pathToDelete });
				});
			});
			const { colSizes } = tableNode;
			if (colSizes) {
				const newColSizes = [...colSizes];
				newColSizes.splice(deletingColIndex, 1);
				editor.tf.setNodes({ colSizes: newColSizes }, { at: tablePath });
			}
		}
	});
};

//#endregion
//#region src/lib/merge/deleteRowWhenExpanded.ts
const deleteRowWhenExpanded = (editor, [table, tablePath]) => {
	const { api } = getEditorPlugin(editor, BaseTablePlugin);
	const columnCount = getTableMergedColumnCount(table);
	const cells = getTableGridAbove(editor, { format: "cell" });
	const firsRowIndex = getCellRowIndexByPath(cells[0][1]);
	if (firsRowIndex === null) return;
	let acrossColumn = 0;
	let lastRowIndex = -1;
	let rowSpanCarry = 0;
	let acrossRow = 0;
	cells.forEach(([cell, cellPath]) => {
		if (cellPath.at(-2) === firsRowIndex) acrossColumn += cell.colSpan ?? 1;
		const currentRowIndex = getCellRowIndexByPath(cellPath);
		if (lastRowIndex !== currentRowIndex) {
			if (rowSpanCarry !== 0) {
				rowSpanCarry--;
				return;
			}
			const rowSpan = api.table.getRowSpan(cell);
			rowSpanCarry = rowSpan && rowSpan > 1 ? rowSpan - 1 : 0;
			acrossRow += rowSpan ?? 1;
		}
		lastRowIndex = currentRowIndex;
	});
	if (acrossColumn === columnCount) {
		const pathRefs = [];
		for (let i = firsRowIndex; i < firsRowIndex + acrossRow; i++) {
			const removedPath = tablePath.concat(i);
			pathRefs.push(editor.api.pathRef(removedPath));
		}
		pathRefs.forEach((item) => {
			editor.tf.removeNodes({ at: item.unref() });
		});
	}
};

//#endregion
//#region src/lib/merge/deleteRow.ts
const deleteTableMergeRow = (editor) => {
	const { api, tf, type } = getEditorPlugin(editor, { key: KEYS.table });
	if (editor.api.some({ match: { type } })) {
		const currentTableItem = editor.api.above({ match: { type } });
		if (!currentTableItem) return;
		if (editor.api.isExpanded()) return deleteRowWhenExpanded(editor, currentTableItem);
		const table = currentTableItem[0];
		const selectedCellEntry = editor.api.above({ match: { type: getCellTypes(editor) } });
		if (!selectedCellEntry) return;
		const selectedCell = selectedCellEntry[0];
		const { row: deletingRowIndex } = getCellIndices(editor, selectedCell);
		const rowsDeleteNumber = api.table.getRowSpan(selectedCell);
		const endingRowIndex = deletingRowIndex + rowsDeleteNumber - 1;
		const colNumber = getTableColumnCount(table);
		const affectedCellsSet = /* @__PURE__ */ new Set();
		for (const cI of Array.from({ length: colNumber }, (_, i) => i)) for (const rI of Array.from({ length: rowsDeleteNumber }, (_, i) => i)) {
			const found = findCellByIndexes(editor, table, deletingRowIndex + rI, cI);
			affectedCellsSet.add(found);
		}
		const { moveToNextRowCells, squizeRowSpanCells } = Array.from(affectedCellsSet).reduce((acc, cur) => {
			if (!cur) return acc;
			const currentCell = cur;
			const { row: curRowIndex } = getCellIndices(editor, currentCell);
			const curRowSpan = api.table.getRowSpan(currentCell);
			if (curRowIndex < deletingRowIndex && curRowSpan > 1) acc.squizeRowSpanCells.push(currentCell);
			else if (curRowSpan > 1 && curRowIndex + curRowSpan - 1 > endingRowIndex) acc.moveToNextRowCells.push(currentCell);
			return acc;
		}, {
			moveToNextRowCells: [],
			squizeRowSpanCells: []
		});
		const nextRowIndex = deletingRowIndex + rowsDeleteNumber;
		const nextRow = table.children[nextRowIndex];
		if (nextRow === void 0 && deletingRowIndex === 0) {
			tf.remove.table();
			return;
		}
		if (nextRow) for (let index = 0; index < moveToNextRowCells.length; index++) {
			const curRowCell = moveToNextRowCells[index];
			const { col: curRowCellColIndex, row: curRowCellRowIndex } = getCellIndices(editor, curRowCell);
			const curRowCellRowSpan = api.table.getRowSpan(curRowCell);
			const startingCellIndex = nextRow.children.findIndex((curC) => {
				const { col: curColIndex } = getCellIndices(editor, curC);
				return curColIndex >= curRowCellColIndex;
			});
			if (startingCellIndex === -1) {
				const startingCell$1 = nextRow.children.at(-1);
				const startingCellPath$1 = editor.api.findPath(startingCell$1);
				const tablePath$1 = startingCellPath$1.slice(0, -2);
				const colPath$1 = startingCellPath$1.at(-1) + index + 1;
				const nextRowStartCellPath$1 = [
					...tablePath$1,
					nextRowIndex,
					colPath$1
				];
				const rowSpan$1 = curRowCellRowSpan - (endingRowIndex - curRowCellRowIndex + 1);
				const newCell$1 = cloneDeep({
					...curRowCell,
					rowSpan: rowSpan$1
				});
				if (newCell$1.attributes?.rowspan) newCell$1.attributes.rowspan = rowSpan$1.toString();
				editor.tf.insertNodes(newCell$1, { at: nextRowStartCellPath$1 });
				continue;
			}
			const startingCell = nextRow.children[startingCellIndex];
			const { col: startingColIndex } = getCellIndices(editor, startingCell);
			let incrementBy = index;
			if (startingColIndex < curRowCellColIndex) incrementBy += 1;
			const startingCellPath = editor.api.findPath(startingCell);
			const tablePath = startingCellPath.slice(0, -2);
			const colPath = startingCellPath.at(-1);
			const nextRowStartCellPath = [
				...tablePath,
				nextRowIndex,
				colPath + incrementBy
			];
			const rowSpan = curRowCellRowSpan - (endingRowIndex - curRowCellRowIndex + 1);
			const newCell = cloneDeep({
				...curRowCell,
				rowSpan
			});
			if (newCell.attributes?.rowspan) newCell.attributes.rowspan = rowSpan.toString();
			editor.tf.insertNodes(newCell, { at: nextRowStartCellPath });
		}
		squizeRowSpanCells.forEach((cur) => {
			const curRowCell = cur;
			const { row: curRowCellRowIndex } = getCellIndices(editor, curRowCell);
			const curRowCellRowSpan = api.table.getRowSpan(curRowCell);
			const curCellPath = editor.api.findPath(curRowCell);
			const rowSpan = curRowCellRowSpan - (Math.min(curRowCellRowIndex + curRowCellRowSpan - 1, endingRowIndex) - deletingRowIndex + 1);
			const newCell = cloneDeep({
				...curRowCell,
				rowSpan
			});
			if (newCell.attributes?.rowspan) newCell.attributes.rowspan = rowSpan.toString();
			editor.tf.setNodes(newCell, { at: curCellPath });
		});
		const rowToDelete = table.children[deletingRowIndex];
		const rowPath = editor.api.findPath(rowToDelete);
		Array.from({ length: rowsDeleteNumber }).forEach(() => {
			editor.tf.removeNodes({ at: rowPath });
		});
	}
};

//#endregion
//#region src/lib/merge/insertTableColumn.ts
const insertTableMergeColumn = (editor, { at, before, fromCell, header, select: shouldSelect } = {}) => {
	const { api, getOptions, type } = getEditorPlugin(editor, BaseTablePlugin);
	const { initialTableWidth, minColumnWidth } = getOptions();
	if (at && !fromCell) {
		if (NodeApi.get(editor, at)?.type === editor.getType(KEYS.table)) {
			fromCell = NodeApi.lastChild(editor, at.concat([0]))[1];
			at = void 0;
		}
	}
	const cellEntry = fromCell ? editor.api.node({
		at: fromCell,
		match: { type: getCellTypes(editor) }
	}) : editor.api.block({ match: { type: getCellTypes(editor) } });
	if (!cellEntry) return;
	const [, cellPath] = cellEntry;
	const cell = cellEntry[0];
	const tableEntry = editor.api.block({
		above: true,
		at: cellPath,
		match: { type }
	});
	if (!tableEntry) return;
	const [tableNode, tablePath] = tableEntry;
	const { col: cellColIndex } = getCellIndices(editor, cell);
	const cellColSpan = api.table.getColSpan(cell);
	let nextColIndex;
	let checkingColIndex;
	if (PathApi.isPath(at)) {
		nextColIndex = cellColIndex;
		checkingColIndex = cellColIndex - 1;
	} else {
		nextColIndex = before ? cellColIndex : cellColIndex + cellColSpan;
		checkingColIndex = before ? cellColIndex : cellColIndex + cellColSpan - 1;
	}
	const rowNumber = tableNode.children.length;
	const firstCol = nextColIndex <= 0;
	let placementCorrection = before ? 0 : 1;
	if (firstCol) {
		checkingColIndex = 0;
		placementCorrection = 0;
	}
	const affectedCellsSet = /* @__PURE__ */ new Set();
	Array.from({ length: rowNumber }, (_, i) => i).forEach((rI) => {
		const found = findCellByIndexes(editor, tableNode, rI, checkingColIndex);
		if (found) affectedCellsSet.add(found);
	});
	Array.from(affectedCellsSet).forEach((curCell) => {
		const { col: curColIndex, row: curRowIndex } = getCellIndices(editor, curCell);
		const curRowSpan = api.table.getRowSpan(curCell);
		const curColSpan = api.table.getColSpan(curCell);
		const currentCellPath = getCellPath(editor, tableEntry, curRowIndex, curColIndex);
		if (curColIndex + curColSpan - 1 >= nextColIndex && !firstCol && !before) {
			const colSpan = curColSpan + 1;
			const newCell = cloneDeep({
				...curCell,
				colSpan
			});
			if (newCell.attributes?.colspan) newCell.attributes.colspan = colSpan.toString();
			editor.tf.setNodes(newCell, { at: currentCellPath });
		} else {
			const curRowPath = currentCellPath.slice(0, -1);
			const curColPath = currentCellPath.at(-1);
			const placementPath = [...curRowPath, before ? curColPath : curColPath + placementCorrection];
			const rowElement = editor.api.parent(currentCellPath)[0];
			const emptyCell = {
				...api.create.tableCell({
					header,
					row: rowElement
				}),
				colSpan: 1,
				rowSpan: curRowSpan
			};
			editor.tf.insertNodes(emptyCell, {
				at: placementPath,
				select: shouldSelect
			});
		}
	});
	editor.tf.withoutNormalizing(() => {
		const { colSizes } = tableNode;
		if (colSizes) {
			let newColSizes = [
				...colSizes.slice(0, nextColIndex),
				0,
				...colSizes.slice(nextColIndex)
			];
			if (initialTableWidth) {
				newColSizes[nextColIndex] = colSizes[nextColIndex] ?? colSizes[nextColIndex - 1] ?? initialTableWidth / colSizes.length;
				const oldTotal = colSizes.reduce((a, b) => a + b, 0);
				const newTotal = newColSizes.reduce((a, b) => a + b, 0);
				const maxTotal = Math.max(oldTotal, initialTableWidth);
				if (newTotal > maxTotal) {
					const factor = maxTotal / newTotal;
					newColSizes = newColSizes.map((size) => Math.max(minColumnWidth ?? 0, Math.floor(size * factor)));
				}
			}
			editor.tf.setNodes({ colSizes: newColSizes }, { at: tablePath });
		}
	});
};

//#endregion
//#region src/lib/merge/insertTableRow.ts
const insertTableMergeRow = (editor, { at, before, fromRow, header, select: shouldSelect } = {}) => {
	const { api, type } = getEditorPlugin(editor, BaseTablePlugin);
	if (at && !fromRow) {
		if (NodeApi.get(editor, at)?.type === editor.getType(KEYS.table)) {
			fromRow = NodeApi.lastChild(editor, at)[1];
			at = void 0;
		}
	}
	const trEntry = editor.api.block({
		at: fromRow,
		match: { type: editor.getType(KEYS.tr) }
	});
	if (!trEntry) return;
	const [, trPath] = trEntry;
	const tableEntry = editor.api.block({
		above: true,
		at: trPath,
		match: { type }
	});
	if (!tableEntry) return;
	const tableNode = tableEntry[0];
	const cellEntry = editor.api.node({
		at: fromRow,
		match: { type: getCellTypes(editor) }
	});
	if (!cellEntry) return;
	const [cellNode, cellPath] = cellEntry;
	const cellElement = cellNode;
	const cellRowSpan = api.table.getRowSpan(cellElement);
	const { row: cellRowIndex } = getCellIndices(editor, cellElement);
	const rowPath = cellPath.at(-2);
	const tablePath = cellPath.slice(0, -2);
	let nextRowIndex;
	let checkingRowIndex;
	let nextRowPath;
	if (PathApi.isPath(at)) {
		nextRowIndex = at.at(-1);
		checkingRowIndex = cellRowIndex - 1;
		nextRowPath = at;
	} else {
		nextRowIndex = before ? cellRowIndex : cellRowIndex + cellRowSpan;
		checkingRowIndex = before ? cellRowIndex - 1 : cellRowIndex + cellRowSpan - 1;
		nextRowPath = [...tablePath, before ? rowPath : rowPath + cellRowSpan];
	}
	const firstRow = nextRowIndex === 0;
	if (firstRow) checkingRowIndex = 0;
	const colCount = getTableColumnCount(tableNode);
	const affectedCellsSet = /* @__PURE__ */ new Set();
	Array.from({ length: colCount }, (_, i) => i).forEach((cI) => {
		const found = findCellByIndexes(editor, tableNode, checkingRowIndex, cI);
		if (found) affectedCellsSet.add(found);
	});
	const affectedCells = Array.from(affectedCellsSet);
	const newRowChildren = [];
	affectedCells.forEach((cur) => {
		if (!cur) return;
		const curCell = cur;
		const { col: curColIndex, row: curRowIndex } = getCellIndices(editor, curCell);
		const curRowSpan = api.table.getRowSpan(curCell);
		const curColSpan = api.table.getColSpan(curCell);
		const currentCellPath = getCellPath(editor, tableEntry, curRowIndex, curColIndex);
		if (curRowIndex + curRowSpan - 1 >= nextRowIndex && !firstRow) {
			const rowSpan = curRowSpan + 1;
			const newCell = cloneDeep({
				...curCell,
				rowSpan
			});
			if (newCell.attributes?.rowspan) newCell.attributes.rowspan = rowSpan.toString();
			editor.tf.setNodes(newCell, { at: currentCellPath });
		} else {
			const rowElement = editor.api.parent(currentCellPath)[0];
			const emptyCell = api.create.tableCell({
				header,
				row: rowElement
			});
			newRowChildren.push({
				...emptyCell,
				colSpan: curColSpan,
				rowSpan: 1
			});
		}
	});
	editor.tf.withoutNormalizing(() => {
		editor.tf.insertNodes({
			children: newRowChildren,
			type: editor.getType(KEYS.tr)
		}, {
			at: nextRowPath,
			select: false
		});
		if (shouldSelect) {
			const cellEntry$1 = editor.api.node({
				at: nextRowPath,
				match: { type: getCellTypes(editor) }
			});
			if (cellEntry$1) {
				const [, nextCellPath] = cellEntry$1;
				editor.tf.select(nextCellPath);
			}
		}
	});
};

//#endregion
//#region src/lib/merge/mergeTableCells.ts
/** Merges multiple selected cells into one. */
const mergeTableCells = (editor) => {
	const { api } = getEditorPlugin(editor, BaseTablePlugin);
	const cellEntries = getTableGridAbove(editor, { format: "cell" });
	editor.tf.withoutNormalizing(() => {
		let colSpan = 0;
		for (const entry of cellEntries) {
			const [cell, path] = entry;
			if (path.at(-2) === cellEntries[0][1].at(-2)) {
				const cellColSpan = api.table.getColSpan(cell);
				colSpan += cellColSpan;
			}
		}
		let rowSpan = 0;
		const { col } = getCellIndices(editor, cellEntries[0][0]);
		cellEntries.forEach((entry) => {
			const cell = entry[0];
			const { col: curCol } = getCellIndices(editor, cell);
			if (col === curCol) rowSpan += api.table.getRowSpan(cell);
		});
		const mergingCellChildren = [];
		for (const cellEntry of cellEntries) {
			const [el] = cellEntry;
			const cellChildren = api.table.getCellChildren(el);
			if (cellChildren.length !== 1 || !editor.api.isEmpty(cellChildren[0])) mergingCellChildren.push(...cloneDeep(cellChildren));
		}
		const cols = {};
		cellEntries.forEach(([_entry, path]) => {
			const rowIndex = path.at(-2);
			if (cols[rowIndex]) cols[rowIndex].push(path);
			else cols[rowIndex] = [path];
		});
		Object.values(cols).forEach((paths) => {
			paths?.forEach(() => {
				editor.tf.removeNodes({ at: paths[0] });
			});
		});
		const mergedCell = {
			...api.create.tableCell({
				children: mergingCellChildren,
				header: cellEntries[0][0].type === editor.getType(KEYS.th)
			}),
			colSpan,
			rowSpan
		};
		editor.tf.insertNodes(mergedCell, { at: cellEntries[0][1] });
	});
	editor.tf.select(editor.api.end(cellEntries[0][1]));
};

//#endregion
//#region src/lib/merge/splitTableCell.ts
const splitTableCell = (editor) => {
	const { api } = getEditorPlugin(editor, BaseTablePlugin);
	const tableRowType = editor.getType(KEYS.tr);
	const [[cellElem, path]] = getTableGridAbove(editor, { format: "cell" });
	editor.tf.withoutNormalizing(() => {
		const createEmptyCell = (children) => ({
			...api.create.tableCell({
				children,
				header: cellElem.type === editor.getType(KEYS.th)
			}),
			colSpan: 1,
			rowSpan: 1
		});
		const tablePath = path.slice(0, -2);
		const [rowPath, colPath] = path.slice(-2);
		const colSpan = api.table.getColSpan(cellElem);
		const rowSpan = api.table.getRowSpan(cellElem);
		const colPaths = [];
		for (let i = 0; i < colSpan; i++) colPaths.push(colPath + i);
		const { col } = getCellIndices(editor, cellElem);
		editor.tf.removeNodes({ at: path });
		const getClosestColPathForRow = (row, targetCol) => {
			const rowEntry = editor.api.node({
				at: [...tablePath, row],
				match: { type: tableRowType }
			});
			if (!rowEntry) return 0;
			const rowEl = rowEntry[0];
			let closestColPath = [];
			let smallestDiff = Number.POSITIVE_INFINITY;
			let isDirectionLeft = false;
			rowEl.children.forEach((cell) => {
				const cellElement = cell;
				const { col: cellCol } = getCellIndices(editor, cellElement);
				const diff = Math.abs(cellCol - targetCol);
				if (diff < smallestDiff) {
					smallestDiff = diff;
					closestColPath = editor.api.findPath(cellElement);
					isDirectionLeft = cellCol < targetCol;
				}
			});
			if (closestColPath.length > 0) {
				const lastIndex = closestColPath.at(-1);
				if (isDirectionLeft) return lastIndex + 1;
				return lastIndex;
			}
			return 1;
		};
		for (let i = 0; i < rowSpan; i++) {
			const currentRowPath = rowPath + i;
			const pathForNextRows = getClosestColPathForRow(currentRowPath, col);
			const newRowChildren = [];
			const _rowPath = [...tablePath, currentRowPath];
			const rowEntry = editor.api.node({
				at: _rowPath,
				match: { type: tableRowType }
			});
			for (let j = 0; j < colPaths.length; j++) {
				const cellChildren = api.table.getCellChildren(cellElem);
				const cellToInsert = i === 0 && j === 0 ? createEmptyCell(cellChildren) : createEmptyCell();
				if (rowEntry) {
					const currentColPath = i === 0 ? colPaths[j] : pathForNextRows;
					const pathForNewCell = [
						...tablePath,
						currentRowPath,
						currentColPath
					];
					editor.tf.insertNodes(cellToInsert, { at: pathForNewCell });
				} else newRowChildren.push(cellToInsert);
			}
			if (!rowEntry) editor.tf.insertNodes({
				children: newRowChildren,
				type: editor.getType(KEYS.tr)
			}, { at: _rowPath });
		}
	});
	editor.tf.select(editor.api.end(path));
};

//#endregion
//#region src/lib/normalizeInitialValueTable.ts
const normalizeInitialValueTable = ({ editor, type, value }) => {
	const tables = editor.api.nodes({
		at: [],
		match: { type }
	});
	for (const [table] of tables) computeCellIndices(editor, { tableNode: table });
	return value;
};

//#endregion
//#region src/lib/transforms/deleteColumn.ts
const deleteColumn = (editor) => {
	const { getOptions, type } = getEditorPlugin(editor, { key: KEYS.table });
	const { disableMerge } = getOptions();
	const tableEntry = editor.api.above({ match: { type } });
	if (!tableEntry) return;
	editor.tf.withoutNormalizing(() => {
		if (!disableMerge) {
			deleteTableMergeColumn(editor);
			return;
		}
		if (editor.api.isExpanded()) return deleteColumnWhenExpanded(editor, tableEntry);
		const tdEntry = editor.api.above({ match: { type: getCellTypes(editor) } });
		const trEntry = editor.api.above({ match: { type: editor.getType(KEYS.tr) } });
		if (tdEntry && trEntry && getTableColumnCount(tableEntry[0]) <= 1) {
			editor.tf.removeNodes({ at: tableEntry[1] });
			return;
		}
		if (tdEntry && trEntry && tableEntry && trEntry[0].children.length > 1) {
			const [tableNode, tablePath] = tableEntry;
			const tdPath = tdEntry[1];
			const colIndex = tdPath.at(-1);
			const pathToDelete = tdPath.slice();
			const replacePathPos = pathToDelete.length - 2;
			tableNode.children.forEach((row, rowIdx) => {
				pathToDelete[replacePathPos] = rowIdx;
				if (row.children.length === 1 || colIndex > row.children.length - 1) return;
				editor.tf.removeNodes({ at: pathToDelete });
			});
			const { colSizes } = tableNode;
			if (colSizes) {
				const newColSizes = [...colSizes];
				newColSizes.splice(colIndex, 1);
				editor.tf.setNodes({ colSizes: newColSizes }, { at: tablePath });
			}
		}
	});
};

//#endregion
//#region src/lib/transforms/deleteRow.ts
const deleteRow = (editor) => {
	const { getOptions, type } = getEditorPlugin(editor, { key: KEYS.table });
	const { disableMerge } = getOptions();
	if (!disableMerge) return deleteTableMergeRow(editor);
	if (editor.api.some({ match: { type } })) {
		const currentTableItem = editor.api.above({ match: { type } });
		if (!currentTableItem) return;
		if (editor.api.isExpanded()) return deleteRowWhenExpanded(editor, currentTableItem);
		const currentRowItem = editor.api.above({ match: { type: editor.getType(KEYS.tr) } });
		if (currentRowItem && currentTableItem && currentTableItem[0].children.length > 1) editor.tf.removeNodes({ at: currentRowItem[1] });
	}
};

//#endregion
//#region src/lib/transforms/deleteTable.ts
const deleteTable = (editor) => {
	if (editor.api.some({ match: { type: editor.getType(KEYS.table) } })) {
		const tableItem = editor.api.above({ match: { type: editor.getType(KEYS.table) } });
		if (tableItem) editor.tf.removeNodes({ at: tableItem[1] });
	}
};

//#endregion
//#region src/lib/transforms/insertTable.ts
/**
* Insert table. If selection in table and no 'at' specified, insert after
* current table. Select start of new table.
*/
const insertTable = (editor, { colCount = 2, header, rowCount = 2 } = {}, { select: shouldSelect, ...options } = {}) => {
	const { api } = editor.getPlugin({ key: KEYS.table });
	const type = editor.getType(KEYS.table);
	editor.tf.withoutNormalizing(() => {
		const newTable = api.create.table({
			colCount,
			header,
			rowCount
		});
		if (!options.at) {
			const currentTableEntry = editor.api.block({ match: { type } });
			if (currentTableEntry) {
				const [, tablePath] = currentTableEntry;
				const insertPath = PathApi.next(tablePath);
				editor.tf.insertNodes(newTable, {
					at: insertPath,
					...options
				});
				if (editor.selection) editor.tf.select(editor.api.start(insertPath));
				return;
			}
		}
		editor.tf.insertNodes(newTable, {
			nextBlock: !options.at,
			select: shouldSelect,
			...options
		});
		if (shouldSelect) {
			const tableEntry = editor.api.node({
				at: options.at,
				match: { type }
			});
			if (!tableEntry) return;
			editor.tf.select(editor.api.start(tableEntry[1]));
		}
	});
};

//#endregion
//#region src/lib/transforms/insertTableColumn.ts
const insertTableColumn = (editor, options = {}) => {
	const { api, getOptions, type } = getEditorPlugin(editor, BaseTablePlugin);
	const { disableMerge, initialTableWidth, minColumnWidth } = getOptions();
	if (!disableMerge) return insertTableMergeColumn(editor, options);
	const { before, header, select: shouldSelect } = options;
	let { at, fromCell } = options;
	if (at && !fromCell) {
		if (NodeApi.get(editor, at)?.type === editor.getType(KEYS.table)) {
			fromCell = NodeApi.lastChild(editor, at.concat([0]))[1];
			at = void 0;
		}
	}
	const cellEntry = editor.api.block({
		at: fromCell,
		match: { type: getCellTypes(editor) }
	});
	if (!cellEntry) return;
	const [, cellPath] = cellEntry;
	const tableEntry = editor.api.block({
		above: true,
		at: cellPath,
		match: { type }
	});
	if (!tableEntry) return;
	const [tableNode, tablePath] = tableEntry;
	let nextCellPath;
	let nextColIndex;
	if (PathApi.isPath(at)) {
		nextCellPath = at;
		nextColIndex = at.at(-1);
	} else {
		nextCellPath = before ? cellPath : PathApi.next(cellPath);
		nextColIndex = before ? cellPath.at(-1) : cellPath.at(-1) + 1;
	}
	const currentRowIndex = cellPath.at(-2);
	editor.tf.withoutNormalizing(() => {
		tableNode.children.forEach((row, rowIndex) => {
			const insertCellPath = [...nextCellPath];
			if (PathApi.isPath(at)) insertCellPath[at.length - 2] = rowIndex;
			else insertCellPath[cellPath.length - 2] = rowIndex;
			const isHeaderRow = header === void 0 ? row.children.every((c) => c.type === editor.getType(KEYS.th)) : header;
			editor.tf.insertNodes(api.create.tableCell({ header: isHeaderRow }), {
				at: insertCellPath,
				select: shouldSelect && rowIndex === currentRowIndex
			});
		});
		const { colSizes } = tableNode;
		if (colSizes) {
			let newColSizes = [
				...colSizes.slice(0, nextColIndex),
				0,
				...colSizes.slice(nextColIndex)
			];
			if (initialTableWidth) {
				newColSizes[nextColIndex] = colSizes[nextColIndex] ?? colSizes[nextColIndex - 1] ?? initialTableWidth / colSizes.length;
				const oldTotal = colSizes.reduce((a, b) => a + b, 0);
				const newTotal = newColSizes.reduce((a, b) => a + b, 0);
				const maxTotal = Math.max(oldTotal, initialTableWidth);
				if (newTotal > maxTotal) {
					const factor = maxTotal / newTotal;
					newColSizes = newColSizes.map((size) => Math.max(minColumnWidth ?? 0, Math.floor(size * factor)));
				}
			}
			editor.tf.setNodes({ colSizes: newColSizes }, { at: tablePath });
		}
	});
};

//#endregion
//#region src/lib/transforms/insertTableRow.ts
const insertTableRow = (editor, options = {}) => {
	const { api, getOptions, type } = getEditorPlugin(editor, BaseTablePlugin);
	const { disableMerge } = getOptions();
	if (!disableMerge) return insertTableMergeRow(editor, options);
	const { before, header, select: shouldSelect } = options;
	let { at, fromRow } = options;
	if (at && !fromRow) {
		if (NodeApi.get(editor, at)?.type === editor.getType(KEYS.table)) {
			fromRow = NodeApi.lastChild(editor, at)[1];
			at = void 0;
		}
	}
	const trEntry = editor.api.block({
		at: fromRow,
		match: { type: editor.getType(KEYS.tr) }
	});
	if (!trEntry) return;
	const [trNode, trPath] = trEntry;
	const tableEntry = editor.api.block({
		above: true,
		at: trPath,
		match: { type }
	});
	if (!tableEntry) return;
	const getEmptyRowNode$1 = () => ({
		children: trNode.children.map((_, i) => {
			const isHeaderColumn = !(tableEntry[0].children.length === 1) && tableEntry[0].children.every((n) => n.children[i].type === editor.getType(KEYS.th));
			return api.create.tableCell({ header: header ?? isHeaderColumn });
		}),
		type: editor.getType(KEYS.tr)
	});
	editor.tf.withoutNormalizing(() => {
		editor.tf.insertNodes(getEmptyRowNode$1(), { at: PathApi.isPath(at) ? at : before ? trPath : PathApi.next(trPath) });
	});
	if (shouldSelect) {
		const cellEntry = editor.api.block({ match: { type: getCellTypes(editor) } });
		if (!cellEntry) return;
		const [, nextCellPath] = cellEntry;
		if (PathApi.isPath(at)) nextCellPath[nextCellPath.length - 2] = at.at(-2);
		else nextCellPath[nextCellPath.length - 2] = before ? nextCellPath.at(-2) : nextCellPath.at(-2) + 1;
		editor.tf.select(nextCellPath);
	}
};

//#endregion
//#region src/lib/transforms/moveSelectionFromCell.ts
/** Move selection by cell unit. */
const moveSelectionFromCell = (editor, { at, edge, fromOneCell, reverse } = {}) => {
	if (edge) {
		const cellEntries = getTableGridAbove(editor, {
			at,
			format: "cell"
		});
		const minCell = fromOneCell ? 0 : 1;
		if (cellEntries.length > minCell) {
			const [, firstCellPath] = cellEntries[0];
			const [, lastCellPath] = cellEntries.at(-1);
			const anchorPath = [...firstCellPath];
			const focusPath = [...lastCellPath];
			switch (edge) {
				case "bottom":
					focusPath[focusPath.length - 2] += 1;
					break;
				case "left":
					anchorPath[anchorPath.length - 1] -= 1;
					break;
				case "right":
					focusPath[focusPath.length - 1] += 1;
					break;
				case "top":
					anchorPath[anchorPath.length - 2] -= 1;
					break;
			}
			if (NodeApi.has(editor, anchorPath) && NodeApi.has(editor, focusPath)) editor.tf.select({
				anchor: editor.api.start(anchorPath),
				focus: editor.api.start(focusPath)
			});
			return true;
		}
		return;
	}
	const cellEntry = editor.api.block({
		at,
		match: { type: getCellTypes(editor) }
	});
	if (cellEntry) {
		const [, cellPath] = cellEntry;
		const nextCellPath = [...cellPath];
		const offset = reverse ? -1 : 1;
		nextCellPath[nextCellPath.length - 2] += offset;
		if (NodeApi.has(editor, nextCellPath)) editor.tf.select(editor.api.start(nextCellPath));
		else {
			const tablePath = cellPath.slice(0, -2);
			if (reverse) editor.tf.withoutNormalizing(() => {
				editor.tf.select(editor.api.start(tablePath));
				editor.tf.move({ reverse: true });
			});
			else editor.tf.withoutNormalizing(() => {
				editor.tf.select(editor.api.end(tablePath));
				editor.tf.move();
			});
		}
		return true;
	}
};

//#endregion
//#region src/lib/transforms/setBorderSize.ts
const setBorderSize = (editor, size, { at, border = "all" } = {}) => {
	const cellEntry = editor.api.node({
		at,
		match: { type: getCellTypes(editor) }
	});
	if (!cellEntry) return;
	const [cellNode, cellPath] = cellEntry;
	const cellIndex = cellPath.at(-1);
	const rowIndex = cellPath.at(-2);
	const borderStyle = { size };
	const setNodesOptions = { match: (n) => ElementApi.isElement(n) && getCellTypes(editor).includes(n.type) };
	if (border === "top") {
		if (rowIndex === 0) {
			const newBorders$1 = {
				...cellNode.borders,
				top: borderStyle
			};
			editor.tf.setNodes({ borders: newBorders$1 }, {
				at: cellPath,
				...setNodesOptions
			});
			return;
		}
		const cellAboveEntry = getTopTableCell(editor, { at: cellPath });
		if (!cellAboveEntry) return;
		const [cellAboveNode, cellAbovePath] = cellAboveEntry;
		const newBorders = {
			...cellAboveNode.borders,
			bottom: borderStyle
		};
		editor.tf.setNodes({ borders: newBorders }, {
			at: cellAbovePath,
			...setNodesOptions
		});
	} else if (border === "bottom") {
		const newBorders = {
			...cellNode.borders,
			bottom: borderStyle
		};
		editor.tf.setNodes({ borders: newBorders }, {
			at: cellPath,
			...setNodesOptions
		});
	}
	if (border === "left") {
		if (cellIndex === 0) {
			const newBorders$1 = {
				...cellNode.borders,
				left: borderStyle
			};
			editor.tf.setNodes({ borders: newBorders$1 }, {
				at: cellPath,
				...setNodesOptions
			});
			return;
		}
		const prevCellEntry = getLeftTableCell(editor, { at: cellPath });
		if (!prevCellEntry) return;
		const [prevCellNode, prevCellPath] = prevCellEntry;
		const newBorders = {
			...prevCellNode.borders,
			right: borderStyle
		};
		editor.tf.setNodes({ borders: newBorders }, {
			at: prevCellPath,
			...setNodesOptions
		});
	} else if (border === "right") {
		const newBorders = {
			...cellNode.borders,
			right: borderStyle
		};
		editor.tf.setNodes({ borders: newBorders }, {
			at: cellPath,
			...setNodesOptions
		});
	}
	if (border === "all") editor.tf.withoutNormalizing(() => {
		setBorderSize(editor, size, {
			at,
			border: "top"
		});
		setBorderSize(editor, size, {
			at,
			border: "bottom"
		});
		setBorderSize(editor, size, {
			at,
			border: "left"
		});
		setBorderSize(editor, size, {
			at,
			border: "right"
		});
	});
};

//#endregion
//#region src/lib/transforms/setTableColSize.ts
const setTableColSize = (editor, { colIndex, width }, options = {}) => {
	const table = editor.api.node({
		match: { type: KEYS.table },
		...options
	});
	if (!table) return;
	const [tableNode, tablePath] = table;
	const colSizes = tableNode.colSizes ? [...tableNode.colSizes] : Array.from({ length: getTableColumnCount(tableNode) }).fill(0);
	colSizes[colIndex] = width;
	editor.tf.setNodes({ colSizes }, { at: tablePath });
};

//#endregion
//#region src/lib/transforms/setTableMarginLeft.ts
const setTableMarginLeft = (editor, { marginLeft }, options = {}) => {
	const table = editor.api.node({
		match: { type: KEYS.table },
		...options
	});
	if (!table) return;
	const [, tablePath] = table;
	editor.tf.setNodes({ marginLeft }, { at: tablePath });
};

//#endregion
//#region src/lib/transforms/setTableRowSize.ts
const setTableRowSize = (editor, { height, rowIndex }, options = {}) => {
	const table = editor.api.node({
		match: { type: KEYS.table },
		...options
	});
	if (!table) return;
	const [, tablePath] = table;
	const tableRowPath = [...tablePath, rowIndex];
	editor.tf.setNodes({ size: height }, { at: tableRowPath });
};

//#endregion
//#region src/lib/transforms/shouldMoveSelectionFromCell.ts
const VISUAL_LINE_TOLERANCE = 1;
const getRangeClientRects = (domRange) => Array.from(domRange?.getClientRects?.() ?? []).filter((rect) => rect.height > 0);
const getTableMoveSelectionContext = (editor, point = editor.selection?.anchor) => {
	if (!point || !editor.api.isAt({
		block: true,
		match: { type: getCellTypes(editor) }
	})) return;
	const cellEntry = editor.api.block({
		at: point,
		match: { type: getCellTypes(editor) }
	});
	const blockEntry = editor.api.block({ at: point });
	if (!cellEntry || !blockEntry) return;
	const [, cellPath] = cellEntry;
	const [, blockPath] = blockEntry;
	return {
		blockPath,
		cellPath,
		point
	};
};
const hasAdjacentBlockInCell = (editor, { blockPath, cellPath, reverse }) => {
	const adjacentBlock = reverse ? editor.api.previous({
		at: blockPath,
		block: true
	}) : editor.api.next({
		at: blockPath,
		block: true
	});
	return !!adjacentBlock && PathApi.isAncestor(cellPath, adjacentBlock[1]);
};
const shouldMoveSelectionFromCell = (editor, { blockPath, point, reverse }) => {
	const blockRange = editor.api.range(blockPath);
	const isAtBlockEdge = reverse ? editor.api.isStart(point, blockPath) : editor.api.isEnd(point, blockPath);
	if (!blockRange) return isAtBlockEdge;
	const caretRects = getRangeClientRects(editor.api.toDOMRange({
		anchor: point,
		focus: point
	}));
	const blockRects = getRangeClientRects(editor.api.toDOMRange(blockRange));
	if (caretRects.length === 0 || blockRects.length === 0) return isAtBlockEdge;
	const caretRect = caretRects.at(-1);
	const boundary = reverse ? Math.min(...blockRects.map((rect) => rect.top)) : Math.max(...blockRects.map((rect) => rect.bottom));
	return reverse ? caretRect.top <= boundary + VISUAL_LINE_TOLERANCE : caretRect.bottom >= boundary - VISUAL_LINE_TOLERANCE;
};

//#endregion
//#region src/lib/withApplyTable.ts
/**
* Selection table:
*
* - If anchor is in table, focus in a block before: set focus to start of table
* - If anchor is in table, focus in a block after: set focus to end of table
* - If focus is in table, anchor in a block before: set focus to end of table
* - If focus is in table, anchor in a block after: set focus to the point before
*   start of table
*/
const withApplyTable = ({ api: _api, editor, getOptions, tf: { apply }, type: tableType }) => ({ transforms: { apply(op) {
	if (op.type === "set_selection" && op.newProperties) {
		const newSelection = {
			...editor.selection,
			...op.newProperties
		};
		if (RangeApi.isRange(newSelection) && editor.api.isAt({
			at: newSelection,
			blocks: true,
			match: (n) => n.type === tableType
		})) {
			const anchorEntry = editor.api.block({
				at: newSelection.anchor,
				match: (n) => n.type === tableType
			});
			if (anchorEntry) {
				const [, anchorPath] = anchorEntry;
				if (RangeApi.isBackward(newSelection)) op.newProperties.focus = editor.api.start(anchorPath);
				else if (editor.api.before(anchorPath)) op.newProperties.focus = editor.api.end(anchorPath);
			} else {
				const focusEntry = editor.api.block({
					at: newSelection.focus,
					match: (n) => n.type === tableType
				});
				if (focusEntry) {
					const [, focusPath] = focusEntry;
					if (RangeApi.isBackward(newSelection)) {
						const startPoint = editor.api.start(focusPath);
						const pointBefore = editor.api.before(startPoint);
						op.newProperties.focus = pointBefore ?? startPoint;
					} else op.newProperties.focus = editor.api.end(focusPath);
				}
			}
		}
	}
	const opType = op.type === "remove_node" ? op.node.type : op.type === "move_node" ? editor.api.node(op.path)?.[0].type : void 0;
	const isTableOperation = (op.type === "remove_node" || op.type === "move_node") && opType && [
		editor.getType(KEYS.tr),
		tableType,
		...getCellTypes(editor)
	].includes(opType);
	if (isTableOperation && op.type === "remove_node") {
		const cells = [...editor.api.nodes({
			at: op.path,
			match: { type: getCellTypes(editor) }
		})];
		const cellIndices = getOptions()._cellIndices;
		cells.forEach(([cell]) => {
			delete cellIndices[cell.id];
		});
	}
	apply(op);
	let table;
	if (isTableOperation && opType !== tableType) {
		table = editor.api.node({
			at: op.type === "move_node" ? op.newPath : op.path,
			match: { type: tableType }
		})?.[0];
		if (table) computeCellIndices(editor, { tableNode: table });
	}
} } });

//#endregion
//#region src/lib/withDeleteTable.ts
/**
* Return true if:
*
* - At start/end of a cell.
* - Next to a table cell. Move selection to the table cell.
*/
const preventDeleteTableCell = (editor, { reverse, unit }) => {
	const { selection } = editor;
	const getNextPoint = reverse ? editor.api.after : editor.api.before;
	if (editor.api.isCollapsed()) {
		const cellEntry = editor.api.block({ match: { type: getCellTypes(editor) } });
		if (cellEntry) {
			const [, cellPath] = cellEntry;
			const start = reverse ? editor.api.end(cellPath) : editor.api.start(cellPath);
			if (selection && PointApi.equals(selection.anchor, start)) return true;
		} else {
			const nextPoint = getNextPoint(selection, { unit });
			if (editor.api.block({
				at: nextPoint,
				match: { type: getCellTypes(editor) }
			})) {
				editor.tf.move({ reverse: !reverse });
				return true;
			}
		}
	}
};
/** Prevent cell deletion. */
const withDeleteTable = ({ editor, tf: { deleteFragment }, type }) => ({ transforms: { deleteFragment(direction) {
	if (editor.api.isAt({
		block: true,
		match: (n) => n.type === type
	})) {
		const cellEntries = getTableGridAbove(editor, { format: "cell" });
		if (cellEntries.length > 1) {
			editor.tf.withoutNormalizing(() => {
				cellEntries.forEach(([, cellPath]) => {
					editor.tf.replaceNodes(editor.api.create.block(), {
						at: cellPath,
						children: true
					});
				});
				editor.tf.select({
					anchor: editor.api.start(cellEntries[0][1]),
					focus: editor.api.end(cellEntries.at(-1)[1])
				});
			});
			return;
		}
	}
	deleteFragment(direction);
} } });

//#endregion
//#region src/lib/withGetFragmentTable.ts
/** If selection is in a table, get subtable above. */
const withGetFragmentTable = ({ api, api: { getFragment }, editor, type }) => ({ api: { getFragment() {
	const fragment = getFragment();
	const newFragment = [];
	fragment.forEach((node) => {
		if (node.type === type) {
			const rows = node.children;
			const rowCount = rows.length;
			if (!rowCount) return;
			const colCount = rows[0].children.length;
			if (rowCount <= 1 && colCount <= 1) {
				const cell = rows[0];
				const cellChildren = api.table.getCellChildren(cell);
				newFragment.push(...cellChildren[0].children);
				return;
			}
			const subTable = getTableGridAbove(editor);
			if (subTable.length > 0) {
				newFragment.push(subTable[0][0]);
				return;
			}
		}
		newFragment.push(node);
	});
	return newFragment;
} } });

//#endregion
//#region src/lib/withInsertFragmentTable.ts
/**
* If inserting a table, If block above anchor is a table,
*
* - Replace each cell above by the inserted table until out of bounds.
* - Select the inserted cells.
*/
const withInsertFragmentTable = ({ api, editor, getOptions, tf: { insert, insertFragment }, type }) => ({ transforms: { insertFragment(fragment) {
	const insertedTable = fragment.find((n) => n.type === type);
	if (!insertedTable) {
		if (getTableAbove(editor, { at: editor.selection?.anchor })) {
			const cellEntries = getTableGridAbove(editor, { format: "cell" });
			if (cellEntries.length > 1) {
				cellEntries.forEach((cellEntry) => {
					if (cellEntry) {
						const [, cellPath] = cellEntry;
						editor.tf.replaceNodes(cloneDeep(fragment), {
							at: cellPath,
							children: true
						});
					}
				});
				editor.tf.select({
					anchor: editor.api.start(cellEntries[0][1]),
					focus: editor.api.end(cellEntries.at(-1)[1])
				});
				return;
			}
		}
	}
	if (insertedTable) {
		if (getTableAbove(editor, { at: editor.selection?.anchor })) {
			const [cellEntry] = getTableGridAbove(editor, {
				at: editor.selection?.anchor,
				format: "cell"
			});
			if (cellEntry) {
				editor.tf.withoutNormalizing(() => {
					const [, startCellPath] = cellEntry;
					const cellPath = [...startCellPath];
					const startColIndex = cellPath.at(-1);
					let lastCellPath = null;
					let initRow = true;
					insertedTable.children.forEach((row) => {
						cellPath[cellPath.length - 1] = startColIndex;
						if (!initRow) {
							const fromRow = cellPath.slice(0, -1);
							cellPath[cellPath.length - 2] += 1;
							if (!NodeApi.has(editor, cellPath)) {
								if (getOptions().disableExpandOnInsert) return;
								insert.tableRow({ fromRow });
							}
						}
						initRow = false;
						const insertedCells = row.children;
						let initCell = true;
						insertedCells.forEach((cell) => {
							if (!initCell) {
								const fromCell = [...cellPath];
								cellPath[cellPath.length - 1] += 1;
								if (!NodeApi.has(editor, cellPath)) {
									if (getOptions().disableExpandOnInsert) return;
									insert.tableColumn({ fromCell });
								}
							}
							initCell = false;
							const cellChildren = api.table.getCellChildren(cell);
							editor.tf.replaceNodes(cloneDeep(cellChildren), {
								at: cellPath,
								children: true
							});
							lastCellPath = [...cellPath];
						});
					});
					if (lastCellPath) editor.tf.select({
						anchor: editor.api.start(startCellPath),
						focus: editor.api.end(lastCellPath)
					});
				});
				return;
			}
		} else if (fragment.length === 1 && fragment[0].type === KEYS.table) {
			editor.tf.insertNodes(fragment[0]);
			return;
		}
	}
	insertFragment(fragment);
} } });

//#endregion
//#region src/lib/withInsertTextTable.ts
const withInsertTextTable = ({ editor, tf: { insertText } }) => ({ transforms: { insertText(text, options) {
	if (editor.api.isExpanded()) {
		if (getTableAbove(editor, { at: editor.selection?.anchor })) {
			if (getTableGridAbove(editor, { format: "cell" }).length > 1) editor.tf.collapse({ edge: "focus" });
		}
	}
	insertText(text, options);
} } });

//#endregion
//#region src/lib/withNormalizeTable.ts
/**
* Normalize table:
*
* - Wrap cell children in a paragraph if they are texts.
*/
const withNormalizeTable = ({ editor, getOption, getOptions, tf: { normalizeNode }, type }) => ({ transforms: { normalizeNode([n, path]) {
	const { enableUnsetSingleColSize, initialTableWidth } = getOptions();
	if (ElementApi.isElement(n)) {
		if (n.type === type) {
			const node = n;
			if (!node.children.some((child) => ElementApi.isElement(child) && child.type === editor.getType(KEYS.tr))) {
				editor.tf.removeNodes({ at: path });
				return;
			}
			if (node.colSizes && node.colSizes.length > 0 && enableUnsetSingleColSize && getTableColumnCount(node) < 2) {
				editor.tf.unsetNodes("colSizes", { at: path });
				return;
			}
			if (editor.api.block({
				above: true,
				at: path,
				match: { type }
			})) {
				editor.tf.unwrapNodes({ at: path });
				return;
			}
			if (initialTableWidth) {
				const tableNode = node;
				const colCount = (tableNode.children[0]?.children)?.length;
				if (colCount) {
					const colSizes = [];
					if (!tableNode.colSizes) for (let i = 0; i < colCount; i++) colSizes.push(initialTableWidth / colCount);
					else if (tableNode.colSizes.some((size) => !size)) tableNode.colSizes.forEach((colSize) => {
						colSizes.push(colSize || initialTableWidth / colCount);
					});
					if (colSizes.length > 0) {
						editor.tf.setNodes({ colSizes }, { at: path });
						return;
					}
				}
			}
		}
		if (n.type === editor.getType(KEYS.tr)) {
			if (editor.api.parent(path)?.[0].type !== type) {
				editor.tf.unwrapNodes({ at: path });
				return;
			}
		}
		if (getCellTypes(editor).includes(n.type)) {
			const node = n;
			const cellIndices = getOption("cellIndices", node.id);
			if (node.id && !cellIndices) computeCellIndices(editor, {
				all: true,
				cellNode: node
			});
			const { children } = node;
			if (editor.api.parent(path)?.[0].type !== editor.getType(KEYS.tr)) {
				editor.tf.unwrapNodes({ at: path });
				return;
			}
			if (TextApi.isText(children[0])) {
				editor.tf.wrapNodes(editor.api.create.block({}, path), {
					at: path,
					children: true
				});
				return;
			}
		}
	}
	normalizeNode([n, path]);
} } });

//#endregion
//#region src/lib/withSetFragmentDataTable.ts
const withSetFragmentDataTable = ({ api, editor, plugin, tf: { setFragmentData } }) => ({ transforms: { setFragmentData(data, originEvent) {
	const tableEntry = getTableGridAbove(editor, { format: "table" })?.[0];
	const selectedCellEntries = getTableGridAbove(editor, { format: "cell" });
	const initialSelection = editor.selection;
	if (!tableEntry || !initialSelection) {
		setFragmentData(data, originEvent);
		return;
	}
	const [tableNode, tablePath] = tableEntry;
	const tableRows = tableNode.children;
	tableNode.children = tableNode.children.filter((v) => v.children.length > 0);
	let textCsv = "";
	let textTsv = "";
	const divElement = document.createElement("div");
	const tableElement = document.createElement("table");
	/**
	* Cover single cell copy | cut operation. In this case, copy cell content
	* instead of table structure.
	*/
	if (tableEntry && initialSelection && selectedCellEntries.length === 1 && (originEvent === "copy" || originEvent === "cut")) {
		setFragmentData(data);
		return;
	}
	editor.tf.withoutNormalizing(() => {
		tableRows.forEach((row) => {
			const rowCells = row.children;
			const cellStrings = [];
			const rowElement = row.type === editor.getType(KEYS.th) ? document.createElement("th") : document.createElement("tr");
			rowCells.forEach((cell) => {
				data.clearData();
				const cellPath = editor.api.findPath(cell);
				editor.tf.select({
					anchor: editor.api.start(cellPath),
					focus: editor.api.end(cellPath)
				});
				setFragmentData(data);
				cellStrings.push(data.getData("text/plain"));
				const cellElement = document.createElement("td");
				cellElement.colSpan = api.table.getColSpan(cell);
				cellElement.rowSpan = api.table.getRowSpan(cell);
				cellElement.innerHTML = data.getData("text/html");
				rowElement.append(cellElement);
			});
			tableElement.append(rowElement);
			textCsv += `${cellStrings.join(",")}\n`;
			textTsv += `${cellStrings.join("	")}\n`;
		});
		const _tableEntry = editor.api.node({
			at: tablePath,
			match: { type: KEYS.table }
		});
		if (_tableEntry != null && _tableEntry.length > 0) {
			const realTable = _tableEntry[0];
			if (realTable.attributes != null) Object.entries(realTable.attributes).forEach(([key, value]) => {
				if (value != null && plugin.node.dangerouslyAllowAttributes?.includes(key)) tableElement.setAttribute(key, String(value));
			});
		}
		editor.tf.select(initialSelection);
		divElement.append(tableElement);
	});
	data.setData("text/csv", textCsv);
	data.setData("text/tsv", textTsv);
	data.setData("text/plain", textTsv);
	data.setData("text/html", divElement.innerHTML);
	const selectedFragmentStr = JSON.stringify([tableNode]);
	const encodedFragment = window.btoa(encodeURIComponent(selectedFragmentStr));
	data.setData("application/x-slate-fragment", encodedFragment);
} } });

//#endregion
//#region src/lib/withTableCellSelection.tsx
const isTargetingSelectedCell = (editor, target, cellPaths) => {
	if (PathApi.isPath(target)) return cellPaths.some((cellPath) => PathApi.isCommon(cellPath, target));
	const range = editor.api.range(target);
	if (!range) return false;
	return cellPaths.some((cellPath) => {
		const cellRange = editor.api.range(cellPath);
		if (!cellRange) return false;
		return RangeApi.includes(cellRange, range.anchor) || RangeApi.includes(cellRange, range.focus) || RangeApi.includes(range, cellRange);
	});
};
const withTableCellSelection = ({ api: { marks }, editor, tf: { addMark, removeMark, setNodes } }) => ({
	api: { marks() {
		const apply = () => {
			const { selection } = editor;
			if (!selection || editor.api.isCollapsed()) return;
			const matchesCell = getTableGridAbove(editor, { format: "cell" });
			if (matchesCell.length <= 1) return;
			const markCounts = {};
			const totalMarks = {};
			let totalNodes = 0;
			matchesCell.forEach(([_cell, cellPath]) => {
				const textNodeEntry = editor.api.nodes({
					at: cellPath,
					match: (n) => TextApi.isText(n)
				});
				Array.from(textNodeEntry, (item) => item[0]).forEach((item) => {
					totalNodes++;
					const keys = Object.keys(item);
					if (keys.length === 1) return;
					keys.splice(keys.indexOf("text"), 1);
					keys.forEach((k) => {
						markCounts[k] = (markCounts[k] || 0) + 1;
						totalMarks[k] = item[k];
					});
				});
			});
			Object.keys(markCounts).forEach((mark) => {
				if (markCounts[mark] !== totalNodes) delete totalMarks[mark];
			});
			return totalMarks;
		};
		const result = apply();
		if (result) return result;
		return marks();
	} },
	transforms: {
		addMark(key, value) {
			const apply = () => {
				const { selection } = editor;
				if (!selection || editor.api.isCollapsed() || editor.meta.isNormalizing) return;
				const matchesCell = getTableGridAbove(editor, { format: "cell" });
				if (matchesCell.length <= 1) return;
				matchesCell.forEach(([_cell, cellPath]) => {
					editor.tf.setNodes({ [key]: value }, {
						at: cellPath,
						split: true,
						voids: true,
						match: (n) => TextApi.isText(n)
					});
				});
				return true;
			};
			if (apply()) return;
			return addMark(key, value);
		},
		removeMark(key) {
			const apply = () => {
				const { selection } = editor;
				if (!selection || editor.api.isCollapsed() || editor.meta.isNormalizing) return;
				const matchesCell = getTableGridAbove(editor, { format: "cell" });
				if (matchesCell.length <= 1) return;
				matchesCell.forEach(([_cell, cellPath]) => {
					editor.tf.setNodes({ [key]: null }, {
						at: cellPath,
						split: true,
						voids: true,
						match: (n) => TextApi.isText(n)
					});
				});
				return true;
			};
			if (apply()) return;
			return removeMark(key);
		},
		setNodes(props, options) {
			const apply = () => {
				const { selection } = editor;
				if (!selection || editor.api.isCollapsed() || editor.meta.isNormalizing) return;
				const matchesCell = getTableGridAbove(editor, { format: "cell" });
				if (matchesCell.length <= 1) return;
				if (options?.at) {
					const cellPaths = matchesCell.map(([, cellPath]) => cellPath);
					if (!isTargetingSelectedCell(editor, options.at, cellPaths)) return;
				}
				setNodes(props, {
					...options,
					match: combineTransformMatchOptions(editor, (_, p) => matchesCell.some(([_$1, cellPath]) => PathApi.isCommon(cellPath, p)), options)
				});
				return true;
			};
			if (apply()) return;
			return setNodes(props, options);
		}
	}
});

//#endregion
//#region src/lib/withTable.ts
const withTable = (ctx) => {
	const { editor, tf: { moveLine, selectAll, tab }, type } = ctx;
	const cellSelection = withTableCellSelection(ctx);
	return {
		api: {
			...withGetFragmentTable(ctx).api,
			...cellSelection.api
		},
		transforms: {
			moveLine: (options) => {
				const apply = () => {
					if (!editor.api.isCollapsed()) return;
					const context = getTableMoveSelectionContext(editor);
					if (!context) return;
					const { blockPath, cellPath, point } = context;
					if (hasAdjacentBlockInCell(editor, {
						blockPath,
						cellPath,
						reverse: options.reverse
					})) return;
					if (!shouldMoveSelectionFromCell(editor, {
						blockPath,
						point,
						reverse: options.reverse
					})) return;
					return moveSelectionFromCell(editor, { reverse: options.reverse });
				};
				if (apply()) return true;
				return moveLine(options);
			},
			selectAll: () => {
				const apply = () => {
					const table = editor.api.above({ match: { type } });
					if (!table) return;
					const [, tablePath] = table;
					const tableRange = editor.api.range(tablePath);
					if (tableRange && editor.selection && RangeApi.equals(editor.selection, tableRange)) {
						const documentRange = editor.api.range([]);
						if (!documentRange) return true;
						editor.tf.select(documentRange);
						return true;
					}
					editor.tf.select(tablePath);
					return true;
				};
				if (apply()) return true;
				return selectAll();
			},
			tab: (options) => {
				const apply = () => {
					if (editor.selection && editor.api.isExpanded()) {
						if (Array.from(editor.api.nodes({
							at: editor.selection,
							match: { type: getCellTypes(editor) }
						})).length > 1) {
							editor.tf.collapse({ edge: "end" });
							return true;
						}
					}
					const entries = getTableEntries(editor);
					if (!entries) return;
					const { cell, row } = entries;
					const [, cellPath] = cell;
					if (options.reverse) {
						const previousCell = getPreviousTableCell(editor, cell, cellPath, row);
						if (previousCell) {
							const [, previousCellPath] = previousCell;
							editor.tf.select(previousCellPath);
						}
					} else {
						const nextCell = getNextTableCell(editor, cell, cellPath, row);
						if (nextCell) {
							const [, nextCellPath] = nextCell;
							editor.tf.select(nextCellPath);
						}
					}
					return true;
				};
				if (apply()) return true;
				return tab(options);
			},
			...withNormalizeTable(ctx).transforms,
			...withDeleteTable(ctx).transforms,
			...withInsertFragmentTable(ctx).transforms,
			...withInsertTextTable(ctx).transforms,
			...withApplyTable(ctx).transforms,
			...withSetFragmentDataTable(ctx).transforms,
			...cellSelection.transforms
		}
	};
};

//#endregion
//#region src/lib/BaseTablePlugin.ts
const parse = ({ element, type }) => {
	const background = element.style.background || element.style.backgroundColor;
	if (background) return {
		background,
		type
	};
	return { type };
};
const BaseTableRowPlugin = createSlatePlugin({
	key: KEYS.tr,
	node: {
		isContainer: true,
		isElement: true,
		isStrictSiblings: true
	},
	parsers: { html: { deserializer: { rules: [{ validNodeName: "TR" }] } } }
});
const BaseTableCellPlugin = createSlatePlugin({
	key: KEYS.td,
	node: {
		dangerouslyAllowAttributes: ["colspan", "rowspan"],
		isContainer: true,
		isElement: true,
		isStrictSiblings: true,
		props: ({ element }) => ({
			colSpan: (element?.attributes)?.colspan,
			rowSpan: (element?.attributes)?.rowspan
		})
	},
	parsers: { html: { deserializer: {
		attributeNames: ["rowspan", "colspan"],
		parse,
		rules: [{ validNodeName: "TD" }]
	} } },
	rules: { merge: { removeEmpty: false } }
});
const BaseTableCellHeaderPlugin = createSlatePlugin({
	key: KEYS.th,
	node: {
		dangerouslyAllowAttributes: ["colspan", "rowspan"],
		isContainer: true,
		isElement: true,
		isStrictSiblings: true,
		props: ({ element }) => ({
			colSpan: (element?.attributes)?.colspan,
			rowSpan: (element?.attributes)?.rowspan
		})
	},
	parsers: { html: { deserializer: {
		attributeNames: ["rowspan", "colspan"],
		parse,
		rules: [{ validNodeName: "TH" }]
	} } },
	rules: { merge: { removeEmpty: false } }
});
/** Enables support for tables. */
const BaseTablePlugin = createTSlatePlugin({
	key: KEYS.table,
	node: {
		isContainer: true,
		isElement: true
	},
	transformInitialValue: normalizeInitialValueTable,
	options: {
		_cellIndices: {},
		_selectedCellIds: void 0,
		_selectedTableIds: void 0,
		_selectionVersion: 0,
		disableMerge: false,
		minColumnWidth: 48,
		selectedCells: null,
		selectedTables: null
	},
	parsers: { html: { deserializer: { rules: [{ validNodeName: "TABLE" }] } } },
	plugins: [
		BaseTableRowPlugin,
		BaseTableCellPlugin,
		BaseTableCellHeaderPlugin
	]
}).extendSelectors(({ editor, getOptions }) => ({
	cellIndices: (id) => getOptions()._cellIndices[id],
	isCellSelected: (id) => {
		const selectedCellIds = getOptions()._selectedCellIds;
		if (selectedCellIds !== void 0) return !!id && (selectedCellIds?.includes(id) ?? false);
		return isCellSelected(editor, id);
	},
	isSelectingCell: () => {
		const selectedCellIds = getOptions()._selectedCellIds;
		if (selectedCellIds !== void 0) return !!selectedCellIds;
		return isSelectingCell(editor);
	},
	selectedCell: (id) => {
		getOptions()._selectionVersion;
		return getSelectedCell(editor, id);
	},
	selectedCellIds: () => {
		const selectedCellIds = getOptions()._selectedCellIds;
		if (selectedCellIds !== void 0) return selectedCellIds;
		return getSelectedCellIds(editor);
	},
	selectedCells: () => {
		getOptions()._selectionVersion;
		return getSelectedCells(editor);
	},
	selectedTableIds: () => {
		const selectedTableIds = getOptions()._selectedTableIds;
		if (selectedTableIds !== void 0) return selectedTableIds;
		return getSelectedTableIds(editor);
	},
	selectedTables: () => {
		getOptions()._selectionVersion;
		return getSelectedTables(editor);
	}
})).extendEditorApi(({ editor }) => ({
	create: {
		table: bindFirst(getEmptyTableNode, editor),
		tableCell: bindFirst(getEmptyCellNode, editor),
		tableRow: bindFirst(getEmptyRowNode, editor)
	},
	table: {
		getCellBorders: bindFirst(getTableCellBorders, editor),
		getCellSize: bindFirst(getTableCellSize, editor),
		getSelectedCell: bindFirst(getSelectedCell, editor),
		getSelectedCellIds: bindFirst(getSelectedCellIds, editor),
		getSelectedCells: bindFirst(getSelectedCells, editor),
		getSelectedTableIds: bindFirst(getSelectedTableIds, editor),
		getSelectedTables: bindFirst(getSelectedTables, editor),
		getColSpan,
		getRowSpan,
		getCellChildren: (cell) => cell.children,
		isCellSelected: bindFirst(isCellSelected, editor),
		isSelectingCell: bindFirst(isSelectingCell, editor)
	}
})).extendEditorTransforms(({ editor }) => ({
	insert: {
		table: bindFirst(insertTable, editor),
		tableColumn: bindFirst(insertTableColumn, editor),
		tableRow: bindFirst(insertTableRow, editor)
	},
	remove: {
		table: bindFirst(deleteTable, editor),
		tableColumn: bindFirst(deleteColumn, editor),
		tableRow: bindFirst(deleteRow, editor)
	},
	table: {
		merge: bindFirst(mergeTableCells, editor),
		split: bindFirst(splitTableCell, editor)
	}
})).overrideEditor(withTable);

//#endregion
//#region src/lib/constants.ts
const KEY_SHIFT_EDGES = {
	"shift+down": "bottom",
	"shift+left": "left",
	"shift+right": "right",
	"shift+up": "top"
};

//#endregion
export { getSelectedCellEntries as $, normalizeInitialValueTable as A, deleteColumnWhenExpanded as B, moveSelectionFromCell as C, getColSpan as Ct, deleteTable as D, insertTable as E, getEmptyCellNode as Et, deleteTableMergeRow as F, getTableAbove as G, getTableColumnCount as H, deleteRowWhenExpanded as I, isSelectedCellBordersNone as J, getSelectedCellsBorders as K, deleteTableMergeColumn as L, mergeTableCells as M, insertTableMergeRow as N, deleteRow as O, insertTableMergeColumn as P, getSelectedCell as Q, getTableMergedColumnCount as R, setBorderSize as S, getRowSpan as St, insertTableColumn as T, getEmptyRowNode as Tt, getTableCellSize as U, getTableOverriddenColSizes as V, getTableCellBorders as W, getTopTableCell as X, isSelectedCellBordersOuter as Y, getSelectedCellsBoundingBox as Z, hasAdjacentBlockInCell as _, getCellTypes as _t, BaseTableRowPlugin as a, isSelectingCell as at, setTableMarginLeft as b, computeCellIndices as bt, withSetFragmentDataTable as c, getTableMergeGridByRange as ct, withInsertFragmentTable as d, getNextTableCell as dt, getSelectedCellIds as et, withGetFragmentTable as f, getLeftTableCell as ft, getTableMoveSelectionContext as g, getTableEntries as gt, withApplyTable as h, getAdjacentTableCell as ht, BaseTablePlugin as i, isCellSelected as it, splitTableCell as j, deleteColumn as k, withNormalizeTable as l, findCellByIndexes as lt, withDeleteTable as m, getCellInNextTableRow as mt, BaseTableCellHeaderPlugin as n, getSelectedTableIds as nt, withTable as o, getTableGridAbove as ot, preventDeleteTableCell as p, getCellInPreviousTableRow as pt, isSelectedCellBorder as q, BaseTableCellPlugin as r, getSelectedTables as rt, withTableCellSelection as s, getTableGridByRange as st, KEY_SHIFT_EDGES as t, getSelectedCells as tt, withInsertTextTable as u, getPreviousTableCell as ut, shouldMoveSelectionFromCell as v, getCellRowIndexByPath as vt, insertTableRow as w, getEmptyTableNode as wt, setTableColSize as x, getCellIndicesWithSpans as xt, setTableRowSize as y, getCellIndices as yt, getCellPath as z };