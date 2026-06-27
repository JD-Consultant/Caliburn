"use client";
import { useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Button } from "@/components/ui/button";

type Opt = { ocs_code: string; name: string };
export function FieldBoundSelect({ value, options, onCommit }: { value: Opt; options: Opt[]; onCommit: (o: Opt) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button type="button" variant="outline" size="sm" className="w-full justify-between gap-1 text-xs">
          <span className="truncate">{value.ocs_code ? `${value.ocs_code}　${value.name}` : "選擇職能基準…"}</span>
          <ChevronsUpDown className="h-3.5 w-3.5 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80">
        <Command>
          <CommandInput placeholder="搜尋職能基準…" />
          <CommandList>
            <CommandEmpty>無候選</CommandEmpty>
            <CommandGroup>
              {options.map((o) => (
                <CommandItem key={o.ocs_code} value={`${o.ocs_code} ${o.name}`} onSelect={() => { onCommit(o); setOpen(false); }}>
                  <Check className={"h-3.5 w-3.5 " + (value.ocs_code === o.ocs_code ? "opacity-100" : "opacity-0")} />
                  <span className="font-mono text-xs text-muted-foreground">{o.ocs_code}</span>
                  <span className="flex-1">{o.name}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
