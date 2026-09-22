import { Ct as NodeComponents, Et as PluginConfig, F as RenderLeafProps, I as RenderElementFn, Ii as ExtendEditor$1, J as BaseEditor, Jr as NavigationFeedbackConfig, L as RenderElementProps, M as RenderTextFn, Mi as AnySlatePlugin, Mo as HandlerReturnType, N as RenderTextProps, Ot as WithAnyKey, P as RenderLeafFn, Pa as ResolvedInputRulesMeta, Q as SlateEditor, Qa as createStaticEditor, R as RenderChunkFn, So as PlateStaticProps, St as NodeComponent, Tt as ParserOptions, U as BaseWithSlateOptions, Y as InferPlugins, _t as InferOptions, ai as WithAutoScrollOptions, at as BasePluginContext, ba as InputRulesConfig, bt as MatchRules, ct as BaseTransformOptions, et as AnyPluginConfig, fi as LiftBlockOptions, gi as InitOptions, gt as InferKey, hr as CorePluginTransforms, ht as InferApi, ia as SlatePluginContext, ii as ScrollMode, it as BasePlugin, j as EditableProps, kt as WithRequiredKey, mi as InsertExitBreakOptions, mr as CorePluginApi, mt as GetInjectNodePropsReturnType, na as SlatePlugin, nt as BaseHtmlDeserializer, pr as CorePlugin, pt as GetInjectNodePropsOptions, qr as NavigationFeedbackActiveTarget, ra as SlatePluginConfig, ri as DomConfig, rt as BaseInjectProps, st as BaseSerializer, ti as AutoScrollOperationsMap, tt as BaseDeserializer, vt as InferSelectors, xa as InputRulesDefinition, yt as InferTransforms, z as RenderChunkProps } from "../index-B7ej2XCF";
import * as _platejs_slate20 from "@platejs/slate";
import { DecoratedRange, Descendant, DescendantIn, Editor, EditorApi, EditorTransforms, ElementEntry, NodeEntry, NodeOperation, Operation, Path, TElement, TNode, TRange, TSelection, TText, TextOperation, Value, ValueOf } from "@platejs/slate";
import { AnyObject, Deep2Partial, Modify, Nullable, UnionToIntersection, UnknownObject } from "@udecode/utils";
import { DefaultPlaceholder, Editable, RenderPlaceholderProps, Slate, useComposing, useFocused, useReadOnly, useSelected, useSlateStatic, withReact } from "slate-react";
import React$1, { DependencyList, HTMLAttributes } from "react";
import { HotkeysEvent, HotkeysOptions, Keys } from "@udecode/react-hotkeys";
import * as jotai0 from "jotai";
import { Atom, atom } from "jotai";
import * as jotai_x0 from "jotai-x";
import { JotaiStore, createAtomStore, useStoreAtomState, useStoreAtomValue, useStoreSetAtom } from "jotai-x";
import * as zustand_x0 from "zustand-x";
import { TCreatedStoreType, TEqualityChecker, createZustandStore, useStoreSelect, useStoreState, useStoreValue, useTracked, useTrackedStore } from "zustand-x";
import { createStore } from "jotai/vanilla";

//#region src/react/plugins/SlateReactExtensionPlugin.d.ts
declare const SlateReactExtensionPlugin: PlatePlugin<PluginConfig<"slateExtension", {
  onNodeChange: (options: {
    editor: SlateEditor;
    node: _platejs_slate20.Descendant;
    operation: _platejs_slate20.NodeOperation;
    prevNode: _platejs_slate20.Descendant;
  }) => void;
  onTextChange: (options: {
    editor: SlateEditor;
    node: _platejs_slate20.Descendant;
    operation: _platejs_slate20.TextOperation;
    prevText: string;
    text: string;
  }) => void;
}, {
  redecorate: (() => void) & (() => void);
  isElementStateEmpty: (element: _platejs_slate20.TElement) => boolean;
}, {
  reset: (options: _platejs_slate20.ResetOptions | undefined) => void;
  init: ((args_0: InitOptions) => void) & ((args_0: InitOptions) => void);
  insertExitBreak: ((args_0?: InsertExitBreakOptions | undefined) => true | undefined) & ((args_0?: InsertExitBreakOptions | undefined) => true | undefined);
  liftBlock: ((args_0?: LiftBlockOptions | undefined) => true | undefined) & ((args_0?: LiftBlockOptions | undefined) => true | undefined);
  resetBlock: ((args_0?: {
    at?: _platejs_slate20.Path;
  } | undefined) => true | undefined) & ((args_0?: {
    at?: _platejs_slate20.Path;
  } | undefined) => true | undefined);
  setValue: ((value?: string | _platejs_slate20.Value | undefined) => void) & ((value?: string | _platejs_slate20.Value | undefined) => void);
  apply: <N$1 extends _platejs_slate20.TElement | _platejs_slate20.TText>(operation: _platejs_slate20.Operation<N$1>) => void;
}, {}>>;
//#endregion
//#region src/react/plugins/event-editor/EventEditorPlugin.d.ts
declare const EventEditorPlugin: PlatePlugin<PluginConfig<"eventEditor", {}, {}, {}, {}>>;
//#endregion
//#region src/react/plugins/event-editor/EventEditorStore.d.ts
type EventEditorState = {
  /** Last editor id that has been blurred. */
  blur: string | null;
  /** Editor id that is currently being focused. */
  focus: string | null;
  /** Last editor id. */
  last: string | null;
};
/** Store where the keys are event names and the values are editor ids. */
declare const EventEditorStore: zustand_x0.TStateApi<EventEditorState, [["zustand/mutative-x", never]], {}, {}>;
declare const useEventEditorValue: {
  <K$1 extends keyof EventEditorState>(key: K$1): EventEditorState[K$1];
  <K$1 extends never>(key: K$1, ...args: Parameters<{}[K$1]>): ReturnType<{}[K$1]>;
  (key: "state"): EventEditorState;
  <K$1 extends keyof EventEditorState>(key: K$1, equalityFn?: zustand_x0.TEqualityChecker<EventEditorState[K$1]> | undefined): EventEditorState[K$1];
  <K$1 extends never>(key: K$1, ...args: [...Parameters<{}[K$1]>, (zustand_x0.TEqualityChecker<ReturnType<{}[K$1]>> | undefined)?]): ReturnType<{}[K$1]>;
};
//#endregion
//#region src/react/plugins/event-editor/getEventPlateId.d.ts
declare const getEventPlateId: (id?: string) => string;
//#endregion
//#region src/react/plugins/event-editor/useFocusEditorEvents.d.ts
declare const FOCUS_EDITOR_EVENT = "focus-editor-event";
declare const BLUR_EDITOR_EVENT = "blur-editor-event";
declare const useFocusEditorEvents: ({
  editorRef,
  onEditorBlur,
  onEditorFocus
}: {
  editorRef: PlateEditor | null;
  onEditorBlur?: () => void;
  onEditorFocus?: () => void;
}) => void;
//#endregion
//#region src/react/plugins/event-editor/useFocusedLast.d.ts
/** Whether the current editor is the last focused editor. */
declare const useFocusedLast: (id?: string) => boolean;
//#endregion
//#region src/react/plugins/navigation-feedback/NavigationFeedbackPlugin.d.ts
declare const NavigationFeedbackPlugin: PlatePlugin<PluginConfig<any, {}, {}, {}, {}>>;
//#endregion
//#region src/react/plugins/navigation-feedback/useNavigationHighlight.d.ts
type NavigationHighlightTarget = Path | TElement | TText | null | undefined;
declare const useNavigationHighlight: (target?: NavigationHighlightTarget) => NavigationFeedbackActiveTarget | null;
//#endregion
//#region src/react/plugins/paragraph/ParagraphPlugin.d.ts
declare const ParagraphPlugin: PlatePlugin<PluginConfig<"p", {}, {}, {}, {}>>;
//#endregion
//#region src/react/plugins/react/ReactPlugin.d.ts
/** @see {@link withReact} */
declare const ReactPlugin: PlatePlugin<PluginConfig<"dom", {
  scrollMode?: ScrollMode;
  scrollOperations?: AutoScrollOperationsMap;
  scrollOptions?: _platejs_slate20.ScrollIntoViewOptions;
}, {
  isScrolling: () => boolean;
}, {
  withScrolling: (fn: () => void, options?: WithAutoScrollOptions | undefined) => void;
}, {}>>;
//#endregion
//#region src/react/plugins/react/withPlateReact.d.ts
declare const withPlateReact: ExtendEditor$1<DomConfig>;
//#endregion
//#region src/react/editor/withPlate.d.ts
type PlateCorePlugin = CorePlugin | typeof EventEditorPlugin | typeof SlateReactExtensionPlugin;
type WithPlateOptions<V$1 extends Value = Value, P$1 extends AnyPluginConfig = PlateCorePlugin> = BaseWithSlateOptions<P$1> & Pick<Partial<AnyPlatePlugin>, 'api' | 'decorate' | 'extendEditor' | 'handlers' | 'inject' | 'transformInitialValue' | 'normalizeInitialValue' | 'options' | 'override' | 'priority' | 'render' | 'shortcuts' | 'transforms' | 'useHooks'> & {
  value?: ((editor: PlateEditor) => Promise<V$1> | V$1) | V$1 | string;
  rootPlugin?: (plugin: AnyPlatePlugin) => AnyPlatePlugin;
  onReady?: (ctx: {
    editor: PlateEditor;
    isAsync: boolean;
    value: V$1;
  }) => void;
};
/**
 * Applies Plate enhancements to an editor instance (React version).
 *
 * @remarks
 *   This function supports React-specific features including component rendering,
 *   event handlers, and React hooks integration.
 * @see {@link createPlateEditor} for a higher-level React editor creation function.
 * @see {@link usePlateEditor} for a memoized version in React components.
 * @see {@link withSlate} for the non-React version of editor enhancement.
 */
declare const withPlate: <V$1 extends Value = Value, P$1 extends AnyPluginConfig = PlateCorePlugin>(e: Editor, options?: WithPlateOptions<V$1, P$1>) => TPlateEditor<V$1, InferPlugins<P$1[]>>;
type CreatePlateEditorOptions<V$1 extends Value = Value, P$1 extends AnyPluginConfig = PlateCorePlugin> = WithPlateOptions<V$1, P$1> & {
  /**
   * Initial editor to be extended with `withPlate`.
   *
   * @default createEditor()
   */
  editor?: Editor;
};
/**
 * Creates a Plate editor (React version).
 *
 * This function creates a fully configured Plate editor instance with
 * React-specific enhancements including component rendering, event handlers,
 * and hooks integration. It applies all specified plugins and configurations to
 * create a functional editor.
 *
 * Examples:
 *
 * ```ts
 * const editor = createPlateEditor({
 *   plugins: [ParagraphPlugin, HeadingPlugin],
 *   value: [{ type: 'p', children: [{ text: 'Hello world!' }] }],
 * });
 *
 * // Editor with custom components
 * const editor = createPlateEditor({
 *   plugins: [ParagraphPlugin.withComponent(ParagraphElement)],
 *   components: { [CodePlugin.key]: CodeLeaf },
 * });
 *
 * // Editor with React-specific options
 * const editor = createPlateEditor({
 *   plugins: [ParagraphPlugin],
 *   handlers: { onKeyDown: customKeyHandler },
 * });
 * ```
 *
 * @see {@link createSlateEditor} for a non-React version of editor creation.
 * @see {@link usePlateEditor} for a memoized version in React components.
 * @see {@link withPlate} for the underlying function that applies Plate enhancements to an editor.
 */
declare const createPlateEditor: <V$1 extends Value = Value, P$1 extends AnyPluginConfig = PlateCorePlugin>({
  editor,
  ...options
}?: CreatePlateEditorOptions<V$1, P$1>) => TPlateEditor<V$1, InferPlugins<P$1[]>>;
//#endregion
//#region src/react/editor/PlateEditor.d.ts
type PlateEditor = BaseEditor & {
  api: EditorApi & UnionToIntersection<InferApi<PlateCorePlugin>>;
  meta: BaseEditor['meta'] & {
    inputRules: ResolvedInputRulesMeta;
    pluginList: AnyEditorPlatePlugin[];
    shortcuts: Shortcuts;
  };
  plugins: Record<string, AnyEditorPlatePlugin>;
  tf: EditorTransforms & UnionToIntersection<InferTransforms<PlateCorePlugin>>;
  transforms: EditorTransforms & UnionToIntersection<InferTransforms<PlateCorePlugin>>;
  getApi: <C extends AnyPluginConfig = PluginConfig>(plugin?: WithRequiredKey<C>) => PlateEditor['api'] & InferApi<C>;
  getPlugin: <C extends AnyPluginConfig = PluginConfig>(plugin: WithRequiredKey<C>) => C extends {
    node: any;
  } ? C : EditorPlatePlugin<C>;
  getTransforms: <C extends AnyPluginConfig = PluginConfig>(plugin?: WithRequiredKey<C>) => PlateEditor['tf'] & InferTransforms<C>;
  uid?: string;
};
type FilterKeys<T, K$1 extends keyof T> = { [P in keyof T as Exclude<P, K$1>]: T[P] };
type TPlateEditor<V$1 extends Value = Value, P$1 extends AnyPluginConfig = PlateCorePlugin> = FilterKeys<PlateEditor, 'children' | 'operations'> & {
  api: EditorApi<V$1> & UnionToIntersection<InferApi<P$1 | PlateCorePlugin>>;
  children: V$1;
  meta: BaseEditor['meta'] & {
    inputRules: ResolvedInputRulesMeta;
    pluginList: P$1[];
    shortcuts: Shortcuts;
  };
  operations: Operation<DescendantIn<V$1>>[];
  plugins: { [K in P$1['key']]: Extract<P$1, {
    key: K;
  }> };
  tf: EditorTransforms<V$1> & UnionToIntersection<InferTransforms<P$1 | PlateCorePlugin>>;
  transforms: EditorTransforms<V$1> & UnionToIntersection<InferTransforms<P$1 | PlateCorePlugin>>;
  getApi: <C extends AnyPluginConfig = PluginConfig>(plugin?: WithRequiredKey<C>) => TPlateEditor<V$1>['api'] & InferApi<C>;
  getTransforms: <C extends AnyPluginConfig = PluginConfig>(plugin?: WithRequiredKey<C>) => TPlateEditor<V$1>['tf'] & InferTransforms<C>;
};
type KeyofPlugins<T extends AnyPluginConfig> = (string & {}) | InferKey<PlateCorePlugin | T>;
//#endregion
//#region src/react/plugin/PlatePlugin.d.ts
type AnyEditorPlatePlugin = EditorPlatePlugin<AnyPluginConfig>;
type AnyPlatePlugin = PlatePlugin<AnyPluginConfig>;
/**
 * Property used by Plate to decorate editor ranges. If the function returns
 * undefined then no ranges are modified. If the function returns an array the
 * returned ranges are merged with the ranges called by other plugins.
 */
