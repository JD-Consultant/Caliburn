import * as platejs56 from "platejs";
import { Descendant, Editor, EditorAboveOptions, ElementEntry, InsertNodesOptions, NodeEntry, OmitFirst, OverrideEditor, Path, PluginConfig, SlateEditor, TElement, TLocation, TRange, TTableCellBorder, TTableCellElement, TTableElement, TTableRowElement, TransformInitialValue } from "platejs";

//#region src/lib/utils/computeCellIndices.d.ts
declare function computeCellIndices(editor: SlateEditor, {
  all,
  cellNode,
  tableNode
}: {
  all?: boolean;
  cellNode?: TTableCellElement;
  tableNode?: TTableElement;
}): {
  col: number;
  row: number;
} | undefined;
//#endregion
//#region src/lib/utils/getCellIndices.d.ts
type CellIndices = {
  col: number;
  row: number;
};
declare const getCellIndices: (editor: SlateEditor, element: TTableCellElement) => CellIndices;
//#endregion
//#region src/lib/utils/getCellRowIndexByPath.d.ts
declare const getCellRowIndexByPath: (cellPath: Path) => number;
//#endregion
//#region src/lib/utils/getCellType.d.ts
/** Get td and th types */
declare const getCellTypes: (editor: SlateEditor) => string[];
//#endregion
//#region src/lib/types.d.ts
type BorderDirection = 'bottom' | 'left' | 'right' | 'top';
type CreateCellOptions = {
  children?: Descendant[];
  header?: boolean;
  row?: TTableRowElement;
};
type TableStoreSizeOverrides = Map<number, number>;
//#endregion
//#region src/lib/api/getEmptyCellNode.d.ts
declare const getEmptyCellNode: (editor: SlateEditor, {
  children,
  header,
  row
}?: CreateCellOptions) => {
  children: platejs56.Descendant[];
  type: string;
};
//#endregion
//#region src/lib/api/getEmptyRowNode.d.ts
interface GetEmptyRowNodeOptions extends CreateCellOptions {
  colCount?: number;
}
declare const getEmptyRowNode: (editor: SlateEditor, {
  colCount,
  ...cellOptions
}?: GetEmptyRowNodeOptions) => {
  children: {
    children: platejs56.Descendant[];
    type: string;
  }[];
  type: string;
};
//#endregion
//#region src/lib/api/getEmptyTableNode.d.ts
interface GetEmptyTableNodeOptions extends GetEmptyRowNodeOptions {
  rowCount?: number;
}
declare const getEmptyTableNode: (editor: SlateEditor, {
  colCount,
  header,
  rowCount,
  ...cellOptions
}?: GetEmptyTableNodeOptions) => TTableElement;
//#endregion
//#region src/lib/merge/deleteColumn.d.ts
declare const deleteTableMergeColumn: (editor: SlateEditor) => void;
//#endregion
//#region src/lib/merge/deleteColumnWhenExpanded.d.ts
declare const deleteColumnWhenExpanded: (editor: SlateEditor, tableEntry: NodeEntry<TTableCellElement>) => void;
//#endregion
//#region src/lib/merge/deleteRow.d.ts
declare const deleteTableMergeRow: (editor: SlateEditor) => void;
//#endregion
//#region src/lib/merge/deleteRowWhenExpanded.d.ts
declare const deleteRowWhenExpanded: (editor: SlateEditor, [table, tablePath]: NodeEntry<TTableCellElement>) => void;
//#endregion
//#region src/lib/merge/findCellByIndexes.d.ts
declare const findCellByIndexes: (editor: SlateEditor, table: TTableElement, searchRowIndex: number, searchColIndex: number) => TTableCellElement | undefined;
//#endregion
//#region src/lib/merge/getCellIndicesWithSpans.d.ts
declare const getCellIndicesWithSpans: ({
  col,
  row
}: {
  col: number;
  row: number;
}, endCell: TTableCellElement) => {
  col: number;
  row: number;
};
//#endregion
//#region src/lib/merge/getCellPath.d.ts
declare const getCellPath: (editor: SlateEditor, tableEntry: NodeEntry<TTableElement>, curRowIndex: number, curColIndex: number) => number[];
//#endregion
//#region src/lib/merge/getSelectionWidth.d.ts
declare const getSelectionWidth: <T extends [TTableCellElement, Path]>(cells: T[]) => number;
//#endregion
//#region src/lib/merge/getTableGridByRange.d.ts
type FormatType = 'all' | 'cell' | 'table';
type GetTableGridByRangeOptions$1<T extends FormatType> = {
  at: TRange;
  /**
   * Format of the output:
   *
   * - Table element
   * - Array of cells
   */
  format?: T;
};
type GetTableGridReturnType<T> = T extends 'all' ? TableGridEntries : ElementEntry[];
type TableGridEntries = {
  cellEntries: ElementEntry[];
  tableEntries: ElementEntry[];
};
/**
 * Get sub table between 2 cell paths. Ensure that the selection is always a
 * valid table grid.
 */
