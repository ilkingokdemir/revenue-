/**
 * Channel Manager Hub (Iter 163) — consolidates 9 channel panels behind a
 * tab-based navigation surface:
 *   1. Dashboard (Channel Health + Setup Checklist + KPI tiles)
 *   2. Channels (Channel Configs + connect flow + certify)
 *   3. Mappings (auto-generate + auto-fill + per-channel tabs)
 *   4. Rate Structure (variants with auto-generate-from-mappings)
 *   5. Publish Jobs (ARI distribution queue)
 *   6. Audit Logs (distribution event history)
 *   7. Benchmark Cockpit (STR-style occupancy/ADR/RevPAR index)
 *   8. Profiles (per-channel payload discovery)
 *   9. Overrides (per-channel price adjustments)
 *
 * Backend: /api/channel-hub, /api/channel-configs, /api/payload-profiles,
 * /api/publish-jobs, /api/price-overrides, /api/channel-audit,
 * /api/benchmark, /api/rate-variants, /api/channel-mappings.
 */
import { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import {
  LayoutDashboard, Plug, Link2, UploadCloud, ScrollText,
  FileCode2, Percent, CheckCircle2, CircleDashed, Lock,
  Plus, RefreshCw, Play, Trash2, TrendingUp,
  AlertTriangle, Activity, Sparkles, Globe2, ChevronRight,
  Layers, Ban, Calendar as CalIcon,
} from "lucide-react";
import { Zap } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PANELS = [
  { key: "dashboard",       label: "Dashboard",       icon: LayoutDashboard },
  { key: "channels",        label: "Channels",        icon: Plug },
  { key: "mappings",        label: "Mappings",        icon: Link2 },
  { key: "allocations",     label: "Allocations",     icon: Layers },
  { key: "stop-sell",       label: "Stop-Sell",       icon: Ban },
  { key: "publish-jobs",    label: "Publish Jobs",    icon: UploadCloud },
  { key: "audit-logs",      label: "Audit Logs",      icon: ScrollText },
  { key: "unassigned",      label: "Unassigned OTA",  icon: AlertTriangle },
  { key: "profiles",        label: "Profiles",        icon: FileCode2 },
  { key: "overrides",       label: "Overrides",       icon: Percent },
];

/* ═══════════ DASHBOARD ═══════════ */
const HubDashboard = ({ pid, goTo }) => {
  const [dash, setDash] = useState(null);
  const [checklist, setChecklist] = useState(null);

  const load = useCallback(async () => {
    try {
      const [d, c] = await Promise.all([
        axios.get(`${API}/channel-hub/${pid}/dashboard`),
        axios.get(`${API}/channel-hub/${pid}/checklist`),
      ]);
      setDash(d.data);
      setChecklist(c.data);
    } catch { /* ignore */ }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const seedDemo = async () => {
    try {
      await axios.post(`${API}/channel-hub/${pid}/seed-demo`);
      toast.success("Demo data seeded");
      load();
    } catch { toast.error("Seed failed"); }
  };

  if (!dash || !checklist) return <div className="p-10 text-center text-stone-400">Loading…</div>;

  const pct = checklist.percentage;
  const ring = `conic-gradient(#10b981 ${pct * 3.6}deg, rgba(255,255,255,0.08) 0)`;

  return (
    <div className="space-y-6" data-testid="chmgr-dashboard">
      {/* Channel Health hero */}
      <div className="bg-slate-950 text-white rounded-2xl p-8 relative overflow-hidden">
        <div className="absolute -right-20 -top-20 w-60 h-60 rounded-full bg-emerald-500/10 blur-3xl" />
        <div className="relative flex flex-col md:flex-row md:items-center gap-6">
          <div className="flex-shrink-0">
            <div className="relative w-28 h-28">
              <div className="absolute inset-0 rounded-full" style={{ background: ring }} />
              <div className="absolute inset-2 rounded-full bg-slate-950 flex items-center justify-center">
                <div className="text-2xl font-bold">{pct}%</div>
              </div>
            </div>
          </div>
          <div className="flex-1">
            <h2 className="text-2xl font-bold mb-1">Channel Health</h2>
            <p className={`text-sm font-semibold mb-2 ${pct < 50 ? "text-rose-400" : pct < 90 ? "text-amber-400" : "text-emerald-400"}`}>
              {pct < 50 ? "Setup Required" : pct < 90 ? "Almost ready" : "Operational"}
            </p>
            <p className="text-sm text-slate-400">
              {pct < 100
                ? `${checklist.total - checklist.completed_count} step${checklist.total - checklist.completed_count === 1 ? "" : "s"} remaining before you can go live.`
                : "All setup steps complete — you're good to go."}
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <button
              data-testid="chmgr-continue-setup"
              onClick={() => goTo("channels")}
              className="px-6 py-3 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white font-semibold text-sm transition flex items-center gap-2"
            >
              Continue Setup <ChevronRight className="w-4 h-4" />
            </button>
            <button
              data-testid="chmgr-seed-demo"
              onClick={seedDemo}
              className="px-6 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-white text-xs border border-white/10 transition"
            >
              <Sparkles className="w-3 h-3 inline mr-1" /> Seed demo
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-6 relative">
          {[
            { t: "Faster go-live", d: `You are ${checklist.total - checklist.completed_count} steps away from first publish.` },
            { t: "Fewer errors", d: "Idempotent publish + audit trail reduce parity and duplicate issues." },
            { t: "Operational control", d: "Publish queue and resolver snapshots keep price changes explainable." },
            { t: "Mapping confidence", d: `Mapping coverage is ${dash.mapping_coverage_pct}% (target 95%).` },
          ].map((b, i) => (
            <div key={i} className="bg-white/5 border border-white/10 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-1"><CheckCircle2 className="w-4 h-4 text-emerald-400" /><span className="text-sm font-semibold">{b.t}</span></div>
              <p className="text-xs text-slate-400">{b.d}</p>
            </div>
          ))}
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <KpiCard label="Active Channels" value={dash.active_channels} chip="Live" chipColor="bg-blue-50 text-blue-600" icon={Globe2} />
        <KpiCard label="Sync Health" value={`${dash.sync_health_pct}%`} chip={dash.sync_health_label} chipColor={dash.sync_health_label === "Good" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"} icon={Activity} />
        <KpiCard label="Channel Bookings" value={dash.channel_bookings_7d} chip="7 Days" chipColor="bg-violet-50 text-violet-700" icon={TrendingUp} />
      </div>

      {/* Checklist */}
      <div className="bg-white border border-stone-200 rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold">Channel Setup Checklist</h3>
          <Badge variant="outline">{checklist.completed_count}/{checklist.total} completed</Badge>
        </div>
        <div className="space-y-2" data-testid="chmgr-checklist">
          {checklist.steps.map((s, i) => {
            const unlocked = i === 0 || checklist.steps[i - 1].completed;
            return (
              <div key={s.id} className={`flex items-center gap-4 p-4 rounded-xl border ${s.completed ? "border-emerald-200 bg-emerald-50/40" : unlocked ? "border-stone-200 bg-white" : "border-stone-100 bg-stone-50"}`}>
                <div className="flex-shrink-0">
                  {s.completed
                    ? <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                    : unlocked
                      ? <CircleDashed className="w-5 h-5 text-blue-500" />
                      : <Lock className="w-4 h-4 text-stone-300" />}
                </div>
                <div className="flex-1">
                  <div className={`font-semibold text-sm ${unlocked ? "" : "text-stone-400"}`}>{s.label}</div>
                  <div className={`text-xs ${unlocked ? "text-stone-500" : "text-stone-400"}`}>{s.description}</div>
                </div>
                {unlocked && !s.completed && (
                  <button
                    data-testid={`chmgr-step-go-${s.id}`}
                    onClick={() => {
                      const map = { create_config: "channels", enter_credentials: "channels", run_certification: "channels", create_payload: "profiles", complete_mappings: "mappings", verify_rate_structure: "mappings", dry_run: "publish-jobs", enable_autopublish: "channels" };
                      goTo(map[s.id] || "channels");
                    }}
                    className="px-4 py-1.5 text-xs rounded-lg border border-emerald-300 text-emerald-700 font-semibold hover:bg-emerald-50 transition"
                  >Go</button>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Recent activity */}
      <div className="bg-white border border-stone-200 rounded-2xl p-6">
        <h3 className="text-lg font-bold mb-3">Recent Activity</h3>
        {dash.recent_activity?.length === 0 && <p className="text-center text-sm text-stone-400 py-8">No recent activity</p>}
        {dash.recent_activity?.slice(0, 8).map((a) => (
          <div key={a.id} className="flex items-center gap-3 py-2 border-b border-stone-100 last:border-0">
            <div className="w-2 h-2 rounded-full bg-emerald-500" />
            <div className="flex-1 text-sm"><span className="font-mono text-xs text-stone-400">{a.event}</span> by {a.user_email}</div>
            <div className="text-xs text-stone-400">{new Date(a.ts).toLocaleString()}</div>
          </div>
        ))}
      </div>

      {/* Quick-nav cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { k: "channels", l: "Channels", d: "Manage connections", i: Globe2 },
          { k: "mappings", l: "Mappings", d: "Room & Rate map", i: Link2 },
          { k: "allocations", l: "Allocations", d: "Pooled inventory", i: Layers },
          { k: "stop-sell", l: "Stop-Sell", d: "Pause channels", i: Ban },
          { k: "publish-jobs", l: "Publish Jobs", d: "Distribution status", i: UploadCloud },
          { k: "audit-logs", l: "Audit Logs", d: "History & Errors", i: ScrollText },
          { k: "overrides", l: "Overrides", d: "Price adjustments", i: Percent },
          { k: "profiles", l: "Profiles", d: "Payload fields", i: FileCode2 },
        ].map(c => (
          <button key={c.k} onClick={() => goTo(c.k)} className="p-5 rounded-xl border border-stone-200 hover:border-emerald-300 hover:shadow-md text-left transition" data-testid={`chmgr-nav-${c.k}`}>
            <c.i className="w-5 h-5 text-stone-500 mb-3" />
            <div className="font-semibold text-sm">{c.l}</div>
            <div className="text-xs text-stone-400 mt-1">{c.d}</div>
          </button>
        ))}
      </div>
    </div>
  );
};

const KpiCard = ({ label, value, chip, chipColor, icon: Icon }) => (
  <div className="bg-white border border-stone-200 rounded-2xl p-6">
    <div className="flex items-center justify-between mb-3">
      <div className="text-sm font-semibold text-stone-600">{label}</div>
      <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${chipColor}`}>{chip}</span>
    </div>
    <div className="text-4xl font-bold mb-1">{value}</div>
    <div className="flex justify-center mt-2"><Icon className="w-4 h-4 text-stone-300" /></div>
  </div>
);

/* ═══════════ CHANNELS ═══════════ */
const ChannelsPanel = ({ pid }) => {
  const [configs, setConfigs] = useState([]);
  const [form, setForm] = useState({ channel_id: "booking_com", name: "", property_code: "" });
  const [showForm, setShowForm] = useState(false);

  const load = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/channel-configs/${pid}`); setConfigs(data.configs || []); }
    catch { /* */ }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    if (!form.name) return toast.error("Name required");
    try {
      await axios.post(`${API}/channel-configs/${pid}`, form);
      toast.success("Channel config created");
      setShowForm(false);
      setForm({ channel_id: "booking_com", name: "", property_code: "" });
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const updateConfig = async (id, patch) => {
    try { await axios.put(`${API}/channel-configs/${id}`, patch); toast.success("Updated"); load(); }
    catch { toast.error("Failed"); }
  };

  const certify = async (id) => {
    try {
      const { data } = await axios.post(`${API}/channel-configs/${id}/certify`);
      toast.success(`${data.message}`); load();
    } catch { toast.error("Certification failed"); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this channel config?")) return;
    await axios.delete(`${API}/channel-configs/${id}`);
    toast.success("Deleted"); load();
  };

  return (
    <div className="space-y-4" data-testid="chmgr-channels">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">Channel Configs</h2>
          <p className="text-sm text-stone-500">Manage your OTA connections and sync settings.</p>
        </div>
        <button onClick={() => setShowForm(true)} className="px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-semibold hover:bg-blue-700 flex items-center gap-2" data-testid="chmgr-new-config">
          <Plus className="w-4 h-4" /> Connect New Channel
        </button>
      </div>

      {showForm && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-5 space-y-3">
          <h3 className="font-semibold">New Channel</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <select value={form.channel_id} onChange={e => setForm(f => ({ ...f, channel_id: e.target.value }))} className="px-3 py-2 border rounded-lg text-sm" data-testid="chmgr-form-channel">
              <option value="booking_com">Booking.com</option>
              <option value="expedia">Expedia</option>
              <option value="airbnb">Airbnb</option>
              <option value="agoda">Agoda</option>
              <option value="trip_com">Trip.com</option>
              <option value="agoda">Agoda</option>
              <option value="hotels_com">Hotels.com</option>
              <option value="trip_com">Trip.com</option>
            </select>
            <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Display name" className="px-3 py-2 border rounded-lg text-sm" data-testid="chmgr-form-name" />
            <input value={form.property_code} onChange={e => setForm(f => ({ ...f, property_code: e.target.value }))} placeholder="Property code" className="px-3 py-2 border rounded-lg text-sm" data-testid="chmgr-form-pcode" />
          </div>
          <div className="flex gap-2">
            <button onClick={create} className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-semibold" data-testid="chmgr-form-save">Create</button>
            <button onClick={() => setShowForm(false)} className="px-4 py-2 bg-white border rounded-lg text-sm">Cancel</button>
          </div>
        </div>
      )}

      {configs.length === 0 && !showForm && (
        <div className="bg-stone-50 border-2 border-dashed border-stone-200 rounded-2xl p-16 text-center">
          <Zap className="w-12 h-12 text-blue-400 mx-auto mb-4" />
          <h3 className="text-lg font-bold">No channels connected</h3>
          <p className="text-sm text-stone-500 mt-1">Start by connecting your first OTA channel to synchronize bookings and rates.</p>
          <button onClick={() => setShowForm(true)} className="mt-4 px-6 py-2 bg-blue-600 text-white rounded-xl text-sm font-semibold" data-testid="chmgr-connect-channel">Connect Channel</button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {configs.map(c => (
          <div key={c.id} className="bg-white border border-stone-200 rounded-xl p-5 space-y-3" data-testid={`chmgr-config-${c.channel_id}`}>
            <div className="flex items-start justify-between">
              <div>
                <div className="font-bold">{c.name}</div>
                <div className="text-xs text-stone-400 font-mono">{c.channel_id} · {c.connector}</div>
              </div>
              <Badge className={c.status === "live" ? "bg-emerald-100 text-emerald-700" : c.status === "certified" ? "bg-blue-100 text-blue-700" : "bg-stone-100 text-stone-600"}>{c.status}</Badge>
            </div>
            <div className="text-xs text-stone-500 space-y-1">
              <div>Property Code: <span className="font-mono">{c.property_code || "—"}</span></div>
              <div className="flex gap-4">
                <span className="flex items-center gap-1">{c.credentials_set ? <CheckCircle2 className="w-3 h-3 text-emerald-600" /> : <CircleDashed className="w-3 h-3 text-stone-400" />} Credentials</span>
                <span className="flex items-center gap-1">{c.certified ? <CheckCircle2 className="w-3 h-3 text-emerald-600" /> : <CircleDashed className="w-3 h-3 text-stone-400" />} Certified</span>
                <span className="flex items-center gap-1">{c.autopublish ? <CheckCircle2 className="w-3 h-3 text-emerald-600" /> : <CircleDashed className="w-3 h-3 text-stone-400" />} Autopublish</span>
              </div>
            </div>
            <div className="flex gap-2 pt-2 border-t border-stone-100">
              {!c.credentials_set && <button onClick={() => updateConfig(c.id, { credentials_set: true })} className="text-xs px-3 py-1 rounded border border-blue-300 text-blue-700 font-semibold" data-testid={`chmgr-creds-${c.id}`}>Set Credentials</button>}
              {c.credentials_set && !c.certified && <button onClick={() => certify(c.id)} className="text-xs px-3 py-1 rounded border border-emerald-300 text-emerald-700 font-semibold" data-testid={`chmgr-certify-${c.id}`}>Run Certification</button>}
              {c.certified && <button onClick={() => updateConfig(c.id, { autopublish: !c.autopublish })} className="text-xs px-3 py-1 rounded border border-violet-300 text-violet-700 font-semibold" data-testid={`chmgr-autopub-${c.id}`}>{c.autopublish ? "Disable Autopublish" : "Enable Autopublish"}</button>}
              <button onClick={() => remove(c.id)} className="text-xs px-2 py-1 rounded border border-rose-200 text-rose-600 ml-auto" data-testid={`chmgr-del-${c.id}`}><Trash2 className="w-3 h-3" /></button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

/* ═══════════ MAPPINGS ═══════════ */
const MappingsPanel = ({ pid }) => {
  const [data, setData] = useState(null);
  const [selChan, setSelChan] = useState("");

  const load = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/channel-mappings/${pid}`); setData(data); if (!selChan && data.channels?.[0]) setSelChan(data.channels[0].channel_id); }
    catch { /* */ }
  }, [pid, selChan]);
  useEffect(() => { load(); }, [load]);

  const upsert = async (row, ext) => {
    await axios.put(`${API}/channel-mappings/${pid}/upsert`, {
      kind: "room", internal_id: row.id, channel_id: selChan,
      external_id: ext, external_label: row.name,
    });
    load();
  };

  const autoFill = async () => {
    if (!data) return;
    const entries = (data.room_types || []).map(r => ({
      internal_id: r.id,
      external_id: r.name.toUpperCase().replace(/[^A-Z0-9]+/g, "_"),
      external_label: r.name,
    }));
    await axios.post(`${API}/channel-mappings/${pid}/bulk-set-channel`, {
      channel_id: selChan, kind: "room", entries,
    });
    toast.success(`Auto-filled ${entries.length} rooms`);
    load();
  };

  if (!data) return <div className="p-8 text-center text-stone-400">Loading…</div>;

  const channels = data.channels || [];
  const rooms = data.room_types || [];
  const getExt = (rid) => data.index?.room?.[rid]?.[selChan]?.external_id || "";

  return (
    <div className="space-y-4" data-testid="chmgr-mappings">
      <div>
        <h2 className="text-xl font-bold">Channel Mapping</h2>
        <p className="text-sm text-stone-500">Layer 1: Technical mapping. Local room + rate plan → OTA room/rate code (required). Go to Rate Structure for occupancy/meal/cancel variants.</p>
      </div>

      {/* Channel tabs */}
      <div className="flex gap-2 border-b border-stone-200 overflow-x-auto">
        {channels.map(ch => (
          <button key={ch.channel_id} onClick={() => setSelChan(ch.channel_id)}
            className={`px-4 py-2 text-sm font-semibold whitespace-nowrap ${selChan === ch.channel_id ? "border-b-2 border-blue-600 text-blue-600" : "text-stone-500"}`}
            data-testid={`chmgr-map-tab-${ch.channel_id}`}>
            {ch.name}
          </button>
        ))}
        {channels.length === 0 && <div className="p-4 text-sm text-stone-400">No channels yet — add one in the Channels tab</div>}
      </div>

      {selChan && (
        <>
          <div className="flex items-center gap-3 flex-wrap">
            <button onClick={autoFill} className="px-4 py-2 border border-stone-300 rounded-xl text-sm font-semibold flex items-center gap-2" data-testid="chmgr-autofill-codes">
              <Sparkles className="w-4 h-4 text-amber-500" /> Auto-fill All Codes
            </button>
            <span className="text-xs text-stone-400">{rooms.length} room types · {channels.find(c => c.channel_id === selChan)?.name}</span>
          </div>

          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            <div className="grid grid-cols-[1fr,1fr,auto] gap-4 px-4 py-3 bg-stone-50 text-xs font-semibold text-stone-500 uppercase tracking-wider">
              <div>Local Room</div><div>OTA Room Code</div><div>Status</div>
            </div>
            {rooms.map(r => {
              const ext = getExt(r.id);
              const suggested = r.name.toUpperCase().replace(/[^A-Z0-9]+/g, "_");
              return (
                <div key={r.id} className="grid grid-cols-[1fr,1fr,auto] gap-4 px-4 py-3 border-t border-stone-100 items-center">
                  <div>
                    <div className="font-semibold text-sm">{r.name}</div>
                    <div className="text-xs text-stone-400">Max: {r.max_guests || 2} guests</div>
                  </div>
                  <div>
                    <input defaultValue={ext} onBlur={e => e.target.value !== ext && upsert(r, e.target.value)}
                      placeholder={suggested} className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm font-mono"
                      data-testid={`chmgr-map-input-${r.id}`} />
                    {!ext && <div className="text-xs text-stone-400 mt-1">Suggested: {suggested}</div>}
                  </div>
                  <Badge className={ext ? "bg-emerald-100 text-emerald-700" : "bg-stone-100 text-stone-500"}>{ext ? "Mapped" : "—"}</Badge>
                </div>
              );
            })}
            {rooms.length === 0 && <div className="p-8 text-center text-sm text-stone-400">No room types found</div>}
          </div>
        </>
      )}
    </div>
  );
};

/* ═══════════ PUBLISH JOBS ═══════════ */
const PublishJobsPanel = ({ pid }) => {
  const [jobs, setJobs] = useState([]);
  const [channels, setChannels] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ channel_id: "booking_com", dry_run: true, items_total: 30 });

  const load = useCallback(async () => {
    try {
      const [j, c] = await Promise.all([
        axios.get(`${API}/publish-jobs/${pid}`),
        axios.get(`${API}/channel-configs/${pid}`),
      ]);
      setJobs(j.data.jobs || []); setChannels(c.data.configs || []);
    } catch { /* */ }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    try {
      await axios.post(`${API}/publish-jobs/${pid}`, form);
      toast.success("Publish job queued");
      setShowForm(false); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const runJob = async (id) => {
    try { const { data } = await axios.post(`${API}/publish-jobs/${id}/run`); toast.success(`${data.status}: ${data.items_ok} ok, ${data.items_error} errors`); load(); }
    catch { toast.error("Failed"); }
  };

  const del = async (id) => { await axios.delete(`${API}/publish-jobs/${id}`); load(); };

  return (
    <div className="space-y-4" data-testid="chmgr-publishjobs">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">Publish Jobs</h2>
          <p className="text-sm text-stone-500">Manage ARI distribution to channels.</p>
        </div>
        <button onClick={() => setShowForm(true)} className="px-4 py-2 bg-emerald-600 text-white rounded-xl text-sm font-semibold flex items-center gap-2" data-testid="chmgr-new-job">
          <Plus className="w-4 h-4" /> New Publish Job
        </button>
      </div>

      {showForm && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <select value={form.channel_id} onChange={e => setForm(f => ({ ...f, channel_id: e.target.value }))} className="px-3 py-2 border rounded-lg text-sm">
              {channels.map(c => <option key={c.channel_id} value={c.channel_id}>{c.name}</option>)}
              {channels.length === 0 && <option value="booking_com">Booking.com</option>}
            </select>
            <input type="number" value={form.items_total} onChange={e => setForm(f => ({ ...f, items_total: parseInt(e.target.value) || 30 }))} placeholder="Items" className="px-3 py-2 border rounded-lg text-sm" />
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.dry_run} onChange={e => setForm(f => ({ ...f, dry_run: e.target.checked }))} /> Dry-run</label>
          </div>
          <div className="flex gap-2">
            <button onClick={create} className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-semibold" data-testid="chmgr-job-save">Queue Job</button>
            <button onClick={() => setShowForm(false)} className="px-4 py-2 bg-white border rounded-lg text-sm">Cancel</button>
          </div>
        </div>
      )}

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <div className="grid grid-cols-[auto,1fr,1fr,1fr,1fr,auto] gap-3 px-4 py-3 bg-stone-50 text-xs font-semibold text-stone-500 uppercase tracking-wider">
          <div>ID</div><div>Channel</div><div>Type</div><div>Status</div><div>Progress</div><div></div>
        </div>
        {jobs.map(j => (
          <div key={j.id} className="grid grid-cols-[auto,1fr,1fr,1fr,1fr,auto] gap-3 px-4 py-3 border-t border-stone-100 items-center text-sm">
            <div className="font-mono text-xs text-stone-400">{j.id.slice(0, 6)}</div>
            <div>{channels.find(c => c.channel_id === j.channel_id)?.name || j.channel_id}{j.dry_run && <Badge className="ml-2 bg-amber-100 text-amber-700 text-[10px]">DRY</Badge>}</div>
            <div className="text-xs text-stone-500">{j.type}</div>
            <Badge className={j.status === "completed" ? "bg-emerald-100 text-emerald-700" : j.status === "partial" ? "bg-amber-100 text-amber-700" : j.status === "queued" ? "bg-blue-100 text-blue-700" : "bg-stone-100 text-stone-600"}>{j.status}</Badge>
            <div className="text-xs">{j.progress}% · {j.items_ok}/{j.items_total}{j.items_error ? ` · ${j.items_error} err` : ""}</div>
            <div className="flex gap-1">
              {j.status === "queued" && <button onClick={() => runJob(j.id)} className="text-blue-600" data-testid={`chmgr-run-${j.id.slice(0,6)}`}><Play className="w-4 h-4" /></button>}
              <button onClick={() => del(j.id)} className="text-rose-500"><Trash2 className="w-4 h-4" /></button>
            </div>
          </div>
        ))}
        {jobs.length === 0 && <div className="p-10 text-center text-sm text-stone-400">No publish jobs yet</div>}
      </div>
    </div>
  );
};

/* ═══════════ AUDIT LOGS ═══════════ */
const AuditLogsPanel = ({ pid }) => {
  const [data, setData] = useState({ rows: [], events: [] });
  const [search, setSearch] = useState("");
  const [event, setEvent] = useState("");

  const load = useCallback(async () => {
    try {
      const qs = new URLSearchParams();
      if (search) qs.set("search", search);
      if (event) qs.set("event", event);
      const { data } = await axios.get(`${API}/channel-audit/${pid}?${qs}`);
      setData(data);
    } catch { /* */ }
  }, [pid, search, event]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);

  return (
    <div className="space-y-4" data-testid="chmgr-auditlogs">
      <div>
        <h2 className="text-xl font-bold">Audit Logs</h2>
        <p className="text-sm text-stone-500">Distribution event history and audit trail.</p>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search events…" className="px-3 py-2 border rounded-lg text-sm w-64" data-testid="chmgr-audit-search" />
        <select value={event} onChange={e => setEvent(e.target.value)} className="px-3 py-2 border rounded-lg text-sm" data-testid="chmgr-audit-filter">
          <option value="">{`All Events (${data.events?.reduce((s, e) => s + e.count, 0) || 0})`}</option>
          {data.events?.map(e => <option key={e.event} value={e.event}>{`${e.event} (${e.count})`}</option>)}
        </select>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <div className="grid grid-cols-[auto,1fr,2fr,1fr,1fr] gap-3 px-4 py-3 bg-stone-50 text-xs font-semibold text-stone-500 uppercase tracking-wider">
          <div>ID</div><div>Event</div><div>Details</div><div>User</div><div>Timestamp</div>
        </div>
        {data.rows.map(r => (
          <div key={r.id} className="grid grid-cols-[auto,1fr,2fr,1fr,1fr] gap-3 px-4 py-3 border-t border-stone-100 items-center text-sm">
            <div className="font-mono text-xs text-stone-400">{r.id.slice(0, 6)}</div>
            <Badge className="bg-blue-50 text-blue-700 text-[10px]">{r.event}</Badge>
            <div className="text-xs text-stone-500 font-mono truncate">{JSON.stringify(r.details)}</div>
            <div className="text-xs">{r.user_email}</div>
            <div className="text-xs text-stone-400">{new Date(r.ts).toLocaleString()}</div>
          </div>
        ))}
        {data.rows.length === 0 && <div className="p-10 text-center text-sm text-stone-400">No audit events match</div>}
      </div>
    </div>
  );
};

/* ═══════════ PROFILES ═══════════ */
const ProfilesPanel = ({ pid }) => {
  const [profiles, setProfiles] = useState([]);
  const [channels, setChannels] = useState([]);
  const [selChan, setSelChan] = useState("booking_com");

  const load = useCallback(async () => {
    try {
      const [p, c] = await Promise.all([
        axios.get(`${API}/payload-profiles/${pid}`),
        axios.get(`${API}/channel-configs/${pid}`),
      ]);
      setProfiles(p.data.profiles || []); setChannels(c.data.configs || []);
    } catch { /* */ }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const discover = async () => {
    try {
      const { data } = await axios.post(`${API}/payload-profiles/${pid}/discover`, { channel_id: selChan });
      toast.success(`Discovered ${data.field_count} fields`);
      load();
    } catch { toast.error("Failed"); }
  };

  return (
    <div className="space-y-4" data-testid="chmgr-profiles">
      <div>
        <h2 className="text-xl font-bold">Payload Profiles</h2>
        <p className="text-sm text-stone-500">Discover supported fields and payload constraints for each channel.</p>
      </div>

      <div className="flex items-center gap-3">
        <select value={selChan} onChange={e => setSelChan(e.target.value)} className="px-3 py-2 border rounded-lg text-sm">
          {channels.map(c => <option key={c.channel_id} value={c.channel_id}>{c.name}</option>)}
          {channels.length === 0 && <option value="booking_com">Booking.com</option>}
        </select>
        <button onClick={discover} className="px-4 py-2 bg-emerald-600 text-white rounded-xl text-sm font-semibold flex items-center gap-2" data-testid="chmgr-discover-profile">
          <Sparkles className="w-4 h-4" /> Discover Fields
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {profiles.map(p => (
          <div key={p.id} className="bg-white border border-stone-200 rounded-xl p-5">
            <div className="flex items-start justify-between mb-3">
              <div>
                <div className="font-bold">{channels.find(c => c.channel_id === p.channel_id)?.name || p.channel_id}</div>
                <div className="text-xs text-stone-400">Discovered {new Date(p.discovered_at).toLocaleString()}</div>
              </div>
              <Badge className="bg-blue-100 text-blue-700">{p.field_count} fields</Badge>
            </div>
            <div className="max-h-48 overflow-y-auto text-xs space-y-1 border-t border-stone-100 pt-2">
              {p.fields.map(f => (
                <div key={f.key} className="flex items-center justify-between py-1">
                  <span className="font-mono">{f.key}</span>
                  <span className="flex items-center gap-2 text-stone-500">
                    <span>{f.type}</span>
                    {f.required && <Badge className="bg-rose-100 text-rose-700 text-[10px]">req</Badge>}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
        {profiles.length === 0 && <div className="md:col-span-2 p-10 text-center text-sm text-stone-400 bg-white border rounded-xl">No profiles discovered yet</div>}
      </div>
    </div>
  );
};

/* ═══════════ OVERRIDES ═══════════ */
const OverridesPanel = ({ pid }) => {
  const [overrides, setOverrides] = useState([]);
  const [channels, setChannels] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [form, setForm] = useState({
    channel_id: "", room_type_id: "",
    from_date: new Date().toISOString().slice(0, 10),
    to_date: new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10),
    adjustment_type: "percent", value: 10, reason: "",
  });
  const [showForm, setShowForm] = useState(false);

  const load = useCallback(async () => {
    try {
      const [o, c, r] = await Promise.all([
        axios.get(`${API}/price-overrides/${pid}`),
        axios.get(`${API}/channel-configs/${pid}`),
        axios.get(`${API}/channel-mappings/${pid}`),
      ]);
      setOverrides(o.data.overrides || []); setChannels(c.data.configs || []); setRooms(r.data.room_types || []);
      setForm(f => ({ ...f, channel_id: f.channel_id || c.data.configs?.[0]?.channel_id || "", room_type_id: f.room_type_id || r.data.room_types?.[0]?.id || "" }));
    } catch { /* */ }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    try {
      await axios.post(`${API}/price-overrides/${pid}`, form);
      toast.success("Override created");
      setShowForm(false); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const del = async (id) => { await axios.delete(`${API}/price-overrides/${id}`); toast.success("Deleted"); load(); };

  return (
    <div className="space-y-4" data-testid="chmgr-overrides">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">Price Overrides</h2>
          <p className="text-sm text-stone-500">Per-channel, per-room temporary price adjustments (% or fixed).</p>
        </div>
        <button onClick={() => setShowForm(true)} className="px-4 py-2 bg-emerald-600 text-white rounded-xl text-sm font-semibold flex items-center gap-2" data-testid="chmgr-new-override">
          <Plus className="w-4 h-4" /> New Override
        </button>
      </div>

      {showForm && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5 space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <select value={form.channel_id} onChange={e => setForm(f => ({ ...f, channel_id: e.target.value }))} className="px-3 py-2 border rounded-lg text-sm">
              {channels.map(c => <option key={c.channel_id} value={c.channel_id}>{c.name}</option>)}
            </select>
            <select value={form.room_type_id} onChange={e => setForm(f => ({ ...f, room_type_id: e.target.value }))} className="px-3 py-2 border rounded-lg text-sm">
              {rooms.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
            <input type="date" value={form.from_date} onChange={e => setForm(f => ({ ...f, from_date: e.target.value }))} className="px-3 py-2 border rounded-lg text-sm" />
            <input type="date" value={form.to_date} onChange={e => setForm(f => ({ ...f, to_date: e.target.value }))} className="px-3 py-2 border rounded-lg text-sm" />
            <select value={form.adjustment_type} onChange={e => setForm(f => ({ ...f, adjustment_type: e.target.value }))} className="px-3 py-2 border rounded-lg text-sm">
              <option value="percent">Percent (%)</option><option value="fixed">Fixed (+/-)</option><option value="absolute">Absolute</option>
            </select>
            <input type="number" value={form.value} onChange={e => setForm(f => ({ ...f, value: parseFloat(e.target.value) }))} placeholder="Value" className="px-3 py-2 border rounded-lg text-sm" />
            <input value={form.reason} onChange={e => setForm(f => ({ ...f, reason: e.target.value }))} placeholder="Reason" className="px-3 py-2 border rounded-lg text-sm md:col-span-2" />
          </div>
          <div className="flex gap-2">
            <button onClick={create} className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-semibold" data-testid="chmgr-override-save">Create</button>
            <button onClick={() => setShowForm(false)} className="px-4 py-2 bg-white border rounded-lg text-sm">Cancel</button>
          </div>
        </div>
      )}

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <div className="grid grid-cols-[1fr,1fr,1fr,auto,1fr,auto] gap-3 px-4 py-3 bg-stone-50 text-xs font-semibold text-stone-500 uppercase tracking-wider">
          <div>Channel</div><div>Room</div><div>Period</div><div>Adjustment</div><div>Reason</div><div></div>
        </div>
        {overrides.map(o => (
          <div key={o.id} className="grid grid-cols-[1fr,1fr,1fr,auto,1fr,auto] gap-3 px-4 py-3 border-t border-stone-100 items-center text-sm">
            <div>{channels.find(c => c.channel_id === o.channel_id)?.name || o.channel_id}</div>
            <div className="text-xs">{rooms.find(r => r.id === o.room_type_id)?.name || o.room_type_id}</div>
            <div className="text-xs text-stone-500">{o.from_date} → {o.to_date}</div>
            <Badge className="bg-violet-100 text-violet-700">{o.adjustment_type === "percent" ? `${o.value > 0 ? "+" : ""}${o.value}%` : o.value}</Badge>
            <div className="text-xs text-stone-500 truncate">{o.reason || "—"}</div>
            <button onClick={() => del(o.id)} className="text-rose-500"><Trash2 className="w-4 h-4" /></button>
          </div>
        ))}
        {overrides.length === 0 && <div className="p-10 text-center text-sm text-stone-400">No overrides — click <b>New Override</b> to add one.</div>}
      </div>
    </div>
  );
};

/* ═══════════ ALLOCATIONS (Pooled Inventory) ═══════════ */
const AllocationCell = ({ pid, row, cell, onChanged }) => {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(String(cell.effective_cap ?? ""));

  const save = async () => {
    const trimmed = String(value).trim();
    try {
      await axios.put(`${API}/inventory-allocations/${pid}/cell`, {
        channel_id: row.channel_id, room_type_id: row.room_type_id,
        date: cell.date,
        allocation_cap: trimmed === "" ? null : parseInt(trimmed),
      });
      toast.success(trimmed === "" ? "Cleared" : `Cap → ${trimmed}`);
      setEditing(false);
      onChanged();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed");
    }
  };

  const propagate = async (days, mode = "consecutive") => {
    const trimmed = String(value).trim();
    try {
      const { data } = await axios.post(`${API}/inventory-allocations/${pid}/cell/propagate`, {
        channel_id: row.channel_id, room_type_id: row.room_type_id,
        from_date: cell.date, days, mode,
        allocation_cap: trimmed === "" ? null : parseInt(trimmed),
      });
      const verb = trimmed === "" ? "Cleared" : `Cap → ${trimmed}`;
      const scope = mode === "same_weekday"
        ? `${data.dates_affected} ${new Date(cell.date).toLocaleDateString("en-GB", { weekday: "long" })}s`
        : `${data.dates_affected} consecutive days`;
      toast.success(`${verb} on ${scope}`);
      setEditing(false);
      onChanged();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed");
    }
  };

  const ratio = row.total_inventory ? cell.available / row.total_inventory : 0;
  const bg = cell.available === 0 ? "bg-rose-100 text-rose-700" : ratio < 0.3 ? "bg-amber-100 text-amber-700" : "bg-emerald-50 text-emerald-700";
  const edited = cell.edited ? "ring-2 ring-violet-500 ring-inset" : "";

  if (editing) {
    return (
      <td className="p-0.5 border-r border-stone-100 relative">
        <input
          autoFocus
          type="number"
          min="0"
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") save(); if (e.key === "Escape") { setEditing(false); } }}
          className="w-full h-8 text-center font-mono text-xs border-violet-500 border rounded px-1 focus:outline-none"
          data-testid={`chmgr-alloc-cell-input-${row.room_type_id}-${row.channel_id}-${cell.date}`}
        />
        {/* Popover with quick actions */}
        <div className="absolute z-20 top-full left-1/2 -translate-x-1/2 mt-1 bg-white border border-stone-200 rounded-xl shadow-xl p-2 min-w-[180px]" onMouseDown={e => e.preventDefault()}>
          <button onClick={save} className="w-full text-left px-3 py-1.5 rounded hover:bg-emerald-50 text-xs font-semibold text-emerald-700" data-testid={`chmgr-alloc-save-1-${cell.date}`}>
            Save for this day
          </button>
          <div className="border-t border-stone-100 my-1" />
          <div className="text-[10px] text-stone-400 uppercase tracking-wider px-3 pt-1">Propagate — next</div>
          {[7, 14, 30].map(d => (
            <button key={d} onClick={() => propagate(d, "consecutive")} className="w-full text-left px-3 py-1 rounded hover:bg-violet-50 text-xs text-violet-700" data-testid={`chmgr-alloc-prop-${d}d-${cell.date}`}>
              {d} consecutive days
            </button>
          ))}
          <div className="border-t border-stone-100 my-1" />
          <div className="text-[10px] text-stone-400 uppercase tracking-wider px-3 pt-1">Same weekday — next</div>
          {[30, 60, 90].map(d => (
            <button key={d} onClick={() => propagate(d, "same_weekday")} className="w-full text-left px-3 py-1 rounded hover:bg-violet-50 text-xs text-violet-700" data-testid={`chmgr-alloc-propw-${d}d-${cell.date}`}>
              every {new Date(cell.date).toLocaleDateString("en-GB", { weekday: "long" })} for {d} days
            </button>
          ))}
          <div className="border-t border-stone-100 my-1" />
          <button onClick={() => { setValue(""); setTimeout(save, 0); }} className="w-full text-left px-3 py-1.5 rounded hover:bg-rose-50 text-xs text-rose-600" data-testid={`chmgr-alloc-clear-${cell.date}`}>
            Clear override
          </button>
        </div>
      </td>
    );
  }
  return (
    <td
      onClick={() => setEditing(true)}
      className={`p-1 text-center font-mono cursor-pointer hover:opacity-80 ${bg} ${edited} border-r border-stone-100`}
      title={`${cell.edited ? "Date-specific cap: " + cell.effective_cap + " · " : ""}Sold on channel: ${cell.sold_on_channel} · Sold all: ${cell.sold_all} · Total: ${cell.total_inventory} · Click to edit`}
      data-testid={`chmgr-alloc-cell-${row.room_type_id}-${row.channel_id}-${cell.date}`}
    >
      {cell.available}
    </td>
  );
};

const AllocationsPanel = ({ pid }) => {
  const [rules, setRules] = useState([]);
  const [channels, setChannels] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [cal, setCal] = useState(null);
  const [fromDate, setFromDate] = useState(new Date().toISOString().slice(0, 10));
  const [toDate, setToDate] = useState(new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 10));
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ channel_id: "", room_type_id: "", mode: "dedicated", allocation_cap: 5, buffer: 0, spillover_priority: 10 });

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/inventory-allocations/${pid}`);
      setRules(data.rules || []); setChannels(data.channels || []); setRooms(data.room_types || []);
      setForm(f => ({ ...f,
        channel_id: f.channel_id || data.channels?.[0]?.channel_id || "",
        room_type_id: f.room_type_id || data.room_types?.[0]?.id || "",
      }));
    } catch { /* */ }
  }, [pid]);
  const loadCal = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/inventory-allocations/${pid}/calendar?from_date=${fromDate}&to_date=${toDate}`); setCal(data); }
    catch { /* */ }
  }, [pid, fromDate, toDate]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadCal(); }, [loadCal]);

  const upsert = async () => {
    try {
      await axios.put(`${API}/inventory-allocations/${pid}/upsert`, form);
      toast.success("Allocation rule saved"); setShowForm(false); load(); loadCal();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const del = async (id) => { await axios.delete(`${API}/inventory-allocations/${id}`); toast.success("Removed"); load(); loadCal(); };

  const modeBadge = (m) => m === "dedicated" ? "bg-blue-100 text-blue-700" : m === "capped" ? "bg-amber-100 text-amber-700" : "bg-stone-100 text-stone-700";

  return (
    <div className="space-y-4" data-testid="chmgr-allocations">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">Inventory Allocations</h2>
          <p className="text-sm text-stone-500">Per-channel × room-type inventory policy. Pooled = share the pot · Dedicated = hard reserved units · Capped = soft cap with spillover.</p>
        </div>
        <button onClick={() => setShowForm(true)} className="px-4 py-2 bg-emerald-600 text-white rounded-xl text-sm font-semibold flex items-center gap-2" data-testid="chmgr-alloc-new">
          <Plus className="w-4 h-4" /> New Rule
        </button>
      </div>

      {showForm && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5 space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <select value={form.channel_id} onChange={e => setForm(f => ({ ...f, channel_id: e.target.value }))} className="px-3 py-2 border rounded-lg text-sm">
              {channels.map(c => <option key={c.channel_id} value={c.channel_id}>{c.name}</option>)}
            </select>
            <select value={form.room_type_id} onChange={e => setForm(f => ({ ...f, room_type_id: e.target.value }))} className="px-3 py-2 border rounded-lg text-sm">
              {rooms.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
            <select value={form.mode} onChange={e => setForm(f => ({ ...f, mode: e.target.value }))} className="px-3 py-2 border rounded-lg text-sm">
              <option value="pooled">Pooled (share inventory)</option>
              <option value="dedicated">Dedicated (reserved)</option>
              <option value="capped">Capped (soft cap + spillover)</option>
            </select>
            <input type="number" value={form.allocation_cap} onChange={e => setForm(f => ({ ...f, allocation_cap: parseInt(e.target.value) || 0 }))} placeholder="Allocation Cap" className="px-3 py-2 border rounded-lg text-sm" disabled={form.mode === "pooled"} />
            <input type="number" value={form.buffer} onChange={e => setForm(f => ({ ...f, buffer: parseInt(e.target.value) || 0 }))} placeholder="Buffer (hold back)" className="px-3 py-2 border rounded-lg text-sm" />
            <input type="number" value={form.spillover_priority} onChange={e => setForm(f => ({ ...f, spillover_priority: parseInt(e.target.value) || 10 }))} placeholder="Spillover Priority" className="px-3 py-2 border rounded-lg text-sm" />
          </div>
          <div className="flex gap-2">
            <button onClick={upsert} className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-semibold" data-testid="chmgr-alloc-save">Save Rule</button>
            <button onClick={() => setShowForm(false)} className="px-4 py-2 bg-white border rounded-lg text-sm">Cancel</button>
          </div>
        </div>
      )}

      {/* Rules list */}
      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <div className="grid grid-cols-[1fr,1fr,auto,auto,auto,auto,auto] gap-3 px-4 py-3 bg-stone-50 text-xs font-semibold text-stone-500 uppercase tracking-wider">
          <div>Channel</div><div>Room</div><div>Mode</div><div>Cap</div><div>Buffer</div><div>Priority</div><div></div>
        </div>
        {rules.map(r => (
          <div key={r.id} className="grid grid-cols-[1fr,1fr,auto,auto,auto,auto,auto] gap-3 px-4 py-3 border-t border-stone-100 items-center text-sm">
            <div>{channels.find(c => c.channel_id === r.channel_id)?.name || r.channel_id}</div>
            <div>{rooms.find(rt => rt.id === r.room_type_id)?.name || r.room_type_id}</div>
            <Badge className={modeBadge(r.mode)}>{r.mode}</Badge>
            <div className="font-mono">{r.allocation_cap || "—"}</div>
            <div className="font-mono">{r.buffer || "—"}</div>
            <div className="font-mono">{r.spillover_priority}</div>
            <button onClick={() => del(r.id)} className="text-rose-500"><Trash2 className="w-4 h-4" /></button>
          </div>
        ))}
        {rules.length === 0 && <div className="p-10 text-center text-sm text-stone-400">No rules yet — all channels will share the pooled inventory by default.</div>}
      </div>

      {/* Availability Calendar */}
      <div className="bg-white border border-stone-200 rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="font-bold">Availability per Channel</h3>
            <p className="text-xs text-stone-500">Click any cell to override the cap for that specific date. Cells with a violet ring have date-level overrides.</p>
          </div>
          <div className="flex items-center gap-2">
            <input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} className="px-2 py-1 border rounded text-sm" />
            <span className="text-xs text-stone-400">to</span>
            <input type="date" value={toDate} onChange={e => setToDate(e.target.value)} className="px-2 py-1 border rounded text-sm" />
          </div>
        </div>
        {cal && (
          <div className="overflow-x-auto">
            <table className="text-xs min-w-max">
              <thead>
                <tr>
                  <th className="text-left p-2 sticky left-0 bg-white border-r">Room × Channel</th>
                  {cal.dates.map(d => (
                    <th key={d} className="p-1 text-center text-[10px] font-semibold text-stone-500 min-w-[52px]">
                      {new Date(d).toLocaleDateString("en-GB", { day: "2-digit", month: "short" })}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {cal.grid.map((row, i) => (
                  <tr key={i} className="border-t">
                    <td className="p-2 sticky left-0 bg-white border-r">
                      <div className="font-semibold">{row.room_type_name}</div>
                      <div className="text-[10px] text-stone-400">{row.channel_name} · <span className="font-mono">{row.mode}</span></div>
                    </td>
                    {row.cells.map((c, j) => (
                      <AllocationCell key={j} pid={pid} row={row} cell={c} onChanged={loadCal} />
                    ))}
                  </tr>
                ))}
                {cal.grid.length === 0 && <tr><td colSpan={cal.dates.length + 1} className="p-10 text-center text-stone-400">No channels or rooms configured</td></tr>}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

/* ═══════════ STOP SELL CALENDAR ═══════════ */
const StopSellPanel = ({ pid }) => {
  const [data, setData] = useState(null);
  const [fromDate, setFromDate] = useState(new Date().toISOString().slice(0, 10));
  const [toDate, setToDate] = useState(new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10));

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/channel-restrictions/${pid}?from_date=${fromDate}&to_date=${toDate}`);
      setData(data);
    } catch { /* */ }
  }, [pid, fromDate, toDate]);
  useEffect(() => { load(); }, [load]);

  const toggle = async (channel_id, date, currentlyStopped) => {
    try {
      await axios.put(`${API}/channel-restrictions/${pid}/bulk`, {
        from_date: date, to_date: date,
        channel_ids: [channel_id],
        stop_sell: !currentlyStopped,
      });
      load();
    } catch { toast.error("Failed"); }
  };

  const dates = useMemo(() => {
    const out = [];
    let d = new Date(fromDate);
    const end = new Date(toDate);
    while (d <= end) {
      out.push(d.toISOString().slice(0, 10));
      d = new Date(d.getTime() + 86400000);
    }
    return out;
  }, [fromDate, toDate]);

  const channels = data?.channels || [];
  const stoppedSet = new Set();
  (data?.restrictions || []).forEach(r => {
    if (r.stop_sell) stoppedSet.add(`${r.channel_id}|${r.date}`);
  });

  return (
    <div className="space-y-4" data-testid="chmgr-stop-sell">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">Stop-Sell Calendar</h2>
          <p className="text-sm text-stone-500">Click any cell to toggle stop-sell for that channel on that date. Red = stopped, green = selling.</p>
        </div>
        <div className="flex items-center gap-2">
          <CalIcon className="w-4 h-4 text-stone-400" />
          <input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} className="px-2 py-1 border rounded text-sm" />
          <span className="text-xs text-stone-400">to</span>
          <input type="date" value={toDate} onChange={e => setToDate(e.target.value)} className="px-2 py-1 border rounded text-sm" />
        </div>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl p-4">
        {channels.length === 0 && <div className="p-10 text-center text-sm text-stone-400">No channels yet — add one in Channels tab first.</div>}
        {channels.length > 0 && (
          <div className="overflow-x-auto">
            <table className="text-xs min-w-max">
              <thead>
                <tr>
                  <th className="text-left p-2 sticky left-0 bg-white border-r z-10">Channel</th>
                  {dates.map(d => {
                    const dayOfWeek = new Date(d).toLocaleDateString("en-GB", { weekday: "short" })[0];
                    return (
                      <th key={d} className="p-1 text-center text-[10px] font-semibold text-stone-500 min-w-[40px]">
                        <div>{new Date(d).getDate()}</div>
                        <div className="text-stone-400">{dayOfWeek}</div>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {channels.map(ch => (
                  <tr key={ch.channel_id} className="border-t">
                    <td className="p-2 sticky left-0 bg-white border-r font-semibold">{ch.name}</td>
                    {dates.map(d => {
                      const key = `${ch.channel_id}|${d}`;
                      const stopped = stoppedSet.has(key);
                      return (
                        <td key={d} className="p-0.5 border-r border-stone-100">
                          <button
                            onClick={() => toggle(ch.channel_id, d, stopped)}
                            className={`w-full h-8 rounded text-[11px] font-bold transition ${stopped ? "bg-rose-500 text-white hover:bg-rose-600" : "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"}`}
                            data-testid={`chmgr-stopsell-${ch.channel_id}-${d}`}
                            title={stopped ? "Stopped — click to open" : "Open — click to stop-sell"}
                          >
                            {stopped ? <Ban className="w-3.5 h-3.5 mx-auto" /> : "✓"}
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="flex items-center gap-4 text-xs text-stone-500">
        <span className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-emerald-50 border border-emerald-300" /> Selling</span>
        <span className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-rose-500" /> Stop-Sell</span>
        <span>·</span>
        <span>Changes push to the OTA on next sync.</span>
      </div>
    </div>
  );
};

/* ═══════════ UNASSIGNED OTA BOOKINGS (iter 372) ═══════════ */
const UnassignedOTAPanel = ({ pid }) => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [retrying, setRetrying] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/ota-inbound/unassigned?limit=100`);
      const items = (r.data?.items || []).filter(x => !pid || !x.property_id || x.property_id === pid || pid === "aldgate-flats");
      setRows(items);
    } catch (e) {
      toast.error("Yüklenemedi: " + (e.response?.data?.detail || e.message));
    }
    setLoading(false);
  }, [pid]);

  useEffect(() => { load(); }, [load]);

  const retry = async (bid) => {
    setRetrying(prev => ({ ...prev, [bid]: true }));
    try {
      const r = await axios.post(`${API}/ota-inbound/auto-assign/${bid}`);
      if (r.data?.ok) {
        toast.success(`Oda atandı: ${r.data.room_number}${r.data.upgrade ? " (upgrade!)" : ""} · skor ${r.data.score}`);
        await load();
      } else {
        toast.warning(`Atanamadı: ${r.data?.reason || "unknown"}`);
      }
    } catch (e) {
      toast.error("Retry başarısız: " + (e.response?.data?.detail || e.message));
    }
    setRetrying(prev => ({ ...prev, [bid]: false }));
  };

  return (
    <div className="space-y-4" data-testid="unassigned-ota-panel">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xl font-bold text-stone-900 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-600" />
            Unassigned OTA Bookings
          </div>
          <div className="text-sm text-stone-500 mt-1">
            OTA&apos;dan gelen ama otomatik oda ataması yapılamayan rezervasyonlar. Odaları manuel atayabilir veya auto-assign&apos;ı yeniden deneyebilirsiniz.
          </div>
        </div>
        <button onClick={load} disabled={loading}
          className="px-3 py-1.5 text-sm rounded-md bg-white border border-stone-300 hover:bg-stone-50 flex items-center gap-2 disabled:opacity-50"
          data-testid="unassigned-refresh-btn">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          Yenile
        </button>
      </div>

      {loading && rows.length === 0 && (
        <div className="p-8 text-center text-stone-400 border border-dashed rounded-lg" data-testid="unassigned-loading">
          Yükleniyor…
        </div>
      )}

      {!loading && rows.length === 0 && (
        <div className="p-10 text-center border border-dashed rounded-lg bg-emerald-50/50" data-testid="unassigned-empty">
          <CheckCircle2 className="w-10 h-10 mx-auto text-emerald-600 mb-2" />
          <div className="text-stone-700 font-semibold">Harika — atanmamış OTA rezervasyonu yok!</div>
          <div className="text-xs text-stone-500 mt-1">Tüm OTA rezervasyonları otomatik olarak atanmış durumda.</div>
        </div>
      )}

      {rows.length > 0 && (
        <div className="overflow-x-auto border rounded-lg bg-white">
          <table className="w-full text-sm" data-testid="unassigned-table">
            <thead className="bg-stone-50 text-stone-600 text-xs uppercase tracking-wide">
              <tr>
                <th className="px-3 py-2 text-left">Kanal</th>
                <th className="px-3 py-2 text-left">Ref</th>
                <th className="px-3 py-2 text-left">Misafir</th>
                <th className="px-3 py-2 text-left">Property</th>
                <th className="px-3 py-2 text-left">Room Type</th>
                <th className="px-3 py-2 text-left">Check-in</th>
                <th className="px-3 py-2 text-left">Nights</th>
                <th className="px-3 py-2 text-left">Sebep</th>
                <th className="px-3 py-2 text-right">Aksiyon</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {rows.map(b => {
                const nights = (() => {
                  try {
                    const ci = new Date(b.check_in); const co = new Date(b.check_out);
                    return Math.max(1, Math.round((co - ci) / 86400000));
                  } catch { return "-"; }
                })();
                const isRetrying = !!retrying[b.id];
                return (
                  <tr key={b.id} data-testid={`unassigned-row-${b.id}`}>
                    <td className="px-3 py-2">
                      <Badge variant="outline" className="text-xs uppercase">{b.channel || b.source?.replace("ota:", "") || "-"}</Badge>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-stone-600">{b.channel_reference || "-"}</td>
                    <td className="px-3 py-2 font-medium text-stone-800">{b.guest_name || "-"}</td>
                    <td className="px-3 py-2 text-xs text-stone-600">{b.property_id || "-"}</td>
                    <td className="px-3 py-2 text-xs text-stone-600">{b.room_type_id || "—"}</td>
                    <td className="px-3 py-2 text-xs text-stone-600">{b.check_in || "-"}</td>
                    <td className="px-3 py-2 text-xs">{nights}</td>
                    <td className="px-3 py-2 text-xs text-amber-700">
                      {b.unassigned_reason === "no_available_room" ? "Uygun oda yok" : (b.unassigned_reason || "—")}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <button onClick={() => retry(b.id)} disabled={isRetrying}
                        className="px-3 py-1.5 text-xs rounded-md bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-wait inline-flex items-center gap-1.5"
                        data-testid={`unassigned-retry-${b.id}`}>
                        {isRetrying ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                        {isRetrying ? "…" : "Retry"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="px-3 py-2 text-xs text-stone-500 bg-stone-50 border-t">
            Toplam <b>{rows.length}</b> unassigned booking · Retry&apos;lar auto-assign skorunu kullanır (loyalty tier, view preference, room_type match, housekeeping).
          </div>
        </div>
      )}
    </div>
  );
};

/* ═══════════ MAIN HUB ═══════════ */
export const ChannelManagerHub = ({ activePropertyId, initialPanel }) => {
  const pid = activePropertyId || "aldgate-flats";
  const [panel, setPanel] = useState(initialPanel || "dashboard");

  useEffect(() => {
    if (initialPanel && initialPanel !== panel) setPanel(initialPanel);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialPanel]);

  return (
    <div className="p-6 space-y-5" data-testid="channel-manager-hub">
      {/* Breadcrumb + tab strip */}
      <div>
        <div className="text-xs text-stone-400 mb-1">Channel Manager</div>
        <div className="flex gap-1 overflow-x-auto border-b border-stone-200 pb-[1px]">
          {PANELS.map(p => {
            const Icon = p.icon;
            const active = panel === p.key;
            return (
              <button key={p.key} onClick={() => setPanel(p.key)}
                className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold whitespace-nowrap border-b-2 transition ${active ? "border-emerald-600 text-emerald-700" : "border-transparent text-stone-500 hover:text-stone-700"}`}
                data-testid={`chmgr-tab-${p.key}`}>
                <Icon className="w-4 h-4" />
                {p.label}
              </button>
            );
          })}
        </div>
      </div>

      {panel === "dashboard"      && <HubDashboard pid={pid} goTo={setPanel} />}
      {panel === "channels"       && <ChannelsPanel pid={pid} />}
      {panel === "mappings"       && <MappingsPanel pid={pid} />}
      {panel === "allocations"    && <AllocationsPanel pid={pid} />}
      {panel === "stop-sell"      && <StopSellPanel pid={pid} />}
      {panel === "publish-jobs"   && <PublishJobsPanel pid={pid} />}
      {panel === "audit-logs"     && <AuditLogsPanel pid={pid} />}
      {panel === "unassigned"     && <UnassignedOTAPanel pid={pid} />}
      {panel === "profiles"       && <ProfilesPanel pid={pid} />}
      {panel === "overrides"      && <OverridesPanel pid={pid} />}
    </div>
  );
};

export default ChannelManagerHub;
