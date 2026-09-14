import { Descendant, EditorApi, OverrideEditor, TElement } from "platejs";

//#region src/lib/types.d.ts
type DiffDeletion = {
  type: 'delete';
};
type DiffInsertion = {
  type: 'insert';
};
type DiffOperation = DiffDeletion | DiffInsertion | DiffUpdate;
type DiffProps = {
  diff: true;
  diffOperation: DiffOperation;
};
type DiffUpdate = {
  newProperties: Record<string, any>;
  properties: Record<string, any>;
  type: 'update';
};
//#endregion
//#region src/lib/computeDiff.d.ts
type ComputeDiffOptions = {
  isInline: EditorApi['isInline'];
  getDeleteProps: (node: Descendant) => any;
  getInsertProps: (node: Descendant) => any;
  getUpdateProps: (node: Descendant, properties: any, newProperties: any) => any;
  ignoreProps?: string[];
  lineBreakChar?: string;
  elementsAreRelated?: (element: TElement, nextElement: TElement) => boolean | null;
};
declare const computeDiff: (doc0: Descendant[], doc1: Descendant[], {
  elementsAreRelated,
  getDeleteProps,
  getInsertProps,
  getUpdateProps,
  ignoreProps,
  isInline,
  ...options
}?: Partial<ComputeDiffOptions>) => Descendant[];
declare const defaultGetInsertProps: () => DiffProps;
declare const defaultGetDeleteProps: () => DiffProps;
declare const defaultGetUpdateProps: (_node: Descendant, properties: any, newProperties: any) => DiffProps;
//#endregion
//#region src/lib/withGetFragmentExcludeDiff.d.ts
declare const withGetFragmentExcludeDiff: OverrideEditor;
//#endregion
export { ComputeDiffOptions, DiffDeletion, DiffInsertion, DiffOperation, DiffProps, DiffUpdate, computeDiff, defaultGetDeleteProps, defaultGetInsertProps, defaultGetUpdateProps, withGetFragmentExcludeDiff };