declare const getTableMergeGridByRange: <T extends FormatType>(editor: SlateEditor, {
  at,
  format
}: GetTableGridByRangeOptions$1<T>) => GetTableGridReturnType<T>;
//#endregion
//#region src/lib/merge/getTableMergedColumnCount.d.ts
declare const getTableMergedColumnCount: (tableNode: TElement) => number;
//#endregion
//#region src/lib/merge/insertTableColumn.d.ts
declare const insertTableMergeColumn: (editor: SlateEditor, {
  at,
  before,
  fromCell,
  header,
  select: shouldSelect
}?: {
  /** Exact path of the cell to insert the column at. Will overrule `fromCell`. */
  at?: Path;
  /** Insert the column before the current column instead of after */
  before?: boolean;
  /** Path of the cell to insert the column from. */
  fromCell?: Path;
  header?: boolean;
  select?: boolean;
}) => void;
//#endregion
//#region src/lib/merge/insertTableRow.d.ts
declare const insertTableMergeRow: (editor: SlateEditor, {
  at,
  before,
  fromRow,
  header,
  select: shouldSelect
}?: {
  /** Exact path of the row to insert the column at. Will overrule `fromRow`. */
  at?: Path;
  /** Insert the row before the current row instead of after */
  before?: boolean;
  fromRow?: Path;
  header?: boolean;
  select?: boolean;
}) => void;
//#endregion
//#region src/lib/merge/isTableRectangular.d.ts
/**
 * Checks if the given table is rectangular, meaning all rows have the same
 * effective number of cells, considering colspan and rowspan.
 */
declare const isTableRectangular: (table?: TTableElement) => boolean;
//#endregion
//#region src/lib/merge/mergeTableCells.d.ts
/** Merges multiple selected cells into one. */
declare const mergeTableCells: (editor: SlateEditor) => void;
//#endregion
//#region src/lib/merge/splitTableCell.d.ts
declare const splitTableCell: (editor: SlateEditor) => void;
//#endregion
//#region src/lib/queries/getAdjacentTableCell.d.ts
declare const getAdjacentTableCell: (editor: SlateEditor, {
  at,
  deltaCol,
  deltaRow
}?: {
  at?: Path;
  deltaCol?: number;
  deltaRow?: number;
}) => NodeEntry<TTableCellElement> | undefined;
//#endregion
//#region src/lib/queries/getCellInNextTableRow.d.ts
declare const getCellInNextTableRow: (editor: Editor, currentRowPath: Path) => NodeEntry | undefined;
//#endregion
//#region src/lib/queries/getCellInPreviousTableRow.d.ts
declare const getCellInPreviousTableRow: (editor: Editor, currentRowPath: Path) => NodeEntry | undefined;
//#endregion
//#region src/lib/queries/getColSpan.d.ts
/**
 * Returns the colspan attribute of the table cell element.
 *
 * @default 1 if undefined.
 */
declare const getColSpan: (cellElem: TTableCellElement) => number;
//#endregion
//#region src/lib/queries/getLeftTableCell.d.ts
declare const getLeftTableCell: (editor: SlateEditor, {
  at: cellPath
}?: {
  at?: Path;
}) => platejs56.NodeEntry<platejs56.TTableCellElement> | undefined;
//#endregion
//#region src/lib/queries/getNextTableCell.d.ts
declare const getNextTableCell: (editor: Editor, _currentCell: NodeEntry, currentPath: Path, currentRow: NodeEntry) => NodeEntry | undefined;
//#endregion
//#region src/lib/queries/getPreviousTableCell.d.ts
declare const getPreviousTableCell: (editor: Editor, _currentCell: NodeEntry, currentPath: Path, currentRow: NodeEntry) => NodeEntry | undefined;
//#endregion
//#region src/lib/queries/getRowSpan.d.ts
/**
 * Returns the rowspan attribute of the table cell element.
 *
 * @default 1 if undefined
 */