type Decorate<C extends AnyPluginConfig = PluginConfig> = (ctx: PlatePluginContext<C> & {
  entry: NodeEntry;
}) => DecoratedRange[] | undefined;
type Deserializer<C extends AnyPluginConfig = PluginConfig> = BaseDeserializer & {
  parse?: (options: PlatePluginContext<C> & {
    element: any;
  }) => Partial<Descendant> | undefined | void;
  query?: (options: PlatePluginContext<C> & {
    element: any;
  }) => boolean;
};
type EditableSiblingComponent = (editableProps: EditableProps) => React$1.ReactElement<any> | null;
type EditorPlatePlugin<C extends AnyPluginConfig = PluginConfig> = Omit<PlatePlugin<C>, keyof PlatePluginMethods | 'override' | 'plugins'>;
/** Plate plugin overriding the `editor` methods. Naming convention is `with*`. */
type ExtendEditor<C extends AnyPluginConfig = PluginConfig> = (ctx: PlatePluginContext<C>) => PlateEditor;
type ExtendEditorApi<C extends AnyPluginConfig = PluginConfig, EA = {}> = (ctx: PlatePluginContext<C>) => EA & Deep2Partial<EditorApi & CorePluginApi> & { [K in keyof InferApi<C>]?: InferApi<C>[K] extends ((...args: any[]) => any) ? (...args: Parameters<InferApi<C>[K]>) => ReturnType<InferApi<C>[K]> : InferApi<C>[K] extends Record<string, (...args: any[]) => any> ? { [N in keyof InferApi<C>[K]]?: (...args: Parameters<InferApi<C>[K][N]>) => ReturnType<InferApi<C>[K][N]> } : never };
type ExtendEditorTransforms<C extends AnyPluginConfig = PluginConfig, ET = {}> = (ctx: PlatePluginContext<C>) => ET & Deep2Partial<EditorTransforms & CorePluginTransforms> & { [K in keyof InferTransforms<C>]?: InferTransforms<C>[K] extends ((...args: any[]) => any) ? (...args: Parameters<InferTransforms<C>[K]>) => ReturnType<InferTransforms<C>[K]> : InferTransforms<C>[K] extends Record<string, (...args: any[]) => any> ? { [N in keyof InferTransforms<C>[K]]?: (...args: Parameters<InferTransforms<C>[K][N]>) => ReturnType<InferTransforms<C>[K][N]> } : never };
type HtmlDeserializer<C extends AnyPluginConfig = PluginConfig> = BaseHtmlDeserializer & {
  parse?: (options: PlatePluginContext<C> & {
    element: HTMLElement;
    node: AnyObject;
  }) => Partial<Descendant> | undefined | void;
  query?: (options: PlatePluginContext<C> & {
    element: HTMLElement;
  }) => boolean;
};
type HtmlReactSerializer<C extends AnyPluginConfig = PluginConfig> = {
  parse?: React$1.FC<PlateElementProps<TElement, C> & PlateLeafProps<TText, C>>;
  query?: (options: PlateElementProps) => boolean;
};
type HtmlSerializer<C extends AnyPluginConfig = PluginConfig> = {
  parse?: (options: PlatePluginContext<C> & {
    node: Descendant;
  }) => string;
  query?: (options: PlatePluginContext<C> & {
    node: Descendant;
  }) => boolean;
};
type InferConfig<P$1> = P$1 extends PlatePlugin<infer C> | SlatePlugin<infer C> ? C : never;
/** Properties used by Plate to inject props into any {@link NodeComponent}. */
type InjectNodeProps<C extends AnyPluginConfig = PluginConfig> = BaseInjectProps & {
  /** Whether to inject the props. If true, overrides all other checks. */
  query?: (options: NonNullable<NonNullable<InjectNodeProps>> & PlatePluginContext<C> & {
    nodeProps: GetInjectNodePropsOptions;
  }) => boolean;
  /**
   * Transform the className.
   *
   * @default clsx(className, classNames[value])
   */
  transformClassName?: (options: TransformOptions<C>) => any;
  /**
   * Transform the node value for the style or className.
   *
   * @default nodeValue
   */
  transformNodeValue?: (options: TransformOptions<C>) => any;
  /** Transform the injected props. */
  transformProps?: (options: TransformOptions<C> & {
    props: GetInjectNodePropsReturnType;
  }) => AnyObject | undefined;
  /**
   * Transform the style.
   *
   * @default { ...style, [styleKey]: value }
   */
  transformStyle?: (options: TransformOptions<C>) => CSSStyleDeclaration;
};
type LeafNodeProps<C extends AnyPluginConfig = PluginConfig> = ((props: PlateLeafProps<TText, C>) => AnyObject | undefined) | AnyObject;
/**
 * Property used by Plate to override node `component` props. If function, its
 * returning value will be shallow merged to the old props, with the old props
 * as parameter. If object, its value will be shallow merged to the old props.
 */
type NodeProps<C extends AnyPluginConfig = PluginConfig> = ((props: PlateElementProps<TElement, C> & PlateLeafProps<TText, C>) => AnyObject | undefined) | AnyObject;
/** @deprecated Use {@link RenderNodeWrapper} instead. */
type NodeWrapperComponent<C extends AnyPluginConfig = PluginConfig> = (props: NodeWrapperComponentProps<C>) => NodeWrapperComponentReturnType<C>;
/** @deprecated Use {@link RenderNodeWrapperProps} instead. */
interface NodeWrapperComponentProps<C extends AnyPluginConfig = PluginConfig> extends PlateElementProps<TElement, C> {
  key: string;
}
/** @deprecated Use {@link RenderNodeWrapperFunction} instead. */
type NodeWrapperComponentReturnType<C extends AnyPluginConfig = PluginConfig> = React$1.FC<PlateElementProps<TElement, C>> | undefined;
type TransformInitialValue<C extends AnyPluginConfig = PluginConfig> = (ctx: PlatePluginContext<C> & {
  value: Value;
}) => Value;
/** @deprecated Use {@link TransformInitialValue} instead. */
type NormalizeInitialValue<C extends AnyPluginConfig = PluginConfig> = (ctx: PlatePluginContext<C> & {
  value: Value;
}) => Value | void;
/**
 * Function called whenever a change occurs in the editor. Return `false` to
 * prevent calling the next plugin handler.
 *
 * @see {@link SlatePropsOnChange}
 */
type OnChange<C extends AnyPluginConfig = PluginConfig> = (ctx: PlatePluginContext<C> & {
  value: Value;
}) => HandlerReturnType;
/**
 * Function called whenever a node operation occurs in the editor. Return `true`
 * to prevent calling the next plugin handler.
 */
type OnNodeChange<C extends AnyPluginConfig = PluginConfig> = (ctx: PlatePluginContext<C> & {
  node: Descendant;
  operation: NodeOperation;
  prevNode: Descendant;
}) => HandlerReturnType;
/**
 * Function called whenever a text operation occurs in the editor. Return `true`
 * to prevent calling the next plugin handler.
 */
type OnTextChange<C extends AnyPluginConfig = PluginConfig> = (ctx: PlatePluginContext<C> & {
  node: Descendant;
  operation: TextOperation;
  prevText: string;
  text: string;
}) => HandlerReturnType;
type OverrideEditor<C extends AnyPluginConfig = PluginConfig> = (ctx: PlatePluginContext<C>) => {
  api?: Deep2Partial<EditorApi & CorePluginApi> & { [K in keyof InferApi<C>]?: InferApi<C>[K] extends ((...args: any[]) => any) ? (...args: Parameters<InferApi<C>[K]>) => ReturnType<InferApi<C>[K]> : InferApi<C>[K] extends Record<string, (...args: any[]) => any> ? { [N in keyof InferApi<C>[K]]?: (...args: Parameters<InferApi<C>[K][N]>) => ReturnType<InferApi<C>[K][N]> } : never };
  transforms?: Deep2Partial<EditorTransforms & CorePluginTransforms> & { [K in keyof InferTransforms<C>]?: InferTransforms<C>[K] extends ((...args: any[]) => any) ? (...args: Parameters<InferTransforms<C>[K]>) => ReturnType<InferTransforms<C>[K]> : InferTransforms<C>[K] extends Record<string, (...args: any[]) => any> ? { [N in keyof InferTransforms<C>[K]]?: (...args: Parameters<InferTransforms<C>[K][N]>) => ReturnType<InferTransforms<C>[K][N]> } : never };
};
/**
 * Used by parser plugins like html to deserialize inserted data to a slate
 * fragment. The fragment will be inserted to the editor if not empty.
 */
