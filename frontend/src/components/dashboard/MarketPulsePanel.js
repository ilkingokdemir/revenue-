/**
 * Market Pulse — 90-day market demand visualization inspired by Market Pulse.
 * - Top: bar chart (demand score 0-100 per day) + 7-day moving average trend line
 * - Middle: delta card ("90-day market demand is strengthening +Xpp")
 * - Bottom: Annual Performance table (this year vs last year, monthly OCC/ADR/REV)
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { TrendUp, TrendDown, ChartLine, Sparkle } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MONTHS_TR = { Jan: "Oca", Feb: "Şub", Mar: "Mar", Apr: "Nis", May: "May", Jun: "Haz", Jul: "Tem", Aug: "Ağu", Sep: "Eyl", Oct: "Eki", Nov: "Kas", Dec: "Ara" };

function fmtGBP(n) {
  const v = Number(n) || 0;
  return "£" + v.toLocaleString("en-GB", { maximumFractionDigits: 0 });
}
function fmtPct(n) {
  return (Number(n) || 0).toFixed(1) + "%";
}

export default function MarketPulsePanel({ activePropertyId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [lang, setLang] = useState(() => localStorage.getItem("maint_lang") || "en");

  const fetchData = useCallback(async () => {
    if (!activePropertyId || activePropertyId === "all") { setLoading(false); return; }
    setLoading(true); setErr("");
    try {
      const { data: res } = await axios.get(`${API}/revenue/market-robot/${activePropertyId}/market-pulse?days=90`);
      setData(res);
    } catch (e) {
      setErr(e?.response?.data?.detail || "Veri yüklenemedi");
    }
    setLoading(false);
  }, [activePropertyId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const L = lang === "tr" ? {
    title: "Market Pulse", subtitle: "90 günlük piyasa talebi ve yıllık performans",
    howBusy: "Piyasa Ne Kadar Yoğun?", howBusyCap: "Yüksek skor = güçlü fiyatlama gücü",
    demandUp: "90 günlük piyasa talebi güçleniyor",
    demandDown: "90 günlük piyasa talebi zayıflıyor",
    demandFlat: "90 günlük piyasa talebi dengeli",
    vsLast: "30 gün öncesine göre",
    annual: "Yıllık Performans — Tüm Metrikler", annualCap: "ADR, Doluluk & Gelir karşılaştırması (12 ay)",
    month: "AY", occ: "DOLULUK", adr: "ADR", rev: "GELİR", delta: "DELTA", deltaPct: "GELİR %", deltaAbs: "GELİR £",
    annualTotal: "Yıllık Toplam", avgScore: "Ortalama skor", peakDays: "Zirve günleri", dates: "Kapsam",
    pickBranch: "Lütfen bir şube seçin", noData: "Henüz tarama yok — Market Robot'u etkinleştirin",
  } : {
    title: "Market Pulse", subtitle: "90-day market demand & annual performance",
    howBusy: "How Busy is the Market?", howBusyCap: "Higher = stronger pricing power",
    demandUp: "90-day market demand is strengthening",
    demandDown: "90-day market demand is weakening",
    demandFlat: "90-day market demand is stable",
    vsLast: "vs 30 days ago",
    annual: "Annual Performance — All Metrics", annualCap: "ADR, Occupancy & Revenue comparison (12 months)",
    month: "MONTH", occ: "OCC", adr: "ADR", rev: "REV", delta: "DELTA", deltaPct: "REV %", deltaAbs: "REV £",
    annualTotal: "Annual Total", avgScore: "Avg score", peakDays: "Peak days", dates: "Days",
    pickBranch: "Please select a branch", noData: "No scan yet — enable the Market Robot",
  };

  if (!activePropertyId || activePropertyId === "all") {
    return (
      <div className="p-8 text-center" data-testid="mp-pick-branch">
        <div className="max-w-md mx-auto bg-amber-50 border border-amber-200 rounded-xl p-6">
          <ChartLine size={36} className="mx-auto text-amber-500 mb-2" />
          <p className="text-sm font-semibold text-amber-800">{L.pickBranch}</p>
        </div>
      </div>
    );
  }

  if (loading) return <div className="p-8 text-center text-stone-400 text-sm">Loading…</div>;
  if (err) return <div className="p-8 text-center text-red-600 text-sm">{err}</div>;
  if (!data || !data.bars || data.bars.length === 0) {
    return (
      <div className="p-8 text-center" data-testid="mp-no-data">
        <div className="max-w-md mx-auto bg-stone-900 border border-stone-700 rounded-xl p-6 text-stone-300">
          <Sparkle size={32} className="mx-auto text-emerald-400 mb-2" weight="fill" />
          <p className="text-sm">{L.noData}</p>
        </div>
      </div>
    );
  }

  const { bars, trend, summary, annual } = data;
  const maxScore = 100;
  const barW = 100 / bars.length;
  const up = summary.delta_pp > 1;
  const down = summary.delta_pp < -1;
  const deltaText = up ? L.demandUp : down ? L.demandDown : L.demandFlat;
  const deltaSign = summary.delta_pp > 0 ? "+" : "";

  // SVG trend path
  const trendPts = trend.map((t, i) => {
    const x = i * barW + barW / 2;
    const y = 100 - (t.value / maxScore) * 100;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ");

  return (
    <div className="min-h-full bg-[#0b1310] text-stone-100 p-4 md:p-6 space-y-5" data-testid="market-pulse-panel">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl md:text-3xl font-black tracking-tight text-emerald-400" style={{ fontFamily: "Outfit, sans-serif" }}>
            {L.title}
          </h1>
          <p className="text-xs text-stone-400 mt-1">{L.subtitle}</p>
        </div>
        <div className="flex gap-1 bg-stone-800 rounded-lg p-0.5" data-testid="mp-lang-toggle">
          {["en", "tr"].map(c => (
            <button key={c} onClick={() => { setLang(c); localStorage.setItem("maint_lang", c); }}
              className={`px-2 py-1 text-[10px] font-bold rounded ${lang === c ? "bg-emerald-500 text-black" : "text-stone-400"}`}
              data-testid={`mp-lang-${c}`}>
              {c.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Trend delta banner */}
      <div className={`flex items-center justify-between rounded-xl px-5 py-4 border ${up ? "bg-emerald-950/40 border-emerald-500/30" : down ? "bg-rose-950/40 border-rose-500/30" : "bg-stone-900 border-stone-700"}`} data-testid="mp-delta-banner">
        <div className="flex items-center gap-3">
          {up ? <TrendUp size={22} weight="bold" className="text-emerald-400" /> : down ? <TrendDown size={22} weight="bold" className="text-rose-400" /> : <ChartLine size={22} className="text-stone-400" />}
          <div>
            <p className={`text-sm font-bold ${up ? "text-emerald-300" : down ? "text-rose-300" : "text-stone-200"}`}>{deltaText}</p>
            <p className="text-[11px] text-stone-400 mt-0.5">{L.vsLast}</p>
          </div>
        </div>
        <div className="text-right">
          <p className={`text-2xl md:text-3xl font-black ${up ? "text-emerald-400" : down ? "text-rose-400" : "text-stone-300"}`} data-testid="mp-delta-value">
            {deltaSign}{summary.delta_pp}pp
          </p>
        </div>
      </div>

      {/* How Busy chart */}
      <div className="bg-stone-900/60 rounded-2xl p-5 border border-stone-800">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base md:text-lg font-bold text-stone-100">{L.howBusy}</h2>
            <p className="text-[11px] text-stone-500 mt-0.5">{L.howBusyCap}</p>
          </div>
          <div className="flex items-center gap-3 text-[10px] text-stone-400">
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-500/70 inline-block" /> Demand</span>
            <span className="flex items-center gap-1"><span className="w-3 h-[2px] border-t border-dashed border-emerald-300 inline-block" /> 7d trend</span>
          </div>
        </div>

        <div className="relative h-56 md:h-64 w-full" data-testid="mp-chart">
          {/* Gridlines */}
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 w-full h-full">
            {[25, 50, 75].map(y => (
              <line key={y} x1="0" y1={y} x2="100" y2={y} stroke="#2a3530" strokeWidth="0.15" strokeDasharray="0.5,0.5" />
            ))}

            {/* Bars */}
            {bars.map((b, i) => {
              const h = Math.max(2, (b.score / maxScore) * 100);
              const y = 100 - h;
              const x = i * barW + 0.3;
              const w = Math.max(0.4, barW - 0.6);
              const fill = b.kind === "peak_event"
                ? "#ef4444"         // red for major event peaks
                : b.kind === "peak_high"
                  ? "#f59e0b"       // amber for very high demand
                  : b.kind === "low"
                    ? "#1f2e26"     // muted for low
                    : "#10b981";    // emerald for normal demand
              return (
                <rect key={i} x={x} y={y} width={w} height={h} fill={fill} opacity={b.kind === "low" ? 0.6 : 0.85}>
                  <title>{b.date} · {b.score}%{b.event ? ` · ${b.event}` : ""}</title>
                </rect>
              );
            })}

            {/* 7d trend dashed line */}
            <polyline points={trendPts} fill="none" stroke="#6ee7b7" strokeWidth="0.35" strokeDasharray="1,0.8" />
          </svg>

          {/* X-axis labels (first, middle, last + one interior) */}
          <div className="absolute bottom-0 left-0 right-0 flex justify-between text-[9px] text-stone-500 -mb-4 px-0.5">
            {[0, Math.floor(bars.length / 4), Math.floor(bars.length / 2), Math.floor((bars.length * 3) / 4), bars.length - 1].map(idx => (
              <span key={idx}>{bars[idx]?.date?.slice(5) || ""}</span>
            ))}
          </div>
        </div>

        {/* Mini stats */}
        <div className="grid grid-cols-3 gap-2 md:gap-4 mt-8">
          <div className="bg-stone-950 rounded-lg px-3 py-2 border border-stone-800">
            <p className="text-[9px] uppercase text-stone-500 font-bold">{L.avgScore}</p>
            <p className="text-lg font-black text-emerald-400" data-testid="mp-avg-score">{summary.avg_score}</p>
          </div>
          <div className="bg-stone-950 rounded-lg px-3 py-2 border border-stone-800">
            <p className="text-[9px] uppercase text-stone-500 font-bold">{L.peakDays}</p>
            <p className="text-lg font-black text-amber-400" data-testid="mp-peak-days">{summary.peak_days}</p>
          </div>
          <div className="bg-stone-950 rounded-lg px-3 py-2 border border-stone-800">
            <p className="text-[9px] uppercase text-stone-500 font-bold">{L.dates}</p>
            <p className="text-lg font-black text-stone-200" data-testid="mp-days-count">{summary.dates_count}</p>
          </div>
        </div>
      </div>

      {/* Annual Performance Table */}
      <div className="bg-stone-900/60 rounded-2xl p-5 border border-stone-800">
        <div className="flex items-center gap-2 mb-4">
          <Sparkle size={16} weight="fill" className="text-emerald-400" />
          <div>
            <h2 className="text-base md:text-lg font-bold text-stone-100">{L.annual}</h2>
            <p className="text-[11px] text-stone-500 mt-0.5">{L.annualCap}</p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs" data-testid="mp-annual-table">
            <thead>
              <tr className="text-[9px] uppercase text-stone-500 border-b border-stone-700">
                <th rowSpan={2} className="text-left py-2 pr-2 font-bold">{L.month}</th>
                <th colSpan={3} className="text-center py-1 font-bold text-emerald-400">{annual.prev_year}</th>
                <th colSpan={3} className="text-center py-1 font-bold text-emerald-400">{annual.curr_year}</th>
                <th colSpan={2} className="text-center py-1 font-bold text-emerald-400">{L.delta}</th>
              </tr>
              <tr className="text-[9px] uppercase text-stone-500 border-b border-stone-700">
                {[L.occ, L.adr, L.rev, L.occ, L.adr, L.rev, L.deltaPct, L.deltaAbs].map((h, i) => (
                  <th key={i} className="text-right py-1 px-2 font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {annual.monthly.map(m => {
                const name = lang === "tr" ? (MONTHS_TR[m.month] || m.month) : m.month;
                const good = m.delta_pct > 0;
                return (
                  <tr key={m.month_num} className={`border-b border-stone-800/60 hover:bg-stone-900 ${m.is_mtd ? "bg-emerald-950/20" : ""}`} data-testid={`mp-row-${m.month_num}`}>
                    <td className="py-2 pr-2 font-semibold text-stone-200">
                      {name}{m.is_mtd && <span className="ml-1.5 text-[8px] bg-emerald-500/20 text-emerald-300 px-1 py-0.5 rounded">MTD</span>}
                    </td>
                    <td className="text-right px-2 text-stone-400">{fmtPct(m.prev_occ)}</td>
                    <td className="text-right px-2 text-stone-400">{fmtGBP(m.prev_adr)}</td>
                    <td className="text-right px-2 text-stone-300">{fmtGBP(m.prev_rev)}</td>
                    <td className="text-right px-2 text-stone-400">{fmtPct(m.curr_occ)}</td>
                    <td className="text-right px-2 text-stone-400">{fmtGBP(m.curr_adr)}</td>
                    <td className="text-right px-2 font-semibold text-stone-200">{fmtGBP(m.curr_rev)}</td>
                    <td className="text-right px-2">
                      <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold ${good ? "bg-emerald-500/20 text-emerald-300" : m.delta_pct < 0 ? "bg-rose-500/20 text-rose-300" : "text-stone-500"}`}>
                        {good ? "+" : ""}{m.delta_pct}%
                      </span>
                    </td>
                    <td className="text-right px-2">
                      <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold ${good ? "bg-emerald-500/20 text-emerald-300" : m.delta_rev < 0 ? "bg-rose-500/20 text-rose-300" : "text-stone-500"}`}>
                        {good ? "+" : ""}{fmtGBP(m.delta_rev)}
                      </span>
                    </td>
                  </tr>
                );
              })}
              <tr className="border-t-2 border-emerald-500/30 bg-stone-950/60" data-testid="mp-row-total">
                <td className="py-2.5 pr-2 font-black text-emerald-400">{L.annualTotal}</td>
                <td colSpan={2}></td>
                <td className="text-right px-2 font-semibold text-stone-300">{fmtGBP(annual.totals.prev_rev)}</td>
                <td colSpan={2}></td>
                <td className="text-right px-2 font-black text-stone-100">{fmtGBP(annual.totals.curr_rev)}</td>
                <td className="text-right px-2">
                  <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-black ${annual.totals.delta_pct > 0 ? "bg-emerald-500/20 text-emerald-300" : "bg-rose-500/20 text-rose-300"}`}>
                    {annual.totals.delta_pct > 0 ? "+" : ""}{annual.totals.delta_pct}%
                  </span>
                </td>
                <td className="text-right px-2">
                  <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-black ${(annual.totals.curr_rev - annual.totals.prev_rev) > 0 ? "bg-emerald-500/20 text-emerald-300" : "bg-rose-500/20 text-rose-300"}`}>
                    {(annual.totals.curr_rev - annual.totals.prev_rev) > 0 ? "+" : ""}{fmtGBP(annual.totals.curr_rev - annual.totals.prev_rev)}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
