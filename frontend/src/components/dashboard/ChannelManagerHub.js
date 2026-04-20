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
  LayoutDashboard, Plug, Link2, Grid3x3, UploadCloud, ScrollText,
  BarChart3, FileCode2, Percent, CheckCircle2, CircleDashed, Lock,
  Zap, Plus, RefreshCw, Play, Trash2, TrendingUp, TrendingDown,
  AlertTriangle, Activity, Sparkles, Globe2, Shield, ChevronRight,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PANELS = [
  { key: "dashboard",       label: "Dashboard",       icon: LayoutDashboard },
  { key: "channels",        label: "Channels",        icon: Plug },
  { key: "mappings",        label: "Mappings",        icon: Link2 },
  { key: "rate-structure",  label: "Rate Structure",  icon: Grid3x3 },
  { key: "publish-jobs",    label: "Publish Jobs",    icon: UploadCloud },
  { key: "audit-logs",      label: "Audit Logs",      icon: ScrollText },
  { key: "benchmark",       label: "Benchmark",       icon: BarChart3 },
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
                      const map = { create_config: "channels", enter_credentials: "channels", run_certification: "channels", create_payload: "profiles", complete_mappings: "mappings", verify_rate_structure: "rate-structure", dry_run: "publish-jobs", enable_autopublish: "channels" };
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
          { k: "rate-structure", l: "Rate Structure", d: "Pricing rules", i: Grid3x3 },
          { k: "publish-jobs", l: "Publish Jobs", d: "Distribution status", i: UploadCloud },
          { k: "audit-logs", l: "Audit Logs", d: "History & Errors", i: ScrollText },
          { k: "overrides", l: "Overrides", d: "Price adjustments", i: Percent },
          { k: "benchmark", l: "Benchmark", d: "Compset index", i: BarChart3 },
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

/* ═══════════ RATE STRUCTURE (Variants) ═══════════ */
const RateStructurePanel = ({ pid }) => {
  const [rows, setRows] = useState([]);
  const [channels, setChannels] = useState([]);

  const load = useCallback(async () => {
    try {
      const [v, c] = await Promise.all([
        axios.get(`${API}/rate-variants/${pid}`),
        axios.get(`${API}/channel-configs/${pid}`),
      ]);
      setRows(v.data.rows || []); setChannels(c.data.configs || []);
    } catch { /* */ }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const autoGen = async () => {
    try {
      const { data } = await axios.post(`${API}/rate-variants/${pid}/auto-generate`, {});
      toast.success(`Generated ${data.generated} variants from ${data.from_mappings} mappings`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const del = async (id) => {
    await axios.delete(`${API}/rate-variants/${id}`);
    toast.success("Removed"); load();
  };

  return (
    <div className="space-y-4" data-testid="chmgr-ratestructure">
      <div>
        <h2 className="text-xl font-bold">Rate Structure / Variants</h2>
        <p className="text-sm text-stone-500">Same rate plan → different occupancy / meal / cancel / tax combinations → OTA rate code. Required step after Channel Mapping (technical mapping ≠ price variation).</p>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm space-y-1">
        <div className="flex items-center gap-2 font-semibold text-blue-900"><Shield className="w-4 h-4" /> What this screen does</div>
        <div className="text-blue-800">Channel Mapping (another screen) links room+rate to a single code. Here we bind the same rate plan's different occupancy/meal/cancel/tax combinations to OTA codes.</div>
        <div className="text-blue-800 pt-1"><b>Example:</b> "Standard Rate" on Booking.com:</div>
        <ul className="list-disc list-inside text-blue-700 text-xs space-y-0.5">
          <li>2 pax + BB + Flexible → <code className="bg-blue-100 px-1 rounded">STD_BB_FLEX</code></li>
          <li>2 pax + RO + Non-Refundable → <code className="bg-blue-100 px-1 rounded">STD_RO_NR</code></li>
          <li>4 pax + BB + Flexible → <code className="bg-blue-100 px-1 rounded">STD_BB_FLEX_4PAX</code></li>
        </ul>
      </div>

      <div className="flex items-center gap-3">
        <button onClick={autoGen} className="px-4 py-2 bg-emerald-600 text-white rounded-xl text-sm font-semibold flex items-center gap-2" data-testid="chmgr-variants-autogen">
          <Zap className="w-4 h-4" /> Auto-generate from Mappings
        </button>
        <span className="text-xs text-stone-400">{rows.length} variants</span>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <div className="grid grid-cols-[auto,1fr,1fr,1fr,1fr,auto,auto] gap-3 px-4 py-3 bg-stone-50 text-xs font-semibold text-stone-500 uppercase tracking-wider">
          <div>ID</div><div>Channel</div><div>Internal Segment</div><div>Details</div><div>Room Code</div><div>Rate Code</div><div></div>
        </div>
        {rows.map(v => (
          <div key={v.id} className="grid grid-cols-[auto,1fr,1fr,1fr,1fr,auto,auto] gap-3 px-4 py-3 border-t border-stone-100 items-center text-sm">
            <div className="font-mono text-xs text-stone-400">{v.id.slice(0, 6)}</div>
            <div className="font-semibold">{channels.find(c => c.channel_id === v.channel_id)?.name || v.channel_id}</div>
            <div>{v.internal_segment}</div>
            <div className="text-xs text-stone-500">{v.occupancy}px · {v.meal_plan} · {v.cancellation}</div>
            <div className="font-mono text-xs">{v.channel_room_code}</div>
            <div className="font-mono text-xs font-bold">{v.channel_rate_code}</div>
            <button onClick={() => del(v.id)} className="text-rose-500" data-testid={`chmgr-var-del-${v.id.slice(0,6)}`}><Trash2 className="w-4 h-4" /></button>
          </div>
        ))}
        {rows.length === 0 && <div className="p-10 text-center text-sm text-stone-400">No variants yet — click <b>Auto-generate from Mappings</b> to populate.</div>}
      </div>
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

/* ═══════════ BENCHMARK ═══════════ */
const BenchmarkPanel = ({ pid }) => {
  const [data, setData] = useState(null);
  const [drift, setDrift] = useState(null);

  const load = useCallback(async () => {
    try {
      const [b, d] = await Promise.all([
        axios.get(`${API}/benchmark/${pid}`),
        axios.get(`${API}/nightly-drift/${pid}`),
      ]);
      setData(b.data); setDrift(d.data);
    } catch { /* */ }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const calc = async () => {
    try { await axios.post(`${API}/benchmark/${pid}/calculate`); toast.success("Snapshot captured"); load(); }
    catch { toast.error("Failed"); }
  };

  const runDrift = async () => {
    try {
      const { data } = await axios.post(`${API}/nightly-drift/${pid}/run-now`);
      toast.success(`Dry-run: ${data.channels_checked} channels · ${data.total_errors}/${data.total_items} errors · ${data.drift_alerts} alerts`);
      load();
    } catch { toast.error("Dry-run failed"); }
  };

  const cur = data?.current;
  const fmt = (v) => v == null ? "—" : v;
  const color = (v) => v == null ? "text-stone-400" : v >= 100 ? "text-emerald-600" : v >= 90 ? "text-amber-500" : "text-rose-600";
  const trend = (v) => v == null ? null : v >= 100 ? TrendingUp : TrendingDown;

  return (
    <div className="space-y-4" data-testid="chmgr-benchmark">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">Benchmark Cockpit</h2>
          <p className="text-sm text-stone-500">Compare performance against competitors (STR-style Occ/ADR/RevPAR index).</p>
        </div>
        <div className="flex gap-2">
          <button onClick={runDrift} className="px-4 py-2 bg-white border border-violet-300 text-violet-700 rounded-xl text-sm font-semibold flex items-center gap-2" data-testid="chmgr-drift-run">
            <Zap className="w-4 h-4" /> Run Nightly Dry-Run
          </button>
          <button onClick={calc} className="px-4 py-2 bg-emerald-600 text-white rounded-xl text-sm font-semibold flex items-center gap-2" data-testid="chmgr-bench-calc">
            <RefreshCw className="w-4 h-4" /> Calculate Snapshot
          </button>
        </div>
      </div>

      {/* Nightly Drift widget */}
      {drift?.latest && (
        <div className={`border rounded-xl p-5 ${drift.latest.drift_alerts?.length > 0 ? "bg-amber-50 border-amber-200" : "bg-emerald-50 border-emerald-200"}`} data-testid="chmgr-drift-widget">
          <div className="flex items-start gap-4">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${drift.latest.drift_alerts?.length > 0 ? "bg-amber-200 text-amber-800" : "bg-emerald-200 text-emerald-800"}`}>
              {drift.latest.drift_alerts?.length > 0 ? <AlertTriangle className="w-5 h-5" /> : <CheckCircle2 className="w-5 h-5" />}
            </div>
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <h3 className="font-bold">OTA Payload Drift — Nightly Dry-Run</h3>
                <span className="text-xs text-stone-500">{new Date(drift.latest.ran_at).toLocaleString()}</span>
              </div>
              <p className="text-sm mt-1">
                Checked <b>{drift.latest.channels_checked}</b> channels · <b>{drift.latest.total_errors}</b>/{drift.latest.total_items} items failed validation
                {drift.latest.drift_alerts?.length > 0
                  ? <span className="text-amber-900"> · <b>{drift.latest.drift_alerts.length}</b> channel{drift.latest.drift_alerts.length === 1 ? "" : "s"} over 5% error threshold</span>
                  : <span className="text-emerald-900"> · no drift alerts</span>}
              </p>
              {drift.latest.drift_alerts?.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {drift.latest.drift_alerts.map((a, i) => (
                    <Badge key={i} className="bg-amber-100 text-amber-800 border border-amber-300">{a.channel_id} · {a.err_pct}% err</Badge>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { l: "Occupancy Index", v: cur?.occupancy_index, our: cur?.our_occupancy, comp: cur?.compset_occupancy, suffix: "%" },
          { l: "ADR Index",       v: cur?.adr_index,       our: cur?.our_adr,       comp: cur?.compset_adr,       prefix: "£" },
          { l: "RevPAR Index",    v: cur?.revpar_index,    our: cur?.our_revpar,    comp: cur?.compset_revpar,    prefix: "£" },
        ].map(k => {
          const Trend = trend(k.v);
          return (
            <div key={k.l} className="bg-white border border-stone-200 rounded-xl p-6 text-center">
              <div className="text-sm text-stone-500 mb-2">{k.l}</div>
              <div className={`text-5xl font-bold mb-1 ${color(k.v)}`}>{fmt(k.v)}{k.v != null && <span className="text-2xl">…</span>}</div>
              {Trend && <Trend className={`w-5 h-5 mx-auto ${color(k.v)}`} />}
              <div className="flex justify-around mt-4 text-xs">
                <div><div className="text-stone-400">You</div><div className="font-semibold">{k.prefix || ""}{fmt(k.our)}{k.suffix || ""}</div></div>
                <div><div className="text-stone-400">Compset</div><div className="font-semibold">{k.prefix || ""}{fmt(k.comp)}{k.suffix || ""}</div></div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white border border-stone-200 rounded-xl p-5">
          <h3 className="font-bold mb-3 flex items-center gap-2"><AlertTriangle className="w-4 h-4 text-amber-500" /> Open Alerts ({data?.alerts?.length || 0})</h3>
          {(data?.alerts || []).length === 0 && <p className="text-sm text-stone-400 text-center py-6">No open alerts</p>}
          {(data?.alerts || []).map(a => (
            <div key={a.id} className="flex items-start gap-3 py-2 border-b border-stone-100 last:border-0">
              <AlertTriangle className="w-4 h-4 text-amber-500 mt-0.5" />
              <div className="flex-1 text-xs"><div className="font-semibold">{a.metric.toUpperCase()}</div><div className="text-stone-500">{a.message}</div></div>
            </div>
          ))}
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-5">
          <h3 className="font-bold mb-3">Recent Snapshots</h3>
          <div className="grid grid-cols-[1fr,auto,auto,auto] gap-2 text-xs font-semibold text-stone-500 pb-2 border-b">
            <div>Date</div><div>Occ</div><div>ADR</div><div>RevPAR</div>
          </div>
          {(data?.recent || []).slice(-6).reverse().map(s => (
            <div key={s.id} className="grid grid-cols-[1fr,auto,auto,auto] gap-2 text-xs py-1.5 border-b border-stone-50 last:border-0">
              <div>{s.snapshot_date}</div>
              <div className={color(s.occupancy_index)}>{s.occupancy_index}</div>
              <div className={color(s.adr_index)}>{s.adr_index}</div>
              <div className={color(s.revpar_index)}>{s.revpar_index}</div>
            </div>
          ))}
          {(!data?.recent || data.recent.length === 0) && <p className="text-center text-sm text-stone-400 py-6">No snapshots yet</p>}
        </div>
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
      {panel === "rate-structure" && <RateStructurePanel pid={pid} />}
      {panel === "publish-jobs"   && <PublishJobsPanel pid={pid} />}
      {panel === "audit-logs"     && <AuditLogsPanel pid={pid} />}
      {panel === "benchmark"      && <BenchmarkPanel pid={pid} />}
      {panel === "profiles"       && <ProfilesPanel pid={pid} />}
      {panel === "overrides"      && <OverridesPanel pid={pid} />}
    </div>
  );
};

export default ChannelManagerHub;
