/**
 * Standardized chart legend — used across all dashboard visualisations
 * for consistent color-encoding explanations.
 *
 * items prop: Array of:
 *   {color: "#ef4444", label: "Yüksek talep", testId?: "..." , kind?: "swatch"|"line"|"dashed"}
 *
 * Default kind = "swatch" (small filled box).
 */
export default function ChartLegend({ items, title = "Lejant", dense = false, dark = true, testId }) {
  const baseBg = dark
    ? "bg-stone-800/60 border-stone-700 text-stone-200"
    : "bg-stone-50 border-stone-200 text-stone-700";
  return (
    <div className={`flex flex-wrap items-center gap-x-3 gap-y-1 ${dense ? "px-2 py-1 text-[9px]" : "px-3 py-1.5 text-[10px]"} ${baseBg} rounded-lg border`}
         data-testid={testId || "chart-legend"}>
      {title && <span className="text-stone-400 font-semibold mr-1">{title}:</span>}
      {items.map((it, i) => {
        const c = it.color;
        let swatch;
        if (it.kind === "line") {
          swatch = <span className="w-4 h-[2px]" style={{ backgroundColor: c }} />;
        } else if (it.kind === "dashed") {
          swatch = <span className="w-4 h-0 border-t border-dashed" style={{ borderColor: c }} />;
        } else {
          swatch = <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: c }} />;
        }
        return (
          <span key={i} className="flex items-center gap-1.5" title={it.title || it.label}
                data-testid={it.testId || `legend-item-${i}`}>
            {swatch}
            <span>{it.label}</span>
          </span>
        );
      })}
    </div>
  );
}
