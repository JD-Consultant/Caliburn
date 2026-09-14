import { A as insertTable, G as getTableCellSize, It as getEmptyRowNode, K as BorderStylesDefault, Lt as getEmptyCellNode, M as deleteRow, N as deleteColumn, O as insertTableRow, Pt as getEmptyTableNode, Rt as BorderDirection, Ut as CellIndices, _ as TableConfig, at as getSelectedCells, ct as isCellSelected, it as getSelectedCellIds, j as deleteTable, k as insertTableColumn, lt as isSelectingCell, mt as getColSpan, nt as getSelectedCell, ot as getSelectedTableIds, q as getTableCellBorders, st as getSelectedTables, ut as getRowSpan, vt as splitTableCell, yt as mergeTableCells } from "../index-BYg7T9gA";
import * as platejs0 from "platejs";
import { SlateEditor, TElement, TTableCellElement, TTableElement } from "platejs";
import * as platejs_react0 from "platejs/react";
import { KeyboardHandler } from "platejs/react";
import React from "react";
import { ResizeHandle } from "@platejs/resizable";

//#region src/react/TablePlugin.d.ts
declare const TableRowPlugin: platejs_react0.PlatePlugin<platejs0.PluginConfig<"tr", {}, {}, {}, {}>>;
declare const TableCellPlugin: platejs_react0.PlatePlugin<platejs0.PluginConfig<"td", {}, {}, {}, {}>>;
declare const TableCellHeaderPlugin: platejs_react0.PlatePlugin<platejs0.PluginConfig<"th", {}, {}, {}, {}>>;
/** Enables support for tables with React-specific features. */
declare const TablePlugin: platejs_react0.PlatePlugin<platejs0.PluginConfig<"table", {
  _cellIndices: Record<string, {
    col: number;
    row: number;
  }>;
  _selectedCellIds: string[] | null | undefined;
  _selectedTableIds: string[] | null | undefined;
  _selectionVersion: number;
  selectedCells: platejs0.TElement[] | null;
  selectedTables: platejs0.TElement[] | null;
  disableExpandOnInsert?: boolean;
  disableMarginLeft?: boolean;
  disableMerge?: boolean;
  enableUnsetSingleColSize?: boolean;
  initialTableWidth?: number;
  minColumnWidth?: number;
}, {
  create: {
    table: platejs0.OmitFirst<typeof getEmptyTableNode>;
    tableCell: platejs0.OmitFirst<typeof getEmptyCellNode>;
    tableRow: platejs0.OmitFirst<typeof getEmptyRowNode>;
  };
  table: {
    getCellBorders: platejs0.OmitFirst<typeof getTableCellBorders>;
    getCellSize: platejs0.OmitFirst<typeof getTableCellSize>;
    getSelectedCell: platejs0.OmitFirst<typeof getSelectedCell>;
    getSelectedCellIds: platejs0.OmitFirst<typeof getSelectedCellIds>;
    getSelectedCells: platejs0.OmitFirst<typeof getSelectedCells>;
    getSelectedTableIds: platejs0.OmitFirst<typeof getSelectedTableIds>;
    getSelectedTables: platejs0.OmitFirst<typeof getSelectedTables>;
    getColSpan: typeof getColSpan;
    getRowSpan: typeof getRowSpan;
    getCellChildren: (cell: platejs0.TTableCellElement) => platejs0.Descendant[];
    isCellSelected: platejs0.OmitFirst<typeof isCellSelected>;
    isSelectingCell: platejs0.OmitFirst<typeof isSelectingCell>;
  };
} & {
  create: {
    table: platejs0.OmitFirst<typeof getEmptyTableNode>;
    tableCell: platejs0.OmitFirst<typeof getEmptyCellNode>;
    tableRow: platejs0.OmitFirst<typeof getEmptyRowNode>;
  };
  table: {
    getCellBorders: platejs0.OmitFirst<typeof getTableCellBorders>;
    getCellSize: platejs0.OmitFirst<typeof getTableCellSize>;
    getSelectedCell: platejs0.OmitFirst<typeof getSelectedCell>;
    getSelectedCellIds: platejs0.OmitFirst<typeof getSelectedCellIds>;
    getSelectedCells: platejs0.OmitFirst<typeof getSelectedCells>;
    getSelectedTableIds: platejs0.OmitFirst<typeof getSelectedTableIds>;
    getSelectedTables: platejs0.OmitFirst<typeof getSelectedTables>;
    getColSpan: typeof getColSpan;
    getRowSpan: typeof getRowSpan;
    getCellChildren: (cell: platejs0.TTableCellElement) => platejs0.Descendant[];
    isCellSelected: platejs0.OmitFirst<typeof isCellSelected>;
    isSelectingCell: platejs0.OmitFirst<typeof isSelectingCell>;
  };
}, {
  insert: {
    table: platejs0.OmitFirst<typeof insertTable>;
    tableColumn: platejs0.OmitFirst<typeof insertTableColumn>;
    tableRow: platejs0.OmitFirst<typeof insertTableRow>;
  };
  remove: {
    table: platejs0.OmitFirst<typeof deleteTable>;
    tableColumn: platejs0.OmitFirst<typeof deleteColumn>;
    tableRow: platejs0.OmitFirst<typeof deleteRow>;
  };
  table: {
    merge: platejs0.OmitFirst<typeof mergeTableCells>;
    split: platejs0.OmitFirst<typeof splitTableCell>;
  };
} & {
  insert: {
    table: platejs0.OmitFirst<typeof insertTable>;
    tableColumn: platejs0.OmitFirst<typeof insertTableColumn>;
    tableRow: platejs0.OmitFirst<typeof insertTableRow>;
  };
  remove: {
    table: platejs0.OmitFirst<typeof deleteTable>;
    tableColumn: platejs0.OmitFirst<typeof deleteColumn>;
    tableRow: platejs0.OmitFirst<typeof deleteRow>;
  };
  table: {
    merge: platejs0.OmitFirst<typeof mergeTableCells>;
    split: platejs0.OmitFirst<typeof splitTableCell>;
  };
}, {
  cellIndices?: (id: string) => CellIndices;
  isCellSelected?: (id?: string | null) => boolean;
  isSelectingCell?: () => boolean;
  selectedCell?: (id?: string | null) => platejs0.TElement | null;
  selectedCellIds?: () => string[] | null;
  selectedCells?: () => platejs0.TElement[] | null;
  selectedTableIds?: () => string[] | null;
  selectedTables?: () => platejs0.TElement[] | null;
}>>;
//#endregion
//#region src/react/onKeyDownTable.d.ts
declare const onKeyDownTable: KeyboardHandler<TableConfig>;
//#endregion
//#region src/react/components/TableCellElement/getOnSelectTableBorderFactory.d.ts
/**
 * Toggle logic for `'none'`, `'outer'`, `'top'|'bottom'|'left'|'right'`.
 * `'none'` toggles no borders ↔ all borders, `'outer'` toggles the bounding
 * rectangle's outer edges on/off, `'top'|'bottom'|'left'|'right'` toggles only
 * that side of the bounding rect.
 */