type Parser<C extends AnyPluginConfig = PluginConfig> = {
  /** Format to get data. Example data types are text/plain and text/uri-list. */
  format?: string[] | string;
  mimeTypes?: string[];
  /** Deserialize data to fragment */
  deserialize?: (options: ParserOptions & PlatePluginContext<C>) => Descendant[] | undefined;
  /**
   * Function called on `editor.tf.insertData` just before
   * `editor.tf.insertFragment`. Default: if the block above the selection is
   * empty and the first fragment node type is not inline, set the selected node
   * type to the first fragment node type.
   *
   * @returns If true, the next handlers will be skipped.
   */
  preInsert?: (options: ParserOptions & PlatePluginContext<C> & {
    fragment: Descendant[];
  }) => HandlerReturnType;
  /** Query to skip this plugin. */
  query?: (options: ParserOptions & PlatePluginContext<C>) => boolean;
  /** Transform the inserted data. */
  transformData?: (options: ParserOptions & PlatePluginContext<C>) => string;
  /** Transform the fragment to insert. */
  transformFragment?: (options: ParserOptions & PlatePluginContext<C> & {
    fragment: Descendant[];
  }) => Descendant[];
};
/** The `PlatePlugin` interface is a React interface for all plugins. */
type PlatePlugin<C extends AnyPluginConfig = PluginConfig> = BasePlugin<C> & Nullable<{
  /** @see {@link Decorate} */
  decorate?: Decorate<WithAnyKey<C>>;
  /** @see {@link ExtendEditor} */
  extendEditor?: ExtendEditor<WithAnyKey<C>>;
  /** Transform the initial value before the editor is ready. */
  transformInitialValue?: TransformInitialValue<WithAnyKey<C>>;
  /** Normalize initial value before passing it into the editor. */
  /** @deprecated Use `transformInitialValue` instead. */
  normalizeInitialValue?: NormalizeInitialValue<WithAnyKey<C>>;
  /** @see {@link UseHooks} */
  useHooks?: UseHooks<WithAnyKey<C>>;
}> & PlatePluginMethods<C> & {
  /**
   * Handlers called whenever the corresponding event occurs in the editor.
   * Event handlers can return a boolean flag to specify whether the event
   * can be treated as being handled. If it returns `true`, the next
   * handlers will not be called.
   */
  handlers: Nullable<DOMHandlers<WithAnyKey<C>> & {
    /** @see {@link OnChange} */
    onChange?: OnChange<WithAnyKey<C>>;
    /** @see {@link OnNodeChange} */
    onNodeChange?: OnNodeChange<WithAnyKey<C>>;
    /** @see {@link OnTextChange} */
    onTextChange?: OnTextChange<WithAnyKey<C>>;
  }>;
  /** Plugin injection. */
  inject: Nullable<{
    nodeProps?: InjectNodeProps<WithAnyKey<C>>;
    /**
     * Property that can be used by a plugin to allow other plugins to
     * inject code. For example, if multiple plugins have defined
     * `inject.editor.tf.insertData.transformData` for `key=HtmlPlugin.key`,
     * `insertData` plugin will call all of these `transformData` for
     * `HtmlPlugin.key` plugin. Differs from `override.plugins` as this is
     * not overriding any plugin.
     */
    plugins?: Record<string, Partial<EditorPlatePlugin<AnyPluginConfig>>>;
    /**
     * A function that returns a plugin config to be injected into other
     * plugins `inject.plugins` specified by targetPlugins.
     */
    targetPluginToInject?: (ctx: PlatePluginContext<C> & {
      targetPlugin: string;
    }) => Partial<PlatePlugin<AnyPluginConfig>>;
  }>;
  node: {
    /** Override `data-slate-leaf` element attributes */
    leafProps?: LeafNodeProps<WithAnyKey<C>>;
    /** Override node attributes */
    props?: NodeProps<WithAnyKey<C>>;
    /** Override `data-slate-node="text"` element attributes */
    textProps?: TextNodeProps<WithAnyKey<C>>;
  };
  override: {
    /** Replace plugin {@link NodeComponent} by key. */
    components?: NodeComponents;
    /** Extend {@link PlatePlugin} by key. */
    plugins?: Record<string, Partial<EditorPlatePlugin<AnyPluginConfig>>>;
  };
  /** @see {@link Parser} */
  parser: Nullable<Parser<WithAnyKey<C>>>;
  parsers: (Record<string, {
    /** @see {@link Deserializer} */
    deserializer?: Deserializer<WithAnyKey<C>>;
    /** @see {@link Serializer} */
    serializer?: Serializer<WithAnyKey<C>>;
  }> & {
    html?: never;
    htmlReact?: never;
  }) | {
    html?: Nullable<{
      /** @see {@link HtmlDeserializer} */
      deserializer?: HtmlDeserializer<WithAnyKey<C>>;
      /** @see {@link HtmlSerializer} */
      serializer?: HtmlSerializer<WithAnyKey<C>>;
    }>;
    htmlReact?: Nullable<{
      /** Function to deserialize HTML to Slate nodes using React. */
      serializer?: HtmlReactSerializer<WithAnyKey<C>>;
    }>;
  };
  /**
   * Recursive plugin support to allow having multiple plugins in a single
   * plugin. Plate eventually flattens all the plugins into the editor.
   */
  plugins: any[];
  render: Nullable<{
    /**
     * When other plugins' node components are rendered, this function can
     * return an optional wrapper function that turns a node's props to a
     * wrapper React node as its parent. Useful for wrapping or decorating
     * nodes with additional UI elements.
     *
     * NOTE: The function can run React hooks. NOTE: Do not run React hooks
     * in the wrapper function. It is not equivalent to a React component.
     */
    aboveNodes?: RenderNodeWrapper<WithAnyKey<C>>;
    /** Renders a component after the `Container` component. */
    afterContainer?: EditableSiblingComponent;
    /**
     * Renders a component after the `Editable` component. This is the last
     * render position within the editor structure.
     */
    afterEditable?: EditableSiblingComponent;
    /** Renders a component before the `Container` component. */
    beforeContainer?: EditableSiblingComponent;
    /** Renders a component before the `Editable` component. */
    beforeEditable?: EditableSiblingComponent;
    /**
     * When other plugins' node components are rendered, this function can
     * return an optional wrapper function that turns a node's props to a
     * wrapper React node. The wrapper node is the node's child and its
     * original children's parent. Useful for wrapping or decorating nodes
     * with additional UI elements.
     *
     * NOTE: The function can run React hooks. NOTE: Do not run React hooks
     * in the wrapper function. It is not equivalent to a React component.
     */
    belowNodes?: RenderNodeWrapper<WithAnyKey<C>>;
    /**
     * Function to render content below the root element but above its
     * children. Similar to belowNodes but renders directly in the element
     * rather than wrapping. Multiple plugins can provide this, and all
     * their content will be rendered in sequence.
     */
    belowRootNodes?: (props: PlateElementProps<TElement, C>) => React$1.ReactNode;
  }>;
  rules: {
    /**
     * Function to determine if this plugin's rules should apply to a node.
     * Used to override behavior based on node properties beyond just type
     * matching.
     *
     * Example: List plugin sets `match: ({ node }) => !!node.listStyleType`
     * to override paragraph behavior when the paragraph is a list item.
     *
     * @default type === node.type
     */
    match?: (options: {
      node: TElement;
      path: Path;
      rule: MatchRules;
    } & PlatePluginContext<C>) => boolean;
  };
  /**
   * Keyboard shortcuts configuration mapping shortcut names to their key
   * combinations and handlers. Each shortcut can link to a transform
   * method, an API method, or use a custom handler function.
   */
  shortcuts: Partial<Record<(string & {}) | Exclude<keyof InferApi<C>[C['key']], keyof InferTransforms<C>[C['key']]> | keyof InferTransforms<C>[C['key']], Shortcut | null>>;
  inputRules: InputRulesDefinition | InputRulesConfig;
  useOptionsStore: TCreatedStoreType<C['options'], [['zustand/mutative-x', never]]>;
};
type PlatePluginConfig<K$1 extends string = any, O = {}, A$1 = {}, T = {}, S = {}, EO = {}, EA = {}, ET = {}, ES = {}> = Partial<Omit<PlatePlugin<PluginConfig<K$1, Partial<O>, A$1, T, S>>, keyof PlatePluginMethods | 'api' | 'node' | 'optionsStore' | 'transforms' | 'useOptionsStore'> & {
  api: EA;
  node: Partial<PlatePlugin<PluginConfig<K$1, O, A$1, T, S>>['node']>;
  options: EO;
  selectors: ES;
  transforms: ET;
}>;
type PlatePluginContext<C extends AnyPluginConfig = PluginConfig, E extends PlateEditor = PlateEditor> = BasePluginContext<C> & {
  editor: E;
  plugin: EditorPlatePlugin<C>;
};
type PlatePluginMethods<C extends AnyPluginConfig = PluginConfig> = {
  __apiExtensions: ((ctx: PlatePluginContext<AnyPluginConfig>) => any)[];
  __configuration: ((ctx: PlatePluginContext<AnyPluginConfig>) => any) | null;
  __extensions: ((ctx: PlatePluginContext<AnyPluginConfig>) => any)[];
  __selectorExtensions: ((ctx: PlatePluginContext<AnyPluginConfig>) => any)[];
  clone: () => PlatePlugin<C>;
  configure: (config: ((ctx: PlatePluginContext<C>) => PlatePluginConfig<C['key'], InferOptions<C>, InferApi<C>, InferTransforms<C>, InferSelectors<C>>) | PlatePluginConfig<C['key'], InferOptions<C>, InferApi<C>, InferTransforms<C>, InferSelectors<C>>) => PlatePlugin<C>;
  configurePlugin: <P$1 extends AnyPlatePlugin | AnySlatePlugin>(plugin: Partial<P$1>, config: (P$1 extends AnyPlatePlugin ? PlatePluginConfig<any, InferOptions<P$1>, InferApi<P$1>, InferTransforms<P$1>, InferSelectors<P$1>> : SlatePluginConfig<any, InferOptions<P$1>, InferApi<P$1>, InferTransforms<P$1>, InferSelectors<P$1>>) | ((ctx: P$1 extends AnyPlatePlugin ? PlatePluginContext<P$1> : SlatePluginContext<P$1>) => P$1 extends AnyPlatePlugin ? PlatePluginConfig<any, InferOptions<P$1>, InferApi<P$1>, InferTransforms<P$1>, InferSelectors<P$1>> : SlatePluginConfig<any, InferOptions<P$1>, InferApi<P$1>, InferTransforms<P$1>, InferSelectors<P$1>>)) => PlatePlugin<C>;
  extend: <EO = {}, EA = {}, ET = {}, ES = {}>(extendConfig: ((ctx: PlatePluginContext<C>) => PlatePluginConfig<C['key'], InferOptions<C>, InferApi<C>, InferTransforms<C>, InferSelectors<C>, EO, EA, ET, ES>) | PlatePluginConfig<C['key'], InferOptions<C>, InferApi<C>, InferTransforms<C>, InferSelectors<C>, EO, EA, ET, ES>) => PlatePlugin<PluginConfig<C['key'], EO & InferOptions<C>, EA & InferApi<C>, ET & InferTransforms<C>, InferSelectors<C>>>;
  extendApi: <EA extends Record<string, (...args: any[]) => any> = Record<string, never>>(extension: (ctx: PlatePluginContext<C>) => EA) => PlatePlugin<PluginConfig<C['key'], InferOptions<C>, InferApi<C> & Record<C['key'], EA>, InferTransforms<C>, InferSelectors<C>>>;
  /**
   * Extends the plugin's API with new methods or nested objects.
   *
   * This method allows you to add new functionality to the plugin's API or
   * extend existing ones. You can add top-level methods, nested objects with
   * methods, or extend existing nested objects. The types of existing methods
   * and nested objects are preserved, while new ones are inferred.
   *
   * @remarks
   *   - New methods can be added at the top level or within nested objects.
   *   - Existing methods can be overridden, but their parameter and return types
   *       must match the original.
   *   - When extending nested objects, you don't need to specify all existing
   *       properties; they will be preserved.
   *   - Only one level of nesting is supported for API objects.
   *
   * @example
   *   ```typescript
   *   const extendedPlugin = basePlugin.extendEditorApi(({ plugin }) => ({
   *     newMethod: (param: string) => param.length,
   *     existingMethod: (n) => n * 2, // Must match original signature
   *     nested: {
   *       newNestedMethod: () => 'new nested method',
   *     },
   *   }));
   *   ```;
   *
   * @template EA - The type of the extended API, inferred from the returned
   *   object.
   * @param extendedApi - A function that returns an object with the new or
   *   extended API methods.
   * @returns A new instance of the plugin with the extended API.
   */
  extendEditorApi: <EA extends Record<string, ((...args: any[]) => any) | Record<string, (...args: any[]) => any>> = Record<string, never>>(extension: ExtendEditorApi<C, EA>) => PlatePlugin<PluginConfig<C['key'], InferOptions<C>, { [K in keyof (EA & InferApi<C>)]: (EA & InferApi<C>)[K] extends ((...args: any[]) => any) ? (EA & InferApi<C>)[K] : { [N in keyof (EA & InferApi<C>)[K]]: (EA & InferApi<C>)[K][N] } }, InferTransforms<C>, InferSelectors<C>>>;
  extendEditorTransforms: <ET extends Record<string, ((...args: any[]) => any) | Record<string, (...args: any[]) => any>> = Record<string, never>>(extension: ExtendEditorTransforms<C, ET>) => PlatePlugin<PluginConfig<C['key'], InferOptions<C>, InferApi<C>, { [K in keyof (ET & InferTransforms<C>)]: (ET & InferTransforms<C>)[K] extends ((...args: any[]) => any) ? (ET & InferTransforms<C>)[K] : { [N in keyof (ET & InferTransforms<C>)[K]]: (ET & InferTransforms<C>)[K][N] } }, InferSelectors<C>>>;
  extendPlugin: <P$1 extends AnyPlatePlugin | AnySlatePlugin, EO = {}, EA = {}, ET = {}>(plugin: Partial<P$1>, extendConfig: (P$1 extends AnyPlatePlugin ? PlatePluginConfig<any, InferOptions<P$1>, InferApi<P$1>, InferTransforms<P$1>, InferSelectors<P$1>, EO, EA, ET> : SlatePluginConfig<any, InferOptions<P$1>, InferApi<P$1>, InferTransforms<P$1>, InferSelectors<P$1>, EO, EA, ET>) | ((ctx: P$1 extends AnyPlatePlugin ? PlatePluginContext<P$1> : SlatePluginContext<P$1>) => P$1 extends AnyPlatePlugin ? PlatePluginConfig<any, InferOptions<P$1>, InferApi<P$1>, InferTransforms<P$1>, InferSelectors<P$1>, EO, EA, ET> : SlatePluginConfig<any, InferOptions<P$1>, InferApi<P$1>, InferTransforms<P$1>, InferSelectors<P$1>, EO, EA, ET>)) => PlatePlugin<C>;
  extendSelectors: <ES extends Record<string, (...args: any[]) => any> = Record<string, never>>(extension: (ctx: PlatePluginContext<C>) => ES) => PlatePlugin<PluginConfig<C['key'], InferOptions<C>, InferApi<C>, InferTransforms<C>, ES & InferSelectors<C>>>;
  extendTransforms: <ET extends Record<string, (...args: any[]) => any> = Record<string, never>>(extension: (ctx: PlatePluginContext<C>) => ET) => PlatePlugin<PluginConfig<C['key'], InferOptions<C>, InferApi<C>, InferTransforms<C> & Record<C['key'], ET>, InferSelectors<C>>>;
  overrideEditor: (override: OverrideEditor<C>) => PlatePlugin<C>;
  /** Returns a new instance of the plugin with the component. */
  withComponent: (component: NodeComponent) => PlatePlugin<C>;
  __resolved?: boolean;
};
type PlatePlugins = AnyPlatePlugin[];
type RenderNodeWrapper<C extends AnyPluginConfig = PluginConfig> = (props: RenderNodeWrapperProps<C>) => RenderNodeWrapperFunction;
type RenderNodeWrapperFunction = ((elementProps: PlateElementProps) => React$1.ReactNode) | undefined;
interface RenderNodeWrapperProps<C extends AnyPluginConfig = PluginConfig> extends PlateElementProps<TElement, C> {
  key: string;
}
type Serializer<C extends AnyPluginConfig = PluginConfig> = BaseSerializer & {
  parser?: (options: PlatePluginContext<C> & {
    node: Descendant;
  }) => any;
  query?: (options: PlatePluginContext<C> & {
    node: Descendant;
  }) => boolean;
};
type Shortcut = HotkeysOptions & {
  keys?: Keys | null;
  priority?: number;
  handler?: (ctx: {
    editor: PlateEditor;
    event: KeyboardEvent;
    eventDetails: HotkeysEvent;
  }) => boolean | void;
};
type Shortcuts = Record<string, Shortcut | null>;
type TextNodeProps<C extends AnyPluginConfig = PluginConfig> = ((props: PlateLeafProps<TText, C>) => AnyObject | undefined) | AnyObject;
type TransformOptions<C extends AnyPluginConfig = PluginConfig> = BaseTransformOptions & PlatePluginContext<C>;
/** Hook called when the editor is initialized. */
type UseHooks<C extends AnyPluginConfig = PluginConfig> = (ctx: PlatePluginContext<C>) => void;
//#endregion
//#region src/react/plugin/DOMHandlers.d.ts
type DOMHandler<C extends AnyPluginConfig = PluginConfig, EV = {}> = (ctx: PlatePluginContext<C> & {
  event: EV;
}) => HandlerReturnType;
type DOMHandlers<C extends AnyPluginConfig = PluginConfig> = {
  onAbort?: DOMHandler<C, React$1.SyntheticEvent>;
  onAbortCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onAnimationEnd?: DOMHandler<C, React$1.AnimationEvent>;
  onAnimationEndCapture?: DOMHandler<C, React$1.AnimationEvent>;
  onAnimationIteration?: DOMHandler<C, React$1.AnimationEvent>;
  onAnimationIterationCapture?: DOMHandler<C, React$1.AnimationEvent>;
  onAnimationStart?: DOMHandler<C, React$1.AnimationEvent>;
  onAnimationStartCapture?: DOMHandler<C, React$1.AnimationEvent>;
  onAuxClick?: DOMHandler<C, React$1.MouseEvent>;
  onAuxClickCapture?: DOMHandler<C, React$1.MouseEvent>;
  onBeforeInput?: DOMHandler<C, React$1.FormEvent>;
  onBeforeInputCapture?: DOMHandler<C, React$1.FormEvent>;
  onBlur?: DOMHandler<C, React$1.FocusEvent>;
  onBlurCapture?: DOMHandler<C, React$1.FocusEvent>;
  onCanPlay?: DOMHandler<C, React$1.SyntheticEvent>;
  onCanPlayCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onCanPlayThrough?: DOMHandler<C, React$1.SyntheticEvent>;
  onCanPlayThroughCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onClick?: DOMHandler<C, React$1.MouseEvent>;
  onClickCapture?: DOMHandler<C, React$1.MouseEvent>;
  onCompositionEnd?: DOMHandler<C, React$1.CompositionEvent>;
  onCompositionEndCapture?: DOMHandler<C, React$1.CompositionEvent>;
  onCompositionStart?: DOMHandler<C, React$1.CompositionEvent>;
  onCompositionStartCapture?: DOMHandler<C, React$1.CompositionEvent>;
  onCompositionUpdate?: DOMHandler<C, React$1.CompositionEvent>;
  onCompositionUpdateCapture?: DOMHandler<C, React$1.CompositionEvent>;
  onContextMenu?: DOMHandler<C, React$1.MouseEvent>;
  onContextMenuCapture?: DOMHandler<C, React$1.MouseEvent>;
  onCopy?: DOMHandler<C, React$1.ClipboardEvent>;
  onCopyCapture?: DOMHandler<C, React$1.ClipboardEvent>;
  onCut?: DOMHandler<C, React$1.ClipboardEvent>;
  onCutCapture?: DOMHandler<C, React$1.ClipboardEvent>;
  onDOMBeforeInput?: DOMHandler<C, Event>;
  onDoubleClick?: DOMHandler<C, React$1.MouseEvent>;
  onDoubleClickCapture?: DOMHandler<C, React$1.MouseEvent>;
  onDrag?: DOMHandler<C, React$1.DragEvent>;
  onDragCapture?: DOMHandler<C, React$1.DragEvent>;
  onDragEnd?: DOMHandler<C, React$1.DragEvent>;
  onDragEndCapture?: DOMHandler<C, React$1.DragEvent>;
  onDragEnter?: DOMHandler<C, React$1.DragEvent>;
  onDragEnterCapture?: DOMHandler<C, React$1.DragEvent>;
  onDragExit?: DOMHandler<C, React$1.DragEvent>;
  onDragExitCapture?: DOMHandler<C, React$1.DragEvent>;
  onDragLeave?: DOMHandler<C, React$1.DragEvent>;
  onDragLeaveCapture?: DOMHandler<C, React$1.DragEvent>;
  onDragOver?: DOMHandler<C, React$1.DragEvent>;
  onDragOverCapture?: DOMHandler<C, React$1.DragEvent>;
  onDragStart?: DOMHandler<C, React$1.DragEvent>;
  onDragStartCapture?: DOMHandler<C, React$1.DragEvent>;
  onDrop?: DOMHandler<C, React$1.DragEvent>;
  onDropCapture?: DOMHandler<C, React$1.DragEvent>;
  onDurationChange?: DOMHandler<C, React$1.SyntheticEvent>;
  onDurationChangeCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onEmptied?: DOMHandler<C, React$1.SyntheticEvent>;
  onEmptiedCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onEncrypted?: DOMHandler<C, React$1.SyntheticEvent>;
  onEncryptedCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onEnded?: DOMHandler<C, React$1.SyntheticEvent>;
  onEndedCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onFocus?: DOMHandler<C, React$1.FocusEvent>;
  onFocusCapture?: DOMHandler<C, React$1.FocusEvent>;
  onGotPointerCapture?: DOMHandler<C, React$1.PointerEvent>;
  onGotPointerCaptureCapture?: DOMHandler<C, React$1.PointerEvent>;
  onInput?: DOMHandler<C, React$1.FormEvent>;
  onInputCapture?: DOMHandler<C, React$1.FormEvent>;
  onInvalid?: DOMHandler<C, React$1.FormEvent>;
  onInvalidCapture?: DOMHandler<C, React$1.FormEvent>;
  onKeyDown?: DOMHandler<C, React$1.KeyboardEvent>;
  onKeyDownCapture?: DOMHandler<C, React$1.KeyboardEvent>;
  onKeyPress?: DOMHandler<C, React$1.KeyboardEvent>;
  onKeyPressCapture?: DOMHandler<C, React$1.KeyboardEvent>;
  onKeyUp?: DOMHandler<C, React$1.KeyboardEvent>;
  onKeyUpCapture?: DOMHandler<C, React$1.KeyboardEvent>;
  onLoad?: DOMHandler<C, React$1.SyntheticEvent>;
  onLoadCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onLoadedData?: DOMHandler<C, React$1.SyntheticEvent>;
  onLoadedDataCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onLoadedMetadata?: DOMHandler<C, React$1.SyntheticEvent>;
  onLoadedMetadataCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onLoadStart?: DOMHandler<C, React$1.SyntheticEvent>;
  onLoadStartCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onLostPointerCapture?: DOMHandler<C, React$1.PointerEvent>;
  onLostPointerCaptureCapture?: DOMHandler<C, React$1.PointerEvent>;
  onMouseDown?: DOMHandler<C, React$1.MouseEvent>;
  onMouseDownCapture?: DOMHandler<C, React$1.MouseEvent>;
  onMouseEnter?: DOMHandler<C, React$1.MouseEvent>;
  onMouseLeave?: DOMHandler<C, React$1.MouseEvent>;
  onMouseMove?: DOMHandler<C, React$1.MouseEvent>;
  onMouseMoveCapture?: DOMHandler<C, React$1.MouseEvent>;
  onMouseOut?: DOMHandler<C, React$1.MouseEvent>;
  onMouseOutCapture?: DOMHandler<C, React$1.MouseEvent>;
  onMouseOver?: DOMHandler<C, React$1.MouseEvent>;
  onMouseOverCapture?: DOMHandler<C, React$1.MouseEvent>;
  onMouseUp?: DOMHandler<C, React$1.MouseEvent>;
  onMouseUpCapture?: DOMHandler<C, React$1.MouseEvent>;
  onPaste?: DOMHandler<C, React$1.ClipboardEvent>;
  onPasteCapture?: DOMHandler<C, React$1.ClipboardEvent>;
  onPause?: DOMHandler<C, React$1.SyntheticEvent>;
  onPauseCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onPlay?: DOMHandler<C, React$1.SyntheticEvent>;
  onPlayCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onPlaying?: DOMHandler<C, React$1.SyntheticEvent>;
  onPlayingCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onPointerCancel?: DOMHandler<C, React$1.PointerEvent>;
  onPointerCancelCapture?: DOMHandler<C, React$1.PointerEvent>;
  onPointerDown?: DOMHandler<C, React$1.PointerEvent>;
  onPointerDownCapture?: DOMHandler<C, React$1.PointerEvent>;
  onPointerEnter?: DOMHandler<C, React$1.PointerEvent>;
  onPointerLeave?: DOMHandler<C, React$1.PointerEvent>;
  onPointerMove?: DOMHandler<C, React$1.PointerEvent>;
  onPointerMoveCapture?: DOMHandler<C, React$1.PointerEvent>;
  onPointerOut?: DOMHandler<C, React$1.PointerEvent>;
  onPointerOutCapture?: DOMHandler<C, React$1.PointerEvent>;
  onPointerOver?: DOMHandler<C, React$1.PointerEvent>;
  onPointerOverCapture?: DOMHandler<C, React$1.PointerEvent>;
  onPointerUp?: DOMHandler<C, React$1.PointerEvent>;
  onPointerUpCapture?: DOMHandler<C, React$1.PointerEvent>;
  onProgress?: DOMHandler<C, React$1.SyntheticEvent>;
  onProgressCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onRateChange?: DOMHandler<C, React$1.SyntheticEvent>;
  onRateChangeCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onReset?: DOMHandler<C, React$1.FormEvent>;
  onResetCapture?: DOMHandler<C, React$1.FormEvent>;
  onScroll?: DOMHandler<C, React$1.UIEvent>;
  onScrollCapture?: DOMHandler<C, React$1.UIEvent>;
  onSeeked?: DOMHandler<C, React$1.SyntheticEvent>;
  onSeekedCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onSeeking?: DOMHandler<C, React$1.SyntheticEvent>;
  onSeekingCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onSelect?: DOMHandler<C, React$1.SyntheticEvent>;
  onSelectCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onStalled?: DOMHandler<C, React$1.SyntheticEvent>;
  onStalledCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onSubmit?: DOMHandler<C, React$1.FormEvent>;
  onSubmitCapture?: DOMHandler<C, React$1.FormEvent>;
  onSuspend?: DOMHandler<C, React$1.SyntheticEvent>;
  onSuspendCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onTimeUpdate?: DOMHandler<C, React$1.SyntheticEvent>;
  onTimeUpdateCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onTouchCancel?: DOMHandler<C, React$1.TouchEvent>;
  onTouchCancelCapture?: DOMHandler<C, React$1.TouchEvent>;
  onTouchEnd?: DOMHandler<C, React$1.TouchEvent>;
  onTouchEndCapture?: DOMHandler<C, React$1.TouchEvent>;
  onTouchMove?: DOMHandler<C, React$1.TouchEvent>;
  onTouchMoveCapture?: DOMHandler<C, React$1.TouchEvent>;
  onTouchStart?: DOMHandler<C, React$1.TouchEvent>;
  onTouchStartCapture?: DOMHandler<C, React$1.TouchEvent>;
  onTransitionEnd?: DOMHandler<C, React$1.TransitionEvent>;
  onTransitionEndCapture?: DOMHandler<C, React$1.TransitionEvent>;
  onVolumeChange?: DOMHandler<C, React$1.SyntheticEvent>;
  onVolumeChangeCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onWaiting?: DOMHandler<C, React$1.SyntheticEvent>;
  onWaitingCapture?: DOMHandler<C, React$1.SyntheticEvent>;
  onWheel?: DOMHandler<C, React$1.WheelEvent>;
  onWheelCapture?: DOMHandler<C, React$1.WheelEvent>;
};
//#endregion
//#region src/react/plugin/KeyboardHandler.d.ts
type KeyboardHandler<C extends AnyPluginConfig = PluginConfig> = DOMHandler<C, React$1.KeyboardEvent>;
//#endregion
//#region src/react/plugin/createPlatePlugin.d.ts
type PlatePluginConfig$2<K$1 extends string = any, O = {}, A$1 = {}, T = {}, S = {}> = Omit<Partial<Modify<PlatePlugin<PluginConfig<K$1, O, A$1, T, S>>, {
  node: Partial<PlatePlugin<PluginConfig<K$1, O, A$1, T, S>>['node']>;
}>>, keyof PlatePluginMethods | 'optionsStore' | 'useOptionsStore'>;
type TPlatePluginConfig<C extends AnyPluginConfig = PluginConfig> = Omit<Partial<Modify<PlatePlugin<C>, {
  node: Partial<PlatePlugin<C>['node']>;
}>>, keyof PlatePluginMethods | 'optionsStore' | 'useOptionsStore'>;
declare const createPlatePlugin: <K$1 extends string = any, O = {}, A$1 = {}, T = {}, S = {}>(config?: ((editor: PlateEditor) => PlatePluginConfig$2<K$1, O, A$1, T, S>) | PlatePluginConfig$2<K$1, O, A$1, T, S>) => PlatePlugin<PluginConfig<K$1, O, A$1, T, S>>;
/**
 * Explicitly typed version of `createPlatePlugin`.
 *
 * @remarks
 *   While `createPlatePlugin` uses type inference, this function requires an
 *   explicit type parameter. Use this when you need precise control over the
 *   plugin's type structure or when type inference doesn't provide the desired
 *   result.
 */