declare const getRowSpan: (cellElem: TTableCellElement) => number;
//#endregion
//#region src/lib/queries/getSelectedCells.d.ts
declare const getSelectedCellEntries: (editor: SlateEditor) => ElementEntry[];
declare const getSelectedCells: (editor: SlateEditor) => TElement[] | null;
declare const getSelectedCellIds: (editor: SlateEditor) => string[] | null;
declare const getSelectedTableIds: (editor: SlateEditor) => string[] | null;
declare const getSelectedCell: (editor: SlateEditor, id?: string | null) => TElement | null;
declare const getSelectedTables: (editor: SlateEditor) => TElement[] | null;
declare const isCellSelected: (editor: SlateEditor, id?: string | null) => boolean;
declare const isSelectingCell: (editor: SlateEditor) => boolean;
//#endregion
//#region src/lib/queries/getSelectedCellsBorders.d.ts
type GetSelectedCellsBordersOptions = {
  select?: {
    none?: boolean;
    outer?: boolean;
    side?: boolean;
  };
};
type TableBorderStates = {
  bottom: boolean;
  left: boolean;
  none: boolean;
  outer: boolean;
  right: boolean;
  top: boolean;
};
/**
 * Get all border states for the selected cells at once. Returns an object with
 * boolean flags for each border state:
 *
 * - Top/bottom/left/right: true if border is visible (size > 0)
 * - Outer: true if all outer borders are visible
 * - None: true if all borders are hidden (size === 0)
 */
declare const getSelectedCellsBorders: (editor: SlateEditor, selectedCells?: TElement[] | null, options?: GetSelectedCellsBordersOptions) => TableBorderStates;
/**
 * Tells if the entire selection is currently borderless (size=0 on all edges).
 * If **any** edge is > 0, returns false.
 */
declare function isSelectedCellBordersNone(editor: SlateEditor, cells: TTableCellElement[]): boolean;
/**
 * Tells if the bounding rectangle for the entire selection is fully set for the
 * **outer** edges, i.e. top/left/bottom/right edges have size=1. We ignore
 * internal edges, only bounding rectangle edges.
 */
declare function isSelectedCellBordersOuter(editor: SlateEditor, cells: TTableCellElement[]): boolean;
/**
 * Tells if the bounding rectangle for the entire selection is fully set for
 * that single side. Example: border='top' => if every cell that sits along the
 * top boundary has top=1.
 */
declare function isSelectedCellBorder(editor: SlateEditor, cells: TTableCellElement[], side: BorderDirection): boolean;
//#endregion
//#region src/lib/queries/getSelectedCellsBoundingBox.d.ts
/** Return bounding box [minRow..maxRow, minCol..maxCol] of all selected cells. */
declare function getSelectedCellsBoundingBox(editor: SlateEditor, cells: TTableCellElement[]): {
  maxCol: number;
  maxRow: number;
  minCol: number;
  minRow: number;
};
//#endregion
//#region src/lib/queries/getTableAbove.d.ts
declare const getTableAbove: (editor: SlateEditor, options?: EditorAboveOptions) => platejs56.NodeEntry<platejs56.TElement> | undefined;
//#endregion
//#region src/lib/queries/getTableCellBorders.d.ts
type BorderStylesDefault = {
  bottom: TTableCellBorder;
  right: TTableCellBorder;
  left?: TTableCellBorder;
  top?: TTableCellBorder;
};
declare const getTableCellBorders: (editor: SlateEditor, {
  cellIndices,
  defaultBorder,
  element
}: {
  element: TTableCellElement;
  cellIndices?: CellIndices;
  defaultBorder?: TTableCellBorder;
}) => BorderStylesDefault;
//#endregion
//#region src/lib/queries/getTableCellSize.d.ts
/** Get the width of a cell with colSpan support. */
declare const getTableCellSize: (editor: SlateEditor, {
  cellIndices,
  colSizes,
  element,
  rowSize
}: {
  element: TTableCellElement;
  cellIndices?: CellIndices;
  colSizes?: number[];
  rowSize?: number;
}) => {
  minHeight: number;
  width: number;
};
//#endregion
//#region src/lib/queries/getTableColumnCount.d.ts
declare const getTableColumnCount: (tableNode: TElement) => number;
//#endregion
//#region src/lib/queries/getTableColumnIndex.d.ts
/** Get table column index of a cell node. */
declare const getTableColumnIndex: (editor: Editor, cellNode: TElement) => number;
//#endregion
//#region src/lib/queries/getTableEntries.d.ts
/**
 * If at (default = selection) is in table>tr>td|th, return table, row, and cell
 * node entries.
 */
