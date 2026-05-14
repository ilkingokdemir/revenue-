/**
 * CompetitorPricePulseCard — Önümüzdeki N gün için rakip fiyat dağılımı + bizim fiyat
 * Recharts ile composed chart: min-max band + ortalama line + bizim çizgi.
 * 60sn polling. Boş veri durumunda "Şimdi Tara" CTA gösterir.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ComposedChart, Line, Area, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer,
  ReferenceLine, CartesianGrid,
} from "recharts";
import { TrendingUp, TrendingDown, RefreshCw, Loader2, Activity, Play } from "lucide-react";
import useLivePolling from "../../hooks/useLivePolling";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function CompetitorPricePulseCard({ propertyId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [days, setDays] = useState(30);

  const load = useCallback(async () => {
    if (!propertyId || propertyId === "all") {
      setData(null);
      return;
    }
    setLoading(true);
    try {
      const { data } = await axios.get(
        `${API}/revenue/market-robot/${propertyId}/competitor-pulse?days=${days}`
      );
      setData(data);
    } catch (e) { /* noop */ }
    setLoading(false);
  }, [propertyId, days]);

  useEffect(() => { load(); }, [load]);
  useLivePolling(load, { intervalMs: 60000 });

  const triggerScan = async () => {
    if (!propertyId || scanning) return;
    setScanning(true);
    try {
      const { data: r } = await axios.post(
        `${API}/revenue/market-robot/${propertyId}/competitors/scan`,
        { days_ahead: days }
      );
      toast.success(`${r.queued || 0} rakip arka planda taranıyor — ~1-2 dk sonra fiyatlar düşecek`);
    } catch {
      toast.error("Tarama başlatılamadı");
    }
    setScanning(false);
  };

  if (propertyId === "all") {
    return (
      <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-5 text-center text-xs text-stone-500">
        Bu görünüm tek şube içindir — soldan bir şube seçin.
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-6 text-center" data-testid="competitor-pulse-loading">
        <Loader2 className="w-5 h-5 text-stone-500 animate-spin mx-auto" />
      </div>
    );
  }

  const { summary, series, competitor_count, scanned_competitors } = data;
  const hasData = summary.days_with_data > 0;
  const vsPct = summary.vs_market_pct;
  const isAbove = vsPct !== null && vsPct > 0;
  const isBelow = vsPct !== null && vsPct < 0;

  // Recharts veri: min/max yerine band shape için "range" array
  const chartData = series.map(s => ({
    date: s.date.slice(5),  // MM-DD
    avg: s.avg,
    our_rate: s.our_rate,
    range: s.min !== null && s.max !== null ? [s.min, s.max] : null,
    min: s.min,
    max: s.max,
    comp_count: s.comp_count,
  }));

  return (
    <div className="bg-stone-900/60 border border-fuchsia-500/30 rounded-2xl p-5 space-y-4" data-testid="competitor-pulse-card">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-fuchsia-500/20">
            <Activity className="w-5 h-5 text-fuchsia-300" />
          </div>
          <div>
            <h3 className="text-sm font-black text-fuchsia-300">Rakip Fiyat Pulse · {days} gün</h3>
            <p className="text-[11px] text-stone-400 mt-0.5">
              {competitor_count} rakip · {scanned_competitors} taranmış · {summary.days_with_data}/{days} günde veri
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {[14, 30, 60].map(n => (
            <button key={n} onClick={() => setDays(n)}
              className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition ${days === n ? "bg-fuchsia-500/30 text-fuchsia-200 ring-1 ring-fuchsia-500/50" : "bg-stone-800 text-stone-400 hover:text-stone-200"}`}
              data-testid={`pulse-days-${n}`}>
              {n}g
            </button>
          ))}
          <button onClick={load} disabled={loading}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-xs text-stone-300 disabled:opacity-50"
            data-testid="pulse-refresh">
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="Pazar Avg" value={summary.market_avg} placeholder="—" prefix="£" testid="pulse-kpi-market-avg" />
        <Kpi label="Bizim Avg" value={summary.our_avg} prefix="£" testid="pulse-kpi-our-avg" />
        <Kpi label="Min (Pazar)" value={summary.market_min} placeholder="—" prefix="£" testid="pulse-kpi-market-min" tone="emerald" />
        <div className="bg-stone-950/40 rounded-xl p-3 border border-stone-800" data-testid="pulse-kpi-vs">
          <p className="text-[10px] uppercase tracking-widest text-stone-500 font-bold">Pazara Karşı</p>
          {vsPct === null
            ? <p className="text-lg font-black text-stone-400 mt-1">—</p>
            : (
              <div className="flex items-center gap-1.5 mt-1">
                {isAbove ? <TrendingUp className="w-4 h-4 text-amber-400" />
                  : isBelow ? <TrendingDown className="w-4 h-4 text-emerald-400" />
                  : <span className="w-4 h-4" />}
                <span className={`text-lg font-black ${isAbove ? "text-amber-300" : isBelow ? "text-emerald-300" : "text-stone-200"}`}>
                  {vsPct > 0 ? "+" : ""}{vsPct}%
                </span>
              </div>
            )}
          <p className="text-[10px] text-stone-500 mt-0.5">
            {isAbove ? "üstündesin" : isBelow ? "altındasın" : "pazarda"}
          </p>
        </div>
      </div>

      {/* Chart */}
      {hasData ? (
        <div className="bg-stone-950/30 rounded-xl p-3 border border-stone-800/50">
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="#3a3030" strokeDasharray="3 6" opacity={0.4} />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#a8a29e" }} />
              <YAxis tick={{ fontSize: 10, fill: "#a8a29e" }} tickFormatter={v => `£${v}`} />
              <Tooltip content={<PulseTooltip />} />
              <Legend wrapperStyle={{ fontSize: "10px", paddingTop: 6 }} />
              <Area dataKey="range" name="Rakip min-max" stroke="none" fill="#d946ef" fillOpacity={0.15} />
              <Line type="monotone" dataKey="avg" name="Rakip avg" stroke="#d946ef" strokeWidth={2}
                dot={false} activeDot={{ r: 4 }} connectNulls />
              <Line type="monotone" dataKey="our_rate" name="Bizim oran" stroke="#10b981" strokeWidth={2.5}
                dot={false} activeDot={{ r: 4 }} />
              {summary.market_avg && (
                <ReferenceLine y={summary.market_avg} stroke="#d946ef" strokeDasharray="2 4" strokeOpacity={0.6} />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="bg-stone-950/40 rounded-xl p-6 border border-dashed border-stone-700 text-center" data-testid="pulse-empty">
          <p className="text-sm text-stone-300 mb-1">Henüz rakip fiyatı taranmadı</p>
          <p className="text-[11px] text-stone-500 mb-4">
            {competitor_count > 0
              ? `${competitor_count} rakip kayıtlı — şimdi tara, ~1-2 dk içinde veriler gelir.`
              : "Bu şubeye hiç rakip eklenmemiş — önce 'Rakipler' sekmesinden ekle."}
          </p>
          {competitor_count > 0 && (
            <button onClick={triggerScan} disabled={scanning}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-fuchsia-500/20 hover:bg-fuchsia-500/30 text-fuchsia-200 text-sm font-bold transition disabled:opacity-50"
              data-testid="pulse-scan-now">
              {scanning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              Şimdi Tara
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function Kpi({ label, value, placeholder = "—", prefix = "", testid, tone }) {
  const toneClass = tone === "emerald" ? "text-emerald-300" : "text-stone-100";
  return (
    <div className="bg-stone-950/40 rounded-xl p-3 border border-stone-800" data-testid={testid}>
      <p className="text-[10px] uppercase tracking-widest text-stone-500 font-bold">{label}</p>
      <p className={`text-lg font-black mt-1 ${toneClass}`}>
        {value === null || value === undefined ? placeholder : `${prefix}${value}`}
      </p>
    </div>
  );
}

function PulseTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  const row = payload[0]?.payload || {};
  return (
    <div className="bg-stone-950/95 border border-fuchsia-500/40 rounded-lg p-2.5 text-[11px] shadow-xl">
      <div className="text-fuchsia-300 font-bold mb-1">{label}</div>
      {row.avg !== null && (
        <>
          <div className="text-stone-300">Rakip avg: <strong className="text-fuchsia-200">£{row.avg}</strong></div>
          <div className="text-stone-400">Aralık: £{row.min} – £{row.max}</div>
          <div className="text-stone-500 text-[10px]">{row.comp_count} rakip</div>
        </>
      )}
      <div className="text-emerald-300 mt-1">Bizim: <strong>£{row.our_rate}</strong></div>
    </div>
  );
}
