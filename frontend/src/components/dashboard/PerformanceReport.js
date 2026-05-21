import { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { TrendingUp, TrendingDown, Zap, BarChart3, Calendar, Radar, PartyPopper, Activity, RefreshCw, Wallet, Pencil, X, Check, Loader2 } from "lucide-react";
import useLivePolling, { LiveBadge } from "../../hooks/useLivePolling";
import { makeCurrencyFormatter } from "../../lib/currency";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SOURCE_LABELS = {
  auto_scanner: { label: "Auto Scanner", color: "bg-emerald-500" },
  market_robot: { label: "Market Robot", color: "bg-indigo-500" },
  ai_dynamic_pricing: { label: "AI Dynamic Pricing", color: "bg-violet-500" },
  event_intelligence: { label: "Event Intelligence", color: "bg-red-500" },
};

export const PerformanceReport = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  // Inline editable manual room count — accessible right from the hero banner
  // so operators don't have to navigate to Onboarding to fix a wrong count.
  const [editingRoomCount, setEditingRoomCount] = useState(false);
  const [roomCountInput, setRoomCountInput] = useState("");
  const [savingRoomCount, setSavingRoomCount] = useState(false);
  // Live indicator for any in-progress background room-count scan kicked off
  // from the Onboarding "Re-scan room count" button. Polled every 10s so the
  // banner reflects scrape progress without the user having to switch tabs.
  const [roomCountJob, setRoomCountJob] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    axios.get(`${API}/revenue/market-robot/${propertyId}/performance`)
      .then(r => { setData(r.data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);
  // ⚡ Performance KPIs (RevPAR, ADR, occupancy) refresh every 90s
  useLivePolling(load, { intervalMs: 90000 });

  const saveRoomCount = async (clear = false) => {
    setSavingRoomCount(true);
    try {
      const payload = clear ? { room_count: null } : { room_count: parseInt(roomCountInput, 10) || 0 };
      const { data: res } = await axios.post(
        `${API}/revenue/market-robot/${propertyId}/room-count/manual`,
        payload,
      );
      if (res.cleared) {
        toast.success("Manuel oda sayısı temizlendi");
      } else {
        toast.success(`Oda sayısı kaydedildi: ${res.manual_room_count}`);
      }
      setEditingRoomCount(false);
      setRoomCountInput("");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Kaydetme başarısız");
    } finally { setSavingRoomCount(false); }
  };

  // Background-scan job status poller. Polls every 10s while a job is
  // 'running'; stops polling as soon as the job finishes (or there is no
  // job). When a job transitions from 'running' to 'done'/'no_data' we also
  // re-fetch the performance data so the banner shows the new room count.
  useEffect(() => {
    let timer;
    let stopped = false;
    const tick = async () => {
      try {
        const { data: j } = await axios.get(
          `${API}/revenue/market-robot/${propertyId}/refresh-room-count/status`,
        );
        if (stopped) return;
        const prevStatus = roomCountJob?.status;
        setRoomCountJob(j);
        // If job just finished, refresh main performance data
        if (prevStatus === "running" && j.status !== "running") {
          load();
        }
        // Keep polling while running, otherwise back off to 30s
        timer = setTimeout(tick, j.status === "running" ? 10000 : 30000);
      } catch {
        if (!stopped) timer = setTimeout(tick, 30000);
      }
    };
    tick();
    return () => { stopped = true; if (timer) clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [propertyId]);

  // Currency formatter driven by the property's configured currency.
  // Hooks must run unconditionally — derive once and gracefully fall back
  // to GBP until the data arrives.
  const fmt = useMemo(
    () => makeCurrencyFormatter(data?.property_currency || ""),
    [data?.property_currency]
  );

  if (loading) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Calculating performance...</div>;
  if (!data) return null;

  const { kpis, by_source, daily_impact, monthly_impact, property_currency } = data;
  const cur = (v) => fmt.format(v, 0);

  // Bar chart max
  const maxMonthly = Math.max(...monthly_impact.map(m => Math.abs(m.est_revenue_uplift)), 1);

  return (
    <div className="space-y-6" data-testid="performance-report">
      {/* Hero Banner */}
      <div className="bg-gradient-to-r from-emerald-800 via-emerald-900 to-teal-900 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-white/10 rounded-xl flex items-center justify-center">
              <Wallet className="w-6 h-6 text-emerald-300" />
            </div>
            <div>
              <h2 className="text-xl font-bold">Robot Performance Report</h2>
              <p className="text-sm text-white/60">
                Revenue impact from automated pricing across all sources
                <span className="ml-2 inline-flex items-center gap-1 text-[10px] text-white/40">
                  · <span className="font-mono text-emerald-200">{property_currency || "GBP"}</span>
                  {data.total_rooms ? (
                    editingRoomCount ? (
                      <span className="inline-flex items-center gap-1 ml-2 bg-white/10 rounded-lg px-2 py-1">
                        <input
                          type="number"
                          min="1"
                          max="5000"
                          autoFocus
                          value={roomCountInput}
                          onChange={(e) => setRoomCountInput(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") saveRoomCount(false);
                            if (e.key === "Escape") { setEditingRoomCount(false); setRoomCountInput(""); }
                          }}
                          data-testid="hero-room-count-input"
                          className="w-16 px-1 py-0.5 text-xs rounded bg-white/20 text-white placeholder-white/40 focus:outline-none focus:bg-white/30 border border-white/30"
                          placeholder="9"
                        />
                        <button
                          onClick={() => saveRoomCount(false)}
                          disabled={savingRoomCount || !roomCountInput}
                          data-testid="hero-room-count-save"
                          className="p-1 rounded bg-emerald-500/40 hover:bg-emerald-500/60 disabled:opacity-50"
                          title="Kaydet"
                        >
                          {savingRoomCount ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
                        </button>
                        <button
                          onClick={() => { setEditingRoomCount(false); setRoomCountInput(""); }}
                          data-testid="hero-room-count-cancel"
                          className="p-1 rounded bg-rose-500/40 hover:bg-rose-500/60"
                          title="İptal"
                        >
                          <X className="w-3 h-3" />
                        </button>
                        {data.room_count_source === "manual" && (
                          <button
                            onClick={() => saveRoomCount(true)}
                            disabled={savingRoomCount}
                            data-testid="hero-room-count-clear"
                            className="p-1 ml-1 rounded bg-amber-500/40 hover:bg-amber-500/60 text-[9px] px-1.5"
                            title="Manuel değeri temizle (auto'ya dön)"
                          >
                            Temizle
                          </button>
                        )}
                      </span>
                    ) : (
                      <span title={
                        data.room_count_source === "manual"
                          ? "Manuel girilen oda sayısı — değiştirmek için tıklayın"
                          : data.room_count_source === "booking_com"
                            ? "Booking.com sayfasından alındı — manuel override için tıklayın"
                            : data.room_count_source === "room_types"
                              ? "Lokal room_types toplamı — manuel girmek için tıklayın"
                              : "Fallback — manuel girmek için tıklayın"
                      }>
                        ·{" "}
                        <button
                          onClick={() => {
                            setRoomCountInput(String(data.total_rooms));
                            setEditingRoomCount(true);
                          }}
                          data-testid="hero-room-count-edit"
                          className="inline-flex items-center gap-1 hover:bg-white/10 rounded px-1.5 py-0.5 transition-colors cursor-pointer"
                        >
                          <span className="text-white/80 font-semibold">{data.total_rooms}</span>
                          <span className="text-white/40">rooms</span>
                          <Pencil className="w-2.5 h-2.5 opacity-50" />
                          <span className={`ml-0.5 px-1 rounded text-[8px] ${data.room_count_source === "manual" ? "bg-fuchsia-500/30 text-fuchsia-200" : data.room_count_source === "booking_com" ? "bg-sky-500/30 text-sky-200" : "bg-stone-500/30 text-stone-200"}`}>
                            {data.room_count_source === "manual" ? "manuel" : data.room_count_source === "booking_com" ? "booking.com" : data.room_count_source === "room_types" ? "local" : "fallback"}
                          </span>
                        </button>
                      </span>
                    )
                  ) : null}
                  {/* Live scanning indicator while a background room-count
                       job is running for this property */}
                  {roomCountJob?.status === "running" && (
                    <span
                      data-testid="room-count-scanning-indicator"
                      title="Booking.com için arka planda oda sayısı taraması devam ediyor"
                      className="inline-flex items-center gap-1 ml-1 px-1.5 py-0.5 rounded-full bg-amber-500/30 text-amber-200 text-[9px] font-bold uppercase tracking-wide animate-pulse"
                    >
                      <Loader2 className="w-2.5 h-2.5 animate-spin" />
                      Taranıyor
                    </span>
                  )}
                  {roomCountJob?.status === "no_data" && roomCountJob?.finished_at && (
                    <span
                      data-testid="room-count-scan-failed"
                      title={roomCountJob?.error || "Otomatik tarama başarısız — lütfen manuel girin"}
                      className="inline-flex items-center gap-1 ml-1 px-1.5 py-0.5 rounded-full bg-rose-500/30 text-rose-200 text-[9px] font-bold uppercase tracking-wide cursor-help"
                    >
                      Otomatik tarama yapılamadı
                    </span>
                  )}
                  {data.occupancy_assumption ? (
                    <span title={`Estimated revenue = per-room uplift × ${data.total_rooms} rooms × ${Math.round(data.occupancy_assumption*100)}% occupancy (${data.occupancy_basis === "actual_30d" ? "actual last-30-day occupancy" : "70% industry-average fallback (no booking history yet)"})`}>
                      · {Math.round(data.occupancy_assumption*100)}%
                      <span className={`ml-1 px-1 rounded text-[8px] ${data.occupancy_basis === "actual_30d" ? "bg-emerald-500/30 text-emerald-200" : "bg-amber-500/30 text-amber-200"}`}>
                        {data.occupancy_basis === "actual_30d" ? "actual" : "est."}
                      </span>
                    </span>
                  ) : null}
                </span>
              </p>
            </div>
          </div>
          <button onClick={load} className="flex items-center gap-2 bg-white/10 hover:bg-white/20 border border-white/20 text-white px-4 py-2 rounded-xl text-sm font-medium" data-testid="perf-refresh">
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
        </div>

        {/* Hero KPIs */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5">
          <div className="bg-white/5 rounded-xl p-4 text-center">
            <p className="text-[10px] text-white/40 uppercase">Estimated Revenue Uplift</p>
            <p className={`text-2xl font-bold mt-1 ${kpis.estimated_revenue_uplift >= 0 ? "text-emerald-300" : "text-red-300"}`}>
              {kpis.estimated_revenue_uplift >= 0 ? "+" : ""}{cur(kpis.estimated_revenue_uplift)}
            </p>
            <p className="text-[10px] text-white/30 mt-1">Total lifetime impact</p>
          </div>
          <div className="bg-white/5 rounded-xl p-4 text-center">
            <p className="text-[10px] text-white/40 uppercase">This Month</p>
            <p className={`text-2xl font-bold mt-1 ${kpis.monthly_revenue_uplift >= 0 ? "text-emerald-300" : "text-red-300"}`}>
              {kpis.monthly_revenue_uplift >= 0 ? "+" : ""}{cur(kpis.monthly_revenue_uplift)}
            </p>
            <p className="text-[10px] text-white/30 mt-1">Current month impact</p>
          </div>
          <div className="bg-white/5 rounded-xl p-4 text-center">
            <p className="text-[10px] text-white/40 uppercase">Days Optimized</p>
            <p className="text-2xl font-bold mt-1">{kpis.total_days_adjusted}</p>
            <p className="text-[10px] text-white/30 mt-1">{kpis.increases} up / {kpis.decreases} down</p>
          </div>
          <div className="bg-white/5 rounded-xl p-4 text-center">
            <p className="text-[10px] text-white/40 uppercase">Event Revenue</p>
            <p className="text-2xl font-bold mt-1 text-red-300">+{cur(kpis.event_revenue_uplift)}</p>
            <p className="text-[10px] text-white/30 mt-1">{kpis.event_boost_days} event-boosted days</p>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4" data-testid="perf-stats">
        <div className="bg-white border border-stone-200 rounded-2xl p-5 text-center">
          <p className="text-[10px] text-stone-400 uppercase tracking-wider font-medium">Avg Uplift/Day</p>
          <p className={`text-2xl font-bold mt-1 ${kpis.avg_uplift_per_day >= 0 ? "text-emerald-600" : "text-red-500"}`}>
            {kpis.avg_uplift_per_day >= 0 ? "+" : ""}{cur(kpis.avg_uplift_per_day)}
          </p>
          <p className="text-[10px] text-stone-400">per room/night</p>
        </div>
        <div className="bg-white border border-stone-200 rounded-2xl p-5 text-center">
          <p className="text-[10px] text-stone-400 uppercase tracking-wider font-medium">Total Scans</p>
          <p className="text-2xl font-bold text-indigo-600 mt-1">{kpis.total_scans}</p>
          <p className="text-[10px] text-stone-400">{kpis.scans_this_month} this month</p>
        </div>
        <div className="bg-white border border-stone-200 rounded-2xl p-5 text-center">
          <p className="text-[10px] text-stone-400 uppercase tracking-wider font-medium">Events Detected</p>
          <p className="text-2xl font-bold text-red-500 mt-1">{kpis.total_events_detected}</p>
          <p className="text-[10px] text-stone-400">{kpis.mega_events} mega, {kpis.large_events} large</p>
        </div>
        <div className="bg-white border border-emerald-100 rounded-2xl p-5 text-center">
          <p className="text-[10px] text-emerald-600 uppercase tracking-wider font-medium">Rate Increases</p>
          <p className="text-2xl font-bold text-emerald-600 mt-1">{kpis.increases}</p>
          <p className="text-[10px] text-stone-400">days with higher rates</p>
        </div>
        <div className="bg-white border border-red-100 rounded-2xl p-5 text-center">
          <p className="text-[10px] text-red-500 uppercase tracking-wider font-medium">Rate Decreases</p>
          <p className="text-2xl font-bold text-red-500 mt-1">{kpis.decreases}</p>
          <p className="text-[10px] text-stone-400">days with lower rates</p>
        </div>
      </div>

      {/* Revenue by Source */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="perf-by-source">
          <h3 className="font-bold text-stone-800 mb-4 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-stone-400" /> Revenue Impact by Source
          </h3>
          <div className="space-y-3">
            {Object.entries(by_source).map(([key, value]) => {
              const src = SOURCE_LABELS[key] || { label: key, color: "bg-stone-400" };
              const totalSource = Object.values(by_source).reduce((s, v) => s + Math.abs(v), 0) || 1;
              const pct = Math.abs(value) / totalSource * 100;
              return (
                <div key={key}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className={`w-3 h-3 rounded-full ${src.color}`} />
                      <span className="text-sm font-medium text-stone-700">{src.label}</span>
                    </div>
                    <span className={`text-sm font-bold ${value >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                      {value >= 0 ? "+" : ""}{cur(value)}
                    </span>
                  </div>
                  <div className="bg-stone-100 rounded-full h-2.5 overflow-hidden">
                    <div className={`h-2.5 rounded-full transition-all ${src.color}`} style={{ width: `${Math.max(pct, 2)}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Monthly Revenue Chart */}
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="perf-monthly">
          <h3 className="font-bold text-stone-800 mb-4 flex items-center gap-2">
            <Calendar className="w-4 h-4 text-stone-400" /> Monthly Revenue Impact
          </h3>
          <div className="space-y-2">
            {monthly_impact.map(m => {
              const pct = (Math.abs(m.est_revenue_uplift) / maxMonthly) * 100;
              const isPos = m.est_revenue_uplift >= 0;
              return (
                <div key={m.month} className="flex items-center gap-3">
                  <span className="w-16 text-xs font-bold text-stone-600">{m.month_label}</span>
                  <div className="flex-1 bg-stone-100 rounded-full h-5 overflow-hidden relative">
                    <div className={`h-5 rounded-full transition-all ${isPos ? "bg-emerald-500" : "bg-red-400"}`} style={{ width: `${Math.max(pct, 3)}%` }} />
                    <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white mix-blend-difference">
                      {isPos ? "+" : ""}{cur(m.est_revenue_uplift)}
                    </span>
                  </div>
                  <div className="w-20 text-right">
                    <span className="text-[10px] text-stone-400">{m.days_adjusted}d</span>
                    {m.event_days > 0 && <span className="text-[9px] text-red-500 ml-1">{m.event_days}ev</span>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Daily Impact Table */}
      {daily_impact.length > 0 && (
        <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden" data-testid="perf-daily">
          <div className="px-5 py-3 bg-stone-50 border-b flex items-center justify-between">
            <span className="font-bold text-stone-800 text-sm">Daily Rate Impact (Last 14 Days)</span>
            <Badge className="bg-stone-100 text-stone-500 text-[10px]">{daily_impact.length} days</Badge>
          </div>
          <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-white z-10">
                <tr className="border-b">
                  {["Date", "Base Rate", "Robot Rate", "Uplift", "Change", "Source", "Event"].map(h => (
                    <th key={h} className="px-3 py-2 text-xs font-semibold text-stone-500 text-center">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {daily_impact.map(d => (
                  <tr key={d.date} className={`border-b border-stone-50 ${d.has_event ? "bg-red-50/20" : d.uplift > 0 ? "bg-emerald-50/20" : d.uplift < 0 ? "bg-red-50/10" : ""}`}>
                    <td className="px-3 py-2 font-medium text-stone-700 text-xs whitespace-nowrap">
                      {new Date(d.date + "T00:00:00").toLocaleDateString("en", { weekday: "short", month: "short", day: "numeric" })}
                    </td>
                    <td className="px-3 py-2 text-center text-stone-400">{cur(d.base_rate)}</td>
                    <td className="px-3 py-2 text-center font-bold text-violet-700">{cur(d.robot_rate)}</td>
                    <td className="px-3 py-2 text-center">
                      <span className={`font-bold ${d.uplift > 0 ? "text-emerald-600" : d.uplift < 0 ? "text-red-500" : "text-stone-400"}`}>
                        {d.uplift > 0 ? "+" : ""}{cur(d.uplift)}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span className={`flex items-center justify-center gap-0.5 text-xs font-semibold ${d.uplift_pct > 0 ? "text-emerald-600" : d.uplift_pct < 0 ? "text-red-500" : "text-stone-400"}`}>
                        {d.uplift_pct > 0 ? <TrendingUp className="w-3 h-3" /> : d.uplift_pct < 0 ? <TrendingDown className="w-3 h-3" /> : null}
                        {d.uplift_pct > 0 ? "+" : ""}{d.uplift_pct}%
                      </span>
                    </td>
                    <td className="px-3 py-2 text-center">
                      <Badge className={`text-[8px] ${
                        d.source === "ai-dynamic-pricing" ? "bg-violet-100 text-violet-700" :
                        d.source === "auto-scanner" ? "bg-emerald-100 text-emerald-700" :
                        d.source === "event-intelligence" ? "bg-red-100 text-red-700" :
                        "bg-indigo-100 text-indigo-700"
                      }`}>{d.source.replace(/-/g, " ")}</Badge>
                    </td>
                    <td className="px-3 py-2 text-center">
                      {d.has_event ? <PartyPopper className="w-4 h-4 text-red-400 mx-auto" /> : <span className="text-stone-300">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