declare const getTableEntries: (editor: SlateEditor, {
  at
}?: {
  at?: TLocation | null;
}) => {
  cell: platejs56.NodeEntry<platejs56.TElement | platejs56.TText>;
  row: platejs56.NodeEntry<platejs56.TElement | platejs56.Editor<platejs56.Value>>;
  table: platejs56.NodeEntry<platejs56.TElement | platejs56.Editor<platejs56.Value>>;
} | undefined;
//#endregion
//#region src/lib/queries/getTableGridByRange.d.ts
type GetTableGridByRangeOptions = {
  at: TRange;
  /**
   * Format of the output:
   *
   * - Table element
   * - Array of cells
   */
  format?: 'cell' | 'table';
};
/** Get sub table between 2 cell paths. */
declare const getTableGridByRange: (editor: SlateEditor, {
  at,
  format
}: GetTableGridByRangeOptions) => ElementEntry[];
//#endregion
//#region src/lib/queries/getTableGridAbove.d.ts
type GetTableGridAboveOptions = EditorAboveOptions & Pick<GetTableGridByRangeOptions, 'format'>;
/** Get sub table above anchor and focus. Format: tables or cells. */
declare const getTableGridAbove: (editor: SlateEditor, {
  format,
  ...options
}?: GetTableGridAboveOptions) => ElementEntry[];
//#endregion
//#region src/lib/queries/getTableOverriddenColSizes.d.ts
/**
 * Returns node.colSizes if it exists, applying overrides, otherwise returns a
 * 0-filled array.
 */
declare const getTableOverriddenColSizes: (tableNode: TTableElement, colSizeOverrides?: TableStoreSizeOverrides) => number[];
//#endregion
//#region src/lib/queries/getTableRowIndex.d.ts
/** Get table row index of a cell node. */
declare const getTableRowIndex: (editor: Editor, cellNode: TElement) => number;
//#endregion
//#region src/lib/queries/getTopTableCell.d.ts
declare const getTopTableCell: (editor: SlateEditor, {
  at: cellPath
}?: {
  at?: Path;
}) => platejs56.NodeEntry<platejs56.TTableCellElement> | undefined;
//#endregion
//#region src/lib/queries/isTableBorderHidden.d.ts
declare const isTableBorderHidden: (editor: SlateEditor, border: BorderDirection) => boolean;
//#endregion
//#region src/lib/transforms/deleteColumn.d.ts
declare const deleteColumn: (editor: SlateEditor) => void;
//#endregion
//#region src/lib/transforms/deleteRow.d.ts
declare const deleteRow: (editor: SlateEditor) => void;
//#endregion
//#region src/lib/transforms/deleteTable.d.ts
declare const deleteTable: (editor: SlateEditor) => void;
//#endregion
//#region src/lib/transforms/insertTable.d.ts
/**
 * Insert table. If selection in table and no 'at' specified, insert after
 * current table. Select start of new table.
 */
