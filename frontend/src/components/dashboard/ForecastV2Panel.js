import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ChartLine,
  Calendar,
  TrendUp,
  Lightning,
  Info,
  ArrowsClockwise,
} from "@phosphor-icons/react";
import CopilotButton from "../CopilotButton";

const API = process.env.REACT_APP_BACKEND_URL;

const TIER_BG = {
  peak: "bg-rose-500 text-white",
  high: "bg-orange-400 text-white",
  medium: "bg-amber-200 text-stone-800",
  low: "bg-sky-200 text-stone-800",
  trough: "bg-stone-200 text-stone-500",
};

export default function ForecastV2Panel({ propertyId }) {
  const [tab, setTab] = useState("horizon");

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="forecast-v2-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <TrendUp size={12} weight="fill" className="text-violet-500" />
          <span>Gelir · 24 Ay Tahmin</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">
          Uzun Vadeli Talep Tahmini
        </h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          24 aya kadar aylık tahmin, 90-365 günlük talep takvimi, pickup eğrisi — rakiplerde ayrı modül, bizde dahili.
        </p>
      </div>

      <div className="flex gap-2 mb-5 border-b border-stone-200">
        <TabBtn active={tab === "horizon"} onClick={() => setTab("horizon")} testId="fcv2-tab-horizon">
          <ChartLine size={14} className="inline mr-1.5" />
          24 Ay Ufku
        </TabBtn>
        <TabBtn active={tab === "calendar"} onClick={() => setTab("calendar")} testId="fcv2-tab-calendar">
          <Calendar size={14} className="inline mr-1.5" />
          Talep Takvimi
        </TabBtn>
        <TabBtn active={tab === "pickup"} onClick={() => setTab("pickup")} testId="fcv2-tab-pickup">
          <Lightning size={14} className="inline mr-1.5" />
          Pickup Eğrisi
        </TabBtn>
      </div>

      {tab === "horizon" && <HorizonTab propertyId={propertyId} />}
      {tab === "calendar" && <CalendarTab propertyId={propertyId} />}
      {tab === "pickup" && <PickupTab propertyId={propertyId} />}
    </div>
  );
}

function TabBtn({ active, onClick, children, testId }) {
  return (
    <button
      onClick={onClick}
      data-testid={testId}
      className={`px-3.5 py-2 text-sm font-medium transition-all border-b-2 -mb-px ${
        active
          ? "border-violet-500 text-violet-700"
          : "border-transparent text-stone-500 hover:text-stone-800"
      }`}
    >
      {children}
    </button>
  );
}