declare function createTPlatePlugin<C extends AnyPluginConfig = PluginConfig>(config?: ((editor: PlateEditor) => TPlatePluginConfig<C>) | TPlatePluginConfig<C>): PlatePlugin<C>;
//#endregion
//#region src/react/editor/getPlateCorePlugins.d.ts
declare const getPlateCorePlugins: ({
  navigationFeedback
}?: {
  navigationFeedback?: NavigationFeedbackConfig["options"] | boolean;
}) => (PlatePlugin<PluginConfig<"eventEditor", {}, {}, {}, {}>> | PlatePlugin<PluginConfig<"slateExtension", {
  onNodeChange: (options: {
    editor: SlateEditor;
    node: _platejs_slate20.Descendant;
    operation: _platejs_slate20.NodeOperation;
    prevNode: _platejs_slate20.Descendant;
  }) => void;
  onTextChange: (options: {
    editor: SlateEditor;
    node: _platejs_slate20.Descendant;
    operation: _platejs_slate20.TextOperation;
    prevText: string;
    text: string;
  }) => void;
}, {
  redecorate: (() => void) & (() => void);
  isElementStateEmpty: (element: _platejs_slate20.TElement) => boolean;
}, {
  reset: (options: _platejs_slate20.ResetOptions | undefined) => void;
  init: ((args_0: InitOptions) => void) & ((args_0: InitOptions) => void);
  insertExitBreak: ((args_0?: InsertExitBreakOptions | undefined) => true | undefined) & ((args_0?: InsertExitBreakOptions | undefined) => true | undefined);
  liftBlock: ((args_0?: LiftBlockOptions | undefined) => true | undefined) & ((args_0?: LiftBlockOptions | undefined) => true | undefined);
  resetBlock: ((args_0?: {
    at?: _platejs_slate20.Path;
  } | undefined) => true | undefined) & ((args_0?: {
    at?: _platejs_slate20.Path;
  } | undefined) => true | undefined);
  setValue: ((value?: string | _platejs_slate20.Value | undefined) => void) & ((value?: string | _platejs_slate20.Value | undefined) => void);
  apply: <N$1 extends _platejs_slate20.TElement | _platejs_slate20.TText>(operation: _platejs_slate20.Operation<N$1>) => void;
}, {}>> | PlatePlugin<PluginConfig<"dom", {
  scrollMode?: ScrollMode;
  scrollOperations?: AutoScrollOperationsMap;
  scrollOptions?: _platejs_slate20.ScrollIntoViewOptions;
}, {
  isScrolling: () => boolean;
}, {
  withScrolling: (fn: () => void, options?: WithAutoScrollOptions | undefined) => void;
}, {}>> | PlatePlugin<PluginConfig<any, {}, {}, {}, {}>> | PlatePlugin<PluginConfig<"p", {}, {}, {}, {}>>)[];
//#endregion
//#region src/react/editor/usePlateEditor.d.ts
/**
 * Creates a memoized Plate editor for React components.
 *
 * This hook creates a fully configured Plate editor instance that is memoized
 * based on the provided dependencies. It's optimized for React components to
 * prevent unnecessary re-creation of the editor on every render.
 *
 * Examples:
 *
 * ```ts
 * const editor = usePlateEditor({
 *   plugins: [ParagraphPlugin, HeadingPlugin],
 *   value: [{ type: 'p', children: [{ text: 'Hello world!' }] }],
 * });
 *
 * // Editor with custom dependencies
 * const editor = usePlateEditor(
 *   {
 *     plugins: [ParagraphPlugin],
 *     enabled,
 *   },
 *   [enabled]
 * ); // Re-create when enabled changes
 * ```
 *
 * @param options - Configuration options for creating the Plate editor
 * @param deps - Additional dependencies for the useMemo hook (default: [])
 * @see {@link createPlateEditor} for detailed information on React editor creation and configuration.
 * @see {@link createSlateEditor} for a non-React version of editor creation.
 * @see {@link withPlate} for the underlying React-specific enhancement function.
 */
declare function usePlateEditor<V$1 extends Value = Value, P$1 extends AnyPluginConfig = PlateCorePlugin, TEnabled extends boolean | undefined = undefined>(options?: CreatePlateEditorOptions<V$1, P$1> & {
  enabled?: TEnabled;
}, deps?: React$1.DependencyList): TEnabled extends false ? null : TEnabled extends true | undefined ? TPlateEditor<V$1, P$1> : TPlateEditor<V$1, P$1> | null;
//#endregion
//#region src/react/editor/usePlateViewEditor.d.ts
/**
 * Creates a memoized static Plate editor for view-only React components.
 *
 * This hook creates a fully configured static Plate editor instance that is
 * memoized based on the provided dependencies. It's optimized for React
 * components to prevent unnecessary re-creation of the editor on every render.
 * Uses createStaticEditor.
 *
 * @param options - Configuration options for creating the static Plate editor
 * @param deps - Additional dependencies for the useMemo hook (default: [])
 * @see {@link createStaticEditor} for detailed information on static editor creation and configuration.
 */
