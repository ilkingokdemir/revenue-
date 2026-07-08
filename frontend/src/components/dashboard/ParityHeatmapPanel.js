/**
 * Rate Parity Heatmap — 60-day calendar showing our rate vs competitor average.
 * Cells colour-coded: red (overpriced >+10%), green (parity ±10%), amber
 * (underpriced <-10%, leaving money on the table), grey (no comp data).
 *
 * Hover/click a cell to see competitor breakdown + occupancy.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { Loader2, RefreshCw, Calendar, TrendingUp, TrendingDown, Minus } from "lucide-react";
import ChartLegend from "./ChartLegend";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => v == null ? "—" : `£${Number(v).toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;

const CLASS_BG = {
  underpriced: "bg-amber-500/30 hover:bg-amber-500/50 border-amber-500/50",
  parity:      "bg-emerald-500/25 hover:bg-emerald-500/45 border-emerald-500/40",
  overpriced:  "bg-rose-500/30 hover:bg-rose-500/50 border-rose-500/50",
  no_data:     "bg-stone-700/20 hover:bg-stone-700/35 border-stone-700",
};
const CLASS_LABEL = {
  underpriced: "Düşük fiyatlı — Fırsat (rakipten %5+ ucuz)",
  parity:      "Pariteli (rakiple ±5%)",
  overpriced:  "Yüksek fiyatlı — Pazar payı kaybı (rakipten %5+ pahalı)",
  no_data:     "Rakip verisi yok",
};

export default function ParityHeatmapPanel({ propertyId, hotelName = "" }) {
  const [days, setDays] = useState(60);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(null);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/parity/heatmap/${propertyId}?days=${days}`);
      setData(data);
    } catch { /* noop */ }
    setLoading(false);
  }, [propertyId, days]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setData(null); setActive(null); }, [propertyId]);

  // Group cells into weeks (rows of 7) starting Mon
  const cells = data?.cells || [];
  const summary = data?.summary || {};

  return (
    <div className="p-5 space-y-5" data-testid="parity-heatmap-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-stone-100 flex items-center gap-2">
            <Calendar className="w-5 h-5 text-orange-400" />
            Rate Parity Heatmap
            {hotelName && <><span className="text-stone-500 mx-1">·</span><span className="text-violet-400">{hotelName}</span></>}
          </h2>
          <p className="text-xs text-stone-400">Future {days} days · our rate vs competitor average</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-stone-900 border border-stone-800 rounded-xl p-0.5" data-testid="parity-days">
            {[30, 60, 90, 180].map(d => (
              <button key={d} onClick={() => setDays(d)}
                className={`px-2.5 py-1 text-xs font-bold rounded-lg ${days === d ? "bg-orange-600 text-white" : "text-stone-400 hover:text-white"}`}
                data-testid={`parity-days-${d}`}>{d}d</button>
            ))}
          </div>
          <button onClick={load} disabled={loading} className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-white text-xs font-bold" data-testid="parity-refresh">
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
            Refresh
          </button>
        </div>
      </div>

      {/* Summary chips */}
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="parity-summary">
          <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-3">
            <div className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-1">Avg Δ vs comp</div>
            <div className={`text-2xl font-black ${summary.avg_delta_pct == null ? "text-stone-400" : summary.avg_delta_pct > 5 ? "text-rose-300" : summary.avg_delta_pct < -5 ? "text-amber-300" : "text-emerald-300"}`}>
              {summary.avg_delta_pct == null ? "—" : `${summary.avg_delta_pct > 0 ? "+" : ""}${summary.avg_delta_pct}%`}
            </div>
          </div>
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-3">
            <div className="text-[10px] uppercase tracking-widest text-amber-400 font-bold mb-1">Underpriced</div>
            <div className="text-2xl font-black text-amber-300">{summary.underpriced_days || 0}<span className="text-xs text-amber-400 ml-1">d</span></div>
          </div>
          <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-2xl p-3">
            <div className="text-[10px] uppercase tracking-widest text-emerald-400 font-bold mb-1">On Parity</div>
            <div className="text-2xl font-black text-emerald-300">{summary.parity_days || 0}<span className="text-xs text-emerald-400 ml-1">d</span></div>
          </div>
          <div className="bg-rose-500/10 border border-rose-500/30 rounded-2xl p-3">
            <div className="text-[10px] uppercase tracking-widest text-rose-400 font-bold mb-1">Overpriced</div>
            <div className="text-2xl font-black text-rose-300">{summary.overpriced_days || 0}<span className="text-xs text-rose-400 ml-1">d</span></div>
          </div>
          <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-3">
            <div className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-1">No data</div>
            <div className="text-2xl font-black text-stone-400">{summary.no_data_days || 0}<span className="text-xs text-stone-500 ml-1">d</span></div>
          </div>
        </div>
      )}

      {/* Grid */}
      {cells.length > 0 && (
        <div className="bg-stone-900/40 border border-stone-800 rounded-2xl p-4" data-testid="parity-grid">
          <ChartLegend
            testId="parity-legend"
            items={[
              { color: "#f59e0b", label: CLASS_LABEL.underpriced, testId: "legend-underpriced" },
              { color: "#10b981", label: CLASS_LABEL.parity, testId: "legend-parity" },
              { color: "#f43f5e", label: CLASS_LABEL.overpriced, testId: "legend-overpriced" },
              { color: "#57534e", label: CLASS_LABEL.no_data, testId: "legend-no-data" },
            ]}
          />
          <div className="grid grid-cols-7 gap-1.5 text-center text-[10px] text-stone-500 font-bold uppercase mb-1 mt-3">
            {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(d => <div key={d}>{d}</div>)}
          </div>
          {/* Pad to first Mon (0=Mon) */}
          {(() => {
            const first = cells[0];
            const dow = new Date(first.date).getDay();
            const pad = (dow + 6) % 7;
            const padded = [...Array(pad).fill(null), ...cells];
            const rows = [];
            for (let i = 0; i < padded.length; i += 7) rows.push(padded.slice(i, i + 7));
            return rows.map((row, ri) => (
              <div key={ri} className="grid grid-cols-7 gap-1.5 mb-1.5">
                {row.map((c, ci) => {
                  if (!c) return <div key={ci} />;
                  const cls = CLASS_BG[c.class] || CLASS_BG.no_data;
                  const isActive = active?.date === c.date;
                  return (
                    <button key={c.date} onClick={() => setActive(c)}
                      data-testid={`parity-cell-${c.date}`}
                      className={`relative aspect-[5/4] rounded-lg border ${cls} text-left p-1.5 transition transform ${isActive ? "ring-2 ring-cyan-400 scale-[1.03] z-10" : ""}`}>
                      <div className="text-[9px] text-stone-300 font-mono">{new Date(c.date).getDate()}</div>
                      <div className="text-[10px] text-stone-100 font-black tabular-nums leading-tight">{cur(c.our_rate)}</div>
                      {c.delta_pct != null && (
                        <div className={`text-[9px] font-bold tabular-nums leading-tight ${c.delta_pct > 5 ? "text-rose-200" : c.delta_pct < -5 ? "text-amber-100" : "text-emerald-200"}`}>
                          {c.delta_pct > 0 ? "+" : ""}{c.delta_pct}%
                        </div>
                      )}
                      {c.is_weekend && <span className="absolute top-0 right-1 text-[8px] text-stone-400">·</span>}
                    </button>
                  );
                })}
              </div>
            ));
          })()}
        </div>
      )}

      {/* Detail drawer */}
      {active && (
        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-4" data-testid="parity-detail">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-sm font-bold text-stone-100">{new Date(active.date).toLocaleDateString("en", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}</h3>
              <p className="text-[11px] text-stone-400">{CLASS_LABEL[active.class]}</p>
            </div>
            <button onClick={() => setActive(null)} className="text-stone-500 hover:text-white text-xs">close</button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <Stat label="Our rate" value={cur(active.our_rate)} hint={active.our_set_by ? `set by ${active.our_set_by}` : "base"} />
            <Stat label="Comp avg" value={cur(active.comp_avg)} hint={`${active.comp_count} comp(s)`} />
            <Stat label="Comp range" value={`${cur(active.comp_min)}–${cur(active.comp_max)}`} />
            <Stat label="Occupancy" value={`${active.occ_pct}%`} hint={active.is_weekend ? "weekend" : ""} />
          </div>
          {(active.competitors || []).length > 0 && (
            <div>
              <div className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-2">Competitor prices</div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-1.5">
                {(active.competitors || []).map((c, i) => (
                  <div key={i} className="flex items-center justify-between bg-stone-800/50 rounded-lg px-3 py-1.5 text-xs">
                    <span className="truncate text-stone-300">{c.name}</span>
                    <span className="font-black tabular-nums text-stone-100">{cur(c.price)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!loading && cells.length === 0 && (
        <div className="text-center py-16 text-stone-500" data-testid="parity-empty">
          <Calendar className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="text-sm">No data yet — run Market Robot scrape first.</p>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, hint }) {
  return (
    <div className="bg-stone-800/60 rounded-xl p-3">
      <div className="text-[9px] uppercase tracking-widest text-stone-500 font-bold mb-0.5">{label}</div>
      <div className="text-lg font-black text-stone-100 tabular-nums">{value}</div>
      {hint && <div className="text-[9px] text-stone-500 mt-0.5">{hint}</div>}
    </div>
  );
}
