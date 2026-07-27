/** Portföy Panosu — Market Pulse tarzı koyu tema: birleşik kartlar + metrik filtreli ısı haritası + tesis YoY tabloları + kurtarma planı */
import { useState } from "react";

const symOf = (c) => ({ GBP: "£", EUR: "€", TRY: "₺", USD: "$", CHF: "CHF ", MIX: "Σ " }[c] || c + " ");
const fmt = (n) => (n || 0).toLocaleString("tr-TR", { maximumFractionDigits: 0 });
const METRICS = [["occ", "Doluluk"], ["adr", "ADR"], ["avail", "Müsait Oda"]];

export default function PortfolioBoard({ data, fetchRecovery }) {
  const [metric, setMetric] = useState("occ");
  const [q, setQ] = useState("");
  const [plan, setPlan] = useState(null);
  const [planLoading, setPlanLoading] = useState("");

  if (!data) return <div className="text-center py-12 text-stone-400 text-sm">Yükleniyor…</div>;
  const c = symOf(data.currency);
  const rows = data.heatmap.rows.filter((r) => r.name.toLowerCase().includes(q.toLowerCase()));

  const openPlan = async (pid) => {
    if (!fetchRecovery) return;
    setPlanLoading(pid);
    try { setPlan(await fetchRecovery(pid)); } catch { /* noop */ }
    setPlanLoading("");
  };

  const cellView = (cell) => {
    if (metric === "adr") {
      const col = cell.adr > 0 ? "#7dd3fc" : "#57534e";
      return <span style={{ color: col }} className="font-semibold">{cell.adr > 0 ? fmt(cell.adr) : "—"}</span>;
    }
    if (metric === "avail") {
      const col = cell.avail === 0 ? "#5eead4" : cell.avail <= 3 ? "#fcd34d" : "#a8a29e";
      return <span style={{ color: col }} className="font-semibold">{cell.avail}</span>;
    }
    const col = cell.occ >= 70 ? "#5eead4" : cell.occ >= 40 ? "#fcd34d" : cell.occ > 0 ? "#fda4af" : "#57534e";
    return (<><span style={{ color: col }} className="font-semibold">{cell.occ}%</span>{cell.pace > 0 && <span className="text-emerald-400 ml-0.5">▲</span>}</>);
  };
  const cellBg = (cell) => {
    if (metric !== "occ") return "transparent";
    return cell.occ >= 70 ? "rgba(45,212,191,0.18)" : cell.occ >= 40 ? "rgba(251,191,36,0.14)" : cell.occ > 0 ? "rgba(244,63,94,0.12)" : "transparent";
  };

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
        <div className="px-4 py-2.5 border-b border-stone-800 flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-1">
            {METRICS.map(([id, label]) => (
              <button key={id} onClick={() => setMetric(id)} data-testid={`pf-metric-${id}`}
                className={`text-[10px] px-2.5 py-1 rounded-md font-bold border ${metric === id ? "bg-teal-500/20 border-teal-500/40 text-teal-200" : "bg-stone-800/60 border-stone-700 text-stone-400"}`}>
                {label}
              </button>
            ))}
            <span className="text-[10px] text-stone-600 ml-2">▲ 7g pickup · ⚠ ort. doluluk %35 altı → tıkla: kurtarma planı</span>
          </div>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Otel ara…" data-testid="pf-search"
            className="text-[11px] px-2.5 py-1 rounded-md bg-stone-800 border border-stone-700 text-stone-200 w-40" />
        </div>
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
              {rows.map((r) => (
                <tr key={r.property_id} className="border-t border-stone-800/60" data-testid={`pf-heat-row-${r.property_id}`}>
                  <td className="sticky left-0 bg-stone-900 px-3 py-1.5 z-10">
                    <button onClick={() => openPlan(r.property_id)} data-testid={`pf-recovery-${r.property_id}`}
                      className="flex items-center gap-1.5 text-left hover:opacity-80" title="Kurtarma planı için tıkla">
                      {r.risk && <span className="text-amber-400">⚠</span>}
                      <div>
                        <div className="text-[11px] font-semibold text-stone-200 whitespace-nowrap">{r.name}{planLoading === r.property_id && <span className="text-stone-500 ml-1">…</span>}</div>
                        <div className="text-[9px] text-stone-600">{r.rooms} oda · ort. {r.avg_occ}%</div>
                      </div>
                    </button>
                  </td>
                  {r.cells.map((cell, i) => (
                    <td key={i} className="px-1 py-1.5 text-center" style={{ background: cellBg(cell) }}>{cellView(cell)}</td>
                  ))}
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

      {plan && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={() => setPlan(null)}>
          <div className="bg-stone-950 border border-stone-700 rounded-2xl max-w-lg w-full max-h-[85vh] overflow-y-auto p-5" onClick={(e) => e.stopPropagation()} data-testid="pf-recovery-modal">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-base font-bold text-stone-100">Kurtarma Planı — {plan.property_name}</div>
                <div className="text-[11px] text-stone-500 mt-0.5">30 gün ort. doluluk {plan.avg_occ_30d}% · {plan.weak_days} zayıf gün · ADR {symOf(plan.currency)}{plan.my_adr}{plan.market_wap ? ` · Pazar ${symOf(plan.currency)}${plan.market_wap}` : ""}</div>
              </div>
              <button onClick={() => setPlan(null)} data-testid="pf-recovery-close" className="text-stone-500 hover:text-stone-200 text-lg leading-none">✕</button>
            </div>
            <div className="space-y-2 mt-4">
              {plan.actions.map((a, i) => (
                <div key={i} className={`rounded-lg border p-3 ${a.impact === "yüksek" ? "border-rose-500/40 bg-rose-500/5" : "border-stone-700 bg-stone-900/60"}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-stone-100">{i + 1}. {a.title}</span>
                    <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase ${a.impact === "yüksek" ? "bg-rose-500/20 text-rose-300" : "bg-amber-500/15 text-amber-300"}`}>{a.impact} etki</span>
                  </div>
                  <div className="text-[11px] text-stone-400 mt-1">{a.desc}</div>
                </div>
              ))}
            </div>
            {plan.weak_dates.length > 0 && (
              <div className="mt-4">
                <div className="text-[10px] uppercase text-stone-500 font-semibold mb-1.5">Zayıf tarihler (ilk 14)</div>
                <div className="flex flex-wrap gap-1">
                  {plan.weak_dates.map((d) => <span key={d} className="text-[10px] px-1.5 py-0.5 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300">{d.slice(5)}</span>)}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
