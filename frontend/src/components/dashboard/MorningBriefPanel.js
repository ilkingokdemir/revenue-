/**
 * Morning Brief — 8 AM dashboard for the duty manager / revenue manager.
 * One screen: today's arrivals/departures/in-house, 7d pickup, STLY snapshot,
 * unanswered alerts, Pricing Autopilot toggle + last run summary.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Sun, Loader2, RefreshCw, Sparkles, Plane, Building2, Bed, MessageSquare, Star,
  ClipboardList, ArrowUp, ArrowDown, Play, ToggleLeft, ToggleRight,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;

export default function MorningBriefPanel({ propertyId, hotelName = "" }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [autopilot, setAutopilot] = useState(null);
  const [running, setRunning] = useState(false);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [{ data: brief }, { data: ap }] = await Promise.all([
        axios.get(`${API}/morning-brief/${propertyId}`),
        axios.get(`${API}/autopilot/pricing/${propertyId}`),
      ]);
      setData(brief);
      setAutopilot(ap);
    } catch (e) {
      toast.error("Failed to load brief");
    }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setData(null); setAutopilot(null); }, [propertyId]);

  const toggleEnabled = async (enabled) => {
    try {
      await axios.post(`${API}/autopilot/pricing/${propertyId}`,
        { ...(autopilot || {}), enabled });
      setAutopilot(p => ({ ...(p || {}), enabled }));
      toast.success(enabled ? "Autopilot enabled" : "Autopilot disabled");
    } catch { toast.error("Failed to toggle"); }
  };

  const updateConfig = async (patch) => {
    try {
      const next = { ...(autopilot || {}), ...patch };
      await axios.post(`${API}/autopilot/pricing/${propertyId}`, next);
      setAutopilot(next);
      toast.success("Saved");
    } catch { toast.error("Failed"); }
  };

  const runNow = async () => {
    if (!propertyId) return;
    setRunning(true);
    try {
      // Step 1 — kick autopilot stamp
      await axios.post(`${API}/autopilot/pricing/${propertyId}/run-now`);
      // Step 2 — fetch fresh AI v2 recommendations
      const { data: rec } = await axios.post(`${API}/dynamic-pricing/${propertyId}/ai-v2/recommend`,
        { days: autopilot?.days_window || 14 });
      // Step 3 — persist summary
      await axios.post(`${API}/autopilot/pricing/${propertyId}/save-run`,
        { recommendations: rec.recommendations || [], summary: rec.summary || "" });
      toast.success(`Autopilot run complete · ${rec.recommendations?.length || 0} suggestions`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Run failed");
    }
    setRunning(false);
  };

  if (!data && loading) return (
    <div className="p-12 text-center text-stone-400">
      <Loader2 className="w-5 h-5 animate-spin inline mr-2" />Loading morning brief…
    </div>
  );

  const today = data?.today || {};
  const stly = data?.stly_7d || {};
  const pickup = data?.pickup_7d || {};
  const alerts = data?.alerts || {};
  const ahead = (stly.delta || 0) >= 0;

  return (
    <div className="p-5 space-y-5" data-testid="morning-brief-panel">
      {/* Header */}
      <div className="bg-gradient-to-br from-orange-900/40 via-rose-900/30 to-amber-900/40 border border-orange-500/30 rounded-2xl p-5">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-amber-300">
              <Sun className="w-4 h-4" />Morning Brief
            </div>
            <h1 className="text-3xl font-black text-stone-100 mt-1">
              {new Date().toLocaleDateString("en", { weekday: "long", day: "numeric", month: "long" })}
            </h1>
            <p className="text-sm text-stone-300 mt-1">{hotelName ? `${hotelName} · ` : ""}Your 8 AM heads-up</p>
          </div>
          <button onClick={load} disabled={loading} data-testid="brief-refresh"
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-white text-xs font-bold">
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}Refresh
          </button>
        </div>
      </div>

      {/* Today */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="brief-today">
        <Stat icon={Plane}    label="Arrivals today"    value={today.arrivals}    color="text-emerald-300" />
        <Stat icon={Building2} label="Departures today" value={today.departures}  color="text-amber-300" />
        <Stat icon={Bed}      label="In-house"          value={today.in_house}    color="text-cyan-300" />
        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-4">
          <div className="text-[10px] uppercase tracking-widest text-stone-400 font-bold mb-1 flex items-center gap-1">
            <ClipboardList className="w-3 h-3" />Pickup last 7 days
          </div>
          <div className="text-2xl font-black text-violet-300 tabular-nums">{pickup.count || 0}</div>
          <div className="text-[10px] text-stone-400 mt-0.5">{cur(pickup.revenue)} revenue</div>
        </div>
      </div>

      {/* STLY snapshot */}
      <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-4 flex items-center justify-between" data-testid="brief-stly">
        <div>
          <div className="text-[10px] uppercase tracking-widest text-stone-400 font-bold mb-1">STLY · next 7 days</div>
          <div className="flex items-center gap-3">
            <span className="text-2xl font-black text-cyan-300 tabular-nums">{stly.ty_rooms || 0}</span>
            <span className="text-stone-400 text-sm">vs LY {stly.ly_rooms || 0}</span>
          </div>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-black ${ahead ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30" : "bg-rose-500/15 text-rose-300 border border-rose-500/30"}`}>
          {ahead ? <ArrowUp className="w-4 h-4" /> : <ArrowDown className="w-4 h-4" />}
          {ahead ? "AHEAD" : "BEHIND"} {Math.abs(stly.delta || 0)} oda · {ahead ? "+" : ""}{stly.delta_pct || 0}%
        </div>
      </div>

      {/* AI Night Shift */}
      {data?.ai_night_shift && (
        <div className="bg-stone-900/60 border border-violet-500/30 rounded-2xl p-4" data-testid="brief-ai-night-shift">
          <h3 className="text-sm font-bold text-stone-100 mb-3 flex items-center gap-2">
            <span className="text-violet-300">🤖</span>AI Gece Vardiyası · son 24 saat
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <NightStat label="Pickup sıçraması" value={data.ai_night_shift.intraday_spikes_24h}
              sub={`${data.ai_night_shift.intraday_prices_applied_24h} fiyat oto-uygulandı`} testid="ns-intraday" />
            <NightStat label="Kısıtlama önerisi" value={data.ai_night_shift.restriction_recs_pending}
              sub={`${data.ai_night_shift.restriction_recs_new_24h} yeni · onay bekliyor`} testid="ns-restrictions"
              highlight={data.ai_night_shift.restriction_recs_pending > 0} />
            <NightStat label="Gap kampanya taslağı" value={data.ai_night_shift.gap_campaign_drafts}
              sub={`${data.ai_night_shift.gap_campaigns_new_24h} yeni üretildi`} testid="ns-gap"
              highlight={data.ai_night_shift.gap_campaign_drafts > 0} />
            <NightStat label="Kontenjan release" value={data.ai_night_shift.allotment_rooms_released_24h}
              sub="oda genel satışa açıldı" testid="ns-allotment" />
          </div>
        </div>
      )}

      {/* Alerts */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3" data-testid="brief-alerts">
        <AlertCard icon={ClipboardList} label="Open logbook items"   count={alerts.open_logbook}        accent="emerald" />
        <AlertCard icon={MessageSquare} label="Unread inbox messages" count={alerts.unread_inbox}        accent="cyan" />
        <AlertCard icon={Star}          label="Unanswered reviews"    count={alerts.unanswered_reviews}  accent="amber" />
      </div>

      {/* Latest reviews */}
      {data?.new_reviews?.length > 0 && (
        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-4" data-testid="brief-reviews">
          <h3 className="text-sm font-bold text-stone-100 mb-3 flex items-center gap-2">
            <Star className="w-4 h-4 text-amber-400" />Latest unanswered reviews
          </h3>
          <div className="space-y-2">
            {data.new_reviews.slice(0, 5).map((r, i) => (
              <div key={i} className="bg-stone-800/40 rounded-lg p-3">
                <div className="flex items-center justify-between text-[11px] mb-1">
                  <span className="font-bold text-stone-200">{r.guest_name || "Guest"} · <span className="text-stone-400">{r.platform}</span></span>
                  <span className="text-amber-300 font-black">★ {r.rating}</span>
                </div>
                <p className="text-xs text-stone-400 line-clamp-2">{r.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AUTOPILOT */}
      <div className="bg-gradient-to-br from-violet-900/30 to-fuchsia-900/30 border border-violet-500/30 rounded-2xl p-5" data-testid="brief-autopilot">
        <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-violet-300" />
            <div>
              <h3 className="text-sm font-bold text-stone-100">Pricing Autopilot</h3>
              <p className="text-[11px] text-violet-200/80">Run AI Pricing v2 nightly · review or auto-apply</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => toggleEnabled(!autopilot?.enabled)} data-testid="autopilot-toggle"
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold ${autopilot?.enabled ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40" : "bg-stone-800 text-stone-400 border border-stone-700"}`}>
              {autopilot?.enabled ? <ToggleRight className="w-4 h-4" /> : <ToggleLeft className="w-4 h-4" />}
              {autopilot?.enabled ? "Enabled" : "Disabled"}
            </button>
            <button onClick={runNow} disabled={running || !propertyId} data-testid="autopilot-run-now"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-br from-violet-600 to-fuchsia-600 hover:from-violet-700 hover:to-fuchsia-700 text-white text-xs font-bold disabled:opacity-50">
              {running ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
              {running ? "Running…" : "Run now"}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
          <div className="bg-stone-900/50 rounded-xl p-3">
            <label className="block text-[10px] uppercase tracking-widest text-stone-400 font-bold mb-1">Days window</label>
            <select value={autopilot?.days_window || 14} onChange={e => updateConfig({ days_window: parseInt(e.target.value) })}
              className="w-full bg-stone-800 border border-stone-700 text-stone-100 text-xs rounded-lg px-2 py-1.5"
              data-testid="autopilot-days-window">
              {[7, 14, 21, 30].map(d => <option key={d} value={d} label={`${d} days`} />)}
            </select>
          </div>
          <div className="bg-stone-900/50 rounded-xl p-3">
            <label className="block text-[10px] uppercase tracking-widest text-stone-400 font-bold mb-1">Schedule</label>
            <select value={autopilot?.schedule || "daily_03"} onChange={e => updateConfig({ schedule: e.target.value })}
              className="w-full bg-stone-800 border border-stone-700 text-stone-100 text-xs rounded-lg px-2 py-1.5"
              data-testid="autopilot-schedule">
              <option value="daily_03">Daily 03:00 UTC</option>
              <option value="daily_06">Daily 06:00 UTC</option>
              <option value="hourly_6">Every 6 hours</option>
            </select>
          </div>
          <div className="bg-stone-900/50 rounded-xl p-3">
            <label className="flex items-center gap-2 cursor-pointer text-xs text-stone-200">
              <input type="checkbox" checked={!!autopilot?.auto_apply}
                onChange={e => updateConfig({ auto_apply: e.target.checked })}
                className="accent-violet-500" data-testid="autopilot-auto-apply" />
              <span>Auto-apply suggestions to rate calendar</span>
            </label>
            <p className="text-[10px] text-stone-400 mt-1">Off = review only</p>
          </div>
        </div>

        {autopilot?.last_run_at && (
          <div className="bg-stone-900/50 rounded-xl p-3" data-testid="autopilot-last-run">
            <div className="flex items-center justify-between mb-2">
              <div className="text-[10px] uppercase tracking-widest text-violet-300 font-bold">Last run</div>
              <div className="text-[10px] text-stone-400">{new Date(autopilot.last_run_at).toLocaleString()}</div>
            </div>
            {autopilot.last_summary && <p className="text-xs text-stone-300 mb-2">{autopilot.last_summary}</p>}
            {(autopilot.last_recommendations || []).length > 0 && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-1.5">
                {autopilot.last_recommendations.slice(0, 8).map((r, i) => (
                  <div key={i} className="bg-stone-800/60 rounded px-2 py-1.5 text-[10px]">
                    <div className="font-mono text-stone-300">{new Date(r.date).toLocaleDateString("en", { day: "2-digit", month: "short" })}</div>
                    <div className="font-black text-emerald-300 tabular-nums">{cur(r.suggested_rate)} <span className={`text-[9px] ${r.delta_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>{r.delta_pct >= 0 ? "+" : ""}{r.delta_pct}%</span></div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function NightStat({ label, value, sub, testid, highlight }) {
  return (
    <div className={`rounded-xl p-3 border ${highlight ? "bg-violet-500/10 border-violet-500/40" : "bg-stone-800/40 border-stone-800"}`} data-testid={testid}>
      <div className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">{label}</div>
      <div className={`text-2xl font-black tabular-nums ${highlight ? "text-violet-300" : "text-stone-200"}`}>{value ?? 0}</div>
      <div className="text-[10px] text-stone-400 mt-0.5">{sub}</div>
    </div>
  );
}

function Stat({ icon: Icon, label, value, color }) {
  return (
    <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-4">
      <div className="text-[10px] uppercase tracking-widest text-stone-400 font-bold mb-1 flex items-center gap-1">
        <Icon className="w-3 h-3" />{label}
      </div>
      <div className={`text-3xl font-black tabular-nums ${color}`}>{value ?? "—"}</div>
    </div>
  );
}

function AlertCard({ icon: Icon, label, count, accent }) {
  const colours = {
    emerald: "border-emerald-500/30 text-emerald-300 bg-emerald-500/10",
    cyan:    "border-cyan-500/30 text-cyan-300 bg-cyan-500/10",
    amber:   "border-amber-500/30 text-amber-300 bg-amber-500/10",
  };
  const has = (count || 0) > 0;
  return (
    <div className={`rounded-2xl p-4 border ${has ? colours[accent] : "border-stone-800 bg-stone-900/40 text-stone-400"}`}>
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-widest font-bold mb-1 opacity-80">{label}</div>
          <div className={`text-2xl font-black tabular-nums ${has ? "" : "text-stone-400"}`}>{count || 0}</div>
        </div>
        <Icon className={`w-6 h-6 ${has ? "" : "opacity-30"}`} />
      </div>
    </div>
  );
}
