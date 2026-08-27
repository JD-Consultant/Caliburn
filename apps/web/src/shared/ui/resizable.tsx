"use client";

import { GripVerticalIcon } from "lucide-react";
import type { ComponentProps } from "react";
import {
  Group as ResizablePanelGroupPrimitive,
  Panel as ResizablePanelPrimitive,
  Separator as ResizableHandlePrimitive,
} from "react-resizable-panels";

import { cn } from "@/shared/lib/utils";

function ResizablePanelGroup({
  className,
  orientation = "horizontal",
  ...props
}: ComponentProps<typeof ResizablePanelGroupPrimitive>) {
  return (
    <ResizablePanelGroupPrimitive
      data-slot="resizable-panel-group"
      data-orientation={orientation}
      orientation={orientation}
      className={cn(
        "flex h-full w-full data-[orientation=vertical]:flex-col",
        className,
      )}
      {...props}
    />
  );
}

function ResizablePanel(
  props: ComponentProps<typeof ResizablePanelPrimitive>,
) {
  return <ResizablePanelPrimitive data-slot="resizable-panel" {...props} />;
}

function ResizableHandle({
  withHandle = false,
  className,
  ...props
}: ComponentProps<typeof ResizableHandlePrimitive> & {
  withHandle?: boolean;
}) {
  return (
    <ResizableHandlePrimitive
      data-slot="resizable-handle"
      className={cn(
        "relative flex w-px items-center justify-center bg-border outline-none",
        "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
        "aria-[orientation=vertical]:h-px aria-[orientation=vertical]:w-full",
        className,
      )}
      {...props}
    >
      {withHandle ? (
        <span className="z-10 flex h-4 w-3 items-center justify-center rounded-sm border bg-background">
          <GripVerticalIcon className="size-2.5" aria-hidden="true" />
        </span>
      ) : null}
    </ResizableHandlePrimitive>
  );
}

export { ResizableHandle, ResizablePanel, ResizablePanelGroup };
