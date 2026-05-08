import React from "react";
import { CaretRight, MagnifyingGlass } from "@phosphor-icons/react";
import { useTranslation } from "@/i18n";

/**
 * SectionHub — Mews/Eviivo-style landing page for a top-level navigation section.
 *
 * Reads `section.items` from the menu and groups them into 2-3 columns of clean
 * cards. Clicking any card navigates to the actual feature panel.
 *
 * Props:
 *   - section: { label, items: [{id, name, icon, testId, ...}] }
 *   - onSelect: (itemId) => void
 *   - subtitle?: string
 *   - tNav?: (item) => string  — optional translator (passed from App.js)
 *   - tSectionLabel?: (sectionOrLabel) => string  — optional section translator
 */
export default function SectionHub({ section, onSelect, subtitle, tNav, tSectionLabel }) {
  const { t } = useTranslation();
  const [query, setQuery] = React.useState("");

  // Local fallbacks if no translator was passed (i.e. used standalone)
  const trItem = React.useCallback(
    (item) => {
      if (tNav) return tNav(item);
      const key = `nav.${(item?.id || "").replace(/-/g, "_")}`;
      const out = t(key);
      return out && out !== key ? out : (item?.name || item?.id || "");
    },
    [tNav, t]
  );

  const trSection = React.useCallback(
    (lbl) => {
      if (tSectionLabel) return tSectionLabel(lbl);
      const label = typeof lbl === "string" ? lbl : (lbl?.label || "");
      const key = `section_label.${label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "")}`;
      const out = t(key);
      return out && out !== key ? out : label;
    },
    [tSectionLabel, t]
  );

  if (!section || !section.items?.length) {
    return (
      <div className="p-6 text-center text-stone-400">
        {t("ui.no_items_in_section")}
      </div>
    );
  }

  const sectionLabelTranslated = trSection(section);
  const items = section.items.filter((it) => {
    if (!query) return true;
    const q = query.toLowerCase();
    const name = (trItem(it) || "").toLowerCase();
    const original = (it.name || "").toLowerCase();
    return name.includes(q) || original.includes(q);
  });

  return (
    <div
      className="p-5 max-w-[1400px] mx-auto"
      data-testid={`section-hub-${(section.label || "").toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
    >
      <div className="mb-6">
        <div className="text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          {t("ui.hub_label")}
        </div>
        <h1 className="text-3xl font-semibold text-stone-900">{sectionLabelTranslated}</h1>
        {subtitle && <p className="text-sm text-stone-500 mt-1 max-w-2xl">{subtitle}</p>}
      </div>

      <div className="relative mb-6">
        <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
        <input
          type="text"
          placeholder={t("ui.search_in_section", { label: sectionLabelTranslated })}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          data-testid="hub-search"
          className="w-full pl-9 pr-3 py-2.5 text-sm border border-stone-200 rounded-md focus:outline-none focus:border-stone-400 bg-white"
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              onClick={() => onSelect(item.id)}
              data-testid={`hub-card-${item.testId}`}
              className="group bg-white border border-stone-200 hover:border-stone-300 hover:shadow-sm rounded-xl p-4 text-left transition-all flex items-center gap-3"
            >
              <div className="w-10 h-10 rounded-lg bg-stone-100 group-hover:bg-stone-900 group-hover:text-white inline-flex items-center justify-center transition-colors shrink-0">
                {Icon ? <Icon size={18} weight="regular" /> : <span className="text-xs font-mono">?</span>}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-stone-900 group-hover:text-stone-900 truncate">
                  {trItem(item)}
                </div>
                <div className="text-[11px] text-stone-400 font-mono truncate">{item.id}</div>
              </div>
              <CaretRight size={12} weight="bold" className="text-stone-300 group-hover:text-stone-600 transition-colors shrink-0" />
            </button>
          );
        })}
      </div>

      {items.length === 0 && (
        <div className="text-center py-12 text-stone-400 text-sm" data-testid="hub-no-results">
          {t("ui.no_items_match", { q: query })}
        </div>
      )}
    </div>
  );
}