declare function setSelectedCellsBorder(editor: SlateEditor, {
  border,
  cells
}: {
  border: BorderDirection | 'none' | 'outer';
  cells: TTableCellElement[];
}): void;
/**
 * Returns a function that sets borders on the selection with toggling logic. If
 * selection has one or many cells, it's the same approach: we read the bounding
 * rectangle, then decide which edges to flip on/off.
 */
declare const getOnSelectTableBorderFactory: (editor: SlateEditor) => (border: BorderDirection | "none" | "outer") => () => void;
//#endregion
//#region src/react/components/TableCellElement/roundCellSizeToStep.d.ts
/**
 * Rounds a cell size to the nearest step, or returns the size if the step is
 * not set.
 */
declare const roundCellSizeToStep: (size: number, step?: number) => number;
//#endregion
//#region src/react/components/TableCellElement/useIsCellSelected.d.ts
declare const useIsCellSelected: (element: TElement) => boolean;
//#endregion
//#region src/react/components/TableCellElement/useTableBordersDropdownMenuContentState.d.ts
declare const useTableBordersDropdownMenuContentState: ({
  element: el
}?: {
  element?: TTableElement;
}) => {
  getOnSelectTableBorder: (border: BorderDirection | "none" | "outer") => () => void;
  hasBottomBorder: boolean;
  hasLeftBorder: boolean;
  hasNoBorders: boolean;
  hasOuterBorders: boolean;
  hasRightBorder: boolean;
  hasTopBorder: boolean;
};
//#endregion
//#region src/react/components/TableCellElement/useTableCellBorders.d.ts
declare function useTableCellBorders({
  element: el
}?: {
  element?: TTableCellElement;
}): BorderStylesDefault;
//#endregion
//#region src/react/components/TableCellElement/useTableCellElement.d.ts
type TableCellElementState = {
  borders: BorderStylesDefault;
  colIndex: number;
  colSpan: number;
  isSelectingCell: boolean;
  minHeight: number | undefined;
  rowIndex: number;
  selected: boolean;
  width: number | string;
};
declare const useTableCellElement: () => TableCellElementState;
//#endregion
//#region src/react/components/TableCellElement/useTableCellElementResizable.d.ts
type TableCellElementResizableOptions = {
  /** Resize by step instead of by pixel. */
  step?: number;
  /** Overrides for X and Y axes. */
  stepX?: number;
  stepY?: number;
} & Pick<TableCellElementState, 'colIndex' | 'colSpan' | 'rowIndex'>;
declare const useTableCellElementResizable: ({
  colIndex,
  colSpan,
  rowIndex,
  step,
  stepX,
  stepY
}: TableCellElementResizableOptions) => {
  bottomProps: React.ComponentPropsWithoutRef<typeof ResizeHandle>;
  hiddenLeft: boolean;
  leftProps: React.ComponentPropsWithoutRef<typeof ResizeHandle>;
  rightProps: React.ComponentPropsWithoutRef<typeof ResizeHandle>;
};
//#endregion
//#region src/react/components/TableCellElement/useTableCellSize.d.ts
declare function useTableCellSize({
  element: el
}?: {
  element?: TTableCellElement;
}): {
  minHeight: number;
  width: number;
};
//#endregion
//#region src/react/components/TableElement/useSelectedCells.d.ts
declare const useSelectedCells: () => void;
//#endregion
//#region src/react/components/TableElement/useTableColSizes.d.ts
/**
 * Returns colSizes with overrides applied. Unset node.colSizes if `colCount`
 * updates to 1.
 */