declare function usePlateViewEditor<V$1 extends Value = Value, P$1 extends AnyPluginConfig = any, TEnabled extends boolean | undefined = undefined>(options?: Parameters<typeof createStaticEditor<V$1, P$1>>[0] & {
  enabled?: TEnabled;
}, deps?: React$1.DependencyList): TEnabled extends false ? null : TEnabled extends true | undefined ? ReturnType<typeof createStaticEditor<V$1, P$1>> : ReturnType<typeof createStaticEditor<V$1, P$1>> | null;
//#endregion
//#region src/react/plugin/getEditorPlugin.d.ts
declare function getEditorPlugin<P$1 extends AnyPluginConfig | PlatePlugin<AnyPluginConfig>>(editor: PlateEditor, plugin: WithRequiredKey<P$1>): PlatePluginContext<InferConfig<P$1> extends never ? P$1 : InferConfig<P$1>>;
//#endregion
//#region src/react/plugin/getPlugin.d.ts
/** Get editor plugin by key or plugin object. */
declare function getPlugin<C extends AnyPluginConfig = PluginConfig>(editor: PlateEditor, plugin: WithRequiredKey<C>): C extends {
  node: any;
} ? C : PlatePlugin<C>;
//#endregion
//#region src/react/plugin/omitPluginContext.d.ts
declare const omitPluginContext: <T extends PlatePluginContext<AnyPlatePlugin>>(ctx: T) => Omit<T, "api" | "editor" | "plugin" | "setOptions" | "tf" | "type" | "getOption" | "getOptions" | "setOption">;
//#endregion
//#region src/react/plugin/toPlatePlugin.d.ts
type PlatePluginConfig$1<C extends AnyPluginConfig, EO = {}, EA = {}, ET = {}, ES = {}> = Omit<Partial<PlatePlugin<PluginConfig<C['key'], EO & InferOptions<C>, EA & InferApi<C>, ET & InferTransforms<C>, ES & InferSelectors<C>>>>, keyof PlatePluginMethods | 'api' | 'node' | 'options' | 'transforms'> & {
  api?: EA & Partial<InferApi<C>>;
  node?: Partial<PlatePlugin<C>['node']>;
  options?: EO & Partial<InferOptions<C>>;
  selectors?: ES & Partial<InferSelectors<C>>;
  transforms?: ET & Partial<InferTransforms<C>>;
};
/**
 * Extends a SlatePlugin to create a React PlatePlugin.
 *
 * @remarks
 *   This function transforms a SlatePlugin into a React PlatePlugin, allowing for
 *   React-specific functionality to be added.
 * @param basePlugin - The base SlatePlugin to be extended.
 * @param extendConfig - A function or object that provides the extension
 *   configuration. If a function, it receives the plugin context and should
 *   return a partial PlatePlugin. If an object, it should be a partial
 *   PlatePlugin configuration.
 * @returns A new PlatePlugin that combines the base SlatePlugin functionality
 *   with React-specific features defined in the extension configuration.
 */
declare function toPlatePlugin<C extends AnyPluginConfig, EO = {}, EA = {}, ET = {}, ES = {}>(basePlugin: SlatePlugin<C>, extendConfig?: ((ctx: PlatePluginContext<C>) => PlatePluginConfig$1<C, EO, EA, ET>) | PlatePluginConfig$1<C, EO, EA, ET>): PlatePlugin<PluginConfig<C['key'], EO & InferOptions<C>, EA & InferApi<C>, ET & InferTransforms<C>, ES & InferSelectors<C>>>;
type ExtendPluginConfig<C extends AnyPluginConfig = PluginConfig> = Omit<Partial<PlatePlugin<PluginConfig<C['key'], Partial<InferOptions<C>>, Partial<InferApi<C>>, Partial<InferTransforms<C>>>>>, keyof PlatePluginMethods>;
/**
 * Explicitly typed version of {@link toPlatePlugin}.
 *
 * @remarks
 *   This function requires explicit type parameters for both the base plugin
 *   configuration and the extension configuration. Use this when you need
 *   precise control over the plugin's type structure or when type inference
 *   doesn't provide the desired result.
 * @typeParam C - The type of the extension configuration for the PlatePlugin
 *   (required).
 * @typeParam TContext - The type of the base SlatePlugin configuration
 *   (optional).
 */
declare function toTPlatePlugin<C extends AnyPluginConfig = PluginConfig, TContext extends AnyPluginConfig = AnyPluginConfig>(basePlugin: SlatePlugin<TContext>, extendConfig?: ((ctx: PlatePluginContext<TContext>) => ExtendPluginConfig<C>) | ExtendPluginConfig<C>): PlatePlugin<PluginConfig<C['key'], InferOptions<C>, InferApi<C>, InferTransforms<C>, InferSelectors<C>>>;
//#endregion
//#region src/react/components/plate-nodes.d.ts
declare const useNodeAttributes: (props: any, ref?: any) => any;
declare const isHtmlVoidElementTag: (tag: keyof HTMLElementTagNameMap) => boolean;
declare const useBlockIdAttributeRef: <T extends HTMLElement>(blockId: unknown, ref?: React$1.Ref<T>) => (node: T) => (() => void) | undefined;
type PlateChunkProps = RenderChunkProps;
type PlateElementProps<N$1 extends TElement = TElement, C extends AnyPluginConfig = PluginConfig> = PlateNodeProps<C> & RenderElementProps<N$1> & {
  attributes: UnknownObject;
  path: Path;
} & DeprecatedNodeProps;
type DeprecatedNodeProps = {
  /**
   * @deprecated Optional class to be merged with `attributes.className`.
   * @default undefined
   */
  className?: string;
  /**
   * @deprecated Optional style to be merged with `attributes.style`
   * @default undefined
   */
  style?: React$1.CSSProperties;
};
type PlateNodeProps<C extends AnyPluginConfig = PluginConfig> = PlatePluginContext<C> & {
  /**
   * Optional ref to be merged with `attributes.ref`
   *
   * @default undefined
   */
  ref?: any;
};
type PlateHTMLProps<C extends AnyPluginConfig = PluginConfig, T extends React$1.ComponentType<PlateElementProps> | keyof HTMLElementTagNameMap = 'div'> = PlateNodeProps<C> & {
  /** HTML attributes to pass to the underlying HTML element */
  attributes: React$1.PropsWithoutRef<T extends React$1.ComponentType<PlateElementProps> ? React$1.ComponentProps<T> : T extends keyof HTMLElementTagNameMap ? React$1.JSX.IntrinsicElements[T] : never>;
  as?: T;
  /** Class to be merged with `attributes.className` */
  className?: string;
  /** Style to be merged with `attributes.style` */
  style?: React$1.CSSProperties;
};
type StyledPlateElementProps<N$1 extends TElement = TElement, C extends AnyPluginConfig = PluginConfig, T extends keyof HTMLElementTagNameMap = 'div'> = Omit<PlateElementProps<N$1, C>, keyof DeprecatedNodeProps> & PlateHTMLProps<C, T> & {
  insetProp?: boolean;
};
declare const PlateElement: <N$1 extends TElement = TElement, C extends AnyPluginConfig = PluginConfig, T extends keyof HTMLElementTagNameMap = "div">(props: StyledPlateElementProps<N$1, C, T>) => React$1.ReactElement;
type PlateTextProps<N$1 extends TText = TText, C extends AnyPluginConfig = PluginConfig> = PlateNodeProps<C> & RenderTextProps<N$1> & DeprecatedNodeProps & {
  attributes: UnknownObject;
};
type StyledPlateTextProps<N$1 extends TText = TText, C extends AnyPluginConfig = PluginConfig, T extends keyof HTMLElementTagNameMap = 'span'> = Omit<PlateTextProps<N$1, C>, keyof DeprecatedNodeProps> & PlateHTMLProps<C, T>;
declare const PlateText: <N$1 extends TText = TText, C extends AnyPluginConfig = PluginConfig, T extends keyof HTMLElementTagNameMap = "span">(props: StyledPlateTextProps<N$1, C, T>) => React$1.ReactElement;
type PlateLeafProps<N$1 extends TText = TText, C extends AnyPluginConfig = PluginConfig> = PlateNodeProps<C> & RenderLeafProps<N$1> & DeprecatedNodeProps & {
  attributes: UnknownObject;
  inset?: boolean;
};
type StyledPlateLeafProps<N$1 extends TText = TText, C extends AnyPluginConfig = PluginConfig, T extends keyof HTMLElementTagNameMap = 'span'> = Omit<PlateLeafProps<N$1, C>, keyof DeprecatedNodeProps> & PlateHTMLProps<C, T>;
declare const PlateLeaf: <N$1 extends TText = TText, C extends AnyPluginConfig = PluginConfig, T extends keyof HTMLElementTagNameMap = "span">({
  className,
  ...props
}: StyledPlateLeafProps<N$1, C, T>) => React$1.ReactElement;
//#endregion
//#region src/react/components/ContentVisibilityChunk.d.ts
declare const ContentVisibilityChunk: ({
  attributes,
  children,
  lowest
}: PlateChunkProps) => any;
//#endregion
//#region src/react/components/EditorHotkeysEffect.d.ts
declare function EditorHotkeysEffect({
  id,
  editableRef
}: {
  editableRef: React$1.RefObject<HTMLDivElement | null>;
  id?: string;
}): React$1.JSX.Element;
//#endregion
//#region src/react/components/EditorMethodsEffect.d.ts
declare const EditorMethodsEffect: ({
  id
}: {
  id?: string;
}) => null;
//#endregion
//#region src/react/components/EditorRefEffect.d.ts
declare function EditorRefPluginEffect({
  id,
  plugin
}: {
  plugin: AnyEditorPlatePlugin;
  id?: string;
}): null;
declare function EditorRefEffect({
  id
}: {
  id?: string;
}): React$1.JSX.Element;
//#endregion
//#region src/react/stores/element/useElement.d.ts
/**
 * Get the element by plugin key. If no element is found in the context, it will
 * return an empty object.
 */
