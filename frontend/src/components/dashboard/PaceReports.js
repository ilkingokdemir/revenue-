/**
 * Pace Reports — STLY (same time last year) + Pickup + Source contribution.
 *
 * Backed by GET /forecast/pace/{propertyId}?days=N (added in
 * routes/loyalty_logbook_forecast.py). One panel, three views — the trio every
 * revenue manager wants to see daily.
 */
import { useEffect, useState, useCallback, useMemo } from "react";
import axios from "axios";
import { Loader2, TrendingUp, Calendar, PoundSterling, BarChart3, ArrowUp, ArrowDown } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;

const SOURCE_COLOURS = {
  booking: "#003580", booking_com: "#003580", "booking.com": "#003580",
  direct: "#a78bfa", website_widget: "#a78bfa",
  expedia: "#fbcc33", airbnb: "#ff5a5f",
  google: "#4285f4", agoda: "#ff5722",
  corporate: "#10b981", phone: "#06b6d4", walk_in: "#94a3b8",
};
const colourFor = (s) => SOURCE_COLOURS[(s || "direct").toLowerCase()] || "#888";

export default function PaceReports({ propertyId, hotelName = "" }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/forecast/pace/${propertyId}?days=${days}`);
      setData(data);
    } catch { /* noop */ }
    setLoading(false);
  }, [propertyId, days]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setData(null); }, [propertyId]);  // branch hygiene

  // STLY chart geometry
  const stlyChart = useMemo(() => {
    if (!data?.stly?.length) return null;
    const pad = { l: 35, r: 10, t: 16, b: 24 };
    const W = 1000, H = 200;
    const iW = W - pad.l - pad.r, iH = H - pad.t - pad.b;
    const n = data.stly.length;
    const sx = (i) => pad.l + (i / Math.max(n - 1, 1)) * iW;
    const allVals = data.stly.flatMap(d => [d.ty_rooms, d.ly_rooms]);
    const maxV = Math.max(...allVals, 1) * 1.1;
    const sy = (v) => pad.t + iH - (v / maxV) * iH;
    const tyPath = data.stly.map((d, i) => `${i === 0 ? "M" : "L"} ${sx(i)} ${sy(d.ty_rooms)}`).join(" ");
    const lyPath = data.stly.map((d, i) => `${i === 0 ? "M" : "L"} ${sx(i)} ${sy(d.ly_rooms)}`).join(" ");
    return { pad, W, H, iW, iH, sx, sy, tyPath, lyPath, maxV };
  }, [data]);

  if (loading) return <div className="p-12 text-center text-stone-400"><Loader2 className="w-5 h-5 animate-spin inline mr-2" />Pace yükleniyor…</div>;
  if (!data) return <div className="p-12 text-center text-stone-500">Veri yok</div>;

  const totals = data.totals || {};
  const stlyDelta = totals.ty_total_rooms - totals.ly_total_rooms;
  const stlyDeltaPct = totals.ly_total_rooms > 0 ? ((stlyDelta / totals.ly_total_rooms) * 100).toFixed(1) : "—";
  const ahead = stlyDelta >= 0;

  return (
    <div className="p-5 space-y-5" data-testid="pace-reports">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-stone-100 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-cyan-400" />
            Pace Reports
            {hotelName && <><span className="text-stone-500 mx-1">·</span><span className="text-violet-400">{hotelName}</span></>}
          </h2>
          <p className="text-xs text-stone-400">STLY (same time last year) · Pickup · Source contribution</p>
        </div>
        <div className="flex items-center gap-1 bg-stone-900 border border-stone-800 rounded-xl p-0.5" data-testid="pace-days-picker">
          {[14, 30, 60, 90, 180].map(d => (
            <button key={d} onClick={() => setDays(d)}
              className={`px-2.5 py-1 text-xs font-bold rounded-lg ${days === d ? "bg-cyan-600 text-white" : "text-stone-400 hover:text-white"}`}
              data-testid={`pace-days-${d}`}>{d}d</button>
          ))}
        </div>
      </div>

      {/* STLY Headline + Chart */}
      <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <h3 className="text-sm font-bold text-stone-100">STLY Pace · Önümüzdeki {days} gün</h3>
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-black ${ahead ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30" : "bg-rose-500/15 text-rose-300 border border-rose-500/30"}`}>
            {ahead ? <ArrowUp className="w-4 h-4" /> : <ArrowDown className="w-4 h-4" />}
            {ahead ? "AHEAD" : "BEHIND"} {Math.abs(stlyDelta)} oda · {ahead ? "+" : ""}{stlyDeltaPct}%
          </div>
        </div>
        {stlyChart && (
          <svg viewBox={`0 0 ${stlyChart.W} ${stlyChart.H}`} className="w-full" data-testid="pace-stly-chart">
            {/* grid */}
            {[0, 25, 50, 75, 100].map(p => {
              const y = stlyChart.pad.t + stlyChart.iH - (p / 100) * stlyChart.iH;
              return <line key={p} x1={stlyChart.pad.l} x2={stlyChart.W - stlyChart.pad.r} y1={y} y2={y} stroke="#374151" strokeWidth="0.5" />;
            })}
            {/* LY (last year) — dashed amber */}
            <path d={stlyChart.lyPath} fill="none" stroke="#f59e0b" strokeWidth="2" strokeDasharray="5 3" opacity="0.85" />
            {/* TY (this year) — solid cyan */}
            <path d={stlyChart.tyPath} fill="none" stroke="#22d3ee" strokeWidth="2.5" />
            {/* x labels (every 7th day) */}
            {data.stly.map((d, i) => i % 7 !== 0 && i !== data.stly.length - 1 ? null : (
              <text key={`x${i}`} x={stlyChart.sx(i)} y={stlyChart.H - 6} textAnchor="middle" fontSize="8" fill="#9ca3af">
                {new Date(d.date).toLocaleDateString("en", { day: "2-digit", month: "short" })}
              </text>
            ))}
            {/* y axis max */}
            <text x={stlyChart.pad.l - 4} y={stlyChart.pad.t + 4} textAnchor="end" fontSize="8" fill="#9ca3af">{Math.round(stlyChart.maxV)}</text>
          </svg>
        )}
        <div className="flex items-center gap-4 mt-2 text-[10px]">
          <span className="flex items-center gap-1.5"><span className="w-4 h-[2px] bg-cyan-400" /> Bu Yıl ({totals.ty_total_rooms} oda)</span>
          <span className="flex items-center gap-1.5"><span className="w-4 h-[2px]" style={{ background: "repeating-linear-gradient(90deg,#f59e0b 0,#f59e0b 4px,transparent 4px,transparent 7px)" }} /> Geçen Yıl ({totals.ly_total_rooms} oda)</span>
        </div>
      </div>

      {/* Pickup Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3" data-testid="pace-pickup">
        {[
          ["last_7d", "Son 7 Gün"],
          ["last_14d", "Son 14 Gün"],
          ["last_30d", "Son 30 Gün"],
        ].map(([key, label]) => {
          const w = data.pickup?.[key] || { total_bookings: 0, total_revenue: 0, by_source: {} };
          return (
            <div key={key} className="bg-stone-900/60 border border-stone-800 rounded-2xl p-4">
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-xs font-bold uppercase tracking-widest text-stone-400">Pickup · {label}</h4>
                <Calendar className="w-3.5 h-3.5 text-stone-500" />
              </div>
              <div className="flex items-end justify-between mb-3">
                <div>
                  <div className="text-3xl font-black text-cyan-300 tabular-nums">{w.total_bookings}</div>
                  <div className="text-[10px] text-stone-500">rezervasyon</div>
                </div>
                <div className="text-right">
                  <div className="text-base font-bold text-emerald-300 tabular-nums">{cur(w.total_revenue)}</div>
                  <div className="text-[10px] text-stone-500">gelir</div>
                </div>
              </div>
              {Object.keys(w.by_source).length > 0 && (
                <div className="space-y-1">
                  {Object.entries(w.by_source).slice(0, 4).map(([src, v]) => {
                    const pct = w.total_bookings > 0 ? Math.round((v.count / w.total_bookings) * 100) : 0;
                    return (
                      <div key={src} className="flex items-center gap-2 text-[10px]">
                        <span className="w-2 h-2 rounded-sm flex-shrink-0" style={{ background: colourFor(src) }} />
                        <span className="text-stone-300 truncate flex-1">{src.replace("_", " ")}</span>
                        <span className="text-stone-500 tabular-nums">{v.count} · {pct}%</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Source contribution */}
      {data.source_contribution?.length > 0 && (
        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-5" data-testid="pace-sources">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-stone-100 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-violet-400" />
              Source Contribution · Önümüzdeki {days} gün
            </h3>
            <div className="flex items-center gap-1.5 text-xs text-stone-400">
              <PoundSterling className="w-3.5 h-3.5" />
              <span className="font-black text-emerald-300">{cur(totals.forecast_revenue)}</span>
              <span className="text-stone-500">tahmini toplam</span>
            </div>
          </div>
          <div className="space-y-2">
            {data.source_contribution.map((s) => {
              const colour = colourFor(s.source);
              return (
                <div key={s.source} className="flex items-center gap-3" data-testid={`pace-source-${s.source}`}>
                  <span className="w-24 text-xs font-bold flex items-center gap-1.5" style={{ color: colour }}>
                    <span className="w-2.5 h-2.5 rounded-sm" style={{ background: colour }} />
                    <span className="truncate">{s.source.replace("_", " ")}</span>
                  </span>
                  <div className="flex-1 h-6 bg-stone-800 rounded-lg overflow-hidden relative">
                    <div className="h-full transition-all" style={{ width: `${s.share_pct}%`, background: colour, opacity: 0.8 }} />
                    <span className="absolute inset-0 flex items-center px-2 text-[11px] font-black text-white mix-blend-difference">
                      {cur(s.revenue)} · {s.bookings} bk
                    </span>
                  </div>
                  <span className="w-12 text-right text-xs font-black tabular-nums text-stone-200">{s.share_pct}%</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