/* ==================== HORIZON (24 MONTHS) ==================== */
function HorizonTab({ propertyId }) {
  const [months, setMonths] = useState(24);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/forecast-v2/horizon/${propertyId}?months=${months}`, { withCredentials: true });
      setData(r.data);
    } catch (e) {
      toast.error("Tahmin yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId, months]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="text-sm text-stone-400">Yükleniyor…</div>;
  if (!data) return null;

  const maxRev = Math.max(...data.forecast.map((f) => f.revenue), 1);
  const totalRev = data.forecast.reduce((s, f) => s + f.revenue, 0);
  const totalBk = data.forecast.reduce((s, f) => s + f.bookings, 0);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="Ufuk" value={`${months} ay`} color="violet" testId="fcv2-kpi-months" />
        <Kpi label="Toplam Tahmini Gelir" value={`£${Math.round(totalRev / 1000)}k`} color="emerald" testId="fcv2-kpi-revenue" />
        <Kpi label="Toplam Rezervasyon" value={totalBk} color="sky" testId="fcv2-kpi-bookings" />
        <Kpi label="YoY Büyüme" value={`${data.yoy_growth_pct > 0 ? "+" : ""}${data.yoy_growth_pct}%`} color={data.yoy_growth_pct >= 0 ? "emerald" : "rose"} testId="fcv2-kpi-yoy" />
      </div>

      <div className="flex justify-end">
        <CopilotButton
          contextType="forecast"
          data={{ months, yoy_growth_pct: data.yoy_growth_pct, total_revenue: totalRev, total_bookings: totalBk, top_months: data.forecast.slice(0, 6) }}
          label="AI Özet: Talep Stratejisi"
          testId="fcv2-copilot-btn"
        />
      </div>

      <div className="flex items-center gap-2">
        <label className="text-xs text-stone-600">Ufuk:</label>
        {[6, 12, 18, 24, 36].map((m) => (
          <button
            key={m}
            onClick={() => setMonths(m)}
            data-testid={`fcv2-horizon-${m}`}
            className={`px-2.5 py-1 text-xs rounded-full border transition-all ${
              months === m ? "bg-violet-500 text-white border-violet-500" : "bg-white text-stone-600 border-stone-200 hover:border-stone-400"
            }`}
          >
            {m} ay
          </button>
        ))}
        <button onClick={load} data-testid="fcv2-refresh" className="ml-auto px-3 py-1 text-xs rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50 inline-flex items-center gap-1.5">
          <ArrowsClockwise size={12} /> Yenile
        </button>
      </div>

      <div className="bg-white border border-stone-200 rounded-lg p-4">
        <div className="text-xs text-stone-500 mb-3 flex items-center gap-1.5">
          <Info size={12} /> Çubuk yüksekliği tahmini gelir, renk YoY değişim, ucu güven skoru.
        </div>
        <div className="flex items-end gap-1.5 h-56 overflow-x-auto" data-testid="fcv2-horizon-chart">
          {data.forecast.map((f) => {
            const h = Math.max(4, (f.revenue / maxRev) * 200);
            const yoy = f.vs_last_year;
            const barColor =
              yoy === null ? "bg-stone-300" :
              yoy > 5 ? "bg-emerald-500" :
              yoy < -5 ? "bg-rose-400" : "bg-sky-400";
            return (
              <div key={f.period} className="flex flex-col items-center flex-shrink-0 group relative" style={{ width: 30 }}>
                <div className="absolute -top-14 bg-stone-900 text-white text-[10px] rounded-md px-2 py-1.5 opacity-0 group-hover:opacity-100 transition-all pointer-events-none whitespace-nowrap z-10">
                  <div className="font-semibold">{f.label}</div>
                  <div>£{f.revenue.toLocaleString()}</div>
                  <div>{f.bookings} rez · ADR £{f.adr}</div>
                  <div>Güven %{f.confidence}</div>
                  {yoy !== null && <div className={yoy >= 0 ? "text-emerald-300" : "text-rose-300"}>{yoy >= 0 ? "+" : ""}{yoy}% YoY</div>}
                </div>
                <div className={`${barColor} rounded-t w-full transition-all group-hover:opacity-80`} style={{ height: h }} />
                <div className="text-[9px] text-stone-500 mt-1 -rotate-45 origin-top-left whitespace-nowrap">{f.label}</div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="bg-white border border-stone-200 rounded-lg overflow-hidden">
        <table className="w-full text-xs" data-testid="fcv2-horizon-table">
          <thead className="bg-stone-50 text-stone-500 uppercase tracking-wider text-[10px]">
            <tr>
              <th className="text-left px-3 py-2">Dönem</th>
              <th className="text-right px-3 py-2">Rezervasyon</th>
              <th className="text-right px-3 py-2">Gelir</th>
              <th className="text-right px-3 py-2">ADR</th>
              <th className="text-right px-3 py-2">LOS</th>
              <th className="text-right px-3 py-2">YoY</th>
              <th className="text-right px-3 py-2">Güven</th>
            </tr>
          </thead>
          <tbody>
            {data.forecast.slice(0, 12).map((f) => (
              <tr key={f.period} className="border-t border-stone-100">
                <td className="px-3 py-2 font-medium text-stone-800">{f.label}</td>
                <td className="px-3 py-2 text-right">{f.bookings}</td>
                <td className="px-3 py-2 text-right">£{f.revenue.toLocaleString()}</td>
                <td className="px-3 py-2 text-right">£{f.adr}</td>
                <td className="px-3 py-2 text-right">{f.los}</td>
                <td className={`px-3 py-2 text-right ${f.vs_last_year > 0 ? "text-emerald-600" : f.vs_last_year < 0 ? "text-rose-600" : "text-stone-500"}`}>
                  {f.vs_last_year !== null ? `${f.vs_last_year > 0 ? "+" : ""}${f.vs_last_year}%` : "—"}
                </td>
                <td className="px-3 py-2 text-right text-stone-500">{f.confidence}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Kpi({ label, value, color, testId }) {
  const bg = {
    violet: "bg-violet-50 text-violet-700",
    emerald: "bg-emerald-50 text-emerald-700",
    sky: "bg-sky-50 text-sky-700",
    rose: "bg-rose-50 text-rose-700",
    amber: "bg-amber-50 text-amber-700",
  }[color] || "bg-stone-50 text-stone-700";
  return (
    <div className={`${bg} border border-stone-100 rounded-lg p-3.5`} data-testid={testId}>
      <div className="text-[10px] uppercase tracking-wider opacity-70">{label}</div>
      <div className="text-xl font-semibold mt-1">{value}</div>
    </div>
  );
}

/* ==================== DEMAND CALENDAR ==================== */
function CalendarTab({ propertyId }) {
  const [days, setDays] = useState(90);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/forecast-v2/demand-calendar/${propertyId}?days=${days}`, { withCredentials: true });
      setData(r.data);
    } catch (e) {
      toast.error("Talep takvimi yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId, days]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="text-sm text-stone-400">Yükleniyor…</div>;
  if (!data) return null;

  // Group by month for display
  const byMonth = {};
  data.days.forEach((d) => {
    const ym = d.date.slice(0, 7);
    byMonth[ym] = byMonth[ym] || [];
    byMonth[ym].push(d);
  });

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="Gün Aralığı" value={`${days} gün`} color="violet" testId="fcv2-cal-kpi-days" />
        <Kpi label="Ort. Talep Skoru" value={data.avg_demand_score} color="sky" testId="fcv2-cal-kpi-avg" />
        <Kpi label="Peak Günler" value={data.peak_days_count} color="rose" testId="fcv2-cal-kpi-peak" />
        <Kpi label="Trough Günler" value={data.trough_days_count} color="amber" testId="fcv2-cal-kpi-trough" />
      </div>

      <div className="flex items-center gap-2">
        <label className="text-xs text-stone-600">Aralık:</label>
        {[30, 60, 90, 180, 365].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            data-testid={`fcv2-cal-days-${d}`}
            className={`px-2.5 py-1 text-xs rounded-full border transition-all ${
              days === d ? "bg-violet-500 text-white border-violet-500" : "bg-white text-stone-600 border-stone-200 hover:border-stone-400"
            }`}
          >
            {d} gün
          </button>
        ))}
      </div>

      {/* Legend */}
      <div className="flex gap-2 flex-wrap items-center text-xs text-stone-600">
        <span className="mr-2 font-medium">Fiyat Önerisi:</span>
        {Object.entries({ peak: "+20%", high: "+10%", medium: "BAR", low: "-10%", trough: "-20%" }).map(([t, l]) => (
          <span key={t} className={`px-2 py-0.5 rounded ${TIER_BG[t]}`}>{l}</span>
        ))}
      </div>

      <div className="space-y-5" data-testid="fcv2-calendar-grid">
        {Object.entries(byMonth).map(([ym, ds]) => (
          <MonthGrid key={ym} ym={ym} days={ds} />
        ))}
      </div>
    </div>
  );
}

