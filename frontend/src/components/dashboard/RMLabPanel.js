/**
 * RM Lab — two competitor-grade meta-RM features in one panel:
 *  1. Forecast Accuracy Tracker — compares past forecasts to actuals,
 *     shows MAE / Trust Score / bias by lead-time bucket.
 *  2. Marketing Automation Queue — birthday / abandoned / win-back triggers
 *     with sendable drafts that staff can mark as sent.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Loader2, Target, Mail, Cake, ShoppingCart, Heart, Send, X, Play, RefreshCw,
  TrendingUp, TrendingDown, Minus, Activity,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;

const TRIGGER_META = {
  birthday:  { icon: Cake,         label: "Birthday",          color: "text-rose-300 bg-rose-500/15 border-rose-500/30" },
  abandoned: { icon: ShoppingCart, label: "Abandoned booking", color: "text-amber-300 bg-amber-500/15 border-amber-500/30" },
  win_back:  { icon: Heart,        label: "Win-back",          color: "text-violet-300 bg-violet-500/15 border-violet-500/30" },
};

export default function RMLabPanel({ propertyId, hotelName = "" }) {
  const [tab, setTab] = useState("accuracy");
  return (
    <div className="p-5 space-y-5" data-testid="rm-lab-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-stone-100 flex items-center gap-2">
            <Activity className="w-5 h-5 text-cyan-400" />RM Lab
            {hotelName && <><span className="text-stone-500 mx-1">·</span><span className="text-violet-400">{hotelName}</span></>}
          </h2>
          <p className="text-xs text-stone-400">Forecast accuracy tracking · marketing automation triggers</p>
        </div>
        <div className="flex items-center gap-1 bg-stone-900 border border-stone-800 rounded-xl p-0.5">
          <TabBtn active={tab === "accuracy"}  onClick={() => setTab("accuracy")}  icon={Target} label="Accuracy" testId="rm-lab-tab-accuracy" />
          <TabBtn active={tab === "marketing"} onClick={() => setTab("marketing")} icon={Mail}   label="Marketing" testId="rm-lab-tab-marketing" />
        </div>
      </div>
      {tab === "accuracy" ? <AccuracyTab propertyId={propertyId} /> : <MarketingTab propertyId={propertyId} />}
    </div>
  );
}

function TabBtn({ active, onClick, icon: Icon, label, testId }) {
  return (
    <button onClick={onClick} data-testid={testId}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold ${active ? "bg-cyan-600 text-white" : "text-stone-400 hover:text-white"}`}>
      <Icon className="w-3.5 h-3.5" />{label}
    </button>
  );
}

// ====== ACCURACY ======
function AccuracyTab({ propertyId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [taking, setTaking] = useState(false);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/forecast/accuracy/${propertyId}?days=60`);
      setData(data);
    } catch { toast.error("Failed to load"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const snapshot = async () => {
    setTaking(true);
    try {
      const { data } = await axios.post(`${API}/forecast/snapshot/${propertyId}?days=30`);
      toast.success(`Snapshot taken · ${data.rows_saved} rows`);
      load();
    } catch { toast.error("Snapshot failed"); }
    setTaking(false);
  };

  if (loading && !data) return <div className="p-12 text-center text-stone-400"><Loader2 className="w-5 h-5 animate-spin inline mr-2" />Scoring forecasts…</div>;

  const m = data?.metrics || {};
  const trust = m.trust_score ?? null;
  const trustColor = trust == null ? "text-stone-400" : trust >= 80 ? "text-emerald-300" : trust >= 60 ? "text-amber-300" : "text-rose-300";
  const biasMeta = {
    too_aggressive: { color: "text-rose-300 bg-rose-500/15 border-rose-500/30",     label: "Too aggressive (rates set high vs actuals)", icon: TrendingUp },
    balanced:       { color: "text-emerald-300 bg-emerald-500/15 border-emerald-500/30", label: "Balanced",                                  icon: Minus },
    too_cautious:   { color: "text-amber-300 bg-amber-500/15 border-amber-500/30",  label: "Too cautious (rates set low vs actuals)",     icon: TrendingDown },
  }[m.bias] || null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-stone-400">{data?.samples ?? 0} sample(s) scored from past 60 days</p>
        <div className="flex gap-2">
          <button onClick={load} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-white text-xs font-bold" data-testid="rm-lab-refresh">
            <RefreshCw className="w-3.5 h-3.5" />Refresh
          </button>
          <button onClick={snapshot} disabled={taking} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-700 text-white text-xs font-bold disabled:opacity-50" data-testid="rm-lab-snapshot">
            {taking ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Target className="w-3.5 h-3.5" />}Take Snapshot
          </button>
        </div>
      </div>

      {/* Metrics row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3" data-testid="rm-lab-metrics">
        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-4 text-center">
          <div className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-1">Trust score</div>
          <div className={`text-4xl font-black tabular-nums ${trustColor}`}>{trust == null ? "—" : trust}</div>
          <div className="text-[10px] text-stone-500 mt-1">/ 100</div>
        </div>
        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-4">
          <div className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-1">Mean abs occ error</div>
          <div className="text-2xl font-black text-cyan-300 tabular-nums">{m.mae_occ ?? "—"}<span className="text-sm text-cyan-400 ml-1">%</span></div>
          <div className="text-[10px] text-stone-500 mt-1">lower = better</div>
        </div>
        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-4">
          <div className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-1">Avg rate error</div>
          <div className="text-2xl font-black text-violet-300 tabular-nums">
            {m.avg_rate_error_pct == null ? "—" : `${m.avg_rate_error_pct > 0 ? "+" : ""}${m.avg_rate_error_pct}%`}
          </div>
          <div className="text-[10px] text-stone-500 mt-1">forecast vs actual</div>
        </div>
        <div className={`rounded-2xl p-4 border ${biasMeta?.color || "border-stone-800 bg-stone-900/60"}`}>
          <div className="text-[10px] uppercase tracking-widest font-bold mb-1 opacity-80">Bias</div>
          <div className="flex items-center gap-2 mt-1">
            {biasMeta?.icon && <biasMeta.icon className="w-5 h-5" />}
            <span className="text-sm font-bold">{biasMeta?.label || "No data"}</span>
          </div>
        </div>
      </div>

      {/* By-lead-time table */}
      {data?.by_lead_days?.length > 0 && (
        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-4" data-testid="rm-lab-by-lead">
          <h3 className="text-sm font-bold text-stone-100 mb-3">Accuracy by lead time</h3>
          <table className="w-full text-xs">
            <thead><tr className="text-stone-400 border-b border-stone-800">
              <th className="text-left py-2 px-2">Lead</th>
              <th className="text-right py-2 px-2">Samples</th>
              <th className="text-right py-2 px-2">Occ MAE</th>
              <th className="text-right py-2 px-2">Avg rate error</th>
            </tr></thead>
            <tbody>
              {data.by_lead_days.map(b => (
                <tr key={b.bucket} className="border-b border-stone-800/50">
                  <td className="py-2 px-2 font-mono text-stone-300">{b.bucket}</td>
                  <td className="py-2 px-2 text-right tabular-nums text-stone-200">{b.n}</td>
                  <td className="py-2 px-2 text-right tabular-nums text-cyan-300">{b.mae_occ == null ? "—" : `${b.mae_occ}%`}</td>
                  <td className="py-2 px-2 text-right tabular-nums text-violet-300">{b.avg_rate_err_pct == null ? "—" : `${b.avg_rate_err_pct > 0 ? "+" : ""}${b.avg_rate_err_pct}%`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(!data || data.samples === 0) && (
        <div className="text-center py-12 text-stone-500" data-testid="rm-lab-empty">
          <Target className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="text-sm">No scored snapshots yet. Click <strong>Take Snapshot</strong> daily — accuracy grows as dates pass.</p>
        </div>
      )}
    </div>
  );
}

// ====== MARKETING ======
function MarketingTab({ propertyId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [filter, setFilter] = useState("");

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/marketing/automation/queue/${propertyId}${filter ? `?status=${filter}` : ""}`);
      setData(data);
    } catch { toast.error("Failed to load"); }
    setLoading(false);
  }, [propertyId, filter]);
  useEffect(() => { load(); }, [load]);

  const run = async () => {
    setRunning(true);
    try {
      const { data } = await axios.post(`${API}/marketing/automation/run/${propertyId}`);
      toast.success(`Queued ${data.total} new email(s)`);
      load();
    } catch { toast.error("Run failed"); }
    setRunning(false);
  };

  const markSent = async (id) => {
    try { await axios.post(`${API}/marketing/automation/${id}/sent`); load(); }
    catch { toast.error("Failed"); }
  };
  const skip = async (id) => {
    try { await axios.post(`${API}/marketing/automation/${id}/skip`); load(); }
    catch { toast.error("Failed"); }
  };

  if (loading && !data) return <div className="p-12 text-center text-stone-400"><Loader2 className="w-5 h-5 animate-spin inline mr-2" />Loading…</div>;
  const stats = data?.by_trigger || {};
  const status = data?.by_status || {};

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          {Object.entries(TRIGGER_META).map(([k, m]) => (
            <div key={k} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-bold ${m.color}`} data-testid={`marketing-stat-${k}`}>
              <m.icon className="w-3.5 h-3.5" />{m.label}: <span className="tabular-nums">{stats[k] || 0}</span>
            </div>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <select value={filter} onChange={e => setFilter(e.target.value)} className="bg-stone-900 border border-stone-800 text-stone-100 text-xs rounded-lg px-2 py-1.5" data-testid="marketing-filter">
            <option value="">All ({data?.total || 0})</option>
            <option value="pending">Pending ({status.pending || 0})</option>
            <option value="sent">Sent ({status.sent || 0})</option>
            <option value="skipped">Skipped ({status.skipped || 0})</option>
          </select>
          <button onClick={run} disabled={running} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-700 text-white text-xs font-bold disabled:opacity-50" data-testid="marketing-run">
            {running ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
            Run automation
          </button>
        </div>
      </div>

      {/* Queue */}
      <div className="space-y-2" data-testid="marketing-queue">
        {(data?.queue || []).map(item => {
          const m = TRIGGER_META[item.trigger] || TRIGGER_META.birthday;
          return (
            <div key={item.id} className="bg-stone-900/60 border border-stone-800 rounded-2xl p-4" data-testid={`marketing-item-${item.id}`}>
              <div className="flex items-start gap-3">
                <div className={`w-9 h-9 rounded-lg ${m.color} flex items-center justify-center flex-shrink-0`}>
                  <m.icon className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline justify-between gap-2 mb-1">
                    <span className="text-xs font-bold text-stone-200 truncate">{item.guest_name || item.guest_email || "—"}</span>
                    <span className="text-[10px] text-stone-500 flex-shrink-0">{new Date(item.created_at).toLocaleString()}</span>
                  </div>
                  <p className="text-sm font-bold text-stone-100 mb-1">{item.subject}</p>
                  <p className="text-xs text-stone-400 line-clamp-2">{item.body}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border ${m.color}`}>{m.label}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${item.status === "sent" ? "bg-emerald-500/20 text-emerald-300" : item.status === "skipped" ? "bg-stone-700 text-stone-400" : "bg-amber-500/20 text-amber-300"}`}>
                      {item.status}
                    </span>
                    <span className="text-[10px] text-stone-500 truncate">{item.guest_email}</span>
                    {item.status === "pending" && (
                      <div className="ml-auto flex gap-1.5">
                        <button onClick={() => markSent(item.id)} className="flex items-center gap-1 text-[10px] px-2 py-1 rounded bg-emerald-600 hover:bg-emerald-700 text-white font-bold" data-testid={`marketing-sent-${item.id}`}>
                          <Send className="w-3 h-3" />Mark sent
                        </button>
                        <button onClick={() => skip(item.id)} className="flex items-center gap-1 text-[10px] px-2 py-1 rounded bg-stone-700 hover:bg-stone-600 text-white font-bold" data-testid={`marketing-skip-${item.id}`}>
                          <X className="w-3 h-3" />Skip
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
        {(!data?.queue || data.queue.length === 0) && (
          <div className="text-center py-12 text-stone-500" data-testid="marketing-empty">
            <Mail className="w-10 h-10 mx-auto mb-3 opacity-40" />
            <p className="text-sm">No queued emails. Click <strong>Run automation</strong> to scan triggers.</p>
          </div>
        )}
      </div>
    </div>
  );
}
