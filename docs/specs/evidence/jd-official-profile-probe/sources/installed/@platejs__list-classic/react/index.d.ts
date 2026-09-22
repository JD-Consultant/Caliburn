import { n as TTodoListItemElement } from "../BaseTodoListPlugin-C3ztdXje";
import * as platejs0 from "platejs";
import * as platejs_react0 from "platejs/react";

//#region src/react/ListPlugin.d.ts
declare const BulletedListPlugin: platejs_react0.PlatePlugin<platejs0.PluginConfig<"ul", {}, {}, Record<"ul", {
  toggle: () => void;
}>, {}>>;
declare const TaskListPlugin: platejs_react0.PlatePlugin<platejs0.PluginConfig<"taskList", {
  inheritCheckStateOnLineEndBreak: boolean;
  inheritCheckStateOnLineStartBreak: boolean;
}, {}, Record<"taskList", {
  toggle: () => void;
}>, {}>>;
declare const NumberedListPlugin: platejs_react0.PlatePlugin<platejs0.PluginConfig<"ol", {}, {}, Record<"ol", {
  toggle: () => void;
}>, {}>>;
declare const ListItemContentPlugin: platejs_react0.PlatePlugin<platejs0.PluginConfig<"lic", {}, {}, {}, {}>>;
declare const ListItemPlugin: platejs_react0.PlatePlugin<platejs0.PluginConfig<"li", {}, {}, {}, {}>>;
/**
 * Enables support for bulleted, numbered and to-do lists with React-specific
 * features.
 */
declare const ListPlugin: platejs_react0.PlatePlugin<platejs0.PluginConfig<"listClassic", {
  enableResetOnShiftTab?: boolean;
  inheritCheckStateOnLineEndBreak?: boolean;
  inheritCheckStateOnLineStartBreak?: boolean;
  validLiChildrenTypes?: string[];
}, {}, {
  toggle: {
    bulletedList: (() => boolean) & (() => boolean);
    list: ((args_0: {
      type: string;
    }) => boolean) & ((args_0: {
      type: string;
    }) => boolean);
    numberedList: (() => boolean) & (() => boolean);
    taskList: ((defaultChecked?: boolean | undefined) => boolean) & ((defaultChecked?: boolean | undefined) => boolean);
  };
}, {}>>;
//#endregion
//#region src/react/TodoListPlugin.d.ts
declare const TodoListPlugin: platejs_react0.PlatePlugin<platejs0.PluginConfig<"action_item", {
  inheritCheckStateOnLineEndBreak: boolean;
  inheritCheckStateOnLineStartBreak: boolean;
}, {}, Record<"action_item", {
  toggle: () => void;
}>, {}>>;
//#endregion
//#region src/react/hooks/useListToolbarButton.d.ts
declare const useListToolbarButtonState: ({
  nodeType
}?: {
  nodeType?: string | undefined;
}) => {
  nodeType: string;
  pressed: boolean;
};
declare const useListToolbarButton: (state: ReturnType<typeof useListToolbarButtonState>) => {
  props: {
    pressed: boolean;
    onClick: () => void;
    onMouseDown: (e: React.MouseEvent<HTMLButtonElement>) => void;
  };
};
//#endregion
//#region src/react/hooks/useTodoListElement.d.ts
declare const useTodoListElementState: ({
  element
}: {
  element: TTodoListItemElement;
}) => any;
declare const useTodoListElement: (state: ReturnType<typeof useTodoListElementState>) => {
  checkboxProps: {
    checked: boolean;
    onCheckedChange: (value: boolean) => void;
  };
};
//#endregion
export { BulletedListPlugin, ListItemContentPlugin, ListItemPlugin, ListPlugin, NumberedListPlugin, TaskListPlugin, TodoListPlugin, useListToolbarButton, useListToolbarButtonState, useTodoListElement, useTodoListElementState };