function MonthGrid({ ym, days }) {
  const [y, m] = ym.split("-").map(Number);
  const firstDow = (new Date(y, m - 1, 1).getDay() + 6) % 7; // Mon=0..Sun=6
  const cells = [];
  for (let i = 0; i < firstDow; i++) cells.push(null);
  days.forEach((d) => cells.push(d));

  const monthLabel = new Date(y, m - 1, 1).toLocaleDateString("tr-TR", { month: "long", year: "numeric" });
  return (
    <div>
      <div className="text-xs font-semibold text-stone-700 mb-2 capitalize">{monthLabel}</div>
      <div className="grid grid-cols-7 gap-0.5 text-[9px] text-stone-400 mb-1">
        {["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"].map((d) => <div key={d} className="text-center">{d}</div>)}
      </div>
      <div className="grid grid-cols-7 gap-0.5">
        {cells.map((c, i) => {
          if (!c) return <div key={i} className="aspect-square" />;
          const tier = c.tier;
          return (
            <div
              key={c.date}
              data-testid={`fcv2-day-${c.date}`}
              className={`${TIER_BG[tier]} aspect-square rounded-sm p-1 text-[9px] relative group cursor-pointer hover:ring-2 hover:ring-stone-400 transition-all`}
              title={`${c.date} · Skor ${c.demand_score} · ${c.tier_label}`}
            >
              <div className="font-semibold">{parseInt(c.date.slice(8))}</div>
              <div className="opacity-80">{c.demand_score}</div>
              {c.holiday && <div className="absolute top-0 right-0 w-1.5 h-1.5 bg-white rounded-full border border-stone-600" title={c.holiday} />}
              <div className="absolute left-0 right-0 bottom-full mb-1 bg-stone-900 text-white text-[10px] rounded-md px-2 py-1.5 opacity-0 group-hover:opacity-100 transition-all pointer-events-none whitespace-nowrap z-10">
                <div className="font-semibold">{c.date} · {c.dow}</div>
                <div>Skor {c.demand_score} · OTB {c.otb}</div>
                <div>Doluluk %{c.occupancy_pct}</div>
                <div>{c.tier_label}</div>
                {c.holiday && <div className="text-amber-300">★ {c.holiday}</div>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ==================== PICKUP CURVE ==================== */
function PickupTab({ propertyId }) {
  const [targetDate, setTargetDate] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() + 30);
    return d.toISOString().slice(0, 10);
  });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/forecast-v2/pickup-curve/${propertyId}?target_date=${targetDate}`, { withCredentials: true });
      setData(r.data);
    } catch (e) {
      toast.error("Pickup verisi yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId, targetDate]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2 flex-wrap">
        <label className="text-xs text-stone-600">Hedef tarih:</label>
        <input
          type="date"
          value={targetDate}
          onChange={(e) => setTargetDate(e.target.value)}
          data-testid="fcv2-pickup-date"
          className="px-2.5 py-1 text-xs border border-stone-200 rounded-md focus:outline-none focus:border-stone-400"
        />
        <button onClick={load} data-testid="fcv2-pickup-refresh" className="px-3 py-1 text-xs rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50 inline-flex items-center gap-1.5">
          <ArrowsClockwise size={12} /> Yenile
        </button>
      </div>

      {loading && <div className="text-sm text-stone-400">Yükleniyor…</div>}

      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Kpi label="Kalan Gün" value={data.days_to_go} color="sky" testId="fcv2-pickup-kpi-dtg" />
            <Kpi label="Mevcut OTB" value={data.current_otb} color="violet" testId="fcv2-pickup-kpi-otb" />
            <Kpi label="Tarih. Karşılaştırma"
                 value={data.pace_vs_hist_pct !== null ? `${data.pace_vs_hist_pct > 0 ? "+" : ""}${data.pace_vs_hist_pct}%` : "—"}
                 color={data.pace_status === "ahead" ? "emerald" : data.pace_status === "behind" ? "rose" : "sky"}
                 testId="fcv2-pickup-kpi-pace" />
            <Kpi label="Pace Durumu"
                 value={{ ahead: "Önde ▲", behind: "Geride ▼", on_track: "Normal ●", no_history: "Veri yok" }[data.pace_status] || "—"}
                 color={data.pace_status === "ahead" ? "emerald" : data.pace_status === "behind" ? "rose" : "amber"}
                 testId="fcv2-pickup-kpi-status" />
          </div>

          <PickupChart actual={data.actual_curve} historical={data.historical_avg_curve} />
        </>
      )}
    </div>
  );
}

function PickupChart({ actual, historical }) {
  const allVals = [
    ...actual.map((p) => p.bookings),
    ...historical.map((p) => p.avg_bookings),
  ];
  const max = Math.max(...allVals, 1);
  const width = 700;
  const height = 200;
  const actualSorted = [...actual].sort((a, b) => b.lead_day - a.lead_day); // high lead -> low lead (left to right = further to closer)
  const histSorted = [...historical].sort((a, b) => b.lead_day - a.lead_day);

  const toPoints = (pts, field) => {
    if (!pts.length) return "";
    return pts.map((p, i) => {
      const x = (i / (pts.length - 1)) * width;
      const y = height - (p[field] / max) * height;
      return `${x},${y}`;
    }).join(" ");
  };

  return (
    <div className="bg-white border border-stone-200 rounded-lg p-4" data-testid="fcv2-pickup-chart">
      <div className="text-xs text-stone-500 mb-3">X ekseni: varışa kalan gün (sol=90 → sağ=0). Y ekseni: toplam rezervasyon birikimi.</div>
      <svg viewBox={`0 0 ${width} ${height + 30}`} className="w-full">
        <polyline fill="none" stroke="#a1a1aa" strokeWidth="1.5" strokeDasharray="4 3" points={toPoints(histSorted, "avg_bookings")} />
        <polyline fill="none" stroke="#7c3aed" strokeWidth="2.5" points={toPoints(actualSorted, "bookings")} />
        {/* x axis labels */}
        <text x="0" y={height + 20} fontSize="10" fill="#78716c">90 gün</text>
        <text x={width / 2 - 15} y={height + 20} fontSize="10" fill="#78716c">45 gün</text>
        <text x={width - 25} y={height + 20} fontSize="10" fill="#78716c">0 gün</text>
      </svg>
      <div className="flex gap-4 text-xs mt-2">
        <span className="inline-flex items-center gap-1.5"><span className="inline-block w-5 h-0.5 bg-violet-500" /> Bu hedef</span>
        <span className="inline-flex items-center gap-1.5"><span className="inline-block w-5 h-0.5 bg-stone-400 border-dashed" style={{ borderTop: "1.5px dashed #a1a1aa", backgroundColor: "transparent" }} /> Geçmiş ortalama</span>
      </div>
    </div>
  );
}