declare const useTableColSizes: ({
  disableOverrides,
  transformColSizes
}?: {
  disableOverrides?: boolean;
  transformColSizes?: (colSizes: number[]) => number[];
}) => number[];
//#endregion
//#region src/react/components/TableElement/useTableElement.d.ts
declare const useTableElement: () => {
  marginLeft: any;
  props: {
    onMouseDown: () => void;
  };
};
//#endregion
//#region src/react/components/TableElement/useTableSelectionDom.d.ts
declare const useTableSelectionDom: (tableRef: React.RefObject<HTMLTableElement | null>) => void;
//#endregion
//#region src/react/hooks/useCellIndices.d.ts
declare const useCellIndices: () => any;
//#endregion
//#region src/react/hooks/useTableMergeState.d.ts
declare const useTableMergeState: () => {
  canMerge: boolean;
  canSplit: boolean;
};
//#endregion
//#region src/react/stores/useTableStore.d.ts
declare const TableProvider: any, tableStore: any, useTableSet: any, useTableState: any, useTableStore: any, useTableValue: any;
declare const useOverrideColSize: () => (index: number, size: number | null) => void;
declare const useOverrideRowSize: () => (index: number, size: number | null) => void;
declare const useOverrideMarginLeft: () => any;
//#endregion
export { TableCellElementResizableOptions, TableCellElementState, TableCellHeaderPlugin, TableCellPlugin, TablePlugin, TableProvider, TableRowPlugin, getOnSelectTableBorderFactory, onKeyDownTable, roundCellSizeToStep, setSelectedCellsBorder, tableStore, useCellIndices, useIsCellSelected, useOverrideColSize, useOverrideMarginLeft, useOverrideRowSize, useSelectedCells, useTableBordersDropdownMenuContentState, useTableCellBorders, useTableCellElement, useTableCellElementResizable, useTableCellSize, useTableColSizes, useTableElement, useTableMergeState, useTableSelectionDom, useTableSet, useTableState, useTableStore, useTableValue };