declare const insertTable: (editor: SlateEditor, {
  colCount,
  header,
  rowCount
}?: GetEmptyTableNodeOptions, {
  select: shouldSelect,
  ...options
}?: InsertNodesOptions) => void;
//#endregion
//#region src/lib/transforms/insertTableColumn.d.ts
declare const insertTableColumn: (editor: SlateEditor, options?: {
  /** Exact path of the cell to insert the column at. Will overrule `fromCell`. */
  at?: Path;
  /** Insert the column before the current column instead of after */
  before?: boolean;
  /** Path of the cell to insert the column from. */
  fromCell?: Path;
  header?: boolean;
  select?: boolean;
}) => void;
//#endregion
//#region src/lib/transforms/insertTableRow.d.ts
declare const insertTableRow: (editor: SlateEditor, options?: {
  /**
   * Exact path of the row to insert the column at. Pass the table path to
   * insert at the end of the table. Will overrule `fromRow`.
   */
  at?: Path;
  /** Insert the row before the current row instead of after */
  before?: boolean;
  fromRow?: Path;
  header?: boolean;
  select?: boolean;
}) => void;
//#endregion
//#region src/lib/transforms/moveSelectionFromCell.d.ts
/** Move selection by cell unit. */
declare const moveSelectionFromCell: (editor: SlateEditor, {
  at,
  edge,
  fromOneCell,
  reverse
}?: {
  at?: TLocation;
  /** Expand cell selection to an edge. */
  edge?: "bottom" | "left" | "right" | "top";
  /** Move selection from one selected cell */
  fromOneCell?: boolean;
  /** False: move selection to cell below true: move selection to cell above */
  reverse?: boolean;
}) => true | undefined;
//#endregion
//#region src/lib/transforms/setBorderSize.d.ts
declare const setBorderSize: (editor: SlateEditor, size: number, {
  at,
  border
}?: {
  at?: Path;
  border?: BorderDirection | "all";
}) => void;
//#endregion
//#region src/lib/transforms/setCellBackground.d.ts
declare const setCellBackground: (editor: SlateEditor, options: {
  color: string | null;
  selectedCells?: TElement[];
}) => void;
//#endregion
//#region src/lib/transforms/setTableColSize.d.ts
declare const setTableColSize: (editor: SlateEditor, {
  colIndex,
  width
}: {
  colIndex: number;
  width: number;
}, options?: EditorAboveOptions) => void;
//#endregion
//#region src/lib/transforms/setTableMarginLeft.d.ts
declare const setTableMarginLeft: (editor: SlateEditor, {
  marginLeft
}: {
  marginLeft: number;
}, options?: EditorAboveOptions) => void;
//#endregion
//#region src/lib/transforms/setTableRowSize.d.ts
declare const setTableRowSize: (editor: SlateEditor, {
  height,
  rowIndex
}: {
  height: number;
  rowIndex: number;
}, options?: EditorAboveOptions) => void;
//#endregion
//#region src/lib/transforms/shouldMoveSelectionFromCell.d.ts
type TableMoveSelectionContext = {
  blockPath: number[];
  cellPath: number[];
  point: {
    offset: number;
    path: number[];
  };
};
declare const getTableMoveSelectionContext: (editor: SlateEditor, point?: platejs56.Point | undefined) => TableMoveSelectionContext | undefined;
declare const hasAdjacentBlockInCell: (editor: SlateEditor, {
  blockPath,
  cellPath,
  reverse
}: Pick<TableMoveSelectionContext, "blockPath" | "cellPath"> & {
  reverse: boolean;
}) => boolean;
declare const shouldMoveSelectionFromCell: (editor: SlateEditor, {
  blockPath,
  point,
  reverse
}: {
  blockPath: number[];
  point: {
    offset: number;
    path: number[];
  };
  reverse: boolean;
}) => boolean;
//#endregion
//#region src/lib/BaseTablePlugin.d.ts
declare const BaseTableRowPlugin: platejs56.SlatePlugin<PluginConfig<"tr", {}, {}, {}, {}>>;
declare const BaseTableCellPlugin: platejs56.SlatePlugin<PluginConfig<"td", {}, {}, {}, {}>>;
declare const BaseTableCellHeaderPlugin: platejs56.SlatePlugin<PluginConfig<"th", {}, {}, {}, {}>>;
type TableConfig = PluginConfig<'table', {
  /** @private Keeps Track of cell indices by id. */
  _cellIndices: Record<string, {
    col: number;
    row: number;
  }>;
  /** @private Keeps track of selected cell ids for cheap membership checks. */
  _selectedCellIds: string[] | null | undefined;
  /** @private Keeps track of selected table ids for cheap table checks. */
  _selectedTableIds: string[] | null | undefined;
  /** @private Forces selection-derived selectors to refresh. */
  _selectionVersion: number;
  /** Legacy selector key. Selected cells are derived from editor selection. */
  selectedCells: TElement[] | null;
  /** Legacy selector key. Selected tables are derived from editor selection. */
  selectedTables: TElement[] | null;
  /** Disable expanding the table when inserting cells. */
  disableExpandOnInsert?: boolean;
  disableMarginLeft?: boolean;
  /**
   * Disable cell merging functionality.
   *
   * @default false
   */
  disableMerge?: boolean;
  /**
   * Disable unsetting the first column width when the table has one column.
   * Set it to true if you want to resize the table width when there is only
   * one column. Keep it false if you have a full-width table.
   */
  enableUnsetSingleColSize?: boolean;
  /**
   * If defined, a normalizer will set each undefined table `colSizes` to this
   * value divided by the number of columns. Merged cells not supported.
   */
  initialTableWidth?: number;
  /**
   * The minimum width of a column.
   *
   * @default 48
   */
  minColumnWidth?: number;
}, {
  create: {
    table: OmitFirst<typeof getEmptyTableNode>;
    /** Cell node factory used each time a cell is created. */
    tableCell: OmitFirst<typeof getEmptyCellNode>;
    tableRow: OmitFirst<typeof getEmptyRowNode>;
  };
  table: {
    getCellBorders: OmitFirst<typeof getTableCellBorders>;
    getCellSize: OmitFirst<typeof getTableCellSize>;
    getSelectedCell: OmitFirst<typeof getSelectedCell>;
    getSelectedCellIds: OmitFirst<typeof getSelectedCellIds>;
    getSelectedCells: OmitFirst<typeof getSelectedCells>;
    getSelectedTableIds: OmitFirst<typeof getSelectedTableIds>;
    getSelectedTables: OmitFirst<typeof getSelectedTables>;
    getColSpan: typeof getColSpan;
    getRowSpan: typeof getRowSpan;
    getCellChildren: (cell: TTableCellElement) => Descendant[];
    isCellSelected: OmitFirst<typeof isCellSelected>;
    isSelectingCell: OmitFirst<typeof isSelectingCell>;
  };
}, {
  insert: {
    table: OmitFirst<typeof insertTable>;
    tableColumn: OmitFirst<typeof insertTableColumn>;
    tableRow: OmitFirst<typeof insertTableRow>;
  };
  remove: {
    table: OmitFirst<typeof deleteTable>;
    tableColumn: OmitFirst<typeof deleteColumn>;
    tableRow: OmitFirst<typeof deleteRow>;
  };
  table: {
    merge: OmitFirst<typeof mergeTableCells>;
    split: OmitFirst<typeof splitTableCell>;
  };
}, {
  cellIndices?: (id: string) => CellIndices;
  isCellSelected?: (id?: string | null) => boolean;
  isSelectingCell?: () => boolean;
  selectedCell?: (id?: string | null) => TElement | null;
  selectedCellIds?: () => string[] | null;
  selectedCells?: () => TElement[] | null;
  selectedTableIds?: () => string[] | null;
  selectedTables?: () => TElement[] | null;
}>;
/** Enables support for tables. */
declare const BaseTablePlugin: platejs56.SlatePlugin<PluginConfig<"table", {
  /** @private Keeps Track of cell indices by id. */
  _cellIndices: Record<string, {
    col: number;
    row: number;
  }>;
  /** @private Keeps track of selected cell ids for cheap membership checks. */
  _selectedCellIds: string[] | null | undefined;
  /** @private Keeps track of selected table ids for cheap table checks. */
  _selectedTableIds: string[] | null | undefined;
  /** @private Forces selection-derived selectors to refresh. */
  _selectionVersion: number;
  /** Legacy selector key. Selected cells are derived from editor selection. */
  selectedCells: TElement[] | null;
  /** Legacy selector key. Selected tables are derived from editor selection. */
  selectedTables: TElement[] | null;
  /** Disable expanding the table when inserting cells. */
  disableExpandOnInsert?: boolean;
  disableMarginLeft?: boolean;
  /**
   * Disable cell merging functionality.
   *
   * @default false
   */
  disableMerge?: boolean;
  /**
   * Disable unsetting the first column width when the table has one column.
   * Set it to true if you want to resize the table width when there is only
   * one column. Keep it false if you have a full-width table.
   */
  enableUnsetSingleColSize?: boolean;
  /**
   * If defined, a normalizer will set each undefined table `colSizes` to this
   * value divided by the number of columns. Merged cells not supported.
   */
  initialTableWidth?: number;
  /**
   * The minimum width of a column.
   *
   * @default 48
   */
  minColumnWidth?: number;
}, {
  create: {
    table: OmitFirst<typeof getEmptyTableNode>;
    tableCell: OmitFirst<typeof getEmptyCellNode>;
    tableRow: OmitFirst<typeof getEmptyRowNode>;
  };
  table: {
    getCellBorders: OmitFirst<typeof getTableCellBorders>;
    getCellSize: OmitFirst<typeof getTableCellSize>;
    getSelectedCell: OmitFirst<typeof getSelectedCell>;
    getSelectedCellIds: OmitFirst<typeof getSelectedCellIds>;
    getSelectedCells: OmitFirst<typeof getSelectedCells>;
    getSelectedTableIds: OmitFirst<typeof getSelectedTableIds>;
    getSelectedTables: OmitFirst<typeof getSelectedTables>;
    getColSpan: typeof getColSpan;
    getRowSpan: typeof getRowSpan;
    getCellChildren: (cell: TTableCellElement) => Descendant[];
    isCellSelected: OmitFirst<typeof isCellSelected>;
    isSelectingCell: OmitFirst<typeof isSelectingCell>;
  };
}, {
  insert: {
    table: OmitFirst<typeof insertTable>;
    tableColumn: OmitFirst<typeof insertTableColumn>;
    tableRow: OmitFirst<typeof insertTableRow>;
  };
  remove: {
    table: OmitFirst<typeof deleteTable>;
    tableColumn: OmitFirst<typeof deleteColumn>;
    tableRow: OmitFirst<typeof deleteRow>;
  };
  table: {
    merge: OmitFirst<typeof mergeTableCells>;
    split: OmitFirst<typeof splitTableCell>;
  };
}, {
  cellIndices?: (id: string) => CellIndices;
  isCellSelected?: (id?: string | null) => boolean;
  isSelectingCell?: () => boolean;
  selectedCell?: (id?: string | null) => TElement | null;
  selectedCellIds?: () => string[] | null;
  selectedCells?: () => TElement[] | null;
  selectedTableIds?: () => string[] | null;
  selectedTables?: () => TElement[] | null;
}>>;
//#endregion
//#region src/lib/constants.d.ts
declare const KEY_SHIFT_EDGES: {
  'shift+down': string;
  'shift+left': string;
  'shift+right': string;
  'shift+up': string;
};
//#endregion
//#region src/lib/normalizeInitialValueTable.d.ts
declare const normalizeInitialValueTable: TransformInitialValue<TableConfig>;
//#endregion
//#region src/lib/withApplyTable.d.ts
/**
 * Selection table:
 *
 * - If anchor is in table, focus in a block before: set focus to start of table
 * - If anchor is in table, focus in a block after: set focus to end of table
 * - If focus is in table, anchor in a block before: set focus to end of table
 * - If focus is in table, anchor in a block after: set focus to the point before
 *   start of table
 */
