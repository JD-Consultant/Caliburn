"use client";

import { AlertDialog } from "@base-ui/react/alert-dialog";
import { Menu } from "@base-ui/react/menu";
import { MoreHorizontal } from "lucide-react";

import { Button } from "@/shared/ui/button";

export type LifecycleAction = {
  label: string;
  onSelect: () => void;
  danger?: boolean;
  disabled?: boolean;
};

const menuItemClass =
  "flex cursor-default items-center rounded-lg px-3 py-2 text-sm outline-none data-[highlighted]:bg-stone-100 data-[disabled]:text-stone-400";

export function DocumentLifecycleMenu({
  label,
  actions,
  disabled = false,
}: {
  label: string;
  actions: LifecycleAction[];
  disabled?: boolean;
}) {
  return (
    <Menu.Root>
      <Menu.Trigger
        aria-label={label}
        disabled={disabled}
        className="inline-flex size-8 items-center justify-center rounded-lg text-stone-500 hover:bg-stone-100 disabled:opacity-40"
      >
        <MoreHorizontal className="size-4" />
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Positioner sideOffset={6} className="z-50 outline-none">
          <Menu.Popup className="min-w-52 rounded-xl border border-stone-200 bg-white p-1.5 shadow-xl outline-none">
            {actions.map((action) => (
              <Menu.Item
                key={action.label}
                disabled={action.disabled}
                className={`${menuItemClass} ${action.danger ? "text-rose-700" : "text-stone-800"}`}
                onClick={action.onSelect}
              >
                {action.label}
              </Menu.Item>
            ))}
          </Menu.Popup>
        </Menu.Positioner>
      </Menu.Portal>
    </Menu.Root>
  );
}

export type LifecycleConfirmation = {
  title: string;
  description: string;
  affectedNames: string[];
  confirmLabel: string;
};

export function LifecycleConfirmationDialog({
  confirmation,
  pending,
  onCancel,
  onConfirm,
}: {
  confirmation: LifecycleConfirmation | null;
  pending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <AlertDialog.Root
      open={confirmation !== null}
      onOpenChange={(open) => !open && onCancel()}
    >
      <AlertDialog.Portal>
        <AlertDialog.Backdrop className="fixed inset-0 z-50 bg-black/20 backdrop-blur-[1px]" />
        <AlertDialog.Popup className="fixed top-1/2 left-1/2 z-50 w-[min(30rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-stone-200 bg-white p-5 shadow-2xl outline-none">
          <AlertDialog.Title className="text-base font-semibold text-stone-950">
            {confirmation?.title}
          </AlertDialog.Title>
          <AlertDialog.Description className="mt-2 text-sm leading-6 text-stone-600">
            {confirmation?.description}
          </AlertDialog.Description>
          {confirmation?.affectedNames.length ? (
            <ul className="mt-3 max-h-40 list-disc space-y-1 overflow-y-auto rounded-xl bg-stone-50 px-7 py-3 text-sm text-stone-700">
              {confirmation.affectedNames.map((name) => (
                <li key={name}>{name}</li>
              ))}
            </ul>
          ) : null}
          <div className="mt-5 flex justify-end gap-2">
            <AlertDialog.Close
              disabled={pending}
              className="inline-flex h-9 items-center justify-center rounded-lg border border-stone-300 bg-white px-3 text-sm font-medium"
            >
              取消
            </AlertDialog.Close>
            <Button
              type="button"
              variant="destructive"
              disabled={pending}
              onClick={onConfirm}
            >
              {pending ? "處理中…" : confirmation?.confirmLabel}
            </Button>
          </div>
        </AlertDialog.Popup>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}