declare const useElement: <T extends TElement = TElement>(pluginKey?: string) => T;
//#endregion
//#region src/react/stores/element/useElementSelector.d.ts
type UseElementSelectorOptions<T> = {
  key?: string;
  equalityFn?: (a: T, b: T) => boolean;
};
declare const useElementSelector: <T>(selector: <N$1 extends TElement>(state: NodeEntry<N$1>, prev?: T) => T, deps: DependencyList, {
  key,
  equalityFn
}?: UseElementSelectorOptions<T>) => T;
//#endregion
//#region src/react/stores/element/useElementStore.d.ts
declare const SCOPE_ELEMENT = "element";
type ElementStoreState = {
  element: TElement;
  entry: ElementEntry;
  path: Path;
};
type ElementContextValue = Nullable<ElementStoreState> & {
  parent: ElementContextValue | null;
  scope?: string;
};
type ElementStoreContextValue = {
  parent: ElementStoreContextValue | null;
  runtime: ElementRuntimeStore;
  scope?: string;
  store: ReturnType<typeof createStore>;
};
type ElementRuntimeState = Nullable<ElementStoreState>;
type ElementRuntimeStore = {
  getJotaiStore: () => ReturnType<typeof createStore>;
  getState: () => ElementRuntimeState;
  setState: (nextState: ElementRuntimeState) => void;
  subscribe: (listener: () => void) => () => void;
};
declare const elementStore: jotai_x0.StoreApi<ElementStoreState, object, "element">;
declare const withElementContext: <T>(context: Omit<ElementContextValue, "parent">, callback: () => T) => T;
declare const useElementContext: (scope?: string) => ElementContextValue | null;
declare const useElementStoreContext: (scope?: string) => ElementStoreContextValue | null;
declare const useElementStore: (scope?: string) => jotai_x0.ReturnOfUseStoreApi<ElementStoreState, object>;
declare function ElementProvider({
  children,
  path,
  scope,
  ...props
}: React$1.PropsWithChildren<Partial<ElementStoreState> & {
  scope?: string;
}>): React$1.JSX.Element;
declare function FirstBlockEffect(): null;
//#endregion
//#region src/react/stores/element/usePath.d.ts
/** Get the memoized path of the closest element. */
declare const usePath: (pluginKey?: string) => Path;
//#endregion
//#region src/react/stores/event-editor/useEventPlateId.d.ts
/** Get last event editor id: focus, blur or last. */
declare const useEventPlateId: (id?: string) => string;
//#endregion
//#region src/react/stores/plate/PlateStore.d.ts
type PlateChangeKey = 'versionDecorate' | 'versionEditor' | 'versionSelection' | 'versionValue';
type PlateStoreState<E extends PlateEditor = PlateEditor> = Nullable<{
  composing: boolean;
  decorate: NonNullable<(options: {
    editor: E;
    entry: NodeEntry;
  }) => TRange[]>;
  /** Whether `Editable` is rendered so slate DOM is resolvable. */
  isMounted: boolean;
  /**
   * Whether the editor is primary. If no editor is active, then PlateController
   * will use the first-mounted primary editor.
   *
   * @default true
   */
  primary: boolean;
  readOnly: boolean;
  renderChunk: NonNullable<EditableProps['renderChunk']>;
  renderElement: NonNullable<EditableProps['renderElement']>;
  renderLeaf: NonNullable<EditableProps['renderLeaf']>;
  renderText: NonNullable<EditableProps['renderText']>;
  /**
   * Version incremented when calling `redecorate`. This is a dependency of the
   * `decorate` function.
   */
  versionDecorate: number;
  /** Version incremented on each editor change. */
  versionEditor: number;
  /** Version incremented on each editor.selection change. */
  versionSelection: number;
  /** Version incremented on each editor.children change. */
  versionValue: number;
  /** Controlled callback called when the editor state changes. */
  onChange: (options: {
    editor: E;
    value: ValueOf<E>;
  }) => void;
  /** Controlled callback called when a node operation is applied. */
  onNodeChange: (options: {
    editor: E;
    node: Descendant;
    operation: NodeOperation;
    prevNode: Descendant;
  }) => void;
  /** Controlled callback called when the editor.selection changes. */
  onSelectionChange: (options: {
    editor: E;
    selection: TSelection;
  }) => void;
  /** Controlled callback called when a text operation is applied. */
  onTextChange: (options: {
    editor: E;
    node: Descendant;
    operation: TextOperation;
    prevText: string;
    text: string;
  }) => void;
  /** Controlled callback called when the editor.children changes. */
  onValueChange: (options: {
    editor: E;
    value: ValueOf<E>;
  }) => void;
}> & {
  /**
   * A unique id used as a provider scope. Use it if you have multiple `Plate`
   * in the same React tree.
   *
   * @default random id
   */
  id: string;
  /** A reference to the editor container element. */
  containerRef: React.RefObject<HTMLDivElement | null>;
  /**
   * Slate editor reference.
   *
   * @default createPlateFallbackEditor()
   */
  editor: E;
  /**
   * A reference to the editor scroll container element.
   *
   * @default containerRef
   */
  scrollRef: React.RefObject<HTMLDivElement | null>;
};
//#endregion
//#region src/react/stores/plate/createPlateStore.d.ts
type PlateStore = ReturnType<typeof usePlateStore>;
declare const PLATE_SCOPE = "plate";
declare const GLOBAL_PLATE_SCOPE: unique symbol;
declare const createPlateStore: <E extends PlateEditor = PlateEditor>({
  id,
  composing,
  containerRef,
  decorate,
  editor,
  isMounted,
  primary,
  readOnly,
  renderChunk,
  renderElement,
  renderLeaf,
  renderText,
  scrollRef,
  versionDecorate,
  versionEditor,
  versionSelection,
  versionValue,
  onChange,
  onNodeChange,
  onSelectionChange,
  onTextChange,
  onValueChange,
  ...state
}?: Partial<PlateStoreState<E>>) => jotai_x0.AtomStoreApi<PlateStoreState<E>, {
  trackedEditor: jotai0.Atom<{
    editor: any;
    version: number | null;
  }>;
  trackedSelection: jotai0.Atom<{
    selection: any;
    version: number | null;
  }>;
  trackedValue: jotai0.Atom<{
    value: any;
    version: number | null;
  }>;
}, "plate">;
declare const PlateStoreProvider: React$1.FC<jotai_x0.ProviderProps<{
    composing: boolean | null;
    decorate: ((options: {
      editor: PlateEditor;
      entry: _platejs_slate20.NodeEntry;
    }) => _platejs_slate20.TRange[]) | null;
    isMounted: boolean | null;
    primary: boolean | null;
    readOnly: boolean | null;
    renderChunk: RenderChunkFn | null;
    renderElement: RenderElementFn | null;
    renderLeaf: RenderLeafFn | null;
    renderText: RenderTextFn | null;
    versionDecorate: number | null;
    versionEditor: number | null;
    versionSelection: number | null;
    versionValue: number | null;
    onChange: ((options: {
      editor: PlateEditor;
      value: _platejs_slate20.Value;
    }) => void) | null;
    onNodeChange: ((options: {
      editor: PlateEditor;
      node: _platejs_slate20.Descendant;
      operation: _platejs_slate20.NodeOperation;
      prevNode: _platejs_slate20.Descendant;
    }) => void) | null;
    onSelectionChange: ((options: {
      editor: PlateEditor;
      selection: _platejs_slate20.TSelection;
    }) => void) | null;
    onTextChange: ((options: {
      editor: PlateEditor;
      node: _platejs_slate20.Descendant;
      operation: _platejs_slate20.TextOperation;
      prevText: string;
      text: string;
    }) => void) | null;
    onValueChange: ((options: {
      editor: PlateEditor;
      value: _platejs_slate20.Value;
    }) => void) | null;
    id: string;
    containerRef: React$1.RefObject<HTMLDivElement | null>;
    editor: PlateEditor;
    scrollRef: React$1.RefObject<HTMLDivElement | null>;
  }>>, plateStore: jotai_x0.StoreApi<PlateStoreState<PlateEditor>, {
    trackedEditor: jotai0.Atom<{
      editor: any;
      version: number | null;
    }>;
    trackedSelection: jotai0.Atom<{
      selection: any;
      version: number | null;
    }>;
    trackedValue: jotai0.Atom<{
      value: any;
      version: number | null;
    }>;
  }, "plate">, usePlateLocalSet: <K$1 extends "decorate" | "renderElement" | "renderLeaf" | "renderText" | "editor" | "id" | "onChange" | "onNodeChange" | "onTextChange" | "readOnly" | "renderChunk" | "composing" | "isMounted" | "primary" | "versionDecorate" | "versionEditor" | "versionSelection" | "versionValue" | "onSelectionChange" | "onValueChange" | "containerRef" | "scrollRef" | "trackedEditor" | "trackedSelection" | "trackedValue">(key: K$1, options?: string | jotai_x0.UseAtomOptions) => ({
    composing: jotai_x0.SimpleWritableAtom<boolean | null>;
    decorate: jotai_x0.SimpleWritableAtom<((options: {
      editor: PlateEditor;
      entry: _platejs_slate20.NodeEntry;
    }) => _platejs_slate20.TRange[]) | null>;
    isMounted: jotai_x0.SimpleWritableAtom<boolean | null>;
    primary: jotai_x0.SimpleWritableAtom<boolean | null>;
    readOnly: jotai_x0.SimpleWritableAtom<boolean | null>;
    renderChunk: jotai_x0.SimpleWritableAtom<RenderChunkFn | null>;
    renderElement: jotai_x0.SimpleWritableAtom<RenderElementFn | null>;
    renderLeaf: jotai_x0.SimpleWritableAtom<RenderLeafFn | null>;
    renderText: jotai_x0.SimpleWritableAtom<RenderTextFn | null>;
    versionDecorate: jotai_x0.SimpleWritableAtom<number | null>;
    versionEditor: jotai_x0.SimpleWritableAtom<number | null>;
    versionSelection: jotai_x0.SimpleWritableAtom<number | null>;
    versionValue: jotai_x0.SimpleWritableAtom<number | null>;
    onChange: jotai_x0.SimpleWritableAtom<((options: {
      editor: PlateEditor;
      value: _platejs_slate20.Value;
    }) => void) | null>;
    onNodeChange: jotai_x0.SimpleWritableAtom<((options: {
      editor: PlateEditor;
      node: _platejs_slate20.Descendant;
      operation: _platejs_slate20.NodeOperation;
      prevNode: _platejs_slate20.Descendant;
    }) => void) | null>;
    onSelectionChange: jotai_x0.SimpleWritableAtom<((options: {
      editor: PlateEditor;
      selection: _platejs_slate20.TSelection;
    }) => void) | null>;
    onTextChange: jotai_x0.SimpleWritableAtom<((options: {
      editor: PlateEditor;
      node: _platejs_slate20.Descendant;
      operation: _platejs_slate20.TextOperation;
      prevText: string;
      text: string;
    }) => void) | null>;
    onValueChange: jotai_x0.SimpleWritableAtom<((options: {
      editor: PlateEditor;
      value: _platejs_slate20.Value;
    }) => void) | null>;
    id: jotai_x0.SimpleWritableAtom<string>;
    containerRef: jotai_x0.SimpleWritableAtom<React$1.RefObject<HTMLDivElement | null>>;
    editor: jotai_x0.SimpleWritableAtom<PlateEditor>;
    scrollRef: jotai_x0.SimpleWritableAtom<React$1.RefObject<HTMLDivElement | null>>;
  } & {
    trackedEditor: jotai0.Atom<{
      editor: any;
      version: number | null;
    }>;
    trackedSelection: jotai0.Atom<{
      selection: any;
      version: number | null;
    }>;
    trackedValue: jotai0.Atom<{
      value: any;
      version: number | null;
    }>;
  })[K$1] extends jotai0.WritableAtom<infer _V, infer A extends unknown[], infer R> ? (...args: A) => R : never, usePlateLocalState: <K$1 extends "decorate" | "renderElement" | "renderLeaf" | "renderText" | "editor" | "id" | "onChange" | "onNodeChange" | "onTextChange" | "readOnly" | "renderChunk" | "composing" | "isMounted" | "primary" | "versionDecorate" | "versionEditor" | "versionSelection" | "versionValue" | "onSelectionChange" | "onValueChange" | "containerRef" | "scrollRef" | "trackedEditor" | "trackedSelection" | "trackedValue">(key: K$1, options?: string | jotai_x0.UseAtomOptions) => ({
    composing: jotai_x0.SimpleWritableAtom<boolean | null>;
    decorate: jotai_x0.SimpleWritableAtom<((options: {
      editor: PlateEditor;
      entry: _platejs_slate20.NodeEntry;
    }) => _platejs_slate20.TRange[]) | null>;
    isMounted: jotai_x0.SimpleWritableAtom<boolean | null>;
    primary: jotai_x0.SimpleWritableAtom<boolean | null>;
    readOnly: jotai_x0.SimpleWritableAtom<boolean | null>;
    renderChunk: jotai_x0.SimpleWritableAtom<RenderChunkFn | null>;
    renderElement: jotai_x0.SimpleWritableAtom<RenderElementFn | null>;
    renderLeaf: jotai_x0.SimpleWritableAtom<RenderLeafFn | null>;
    renderText: jotai_x0.SimpleWritableAtom<RenderTextFn | null>;
    versionDecorate: jotai_x0.SimpleWritableAtom<number | null>;
    versionEditor: jotai_x0.SimpleWritableAtom<number | null>;
    versionSelection: jotai_x0.SimpleWritableAtom<number | null>;
    versionValue: jotai_x0.SimpleWritableAtom<number | null>;
    onChange: jotai_x0.SimpleWritableAtom<((options: {
      editor: PlateEditor;
      value: _platejs_slate20.Value;
    }) => void) | null>;
    onNodeChange: jotai_x0.SimpleWritableAtom<((options: {
      editor: PlateEditor;
      node: _platejs_slate20.Descendant;
      operation: _platejs_slate20.NodeOperation;
      prevNode: _platejs_slate20.Descendant;
    }) => void) | null>;
    onSelectionChange: jotai_x0.SimpleWritableAtom<((options: {
      editor: PlateEditor;
      selection: _platejs_slate20.TSelection;
    }) => void) | null>;
    onTextChange: jotai_x0.SimpleWritableAtom<((options: {
      editor: PlateEditor;
      node: _platejs_slate20.Descendant;
      operation: _platejs_slate20.TextOperation;
      prevText: string;
      text: string;
    }) => void) | null>;
    onValueChange: jotai_x0.SimpleWritableAtom<((options: {
      editor: PlateEditor;
      value: _platejs_slate20.Value;
    }) => void) | null>;
    id: jotai_x0.SimpleWritableAtom<string>;
    containerRef: jotai_x0.SimpleWritableAtom<React$1.RefObject<HTMLDivElement | null>>;
    editor: jotai_x0.SimpleWritableAtom<PlateEditor>;
    scrollRef: jotai_x0.SimpleWritableAtom<React$1.RefObject<HTMLDivElement | null>>;
  } & {
    trackedEditor: jotai0.Atom<{
      editor: any;
      version: number | null;
    }>;
    trackedSelection: jotai0.Atom<{
      selection: any;
      version: number | null;
    }>;
    trackedValue: jotai0.Atom<{
      value: any;
      version: number | null;
    }>;
  })[K$1] extends jotai0.WritableAtom<infer V, infer A extends unknown[], infer R> ? [V, (...args: A) => R] : never, usePlateLocalStore: jotai_x0.UseStoreApi<PlateStoreState<PlateEditor>, {
    trackedEditor: jotai0.Atom<{
      editor: any;
      version: number | null;
    }>;
    trackedSelection: jotai0.Atom<{
      selection: any;
      version: number | null;
    }>;
    trackedValue: jotai0.Atom<{
      value: any;
      version: number | null;
    }>;
  }>, usePlateLocalValue: <K$1 extends "decorate" | "renderElement" | "renderLeaf" | "renderText" | "editor" | "id" | "onChange" | "onNodeChange" | "onTextChange" | "readOnly" | "renderChunk" | "composing" | "isMounted" | "primary" | "versionDecorate" | "versionEditor" | "versionSelection" | "versionValue" | "onSelectionChange" | "onValueChange" | "containerRef" | "scrollRef" | "trackedEditor" | "trackedSelection" | "trackedValue", S = (({
    composing: jotai_x0.SimpleWritableAtom<boolean | null>;
    decorate: jotai_x0.SimpleWritableAtom<((options: {
      editor: PlateEditor;
      entry: _platejs_slate20.NodeEntry;
    }) => _platejs_slate20.TRange[]) | null>;
    isMounted: jotai_x0.SimpleWritableAtom<boolean | null>;
    primary: jotai_x0.SimpleWritableAtom<boolean | null>;
    readOnly: jotai_x0.SimpleWritableAtom<boolean | null>;
    renderChunk: jotai_x0.SimpleWritableAtom<RenderChunkFn | null>;
    renderElement: jotai_x0.SimpleWritableAtom<RenderElementFn | null>;
    renderLeaf: jotai_x0.SimpleWritableAtom<RenderLeafFn | null>;
    renderText: jotai_x0.SimpleWritableAtom<RenderTextFn | null>;
    versionDecorate: jotai_x0.SimpleWritableAtom<number | null>;
    versionEditor: jotai_x0.SimpleWritableAtom<number | null>;
    versionSelection: jotai_x0.SimpleWritableAtom<number | null>;
    versionValue: jotai_x0.SimpleWritableAtom<number | null>;
    onChange: jotai_x0.SimpleWritableAtom<((options: {
      editor: PlateEditor;
      value: _platejs_slate20.Value;
    }) => void) | null>;
    onNodeChange: jotai_x0.SimpleWritableAtom<((options: {
      editor: PlateEditor;
      node: _platejs_slate20.Descendant;
      operation: _platejs_slate20.NodeOperation;
      prevNode: _platejs_slate20.Descendant;
    }) => void) | null>;
    onSelectionChange: jotai_x0.SimpleWritableAtom<((options: {
      editor: PlateEditor;
      selection: _platejs_slate20.TSelection;
    }) => void) | null>;
    onTextChange: jotai_x0.SimpleWritableAtom<((options: {
      editor: PlateEditor;
      node: _platejs_slate20.Descendant;
      operation: _platejs_slate20.TextOperation;
      prevText: string;
      text: string;
    }) => void) | null>;
    onValueChange: jotai_x0.SimpleWritableAtom<((options: {
      editor: PlateEditor;
      value: _platejs_slate20.Value;
    }) => void) | null>;
    id: jotai_x0.SimpleWritableAtom<string>;
    containerRef: jotai_x0.SimpleWritableAtom<React$1.RefObject<HTMLDivElement | null>>;
    editor: jotai_x0.SimpleWritableAtom<PlateEditor>;
    scrollRef: jotai_x0.SimpleWritableAtom<React$1.RefObject<HTMLDivElement | null>>;
  } & {
    trackedEditor: jotai0.Atom<{
      editor: any;
      version: number | null;
    }>;
    trackedSelection: jotai0.Atom<{
      selection: any;
      version: number | null;
    }>;
    trackedValue: jotai0.Atom<{
      value: any;
      version: number | null;
    }>;
  })[K$1] extends jotai0.Atom<infer V> ? V : never)>(key: K$1, options?: ({
    selector?: ((v: ({
      composing: jotai_x0.SimpleWritableAtom<boolean | null>;
      decorate: jotai_x0.SimpleWritableAtom<((options: {
        editor: PlateEditor;
        entry: _platejs_slate20.NodeEntry;
      }) => _platejs_slate20.TRange[]) | null>;
      isMounted: jotai_x0.SimpleWritableAtom<boolean | null>;
      primary: jotai_x0.SimpleWritableAtom<boolean | null>;
      readOnly: jotai_x0.SimpleWritableAtom<boolean | null>;
      renderChunk: jotai_x0.SimpleWritableAtom<RenderChunkFn | null>;
      renderElement: jotai_x0.SimpleWritableAtom<RenderElementFn | null>;
      renderLeaf: jotai_x0.SimpleWritableAtom<RenderLeafFn | null>;
      renderText: jotai_x0.SimpleWritableAtom<RenderTextFn | null>;
      versionDecorate: jotai_x0.SimpleWritableAtom<number | null>;
      versionEditor: jotai_x0.SimpleWritableAtom<number | null>;
      versionSelection: jotai_x0.SimpleWritableAtom<number | null>;
      versionValue: jotai_x0.SimpleWritableAtom<number | null>;
      onChange: jotai_x0.SimpleWritableAtom<((options: {
        editor: PlateEditor;
        value: _platejs_slate20.Value;
      }) => void) | null>;
      onNodeChange: jotai_x0.SimpleWritableAtom<((options: {
        editor: PlateEditor;
        node: _platejs_slate20.Descendant;
        operation: _platejs_slate20.NodeOperation;
        prevNode: _platejs_slate20.Descendant;
      }) => void) | null>;
      onSelectionChange: jotai_x0.SimpleWritableAtom<((options: {
        editor: PlateEditor;
        selection: _platejs_slate20.TSelection;
      }) => void) | null>;
      onTextChange: jotai_x0.SimpleWritableAtom<((options: {
        editor: PlateEditor;
        node: _platejs_slate20.Descendant;
        operation: _platejs_slate20.TextOperation;
        prevText: string;
        text: string;
      }) => void) | null>;
      onValueChange: jotai_x0.SimpleWritableAtom<((options: {
        editor: PlateEditor;
        value: _platejs_slate20.Value;
      }) => void) | null>;
      id: jotai_x0.SimpleWritableAtom<string>;
      containerRef: jotai_x0.SimpleWritableAtom<React$1.RefObject<HTMLDivElement | null>>;
      editor: jotai_x0.SimpleWritableAtom<PlateEditor>;
      scrollRef: jotai_x0.SimpleWritableAtom<React$1.RefObject<HTMLDivElement | null>>;
    } & {
      trackedEditor: jotai0.Atom<{
        editor: any;
        version: number | null;
      }>;
      trackedSelection: jotai0.Atom<{
        selection: any;
        version: number | null;
      }>;
      trackedValue: jotai0.Atom<{
        value: any;
        version: number | null;
      }>;
    })[K$1] extends jotai0.Atom<infer V_1> ? V_1 : never, prevSelectorOutput?: S | undefined) => S) | undefined;
    equalityFn?: ((prev: S, next: S) => boolean) | undefined;
  } & jotai_x0.UseAtomOptions) | undefined, deps?: unknown[]) => S;