declare const withApplyTable: OverrideEditor<TableConfig>;
//#endregion
//#region src/lib/withDeleteTable.d.ts
/**
 * Return true if:
 *
 * - At start/end of a cell.
 * - Next to a table cell. Move selection to the table cell.
 */
declare const preventDeleteTableCell: (editor: SlateEditor, {
  reverse,
  unit
}: {
  reverse?: boolean;
  unit?: "block" | "character" | "line" | "word";
}) => true | undefined;
/** Prevent cell deletion. */
declare const withDeleteTable: OverrideEditor<TableConfig>;
//#endregion
//#region src/lib/withGetFragmentTable.d.ts
/** If selection is in a table, get subtable above. */
declare const withGetFragmentTable: OverrideEditor<TableConfig>;
//#endregion
//#region src/lib/withInsertFragmentTable.d.ts
/**
 * If inserting a table, If block above anchor is a table,
 *
 * - Replace each cell above by the inserted table until out of bounds.
 * - Select the inserted cells.
 */
declare const withInsertFragmentTable: OverrideEditor<TableConfig>;
//#endregion
//#region src/lib/withInsertTextTable.d.ts
declare const withInsertTextTable: OverrideEditor<TableConfig>;
//#endregion
//#region src/lib/withNormalizeTable.d.ts
/**
 * Normalize table:
 *
 * - Wrap cell children in a paragraph if they are texts.
 */
