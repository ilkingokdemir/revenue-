import React, { useEffect, useState, useMemo, useCallback } from "react";
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "./ui/command";
import { MagnifyingGlass, ArrowRight, Sparkle } from "@phosphor-icons/react";

/**
 * CommandPalette — global ⌘K / Ctrl+K finder.
 * Pass a flat catalogue of navigable items: [{ id, name, group, keywords, testId, hint }]
 * onSelect(id) is called when user picks an item.
 *
 * Also exposes a quick "AI shortcut" row at the top as a hint when query starts with "?".
 */
export default function CommandPalette({ items = [], onSelect, recents = [], onAskAi }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  // Global hotkey: ⌘K / Ctrl+K
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  // Group items by their `group` field
  const grouped = useMemo(() => {
    const m = new Map();
    for (const it of items) {
      const k = it.group || "Other";
      if (!m.has(k)) m.set(k, []);
      m.get(k).push(it);
    }
    return Array.from(m.entries());
  }, [items]);

  const askAi = query.startsWith("?");

  const pick = useCallback(
    (id) => {
      setOpen(false);
      setQuery("");
      onSelect && onSelect(id);
    },
    [onSelect]
  );

  return (
    <>
      {/* Trigger button (visible top of sidebar) */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-xs text-stone-400 hover:text-stone-200 bg-stone-900/60 hover:bg-stone-800 border border-stone-800 transition"
        data-testid="command-palette-trigger"
      >
        <span className="flex items-center gap-2">
          <MagnifyingGlass size={14} />
          <span>Ara veya komut çalıştır…</span>
        </span>
        <kbd className="hidden sm:inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-stone-800 text-[10px] font-mono text-stone-400 border border-stone-700">
          ⌘K
        </kbd>
      </button>

      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandInput
          placeholder="Bir şey ara… (örn: 'fatura', 'no show', 'rate'). '?' ile AI'ya sor."
          value={query}
          onValueChange={setQuery}
          data-testid="command-palette-input"
        />
        <CommandList>
          {askAi && (
            <CommandGroup heading="AI">
              <CommandItem
                value={`__ai_${query}`}
                onSelect={() => {
                  setOpen(false);
                  const q = query.replace(/^\?+\s*/, "").trim();
                  setQuery("");
                  onAskAi && onAskAi(q);
                }}
                data-testid="command-palette-ai-ask"
              >
                <Sparkle size={16} className="text-violet-400" />
                <span className="ml-2">
                  <span className="text-stone-300">AI'ya sor:</span>{" "}
                  <span className="text-violet-300 font-medium">
                    "{query.replace(/^\?+\s*/, "")}"
                  </span>
                </span>
                <ArrowRight size={14} className="ml-auto text-stone-500" />
              </CommandItem>
            </CommandGroup>
          )}

          <CommandEmpty>Sonuç yok. '?' yazıp AI'ya sorabilirsiniz.</CommandEmpty>

          {!askAi && recents?.length > 0 && (
            <>
              <CommandGroup heading="Son ziyaret edilen">
                {recents.slice(0, 5).map((it) => (
                  <CommandItem
                    key={`recent-${it.id}`}
                    value={`recent-${it.name}-${it.id}`}
                    onSelect={() => pick(it.id)}
                    data-testid={`command-palette-recent-${it.id}`}
                  >
                    {it.icon ? (
                      <it.icon size={16} className="text-stone-400" />
                    ) : (
                      <span className="w-4 inline-block" />
                    )}
                    <span className="ml-2">{it.name}</span>
                    {it.group && (
                      <span className="ml-auto text-[10px] text-stone-500">{it.group}</span>
                    )}
                  </CommandItem>
                ))}
              </CommandGroup>
              <CommandSeparator />
            </>
          )}

          {!askAi &&
            grouped.map(([group, list]) => (
              <CommandGroup key={group} heading={group}>
                {list.map((it) => (
                  <CommandItem
                    key={`${group}-${it.id}`}
                    value={`${it.name} ${it.keywords || ""} ${it.id}`}
                    onSelect={() => pick(it.id)}
                    data-testid={`command-palette-item-${it.id}`}
                  >
                    {it.icon ? (
                      <it.icon size={16} className="text-stone-400" />
                    ) : (
                      <span className="w-4 inline-block" />
                    )}
                    <span className="ml-2 truncate">{it.name}</span>
                    {it.hint && (
                      <span className="ml-auto text-[10px] text-stone-500">{it.hint}</span>
                    )}
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
        </CommandList>

        <div className="px-3 py-2 border-t border-stone-800 bg-stone-950/40 text-[10px] text-stone-500 flex items-center justify-between">
          <span>
            <kbd className="px-1 py-0.5 rounded bg-stone-800 border border-stone-700 font-mono">↑↓</kbd>{" "}
            gez ·{" "}
            <kbd className="px-1 py-0.5 rounded bg-stone-800 border border-stone-700 font-mono">↵</kbd>{" "}
            seç ·{" "}
            <kbd className="px-1 py-0.5 rounded bg-stone-800 border border-stone-700 font-mono">esc</kbd>{" "}
            kapat
          </span>
          <span className="text-stone-600">MyHotelBox · Command</span>
        </div>
      </CommandDialog>
    </>
  );
}
