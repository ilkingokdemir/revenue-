/**
 * Market Pulse — Premium 90-day market demand visualization.
 * Glassmorphism + gradient bars + 7d dotted trend + animated delta + hover tooltips.
 */
import { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import { motion, AnimatePresence } from "framer-motion";
import {
  TrendUp, TrendDown, ChartLine, Sparkle, Pulse, Calendar, Flame, Snowflake,
} from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MONTHS_TR = { Jan: "Oca", Feb: "Şub", Mar: "Mar", Apr: "Nis", May: "May", Jun: "Haz", Jul: "Tem", Aug: "Ağu", Sep: "Eyl", Oct: "Eki", Nov: "Kas", Dec: "Ara" };

const fmtGBP = (n) => "£" + (Number(n) || 0).toLocaleString("en-GB", { maximumFractionDigits: 0 });
const fmtPct = (n) => (Number(n) || 0).toFixed(1) + "%";

export default function MarketPulsePanel({ activePropertyId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [lang, setLang] = useState(() => localStorage.getItem("maint_lang") || "en");
  const [hover, setHover] = useState(null); // {i, x, y}

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
    title: "Market Pulse", subtitle: "90 günlük piyasa nabzı · Yıllık performans",
    howBusy: "Piyasa Nabzı", howBusyCap: "Yüksek skor = güçlü fiyatlama gücü",
    demandUp: "Piyasa talebi güçleniyor", demandDown: "Piyasa talebi zayıflıyor", demandFlat: "Piyasa talebi dengeli",
    vsLast: "30 gün öncesine göre",
    annual: "Yıllık Performans", annualCap: "ADR · Doluluk · Gelir · 12 ay karşılaştırması",
    month: "AY", occ: "DOLULUK", adr: "ADR", rev: "GELİR", delta: "DELTA", deltaPct: "GELİR %", deltaAbs: "GELİR £",
    annualTotal: "Yıllık Toplam", avgScore: "Ortalama", peakDays: "Zirve Gün", dates: "Gün Sayısı",
    pickBranch: "Lütfen bir şube seçin", noData: "Henüz tarama yok — Market Robot'u etkinleştirin",
    legendNormal: "Normal", legendHigh: "Yüksek", legendPeak: "Zirve", legendTrend: "7g ort",
    eventLabel: "Etkinlik", scoreLabel: "Talep skoru",
  } : {
    title: "Market Pulse", subtitle: "90-day market heartbeat · Annual performance",
    howBusy: "Market Heartbeat", howBusyCap: "Higher = stronger pricing power",
    demandUp: "Market demand is strengthening", demandDown: "Market demand is weakening", demandFlat: "Market demand is stable",
    vsLast: "vs 30 days ago",
    annual: "Annual Performance", annualCap: "ADR · Occupancy · Revenue · 12-month comparison",
    month: "MONTH", occ: "OCC", adr: "ADR", rev: "REV", delta: "DELTA", deltaPct: "REV %", deltaAbs: "REV £",
    annualTotal: "Annual Total", avgScore: "Avg", peakDays: "Peak", dates: "Days",
    pickBranch: "Please select a branch", noData: "No scan yet — enable the Market Robot",
    legendNormal: "Normal", legendHigh: "High", legendPeak: "Peak", legendTrend: "7d avg",
    eventLabel: "Event", scoreLabel: "Demand",
  };

  // Derived chart data
  const chart = useMemo(() => {
    if (!data?.bars) return null;
    const bars = data.bars;
    const maxScore = 100;
    const W = 1000, H = 260, padL = 0, padR = 0, padT = 18, padB = 30;
    const innerW = W - padL - padR;
    const innerH = H - padT - padB;
    const barW = innerW / bars.length;
    const barGap = Math.max(1.2, barW * 0.18);
    const actualW = barW - barGap;

    const trendPts = data.trend.map((t, i) => {
      const cx = padL + i * barW + barW / 2;
      const cy = padT + innerH - (t.value / maxScore) * innerH;
      return [cx, cy];
    });
    const trendPath = trendPts.map(([x, y], i) => (i === 0 ? `M${x},${y}` : `L${x},${y}`)).join(" ");

    return { bars, W, H, padL, padT, padB, innerH, barW, actualW, trendPath, trendPts, maxScore };
  }, [data]);

  if (!activePropertyId || activePropertyId === "all") {
    return (
      <div className="p-10 text-center" data-testid="mp-pick-branch">
        <div className="max-w-md mx-auto bg-gradient-to-br from-amber-500/10 to-amber-400/5 border border-amber-500/30 rounded-2xl p-8 backdrop-blur">
          <ChartLine size={40} className="mx-auto text-amber-400 mb-3" weight="fill" />
          <p className="text-sm font-semibold text-amber-200">{L.pickBranch}</p>
        </div>
      </div>
    );
  }
  if (loading) {
    return (
      <div className="p-10 flex items-center justify-center">
        <div className="flex items-center gap-3 text-emerald-400">
          <Pulse size={22} className="animate-pulse" weight="fill" />
          <span className="text-sm font-semibold tracking-wide">Loading Market Pulse…</span>
        </div>
      </div>
    );
  }
  if (err) return <div className="p-8 text-center text-rose-400 text-sm">{err}</div>;
  if (!data || !data.bars || data.bars.length === 0) {
    return (
      <div className="p-10 text-center" data-testid="mp-no-data">
        <div className="max-w-md mx-auto bg-gradient-to-br from-emerald-500/10 to-teal-500/5 border border-emerald-500/20 rounded-2xl p-8 backdrop-blur">
          <Sparkle size={36} className="mx-auto text-emerald-400 mb-3" weight="fill" />
          <p className="text-sm text-stone-200">{L.noData}</p>
        </div>
      </div>
    );
  }

  const { bars, summary, annual } = data;
  const up = summary.delta_pp > 1;
  const down = summary.delta_pp < -1;
  const deltaText = up ? L.demandUp : down ? L.demandDown : L.demandFlat;
  const deltaSign = summary.delta_pp > 0 ? "+" : "";

  return (
    <div className="relative min-h-full bg-[#070f0d] text-stone-100 p-4 md:p-8 space-y-6 overflow-hidden" data-testid="market-pulse-panel">
      {/* Ambient glow backdrop */}
      <div className="pointer-events-none absolute -top-40 -right-40 w-[500px] h-[500px] rounded-full bg-emerald-500/10 blur-[140px]" />
      <div className="pointer-events-none absolute -bottom-40 -left-40 w-[500px] h-[500px] rounded-full bg-teal-500/10 blur-[140px]" />
      <div className="pointer-events-none absolute inset-0 opacity-[0.015]" style={{
        backgroundImage: "radial-gradient(rgba(255,255,255,0.6) 1px, transparent 1px)",
        backgroundSize: "20px 20px",
      }} />

      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="relative flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="absolute inset-0 bg-emerald-400 blur-xl opacity-40" />
            <div className="relative w-11 h-11 rounded-2xl bg-gradient-to-br from-emerald-400 to-teal-600 flex items-center justify-center shadow-lg shadow-emerald-500/40">
              <Pulse size={22} className="text-black" weight="fill" />
            </div>
          </div>
          <div>
            <h1 className="text-2xl md:text-4xl font-black tracking-tight bg-gradient-to-r from-emerald-300 via-teal-200 to-emerald-400 bg-clip-text text-transparent" style={{ fontFamily: "Outfit, sans-serif" }}>
              {L.title}
            </h1>
            <p className="text-[11px] md:text-xs text-stone-400 mt-0.5 tracking-wide">{L.subtitle}</p>
          </div>
        </div>
        <div className="flex gap-0.5 bg-stone-900/80 border border-stone-700 rounded-xl p-0.5 backdrop-blur" data-testid="mp-lang-toggle">
          {["en", "tr"].map(c => (
            <button key={c} onClick={() => { setLang(c); localStorage.setItem("maint_lang", c); }}
              className={`px-3 py-1.5 text-[10px] font-black rounded-lg transition-all ${lang === c ? "bg-gradient-to-br from-emerald-400 to-teal-500 text-black shadow-md" : "text-stone-400 hover:text-stone-200"}`}
              data-testid={`mp-lang-${c}`}>
              {c === "en" ? "🇬🇧" : "🇹🇷"} {c.toUpperCase()}
            </button>
          ))}
        </div>
      </motion.div>

      {/* Trend delta banner */}
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.1 }}
        className={`relative overflow-hidden rounded-2xl px-6 py-5 border backdrop-blur-sm ${
          up ? "border-emerald-500/40 bg-gradient-to-r from-emerald-950/70 via-emerald-900/30 to-transparent"
          : down ? "border-rose-500/40 bg-gradient-to-r from-rose-950/70 via-rose-900/30 to-transparent"
          : "border-stone-700 bg-stone-900/40"}`}
        data-testid="mp-delta-banner">
        <div className={`absolute left-0 top-0 bottom-0 w-1 ${up ? "bg-emerald-400" : down ? "bg-rose-400" : "bg-stone-500"} shadow-lg shadow-emerald-500/50`} />
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${up ? "bg-emerald-500/20 text-emerald-300" : down ? "bg-rose-500/20 text-rose-300" : "bg-stone-700/40 text-stone-300"}`}>
              {up ? <TrendUp size={20} weight="bold" /> : down ? <TrendDown size={20} weight="bold" /> : <ChartLine size={20} />}
            </div>
            <div>
              <p className={`text-sm md:text-base font-bold tracking-wide ${up ? "text-emerald-200" : down ? "text-rose-200" : "text-stone-200"}`}>{deltaText}</p>
              <p className="text-[10px] md:text-xs text-stone-500 mt-0.5 uppercase tracking-widest">{L.vsLast}</p>
            </div>
          </div>
          <div className="text-right">
            <motion.p
              key={summary.delta_pp}
              initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
              className={`text-3xl md:text-5xl font-black tabular-nums ${up ? "text-emerald-300 drop-shadow-[0_0_18px_rgba(16,185,129,0.55)]" : down ? "text-rose-300 drop-shadow-[0_0_18px_rgba(244,63,94,0.5)]" : "text-stone-300"}`}
              data-testid="mp-delta-value">
              {deltaSign}{summary.delta_pp}<span className="text-sm md:text-lg font-bold opacity-70 ml-0.5">pp</span>
            </motion.p>
          </div>
        </div>
      </motion.div>

      {/* Chart */}
      <motion.div
        initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
        className="relative rounded-2xl p-5 md:p-6 border border-stone-800/80 bg-gradient-to-br from-stone-900/80 to-stone-950/60 backdrop-blur shadow-[0_0_40px_-20px_rgba(16,185,129,0.3)]">
        <div className="flex items-start justify-between mb-5">
          <div className="flex items-center gap-2.5">
            <span className="relative flex">
              <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60 animate-ping" />
              <span className="relative inline-flex w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
            </span>
            <div>
              <h2 className="text-base md:text-lg font-bold text-stone-100 tracking-tight">{L.howBusy}</h2>
              <p className="text-[10px] md:text-xs text-stone-500 mt-0.5">{L.howBusyCap}</p>
            </div>
          </div>
          <div className="flex items-center gap-3 text-[10px] text-stone-400 flex-wrap justify-end">
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-gradient-to-t from-emerald-600 to-emerald-400 inline-block" /> {L.legendNormal}</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-gradient-to-t from-amber-600 to-amber-400 inline-block" /> {L.legendHigh}</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-gradient-to-t from-rose-600 to-rose-400 inline-block" /> {L.legendPeak}</span>
            <span className="flex items-center gap-1.5"><span className="w-5 h-[2px] border-t-2 border-dashed border-emerald-300 inline-block" /> {L.legendTrend}</span>
          </div>
        </div>

        <div className="relative h-64 md:h-72 w-full" data-testid="mp-chart">
          <svg viewBox={`0 0 ${chart.W} ${chart.H}`} preserveAspectRatio="none" className="absolute inset-0 w-full h-full overflow-visible">
            <defs>
              <linearGradient id="mp-bar-normal" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#34d399" stopOpacity="1" />
                <stop offset="100%" stopColor="#059669" stopOpacity="0.8" />
              </linearGradient>
              <linearGradient id="mp-bar-high" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#fbbf24" stopOpacity="1" />
                <stop offset="100%" stopColor="#d97706" stopOpacity="0.85" />
              </linearGradient>
              <linearGradient id="mp-bar-peak" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#fb7185" stopOpacity="1" />
                <stop offset="100%" stopColor="#e11d48" stopOpacity="0.9" />
              </linearGradient>
              <linearGradient id="mp-bar-low" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#10b981" stopOpacity="0.35" />
                <stop offset="100%" stopColor="#047857" stopOpacity="0.2" />
              </linearGradient>
              <linearGradient id="mp-trend" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#a7f3d0" stopOpacity="0.7" />
                <stop offset="50%" stopColor="#6ee7b7" stopOpacity="1" />
                <stop offset="100%" stopColor="#34d399" stopOpacity="0.7" />
              </linearGradient>
              <filter id="mp-glow">
                <feGaussianBlur stdDeviation="2" result="glow" />
                <feMerge><feMergeNode in="glow" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
            </defs>

            {/* Gridlines */}
            {[25, 50, 75].map(pct => {
              const y = chart.padT + chart.innerH - (pct / 100) * chart.innerH;
              return (
                <g key={pct}>
                  <line x1={chart.padL} y1={y} x2={chart.W - 0} y2={y} stroke="#1e2a26" strokeWidth="1" strokeDasharray="3,4" />
                  <text x={chart.W - 6} y={y - 3} textAnchor="end" fill="#4b5b55" fontSize="9" fontWeight="600">{pct}</text>
                </g>
              );
            })}

            {/* Bars */}
            {bars.map((b, i) => {
              const h = Math.max(3, (b.score / chart.maxScore) * chart.innerH);
              const y = chart.padT + chart.innerH - h;
              const x = chart.padL + i * chart.barW + (chart.barW - chart.actualW) / 2;
              const gradId = b.kind === "peak_event" ? "mp-bar-peak" : b.kind === "peak_high" ? "mp-bar-high" : b.kind === "low" ? "mp-bar-low" : "mp-bar-normal";
              const rx = Math.min(2.5, chart.actualW * 0.3);
              const highlighted = hover?.i === i;
              return (
                <g key={i}
                   onMouseEnter={(e) => setHover({ i, x: x + chart.actualW / 2, y })}
                   onMouseLeave={() => setHover(null)}
                   style={{ cursor: "pointer" }}>
                  <rect x={x} y={y} width={chart.actualW} height={h} rx={rx} fill={`url(#${gradId})`}
                        filter={b.kind === "peak_event" || b.kind === "peak_high" ? "url(#mp-glow)" : undefined}
                        opacity={highlighted ? 1 : 0.92} />
                  {highlighted && (
                    <rect x={x - 1} y={y - 2} width={chart.actualW + 2} height={h + 2} rx={rx} fill="none" stroke="#fff" strokeOpacity="0.25" strokeWidth="0.8" />
                  )}
                </g>
              );
            })}

            {/* 7d trend dotted line */}
            <path d={chart.trendPath} fill="none" stroke="url(#mp-trend)" strokeWidth="2" strokeDasharray="5,4" strokeLinecap="round" filter="url(#mp-glow)" />
            {/* Trend dots at notable positions */}
            {chart.trendPts.filter((_, i) => i % 14 === 0 || i === chart.trendPts.length - 1).map((p, k) => (
              <circle key={k} cx={p[0]} cy={p[1]} r="2.5" fill="#6ee7b7" stroke="#022c22" strokeWidth="1" />
            ))}
          </svg>

          {/* Hover tooltip */}
          <AnimatePresence>
            {hover && bars[hover.i] && (
              <motion.div
                initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                className="absolute pointer-events-none z-20 bg-stone-950/95 border border-emerald-500/30 rounded-lg px-3 py-2 text-xs shadow-2xl shadow-emerald-500/20 backdrop-blur"
                style={{
                  left: `calc(${(hover.x / chart.W) * 100}% - 80px)`,
                  top: `calc(${(hover.y / chart.H) * 100}% - 76px)`,
                }}>
                <p className="font-bold text-emerald-300 text-[11px]">{bars[hover.i].date}</p>
                <p className="text-stone-400 text-[10px] mt-0.5">{L.scoreLabel}: <span className="text-stone-100 font-bold">{bars[hover.i].score}%</span></p>
                {bars[hover.i].event && (
                  <p className="text-amber-300 text-[10px] mt-0.5 font-semibold truncate max-w-[160px]">★ {bars[hover.i].event}</p>
                )}
              </motion.div>
            )}
          </AnimatePresence>

          {/* X-axis labels */}
          <div className="absolute bottom-0 left-0 right-0 flex justify-between text-[9px] text-stone-500 font-semibold tabular-nums px-0.5">
            {[0, Math.floor(bars.length / 4), Math.floor(bars.length / 2), Math.floor((bars.length * 3) / 4), bars.length - 1].map(idx => (
              <span key={idx}>{bars[idx]?.date?.slice(5) || ""}</span>
            ))}
          </div>
        </div>

        {/* KPI strip */}
        <div className="grid grid-cols-3 gap-3 md:gap-5 mt-5">
          {[
            { label: L.avgScore, value: summary.avg_score, tone: "emerald", icon: ChartLine, testId: "mp-avg-score" },
            { label: L.peakDays, value: summary.peak_days, tone: "amber", icon: Flame, testId: "mp-peak-days" },
            { label: L.dates, value: summary.dates_count, tone: "slate", icon: Calendar, testId: "mp-days-count" },
          ].map((k, idx) => {
            const Icon = k.icon;
            const tones = {
              emerald: "from-emerald-500/15 to-emerald-700/5 border-emerald-500/30 text-emerald-300",
              amber: "from-amber-500/15 to-amber-700/5 border-amber-500/30 text-amber-300",
              slate: "from-stone-600/15 to-stone-800/5 border-stone-600/40 text-stone-200",
            };
            return (
              <motion.div
                key={k.label}
                initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 + idx * 0.06 }}
                className={`relative overflow-hidden rounded-xl border bg-gradient-to-br ${tones[k.tone]} p-3 md:p-4 backdrop-blur`}>
                <Icon size={30} className="absolute -right-2 -bottom-2 opacity-10" weight="fill" />
                <p className="text-[9px] md:text-[10px] uppercase font-black tracking-widest opacity-70">{k.label}</p>
                <p className="text-2xl md:text-3xl font-black tabular-nums mt-1" data-testid={k.testId}>{k.value}</p>
              </motion.div>
            );
          })}
        </div>
      </motion.div>

      {/* Annual Performance */}
      <motion.div
        initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}
        className="relative rounded-2xl p-5 md:p-6 border border-stone-800/80 bg-gradient-to-br from-stone-900/80 to-stone-950/60 backdrop-blur">
        <div className="flex items-center gap-2.5 mb-5">
          <Sparkle size={18} weight="fill" className="text-emerald-400 drop-shadow-[0_0_6px_rgba(52,211,153,0.6)]" />
          <div>
            <h2 className="text-base md:text-lg font-bold text-stone-100 tracking-tight">{L.annual}</h2>
            <p className="text-[10px] md:text-xs text-stone-500 mt-0.5">{L.annualCap}</p>
          </div>
          <div className="ml-auto flex items-center gap-2 text-[10px] text-stone-400">
            <span className="px-2 py-0.5 rounded-md bg-stone-800 border border-stone-700 font-bold">{annual.prev_year}</span>
            <span className="text-stone-600">vs</span>
            <span className="px-2 py-0.5 rounded-md bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold">{annual.curr_year}</span>
          </div>
        </div>

        <div className="overflow-x-auto -mx-5 md:-mx-6 px-5 md:px-6">
          <table className="w-full text-xs min-w-[720px]" data-testid="mp-annual-table">
            <thead>
              <tr className="text-[9px] uppercase text-stone-500 border-b border-stone-700/60">
                <th rowSpan={2} className="text-left py-2 pr-3 font-black tracking-widest">{L.month}</th>
                <th colSpan={3} className="text-center py-1.5 font-black tracking-widest text-stone-400 border-l border-stone-800">{annual.prev_year}</th>
                <th colSpan={3} className="text-center py-1.5 font-black tracking-widest text-emerald-400 border-l border-stone-800">{annual.curr_year}</th>
                <th colSpan={2} className="text-center py-1.5 font-black tracking-widest text-stone-200 border-l border-stone-800">{L.delta}</th>
              </tr>
              <tr className="text-[9px] uppercase text-stone-500 border-b border-stone-700/60">
                {[L.occ, L.adr, L.rev, L.occ, L.adr, L.rev, L.deltaPct, L.deltaAbs].map((h, i) => (
                  <th key={i} className={`text-right py-1.5 px-2 font-bold ${i === 0 || i === 3 || i === 6 ? "border-l border-stone-800" : ""}`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {annual.monthly.map((m, idx) => {
                const name = lang === "tr" ? (MONTHS_TR[m.month] || m.month) : m.month;
                const good = m.delta_pct > 0;
                const bad = m.delta_pct < 0;
                return (
                  <motion.tr key={m.month_num}
                    initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.28 + idx * 0.015 }}
                    className={`border-b border-stone-800/40 transition-colors hover:bg-emerald-500/5 ${m.is_mtd ? "bg-gradient-to-r from-emerald-950/40 to-transparent" : ""}`}
                    data-testid={`mp-row-${m.month_num}`}>
                    <td className="py-2.5 pr-3">
                      <span className="font-bold text-stone-100">{name}</span>
                      {m.is_mtd && <span className="ml-2 text-[8px] bg-emerald-500/30 text-emerald-200 px-1.5 py-0.5 rounded font-black uppercase tracking-widest">MTD</span>}
                    </td>
                    <td className="text-right px-2 text-stone-500 tabular-nums border-l border-stone-800/40">{fmtPct(m.prev_occ)}</td>
                    <td className="text-right px-2 text-stone-500 tabular-nums">{fmtGBP(m.prev_adr)}</td>
                    <td className="text-right px-2 text-stone-400 font-semibold tabular-nums">{fmtGBP(m.prev_rev)}</td>
                    <td className="text-right px-2 text-stone-300 tabular-nums border-l border-stone-800/40">{fmtPct(m.curr_occ)}</td>
                    <td className="text-right px-2 text-stone-300 tabular-nums">{fmtGBP(m.curr_adr)}</td>
                    <td className="text-right px-2 text-stone-100 font-bold tabular-nums">{fmtGBP(m.curr_rev)}</td>
                    <td className="text-right px-2 border-l border-stone-800/40">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-black tabular-nums ${good ? "bg-emerald-500/15 text-emerald-300 shadow-[inset_0_0_0_1px_rgba(16,185,129,0.25)]" : bad ? "bg-rose-500/15 text-rose-300 shadow-[inset_0_0_0_1px_rgba(244,63,94,0.25)]" : "bg-stone-800 text-stone-500"}`}>
                        {good ? "▲" : bad ? "▼" : "—"} {good ? "+" : ""}{m.delta_pct}%
                      </span>
                    </td>
                    <td className="text-right px-2">
                      <span className={`inline-block px-2 py-0.5 rounded-md text-[10px] font-black tabular-nums ${good ? "bg-emerald-500/15 text-emerald-300" : bad ? "bg-rose-500/15 text-rose-300" : "bg-stone-800 text-stone-500"}`}>
                        {good ? "+" : ""}{fmtGBP(m.delta_rev)}
                      </span>
                    </td>
                  </motion.tr>
                );
              })}
              <tr className="border-t-2 border-emerald-500/50 bg-gradient-to-r from-emerald-950/40 via-emerald-900/20 to-transparent" data-testid="mp-row-total">
                <td className="py-3 pr-3">
                  <span className="font-black text-emerald-300 tracking-wide uppercase text-[11px]">{L.annualTotal}</span>
                </td>
                <td colSpan={2} className="border-l border-stone-800/40"></td>
                <td className="text-right px-2 font-bold text-stone-400 tabular-nums">{fmtGBP(annual.totals.prev_rev)}</td>
                <td colSpan={2} className="border-l border-stone-800/40"></td>
                <td className="text-right px-2 font-black text-stone-100 tabular-nums text-sm">{fmtGBP(annual.totals.curr_rev)}</td>
                <td className="text-right px-2 border-l border-stone-800/40">
                  <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-black tabular-nums ${annual.totals.delta_pct > 0 ? "bg-emerald-500/25 text-emerald-200 shadow-[0_0_12px_rgba(16,185,129,0.4)]" : "bg-rose-500/25 text-rose-200 shadow-[0_0_12px_rgba(244,63,94,0.4)]"}`}>
                    {annual.totals.delta_pct > 0 ? "▲ +" : "▼ "}{annual.totals.delta_pct}%
                  </span>
                </td>
                <td className="text-right px-2">
                  <span className={`inline-block px-2 py-1 rounded-md text-[11px] font-black tabular-nums ${(annual.totals.curr_rev - annual.totals.prev_rev) > 0 ? "bg-emerald-500/25 text-emerald-200" : "bg-rose-500/25 text-rose-200"}`}>
                    {(annual.totals.curr_rev - annual.totals.prev_rev) > 0 ? "+" : ""}{fmtGBP(annual.totals.curr_rev - annual.totals.prev_rev)}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </motion.div>
    </div>
  );
}
