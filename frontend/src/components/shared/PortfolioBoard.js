/** Portföy Panosu — Market Pulse tarzı koyu tema: birleşik kartlar + doluluk ısı haritası + tesis YoY tabloları */
const symOf = (c) => ({ GBP: "£", EUR: "€", TRY: "₺", USD: "$", CHF: "CHF ", MIX: "Σ " }[c] || c + " ");
const fmt = (n) => (n || 0).toLocaleString("tr-TR", { maximumFractionDigits: 0 });

export default function PortfolioBoard({ data }) {
  if (!data) return <div className="text-center py-12 text-stone-400 text-sm">Yükleniyor…</div>;
  const c = symOf(data.currency);

  return (
    <div className="rounded-2xl bg-stone-950 border border-stone-800 p-5 space-y-5" data-testid="portfolio-board">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <div className="text-lg font-bold text-stone-100">Portföy Panosu</div>
          <div className="text-[11px] text-stone-500">{data.heatmap.rows.length} tesis · riske göre sıralı{data.currency_mixed ? " · karma para birimi toplamı (Σ)" : ""}</div>
        </div>
        <span className="text-[10px] px-2 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 font-bold">● TÜM SİSTEMLER CANLI</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {data.month_cards.map((m) => (
          <div key={m.label} className="rounded-xl border border-stone-800 bg-stone-900/70 p-4" data-testid={`pf-card-${m.tag}`}>
            <div className="flex items-center justify-between">
              <div className="text-[10px] uppercase tracking-wider text-stone-500">{m.label} · {m.month} ({m.tag})</div>
              {m.yoy_pct != null && (
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${m.yoy_pct >= 0 ? "bg-emerald-500/15 text-emerald-300" : "bg-rose-500/15 text-rose-300"}`}>
                  YoY {m.yoy_pct >= 0 ? "+" : ""}{m.yoy_pct}%
                </span>
              )}
            </div>
            <div className="text-3xl font-bold text-teal-300 mt-2">{c}{fmt(m.revenue)}</div>
            <div className="text-[9px] uppercase text-stone-600 mb-3">Toplam Gelir</div>
            <div className="text-[11px] space-y-1">
              <div className="flex justify-between text-stone-600"><span></span><span className="flex gap-4"><span className="w-16 text-right">Bu yıl</span><span className="w-16 text-right">Geçen yıl</span></span></div>
              {[["Gelir", `${c}${fmt(m.revenue)}`, `${c}${fmt(m.ly_revenue)}`], ["Doluluk", `${m.occ}%`, `${m.ly_occ}%`], ["ADR", `${c}${Math.round(m.adr)}`, `${c}${Math.round(m.ly_adr)}`]].map(([l, a, b]) => (
                <div key={l} className="flex justify-between"><span className="text-stone-500">{l}</span><span className="flex gap-4"><span className="w-16 text-right font-semibold text-stone-200">{a}</span><span className="w-16 text-right text-stone-500">{b}</span></span></div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-stone-800 bg-stone-900/50 overflow-hidden" data-testid="pf-heatmap">
        <div className="px-4 py-2.5 border-b border-stone-800 text-xs font-semibold text-stone-300">30 Günlük Doluluk Isı Haritası <span className="text-stone-600 font-normal">· ▲ son 7 günde pickup · ⚠ ort. doluluk %35 altı</span></div>
        <div className="overflow-x-auto">
          <table className="text-[10px] border-collapse">
            <thead>
              <tr>
                <th className="sticky left-0 bg-stone-900 text-left px-3 py-2 text-stone-500 uppercase text-[9px] min-w-[170px] z-10">Otel</th>
                {data.heatmap.days.map((d) => (
                  <th key={d.date} className="px-1 py-2 text-stone-600 font-normal min-w-[42px] text-center">
                    <div>{d.dow}</div><div className="text-stone-500">{d.date.slice(8)}.{d.date.slice(5, 7)}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.heatmap.rows.map((r) => (
                <tr key={r.property_id} className="border-t border-stone-800/60" data-testid={`pf-heat-row-${r.property_id}`}>
                  <td className="sticky left-0 bg-stone-900 px-3 py-1.5 z-10">
                    <div className="flex items-center gap-1.5">
                      {r.risk && <span className="text-amber-400" title="Riskli — düşük doluluk">⚠</span>}
                      <div>
                        <div className="text-[11px] font-semibold text-stone-200 whitespace-nowrap">{r.name}</div>
                        <div className="text-[9px] text-stone-600">{r.rooms} oda · ort. {r.avg_occ}%</div>
                      </div>
                    </div>
                  </td>
                  {r.cells.map((cell, i) => {
                    const bg = cell.occ >= 70 ? "rgba(45,212,191,0.18)" : cell.occ >= 40 ? "rgba(251,191,36,0.14)" : cell.occ > 0 ? "rgba(244,63,94,0.12)" : "transparent";
                    const col = cell.occ >= 70 ? "#5eead4" : cell.occ >= 40 ? "#fcd34d" : cell.occ > 0 ? "#fda4af" : "#57534e";
                    return (
                      <td key={i} className="px-1 py-1.5 text-center" style={{ background: bg }}>
                        <span style={{ color: col }} className="font-semibold">{cell.occ}%</span>
                        {cell.pace > 0 && <span className="text-emerald-400 ml-0.5">▲</span>}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-3" data-testid="pf-monthly-tables">
        {data.properties.map((p) => {
          const pc = symOf(p.currency);
          return (
            <div key={p.property_id} className="rounded-xl border border-stone-800 bg-stone-900/50 overflow-hidden">
              <div className="px-4 py-2.5 border-b border-stone-800 flex items-center justify-between">
                <span className="text-xs font-bold text-stone-200 uppercase tracking-wide">{p.name}</span>
                <span className="text-[10px] text-stone-600">{p.rooms} oda</span>
              </div>
              <table className="w-full text-[11px]">
                <thead className="text-[8px] uppercase text-stone-600">
                  <tr>
                    <th className="text-left px-3 py-1.5">Ay</th>
                    <th className="text-right px-1">{data.prev_year} Occ</th><th className="text-right px-1">ADR</th><th className="text-right px-2">Gelir</th>
                    <th className="text-right px-1 border-l border-stone-800">{data.cur_year} Occ</th><th className="text-right px-1">ADR</th><th className="text-right px-2">Gelir</th>
                    <th className="text-right px-3">Var</th>
                  </tr>
                </thead>
                <tbody>
                  {p.months.map((m) => (
                    <tr key={m.month} className={`border-t border-stone-800/50 ${m.mtd ? "bg-teal-500/5" : ""}`}>
                      <td className="px-3 py-1 text-stone-400">{m.month}</td>
                      <td className="text-right px-1 text-stone-600">{m.p_occ}%</td><td className="text-right px-1 text-stone-600">{pc}{Math.round(m.p_adr)}</td><td className="text-right px-2 text-stone-500">{pc}{fmt(m.p_rev)}</td>
                      <td className="text-right px-1 border-l border-stone-800/50 text-stone-300">{m.c_occ}%</td><td className="text-right px-1 text-stone-300">{pc}{Math.round(m.c_adr)}</td><td className="text-right px-2 font-semibold text-teal-300">{pc}{fmt(m.c_rev)}</td>
                      <td className="text-right px-3">
                        {m.var_pct == null ? <span className="text-stone-700">—</span> : (
                          <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${m.var_pct >= 0 ? "bg-emerald-500/15 text-emerald-300" : "bg-rose-500/15 text-rose-300"}`}>{m.var_pct >= 0 ? "+" : ""}{m.var_pct}%</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        })}
      </div>
    </div>
  );
}