declare const usePlateStore: (id?: string) => jotai_x0.ReturnOfUseStoreApi<PlateStoreState<PlateEditor>, {
  trackedEditor: jotai0.Atom<{
    editor: any;
    version: number | null;
  }>;
  trackedSelection: jotai0.Atom<{
    selection: any;
    version: number | null;
  }>;
  trackedValue: jotai0.Atom<{
    value: any;
    version: number | null;
  }>;
}>;
declare const usePlateSet: typeof usePlateLocalSet;
declare const usePlateValue: typeof usePlateLocalValue;
declare const usePlateState: typeof usePlateLocalState;
/** Get the closest `Plate` id. */
declare const useEditorId: () => string;
declare const useEditorContainerRef: (id?: string) => React$1.RefObject<HTMLDivElement | null>;
declare const useEditorScrollRef: (id?: string) => React$1.RefObject<HTMLDivElement | null>;
/** Returns the scrollRef if it exists, otherwise returns the containerRef. */
declare const useScrollRef: (id?: string) => React$1.RefObject<HTMLDivElement | null>;
declare const useEditorMounted: (id?: string) => boolean;
/**
 * Whether the editor is read-only. You can also use `useReadOnly` from
 * `slate-react` in node components.
 */
declare const useEditorReadOnly: (id?: string) => boolean;
/** Whether the editor is composing. */
declare const useEditorComposing: (id?: string) => boolean;
/**
 * Get a reference to the editor instance that remains stable across re-renders.
 * The editor object is enhanced with a `store` property that provides access to
 * the Plate store.
 *
 * @example
 *   ```tsx
 *   const editor = useEditorRef();
 *   const readOnly = useAtomStoreValue(editor.store, 'readOnly');
 */
declare const useEditorRef: <E extends PlateEditor = PlateEditor>(id?: string) => E & {
  store: PlateStore;
};
/** Get the editor selection (deeply memoized). */
declare const useEditorSelection: (id?: string) => any;
/** Get editor state which is updated on editor change. */
declare const useEditorState: <E extends PlateEditor = PlateEditor>(id?: string) => E;
/** Version incremented on each editor change. */
declare const useEditorVersion: (id?: string) => number | null;
/** Version incremented on selection change. */
declare const useSelectionVersion: (id?: string) => number | null;
/** Get the editor value (deeply memoized). */
declare const useEditorValue: (id?: string) => any;
/** Version incremented on value change. */
declare const useValueVersion: (id?: string) => number | null;
declare const useIncrementVersion: (key: PlateChangeKey, id?: string) => () => void;
declare const useRedecorate: (id?: string) => () => void;
//#endregion
//#region src/react/stores/plate/useEditorPlugin.d.ts
/** Get editor and plugin context. */
declare function useEditorPlugin<P$1 extends AnyPluginConfig | PlatePlugin<AnyPluginConfig>, E extends PlateEditor = PlateEditor>(p: WithRequiredKey<P$1>, id?: string): PlatePluginContext<InferConfig<P$1> extends never ? P$1 : InferConfig<P$1>, E> & {
  store: PlateStore;
};
//#endregion
//#region src/react/stores/plate/useEditorSelector.d.ts
type UseEditorSelectorOptions<T> = {
  id?: string;
  equalityFn?: (a: T, b: T) => boolean;
};
declare const useEditorSelector: <T, E extends PlateEditor = PlateEditor>(selector: (editor: E, prev?: T) => T, deps: React$1.DependencyList, {
  id,
  equalityFn
}?: UseEditorSelectorOptions<T>) => T;
//#endregion
//#region src/react/stores/plate/usePluginOption.d.ts
/**
 * Hook to access plugin options. For usage outside `<Plate>`, use
 * `useEditorPluginOption` instead.
 *
 * @example
 *   const value = usePluginOption(plugin, 'value');
 *   const doubleValue = usePluginOption(plugin, 'doubleValue', 2);
 */
declare function usePluginOption<C extends AnyPluginConfig, StateType extends InferOptions<C>, TSelectors extends InferSelectors<C>, K$1 extends keyof StateType | keyof TSelectors | 'state'>(plugin: WithRequiredKey<C>, key: K$1, ...args: [...(K$1 extends keyof TSelectors ? Parameters<TSelectors[K$1]> : unknown[]), TEqualityChecker<K$1 extends 'state' ? StateType : K$1 extends keyof TSelectors ? ReturnType<TSelectors[K$1]> : K$1 extends keyof StateType ? StateType[K$1] : never>?]): K$1 extends 'state' ? StateType : K$1 extends keyof TSelectors ? ReturnType<TSelectors[K$1]> : K$1 extends keyof StateType ? StateType[K$1] : never;
declare function useEditorPluginOption<C extends AnyPluginConfig, StateType extends InferOptions<C>, TSelectors extends InferSelectors<C>, K$1 extends keyof StateType | keyof TSelectors | 'state'>(editor: PlateEditor, plugin: WithRequiredKey<C>, key: K$1, ...args: [...(K$1 extends keyof TSelectors ? Parameters<TSelectors[K$1]> : unknown[]), TEqualityChecker<K$1 extends 'state' ? StateType : K$1 extends keyof TSelectors ? ReturnType<TSelectors[K$1]> : K$1 extends keyof StateType ? StateType[K$1] : never>?]): K$1 extends 'state' ? StateType : K$1 extends keyof TSelectors ? ReturnType<TSelectors[K$1]> : K$1 extends keyof StateType ? StateType[K$1] : never;
/**
 * Use zustand store selector.
 *
 * @example
 *   const name = usePluginOptions(plugin, (state) => state.name, equalityFn);
 */
declare function usePluginOptions<C extends AnyPluginConfig, U>(plugin: WithRequiredKey<C>, selector: (state: InferOptions<C>) => U, {
  id,
  equalityFn
}?: {
  id?: string;
  equalityFn?: (a: U, b: U) => boolean;
}): U;
declare function useEditorPluginOptions<C extends AnyPluginConfig, U>(editor: PlateEditor, plugin: WithRequiredKey<C>, selector: (state: InferOptions<C>) => U, {
  equalityFn
}?: {
  equalityFn?: (a: U, b: U) => boolean;
}): U;
//#endregion
//#region src/react/stores/plate-controller/plateControllerStore.d.ts
declare const PlateController: React$1.FC<jotai_x0.ProviderProps<{
    activeId: string | null;
    editorStores: Record<string, ({
      get: <Value$1>(atom: Atom<Value$1>) => Value$1;
      set: <Value$1, Args extends unknown[], Result>(atom: jotai0.WritableAtom<Value$1, Args, Result>, ...args: Args) => Result;
      sub: (atom: Atom<unknown>, listener: () => void) => () => void;
    } & Partial<{
      dev_subscribe_store: (l: (action: {
        type: "write";
        flushed: Set<Atom<unknown>>;
      } | {
        type: "async-write";
        flushed: Set<Atom<unknown>>;
      } | {
        type: "sub";
        flushed: Set<Atom<unknown>>;
      } | {
        type: "unsub";
      } | {
        type: "restore";
        flushed: Set<Atom<unknown>>;
      }) => void, rev: 2) => () => void;
      dev_get_mounted_atoms: () => IterableIterator<Atom<unknown>>;
      dev_get_atom_state: (a: Atom<unknown>) => ({
        d: Map<Atom<unknown>, /*elided*/any & ({
          e: unknown;
        } | {
          v: unknown;
        })>;
      } & ({
        e: unknown;
      } | {
        v: unknown;
      })) | undefined;
      dev_get_mounted: (a: Atom<unknown>) => {
        l: Set<() => void>;
        t: Set<Atom<unknown>>;
        u?: () => void;
      } | undefined;
      dev_restore_atoms: (values: Iterable<readonly [Atom<unknown>, unknown]>) => void;
    }>) | null>;
    primaryEditorIds: string[];
  }>>, plateControllerStore: jotai_x0.StoreApi<{
    activeId: jotai0.PrimitiveAtom<string | null> & {
      init: string | null;
    };
    editorStores: jotai0.PrimitiveAtom<Record<string, ({
      get: <Value$1>(atom: Atom<Value$1>) => Value$1;
      set: <Value$1, Args extends unknown[], Result>(atom: jotai0.WritableAtom<Value$1, Args, Result>, ...args: Args) => Result;
      sub: (atom: Atom<unknown>, listener: () => void) => () => void;
    } & Partial<{
      dev_subscribe_store: (l: (action: {
        type: "write";
        flushed: Set<Atom<unknown>>;
      } | {
        type: "async-write";
        flushed: Set<Atom<unknown>>;
      } | {
        type: "sub";
        flushed: Set<Atom<unknown>>;
      } | {
        type: "unsub";
      } | {
        type: "restore";
        flushed: Set<Atom<unknown>>;
      }) => void, rev: 2) => () => void;
      dev_get_mounted_atoms: () => IterableIterator<Atom<unknown>>;
      dev_get_atom_state: (a: Atom<unknown>) => ({
        d: Map<Atom<unknown>, /*elided*/any & ({
          e: unknown;
        } | {
          v: unknown;
        })>;
      } & ({
        e: unknown;
      } | {
        v: unknown;
      })) | undefined;
      dev_get_mounted: (a: Atom<unknown>) => {
        l: Set<() => void>;
        t: Set<Atom<unknown>>;
        u?: () => void;
      } | undefined;
      dev_restore_atoms: (values: Iterable<readonly [Atom<unknown>, unknown]>) => void;
    }>) | null>> & {
      init: Record<string, ({
        get: <Value$1>(atom: Atom<Value$1>) => Value$1;
        set: <Value$1, Args extends unknown[], Result>(atom: jotai0.WritableAtom<Value$1, Args, Result>, ...args: Args) => Result;
        sub: (atom: Atom<unknown>, listener: () => void) => () => void;
      } & Partial<{
        dev_subscribe_store: (l: (action: {
          type: "write";
          flushed: Set<Atom<unknown>>;
        } | {
          type: "async-write";
          flushed: Set<Atom<unknown>>;
        } | {
          type: "sub";
          flushed: Set<Atom<unknown>>;
        } | {
          type: "unsub";
        } | {
          type: "restore";
          flushed: Set<Atom<unknown>>;
        }) => void, rev: 2) => () => void;
        dev_get_mounted_atoms: () => IterableIterator<Atom<unknown>>;
        dev_get_atom_state: (a: Atom<unknown>) => ({
          d: Map<Atom<unknown>, /*elided*/any & ({
            e: unknown;
          } | {
            v: unknown;
          })>;
        } & ({
          e: unknown;
        } | {
          v: unknown;
        })) | undefined;
        dev_get_mounted: (a: Atom<unknown>) => {
          l: Set<() => void>;
          t: Set<Atom<unknown>>;
          u?: () => void;
        } | undefined;
        dev_restore_atoms: (values: Iterable<readonly [Atom<unknown>, unknown]>) => void;
      }>) | null>;
    };
    primaryEditorIds: jotai0.PrimitiveAtom<string[]> & {
      init: string[];
    };
  }, object, "plateController">, _usePlateControllerStore: jotai_x0.UseStoreApi<{
    activeId: jotai0.PrimitiveAtom<string | null> & {
      init: string | null;
    };
    editorStores: jotai0.PrimitiveAtom<Record<string, ({
      get: <Value$1>(atom: Atom<Value$1>) => Value$1;
      set: <Value$1, Args extends unknown[], Result>(atom: jotai0.WritableAtom<Value$1, Args, Result>, ...args: Args) => Result;
      sub: (atom: Atom<unknown>, listener: () => void) => () => void;
    } & Partial<{
      dev_subscribe_store: (l: (action: {
        type: "write";
        flushed: Set<Atom<unknown>>;
      } | {
        type: "async-write";
        flushed: Set<Atom<unknown>>;
      } | {
        type: "sub";
        flushed: Set<Atom<unknown>>;
      } | {
        type: "unsub";
      } | {
        type: "restore";
        flushed: Set<Atom<unknown>>;
      }) => void, rev: 2) => () => void;
      dev_get_mounted_atoms: () => IterableIterator<Atom<unknown>>;
      dev_get_atom_state: (a: Atom<unknown>) => ({
        d: Map<Atom<unknown>, /*elided*/any & ({
          e: unknown;
        } | {
          v: unknown;
        })>;
      } & ({
        e: unknown;
      } | {
        v: unknown;
      })) | undefined;
      dev_get_mounted: (a: Atom<unknown>) => {
        l: Set<() => void>;
        t: Set<Atom<unknown>>;
        u?: () => void;
      } | undefined;
      dev_restore_atoms: (values: Iterable<readonly [Atom<unknown>, unknown]>) => void;
    }>) | null>> & {
      init: Record<string, ({
        get: <Value$1>(atom: Atom<Value$1>) => Value$1;
        set: <Value$1, Args extends unknown[], Result>(atom: jotai0.WritableAtom<Value$1, Args, Result>, ...args: Args) => Result;
        sub: (atom: Atom<unknown>, listener: () => void) => () => void;
      } & Partial<{
        dev_subscribe_store: (l: (action: {
          type: "write";
          flushed: Set<Atom<unknown>>;
        } | {
          type: "async-write";
          flushed: Set<Atom<unknown>>;
        } | {
          type: "sub";
          flushed: Set<Atom<unknown>>;
        } | {
          type: "unsub";
        } | {
          type: "restore";
          flushed: Set<Atom<unknown>>;
        }) => void, rev: 2) => () => void;
        dev_get_mounted_atoms: () => IterableIterator<Atom<unknown>>;
        dev_get_atom_state: (a: Atom<unknown>) => ({
          d: Map<Atom<unknown>, /*elided*/any & ({
            e: unknown;
          } | {
            v: unknown;
          })>;
        } & ({
          e: unknown;
        } | {
          v: unknown;
        })) | undefined;
        dev_get_mounted: (a: Atom<unknown>) => {
          l: Set<() => void>;
          t: Set<Atom<unknown>>;
          u?: () => void;
        } | undefined;
        dev_restore_atoms: (values: Iterable<readonly [Atom<unknown>, unknown]>) => void;
      }>) | null>;
    };
    primaryEditorIds: jotai0.PrimitiveAtom<string[]> & {
      init: string[];
    };
  }, object>;
