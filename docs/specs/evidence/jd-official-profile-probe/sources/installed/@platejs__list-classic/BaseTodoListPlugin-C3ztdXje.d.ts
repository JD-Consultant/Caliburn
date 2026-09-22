import * as platejs12 from "platejs";
import { TElement } from "platejs";

//#region src/lib/BaseTodoListPlugin.d.ts
interface TTodoListItemElement extends TElement {
  checked?: boolean;
}
declare const BaseTodoListPlugin: platejs12.SlatePlugin<platejs12.PluginConfig<"action_item", {
  inheritCheckStateOnLineEndBreak: boolean;
  inheritCheckStateOnLineStartBreak: boolean;
}, {}, Record<"action_item", {
  toggle: () => void;
}>, {}>>;
//#endregion
export { TTodoListItemElement as n, BaseTodoListPlugin as t };