declare const withNormalizeTable: OverrideEditor<TableConfig>;
//#endregion
//#region src/lib/withSetFragmentDataTable.d.ts
declare const withSetFragmentDataTable: OverrideEditor<TableConfig>;
//#endregion
//#region src/lib/withTable.d.ts
declare const withTable: OverrideEditor<TableConfig>;
//#endregion
//#region src/lib/withTableCellSelection.d.ts
declare const withTableCellSelection: OverrideEditor<TableConfig>;
//#endregion
export { isSelectedCellBorder as $, insertTable as A, deleteTableMergeRow as At, GetTableGridByRangeOptions as B, TableStoreSizeOverrides as Bt, setTableMarginLeft as C, getTableMergedColumnCount as Ct, moveSelectionFromCell as D, getCellIndicesWithSpans as Dt, setBorderSize as E, getCellPath as Et, getTopTableCell as F, GetEmptyRowNodeOptions as Ft, getTableCellSize as G, computeCellIndices as Gt, getTableEntries as H, getCellRowIndexByPath as Ht, getTableRowIndex as I, getEmptyRowNode as It, getTableAbove as J, BorderStylesDefault as K, getTableOverriddenColSizes as L, getEmptyCellNode as Lt, deleteRow as M, deleteTableMergeColumn as Mt, deleteColumn as N, GetEmptyTableNodeOptions as Nt, insertTableRow as O, findCellByIndexes as Ot, isTableBorderHidden as P, getEmptyTableNode as Pt, getSelectedCellsBorders as Q, GetTableGridAboveOptions as R, BorderDirection as Rt, setTableRowSize as S, insertTableMergeColumn as St, setCellBackground as T, getSelectionWidth as Tt, getTableColumnIndex as U, CellIndices as Ut, getTableGridByRange as V, getCellTypes as Vt, getTableColumnCount as W, getCellIndices as Wt, GetSelectedCellsBordersOptions as X, getSelectedCellsBoundingBox as Y, TableBorderStates as Z, TableConfig as _, getAdjacentTableCell as _t, withInsertTextTable as a, getSelectedCells as at, hasAdjacentBlockInCell as b, isTableRectangular as bt, preventDeleteTableCell as c, isCellSelected as ct, normalizeInitialValueTable as d, getPreviousTableCell as dt, isSelectedCellBordersNone as et, KEY_SHIFT_EDGES as f, getNextTableCell as ft, BaseTableRowPlugin as g, getCellInNextTableRow as gt, BaseTablePlugin as h, getCellInPreviousTableRow as ht, withNormalizeTable as i, getSelectedCellIds as it, deleteTable as j, deleteColumnWhenExpanded as jt, insertTableColumn as k, deleteRowWhenExpanded as kt, withDeleteTable as l, isSelectingCell as lt, BaseTableCellPlugin as m, getColSpan as mt, withTable as n, getSelectedCell as nt, withInsertFragmentTable as o, getSelectedTableIds as ot, BaseTableCellHeaderPlugin as p, getLeftTableCell as pt, getTableCellBorders as q, withSetFragmentDataTable as r, getSelectedCellEntries as rt, withGetFragmentTable as s, getSelectedTables as st, withTableCellSelection as t, isSelectedCellBordersOuter as tt, withApplyTable as u, getRowSpan as ut, TableMoveSelectionContext as v, splitTableCell as vt, setTableColSize as w, getTableMergeGridByRange as wt, shouldMoveSelectionFromCell as x, insertTableMergeRow as xt, getTableMoveSelectionContext as y, mergeTableCells as yt, getTableGridAbove as z, CreateCellOptions as zt };