declare const usePlateControllerLocalStore: typeof _usePlateControllerStore;
declare const usePlateControllerExists: () => boolean;
/**
 * Retrieve from PlateController the JotaiStore for the editor with a given ID,
 * or the active editor if no ID is provided, or the first primary editor if no
 * editor is active, or null.
 */
declare const usePlateControllerStore: (idProp?: string) => JotaiStore | null;
//#endregion
//#region src/react/components/Plate.d.ts
interface PlateProps<E extends PlateEditor = PlateEditor> extends Partial<Pick<PlateStoreState<E>, 'decorate' | 'onChange' | 'onNodeChange' | 'onSelectionChange' | 'onTextChange' | 'onValueChange' | 'primary' | 'readOnly'>> {
  children: React$1.ReactNode;
  editor: E | null;
  renderElement?: EditableProps['renderElement'];
  renderLeaf?: EditableProps['renderLeaf'];
  suppressInstanceWarning?: boolean;
}
declare function Plate<E extends PlateEditor = PlateEditor>(props: PlateProps<E>): React$1.JSX.Element | null;
//#endregion
//#region src/react/components/PlateContainer.d.ts
declare const PlateContainer: {
  ({
    children,
    ...props
  }: HTMLAttributes<HTMLDivElement>): React$1.JSX.Element;
  displayName: string;
};
//#endregion
//#region src/react/components/PlateContent.d.ts
type PlateContentProps = Omit<EditableProps, 'decorate'> & {
  /** Autofocus when it becomes editable (readOnly false -> readOnly true) */
  autoFocusOnEditable?: boolean;
  decorate?: PlateStoreState['decorate'];
  disabled?: boolean;
  /** R enders the editable content. */
  renderEditable?: (editable: React$1.ReactElement<any>) => React$1.ReactNode;
};
/**
 * Editable with plugins.
 *
 * - Decorate prop
 * - DOM handler props
 * - ReadOnly prop
 * - Render.afterEditable
 * - Render.beforeEditable
 * - RenderElement prop
 * - RenderLeaf prop
 * - UseHooks
 */
declare const PlateContent: React$1.ForwardRefExoticComponent<Omit<EditableProps, "decorate"> & {
  /** Autofocus when it becomes editable (readOnly false -> readOnly true) */
  autoFocusOnEditable?: boolean;
  decorate?: PlateStoreState["decorate"];
  disabled?: boolean;
  /** R enders the editable content. */
  renderEditable?: (editable: React$1.ReactElement<any>) => React$1.ReactNode;
} & React$1.RefAttributes<unknown>>;
//#endregion
//#region src/react/components/PlateControllerEffect.d.ts
type PlateControllerEffectProps = {
  id?: string;
};
declare const PlateControllerEffect: ({
  id: idProp
}: PlateControllerEffectProps) => null;
//#endregion
//#region src/react/components/PlateSlate.d.ts
/**
 * Slate with plugins.
 *
 * - OnChange prop
 * - RenderAboveSlate
 */
declare function PlateSlate({
  id,
  children
}: {
  children: React$1.ReactNode;
  id?: string;
}): React$1.ReactElement<any, string | React$1.JSXElementConstructor<any>>;
//#endregion
//#region src/react/components/PlateTest.d.ts
declare function PlateTest({
  editableProps,
  shouldNormalizeEditor,
  variant,
  ...props
}: CreatePlateEditorOptions & PlateProps & {
  editableProps?: PlateContentProps;
  variant?: 'comment' | 'wordProcessor';
}): React$1.JSX.Element;
//#endregion
//#region src/react/components/PlateView.d.ts
type PlateViewProps = PlateStaticProps & {};
declare const PlateView: (props: PlateViewProps) => React$1.JSX.Element;
//#endregion
//#region src/react/components/withHOC.d.ts
type RefComponent<P$1, R$1> = React$1.FC<P$1> & {
  ref?: React$1.Ref<R$1>;
};
declare const withHOC: <ComponentProps, HOCProps, ComponentRef, HOCRef>(HOC: RefComponent<HOCProps, HOCRef>, Component: RefComponent<ComponentProps, ComponentRef>, hocProps?: Omit<HOCProps, "children">, hocRef?: React$1.Ref<HOCRef>) => React$1.ForwardRefExoticComponent<React$1.PropsWithoutRef<ComponentProps> & React$1.RefAttributes<ComponentRef>>;
//#endregion
//#region src/react/hooks/useEditableProps.d.ts
declare const useEditableProps: ({
  disabled,
  readOnly,
  ...editableProps
}?: Omit<EditableProps, "decorate"> & Pick<PlateProps, "decorate">) => EditableProps;
//#endregion
//#region src/react/hooks/useNodePath.d.ts
/**
 * Returns the path of a node every time the node changes. Note, however, that
 * if another node is updated in a way that affects this node's path, this hook
 * will not return the new path.
 */
declare const useNodePath: (node: TNode) => _platejs_slate20.Path | undefined;
//#endregion
//#region src/react/hooks/useSlateProps.d.ts
type SlateComponentProps = Omit<React$1.ComponentProps<typeof Slate>, 'children'>;
interface PlateSlateProps extends SlateComponentProps {
  key: React$1.Key;
}
/** Get Slate props stored in a global store. */
declare const useSlateProps: ({
  id
}: {
  id?: string;
}) => PlateSlateProps;
//#endregion
//#region src/react/utils/createPlateFallbackEditor.d.ts
declare const createPlateFallbackEditor: (options?: CreatePlateEditorOptions) => TPlateEditor<_platejs_slate20.Value, PlateCorePlugin>;
//#endregion
//#region src/react/utils/dom-attributes.d.ts
declare const DOM_HANDLERS: (keyof DOMHandlers)[];
//#endregion
//#region src/react/utils/getRenderNodeProps.d.ts
/**
 * Override node props with plugin props. Allowed properties in
 * `props.element.attributes` are passed into `props.attributes`. Extend the
 * class name with the node type.
 */
declare const getRenderNodeProps: ({
  attributes: nodeAttributes,
  disableInjectNodeProps,
  editor,
  plugin,
  pluginContext,
  props,
  readOnly
}: {
  editor: PlateEditor;
  props: PlateHTMLProps;
  attributes?: AnyObject;
  disableInjectNodeProps?: boolean;
  plugin?: AnyEditorPlatePlugin;
  pluginContext?: AnyObject;
  readOnly?: boolean;
}) => PlateHTMLProps;
//#endregion
//#region src/react/utils/pipeHandler.d.ts
declare const convertDomEventToSyntheticEvent: (domEvent: Event) => React$1.SyntheticEvent<unknown, unknown>;
/** Check if an event is overrided by a handler. */
declare const isEventHandled: <EventType extends React$1.SyntheticEvent<unknown, unknown>>(event: EventType, handler?: (event: EventType) => boolean | void) => boolean;
/**
 * Generic pipe for handlers.
 *
 * - Get all the plugins handlers by `handlerKey`.
 * - If there is no plugin handler or editable prop handler for this key, return
 *   `undefined`.
 * - Return a handler calling all the plugins handlers then the prop handler.
 * - Any handler returning true will stop the next handlers to be called,
 *   including slate internal handler.
 */
declare const pipeHandler: <K$1 extends keyof DOMHandlers>(editor: PlateEditor, {
  editableProps,
  handlerKey
}: {
  handlerKey: K$1;
  editableProps?: Omit<EditableProps, "decorate"> | null;
}) => ((event: any) => void) | undefined;
//#endregion
//#region src/react/utils/pipeOnChange.d.ts
declare const pipeOnChange: (editor: PlateEditor, value: Value) => boolean;
//#endregion
//#region src/react/utils/pipeRenderElement.d.ts
/** @see {@link RenderElement} */
declare const pipeRenderElement: (editor: PlateEditor, renderElementProp?: EditableProps["renderElement"]) => EditableProps["renderElement"];
//#endregion
//#region src/react/utils/pipeRenderLeaf.d.ts
/** @see {@link RenderLeaf} */
declare const pipeRenderLeaf: (editor: PlateEditor, renderLeafProp?: EditableProps["renderLeaf"]) => EditableProps["renderLeaf"];
//#endregion
//#region src/react/utils/pipeRenderText.d.ts
/** @see {@link RenderText} */
declare const pipeRenderText: (editor: PlateEditor, renderTextProp?: EditableProps["renderText"]) => EditableProps["renderText"];
//#endregion
//#region src/react/utils/pluginRenderElement.d.ts
/**
 * Function used to render an element. If the function returns undefined then
 * the next RenderElement function is called. If the function renders a JSX
 * element then that JSX element is rendered.
 */
type RenderElement = (props: PlateElementProps) => React$1.ReactElement<any> | undefined;
declare function BelowRootNodes({
  ...props
}: any): React$1.JSX.Element;
/**
 * Get a `Editable.renderElement` handler for `plugin.node.type`. If the type is
 * equals to the slate element type, render `plugin.render.node`. Else, return
 * `undefined` so the pipeline can check the next plugin.
 */
declare const pluginRenderElement: (editor: PlateEditor, plugin: AnyEditorPlatePlugin) => RenderElement;
//#endregion
//#region src/react/utils/pluginRenderLeaf.d.ts
type RenderLeaf = (props: PlateLeafProps) => React$1.ReactElement<any>;
/**
 * Get a `Editable.renderLeaf` handler for `plugin.node.type`. If the type is
 * equals to the slate leaf type, render `plugin.render.node`. Else, return
 * `children`.
 */
declare const pluginRenderLeaf: (editor: PlateEditor, plugin: AnyEditorPlatePlugin) => RenderLeaf;
//#endregion
//#region src/react/utils/pluginRenderText.d.ts
type RenderText = (props: PlateTextProps) => React$1.ReactElement<any>;
/**
 * Get a `Editable.renderText` handler for `plugin.node.type`. If the type is
 * equals to the slate text type and isDecoration is false, render
 * `plugin.render.node`. Else, return the default text rendering.
 */
declare const pluginRenderText: (editor: PlateEditor, plugin: AnyEditorPlatePlugin) => RenderText;
//#endregion
export { AnyEditorPlatePlugin, AnyPlatePlugin, BLUR_EDITOR_EVENT, BelowRootNodes, ContentVisibilityChunk, CreatePlateEditorOptions, DOMHandler, DOMHandlers, DOM_HANDLERS, Decorate, DefaultPlaceholder, Deserializer, Editable, EditableSiblingComponent, EditorHotkeysEffect, EditorMethodsEffect, EditorPlatePlugin, EditorRefEffect, EditorRefPluginEffect, ElementProvider, ElementStoreState, EventEditorPlugin, EventEditorState, EventEditorStore, ExtendEditor, ExtendEditorApi, ExtendEditorTransforms, FOCUS_EDITOR_EVENT, FirstBlockEffect, GLOBAL_PLATE_SCOPE, HtmlDeserializer, HtmlReactSerializer, HtmlSerializer, InferConfig, InjectNodeProps, KeyboardHandler, KeyofPlugins, LeafNodeProps, NavigationFeedbackPlugin, NodeProps, NodeWrapperComponent, NodeWrapperComponentProps, NodeWrapperComponentReturnType, NormalizeInitialValue, OnChange, OnNodeChange, OnTextChange, OverrideEditor, PLATE_SCOPE, ParagraphPlugin, Parser, Plate, PlateChangeKey, PlateChunkProps, PlateContainer, PlateContent, PlateContentProps, PlateController, PlateControllerEffect, PlateControllerEffectProps, PlateCorePlugin, PlateEditor, PlateElement, PlateElementProps, PlateHTMLProps, PlateLeaf, PlateLeafProps, PlateNodeProps, PlatePlugin, PlatePluginConfig, PlatePluginContext, PlatePluginMethods, PlatePlugins, PlateProps, PlateSlate, PlateStore, PlateStoreProvider, PlateStoreState, PlateTest, PlateText, PlateTextProps, PlateView, PlateViewProps, ReactPlugin, RenderElement, RenderLeaf, RenderNodeWrapper, RenderNodeWrapperFunction, RenderNodeWrapperProps, type RenderPlaceholderProps, RenderText, SCOPE_ELEMENT, Serializer, Shortcut, Shortcuts, Slate, SlateReactExtensionPlugin, StyledPlateElementProps, StyledPlateLeafProps, StyledPlateTextProps, TPlateEditor, TextNodeProps, TransformInitialValue, TransformOptions, UseEditorSelectorOptions, UseHooks, WithPlateOptions, atom, convertDomEventToSyntheticEvent, createAtomStore, createPlateEditor, createPlateFallbackEditor, createPlatePlugin, createPlateStore, createTPlatePlugin, createZustandStore, elementStore, getEditorPlugin, getEventPlateId, getPlateCorePlugins, getPlugin, getRenderNodeProps, isEventHandled, isHtmlVoidElementTag, omitPluginContext, pipeHandler, pipeOnChange, pipeRenderElement, pipeRenderLeaf, pipeRenderText, plateControllerStore, plateStore, pluginRenderElement, pluginRenderLeaf, pluginRenderText, toPlatePlugin, toTPlatePlugin, useBlockIdAttributeRef, useComposing, useEditableProps, useEditorComposing, useEditorContainerRef, useEditorId, useEditorMounted, useEditorPlugin, useEditorPluginOption, useEditorPluginOptions, useEditorReadOnly, useEditorRef, useEditorScrollRef, useEditorSelection, useEditorSelector, useEditorState, useEditorValue, useEditorVersion, useElement, useElementContext, useElementSelector, useElementStore, useElementStoreContext, useEventEditorValue, useEventPlateId, useFocusEditorEvents, useFocused, useFocusedLast, useIncrementVersion, useNavigationHighlight, useNodeAttributes, useNodePath, usePath, usePlateControllerExists, usePlateControllerLocalStore, usePlateControllerStore, usePlateEditor, usePlateLocalStore, usePlateSet, usePlateState, usePlateStore, usePlateValue, usePlateViewEditor, usePluginOption, usePluginOptions, useReadOnly, useRedecorate, useScrollRef, useSelected, useSelectionVersion, useSlateProps, useSlateStatic, useStoreAtomState, useStoreAtomValue, useStoreSelect, useStoreSetAtom, useStoreState, useStoreValue, useTracked, useTrackedStore, useValueVersion, withElementContext, withHOC, withPlate, withPlateReact, withReact };