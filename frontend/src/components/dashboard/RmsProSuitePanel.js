/**
 * RmsProSuitePanel — Tek panelde 6 yeni özellik:
 * 1. RevPAG vs RevPAR
 * 2. Quality Score
 * 3. Forecast Accuracy
 * 4. Group Pricing Optimizer (modal)
 * 5. Autopilot Mode toggle
 * 6. Autopilot History
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Award, Brain, Activity, Users, Bot, History,
  TrendingUp, Loader2, Power, Zap, Sparkles, RefreshCw,
} from "lucide-react";
import useLivePolling from "../../hooks/useLivePolling";
import GroupPricingModal from "./GroupPricingModal";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function RmsProSuitePanel({ propertyId = "aldgate-flats" }) {
  const [revpag, setRevpag] = useState(null);
  const [quality, setQuality] = useState(null);
  const [accuracy, setAccuracy] = useState(null);
  const [autopilot, setAutopilot] = useState(null);
  const [groupOpen, setGroupOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!propertyId || propertyId === "all") {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [r1, r2, r3, r4] = await Promise.all([
        axios.get(`${API}/rms-pro/revpag/${propertyId}?days=30`),
        axios.get(`${API}/rms-pro/quality-score/${propertyId}`),
        axios.get(`${API}/rms-pro/forecast-accuracy/${propertyId}?days=90`),
        axios.get(`${API}/rms-pro/autopilot/config`),
      ]);
      setRevpag(r1.data);
      setQuality(r2.data);
      setAccuracy(r3.data);
      setAutopilot(r4.data);
    } catch { /* noop */ }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);
  useLivePolling(load, { intervalMs: 60000 });

  const toggleAutopilot = async () => {
    if (!autopilot) return;
    try {
      const { data } = await axios.post(`${API}/rms-pro/autopilot/config`, {
        ...autopilot,
        enabled: !autopilot.enabled,
      });
      setAutopilot(data.config);
      toast.success(data.config.enabled ? "🤖 Autopilot AÇIK · her gece otomatik AI optimize" : "Autopilot KAPALI");
    } catch {
      toast.error("Autopilot ayarlanamadı");
    }
  };

  if (propertyId === "all") {
    return (
      <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-6 text-center text-xs text-stone-500">
        Bu görünüm tek şube içindir — soldan bir şube seçin.
      </div>
    );
  }

  if (loading || !revpag) {
    return (
      <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-8 text-center" data-testid="rms-pro-loading">
        <Loader2 className="w-6 h-6 text-stone-500 animate-spin mx-auto" />
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="rms-pro-panel">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-gradient-to-br from-emerald-500/30 via-cyan-500/30 to-fuchsia-500/30">
            <Sparkles className="w-5 h-5 text-cyan-200" />
          </div>
          <div>
            <h2 className="text-sm font-black bg-gradient-to-r from-emerald-300 via-cyan-300 to-fuchsia-300 bg-clip-text text-transparent">
              RMS Pro Suite
            </h2>
            <p className="text-[11px] text-stone-400">Flyr · RoomPriceGenie · Duetto · IDeaS · BEONx · Atomize parity</p>
          </div>
        </div>
        <button onClick={load}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-xs text-stone-300"
          data-testid="rms-pro-refresh">
          <RefreshCw className="w-3.5 h-3.5" /> Yenile
        </button>
      </div>

      {/* Top KPI grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* RevPAG vs RevPAR — BEONx parity */}
        <KpiCard
          icon={Users} tone="emerald" title="RevPAG" subtitle="BEONx metric"
          big={`£${revpag.revpag}`}
          subtext={`RevPAR £${revpag.revpar} · ADR £${revpag.adr}`}
          footer={`Party: ${revpag.avg_party_size} guests · Occ ${revpag.occupancy_pct}%`}
          testid="kpi-revpag"
        />

        {/* Quality Score — BEONx 21+ factors */}
        <KpiCard
          icon={Award} tone="amber" title="Quality Score" subtitle="BEONx-style"
          big={`${quality.quality_score}`}
          unit="/100"
          subtext={`Önerilen uplift: ${quality.recommended_rate_uplift_pct > 0 ? "+" : ""}${quality.recommended_rate_uplift_pct}%`}
          footer={`${quality.factors.length} faktör değerlendirildi`}
          testid="kpi-quality"
        />

        {/* Forecast Accuracy — Cloudbeds 95% benchmark */}
        <KpiCard
          icon={Activity} tone="cyan" title="Forecast Acc." subtitle="Cloudbeds parity"
          big={accuracy.occupancy_accuracy_pct !== null ? `${accuracy.occupancy_accuracy_pct}%` : "—"}
          subtext={`Revenue: ${accuracy.revenue_accuracy_pct !== null ? `${accuracy.revenue_accuracy_pct}%` : "—"}`}
          footer={`${accuracy.scored_samples || 0} scored snapshots · benchmark ${accuracy.benchmark_industry}%`}
          testid="kpi-accuracy"
          highlight={accuracy.occupancy_accuracy_pct !== null && accuracy.occupancy_accuracy_pct >= 90}
        />

        {/* Autopilot — Atomize/Flyr fire-and-forget */}
        <div className={`bg-stone-900/60 border rounded-xl p-4 transition ${autopilot?.enabled ? "border-emerald-500/60" : "border-stone-800"}`} data-testid="kpi-autopilot">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Bot className={`w-4 h-4 ${autopilot?.enabled ? "text-emerald-400" : "text-stone-500"}`} />
              <span className="text-xs font-black text-stone-100">Autopilot</span>
            </div>
            <span className="text-[9px] uppercase tracking-widest text-stone-500 font-bold">Atomize parity</span>
          </div>
          <button onClick={toggleAutopilot}
            className={`w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-black transition ${
              autopilot?.enabled
                ? "bg-emerald-500/30 hover:bg-emerald-500/40 text-emerald-200"
                : "bg-stone-800 hover:bg-stone-700 text-stone-300"
            }`}
            data-testid="autopilot-toggle">
            <Power className="w-3.5 h-3.5" />
            {autopilot?.enabled ? "AÇIK" : "Kapalı"}
          </button>
          {autopilot?.enabled && (
            <p className="text-[10px] text-stone-400 mt-2 text-center">
              Her gece {autopilot.schedule_hour_utc}:00 UTC · ≥{autopilot.min_uplift_to_apply_pct}% uplift'te uygula
            </p>
          )}
          {autopilot?.last_run_at && (
            <p className="text-[10px] text-stone-500 mt-1 text-center">
              Son çalışma: {new Date(autopilot.last_run_at).toLocaleString("tr-TR")}
            </p>
          )}
        </div>
      </div>

      {/* Group Pricing CTA — IDeaS/Flyr signature feature */}
      <button onClick={() => setGroupOpen(true)}
        className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-gradient-to-r from-violet-500/20 via-purple-500/20 to-violet-500/20 hover:from-violet-500/35 hover:via-purple-500/35 hover:to-violet-500/35 border border-violet-500/40 text-violet-100 text-sm font-black transition group"
        data-testid="group-pricing-cta">
        <Users className="w-5 h-5 group-hover:scale-110 transition" />
        <span>Grup Fiyat Optimizer</span>
        <span className="text-stone-400 text-xs">·</span>
        <span className="text-violet-200">displacement analysis + AI öneri</span>
        <span className="text-stone-500 text-[10px] ml-1">(IDeaS/Flyr core)</span>
      </button>

      {/* Quality Score factors breakdown */}
      <div className="bg-stone-900/40 border border-stone-800 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Brain className="w-4 h-4 text-amber-400" />
          <h3 className="text-xs font-black text-stone-200">Kalite Faktörleri</h3>
          <span className="text-[10px] text-stone-500">→ otomatik fiyat uplift</span>
        </div>
        <div className="space-y-2">
          {quality.factors.map(f => (
            <div key={f.name} className="flex items-center justify-between gap-3 text-[11px]" data-testid={`quality-factor-${f.name.replace(/\s/g, '-').toLowerCase()}`}>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-stone-300 font-bold">{f.name}</span>
                  <span className="text-stone-500">·</span>
                  <span className="text-stone-400">{f.reason}</span>
                </div>
              </div>
              <span className={`tabular-nums font-black text-xs ${
                f.uplift_pct > 0 ? "text-emerald-300" : f.uplift_pct < 0 ? "text-amber-300" : "text-stone-500"
              }`}>
                {f.uplift_pct > 0 ? "+" : ""}{f.uplift_pct}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {groupOpen && (
        <GroupPricingModal propertyId={propertyId} onClose={() => setGroupOpen(false)} />
      )}
    </div>
  );
}

function KpiCard({ icon: Icon, tone = "cyan", title, subtitle, big, unit, subtext, footer, testid, highlight }) {
  const toneClass = {
    emerald: "border-emerald-500/30 text-emerald-300",
    amber: "border-amber-500/30 text-amber-300",
    cyan: "border-cyan-500/30 text-cyan-300",
    fuchsia: "border-fuchsia-500/30 text-fuchsia-300",
  }[tone] || "border-stone-800 text-stone-300";

  return (
    <div className={`bg-stone-900/60 border rounded-xl p-4 transition ${highlight ? "ring-2 ring-emerald-400/50" : ""} ${toneClass.split(" ")[0]}`} data-testid={testid}>
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <Icon className={`w-4 h-4 ${toneClass.split(" ")[1]}`} />
          <span className="text-xs font-black text-stone-100">{title}</span>
        </div>
        {subtitle && <span className="text-[9px] uppercase tracking-widest text-stone-500 font-bold">{subtitle}</span>}
      </div>
      <p className="text-2xl font-black text-stone-50 mt-1 tabular-nums">
        {big}
        {unit && <span className="text-xs text-stone-500 font-normal ml-0.5">{unit}</span>}
      </p>
      {subtext && <p className="text-[11px] text-stone-400 mt-0.5">{subtext}</p>}
      {footer && <p className="text-[10px] text-stone-500 mt-1.5">{footer}</p>}
    </div>
  );
}
